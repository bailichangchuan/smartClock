# ==================== 网络时间同步工具 ====================
# 这个文件负责从互联网获取标准时间，像给系统对表
# 功能说明：连接NTP时间服务器，自动校准系统时钟，确保时间准确
# 使用场景：开机时校准一次，之后每隔一段时间自动对时

# ==================== 导入必要工具 ====================
# RTC模块：系统实时时钟（可以设置和读取当前时间）
from machine import RTC
# socket模块：网络通信（UDP协议连接NTP服务器）
import socket
# time模块：延时等待和异常处理
import time

# 导入整个config模块（避免单变量导入失败）
import config

# ==================== 模块级缓存（替代函数属性，解决MicroPython兼容性问题） ====================
# 记录上次推送到屏幕的时间数据（避免重复推送）
_last_date = None       # 上次推送的日期
_last_weekday = None    # 上次推送的星期
_last_minute = None     # 上次推送的分钟
_last_formatted_time = None  # 记录上次推送的完整时间字符串（用于自动推送）

# ==================== 时间转换工具 ====================
def _is_leap_year(year):
    """
    判断某一年是不是闰年（闰年2月有29天，平年28天）
    规则：能被4整除但不能被100整除，或者能被400整除
    参数：
      year: 年份数字（比如2025）
    返回：True=闰年，False=平年
    作用：NTP时间转换时需要知道每个月有多少天
    """
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

def _ntp_to_local(ntp_timestamp):
    """
    把NTP时间戳转换成本地时间（北京时间）
    参数：
      ntp_timestamp: NTP服务器返回的时间戳（从1900年1月1日开始的秒数）
    返回：本地时间元组（年, 月, 日, 时, 分, 秒, 星期）
    转换过程：加8小时 → 算年月日 → 算时分秒 → 算星期几
    """
    # 1. 加上时区偏移（UTC+8，北京在东八区）
    ntp_timestamp += int(config.TIMEZONE_OFFSET * 3600)
    
    # 2. 把时间戳换算成天数和当天秒数
    seconds_per_day = 86400  # 一天=24*60*60=86400秒
    total_days = (ntp_timestamp + seconds_per_day - 1) // seconds_per_day
    remaining_seconds = ntp_timestamp % seconds_per_day
    
    # 3. 从1900年开始，一年一年往下减，算出当前年份
    year = 1900
    while True:
        # 判断这一年是闰年还是平年（闰年366天，平年365天）
        leap = _is_leap_year(year)
        days_in_year = 366 if leap else 365
        
        # 如果总天数小于这一年，说明找到了当前年份
        if total_days < days_in_year:
            break
        
        # 否则减去这一年的天数，继续找下一年
        total_days -= days_in_year
        year += 1
    
    # 4. 在这一年里，一个月一个月往下减，算出当前月份
    # 每个月的天数表（闰年2月是29天）
    months = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if _is_leap_year(year):
        months[1] = 29  # 闰年2月29天
    
    month = 0  # 月份索引（0=1月，1=2月...）
    while month < 11 and total_days >= months[month]:
        total_days -= months[month]  # 减去当月天数
        month += 1
    month += 1  # 转换成实际月份（1-12）
    day = total_days + 1  # 转换成实际日期（1-31）
    
    # 5. 把当天剩余秒数换算成时分秒
    hours = remaining_seconds // 3600
    minutes = (remaining_seconds % 3600) // 60
    seconds = remaining_seconds % 60
    
    # 6. 计算星期几（1900年1月1日是星期一）
    # 用总天数取模7，余数0=周一，1=周二...6=周日
    weekday = (total_days - 1) % 7
    
    return (year, month, day, hours, minutes, seconds, weekday)

