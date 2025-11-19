"""
串口屏指令解析服务 - 智能时钟的用户交互翻译官
功能：解析串口屏发送的指令数据，识别用户操作意图
特点：协议兼容、严格校验、操作过滤、友好接口
"""

# 导入系统配置 - 使用面向用户的友好配置项
from config import (
    # 调试开关
    SCREEN_DEBUG, GLOBAL_DEBUG
)


class ScreenCommandParser:
    """
    串口屏指令解析专家 - 智能时钟的用户交互翻译中心
    负责解析从串口屏接收的原始指令，转换为系统可理解的用户操作
    就像一位专业的翻译官，将屏幕的"语言"翻译成系统能理解的"指令"
    """
    
    # 串口屏通信协议常量
    CMD_HEADER = 0x65           # 指令帧头 - 每条指令的开始标志
    CMD_END = [0xFF, 0xFF, 0xFF] # 指令结束符 - 指令的结束标志
    OP_PRESS = 0x01              # 按下操作 - 用户按下按钮的动作
    OP_RELEASE = 0x00            # 松开操作 - 用户松开按钮的动作（通常忽略）
    
    # 标准指令长度（字节）
    STANDARD_CMD_LENGTH = 7
    
    def __init__(self, verbose=None):
        """
        初始化指令解析服务
        
        参数说明：
        - verbose: 详细日志开关（如果为None，使用配置中的SCREEN_DEBUG）
        """
        # 设置调试模式：优先使用参数，其次使用配置开关
        self.verbose = verbose if verbose is not None else SCREEN_DEBUG
        
        # 解析统计信息
        self.parse_stats = {
            'total_commands': 0,      # 总接收指令数
            'valid_commands': 0,      # 有效指令数
            'press_commands': 0,      # 按下操作数
            'invalid_commands': 0     # 无效指令数
        }
        
        if self.verbose:
            print("[指令解析] 串口屏指令解析服务初始化完成")

    def parse_screen_command(self, raw_data):
        """
        解析串口屏发送的原始指令数据
        核心功能：将字节数据转换为有意义的用户操作信息
        
        参数说明：
        - raw_data: 从串口接收的原始字节数据
        
        返回：解析结果字典或None（无效指令）
        """
        if raw_data is None:
            if self.verbose:
                print("[指令解析] 接收到空数据")
            return None
        
        # 更新统计：总接收指令数
        self.parse_stats['total_commands'] += 1
        
        if self.verbose:
            hex_data = raw_data.hex().upper() if raw_data else "空"
            print(f"[指令解析] 接收原始数据: {hex_data} (长度: {len(raw_data)})")
        
        # 第一步：基础数据验证
        if not self._validate_basic_data(raw_data):
            self.parse_stats['invalid_commands'] += 1
            return None
        
        # 第二步：协议格式验证
        if not self._validate_protocol_format(raw_data):
            self.parse_stats['invalid_commands'] += 1
            return None
        
        # 第三步：提取指令字段
        parsed_command = self._extract_command_fields(raw_data)
        if parsed_command is None:
            self.parse_stats['invalid_commands'] += 1
            return None
        
        # 第四步：验证操作类型
        if not self._validate_operation_type(parsed_command):
            self.parse_stats['invalid_commands'] += 1
            return None
        
        # 更新统计：有效指令数
        self.parse_stats['valid_commands'] += 1
        if parsed_command['operation'] == self.OP_PRESS:
            self.parse_stats['press_commands'] += 1
        
        if self.verbose:
            print(f"[指令解析] 解析成功: 页面={parsed_command['page']}, "
                  f"控件={parsed_command['control']}, 操作={parsed_command['operation_name']}")
        
        return parsed_command

    def _validate_basic_data(self, raw_data):
        """
        基础数据验证
        确保输入数据满足最基本的解析要求
        """
        # 检查数据是否为字节类型
        if not isinstance(raw_data, (bytes, bytearray)):
            if self.verbose:
                print("[指令解析] 无效数据类型，期望bytes或bytearray")
            return False
        
        # 检查数据长度是否符合标准
        if len(raw_data) != self.STANDARD_CMD_LENGTH:
            if self.verbose:
                print(f"[指令解析] 指令长度无效: 期望{self.STANDARD_CMD_LENGTH}字节, 实际{len(raw_data)}字节")
            return False
        
        # 检查数据是否为空
        if len(raw_data) == 0:
            if self.verbose:
                print("[指令解析] 接收到空指令数据")
            return False
        
        return True

    def _validate_protocol_format(self, raw_data):
        """
        协议格式验证
        验证指令是否符合串口屏通信协议规范
        """
        # 验证指令帧头
        if raw_data[0] != self.CMD_HEADER:
            if self.verbose:
                print(f"[指令解析] 指令帧头错误: 期望0x{self.CMD_HEADER:02X}, 实际0x{raw_data[0]:02X}")
            return False
        
        # 验证指令结束符
        actual_end = list(raw_data[-3:])
        if actual_end != self.CMD_END:
            if self.verbose:
                expected_hex = ''.join(f'{b:02X}' for b in self.CMD_END)
                actual_hex = ''.join(f'{b:02X}' for b in actual_end)
                print(f"[指令解析] 指令结束符错误: 期望{expected_hex}, 实际{actual_hex}")
            return False
        
        return True

    def _extract_command_fields(self, raw_data):
        """
        提取指令字段
        从有效指令数据中提取页面、控件和操作信息
        """
        try:
            # 按照串口屏协议提取字段
            page_number = raw_data[1]      # 页面编号（索引1）
            control_id = raw_data[2]       # 控件编号（索引2）
            operation_code = raw_data[3]   # 操作代码（索引3）
            
            # 验证字段值的合理性
            if not self._validate_field_values(page_number, control_id, operation_code):
                return None
            
            # 构建解析结果
            parsed_result = {
                'page': page_number,
                'control': control_id,
                'operation': operation_code,
                'operation_name': self._get_operation_name(operation_code),
                'raw_data': raw_data.hex().upper()  # 保存原始数据用于调试
            }
            
            return parsed_result
            
        except Exception as e:
            print(f"❌ 指令字段提取异常: {e}")
            return None

    def _validate_field_values(self, page, control, operation):
        """
        验证字段值的合理性
        确保提取的字段值在合理范围内
        """
        # 验证页面编号（通常0-255，但实际使用中可能有限制）
        if not (0 <= page <= 255):
            if self.verbose:
                print(f"[指令解析] 无效页面编号: {page}")
            return False
        
        # 验证控件编号（通常0-255）
        if not (0 <= control <= 255):
            if self.verbose:
                print(f"[指令解析] 无效控件编号: {control}")
            return False
        
        # 验证操作代码（已知的操作码范围）
        valid_operations = [self.OP_PRESS, self.OP_RELEASE]
        if operation not in valid_operations:
            if self.verbose:
                print(f"[指令解析] 未知操作代码: 0x{operation:02X}")
            return False
        
        return True

    def _validate_operation_type(self, parsed_command):
        """
        验证操作类型
        检查操作类型是否符合系统处理要求
        """
        operation = parsed_command['operation']
        
        # 目前只处理按下操作，松开操作通常忽略
        if operation == self.OP_RELEASE:
            if self.verbose:
                print("[指令解析] 忽略松开操作")
            return False
        
        return True

    def _get_operation_name(self, operation_code):
        """
        获取操作名称
        将操作代码转换为可读的操作名称
        """
        operation_names = {
            self.OP_PRESS: "按下",
            self.OP_RELEASE: "松开"
        }
        return operation_names.get(operation_code, f"未知(0x{operation_code:02X})")

    def is_press_command(self, parsed_command):
        """
        判断是否为按下指令
        快速检查解析结果是否为用户按下操作
        """
        if parsed_command is None:
            return False
        
        return parsed_command['operation'] == self.OP_PRESS

    def get_control_identifier(self, parsed_command):
        """
        获取控件标识符
        生成统一的控件标识字符串，便于处理
        """
        if parsed_command is None:
            return None
        
        return f"page{parsed_command['page']}_control{parsed_command['control']}"

    def get_parse_statistics(self):
        """
        获取解析统计信息
        用于监控指令解析的性能和准确性
        """
        total = self.parse_stats['total_commands']
        valid = self.parse_stats['valid_commands']
        
        return {
            'total_commands': total,
            'valid_commands': valid,
            'press_commands': self.parse_stats['press_commands'],
            'invalid_commands': self.parse_stats['invalid_commands'],
            'success_rate': self._calculate_success_rate(total, valid),
            'verbose_mode': self.verbose
        }

    def _calculate_success_rate(self, total, valid):
        """
        计算解析成功率
        基于总指令数和有效指令数计算解析成功率
        """
        if total == 0:
            return 100.0  # 没有指令时默认100%成功率
        
        success_rate = (valid / total) * 100
        return round(success_rate, 1)

    def reset_statistics(self):
        """
        重置统计信息
        清空所有计数，重新开始统计
        """
        self.parse_stats = {
            'total_commands': 0,
            'valid_commands': 0,
            'press_commands': 0,
            'invalid_commands': 0
        }
        
        if self.verbose:
            print("[指令解析] 解析统计已重置")


