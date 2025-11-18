# ===导入依赖模块=======
# 硬件时钟模块：提供RTC（实时时钟）操作接口（设置/读取系统时间）
from machine import RTC
# 网络通信模块：提供UDP Socket接口（NTP协议基于UDP）和域名解析
import socket
# 时间工具模块：提供时间相关辅助（无直接调用，保留原依赖）
import utime
# 配置文件导入：NTP服务器地址、时区偏移、请求超时（统一管理）
from config import NTP_SERVER, TIMEZONE_OFFSET, NTP_TIMEOUT
# 串口屏推送工具：封装串口屏数据上传逻辑（推送时间数据到指定控件）
from ui import sent_to_screen

# ===模块配置与全局变量=======
# DEBUG日志控制开关：当前为模块级开关，建议后续与main.py全局VERBOSE对齐（保持原逻辑不修改）
# 作用：控制NTP通信、时间转换的DEBUG日志输出，True启用，False关闭
VERBOSE = False
# RTC实例：系统实时时钟核心对象（用于设置/读取本地时间）
rtc = RTC()

# 时间数据缓存：记录上一次推送至串口屏的数据（避免重复推送，减少串口通信量）
last_date = None       # 上一次推送的日期（格式：YYYY-MM-DD）
last_weekday = None    # 上一次推送的星期（格式：“一”“二”...“日”）
last_minute = None     # 上一次推送的分钟数（用于判断时间是否变化，避免每秒重复推送）

# ===辅助工具函数：闰年判断=======
def _is_leap_year(year):
    """
    判断指定年份是否为闰年（用于NTP时间转本地时间时计算月份天数）
    :param year: 待判断年份（整数，如2025）
    :return: True=闰年，False=平年
    闰年判断规则：
    1. 能被4整除但不能被100整除；
    2. 能被400整除（例外情况，如2000年是闰年，1900年不是）
    """
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

# ===辅助工具函数：NTP时间戳转本地时间=======
def _ntp_to_local(ntp_ts):
    """
    将NTP时间戳转换为本地时间（含时区偏移、日期计算、星期计算）
    :param ntp_ts: NTP服务器返回的时间戳（秒级，从1900年1月1日00:00:00开始）
    :return: 本地时间元组 (年, 月, 日, 时, 分, 秒, 星期)
    转换逻辑：
    1. 叠加时区偏移（将UTC时间转为本地时间）；
    2. 拆分总秒数为“总天数”和“当日剩余秒数”；
    3. 从1900年开始计算实际年份（累计每年天数，直到总天数小于当年天数）；
    4. 计算当年实际月份（累计每月天数，直到总天数小于当月天数）；
    5. 计算当日时分秒（拆分当日剩余秒数）；
    6. 计算星期（NTP时间戳起始日为1900-01-01，对应星期一，按总天数取模）
    """
    # 步骤1：叠加时区偏移（UTC时间 + 时区偏移秒数 = 本地时间）
    ntp_ts += int(TIMEZONE_OFFSET * 3600)
    # 常量定义：一天的总秒数（24*60*60=86400）
    sec_per_day = 86400
    # 步骤2：拆分总秒数为“总天数”和“当日剩余秒数”（修改1：向上取整，避免跨天少算1天）
    total_days = (ntp_ts + sec_per_day - 1) // sec_per_day
    remaining_secs = ntp_ts % sec_per_day
    
    # 步骤3：计算当日时分秒（拆分剩余秒数）
    hours = remaining_secs // 3600          # 小时（0-23）
    mins = (remaining_secs % 3600) // 60    # 分钟（0-59）
    secs = remaining_secs % 60              # 秒（0-59）
    
    # 步骤4：计算实际年份（从1900年开始累计）
    year = 1900
    while True:
        leap = _is_leap_year(year)          # 判断当前年份是否为闰年
        days_in_year = 366 if leap else 365# 当年总天数（闰年366天，平年365天）
        if total_days < days_in_year:       # 总天数小于当年天数，找到目标年份
            break
        total_days -= days_in_year          # 总天数减去当年天数，继续查找下一年
        year += 1
    
    # 步骤5：计算实际月份（按月份累计天数）
    months = [31,28,31,30,31,30,31,31,30,31,30,31]  # 平年各月天数
    if leap:
        months[1] = 29  # 闰年2月改为29天
    month = 0  # 月份索引（0-11，对应1-12月）
    while month < 11 and total_days >= months[month]:
        total_days -= months[month]  # 总天数减去当月天数
        month += 1
    month += 1  # 转换为实际月份（1-12）
    day = total_days + 1  # 转换为实际日期（1-31）
    
    # 步骤6：计算星期（修改2：用修正后的total_days，(total_days-1)%7确保索引正确）
    # 逻辑：NTP起始日1900-01-01为周一 → total_days-1后取模，0=周一、2=周三
    weekday = (total_days - 1) % 7
    # 返回本地时间元组（年, 月, 日, 时, 分, 秒, 星期）
    return (year, month, day, hours, mins, secs, weekday)

