# ===导入依赖模块=======
# 时间工具模块：提供毫秒级延时（避免串口数据拥堵，确保指令完整发送）
import utime

VERBOSE = False  # 数据推送DEBUG输出控制开关

# ===核心工具函数：串口屏数据推送=======
def upload(
    uart,
    time_str,
    control_name="t0",
    property_name="txt"
):
    """
    向串口屏指定控件推送数据（复用main.py传入的持续开启UART实例，避免重复初始化/关闭）
    核心特性：
    1. 通用指令格式：支持任意控件+任意属性的赋值操作
    2. 协议兼容：遵循串口屏标准指令格式（{控件名}.{属性名}="值"+三字节结束符）
    3. 防拥堵：推送后10毫秒短延时，避免串口数据堆积
    4. 异常捕获：捕获所有发送异常，输出明确错误信息
    5. DEBUG日志：推送详情受VERBOSE全局开关控制
    :param uart: 串口屏专用UART实例（main.py中初始化的持续开启实例，不可为None）
    :param time_str: 待推送的数据内容（字符串类型，如日期、天气、传感器值等）
    :param control_name: 串口屏控件名称（默认"t0"，需与屏幕配置的控件名一致）
    :param property_name: 控件属性名称（默认"txt"，即文本属性，支持串口屏支持的所有属性）
    :return: 无返回值（推送成功无输出，失败输出错误信息）
    推送流程：
    1. 构造串口屏标准指令字符串（{控件名}.{属性名}="数据内容"）
    2. 通过UART实例发送指令字符串
    3. 发送串口屏协议要求的三字节结束符（0xFF, 0xFF, 0xFF）
    4. 10毫秒短延时，确保指令完整发送，避免串口拥堵
    5. 捕获所有异常（如UART未就绪、发送失败等），输出错误信息
    """
    try:
        # 步骤1：构造串口屏指令（遵循屏幕协议：控件名.属性名="值"）
        # 示例：t0.txt="2025-11-18" → 向控件t0的文本属性赋值
        command = f"{control_name}.{property_name}=\"{time_str}\""
        
        # DEBUG日志：仅VERBOSE=True时输出推送详情（指令内容、控件、属性）
        if VERBOSE:
            print(f"[SCREEN UPLOAD DEBUG] 推送指令：{command} | 控件：{control_name} | 属性：{property_name}")
        
        # 步骤2：通过UART实例发送指令字符串（自动编码为字节串）
        uart.write(command)
        
        # 步骤3：发送串口屏协议结束符（三字节0xFF，告知屏幕指令结束）
        end_sequence = bytearray([0xff, 0xff, 0xff])
        uart.write(end_sequence)
        
        # 步骤4：短延时防拥堵（10毫秒，平衡实时性和数据完整性）
        utime.sleep_ms(10)
    
    # 捕获所有发送异常（如UART未初始化、串口断开、权限不足等）
    except Exception as e:
        # 异常信息必显（推送失败影响用户交互，需及时告知）
        print(f"串口屏数据推送失败（控件：{control_name}，属性：{property_name}）：{e}")