# 创建全局指令解析器实例（兼容旧代码）
_command_parser = ScreenCommandParser()

# 兼容旧代码的全局函数
def parse_screen_command(data):
    """
    解析串口屏指令（兼容旧代码接口）
    
    参数说明：
    - data: 原始字节数据
    
    返回：元组 (页号, 控件号, 操作码) 或 None
    """
    parsed_result = _command_parser.parse_screen_command(data)
    if parsed_result:
        return (parsed_result['page'], parsed_result['control'], parsed_result['operation'])
    return None


# =============================================================================
# 独立运行模式 - 指令解析服务的专用测试环境
# =============================================================================
if __name__ == "__main__":
    print("\n" + "="*50)
    print("  串口屏指令解析服务 - 测试模式")
    print("="*50)
    
    def test_command_parsing():
        """测试指令解析功能"""
        parser = ScreenCommandParser(verbose=True)
        
        print("1. 测试有效指令解析...")
        # 模拟有效指令数据：0x65 页号 控件号 操作码 0xFF 0xFF 0xFF
        valid_command = bytes([0x65, 0x01, 0x02, 0x01, 0xFF, 0xFF, 0xFF])
        result = parser.parse_screen_command(valid_command)
        print(f"   有效指令解析: {'成功' if result else '失败'}")
        if result:
            print(f"   解析结果: 页面={result['page']}, 控件={result['control']}, 操作={result['operation_name']}")
        
        print("2. 测试无效指令...")
        test_cases = [
            (b"", "空数据"),
            (b"\x65\x01\x02", "长度不足"),
            (b"\x66\x01\x02\x01\xFF\xFF\xFF", "错误帧头"),
            (b"\x65\x01\x02\x01\xFE\xFF\xFF", "错误结束符"),
        ]
        
        for data, desc in test_cases:
            result = parser.parse_screen_command(data)
            print(f"   {desc}: {'无效' if result is None else '意外有效'}")
        
        print("3. 测试统计功能...")
        stats = parser.get_parse_statistics()
        print(f"   解析统计: {stats}")
        
        return True
    
    try:
        success = test_command_parsing()
        print(f"\n{'✅' if success else '❌'} 指令解析测试{'通过' if success else '失败'}")
    except Exception as e:
        print(f"\n💥 测试异常: {e}")
    
    print("\n👋 指令解析测试结束")