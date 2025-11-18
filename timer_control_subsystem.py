# ===定时器控制子系统（核心1专属）=======
# 功能：从原main.py拆分所有定时器相关非阻塞任务，独立运行在核心1
# 保留原功能逻辑：时间输出、NTP校准、天气更新、传感器读取

# ===导入依赖模块=======
# 时间工具模块：提供秒级时间戳、延时功能
from utime import time, sleep_ms
# 硬件控制模块：提供低功耗接口
import machine
# 配置文件导入：定时任务相关配置
from config import (
    WEATHER_REFRESH_INTERVAL,
    NTP_CALIBRATION_HOURS,
    TIME_PRINT_INTERVAL,
    SENSOR_READ_INTERVAL
)
# 功能模块导入：复用原功能逻辑
import function.weather as weather_module
import function.ntp_clock as ntp_module
import function.multi_sensor as sensor_module

# ===定时任务时间戳缓存（从main.py迁移）=======
last_ntp_cal = 0          # 上一次NTP时钟校准的时间戳（秒级）
last_weather = 0          # 上一次天气查询的时间戳（秒级）
last_sensor_read = 0      # 上一次传感器数据读取的时间戳（秒级）
last_time_print = 0       # 上一次时间输出的时间戳（秒级，适配原TIME_PRINT_INTERVAL）

# ===定时任务工具函数 - 时间输出（从main.py迁移，适配非阻塞循环）=======
def _print_time(global_uart, verbose):
    """
    时间输出任务：按配置间隔输出当前时间并推送至串口屏
    适配修改：从定时器回调改为非阻塞循环触发
    """
    global last_time_print
    now = time()
    if now - last_time_print >= TIME_PRINT_INTERVAL:
        if verbose:
            print(f"[TIMER DEBUG] 触发时间输出（间隔{TIME_PRINT_INTERVAL}秒）")
        current_time = ntp_module.get_current_formatted_time()
        print(f"当前时间 {current_time}")
        ntp_module.send_time_to_serial_screen(global_uart)
        last_time_print = now

# ===定时任务工具函数 - 传感器读取（从main.py迁移，无修改）=======
def _read_sensor(sensor, global_uart, sensor_uart, verbose):
    """传感器定时读取函数（完全复用原逻辑）"""
    global last_sensor_read
    now = time()
    if now - last_sensor_read >= SENSOR_READ_INTERVAL:
        if verbose:
            print(f"[TIMER DEBUG] 触发传感器定时读取（间隔{SENSOR_READ_INTERVAL}秒）")
        if sensor and global_uart and sensor_uart:
            if verbose:
                print(f"[TIMER DEBUG] 调用传感器read_sensor_data（force=False）")
            sensor.read_sensor_data(global_uart)
            last_sensor_read = now
        else:
            if verbose:
                print(f"[TIMER DEBUG] 传感器读取条件不满足：sensor={sensor is not None}，global_uart={global_uart is not None}，sensor_uart={sensor_uart is not None}")

# ===全局轮询任务函数（从main.py迁移，适配非阻塞循环）=======
def _poll_tasks(global_uart, sensor, sensor_uart, verbose):
    """
    全局轮询任务：整合所有定时任务（完全复用原逻辑）
    适配修改：从定时器回调改为非阻塞循环触发
    """
    global last_ntp_cal, last_weather
    now = time()
    ntp_cal_sec = int(NTP_CALIBRATION_HOURS * 3600)
    
    # 1. NTP时钟校准任务
    if now - last_ntp_cal >= ntp_cal_sec:
        if verbose:
            print(f"[TIMER DEBUG] 触发NTP校准 周期 {NTP_CALIBRATION_HOURS}小时")
        if ntp_module.sync_ntp_to_rtc()[0]:
            last_ntp_cal = now
    
    # 2. 天气查询任务
    if now - last_weather >= WEATHER_REFRESH_INTERVAL:
        if verbose:
            print(f"[TIMER DEBUG] 触发天气查询（间隔{WEATHER_REFRESH_INTERVAL}秒）")
        weather_module.get_weather_by_ip(global_uart)
        last_weather = now
    
    # 3. 传感器数据读取任务
    _read_sensor(sensor, global_uart, sensor_uart, verbose)
    
    # 4. 时间输出任务
    _print_time(global_uart, verbose)

# ===核心入口：启动定时器控制子系统（核心1绑定）=======
def run_timer_control_subsystem(global_uart, sensor, sensor_uart, verbose):
    """
    启动定时器控制子系统（核心1专属）
    :param global_uart: 串口2实例（从main.py传入）
    :param sensor: 传感器实例（从main.py传入）
    :param sensor_uart: 串口1实例（从main.py传入）
    :param verbose: DEBUG开关（从main.py传入）
    核心逻辑：非阻塞循环，绑定核心1运行，调度所有定时任务
    """
    print("==================================")
    print(" 定时器控制子系统（核心1）启动中")
    print("==================================")
    print(f"  - 时间输出间隔 {TIME_PRINT_INTERVAL}秒")
    print(f"  - 天气查询间隔 {WEATHER_REFRESH_INTERVAL}秒")
    print(f"  - NTP校准周期 {NTP_CALIBRATION_HOURS}小时")
    print(f"  - 传感器读取间隔 {SENSOR_READ_INTERVAL}秒")
    print("==================================\n")
    
    # 初始化时间戳（设为当前时间，避免启动时立即触发任务）
    global last_ntp_cal, last_weather, last_sensor_read, last_time_print
    init_time = time()
    last_ntp_cal = init_time
    last_weather = init_time
    last_sensor_read = init_time
    last_time_print = init_time
    
    # 核心1专属非阻塞循环（绑定核心1，持续调度任务）
    while True:
        # 执行轮询任务（整合所有定时逻辑）
        _poll_tasks(global_uart, sensor, sensor_uart, verbose)
        # 低功耗空闲：降低核心1占用率（50毫秒，不影响任务实时性）
        machine.idle()
        sleep_ms(50)

# ===本地测试入口（仅验证框架可运行）=======
if __name__ == "__main__":
    try:
        print("启动定时器控制子系统（本地测试模式）...")
        # 测试时传入None占位，实际运行从main.py传入真实实例
        run_timer_control_subsystem(
            global_uart=None,
            sensor=None,
            sensor_uart=None,
            verbose=True
        )
    except KeyboardInterrupt:
        print("\n定时器控制子系统测试停止（用户主动中断）")