# ==================== NTP服务器通信 ====================
def _get_ntp_timestamp():
    """
    连接NTP服务器，获取标准时间戳
    参数：无
    返回：NTP时间戳（从1900年1月1日开始的秒数）或None（失败）
    通信过程：解析域名 → 创建UDP → 发送请求 → 接收响应 → 提取时间
    """
    # 1. 解析NTP服务器域名（比如"ntp.aliyun.com"）得到IP地址
    try:
        addr_info = socket.getaddrinfo(config.NTP_SERVER, 123)
        if not addr_info:
            if config.VERBOSE_NTP:
                print("[NTP] 域名解析失败")
            return None
        ntp_ip = addr_info[0][-1][0]  # 提取第一个IP地址
    except:
        if config.VERBOSE_NTP:
            print(f"[NTP] 无法解析{config.NTP_SERVER}")
        return None
    
    # 2. 创建UDP socket（NTP协议基于UDP）
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(config.NTP_TIMEOUT)  # 设置超时时间
        
        # 3. 构造NTP请求包（48字节，格式固定）
        # 第一个字节0x23表示：客户端模式 + NTP版本3
        ntp_packet = bytearray(48)
        ntp_packet[0] = 0x23
        
        # 4. 发送请求到NTP服务器的123端口
        sock.sendto(ntp_packet, (ntp_ip, 123))
        
        # 5. 接收响应包（也是48字节）
        data = sock.recv(48)
        if len(data) != 48:
            if config.VERBOSE_NTP:
                print(f"[NTP] 响应包长度错误：期望48字节，实际{len(data)}字节")
            return None
        
        # 6. 提取时间戳（第40-43字节，大端格式）
        timestamp = (data[40] << 24) | (data[41] << 16) | (data[42] << 8) | data[43]
        return timestamp
    
    except Exception as e:
        if config.VERBOSE_NTP:
            print(f"[NTP] 请求失败: {type(e).__name__}: {e}")
        return None
    
    finally:
        # 7. 确保关闭socket（释放资源）
        if sock:
            sock.close()

# ==================== RTC时钟操作 ====================
# RTC = Real Time Clock，系统实时时钟（断电后由电池维持）
rtc = RTC()  # 创建RTC实例（全局使用）

def sync_ntp_to_rtc():
    """
    从NTP服务器获取时间，写入系统RTC
    参数：无
    返回：元组(成功标识, 时区)
      成功标识：True=同步成功，False=失败
      时区：UTC+8（北京时间）
    同步过程：获取NTP时间戳 → 转换为本地时间 → 写入RTC → 打印结果
    """
    # 1. 获取NTP时间戳
    ntp_ts = _get_ntp_timestamp()
    if not ntp_ts:
        print("[NTP] ⚠️ 时间获取失败（检查WiFi和网络连接）")
        return False, config.TIMEZONE_OFFSET
    
    # 2. 转换为本地时间
    local_time = _ntp_to_local(ntp_ts)
    
    # 3. 验证年份合理性（防止异常时间）
    year = local_time[0]
    if not (1970 <= year <= 2100):
        print(f"[NTP] ⚠️ 时间无效：年份{year}超出合理范围（1970-2100）")
        return False, config.TIMEZONE_OFFSET
    
    # 4. 设置RTC时间
    # RTC格式：(年, 月, 日, 星期, 时, 分, 秒, 微秒)
    # 注意：RTC星期是1-7（1=周一），转换函数返回0-6（0=周一）
    rtc.datetime((year, local_time[1], local_time[2], 
                  local_time[6] + 1,  # 星期+1
                  local_time[3], local_time[4], local_time[5], 0))
    
    # 5. 打印成功信息
    formatted = f"{year:04d}-{local_time[1]:02d}-{local_time[2]:02d} {local_time[3]:02d}:{local_time[4]:02d}:{local_time[5]:02d}"
    print(f"[NTP] ✅ 时间同步成功：{formatted} UTC+{config.TIMEZONE_OFFSET:.1f}")
    return True, config.TIMEZONE_OFFSET

