# ===导入依赖模块=======
# 硬件控制模块：提供UART实例操作、Pin引脚配置（测试模式用）
import machine
# 时间工具模块：提供毫秒级延时（降低CPU占用、指令防抖）
import utime
# 多线程模块：创建独立监听子线程（不阻塞主程序）
import _thread
# 配置文件导入：串口2参数（仅测试模式使用，与main.py保持一致）
from config import SERIAL_PORT, SERIAL_BAUD_RATE, SERIAL_TX_PIN, SERIAL_RX_PIN
# 功能模块导入：天气查询（响应指令更新天气）
from function import weather as weather_module
# 功能模块导入：NTP时间（响应指令更新时间）
from function import ntp_clock as ntp_module
# 功能模块导入：传感器控制（响应指令更新空气质量，接收main.py实例）
from function import multi_sensor as sensor_module

# ===串口屏指令解析配置常量=======
# 指令帧头：串口屏输出指令的固定起始标识（单字节，与串口屏协议一致）
CMD_HEADER = 0x65
# 指令结束符：串口屏输出指令的固定结束标识（3字节，与串口屏协议一致）
CMD_END = [0xFF, 0xFF, 0xFF]
# 操作码：按下操作（仅响应按下动作，忽略松开动作）
OP_PRESS = 0x01
# 操作码：松开操作（不响应，仅作为对比判断）
OP_RELEASE = 0x00
# 全局DEBUG控制开关：默认False，实际运行时由main.py传入传感器实例的verbose属性控制
# （注：因该模块通过sensor实例关联全局VERBOSE，无需单独定义，直接复用sensor.verbose）

# ===辅助函数：串口屏指令解析=======
def parse_screen_command(data):
    """
    解析串口屏发送的指令数据，提取有效操作信息
    :param data: 串口接收的原始数据（bytes类型，预期7字节）
    :return: 有效指令元组 (页号, 控件号, 操作码) / None（无效指令）
    解析逻辑：
    1. 长度校验：仅接收7字节数据（串口屏协议约定指令长度）
    2. 帧头+结束符校验：必须匹配CMD_HEADER和CMD_END（确保是目标指令）
    3. 提取有效字段：从指定索引位置提取页号、控件号、操作码
    """
    # 长度校验：非7字节数据直接判定为无效指令
    if len(data) != 7:
        return None
    # 帧头+结束符校验：匹配协议约定的起始和结束标识
    if data[0] != CMD_HEADER or list(data[-3:]) != CMD_END:
        return None
    # 提取有效字段并返回（页号：索引1，控件号：索引2，操作码：索引3）
    return (data[1], data[2], data[3])

