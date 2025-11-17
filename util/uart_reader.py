import machine
import time
from config import (
    UART_NUM,
    UART_BAUDRATE,
    UART_TX_PIN,
    UART_RX_PIN,
)

class UARTReader:
    def __init__(self, data_bits=8, parity=None, stop_bits=1, verbose=False):
        """
        通用串口数据读取器
        从config.py读取串口核心配置 支持调试输出控制
        :param data_bits: 数据位
        :param parity: 校验位
        :param stop_bits: 停止位
        :param verbose: 调试输出开关
        """
        self.verbose = verbose
        self.buffer = b""  # 串口数据缓存 避免丢失帧数据
        
        # 初始化UART
        try:
            self.uart = machine.UART(
                UART_NUM,
                baudrate=UART_BAUDRATE,
                bits=data_bits,
                parity=parity,
                stop=stop_bits,
                tx=machine.Pin(UART_TX_PIN),
                rx=machine.Pin(UART_RX_PIN),
                timeout=10  # 单次读取超时 单位ms
            )
            if self.verbose:
                print(f"[UART] 初始化成功 编号：{UART_NUM} 波特率：{UART_BAUDRATE} TX：{UART_TX_PIN} RX：{UART_RX_PIN}")
        except Exception as e:
            if self.verbose:
                print(f"[UART] 初始化失败：{str(e)}")
            raise  # 抛出异常 由调用者处理

    def find_data_frame(self, frame_header, frame_length, timeout=1.0):
        """
        按指定规则从串口缓存寻找完整数据帧
        通用逻辑 与传感器协议解耦
        :param frame_header: 帧头字节
        :param frame_length: 完整数据帧长度 单位字节
        :param timeout: 超时时间 单位秒
        :return: 完整数据帧 bytes类型 或None
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # 读取串口所有可用数据 追加到缓存
            if self.uart.any():
                read_data = self.uart.read()
                self.buffer += read_data
                if self.verbose:
                    print(f"[UART] 读取数据：{read_data.hex()} 缓存长度：{len(self.buffer)}")
            
            # 缓存长度足够时 查找帧头
            if len(self.buffer) >= frame_length:
                # 遍历缓存 匹配帧头并提取完整帧
                for i in range(len(self.buffer) - frame_length + 1):
                    if self.buffer[i] == frame_header:
                        target_frame = self.buffer[i:i+frame_length]
                        # 更新缓存 保留帧后未处理数据
                        self.buffer = self.buffer[i+frame_length:]
                        if self.verbose:
                            print(f"[UART] 找到有效帧：{target_frame.hex()} 剩余缓存：{len(self.buffer)}字节")
                        return target_frame
            
            time.sleep(0.005)  # 降低CPU占用
        
        # 超时未找到 清空缓存
        self.buffer = b""
        if self.verbose:
            print(f"[UART] 超时未找到有效帧 帧头：0x{frame_header:02X} 长度：{frame_length}")
        return None

    def clear_buffer(self):
        """清空串口缓存"""
        self.buffer = b""
        if self.uart.any():
            self.uart.read()
        if self.verbose:
            print(f"[UART] 缓存已清空")