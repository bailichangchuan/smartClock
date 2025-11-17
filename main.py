from machine import Timer
from utime import time, sleep
import util.network as net_util
import function.weather
import function.ntp_clock
from config import WEATHER_REFRESH_INTERVAL, NTP_CALIBRATION_HOURS, TIME_PRINT_INTERVAL

VERBOSE = False

# 全局变量（仅保留必需）
last_ntp_cal = 0
last_weather = 0

# 时间输出回调（极简）
def _print_time(timer):
    print(f"当前时间 {function.ntp_clock.get_current_formatted_time()}")

# 轮询任务回调（合并NTP+天气）
def _poll_tasks(timer):
    global last_ntp_cal, last_weather
    now = time()
    ntp_cal_sec = int(NTP_CALIBRATION_HOURS * 3600)
    
    # NTP校准
    if now - last_ntp_cal >= ntp_cal_sec:
        if VERBOSE:
            print(f"触发NTP校准 周期 {NTP_CALIBRATION_HOURS}小时")
        if function.ntp_clock.sync_ntp_to_rtc()[0]:
            last_ntp_cal = now
    
    # 天气查询
    if now - last_weather >= WEATHER_REFRESH_INTERVAL:
        if VERBOSE:
            print("触发天气查询")
        function.weather.get_weather_by_ip()
        last_weather = now

def main():
    # ===== 启动提示 =====
    print("==================================")
    print(" 香港实时天气查询程序 - 启动成功")
    print("==================================")
    
    # ===== WiFi连接 =====
    if not net_util.connect_wifi():
        print("\nWiFi连接失败 程序退出")
        return
    
    # ===== NTP首次校准 =====
    print("\n==================================")
    print(" NTP时钟 - 首次校准中")
    print("==================================")
    while True:
        success, tz = function.ntp_clock.sync_ntp_to_rtc()
        if success:
            last_ntp_cal = time()
            print(f"NTP校准成功 时区 UTC+{tz:.1f}")
            print("==================================\n")
            break
        sleep(2)
    
    # ===== 启动服务（2个定时器） =====
    # 定时器0：时间输出
    Timer(0).init(
        mode=Timer.PERIODIC,
        period=TIME_PRINT_INTERVAL * 1000,
        callback=_print_time
    )
    print(f"时间输出 间隔 {TIME_PRINT_INTERVAL}秒")
    
    # 初始化天气查询时间
    last_weather = time()
    
    # 定时器1：轮询任务
    Timer(1).init(
        mode=Timer.PERIODIC,
        period=1000,
        callback=_poll_tasks
    )
    print(f"天气查询 间隔 {WEATHER_REFRESH_INTERVAL}秒")
    print(f"NTP校准 周期 {NTP_CALIBRATION_HOURS}小时")
    
    # ===== 主程序挂起 =====
    print("\n==================================")
    print(" 所有服务启动完成 持续运行中")
    print("==================================")
    while True:
        sleep(1)

if __name__ == "__main__":
    main()