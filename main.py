# ===导入依赖模块=======
# 硬件控制核心模块：提供UART串口、定时器、GPIO引脚等硬件操作接口
import machine
# 时间工具模块：提供秒级时间戳（time）和延时（sleep）功能
from utime import time, sleep
# 网络工具模块：封装WiFi连接逻辑（包含连接重试、状态判断）
import util.network as net_util
# 天气功能模块：封装IP定位天气查询、串口屏数据推送逻辑
import function.weather as weather_module
# NTP时钟模块：封装网络时间校准、时间格式化、串口屏时间推送逻辑
import function.ntp_clock as ntp_module
# 传感器功能模块：封装多传感器数据读取、解析、串口屏推送逻辑
import function.multi_sensor as sensor_module
# 串口屏监听模块：封装串口屏指令接收、解析及传感器联动控制逻辑
import ui.read_from_screen as read_screen_module
# 配置文件导入：统一管理所有可配置参数（避免硬编码，便于维护）
from config import (
    WEATHER_REFRESH_INTERVAL,
    NTP_CALIBRATION_HOURS,
    TIME_PRINT_INTERVAL,
    SERIAL_PORT,
    SERIAL_BAUD_RATE,
    SERIAL_TX_PIN,
    SERIAL_RX_PIN,
    UART_NUM,
    UART_BAUDRATE,
    UART_TX_PIN,
    UART_RX_PIN,
    SENSOR_READ_INTERVAL
)

# ===全局配置与共享变量定义=======
# 全局DEBUG输出控制开关：True=启用所有模块的DEBUG日志，False=关闭所有DEBUG输出
# 作用范围：main.py + multi_sensor.py + uart_reader.py + 其他依赖模块
VERBOSE = False

# 定时任务时间戳缓存：记录各任务上一次执行时间，用于控制执行间隔（避免重复触发）
last_ntp_cal = 0          # 上一次NTP时钟校准的时间戳（秒级）
last_weather = 0          # 上一次天气查询的时间戳（秒级）
last_sensor_read = 0      # 上一次传感器数据读取的时间戳（秒级）

# 全局核心实例缓存：跨函数共享的模块实例，避免重复初始化（提升性能）
global_uart = None        # 串口2实例：用于串口屏通信（时间、天气、传感器数据推送）
sensor = None             # 多传感器实例：传感器数据读取、解析的核心实例
sensor_uart = None        # 串口1实例：传感器专用通信端口（独立于串口2，避免冲突）

# ===定时任务工具函数 - 时间输出=======
def _print_time(timer):
    """
    定时器回调函数：周期性输出当前时间并推送至串口屏
    :param timer: 定时器实例（由系统自动传入，无需手动处理）
    逻辑流程：
    1. VERBOSE=True时，输出DEBUG日志（标记定时器触发）
    2. 调用NTP模块获取格式化时间字符串（如"2025-11-18 16:30:00"）
    3. 控制台打印当前时间（核心状态输出，不受VERBOSE控制）
    4. 推送格式化时间至串口屏，更新屏幕时间显示
    """
    if VERBOSE:
        print(f"[DEBUG] 时间输出定时器触发")
    current_time = ntp_module.get_current_formatted_time()
    print(f"当前时间 {current_time}")
    ntp_module.send_time_to_serial_screen(global_uart)

