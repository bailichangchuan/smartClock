"""
串口屏数据推送工具 - 智能时钟的显示管家
功能：向串口屏发送数据指令，控制屏幕显示内容和属性
特点：通用指令格式、协议兼容、防数据拥堵、异常安全
"""

# 导入时间工具模块 - 提供精确的延时控制
import utime

# 导入系统配置 - 使用面向用户的友好配置项
from config import (
    # 调试开关
    SCREEN_DEBUG, GLOBAL_DEBUG,
    # 系统配置
    UART_TIMEOUT
)


class ScreenDataUploader:
    """
    串口屏数据推送专家 - 智能时钟的显示控制中心
    负责向串口屏发送各种显示指令，确保用户界面准确反映系统状态
    就像一位专业的舞台灯光师，精确控制每个显示元素的呈现
    """
    
    # 串口屏通信协议常量
    COMMAND_END_SEQUENCE = bytes([0xFF, 0xFF, 0xFF])  # 指令结束标志
    MINIMAL_DELAY_MS = 10                             # 最小延迟时间（毫秒）
    
    def __init__(self, verbose=None):
        """
        初始化屏幕数据推送工具
        
        参数说明：
        - verbose: 详细日志开关（如果为None，使用配置中的SCREEN_DEBUG）
        """
        # 设置调试模式：优先使用参数，其次使用配置开关
        self.verbose = verbose if verbose is not None else SCREEN_DEBUG
        
        # 推送统计信息
        self.upload_stats = {
            'success_count': 0,      # 成功推送次数
            'fail_count': 0,         # 推送失败次数
            'last_upload_time': 0,   # 最后一次推送时间
            'total_data_sent': 0     # 总发送数据量（字节）
        }
        
        if self.verbose:
            print("[屏幕推送] 屏幕数据推送工具初始化完成")

    def upload_data(self, uart_instance, data_content, control_name="t0", property_name="txt"):
        """
        向串口屏指定控件推送数据
        核心功能：将各种数据（时间、天气、传感器值等）准确显示在屏幕指定位置
        
        参数说明：
        - uart_instance: 串口屏专用UART实例（必须已初始化）
        - data_content: 要显示的数据内容（支持字符串、数字等）
        - control_name: 屏幕控件名称（如"t0", "t1", "b0"等）
        - property_name: 控件属性名称（如"txt"文本, "pic"图片, "font"字体等）
        
        返回：推送是否成功
        """
        # 第一步：验证输入参数的合理性
        validation_result = self._validate_upload_parameters(
            uart_instance, data_content, control_name, property_name
        )
        if not validation_result:
            return False
        
        if self.verbose:
            print(f"[屏幕推送] 准备推送数据: 控件={control_name}, 属性={property_name}, 内容={data_content}")
        
        try:
            # 第二步：构建完整的屏幕指令
            screen_command = self._build_screen_command(data_content, control_name, property_name)
            if screen_command is None:
                return False
            
            # 第三步：发送指令到串口屏
            send_success = self._send_to_screen(uart_instance, screen_command)
            
            # 第四步：更新推送统计
            self._update_upload_stats(send_success, len(screen_command))
            
            return send_success
            
        except Exception as e:
            # 捕获所有未预期的异常，确保系统稳定
            print(f"❌ 屏幕数据推送异常 (控件:{control_name}): {e}")
            self.upload_stats['fail_count'] += 1
            return False

    def _validate_upload_parameters(self, uart_instance, data_content, control_name, property_name):
        """
        验证推送参数的合理性
        确保所有输入参数都符合要求，避免无效操作
        """
        # 检查UART实例是否有效
        if uart_instance is None:
            print("❌ 屏幕推送失败：UART实例为空，请确保屏幕通信已初始化")
            return False
        
        # 检查数据内容是否有效
        if data_content is None:
            print("❌ 屏幕推送失败：数据内容为空")
            return False
        
        # 检查控件名称格式
        if not control_name or not isinstance(control_name, str):
            print("❌ 屏幕推送失败：控件名称格式错误")
            return False
        
        # 检查属性名称格式
        if not property_name or not isinstance(property_name, str):
            print("❌ 屏幕推送失败：属性名称格式错误")
            return False
        
        # 将数据内容转换为字符串（确保兼容数字等其他类型）
        try:
            str_data = str(data_content)
            if len(str_data) == 0:
                print("⚠️ 屏幕推送警告：数据内容为空字符串")
        except Exception as e:
            print(f"❌ 屏幕推送失败：数据内容转换错误 - {e}")
            return False
        
        return True

    def _build_screen_command(self, data_content, control_name, property_name):
        """
        构建屏幕显示指令
        按照串口屏通信协议组装完整的指令数据包
        """
        try:
            # 将数据内容转换为字符串（确保兼容性）
            data_string = str(data_content)
            
            # 构建标准指令格式：控件名.属性名="数据内容"
            # 示例：t0.txt="2024-01-01" 或 b0.pic="1"
            command_string = f'{control_name}.{property_name}="{data_string}"'
            
            if self.verbose:
                print(f"[屏幕推送] 构建指令: {command_string}")
            
            # 转换为字节序列（串口通信需要字节格式）
            command_bytes = command_string.encode('utf-8')
            
            # 添加指令结束序列（三字节0xFF）
            full_command = command_bytes + self.COMMAND_END_SEQUENCE
            
            return full_command
            
        except Exception as e:
            print(f"❌ 构建屏幕指令失败: {e}")
            return None

    def _send_to_screen(self, uart_instance, command_data):
        """
        向串口屏发送指令数据
        确保指令可靠地发送到屏幕，并处理可能的通信异常
        """
        try:
            # 第一步：发送指令数据
            bytes_sent = uart_instance.write(command_data)
            
            # 第二步：验证发送是否完整
            if bytes_sent != len(command_data):
                print(f"❌ 屏幕推送不完整: 期望{len(command_data)}字节, 实际{bytes_sent}字节")
                return False
            
            # 第三步：短暂延时，确保指令处理完成
            # 这就像给屏幕一点"消化"时间，避免指令拥堵
            utime.sleep_ms(self.MINIMAL_DELAY_MS)
            
            if self.verbose:
                hex_data = command_data.hex().upper()
                print(f"[屏幕推送] 指令发送成功: {hex_data}")
            
            return True
            
        except Exception as e:
            print(f"❌ 屏幕指令发送异常: {e}")
            return False

    def _update_upload_stats(self, success, data_length):
        """
        更新推送统计信息
        记录成功/失败次数和数据量，用于监控和调试
        """
        current_time = utime.time()
        
        if success:
            self.upload_stats['success_count'] += 1
            self.upload_stats['total_data_sent'] += data_length
            self.upload_stats['last_upload_time'] = current_time
        else:
            self.upload_stats['fail_count'] += 1

    def upload_time_display(self, uart_instance, time_data, control_name="t2"):
        """
        专用方法：更新时间显示
        优化时间显示的特殊处理，确保时间显示的准确性和效率
        """
        if self.verbose:
            print(f"[屏幕推送] 更新时间显示: {time_data} → 控件{control_name}")
        
        return self.upload_data(uart_instance, time_data, control_name, "txt")

    def upload_date_display(self, uart_instance, date_data, control_name="t0"):
        """
        专用方法：更新日期显示
        日期显示的特殊优化处理
        """
        if self.verbose:
            print(f"[屏幕推送] 更新日期显示: {date_data} → 控件{control_name}")
        
        return self.upload_data(uart_instance, date_data, control_name, "txt")

    def upload_weather_display(self, uart_instance, weather_data, control_name="t4"):
        """
        专用方法：更新天气显示
        天气信息显示的特殊处理
        """
        if self.verbose:
            print(f"[屏幕推送] 更新天气显示: {weather_data} → 控件{control_name}")
        
        return self.upload_data(uart_instance, weather_data, control_name, "txt")

    def upload_temperature_display(self, uart_instance, temp_data, control_name="t5"):
        """
        专用方法：更新温度显示
        温度数据显示的特殊处理
        """
        if self.verbose:
            print(f"[屏幕推送] 更新温度显示: {temp_data} → 控件{control_name}")
        
        return self.upload_data(uart_instance, temp_data, control_name, "txt")

    def set_screen_brightness(self, uart_instance, brightness_level, control_name="dim"):
        """
        专用方法：设置屏幕亮度
        特殊的亮度控制指令，不同于常规的数据显示
        """
        try:
            # 亮度控制指令格式特殊：dim=亮度值
            brightness_level = max(0, min(100, brightness_level))  # 限制范围0-100
            command_string = f"{control_name}={brightness_level}"
            command_bytes = command_string.encode('utf-8') + self.COMMAND_END_SEQUENCE
            
            bytes_sent = uart_instance.write(command_bytes)
            utime.sleep_ms(self.MINIMAL_DELAY_MS)
            
            if self.verbose:
                print(f"[屏幕推送] 设置屏幕亮度: {brightness_level}%")
            
            return bytes_sent == len(command_bytes)
            
        except Exception as e:
            print(f"❌ 设置屏幕亮度失败: {e}")
            return False

    def get_upload_statistics(self):
        """
        获取推送统计信息
        用于监控屏幕数据推送的性能和可靠性
        """
        return {
            'success_count': self.upload_stats['success_count'],
            'fail_count': self.upload_stats['fail_count'],
            'last_upload_time': self.upload_stats['last_upload_time'],
            'total_data_sent': self.upload_stats['total_data_sent'],
            'success_rate': self._calculate_success_rate(),
            'verbose_mode': self.verbose
        }

    def _calculate_success_rate(self):
        """
        计算推送成功率
        基于成功和失败次数计算当前的成功率百分比
        """
        total_attempts = self.upload_stats['success_count'] + self.upload_stats['fail_count']
        if total_attempts == 0:
            return 100.0  # 没有尝试时默认100%成功率
        
        success_rate = (self.upload_stats['success_count'] / total_attempts) * 100
        return round(success_rate, 1)

    def reset_statistics(self):
        """
        重置统计信息
        清空所有计数，重新开始统计
        """
        self.upload_stats = {
            'success_count': 0,
            'fail_count': 0,
            'last_upload_time': 0,
            'total_data_sent': 0
        }
        
        if self.verbose:
            print("[屏幕推送] 推送统计已重置")