# ===核心辅助函数：获取NTP服务器时间戳=======
def _get_ntp_timestamp():
    """
    向NTP服务器发送UDP请求，获取原始NTP时间戳
    :return: NTP时间戳（整数，秒级）/ None（请求失败/响应无效）
    通信逻辑：
    1. 解析NTP服务器域名，获取IP地址；
    2. 创建UDP Socket，设置超时时间（从config读取）；
    3. 构造NTP请求包（48字节，首字节0x23表示客户端请求）；
    4. 发送请求到NTP服务器123端口（NTP协议默认端口）；
    5. 接收响应包（48字节），提取时间戳字段（第40-43字节，大端序）；
    6. 异常处理：捕获网络异常，确保Socket最终关闭；
    """
    sock = None  # 初始化Socket实例（避免未创建时关闭报错）
    try:
        # 步骤1：解析NTP服务器域名，获取IP地址（返回地址信息列表）
        addr_info = socket.getaddrinfo(NTP_SERVER, 123)
        if not addr_info:  # 域名解析失败，返回None
            if VERBOSE:
                print("[NTP DEBUG] NTP服务器域名解析失败")
            return None
        # 提取第一个IP地址（IPv4）
        ntp_ip = addr_info[0][-1][0]
        
        # 步骤2：创建UDP Socket（AF_INET=IPv4，SOCK_DGRAM=UDP）
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 设置Socket超时时间（避免网络阻塞）
        sock.settimeout(NTP_TIMEOUT)
        # 步骤3：构造NTP请求包（48字节，符合NTP协议v3标准）
        ntp_packet = bytearray(48)
        ntp_packet[0] = 0x23  # 首字节：0b00100011（客户端模式，版本3）
        # 步骤4：发送请求到NTP服务器（IP+123端口）
        sock.sendto(ntp_packet, (ntp_ip, 123))
        
        # 步骤5：接收响应包（预期48字节，否则视为无效）
        data = sock.recv(48)
        if len(data) != 48:
            if VERBOSE:
                print(f"[NTP DEBUG] NTP响应包长度无效（预期48字节，实际{len(data)}字节）")
            return None
        # 提取时间戳（第40-43字节，大端序，拼接为32位整数）
        return (data[40] << 24) | (data[41] << 16) | (data[42] << 8) | data[43]
    
    # 捕获网络异常（如超时、连接失败、接收失败等）
    except OSError:
        if VERBOSE:
            print("[NTP DEBUG] NTP请求网络异常（超时/连接失败）")
        return None
    finally:
        # 确保Socket最终关闭（释放网络资源）
        if sock:
            sock.close()

# ===核心函数：NTP时间同步到RTC实时时钟=======
def sync_ntp_to_rtc():
    """
    从NTP服务器获取时间，同步到系统RTC实时时钟
    :return: 元组 (同步成功标识, 时区偏移) → (True/False, TIMEZONE_OFFSET)
    同步逻辑：
    1. 调用_get_ntp_timestamp获取NTP时间戳；
    2. 时间戳无效：输出错误信息，返回同步失败；
    3. 转换本地时间：调用_ntp_to_local将时间戳转为本地时间元组；
    4. 时间有效性校验：年份需在1970-2100之间（避免异常时间）；
    5. 同步到RTC：设置RTC datetime（格式：(年,月,日,星期,时,分,秒,微秒)）；
    6. 输出同步成功信息（必显），返回同步成功；
    """
    # 步骤1：获取NTP时间戳
    ntp_ts = _get_ntp_timestamp()
    if not ntp_ts:  # 时间戳无效（None）
        print("NTP时间获取失败")
        return False, TIMEZONE_OFFSET
    
    # 步骤2：转换为本地时间
    local = _ntp_to_local(ntp_ts)
    # 步骤3：校验时间有效性（年份1970-2100，避免异常值）
    if not (1970 <= local[0] <= 2100):
        print(f"NTP时间无效（年份{local[0]}超出1970-2100范围）")
        return False, TIMEZONE_OFFSET
    
    # 步骤4：同步到RTC（RTC.datetime格式：(年,月,日,星期,时,分,秒,微秒)）
    # 注意：RTC星期格式为1-7（1=星期一，7=星期日），本地时间星期为0-6，需+1适配
    rtc.datetime((local[0], local[1], local[2], local[6]+1, local[3], local[4], local[5], 0))
    # 格式化同步成功信息（必显，便于用户确认）
    formatted = f"{local[0]:04d}-{local[1]:02d}-{local[2]:02d} {local[3]:02d}:{local[4]:02d}:{local[5]:02d}"
    print(f"NTP时间校准成功：{formatted} UTC+{TIMEZONE_OFFSET:.1f}")
    return True, TIMEZONE_OFFSET

