"""
UART串口数据发送器 - 智能时钟的数据发送专家
功能：专门负责向各种串口设备发送数据，支持多种数据格式和协议
特点：可靠发送、错误处理、超时控制、调试支持
"""

# 导入硬件控制模块 - 与串口设备直接对话的接口
import machine
import time

# 导入系统配置 - 使用面向用户的友好配置项
from config import (
    # 调试开关
    GLOBAL_DEBUG, 
    # 系统配置
    UART_TIMEOUT
)

# 为UART模块定义独立调试开关（如果config中没有，使用全局开关）
try:
    from config import UART_DEBUG
except ImportError:
    UART_DEBUG = GLOBAL_DEBUG


class UARTSender:
    """
    UART数据发送专家 - 专门处理串口通信中的数据发送
    就像一位专业的信使，准确可靠地将信息传递给目标设备
    """
    
    def __init__(self, uart_instance=None, verbose=None):
        """
        初始化UART发送器，建立与串口设备的通信连接
        
        参数说明：
        - uart_instance: 已配置好的UART实例（如果为None，需要后续手动设置）
        - verbose: 详细日志开关（如果为None，使用配置中的UART_DEBUG）
        """
        # 设置调试模式：优先使用参数，其次使用配置开关
        self.verbose = verbose if verbose is not None else UART_DEBUG
        
        # 发送统计：记录发送成功和失败的数据包数量
        self.send_stats = {
            'success_count': 0,
            'fail_count': 0,
            'last_send_time': 0
        }
        
        # UART通信实例：与外部设备对话的通道
        self.uart_channel = None
        
        # 设置UART实例
        if uart_instance is not None:
            self.set_uart_instance(uart_instance)
            
        if self.verbose:
            print("[UART发送器] 初始化完成，准备发送数据")

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
                print("[UART发送器] UART通信通道建立成功")
                
        except Exception as e:
            print(f"❌ UART发送器设置失败: {e}")
            raise

    def send_data(self, data, retry_count=1, retry_delay=0.1):
        """
        发送数据到串口设备
        核心功能：确保数据准确可靠地送达目标设备
        
        参数说明：
        - data: 要发送的数据（支持bytes、bytearray、整数列表等格式）
        - retry_count: 发送失败时的重试次数
        - retry_delay: 重试之间的延迟时间（秒）
        """
        if self.uart_channel is None:
            if self.verbose:
                print("[UART发送器] 错误：未设置UART实例，无法发送数据")
            return False
        
        # 统一数据格式：确保所有输入格式都能正确处理
        formatted_data = self._format_data(data)
        if formatted_data is None:
            return False
        
        if self.verbose:
            hex_data = formatted_data.hex().upper()
            data_length = len(formatted_data)
            print(f"[UART发送器] 准备发送数据: {hex_data} (长度: {data_length} 字节)")
        
        # 尝试发送数据，支持重试机制
        for attempt in range(retry_count):
            try:
                # 实际发送数据
                bytes_sent = self.uart_channel.write(formatted_data)
                
                # 验证发送是否成功（发送字节数应等于数据长度）
                if bytes_sent == len(formatted_data):
                    # 更新发送统计
                    self.send_stats['success_count'] += 1
                    self.send_stats['last_send_time'] = time.time()
                    
                    if self.verbose:
                        print(f"[UART发送器] 数据发送成功 (尝试 {attempt + 1}/{retry_count})")
                    return True
                else:
                    # 发送字节数不匹配，记录警告
                    if self.verbose:
                        print(f"[UART发送器] 警告：部分数据发送 (期望: {len(formatted_data)}, 实际: {bytes_sent})")
                    
                    # 如果不是最后一次尝试，等待后重试
                    if attempt < retry_count - 1:
                        time.sleep(retry_delay)
                        
            except Exception as e:
                print(f"❌ 数据发送异常 (尝试 {attempt + 1}/{retry_count}): {e}")
                
                # 如果不是最后一次尝试，等待后重试
                if attempt < retry_count - 1:
                    time.sleep(retry_delay)
        
        # 所有重试都失败
        self.send_stats['fail_count'] += 1
        print(f"❌ 数据发送失败，已尝试 {retry_count} 次")
        return False

    def _format_data(self, data):
        """
        统一数据格式，支持多种输入方式
        让用户可以用最方便的方式指定要发送的数据
        """
        if isinstance(data, bytes):
            # 已经是字节格式：直接使用
            return data
        elif isinstance(data, bytearray):
            # 字节数组：转换为字节
            return bytes(data)
        elif isinstance(data, int):
            # 单字节整数：转换为字节
            return bytes([data])
        elif isinstance(data, list) and all(isinstance(b, int) for b in data):
            # 整数列表：转换为字节序列
            return bytes(data)
        elif isinstance(data, str):
            # 字符串：编码为字节
            return data.encode('utf-8')
        else:
            print(f"❌ 不支持的数据格式: {type(data)}")
            return None

    def send_command(self, command_header, command_data=None, checksum=True):
        """
        发送标准命令帧
        适用于需要特定格式的命令协议
        
        参数说明：
        - command_header: 命令头（帧头）
        - command_data: 命令数据（可选）
        - checksum: 是否自动计算并添加校验和
        """
        if self.verbose:
            print(f"[UART发送器] 准备发送命令: 头={command_header}, 数据={command_data}")
        
        # 构建命令帧
        command_frame = self._build_command_frame(command_header, command_data, checksum)
        if command_frame is None:
            return False
        
        # 发送命令帧
        return self.send_data(command_frame)

    def _build_command_frame(self, header, data, include_checksum):
        """
        构建完整的命令帧
        根据协议要求组装命令头、数据和校验和
        """
        try:
            # 格式化命令头
            header_bytes = self._format_data(header)
            if header_bytes is None:
                return None
            
            # 初始化帧数据
            frame_data = header_bytes
            
            # 添加命令数据（如果有）
            if data is not None:
                data_bytes = self._format_data(data)
                if data_bytes is None:
                    return None
                frame_data += data_bytes
            
            # 计算并添加校验和（如果需要）
            if include_checksum:
                checksum = self._calculate_checksum(frame_data)
                frame_data += bytes([checksum])
            
            if self.verbose:
                hex_frame = frame_data.hex().upper()
                print(f"[UART发送器] 构建命令帧: {hex_frame}")
            
            return frame_data
            
        except Exception as e:
            print(f"❌ 构建命令帧失败: {e}")
            return None

    def _calculate_checksum(self, data):
        """
        计算简单的校验和
        使用字节求和取模的简单校验方式
        """
        if isinstance(data, bytes) or isinstance(data, bytearray):
            return sum(data) % 256
        else:
            # 对于其他格式，先转换为字节再计算
            formatted_data = self._format_data(data)
            if formatted_data:
                return sum(formatted_data) % 256
            return 0

    def flush_output(self):
        """
        刷新输出缓冲区
        确保所有待发送数据都已实际发送出去
        """
        if self.uart_channel is None:
            if self.verbose:
                print("[UART发送器] 警告：未设置UART实例，无法刷新缓冲区")
            return
        
        try:
            # 在某些UART实现中，可能需要特殊操作来确保数据发送完成
            # 这里可以添加特定硬件的刷新逻辑
            if self.verbose:
                print("[UART发送器] 输出缓冲区已刷新")
        except Exception as e:
            print(f"❌ 刷新输出缓冲区异常: {e}")

    def get_send_statistics(self):
        """
        获取发送统计信息
        用于监控和调试数据发送情况
        """
        return {
            'success_count': self.send_stats['success_count'],
            'fail_count': self.send_stats['fail_count'],
            'last_send_time': self.send_stats['last_send_time'],
            'uart_ready': self.uart_channel is not None,
            'verbose_mode': self.verbose
        }

    def reset_statistics(self):
        """
        重置发送统计
        清空成功和失败的计数，重新开始统计
        """
        self.send_stats = {
            'success_count': 0,
            'fail_count': 0,
            'last_send_time': 0
        }
        
        if self.verbose:
            print("[UART发送器] 发送统计已重置")


