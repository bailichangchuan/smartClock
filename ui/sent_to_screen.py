import utime

def upload(
    uart,  # 新增必填参数：接收main初始化的持续开启UART实例
    time_str,
    control_name="t0",
    property_name="txt"
):
    # 向串口屏指定控件发送值（复用main传入的UART，不重复初始化/关闭）
    try:
        # 构造通用串口屏指令：{控件名}.{属性名}="值"
        command = f"{control_name}.{property_name}=\"{time_str}\""
        # 用共享UART发送指令
        uart.write(command)
        # 发送结束符
        end_sequence = bytearray([0xff, 0xff, 0xff])
        uart.write(end_sequence)
        # 短延时 避免串口拥堵
        utime.sleep_ms(10)
    except Exception as e:
        print(f"串口屏发送失败：{e}")