from machine import RTC
import socket
from config import NTP_SERVER, TIMEZONE_OFFSET, NTP_TIMEOUT

VERBOSE = False
rtc = RTC()

def _is_leap_year(year):
    # 判断闰年
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

def _ntp_to_local(ntp_ts):
    # NTP时间戳转换为本地时间元组
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
    # 获取NTP服务器UTC时间戳
    sock = None
    try:
        addr_info = socket.getaddrinfo(NTP_SERVER, 123)
        if not addr_info:
            return None
        ntp_ip = addr_info[0][-1][0]
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(NTP_TIMEOUT)
        ntp_packet = bytearray(48)
        ntp_packet[0] = 0x23  # NTP v4客户端模式
        sock.sendto(ntp_packet, (ntp_ip, 123))
        
        data = sock.recv(48)
        if len(data) != 48:
            return None
        # 解析大端序时间戳
        return (data[40] << 24) | (data[41] << 16) | (data[42] << 8) | data[43]
    except OSError:
        return None
    finally:
        if sock:
            sock.close()

def sync_ntp_to_rtc():
    # 同步NTP时间到RTC，返回成功状态和时区偏移
    ntp_ts = _get_ntp_timestamp()
    if not ntp_ts:
        print("ntp_clock NTP获取失败")
        return False, TIMEZONE_OFFSET
    
    local = _ntp_to_local(ntp_ts)
    if not (1970 <= local[0] <= 2100):
        print(f"ntp_clock 时间无效（年份：{local[0]}）")
        return False, TIMEZONE_OFFSET
    
    # RTC参数顺序：年 月 日 星期 时 分 秒 微秒
    rtc.datetime((local[0], local[1], local[2], local[6]+1, local[3], local[4], local[5], 0))
    
    formatted = f"{local[0]:04d}-{local[1]:02d}-{local[2]:02d} {local[3]:02d}:{local[4]:02d}:{local[5]:02d}"
    print(f"ntp_clock 校准成功：{formatted} UTC+{TIMEZONE_OFFSET:.1f}")
    return True, TIMEZONE_OFFSET

def get_current_formatted_time():
    # 获取当前RTC格式化时间
    r = rtc.datetime()
    return f"{r[0]:04d}-{r[1]:02d}-{r[2]:02d} {r[4]:02d}:{r[5]:02d}:{r[6]:02d}"