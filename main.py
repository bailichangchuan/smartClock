from machine import Timer
from utime import time, sleep
import util.network as net_util
import function.weather
import function.ntp_clock
from config import (
    WEATHER_REFRESH_INTERVAL,
    NTP_CALIBRATION_HOURS,
    TIME_PRINT_INTERVAL,
)

VERBOSE = False

# ==================== 全局变量定义 ====================
last_ntp_cal = 0
last_weather = 0
# 传感器相关全局变量
# last_sensor_read = 0
# 传感器实例
# sensor = None

# ==================== 时间输出回调 ====================
def _print_time(timer):
    if VERBOSE:
        print(f"[DEBUG] 时间输出定时器触发")
    print(f"当前时间 {function.ntp_clock.get_current_formatted_time()}")

# ==================== 传感器读取回调 ====================
# def _read_sensor():
#     """传感器数据读取 仅调用接口 输出由传感器包内部完成"""
#     global last_sensor_read
#     from config import SENSOR_READ_INTERVAL
#     
#     # 检查读取间隔
#     if time() - last_sensor_read < SENSOR_READ_INTERVAL:
#         return
#     
#     if VERBOSE:
#         print(f"[DEBUG] 触发传感器数据读取")
#     
#     try:
#         # 仅调用读取接口 不处理具体数据
#         sensor.read_sensor_data(verbose=VERBOSE)
#         last_sensor_read = time()
#     except Exception as e:
#         if VERBOSE:
#             print(f"[DEBUG] 传感器读取异常：{str(e)}")

# ==================== 轮询任务回调 ====================
def _poll_tasks(timer):
    global last_ntp_cal, last_weather
    now = time()
    ntp_cal_sec = int(NTP_CALIBRATION_HOURS * 3600)
    
    # ==================== NTP校准 ====================
    if now - last_ntp_cal >= ntp_cal_sec:
        if VERBOSE:
            print(f"[DEBUG] 触发NTP校准 周期 {NTP_CALIBRATION_HOURS}小时")
        if function.ntp_clock.sync_ntp_to_rtc()[0]:
            last_ntp_cal = now
    
    # ==================== 天气查询 ====================
    if now - last_weather >= WEATHER_REFRESH_INTERVAL:
        if VERBOSE:
            print(f"[DEBUG] 触发天气查询")
        function.weather.get_weather_by_ip()
        last_weather = now
    
    # ==================== 传感器读取 ====================
    # try:
    #     _read_sensor()
    # except Exception as e:
    #     if VERBOSE:
    #         print(f"[DEBUG] 轮询中传感器读取异常：{str(e)}")

# ==================== 传感器初始化 ====================
# def _init_sensor():
#     """传感器初始化 独立函数 仅创建实例"""
#     global sensor, last_sensor_read
#     if VERBOSE:
#         print(f"[DEBUG] 开始初始化传感器")
#     
#     try:
#         # 传感器包自行读取config.py配置 无需main.py传递参数
#         from multi_sensor import MultiSensor
#         # 直接初始化
#         sensor = MultiSensor()
#         last_sensor_read = time()
#         if VERBOSE:
#             print(f"[DEBUG] 传感器初始化成功")
#         return True
#     except ImportError as e:
#         if VERBOSE:
#             print(f"[DEBUG] 传感器模块导入失败：{str(e)}")
#     except Exception as e:
#         if VERBOSE:
#             print(f"[DEBUG] 传感器初始化失败：{str(e)}")
#     return False

# ==================== 主函数 ====================
def main():
    # ==================== 启动提示 ====================
    print("==================================")
    print(" 香港实时天气查询程序 - 启动成功")
    print("==================================")
    
    # ==================== WiFi连接 ====================
    print("\n==================================")
    print(" WiFi连接 - 正在连接")
    print("==================================")
    if not net_util.connect_wifi():
        print("\nWiFi连接失败 程序退出")
        return
    print("WiFi连接成功")
    print("==================================\n")
    
    # ==================== 传感器初始化 ====================
    # print("\n==================================")
    # print(" 传感器模块 - 初始化中")
    # print("==================================")
    # sensor_init_ok = _init_sensor()
    # if sensor_init_ok:
    #     print("传感器初始化成功 注释状态")
    # else:
    #     print("传感器初始化失败 注释状态")
    # print("==================================\n")
    
    # ==================== NTP首次校准 ====================
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
        if VERBOSE:
            print(f"[DEBUG] NTP校准重试...")
        sleep(2)
    
    # ==================== 初始化任务时间戳 ====================
    last_weather = time()
    # if sensor:
    #     last_sensor_read = time()
    
    # ==================== 启动定时器服务 ====================
    print("==================================")
    print(" 定时器服务 - 启动中")
    print("==================================")
    
    # 定时器0：时间输出
    Timer(0).init(
        mode=Timer.PERIODIC,
        period=TIME_PRINT_INTERVAL * 1000,
        callback=_print_time
    )
    print(f"时间输出服务启动 间隔 {TIME_PRINT_INTERVAL}秒")
    
    # 定时器1：轮询任务
    Timer(1).init(
        mode=Timer.PERIODIC,
        period=1000,
        callback=_poll_tasks
    )
    print(f"轮询任务服务启动 周期 1秒")
    print(f"  - 天气查询间隔 {WEATHER_REFRESH_INTERVAL}秒")
    print(f"  - NTP校准周期 {NTP_CALIBRATION_HOURS}小时")
    # if sensor:
    #     from config import SENSOR_READ_INTERVAL
    #     print(f"  - 传感器读取间隔 {SENSOR_READ_INTERVAL}秒")
    
    print("==================================\n")
    
    # ==================== 主程序挂起 ====================
    print("==================================")
    print(" 所有服务启动完成 持续运行中")
    print("==================================\n")
    while True:
        sleep(1)

if __name__ == "__main__":
    main()