import machine
from config import SERIAL_PORT, SERIAL_BAUD_RATE, SERIAL_TX_PIN, SERIAL_RX_PIN

def upload(
    time_str,
    control_name="t0",  # 新增可选参数：控件名（默认t0，外部可输入）
    property_name="txt" # 新增可选参数：属性名（默认txt，外部可输入）
):
    # 向串口屏指定控件的指定属性发送值，用前初始化UART，用后关闭
    try:
        # 每次使用前初始化UART
        uart = machine.UART(
            SERIAL_PORT,
            baudrate=SERIAL_BAUD_RATE,
            tx=machine.Pin(SERIAL_TX_PIN),
            rx=machine.Pin(SERIAL_RX_PIN)
        )
        # 构造通用串口屏指令：{控件名}.{属性名}="值"
        command = f"{control_name}.{property_name}=\"{time_str}\""
        # 发送指令
        uart.write(command)
        # 发送串口屏指令结束符
        end_sequence = bytearray([0xff, 0xff, 0xff])
        uart.write(end_sequence)
    except Exception as e:
        # 打印通用错误信息（适配所有控件/属性发送场景）
        print(f"串口屏发送失败：{e}")
    finally:
        # 无论是否成功，使用后关闭UART
        if 'uart' in locals():
            uart.close()