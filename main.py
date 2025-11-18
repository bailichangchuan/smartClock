import machine
from utime import time, sleep
import util.network as net_util
import function.weather as weather_module
import function.ntp_clock as ntp_module
import function.multi_sensor as sensor_module
import ui.read_from_screen as read_screen_module
from config import (
    WEATHER_REFRESH_INTERVAL,
    NTP_CALIBRATION_HOURS,
    TIME_PRINT_INTERVAL,
    # 串口2配置
    SERIAL_PORT,
    SERIAL_BAUD_RATE,
    SERIAL_TX_PIN,
    SERIAL_RX_PIN,
    # 传感器串口1配置（严格读取config）
    UART_NUM,
    UART_BAUDRATE,
    UART_TX_PIN,  # TX=3（config配置）
    UART_RX_PIN,  # RX=2（config配置）
    SENSOR_READ_INTERVAL
)

VERBOSE = False

# 全局变量定义
last_ntp_cal = 0
last_weather = 0
last_sensor_read = 0
global_uart = None    # 串口2
sensor = None         # 传感器实例
sensor_uart = None    # 串口1（传感器专用）

# ========== 1. 正确定义 _print_time 函数 ==========
def _print_time(timer):
    if VERBOSE:
        print(f"[DEBUG] 时间输出定时器触发")
    current_time = ntp_module.get_current_formatted_time()
    print(f"当前时间 {current_time}")
    ntp_module.send_time_to_serial_screen(global_uart)

# ========== 2. 正确定义 _read_sensor 函数（仅处理传感器读取） ==========
def _read_sensor():
    global last_sensor_read
    now = time()
    if now - last_sensor_read >= SENSOR_READ_INTERVAL:
        if VERBOSE:
            print(f"[DEBUG] 触发传感器定时读取（间隔{SENSOR_READ_INTERVAL}秒）")
        if sensor and global_uart and sensor_uart:
            print(f"[DEBUG] 调用传感器read_sensor_data（force=False）")
            sensor.read_sensor_data(global_uart)
            last_sensor_read = now
        else:
            print(f"[DEBUG] 传感器读取条件不满足：sensor={sensor is not None}，global_uart={global_uart is not None}，sensor_uart={sensor_uart is not None}")

# ========== 3. 正确定义 _poll_tasks 函数（整合所有定时任务，避免嵌套） ==========
def _poll_tasks(timer):
    global last_ntp_cal, last_weather
    now = time()
    ntp_cal_sec = int(NTP_CALIBRATION_HOURS * 3600)  # 转换为秒
    
    # NTP校准
    if now - last_ntp_cal >= ntp_cal_sec:
        if VERBOSE:
            print(f"[DEBUG] 触发NTP校准 周期 {NTP_CALIBRATION_HOURS}小时")
        if ntp_module.sync_ntp_to_rtc()[0]:
            last_ntp_cal = now
    
    # 天气查询
    if now - last_weather >= WEATHER_REFRESH_INTERVAL:
        if VERBOSE:
            print(f"[DEBUG] 触发天气查询")
        weather_module.get_weather_by_ip(global_uart)
        last_weather = now
    
    # 传感器读取
    _read_sensor()