# ===定时任务工具函数 - 传感器读取=======
def _read_sensor():
    """
    传感器定时读取函数：按配置间隔触发传感器数据读取（独立函数，便于复用）
    逻辑流程：
    1. 引用全局变量last_sensor_read，获取上一次读取时间戳
    2. 计算当前时间与上次读取时间差，判断是否达到配置的读取间隔
    3. 达到间隔后，VERBOSE=True时输出DEBUG触发日志
    4. 校验核心实例（传感器、串口2、串口1）是否全部就绪
    5. 实例就绪：调用传感器读取方法，更新上次读取时间戳
    6. 实例未就绪：VERBOSE=True时输出DEBUG日志（说明未就绪原因）
    """
    global last_sensor_read
    now = time()
    if now - last_sensor_read >= SENSOR_READ_INTERVAL:
        if VERBOSE:
            print(f"[DEBUG] 触发传感器定时读取（间隔{SENSOR_READ_INTERVAL}秒）")
        if sensor and global_uart and sensor_uart:
            if VERBOSE:
                print(f"[DEBUG] 调用传感器read_sensor_data（force=False）")
            sensor.read_sensor_data(global_uart)
            last_sensor_read = now
        else:
            if VERBOSE:
                print(f"[DEBUG] 传感器读取条件不满足：sensor={sensor is not None}，global_uart={global_uart is not None}，sensor_uart={sensor_uart is not None}")

# ===主轮询任务函数=======
def _poll_tasks(timer):
    """
    全局轮询任务函数：整合所有定时任务（避免多个定时器冲突，便于管理）
    :param timer: 定时器实例（由系统自动传入，无需手动处理）
    整合任务：
    1. NTP时钟校准：按配置小时数周期性触发（校准系统时间）
    2. 天气查询：按配置秒数周期性触发（更新天气数据）
    3. 传感器读取：调用_read_sensor函数（更新传感器数据）
    逻辑特点：所有任务共享1秒周期定时器，通过时间戳控制各自执行间隔
    """
    global last_ntp_cal, last_weather
    now = time()
    # 将NTP校准周期（小时）转换为秒级时间戳（便于时间差计算）
    ntp_cal_sec = int(NTP_CALIBRATION_HOURS * 3600)
    
    # 1. NTP时钟校准任务
    if now - last_ntp_cal >= ntp_cal_sec:
        if VERBOSE:
            print(f"[DEBUG] 触发NTP校准 周期 {NTP_CALIBRATION_HOURS}小时")
        # 调用NTP校准方法，返回（校准成功标识，时区），成功则更新时间戳
        if ntp_module.sync_ntp_to_rtc()[0]:
            last_ntp_cal = now
    
    # 2. 天气查询任务
    if now - last_weather >= WEATHER_REFRESH_INTERVAL:
        if VERBOSE:
            print(f"[DEBUG] 触发天气查询")
        # 调用天气查询方法（按IP定位查询香港天气，推送至串口屏）
        weather_module.get_weather_by_ip(global_uart)
        last_weather = now
    
    # 3. 传感器数据读取任务（调用独立函数，降低耦合）
    _read_sensor()

