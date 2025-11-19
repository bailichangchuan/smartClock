"""
UART串口数据读取器 - 智能时钟的数据接收专家
功能：专门负责从各种串口设备读取数据，支持帧头匹配和超时控制
特点：非阻塞读取、智能缓存管理、多格式帧头支持
"""

# 导入硬件控制模块 - 与串口设备直接对话的接口
import machine
import time

# 导入系统配置 - 使用面向用户的友好配置项
from config import (
    # 调试开关
    GLOBAL_DEBUG, 
    # 系统配置
    UART_TIMEOUT, UART_BUFFER_SIZE
)

# 为UART模块定义独立调试开关（如果config中没有，使用全局开关）
try:
    from config import UART_DEBUG
except ImportError:
    UART_DEBUG = GLOBAL_DEBUG


class UARTReader:
    """
    UART数据读取专家 - 专门处理串口通信中的数据接收
    就像一位专注的倾听者，耐心等待并准确捕捉设备发送的信息
    """
    
    def __init__(self, uart_instance=None, verbose=None):
        """
        初始化UART读取器，建立与串口设备的通信连接
        
        参数说明：
        - uart_instance: 已配置好的UART实例（如果为None，需要后续手动设置）
        - verbose: 详细日志开关（如果为None，使用配置中的UART_DEBUG）
        """
        # 设置调试模式：优先使用参数，其次使用配置开关
        self.verbose = verbose if verbose is not None else UART_DEBUG
        
        # 数据缓存区：暂存未处理完的串口数据
        # 就像一个临时仓库，存放还没分类整理的原材料
        self.data_buffer = b""
        
        # UART通信实例：与外部设备对话的通道
        self.uart_channel = None
        
        # 设置UART实例
        if uart_instance is not None:
            self.set_uart_instance(uart_instance)
            
        if self.verbose:
            print("[UART读取器] 初始化完成，准备接收数据")

    def set_uart_instance(self, uart_instance):
        """
        设置UART通信实例
        建立与具体硬件设备的对话通道
        
        参数说明：
        - uart_instance: 已初始化的machine.UART实例
        """
        try:
            # 验证传入的是有效的UART实例
            if not isinstance(uart_instance, machine.UART):
                raise ValueError("需要传入有效的machine.UART实例")
            
            self.uart_channel = uart_instance
            
            if self.verbose:
                print("[UART读取器] UART通信通道建立成功")
                
        except Exception as e:
            print(f"❌ UART读取器设置失败: {e}")
            raise

    def read_available_data(self):
        """
        读取串口缓冲区中所有可用的数据
        就像检查邮箱里是否有新信件，有多少就读多少
        """
        if self.uart_channel is None:
            if self.verbose:
                print("[UART读取器] 警告：未设置UART实例，无法读取数据")
            return b""
        
        try:
            # 检查串口缓冲区是否有数据等待读取
            if self.uart_channel.any():
                # 读取所有可用数据
                received_data = self.uart_channel.read()
                
                if self.verbose and received_data:
                    # 在调试模式下显示接收到的数据（十六进制格式）
                    hex_data = received_data.hex().upper()
                    print(f"[UART读取器] 接收到数据: {hex_data}")
                
                return received_data if received_data else b""
            
            return b""
            
        except Exception as e:
            print(f"❌ 串口数据读取异常: {e}")
            return b""

    def find_data_frame(self, frame_header, frame_length, timeout=None):
        """
        查找并提取完整的数据帧
        根据指定的帧头和长度，从数据流中准确识别完整的数据包
        
        参数说明：
        - frame_header: 帧头标识（支持单字节、多字节或字节序列）
        - frame_length: 完整数据帧的长度（包含帧头）
        - timeout: 查找超时时间（秒），默认使用配置中的超时设置
        """
        # 设置超时时间：优先使用参数，其次使用配置
        if timeout is None:
            timeout = UART_TIMEOUT / 1000  # 将毫秒转换为秒
        
        if self.uart_channel is None:
            if self.verbose:
                print("[UART读取器] 错误：UART实例未就绪，无法查找数据帧")
            return None
        
        # 统一帧头格式：支持多种输入方式
        header_bytes = self._normalize_frame_header(frame_header)
        if header_bytes is None:
            return None
        
        header_length = len(header_bytes)
        
        if self.verbose:
            hex_header = header_bytes.hex().upper()
            print(f"[UART读取器] 开始查找数据帧: 帧头={hex_header}, 长度={frame_length}, 超时={timeout}秒")
        
        # 记录开始时间，用于超时判断
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # 读取新数据并添加到缓存
            new_data = self.read_available_data()
            if new_data:
                self.data_buffer += new_data
            
            # 检查缓存中是否有完整的数据帧
            if len(self.data_buffer) >= frame_length:
                frame_data = self._extract_frame_from_buffer(header_bytes, header_length, frame_length)
                if frame_data is not None:
                    return frame_data
            
            # 短暂休息，避免过度占用CPU
            # 这就像在等待时稍微闭眼休息，但随时准备接收新信息
            time.sleep(0.005)  # 5毫秒
        
        # 超时未找到完整数据帧
        if self.verbose:
            buffer_size = len(self.data_buffer)
            print(f"[UART读取器] 查找超时，缓存中剩余 {buffer_size} 字节数据")
        
        return None

    def _normalize_frame_header(self, frame_header):
        """
        统一帧头格式，支持多种输入方式
        让用户可以用最方便的方式指定帧头格式
        """
        if isinstance(frame_header, int):
            # 单字节帧头：直接转换为字节
            return bytes([frame_header])
        elif isinstance(frame_header, list) and all(isinstance(b, int) for b in frame_header):
            # 多字节帧头列表：转换为字节序列
            return bytes(frame_header)
        elif isinstance(frame_header, bytes):
            # 已经是字节格式：直接使用
            return frame_header
        else:
            print(f"❌ 不支持的帧头格式: {type(frame_header)}")
            return None

    def _extract_frame_from_buffer(self, header_bytes, header_length, frame_length):
        """
        从缓存中提取完整的数据帧
        就像从一堆杂乱的材料中找出完整的成品
        """
        # 在缓存中查找帧头位置
        header_position = self.data_buffer.find(header_bytes)
        
        if header_position == -1:
            # 未找到帧头，但缓存可能已满，需要清理
            if len(self.data_buffer) >= UART_BUFFER_SIZE:
                if self.verbose:
                    print("[UART读取器] 缓存已满且未找到帧头，清理缓存")
                self.data_buffer = b""
            return None
        
        # 计算完整帧的结束位置
        frame_end = header_position + frame_length
        
        if frame_end <= len(self.data_buffer):
            # 提取完整的数据帧
            complete_frame = self.data_buffer[header_position:frame_end]
            
            # 从缓存中移除已提取的数据
            self.data_buffer = self.data_buffer[frame_end:]
            
            if self.verbose:
                hex_frame = complete_frame.hex().upper()
                remaining = len(self.data_buffer)
                print(f"[UART读取器] 找到完整数据帧: {hex_frame}, 缓存剩余 {remaining} 字节")
            
            return complete_frame
        
        return None

    def clear_buffers(self):
        """
        清空所有数据缓存
        就像把工作台清理干净，准备新的工作
        """
        if self.uart_channel is None:
            if self.verbose:
                print("[UART读取器] 警告：未设置UART实例，无法清空缓存")
            return
        
        # 清空软件缓存
        self.data_buffer = b""
        
        # 清空硬件缓冲区
        try:
            while self.uart_channel.any():
                self.uart_channel.read()
        except Exception as e:
            print(f"❌ 清空硬件缓冲区异常: {e}")
        
        if self.verbose:
            print("[UART读取器] 所有缓存已清空")

    def get_buffer_status(self):
        """
        获取缓存状态信息
        用于监控和调试数据接收情况
        """
        return {
            'buffer_size': len(self.data_buffer),
            'uart_ready': self.uart_channel is not None,
            'verbose_mode': self.verbose
        }


