# ===串口屏控制核心模块（根目录）=======
# 功能：整合指令监听与解析，提供统一对外接口，运行在核心0
# 依赖：screen_control_tool中的监听模块和解析模块

# ===导入依赖模块=======
# 硬件控制模块：提供UART实例操作（串口屏初始化）
import machine
# 配置文件导入：串口2参数（与main.py保持一致）
from config import SERIAL_PORT, SERIAL_BAUD_RATE, SERIAL_TX_PIN, SERIAL_RX_PIN
# 屏幕指令监听模块：导入启动监听的统一接口
from screen_control_tool.screen_command_listener import start_listen_thread

# ===串口屏初始化=======
def init_serial_screen():
    """
    初始化串口屏专用UART实例（串口2）
    :return: 初始化成功的UART实例 / None（初始化失败）
    逻辑说明：按照config配置参数创建UART对象，确保与串口屏通信参数一致
    """
    try:
        # 初始化UART2实例（匹配串口屏通信协议）
        uart = machine.UART(
            SERIAL_PORT,
            baudrate=SERIAL_BAUD_RATE,
            tx=machine.Pin(SERIAL_TX_PIN),
            rx=machine.Pin(SERIAL_RX_PIN),
            bits=8,
            parity=None,
            stop=1,
            timeout=100
        )
        print(f"串口屏UART{SERIAL_PORT}初始化成功（波特率：{SERIAL_BAUD_RATE}）")
        return uart
    except Exception as e:
        # 初始化失败日志（必显，告知用户异常原因）
        print(f"串口屏UART初始化失败：{str(e)}")
        return None

# ===核心入口：启动串口屏控制子系统=======
def run_screen_control_subsystem(sensor):
    """
    启动串口屏控制子系统（对外暴露的统一入口，供main.py调用）
    :param sensor: 传感器处理实例（main.py中的MultiSensor对象，用于指令响应）
    逻辑说明：
    1. 初始化串口屏UART
    2. 启动指令监听子线程（非阻塞，不影响其他模块运行）
    3. 维持子系统运行（避免主线程退出）
    """
    # 初始化串口屏
    uart = init_serial_screen()
    if not uart:
        print("串口屏控制子系统启动失败：UART初始化未完成")
        return
    
    # 启动指令监听子线程（传入UART和传感器实例）
    start_listen_thread(uart, sensor)
    
    # 无限循环：维持子系统运行（核心0专属循环，不阻塞核心1任务）
    while True:
        # 短延时：降低核心0占用率（100毫秒，不影响指令响应）
        machine.idle()  # 进入低功耗空闲状态，优化资源占用

# ===本地测试入口=======
if __name__ == "__main__":
    """
    本地测试模式：独立运行该文件时验证子系统功能
    逻辑：初始化测试实例，启动子系统，捕获中断优雅退出
    """
    # 导入传感器模块（测试用）
    from function import multi_sensor as sensor_module
    
    # 初始化测试用传感器实例（verbose=True，启用DEBUG日志）
    test_sensor = sensor_module.MultiSensor(verbose=True)
    
    try:
        # 启动串口屏控制子系统（传入测试传感器实例）
        print("启动串口屏控制子系统（本地测试模式）...")
        run_screen_control_subsystem(test_sensor)
    except KeyboardInterrupt:
        # 捕获键盘中断（Ctrl+C），打印停止信息
        print("\n串口屏控制子系统本地测试停止（用户主动中断）")