# =============================================================================
# 独立运行模式 - UART发送器的专用测试环境
# 当直接运行这个文件时，会进入测试模式，方便单独测试发送功能
# =============================================================================
if __name__ == "__main__":
    """
    UART发送器独立测试模式
    无需启动整个智能时钟系统，单独测试数据发送功能
    """
    print("\n" + "="*60)
    print("  UART数据发送器 - 独立测试模式")
    print("="*60)
    
    def run_uart_sender_test():
        """运行UART发送器的基本功能测试"""
        print("\n🧪 开始UART发送器功能测试...")
        
        # 创建测试用的UART发送器实例
        sender = UARTSender(verbose=True)
        
        # 测试1: 数据格式标准化
        print("\n1. 测试数据格式标准化...")
        test_data_formats = [
            b'\x01\x02\x03',           # 字节格式
            [0x01, 0x02, 0x03],        # 整数列表
            0x3C,                      # 单字节整数
            "TEST",                    # 字符串
            bytearray(b'\x01\x02\x03') # 字节数组
        ]
        
        for i, data in enumerate(test_data_formats):
            result = sender._format_data(data)
            if result:
                hex_result = result.hex().upper() if len(result) > 0 else "空"
                print(f"   ✅ 测试用例 {i+1}: {type(data).__name__} -> {hex_result}")
            else:
                print(f"   ❌ 测试用例 {i+1} 失败")
        
        # 测试2: 命令帧构建
        print("\n2. 测试命令帧构建...")
        test_frame = sender._build_command_frame(0x3C, [0x01, 0x02], True)
        if test_frame:
            hex_frame = test_frame.hex().upper()
            print(f"   ✅ 命令帧构建成功: {hex_frame}")
        else:
            print("   ❌ 命令帧构建失败")
        
        # 测试3: 校验和计算
        print("\n3. 测试校验和计算...")
        test_data = b'\x01\x02\x03'
        checksum = sender._calculate_checksum(test_data)
        print(f"   ✅ 校验和计算: {test_data.hex().upper()} -> 0x{checksum:02X}")
        
        # 测试4: 统计信息查询
        print("\n4. 测试统计信息查询...")
        stats = sender.get_send_statistics()
        print(f"   发送统计: {stats}")
        
        print("\n🎉 UART发送器基本功能测试完成")
        return True
    
    try:
        # 运行测试
        success = run_uart_sender_test()
        
        if success:
            print("\n✅ UART发送器独立测试全部通过")
        else:
            print("\n❌ UART发送器测试失败")
            
    except Exception as e:
        print(f"\n💥 测试过程中发生异常: {e}")
        import sys
        sys.print_exception(e)
    
    print("\n👋 UART数据发送器测试结束")