# 创建全局屏幕数据推送器实例（兼容旧代码）
_screen_uploader = ScreenDataUploader()

# 兼容旧代码的全局函数
def upload(uart, data_content, control_name="t0", property_name="txt"):
    """
    向串口屏推送数据（兼容旧代码接口）
    
    参数说明：
    - uart: 串口屏UART实例
    - data_content: 要显示的数据内容
    - control_name: 控件名称（默认"t0"）
    - property_name: 属性名称（默认"txt"）
    """
    return _screen_uploader.upload_data(uart, data_content, control_name, property_name)


# =============================================================================
# 独立运行模式 - 屏幕数据推送工具的专用测试环境
# 当直接运行这个文件时，会进入测试模式，方便单独测试推送功能
# =============================================================================
if __name__ == "__main__":
    """
    屏幕数据推送工具独立测试模式
    无需启动整个智能时钟系统，单独测试数据推送功能
    """
    print("\n" + "="*60)
    print("  屏幕数据推送工具 - 独立测试模式")
    print("="*60)
    
    def run_screen_upload_test():
        """运行屏幕数据推送工具的基本功能测试"""
        print("\n🧪 开始屏幕数据推送功能测试...")
        
        # 创建测试用的屏幕数据推送器实例
        upload_tool = ScreenDataUploader(verbose=True)
        
        print("1. 测试指令构建功能...")
        test_cases = [
            ("Hello World", "t0", "txt"),
            ("2024-01-01", "t1", "txt"), 
            ("25°C", "t2", "txt")
        ]
        
        for data, control, prop in test_cases:
            command = upload_tool._build_screen_command(data, control, prop)
            if command:
                command_str = command.decode('utf-8', errors='ignore')
                print(f"   ✅ 构建指令: {command_str}")
            else:
                print(f"   ❌ 构建指令失败: {data} → {control}.{prop}")
        
        print("2. 测试参数验证功能...")
        # 测试无效参数
        invalid_cases = [
            (None, "test", "t0", "txt"),  # 无效UART
            ("data", "", "txt"),           # 无效控件名
            ("data", "t0", ""),            # 无效属性名
        ]
        
        for uart, data, control, prop in invalid_cases:
            result = upload_tool._validate_upload_parameters(uart, data, control, prop)
            print(f"   验证参数: UART={uart is not None}, 数据='{data}' → {'有效' if result else '无效'}")
        
        print("3. 测试统计功能...")
        stats = upload_tool.get_upload_statistics()
        print(f"   初始统计: {stats}")
        
        # 模拟一些推送操作
        upload_tool.upload_stats['success_count'] = 5
        upload_tool.upload_stats['fail_count'] = 1
        stats_updated = upload_tool.get_upload_statistics()
        print(f"   更新统计: 成功率={stats_updated['success_rate']}%")
        
        print("4. 测试专用显示方法...")
        # 创建模拟UART用于测试
        class MockUART:
            def write(self, data):
                if SCREEN_DEBUG:
                    data_str = data.decode('utf-8', errors='ignore') if isinstance(data, bytes) else str(data)
                    print(f"[模拟屏幕] 接收数据: {data_str}")
                return len(data)
        
        mock_uart = MockUART()
        
        # 测试专用方法
        test_methods = [
            ("更新时间", upload_tool.upload_time_display, "12:30"),
            ("更新日期", upload_tool.upload_date_display, "2024-01-01"),
            ("更新天气", upload_tool.upload_weather_display, "晴天"),
            ("更新温度", upload_tool.upload_temperature_display, "25°C")
        ]
        
        for desc, method, data in test_methods:
            result = method(mock_uart, data)
            print(f"   {desc}: {'成功' if result else '失败'}")
        
        print("5. 测试亮度控制...")
        brightness_result = upload_tool.set_screen_brightness(mock_uart, 80)
        print(f"   亮度控制: {'成功' if brightness_result else '失败'}")
        
        print("\n🎉 屏幕数据推送工具基本功能测试完成")
        return True
    
    try:
        # 运行测试
        success = run_screen_upload_test()
        
        if success:
            print("\n✅ 屏幕数据推送工具独立测试通过")
        else:
            print("\n❌ 屏幕数据推送工具测试失败")
            
    except Exception as e:
        print(f"\n💥 测试过程中发生异常: {e}")
        import sys
        sys.print_exception(e)
    
    print("\n👋 屏幕数据推送工具测试结束")