# ========== 主函数 ==========
def main():
    global global_uart, sensor, sensor_uart, last_ntp_cal, last_weather, last_sensor_read
    
    print("==================================")
    print(" 香港实时天气查询程序 - 启动成功")
    print("（修复NameError + 串口1引脚配置正确）")
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
    
    # 初始化串口2
    print("\n==================================")
    print(" 串口2初始化（串口屏/天气/时间）")
    print("==================================")
    try:
        global_uart = machine.UART(
            SERIAL_PORT,
            baudrate=SERIAL_BAUD_RATE,
            tx=machine.Pin(SERIAL_TX_PIN),
            rx=machine.Pin(SERIAL_RX_PIN),
            bits=8,
            parity=None,
            stop=1,
            timeout=100
        )
        print(f"[MAIN DEBUG] 串口2初始化成功：端口{SERIAL_PORT} 波特率{SERIAL_BAUD_RATE}")
        print(f"[MAIN DEBUG] 串口2 TX：{SERIAL_TX_PIN} RX：{SERIAL_RX_PIN}")
        print("==================================\n")
    except Exception as e:
        print(f"[MAIN ERROR] 串口2初始化失败：{e}")
        return
    
    # 初始化串口1（传感器专用，严格使用config引脚）
    print("\n==================================")
    print(" 串口1初始化（传感器专用）")
    print("==================================")
    try:
        sensor_uart = machine.UART(
            UART_NUM,
            baudrate=UART_BAUDRATE,
            tx=machine.Pin(UART_TX_PIN),  # 读取config的UART_TX_PIN=3
            rx=machine.Pin(UART_RX_PIN),  # 读取config的UART_RX_PIN=2
            bits=8,
            parity=None,
            stop=1,
            timeout=10
        )
        sensor_uart.write(b"")  # 测试引脚可用性
        print(f"[MAIN DEBUG] 串口1初始化成功：端口{UART_NUM} 波特率{UART_BAUDRATE}")
        print(f"[MAIN DEBUG] 串口1 TX：{UART_TX_PIN}（config配置） RX：{UART_RX_PIN}（config配置）")
        print("==================================\n")
    except Exception as e:
        print(f"[MAIN ERROR] 串口1初始化失败：{e}")
        print("[MAIN ERROR] 请检查引脚是否被占用（如TX=3、RX=2是否可用）")
        print("==================================\n")
        sensor_uart = None
    
    # 传感器初始化
    print("\n==================================")
    print(" 传感器初始化 - 启动中")
    print("==================================")
    try:
        sensor = sensor_module.MultiSensor(uart=sensor_uart, verbose=VERBOSE)
        print(f"[MAIN DEBUG] 传感器实例创建成功")
        print("==================================\n")
        
        # 启动后立即强制读取一次
        print("\n[MAIN TEST] 强制读取传感器数据...")
        if sensor and global_uart:
            sensor.read_sensor_data(global_uart, force=True)
        else:
            print("[MAIN TEST] 强制读取失败：传感器或串口屏未就绪")
    except Exception as e:
        print(f"[MAIN ERROR] 传感器初始化失败：{e}")
        sensor = None
        print("==================================\n")
    
    # NTP首次校准
    print("\n==================================")
    print(" NTP时钟 - 首次校准中")
    print("==================================")
    while True:
        success, tz = ntp_module.sync_ntp_to_rtc()
        if success:
            last_ntp_cal = time()
            print(f"NTP校准成功 时区 UTC+{tz:.1f}")
            print("==================================\n")
            break
        print(f"[MAIN DEBUG] NTP校准重试...")
        sleep(2)
    
    # 初始化任务时间戳
    last_weather = time()
    last_sensor_read = time()
    
    # 启动串口屏监听子线程
    print("\n==================================")
    print(" 串口监听 - 启动子线程")
    print("==================================")
    try:
        read_screen_module.start_listen_thread(global_uart, sensor)
        print("[MAIN DEBUG] 监听子线程启动成功")
        print("==================================\n")
    except Exception as e:
        print(f"[MAIN ERROR] 监听子线程启动失败：{e}")
        return
    
    # 启动定时器服务（调用正确定义的_poll_tasks）
    print("==================================")
    print(" 定时器服务 - 启动中")
    print("==================================")
    
    # 定时器0：时间输出
    machine.Timer(0).init(
        mode=machine.Timer.PERIODIC,
        period=TIME_PRINT_INTERVAL * 1000,
        callback=_print_time
    )
    print(f"时间输出服务启动 间隔 {TIME_PRINT_INTERVAL}秒")
    
    # 定时器1：轮询任务（调用_poll_tasks，已正确定义）
    machine.Timer(1).init(
        mode=machine.Timer.PERIODIC,
        period=1000,
        callback=_poll_tasks
    )
    print(f"轮询任务服务启动 周期 1秒")
    print(f"  - 天气查询间隔 {WEATHER_REFRESH_INTERVAL}秒")
    print(f"  - NTP校准周期 {NTP_CALIBRATION_HOURS}小时")
    print(f"  - 传感器读取间隔 {SENSOR_READ_INTERVAL}秒")
    print("==================================\n")
    
    # 主程序挂起
    print("==================================")
    print(" 所有服务启动完成 持续运行中")
    print("  关键检查：")
    print(f"  1. 串口1引脚：TX={UART_TX_PIN}、RX={UART_RX_PIN}（需与硬件接线一致）")
    print(f"  2. 硬件接线：ESP32 TX({UART_TX_PIN}) → 传感器RX；ESP32 RX({UART_RX_PIN}) → 传感器TX")
    print("  3. 波特率：{UART_BAUDRATE}（需与传感器一致）")
    print("==================================\n")
    while True:
        sleep(1)

if __name__ == "__main__":
    main()