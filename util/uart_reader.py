import machine
import time

class UARTReader:
    def __init__(self, uart=None, data_bits=8, parity=None, stop_bits=1, verbose=False):
        self.verbose = verbose
        self.buffer = b""  # 串口数据缓存
        self.uart = None
        
        try:
            if uart is None or not isinstance(uart, machine.UART):
                raise ValueError("必须传入有效的UART实例（需在main中初始化）")
            self.uart = uart
            if self.verbose:
                print(f"[UART] 读取器初始化成功（使用外部UART实例）")
        except Exception as e:
            if self.verbose:
                print(f"[UART] 初始化失败：{str(e)}")
            raise

    def find_data_frame(self, frame_header, frame_length, timeout=1.0):
        if not self.uart:
            if self.verbose:
                print("[UART] 未初始化UART实例，无法查找数据帧")
            return None
        
        # 统一帧头格式（支持1字节/多字节）
        if isinstance(frame_header, int):
            header_bytes = bytes([frame_header])
        elif isinstance(frame_header, list) and all(isinstance(b, int) for b in frame_header):
            header_bytes = bytes(frame_header)
        else:
            if self.verbose:
                print(f"[UART] 帧头格式错误（仅支持int或int列表）")
            return None
        header_len = len(header_bytes)
        min_buffer_len = frame_length
        start_time = time.time()
        
        if self.verbose:
            print(f"[UART] 查找帧：帧头{header_bytes.hex().upper()}（{header_len}字节），长度{frame_length}字节，超时{timeout}秒")
        
        while time.time() - start_time < timeout:
            # 读取串口数据追加到缓存
            if self.uart.any():
                read_data = self.uart.read()
                self.buffer += read_data
                if self.verbose:
                    print(f"[UART] 读取数据：{read_data.hex().upper()} 缓存长度：{len(self.buffer)}")
            
            # 多字节帧头匹配
            if len(self.buffer) >= min_buffer_len:
                for i in range(len(self.buffer) - frame_length + 1):
                    buffer_header = self.buffer[i:i+header_len]
                    if buffer_header == header_bytes:
                        target_frame = self.buffer[i:i+frame_length]
                        self.buffer = self.buffer[i+frame_length:]  # 找到有效帧后，保留后续数据
                        if self.verbose:
                            print(f"[UART] 找到有效帧：{target_frame.hex().upper()} 剩余缓存：{len(self.buffer)}字节")
                        return target_frame
            
            time.sleep(0.005)
        
        # ========== 核心修改：超时不清空缓存！保留已接收数据，下次继续查找 ==========
        if self.verbose:
            print(f"[UART] 超时未找到有效帧（缓存保留{len(self.buffer)}字节，下次继续查找）")
        return None  # 仅返回None，不清空buffer

    def clear_buffer(self):
        if not self.uart:
            if self.verbose:
                print("[UART] 未初始化UART实例，无法清空缓存")
            return
        
        self.buffer = b""
        if self.uart.any():
            self.uart.read()
        if self.verbose:
            print(f"[UART] 缓存已清空（软件+硬件缓存）")