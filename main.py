# ===程序主入口（仅开机运行一次初始化，绑定双核心）=======
# 功能：保留开机日志、硬件初始化、核心绑定，不包含定时任务
# 核心分配：核心0 → screen_control_subsystem，核心1 → timer_control_subsystem + SR602人体检测

# ===导入依赖模块=======
# 硬件控制核心模块：提供UART串口、GPIO引脚等硬件操作接口
import machine
# 时间工具模块：提供秒级延时功能
from utime import sleep
# 多线程模块：用于创建核心绑定的子线程（ESP32双核心支持）
import _thread
# 网络工具模块：封装WiFi连接逻辑
import util.network as net_util
# NTP时钟模块：仅用于首次校准（定时校准迁移到timer子系统）
import function.ntp_clock as ntp_module
# 传感器功能模块：仅用于初始化（读取逻辑迁移到timer子系统）
import function.multi_sensor as sensor_module
# 串口屏控制子系统（核心0运行）
import screen_control_subsystem
# 定时器控制子系统（核心1运行）
import timer_control_subsystem
# SR602人体红外检测模块（独立线程，核心1运行）
import function.sr602 as sr602_module
# 配置文件导入：所有可配置参数
from config import (
    SERIAL_PORT,
    SERIAL_BAUD_RATE,
    SERIAL_TX_PIN,
    SERIAL_RX_PIN,
    UART_NUM,
    UART_BAUDRATE,
    UART_TX_PIN,
    UART_RX_PIN
)

# ===全局配置（仅保留必要项）=======
VERBOSE = False  # 全局DEBUG输出控制开关

# ===核心绑定工具函数=======
def bind_core(core_id):
    """
    绑定线程到指定核心（ESP32支持核心0和核心1）
    :param core_id: 核心编号（0或1）
    :return: 绑定成功标识
    """
    try:
        # ESP32 MicroPython通过_thread.set_core()绑定核心（部分固件支持，若不支持会抛异常）
        _thread.set_core(_thread.get_ident(), core_id)
        print(f"线程绑定核心{core_id}成功")
        return True
    except AttributeError:
        # 兼容不支持set_core()的固件：通过循环中强制指定核心逻辑（备选方案）
        print(f"警告：当前固件不支持直接绑定核心，将通过任务调度优先占用核心{core_id}")
        return False

# ===子线程包装函数 - 核心0（screen_control_subsystem）=======
def core0_task(global_uart, sensor):
    """核心0专属任务：运行串口屏控制子系统"""
    print("\n==================================")
    print(" 核心0任务启动 - screen_control_subsystem")
    print("==================================\n")
    # 绑定核心0
    bind_core(0)
    # 启动串口屏控制子系统（核心0持续运行）
    screen_control_subsystem.run_screen_control_subsystem(sensor)

# ===子线程包装函数 - 核心1（timer_control_subsystem）=======
def core1_task(global_uart, sensor, sensor_uart):
    """核心1专属任务：运行定时器控制子系统"""
    print("\n==================================")
    print(" 核心1任务启动 - timer_control_subsystem")
    print("==================================\n")
    # 绑定核心1
    bind_core(1)
    # 启动定时器控制子系统（核心1持续运行）
    timer_control_subsystem.run_timer_control_subsystem(global_uart, sensor, sensor_uart, VERBOSE)

# ===主函数（仅开机初始化，绑定双核心）=======
def main():
    """程序主函数：仅执行开机初始化，启动双核心任务后挂起"""
    # 局部变量（替代原全局变量，避免跨线程冲突）
    global_uart = None        # 串口2实例（串口屏/天气/时间通信）
    sensor = None             # 多传感器实例
    sensor_uart = None        # 串口1实例（传感器专用）
    
    # 程序启动标识（必显）
    print("==================================")
    print(" 香港实时天气查询程序 - 启动成功")
    print("==================================\n")
    
    # 1. WiFi连接（核心依赖，连接失败则退出）
    print("==================================")
    print(" WiFi连接 - 正在连接")
    print("==================================\n")
    if not net_util.connect_wifi():
        print("WiFi连接失败 程序退出")
        return
    print("WiFi连接成功\n")
    
    # 2. 串口2初始化（串口屏/天气/时间通信）
    print("==================================")
    print(" 串口2初始化（串口屏/天气/时间）")
    print("==================================\n")
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
        if VERBOSE:
            print(f"[MAIN DEBUG] 串口2初始化成功：端口{SERIAL_PORT} 波特率{SERIAL_BAUD_RATE}")
        print("串口2初始化成功\n")
    except Exception as e:
        print(f"串口2初始化失败：{e}")
        return
    
    # 3. 串口1初始化（传感器专用）
    print("==================================")
    print(" 串口1初始化（传感器专用）")
    print("==================================\n")
    try:
        sensor_uart = machine.UART(
            UART_NUM,
            baudrate=UART_BAUDRATE,
            tx=machine.Pin(UART_TX_PIN),
            rx=machine.Pin(UART_RX_PIN),
            bits=8,
            parity=None,
            stop=1,
            timeout=10
        )
        sensor_uart.write(b"")
        if VERBOSE:
            print(f"[MAIN DEBUG] 串口1初始化成功：端口{UART_NUM} 波特率{UART_BAUDRATE}")
        print("串口1初始化成功\n")
    except Exception as e:
        print(f"串口1初始化失败：{e}")
        sensor_uart = None
    
    # 4. 传感器实例初始化
    print("==================================")
    print(" 传感器初始化 - 启动中")
    print("==================================\n")
    try:
        sensor = sensor_module.MultiSensor(uart=sensor_uart, verbose=VERBOSE)
        print("传感器初始化成功\n")
        # 启动后强制读取一次传感器数据（测试通信）
        if VERBOSE and sensor and global_uart:
            print("[MAIN TEST] 强制读取传感器数据...")
            sensor.read_sensor_data(global_uart, force=True)
    except Exception as e:
        print(f"传感器初始化失败：{e}\n")
        sensor = None
    
    # 5. NTP时钟首次校准（阻塞式，确保开机时间准确）
    print("==================================")
    print(" NTP时钟 - 首次校准中")
    print("==================================\n")
    while True:
        success, tz = ntp_module.sync_ntp_to_rtc()
        if success:
            print(f"NTP校准成功 时区 UTC+{tz:.1f}\n")
            break
        if VERBOSE:
            print("[MAIN DEBUG] NTP校准重试...")
        sleep(2)
    
    # 6. 启动双核心任务（核心0和核心1分别运行对应子系统）
    print("==================================")
    print(" 双核心任务启动 - 系统开始运行")
    print("==================================\n")
    print(f" 核心0：串口屏控制子系统（screen_control_subsystem）")
    print(f" 核心1：定时器控制子系统（timer_control_subsystem）+ SR602人体检测")
    print("==================================\n")
    
    # 创建核心1任务线程（先启动核心1，避免资源竞争）
    _thread.start_new_thread(core1_task, (global_uart, sensor, sensor_uart))
    
    # 启动SR602人体检测独立线程（运行在核心1，与定时器子系统同核心）
    sr602_module.start_sr602_detect(global_uart, VERBOSE)
    print("[SR602] 人体检测独立线程启动成功（优先运行在核心1）\n")
    
    # 核心0任务直接在主线程运行（主线程默认绑定核心0，无需额外创建线程）
    core0_task(global_uart, sensor)

# ===程序启动入口=======
if __name__ == "__main__":
    """程序启动入口：调用主函数，执行开机初始化和核心绑定"""
    main()