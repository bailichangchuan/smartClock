from machine import RTC
from utime import localtime, mktime
from util.network import get_ntp_time
rtc = RTC()
def set_time_from_ntp():
    ntp_time = get_ntp_time()
    if ntp_time:
        tm = localtime(ntp_time)
        rtc.datetime((tm[0], tm[1], tm[2], tm[6]+1, tm[3], tm[4], tm[5], 0))
        return True
    return False
def get_current_time():
    return mktime(rtc.datetime()[:7])
def format_time(tm):
    return "{:04}-{:02}-{:02} {:02}:{:02}:{:02}".format(tm[0], tm[1], tm[2], tm[3], tm[4], tm[5])
def get_formatted_current_time():
    return format_time(rtc.datetime()[:7])
def is_time_set():
    year = rtc.datetime()[0]
    return year > 2000
def wait_for_time_sync(timeout=30):
    import time
    start = time.time()
    while not is_time_set():
        if time.time() - start > timeout:
            return False
        set_time_from_ntp()
        time.sleep(1)
    return True