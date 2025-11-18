# ===导入依赖模块=======
# 硬件控制模块：提供UART实例类型判断（确保传入有效串口实例）
import machine
# 时间工具模块：提供时间戳（超时判断）和延时（降低CPU占用）功能
import time

# ===UART串口数据读取核心类=======
class UARTReader:
    """
    UART串口数据读取器类：专注于查找指定帧头和长度的有效数据帧
    核心特性：
    1. 支持多字节/单字节帧头匹配
    2. 超时后保留缓存数据（下次查找可复用，避免数据丢失）
    3. 服从全局VERBOSE开关，统一控制DEBUG日志输出
    4. 支持软件+硬件缓存双重清空
    依赖：需在外部（如main.py）初始化machine.UART实例并传入
    """
    
    # ===类初始化方法=======
    def __init__(self, uart=None, data_bits=8, parity=None, stop_bits=1, verbose=False):
        """
        初始化UART数据读取器
        :param uart: machine.UART实例（必须外部初始化后传入，确保串口配置正确）
        :param data_bits: 数据位（默认8位，兼容串口标准配置，当前未直接使用）
        :param parity: 校验位（默认None，兼容串口标准配置，当前未直接使用）
        :param stop_bits: 停止位（默认1位，兼容串口标准配置，当前未直接使用）
        :param verbose: DEBUG日志控制开关（接收main.py全局VERBOSE参数）
        初始化逻辑：
        1. 接收全局VERBOSE开关，控制当前类所有DEBUG输出
        2. 初始化数据缓存（用于暂存未匹配的串口数据）
        3. 校验传入UART实例有效性，无效则抛出异常
        4. 初始化成功/失败的DEBUG日志输出（受VERBOSE控制）
        """
        # 接收全局DEBUG控制开关（来自main.py，统一管控日志）
        self.verbose = verbose
        # 软件缓存：暂存串口接收的未匹配数据（超时不清空，下次复用）
        self.buffer = b""
        # UART串口实例：外部传入（确保串口配置与硬件一致）
        self.uart = None
        
        try:
            # 校验UART实例有效性（必须是machine.UART类型）
            if uart is None or not isinstance(uart, machine.UART):
                raise ValueError("必须传入有效的machine.UART实例（需在main中完成串口初始化）")
            self.uart = uart
            # DEBUG日志：仅VERBOSE=True时输出初始化成功信息
            if self.verbose:
                print(f"[UART] 读取器初始化成功（使用外部传入的UART实例）")
        except Exception as e:
            # DEBUG日志：仅VERBOSE=True时输出初始化失败原因
            if self.verbose:
                print(f"[UART] 初始化失败：{str(e)}")
            # 抛出异常，中断外部初始化流程（避免无效实例使用）
            raise

    # ===核心方法：查找指定格式的有效数据帧=======
    def find_data_frame(self, frame_header, frame_length, timeout=1.0):
        """
        查找并返回符合条件的有效数据帧（按帧头+固定长度匹配）
        :param frame_header: 帧头（支持int单字节/int列表多字节，如0x3C或[0x3C, 0x02]）
        :param frame_length: 有效数据帧总长度（包含帧头，单位：字节）
        :param timeout: 查找超时时间（单位：秒，默认1.0秒）
        :return: 有效数据帧（bytes类型）/ None（超时未找到）
        核心逻辑：
        1. 校验UART实例是否就绪，未就绪返回None
        2. 统一帧头格式（int→bytes，list→bytes），确保匹配兼容性
        3. 循环读取串口数据，追加到软件缓存
        4. 缓存长度满足帧长时，遍历查找匹配帧头的连续数据
        5. 找到有效帧：返回帧数据，缓存保留后续未匹配数据
        6. 超时未找到：返回None，缓存保留已接收数据（下次查找复用）
        """
        # 校验UART实例是否就绪（未就绪则输出日志并返回None）
        if not self.uart:
            if self.verbose:
                print("[UART] 未初始化有效UART实例，无法执行数据帧查找")
            return None
        
        # 统一帧头格式：支持int（单字节）和int列表（多字节）输入
        if isinstance(frame_header, int):
            # int类型→bytes（单字节），如0x3C→b'\x3C'
            header_bytes = bytes([frame_header])
        elif isinstance(frame_header, list) and all(isinstance(b, int) for b in frame_header):
            # int列表→bytes（多字节），如[0x3C, 0x02]→b'\x3C\x02'
            header_bytes = bytes(frame_header)
        else:
            # 帧头格式错误：输出日志并返回None
            if self.verbose:
                print(f"[UART] 帧头格式错误：仅支持int（单字节）或int列表（多字节）")
            return None
        
        # 计算帧头长度和最小缓存长度（需满足完整帧长才开始匹配）
        header_len = len(header_bytes)
        min_buffer_len = frame_length
        # 记录查找开始时间戳（用于超时判断）
        start_time = time.time()
        
        # DEBUG日志：输出查找配置信息（帧头、帧长、超时）
        if self.verbose:
            print(f"[UART] 开始查找数据帧：帧头{header_bytes.hex().upper()}（{header_len}字节），帧总长度{frame_length}字节，超时{timeout}秒")
        
        # 循环查找：直到超时或找到有效帧
        while time.time() - start_time < timeout:
            # 读取串口缓冲区数据（有数据则追加到软件缓存）
            if self.uart.any():
                # 读取所有可用数据（避免分次读取导致帧断裂）
                read_data = self.uart.read()
                self.buffer += read_data
                # DEBUG日志：输出本次读取数据和当前缓存长度
                if self.verbose:
                    print(f"[UART] 读取串口数据：{read_data.hex().upper()}，当前缓存长度：{len(self.buffer)}字节")
            
            # 缓存长度满足最小帧长时，开始查找有效帧
            if len(self.buffer) >= min_buffer_len:
                # 遍历缓存：从每个位置尝试匹配帧头（确保不遗漏中间帧）
                for i in range(len(self.buffer) - frame_length + 1):
                    # 截取当前位置的帧头长度数据，与目标帧头匹配
                    buffer_header = self.buffer[i:i+header_len]
                    if buffer_header == header_bytes:
                        # 找到匹配帧头：截取完整有效帧（帧头+后续数据=帧总长度）
                        target_frame = self.buffer[i:i+frame_length]
                        # 更新缓存：保留有效帧之后的未匹配数据（避免数据丢失）
                        self.buffer = self.buffer[i+frame_length:]
                        # DEBUG日志：输出找到的有效帧和剩余缓存长度
                        if self.verbose:
                            print(f"[UART] 找到有效数据帧：{target_frame.hex().upper()}，剩余缓存长度：{len(self.buffer)}字节")
                        # 返回有效帧（结束查找）
                        return target_frame
            
            # 短延时：降低CPU占用率（5毫秒，不影响数据接收实时性）
            time.sleep(0.005)
        
        # 超时未找到有效帧：输出日志，保留缓存数据（下次查找可复用）
        if self.verbose:
            print(f"[UART] 查找超时（{timeout}秒），未找到有效数据帧，缓存保留{len(self.buffer)}字节（下次查找继续匹配）")
        # 返回None表示未找到有效帧
        return None

    # ===辅助方法：清空软件+硬件缓存=======
    def clear_buffer(self):
        """
        清空串口缓存（软件缓存+硬件缓存双重清空）
        作用：避免旧数据干扰新数据查找（如读取前清空历史缓存）
        逻辑：
        1. 校验UART实例是否就绪，未就绪则输出日志
        2. 清空软件缓存（self.buffer）
        3. 读取硬件缓冲区所有数据（强制清空硬件缓存）
        4. 输出清空成功日志（受VERBOSE控制）
        """
        # 校验UART实例是否就绪（未就绪则输出日志并返回）
        if not self.uart:
            if self.verbose:
                print("[UART] 未初始化有效UART实例，无法清空缓存")
            return
        
        # 清空软件缓存（重置为空字节串）
        self.buffer = b""
        # 清空硬件缓存：读取所有硬件缓冲区数据（丢弃）
        if self.uart.any():
            self.uart.read()
        # DEBUG日志：仅VERBOSE=True时输出缓存清空信息
        if self.verbose:
            print(f"[UART] 缓存已清空（软件缓存+串口硬件缓存）")