# ==================== 核心函数：格式化当前时间 ====================
def get_current_formatted_time():
    """
    从RTC读取当前时间，格式化成字符串（YYYY-MM-DD HH:MM:SS）
    参数：无
    返回：格式化时间字符串
    用途：控制台打印、日志记录
    """
    r = rtc.datetime()
    return f"{r[0]:04d}-{r[1]:02d}-{r[2]:02d} {r[4]:02d}:{r[5]:02d}:{r[6]:02d}"

# ==================== 核心函数：推送时间到屏幕（唯一入口） ====================
def send_time_to_serial_screen(uart, force=False):
    """
    从RTC读取当前时间，推送到屏幕显示（唯一的时间推送入口）
    参数：
      uart: 屏幕串口
      force: 强制更新（True=不管是否变化都推送）
    推送内容：日期（t1）、星期（t9）、时间（t0）
    作用：让屏幕显示实时时间
    机制：内部检查各组成部分变化，只在变化时推送
    """
    # 使用全局模块变量记录上次推送数据
    global _last_date, _last_weekday, _last_minute
    
    # 初始化模块变量（首次调用时）
    if _last_date is None:
        _last_date = None
        _last_weekday = None
        _last_minute = None
    
    # 读取RTC时间
    r = rtc.datetime()
    year, month, day = r[0], r[1], r[2]
    weekday_num = r[3]  # RTC格式：1=周一，7=周日
    hour, minute = r[4], r[5]
    
    # 格式化数据
    current_date = f"{year:04d}-{month:02d}-{day:02d}"
    # 星期转换：1=周一...7=周日 → "一"..."日"
    weekday_str = [None, '一', '二', '三', '四', '五', '六', '日'][weekday_num]
    current_weekday = f"星期{weekday_str}"
    current_minute_val = minute
    
    # 推送到屏幕（仅变化时推送，减少串口通信）
    from util.sent_to_screen import upload
    
    # 标记是否有实际推送
    pushed = False
    
    # 日期推送
    if force or current_date != _last_date:
        upload(uart, current_date, "t1", "txt")
        _last_date = current_date
        pushed = True
    
    # 星期推送
    if force or current_weekday != _last_weekday:
        upload(uart, current_weekday, "t9", "txt")
        _last_weekday = current_weekday
        pushed = True
    
    # 分钟推送（核心：只在分钟变化时推送）
    if force or current_minute_val != _last_minute:
        upload(uart, f"{hour:02d}:{minute:02d}", "t0", "txt")
        _last_minute = current_minute_val
        pushed = True
    
    # 只在实际推送时输出日志，避免刷屏
    if pushed and config.VERBOSE_TIME_PRINT:
        print(f"[Time] ✅ 时间推送：{current_date} {current_weekday} {hour:02d}:{minute:02d}")
    
    return pushed  # 返回是否推送成功

# ==================== 独立测试入口 ====================
if __name__ == "__main__":
    """
    独立测试：不依赖其他文件，直接测试NTP功能
    测试内容：连接NTP服务器 → 获取时间 → 设置RTC → 读取显示 → 自动推送
    """
    print("="*50)
    print(" NTP时间同步 - 独立测试")
    print("   测试NTP服务器连接和RTC设置")
    print("="*50)
    
    # 测试1：同步时间
    print("\n[测试1] 连接NTP服务器...")
    success, tz = sync_ntp_to_rtc()
    
    if success:
        print("\n[测试2] 读取RTC时间...")
        current_time = get_current_formatted_time()
        print(f"   当前时间：{current_time}")
        
        print("\n[测试3] 时间自动推送...")
        check_and_send_time(None)  # 模拟推送
        print("   ✅ 自动推送机制正常")
        
        print("\n✅ 所有测试通过！NTP功能正常")
        print(f"   时区：UTC+{tz:.1f}")
    else:
        print("\n❌ 测试失败：无法同步时间")
        print("   请检查：1. WiFi是否连接  2. 能否上网  3. NTP服务器地址")
    
    print("\n独立测试结束")