# ===主函数（程序入口）=======
def main():
    """
    程序主函数：统一初始化所有核心模块，启动服务（按顺序执行，确保依赖正确）
    执行流程：
    1. 打印程序启动标识（必显，用户感知程序状态）
    2. WiFi连接（核心依赖，连接失败则退出程序）
    3. 串口2初始化（串口屏、天气、时间通信）
    4. 串口1初始化（传感器专用通信，独立端口避免冲突）
    5. 传感器实例初始化（传入串口1实例和VERBOSE开关）
    6. NTP时钟首次校准（阻塞式，确保程序启动时时间准确）
    7. 初始化定时任务时间戳（避免程序启动时立即触发重复任务）
    8. 启动串口屏监听子线程（异步处理串口屏指令，不阻塞主程序）
    9. 启动定时器服务（时间输出+全局轮询任务）
    10. 主程序挂起（持续运行，维持服务）
    """
    # 引用全局变量（需显式声明，否则视为局部变量）
    global global_uart, sensor, sensor_uart, last_ntp_cal, last_weather, last_sensor_read
    
    # 程序启动标识（必显，清晰告知用户程序启动状态）
    print("==================================")
    print(" 香港实时天气查询程序 - 启动成功")
    print("==================================")
    
    # 1. WiFi连接（核心依赖：NTP校准、天气查询需网络，连接失败直接退出）
    print("\n==================================")
    print(" WiFi连接 - 正在连接")
    print("==================================")
    if not net_util.connect_wifi():
        print("\nWiFi连接失败 程序退出")
        return
    print("WiFi连接成功")
    print("==================================\n")
    
    # 2. 串口2初始化（用于串口屏、天气数据、时间推送，核心通信端口）
    print("\n==================================")
    print(" 串口2初始化（串口屏/天气/时间）")
    print("==================================")
    try:
        global_uart = machine.UART(
            SERIAL_PORT,          # 串口编号（从config配置读取）
            baudrate=SERIAL_BAUD_RATE,  # 波特率（从config配置读取，需与串口屏一致）
            tx=machine.Pin(SERIAL_TX_PIN),  # TX引脚（从config配置读取）
            rx=machine.Pin(SERIAL_RX_PIN),  # RX引脚（从config配置读取）
            bits=8,               # 数据位：8位（串口标准配置）
            parity=None,          # 校验位：无（串口标准配置）
            stop=1,               # 停止位：1位（串口标准配置）
            timeout=100           # 读取超时：100ms（适配串口屏响应速度）
        )
        if VERBOSE:
            print(f"[MAIN DEBUG] 串口2初始化成功：端口{SERIAL_PORT} 波特率{SERIAL_BAUD_RATE}")
            print(f"[MAIN DEBUG] 串口2 TX：{SERIAL_TX_PIN} RX：{SERIAL_RX_PIN}")
        print("串口2初始化成功")
        print("==================================\n")
    except Exception as e:
        print(f"串口2初始化失败：{e}")
        return
    
    # 3. 串口1初始化（传感器专用，独立于串口2，避免通信冲突）
    print("\n==================================")
    print(" 串口1初始化（传感器专用）")
    print("==================================")
    try:
        sensor_uart = machine.UART(
            UART_NUM,             # 串口编号（从config配置读取，默认1）
            baudrate=UART_BAUDRATE,  # 波特率（从config配置读取，需与传感器一致）
            tx=machine.Pin(UART_TX_PIN),  # TX引脚（从config配置读取）
            rx=machine.Pin(UART_RX_PIN),  # RX引脚（从config配置读取）
            bits=8,               # 数据位：8位（传感器串口标准配置）
            parity=None,          # 校验位：无（传感器串口标准配置）
            stop=1,               # 停止位：1位（传感器串口标准配置）
            timeout=10            # 读取超时：10ms（适配传感器响应速度）
        )
        sensor_uart.write(b"")  # 发送空字节测试：验证引脚可用性（避免硬件占用冲突）
        if VERBOSE:
            print(f"[MAIN DEBUG] 串口1初始化成功：端口{UART_NUM} 波特率{UART_BAUDRATE}")
            print(f"[MAIN DEBUG] 串口1 TX：{UART_TX_PIN} RX：{UART_RX_PIN}")
        print("串口1初始化成功")
        print("==================================\n")
    except Exception as e:
        print(f"串口1初始化失败：{e}")
        print("请检查引脚是否被占用或硬件接线是否正确")
        print("==================================\n")
        sensor_uart = None
    
    # 4. 传感器实例初始化（传入串口1实例和全局VERBOSE开关，统一控制DEBUG）
    print("\n==================================")
    print(" 传感器初始化 - 启动中")
    print("==================================")
    try:
        # 创建传感器实例：传入串口1（通信端口）和VERBOSE（DEBUG控制）
        sensor = sensor_module.MultiSensor(uart=sensor_uart, verbose=VERBOSE)
        if VERBOSE:
            print(f"[MAIN DEBUG] 传感器实例创建成功")
        print("传感器初始化成功")
        print("==================================\n")
        
        # 启动后强制读取一次传感器数据（测试通信是否正常，仅VERBOSE=True时显式日志）
        if VERBOSE:
            print("\n[MAIN TEST] 强制读取传感器数据...")
        if sensor and global_uart:
            sensor.read_sensor_data(global_uart, force=True)
        else:
            if VERBOSE:
                print("[MAIN TEST] 强制读取失败：传感器或串口屏未就绪")
    except Exception as e:
        print(f"传感器初始化失败：{e}")
        sensor = None
        print("==================================\n")
    
    # 5. NTP时钟首次校准（阻塞式：确保程序启动时时间准确，后续按周期自动校准）
    print("\n==================================")
    print(" NTP时钟 - 首次校准中")
    print("==================================")
    while True:
        # 调用NTP校准方法：返回（校准成功标识，时区）
        success, tz = ntp_module.sync_ntp_to_rtc()
        if success:
            last_ntp_cal = time()  # 更新校准时间戳，避免重复校准
            print(f"NTP校准成功 时区 UTC+{tz:.1f}")
            print("==================================\n")
            break
        if VERBOSE:
            print(f"[MAIN DEBUG] NTP校准重试...")
        sleep(2)  # 校准失败时，2秒后重试（避免频繁重试占用资源）
    
    # 6. 初始化定时任务时间戳（设为当前时间，避免程序启动时立即触发任务）
    last_weather = time()
    last_sensor_read = time()
    
    # 7. 启动串口屏监听子线程（异步处理：避免阻塞主程序，实时响应串口屏指令）
    print("\n==================================")
    print(" 串口监听 - 启动子线程")
    print("==================================")
    try:
        # 启动监听线程：传入串口2（通信端口）和传感器实例（指令联动控制）
        read_screen_module.start_listen_thread(global_uart, sensor)
        if VERBOSE:
            print("[MAIN DEBUG] 监听子线程启动成功")
        print("串口屏监听子线程启动成功")
        print("==================================\n")
    except Exception as e:
        print(f"串口屏监听子线程启动失败：{e}")
        return
    
    # 8. 启动定时器服务（核心定时任务调度：时间输出+全局轮询）
    print("==================================")
    print(" 定时器服务 - 启动中")
    print("==================================")
    
    # 定时器0：时间输出服务（按配置间隔打印并推送时间）
    machine.Timer(0).init(
        mode=machine.Timer.PERIODIC,  # 模式：周期性触发
        period=TIME_PRINT_INTERVAL * 1000,  # 周期：配置秒数×1000（转换为毫秒）
        callback=_print_time  # 回调函数：_print_time（时间输出逻辑）
    )
    print(f"时间输出服务启动 间隔 {TIME_PRINT_INTERVAL}秒")
    
    # 定时器1：全局轮询任务服务（1秒周期，调度所有定时任务）
    machine.Timer(1).init(
        mode=machine.Timer.PERIODIC,  # 模式：周期性触发
        period=1000,  # 周期：1000毫秒（1秒，确保任务响应及时）
        callback=_poll_tasks  # 回调函数：_poll_tasks（整合所有定时任务）
    )
    print(f"轮询任务服务启动 周期 1秒")
    print(f"  - 天气查询间隔 {WEATHER_REFRESH_INTERVAL}秒")
    print(f"  - NTP校准周期 {NTP_CALIBRATION_HOURS}小时")
    print(f"  - 传感器读取间隔 {SENSOR_READ_INTERVAL}秒")
    print("==================================\n")
    
    # 9. 主程序挂起（持续运行，维持所有服务，避免程序退出）
    print("==================================")
    print(" 所有服务启动完成 持续运行中")
    print("  关键检查：")
    print(f"  1. 串口1引脚：TX={UART_TX_PIN}、RX={UART_RX_PIN}（需与硬件接线一致）")
    print(f"  2. 硬件接线：ESP32 TX({UART_TX_PIN}) → 传感器RX；ESP32 RX({UART_RX_PIN}) → 传感器TX")
    print(f"  3. 波特率：{UART_BAUDRATE}（需与传感器手册一致）")
    print("==================================\n")
    while True:
        sleep(1)  # 1秒延时：降低CPU占用率，同时维持程序运行

# ===程序启动入口=======
if __name__ == "__main__":
    """程序启动入口：直接调用主函数，启动所有核心服务"""
    main()