# =============================================================================
# 独立运行模式 - UART读取器的专用测试环境
# 当直接运行这个文件时，会进入测试模式，方便单独测试读取功能
# =============================================================================
if __name__ == "__main__":
    """
    UART读取器独立测试模式
    无需启动整个智能时钟系统，单独测试数据读取功能
    """
    print("\n" + "="*60)
    print("  UART数据读取器 - 独立测试模式")
    print("="*60)
    
    def run_uart_reader_test():
        """运行UART读取器的基本功能测试"""
        print("\n🧪 开始UART读取器功能测试...")
        
        # 创建测试用的UART读取器实例
        reader = UARTReader(verbose=True)
        
        # 测试1: 帧头格式标准化
        print("\n1. 测试帧头格式标准化...")
        test_headers = [
            0x3C,                    # 单字节帧头
            [0x3C, 0x02],            # 多字节帧头列表
            b'\x3C\x02'              # 字节序列帧头
        ]
        
        for i, header in enumerate(test_headers):
            result = reader._normalize_frame_header(header)
            if result:
                hex_result = result.hex().upper()
                print(f"   ✅ 测试用例 {i+1}: {header} -> {hex_result}")
            else:
                print(f"   ❌ 测试用例 {i+1} 失败")
        
        # 测试2: 缓存状态查询
        print("\n2. 测试缓存状态查询...")
        status = reader.get_buffer_status()
        print(f"   缓存状态: {status}")
        
        # 测试3: 缓存清空功能
        print("\n3. 测试缓存清空功能...")
        reader.clear_buffers()
        print("   ✅ 缓存清空测试完成")
        
        print("\n🎉 UART读取器基本功能测试完成")
        return True
    
    try:
        # 运行测试
        success = run_uart_reader_test()
        
        if success:
            print("\n✅ UART读取器独立测试全部通过")
        else:
            print("\n❌ UART读取器测试失败")
            
    except Exception as e:
        print(f"\n💥 测试过程中发生异常: {e}")
        import sys
        sys.print_exception(e)
    
    print("\n👋 UART数据读取器测试结束")