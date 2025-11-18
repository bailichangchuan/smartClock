from machine import RTC
import socket
import utime
from config import NTP_SERVER, TIMEZONE_OFFSET, NTP_TIMEOUT
from ui import sent_to_screen

VERBOSE = False
rtc = RTC()

# 存储上次更新状态 用于判断是否需要刷新显示
last_date = None
last_weekday = None
last_minute = None

def _is_leap_year(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

def _ntp_to_local(ntp_ts):
    ntp_ts += int(TIMEZONE_OFFSET * 3600)
    sec_per_day = 86400
    total_days = ntp_ts // sec_per_day
    remaining_secs = ntp_ts % sec_per_day
    
    hours = remaining_secs // 3600
    mins = (remaining_secs % 3600) // 60
    secs = remaining_secs % 60
    
    year = 1900
    while True:
        leap = _is_leap_year(year)
        days_in_year = 366 if leap else 365
        if total_days < days_in_year:
            break
        total_days -= days_in_year
        year += 1
    
    months = [31,28,31,30,31,30,31,31,30,31,30,31]
    if leap:
        months[1] = 29
    month = 0
    while month < 11 and total_days >= months[month]:
        total_days -= months[month]
        month += 1
    month += 1
    day = total_days + 1
    
    weekday = (1 + ntp_ts // sec_per_day) % 7
    return (year, month, day, hours, mins, secs, weekday)

def _get_ntp_timestamp():
    sock = None
    try:
        addr_info = socket.getaddrinfo(NTP_SERVER, 123)
        if not addr_info:
            return None
        ntp_ip = addr_info[0][-1][0]
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(NTP_TIMEOUT)
        ntp_packet = bytearray(48)
        ntp_packet[0] = 0x23
        sock.sendto(ntp_packet, (ntp_ip, 123))
        
        data = sock.recv(48)
        if len(data) != 48:
            return None
        return (data[40] << 24) | (data[41] << 16) | (data[42] << 8) | data[43]
    except OSError:
        return None
    finally:
        if sock:
            sock.close()

def sync_ntp_to_rtc():
    ntp_ts = _get_ntp_timestamp()
    if not ntp_ts:
        print("ntp_clock NTP获取失败")
        return False, TIMEZONE_OFFSET
    
    local = _ntp_to_local(ntp_ts)
    if not (1970 <= local[0] <= 2100):
        print("ntp_clock 时间无效")
        return False, TIMEZONE_OFFSET
    
    rtc.datetime((local[0], local[1], local[2], local[6]+1, local[3], local[4], local[5], 0))
    formatted = f"{local[0]:04d}-{local[1]:02d}-{local[2]:02d} {local[3]:02d}:{local[4]:02d}:{local[5]:02d}"
    print(f"ntp_clock 校准成功：{formatted} UTC+{TIMEZONE_OFFSET:.1f}")
    return True, TIMEZONE_OFFSET

def get_current_formatted_time():
    r = rtc.datetime()
    return f"{r[0]:04d}-{r[1]:02d}-{r[2]:02d} {r[4]:02d}:{r[5]:02d}:{r[6]:02d}"

def send_time_to_serial_screen(uart, force=False):  # 核心：新增force参数，默认False（原有逻辑）
    global last_date, last_weekday, last_minute
    r = rtc.datetime()
    
    # 解析当前时间参数
    year, month, day = r[0], r[1], r[2]
    weekday_num = r[3]
    hour, minute = r[4], r[5]
    
    # 格式化关键对比参数
    current_date = f"{year:04d}-{month:02d}-{day:02d}"
    current_weekday = [None, '一', '二', '三', '四', '五', '六', '日'][weekday_num]
    current_minute_val = minute  # 避免变量名与函数参数冲突（优化可读性）
    
    
    # ===日期更新（t0）=== 强制更新或数据变化时发送
    if force or current_date != last_date:
        sent_to_screen.upload(uart, current_date, control_name="t0", property_name="txt")  # 传入uart
        last_date = current_date
    
    
    # ===星期更新（t1）=== 强制更新或数据变化时发送
    if force or current_weekday != last_weekday:
        weekday_str = f"星期{current_weekday}"
        sent_to_screen.upload(uart, weekday_str, control_name="t1", property_name="txt")  # 传入uart
        last_weekday = current_weekday
       
    
    # ===时间更新（t2）=== 强制更新或数据变化时发送
    if force or current_minute_val != last_minute:
        time_str = f"{hour:02d}:{minute:02d}"
        sent_to_screen.upload(uart, time_str, control_name="t2", property_name="txt")  # 传入uart
        last_minute = current_minute_val