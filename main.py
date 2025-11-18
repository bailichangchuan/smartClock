import machine
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

# 全局变量定义
last_ntp_cal = 0
last_weather = 0
# 传感器相关全局变量（未启用）
# last_sensor_read = 0
# 传感器实例（未启用）
# sensor = None

# 时间输出回调：打印当前时间并发送到串口屏
def _print_time(timer):
    if VERBOSE:
        print(f"[DEBUG] 时间输出定时器触发")
    print(f"当前时间 {function.ntp_clock.get_current_formatted_time()}")
    # 调用NTP模块函数，向串口屏t0控件发送时间
    function.ntp_clock.send_time_to_serial_screen()

# 传感器读取回调（未启用）
# def _read_sensor():
#     """传感器数据读取 仅调用接口 输出由传感器包内部完成"""
#     global last_sensor_read
#     from config import SENSOR_READ_INTERVAL
#     
#     if time() - last_sensor_read < SENSOR_READ_INTERVAL:
#         return
#     
#     if VERBOSE:
#         print(f"[DEBUG] 触发传感器数据读取")
#     
#     try:
#         sensor.read_sensor_data(verbose=VERBOSE)
#         last_sensor_read = time()
#     except Exception as e:
#         if VERBOSE:
#             print(f"[DEBUG] 传感器读取异常：{str(e)}")

# 轮询任务回调：处理NTP校准、天气查询
def _poll_tasks(timer):
    global last_ntp_cal, last_weather
    now = time()
    ntp_cal_sec = int(NTP_CALIBRATION_HOURS * 3600)
    
    # NTP校准：按周期同步时间
    if now - last_ntp_cal >= ntp_cal_sec:
        if VERBOSE:
            print(f"[DEBUG] 触发NTP校准 周期 {NTP_CALIBRATION_HOURS}小时")
        if function.ntp_clock.sync_ntp_to_rtc()[0]:
            last_ntp_cal = now
    
    # 天气查询：按间隔获取天气
    if now - last_weather >= WEATHER_REFRESH_INTERVAL:
        if VERBOSE:
            print(f"[DEBUG] 触发天气查询")
        function.weather.get_weather_by_ip()
        last_weather = now
    
    # 传感器读取（未启用）
    # try:
    #     _read_sensor()
    # except Exception as e:
    #     if VERBOSE:
    #         print(f"[DEBUG] 轮询中传感器读取异常：{str(e)}")

# 传感器初始化（未启用）
# def _init_sensor():
#     """传感器初始化 独立函数 仅创建实例"""
#     global sensor, last_sensor_read
#     if VERBOSE:
#         print(f"[DEBUG] 开始初始化传感器")
#     
#     try:
#         from multi_sensor import MultiSensor
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

# 主函数：初始化服务并启动
def main():
    # 启动提示
    print("==================================")
    print(" 香港实时天气查询程序 - 启动成功")
    print("==================================")
    
    # WiFi连接
    print("\n==================================")
    print(" WiFi连接 - 正在连接")
    print("==================================")
    if not net_util.connect_wifi():
        print("\nWiFi连接失败 程序退出")
        return
    print("WiFi连接成功")
    print("==================================\n")
    
    # 传感器初始化（未启用）
    # print("\n==================================")
    # print(" 传感器模块 - 初始化中")
    # print("==================================\n")
    # sensor_init_ok = _init_sensor()
    # print(f"传感器初始化{'成功' if sensor_init_ok else '失败'} 注释状态")
    # print("==================================\n")
    
    # NTP首次校准
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
    
    # 初始化任务时间戳
    last_weather = time()
    # if sensor:
    #     last_sensor_read = time()
    
    # 启动定时器服务
    print("==================================")
    print(" 定时器服务 - 启动中")
    print("==================================")
    
    # 定时器0：定时输出时间并发送到串口屏
    machine.Timer(0).init(
        mode=machine.Timer.PERIODIC,
        period=TIME_PRINT_INTERVAL * 1000,
        callback=_print_time
    )
    print(f"时间输出服务启动 间隔 {TIME_PRINT_INTERVAL}秒")
    
    # 定时器1：周期执行轮询任务
    machine.Timer(1).init(
        mode=machine.Timer.PERIODIC,
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
    
    # 主程序挂起
    print("==================================")
    print(" 所有服务启动完成 持续运行中")
    print("==================================\n")
    while True:
        sleep(1)

if __name__ == "__main__":
    main()