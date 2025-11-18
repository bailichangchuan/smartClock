import machine
import utime
import _thread
from config import SERIAL_PORT, SERIAL_BAUD_RATE, SERIAL_TX_PIN, SERIAL_RX_PIN
# 导入模块（与main.py保持一致的导入路径）
from function import weather as weather_module
from function import ntp_clock as ntp_module
from function import multi_sensor as sensor_module  # 新增：导入传感器模块

# ================== 指令解析配置 ==================
CMD_HEADER = 0x65  # 固定指令头
CMD_END = [0xFF, 0xFF, 0xFF]  # 固定结束符
OP_PRESS = 0x01  # 按下操作码（仅响应按下）
OP_RELEASE = 0x00  # 松开操作码（不响应）

def parse_screen_command(data):
    """解析串口屏指令，返回(页号, 控件号, 操作码)，无效返回None"""
    if len(data) != 7:
        return None
    if data[0] != CMD_HEADER or list(data[-3:]) != CMD_END:
        return None
    return (data[1], data[2], data[3])  # (页号, 控件号, 操作码)

# 新增参数：sensor（接收main.py传入的传感器实例）
def uart_listen_thread(uart, sensor):
    """串口监听子线程（核心0）：不间断监听，执行对应操作"""
    print(f"监听子线程启动（核心{_thread.get_ident()}），持续监听串口屏指令...")
    while True:
        data = uart.read(7)
        if data:
            cmd_info = parse_screen_command(data)
            if cmd_info:
                page, control, op = cmd_info
                if op == OP_PRESS:
                    print(f"检测到操作：页{page} 控件{control} 按下（强制更新）")
                    
                    # 原有功能：0页控件4→强制更新天气（按你的指令映射）
                    if page == 1 and control == 0:
                        utime.sleep_ms(50)
                        print("执行操作：强制更新天气...")
                        weather_module.get_weather_by_ip(uart, force=True)
                    
                    # 原有功能：1页控件4→强制更新时间（按你的指令映射）
                    elif page == 0 and control == 0:
                        utime.sleep_ms(50)
                        print("执行操作：强制更新时间...")
                        ntp_module.send_time_to_serial_screen(uart, force=True)
                    
                    # 新增功能：2页控件0→强制更新空气质量（核心）
                    elif page == 2 and control == 0:
                        utime.sleep_ms(50)
                        print("执行操作：强制更新空气质量...")
                        # 强制读取传感器数据（force=True→忽略缓存，直接推送屏幕）
                        if sensor and uart:
                            sensor.read_sensor_data(uart, force=True)
                        else:
                            print("警告：传感器未初始化或串口异常，无法强制更新")

            else:
                print(f"收到无效指令：{data.hex().upper()}")
        
        utime.sleep_ms(10)  # 降低CPU占用

# 新增参数：sensor（接收传感器实例，传递给子线程）
def start_listen_thread(uart, sensor):
    """启动监听子线程，传入：串口屏UART实例 + 传感器实例"""
    _thread.start_new_thread(uart_listen_thread, (uart, sensor))  # 传递2个参数
    print("监听子线程启动成功，等待串口屏指令...")

if __name__ == "__main__":
    # 测试用：本地初始化
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
    test_sensor = sensor_module.MultiSensor(verbose=True)
    try:
        start_listen_thread(test_uart, test_sensor)
        while True:
            utime.sleep(1)
    except KeyboardInterrupt:
        print("\n测试停止")
    finally:
        test_uart.close()