# ===辅助函数：获取当前格式化时间字符串=======
def get_current_formatted_time():
    """
    从RTC读取当前时间，返回格式化字符串（用于控制台打印和时间输出）
    :return: 格式化时间字符串（格式：YYYY-MM-DD HH:MM:SS）
    逻辑：读取RTC datetime元组，按固定格式拼接字符串（补零确保两位显示）
    """
    # 读取RTC时间（元组格式：(年,月,日,星期,时,分,秒,微秒)）
    r = rtc.datetime()
    # 格式化字符串（年4位，月/日/时/分/秒各2位，补零）
    return f"{r[0]:04d}-{r[1]:02d}-{r[2]:02d} {r[4]:02d}:{r[5]:02d}:{r[6]:02d}"

# ===核心函数：推送当前时间到串口屏=======
def send_time_to_serial_screen(uart, force=False):
    """
    从RTC读取当前时间，推送至串口屏指定控件（t0=日期、t1=星期、t2=时间）
    :param uart: 串口屏专用UART实例（main.py中的串口2，用于数据推送）
    :param force: 强制更新标识（True=忽略数据变化检测，强制推送；False=仅数据变化时推送）
    :return: 无返回值（成功推送至串口屏，无失败输出）
    推送逻辑：
    1. 读取RTC当前时间；
    2. 格式化关键数据（日期：YYYY-MM-DD，星期：“一”“二”...，分钟数：用于判断变化）；
    3. 按控件映射推送：
       - t0：日期（仅日期变化或force=True时推送）；
       - t1：星期（仅星期变化或force=True时推送）；
       - t2：时间（仅分钟变化或force=True时推送，避免每秒重复推送）；
    4. 更新缓存：推送成功后更新对应缓存变量，避免重复推送；
    """
    # 引用模块级全局缓存变量（记录上一次推送数据）
    global last_date, last_weekday, last_minute
    # 读取RTC当前时间（元组格式：(年,月,日,星期,时,分,秒,微秒)）
    r = rtc.datetime()
    
    # 步骤1：解析当前时间关键参数
    year, month, day = r[0], r[1], r[2]          # 年、月、日
    weekday_num = r[3]                            # 星期（RTC格式：1=周一，7=周日）
    hour, minute = r[4], r[5]                     # 时、分
    
    # 步骤2：格式化关键对比参数（用于判断是否需要推送）
    current_date = f"{year:04d}-{month:02d}-{day:02d}"  # 日期字符串（YYYY-MM-DD）
    # 星期转换：RTC星期1-7 → 中文“一”“二”...“日”（索引0占位，对应RTC星期1-7）
    current_weekday = [None, '一', '二', '三', '四', '五', '六', '日'][weekday_num]
    current_minute_val = minute  # 分钟数（用于判断时间是否变化，避免每秒推送）
    
    # 推送1：日期 → 串口屏控件t0（仅日期变化或强制更新时推送）
    if force or current_date != last_date:
        sent_to_screen.upload(uart, current_date, control_name="t0", property_name="txt")
        last_date = current_date  # 更新日期缓存，避免重复推送
    
    # 推送2：星期 → 串口屏控件t1（仅星期变化或强制更新时推送）
    if force or current_weekday != last_weekday:
        weekday_str = f"星期{current_weekday}"  # 拼接星期字符串（如“星期一”）
        sent_to_screen.upload(uart, weekday_str, control_name="t1", property_name="txt")
        last_weekday = current_weekday  # 更新星期缓存
    
    # 推送3：时间 → 串口屏控件t2（仅分钟变化或强制更新时推送，避免每秒重复）
    if force or current_minute_val != last_minute:
        time_str = f"{hour:02d}:{minute:02d}"  # 时间字符串（HH:MM，补零）
        sent_to_screen.upload(uart, time_str, control_name="t2", property_name="txt")
        last_minute = current_minute_val  # 更新分钟缓存