# ===核心函数：串口屏指令监听子线程=======
def uart_listen_thread(uart, sensor):
    """
    串口屏指令监听子线程：独立核心运行，不间断接收并响应指令
    :param uart: 串口屏专用UART实例（main.py中的串口2，用于接收指令/推送响应数据）
    :param sensor: 传感器处理实例（main.py中的MultiSensor对象，用于强制更新空气质量）
    核心逻辑：
    1. 启动时打印核心状态（必显，告知用户监听启动）
    2. 无限循环接收串口数据（每次读取7字节，匹配指令长度）
    3. 解析指令：调用parse_screen_command提取有效操作
    4. 响应按下操作：仅OP_PRESS时执行对应功能（更新天气/时间/空气质量）
    5. 无效指令处理：VERBOSE=True时输出无效指令日志（受全局控制）
    6. 短延时：降低CPU占用率（10毫秒，不影响指令响应实时性）
    """
    # 核心状态输出（必显，告知用户子线程启动状态及运行核心）
    print(f"串口屏指令监听子线程启动（运行核心：{_thread.get_ident()}），持续监听指令...")
    
    # 无限循环：不间断监听串口数据
    while True:
        # 读取串口数据（每次读取7字节，匹配指令约定长度）
        data = uart.read(7)
        if data:  # 接收到数据时执行解析逻辑
            # 解析指令：提取页号、控件号、操作码
            cmd_info = parse_screen_command(data)
            if cmd_info:  # 解析到有效指令
                page, control, op = cmd_info
                # 仅响应按下操作（忽略松开操作，避免重复执行）
                if op == OP_PRESS:
                    # 核心状态输出（必显，告知用户检测到的操作）
                    print(f"检测到串口屏操作：页{page} → 控件{control}（按下，执行强制更新）")
                    
                    # 指令映射1：页1-控件0 → 强制更新天气
                    if page == 1 and control == 0:
                        utime.sleep_ms(50)  # 防抖延时：避免指令误触发
                        print("执行操作：强制更新天气数据...")
                        # 调用天气模块强制更新（force=True：忽略缓存，实时请求）
                        weather_module.get_weather_by_ip(uart, force=True)
                    
                    # 指令映射2：页0-控件0 → 强制更新时间
                    elif page == 0 and control == 0:
                        utime.sleep_ms(50)  # 防抖延时
                        print("执行操作：强制更新串口屏时间...")
                        # 调用NTP模块强制更新时间（force=True：忽略缓存，实时校准推送）
                        ntp_module.send_time_to_serial_screen(uart, force=True)
                    
                    # 指令映射3：页2-控件0 → 强制更新空气质量（传感器数据）
                    elif page == 2 and control == 0:
                        utime.sleep_ms(50)  # 防抖延时
                        print("执行操作：强制更新空气质量数据...")
                        # 校验传感器和串口实例就绪状态
                        if sensor and uart:
                            # 调用传感器强制读取并推送（force=True：忽略2秒间隔）
                            sensor.read_sensor_data(uart, force=True)
                        else:
                            # 异常状态输出（必显，告知用户无法执行的原因）
                            print("警告：传感器实例未初始化或串口异常，无法执行强制更新")
            
            else:  # 解析到无效指令
                # DEBUG日志：仅VERBOSE=True时输出无效指令（受全局控制）
                if sensor and sensor.verbose:
                    print(f"[SCREEN DEBUG] 收到无效串口屏指令：{data.hex().upper()}")
        
        # 短延时：降低CPU占用率（10毫秒，平衡实时性和资源占用）
        utime.sleep_ms(10)

# ===对外接口：启动监听子线程=======
def start_listen_thread(uart, sensor):
    """
    启动串口屏指令监听子线程（对外暴露的统一接口，供main.py调用）
    :param uart: 串口屏专用UART实例（main.py中的串口2）
    :param sensor: 传感器处理实例（main.py中的MultiSensor对象，携带全局VERBOSE开关）
    逻辑说明：
    1. 创建新线程并启动监听逻辑（传入uart和sensor参数）
    2. 启动成功后打印核心状态（必显，告知用户接口调用结果）
    """
    # 启动新线程：执行uart_listen_thread，传递串口和传感器实例
    _thread.start_new_thread(uart_listen_thread, (uart, sensor))
    # 核心状态输出（必显，告知用户子线程启动成功）
    print("串口屏指令监听子线程启动成功，等待接收指令...")

# ===本地测试入口=======
if __name__ == "__main__":
    """
    本地测试模式：独立运行该文件时初始化测试实例，验证监听功能
    测试逻辑：
    1. 初始化串口2实例（使用config配置参数，与main.py保持一致）
    2. 初始化传感器测试实例（verbose=True，启用DEBUG日志便于测试）
    3. 启动监听子线程，进入无限循环维持测试运行
    4. 捕获键盘中断（Ctrl+C），优雅停止测试并关闭串口
    """
    # 初始化测试用串口2实例（匹配main.py的串口配置）
    test_uart = machine.UART(
        SERIAL_PORT,
        baudrate=SERIAL_BAUD_RATE,
        tx=machine.Pin(SERIAL_TX_PIN),
        rx=machine.Pin(SERIAL_RX_PIN),
        bits=8,
        parity=None,
        stop=1,
        timeout=100
    )
    # 初始化测试用传感器实例（verbose=True，测试时启用DEBUG日志）
    test_sensor = sensor_module.MultiSensor(verbose=True)
    
    try:
        # 启动监听子线程（传入测试实例）
        start_listen_thread(test_uart, test_sensor)
        # 无限循环：维持测试运行（避免主线程退出）
        while True:
            utime.sleep(1)
    except KeyboardInterrupt:
        # 捕获键盘中断（Ctrl+C），打印测试停止信息
        print("\n本地测试停止（用户主动中断）")
    finally:
        # 测试结束：关闭串口，释放硬件资源
        test_uart.close()