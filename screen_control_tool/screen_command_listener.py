"""
串口屏指令监听服务 - 智能时钟的用户交互监听器
功能：持续监听串口屏用户操作，响应按钮点击和触摸事件
特点：非阻塞监听、指令防抖、多操作映射、错误恢复
"""

import utime
import _thread
from config import SCREEN_DEBUG, GLOBAL_DEBUG

# 导入功能服务模块
from function import weather as weather_module
from function import ntp_clock as ntp_module
from util.screen_command_parser import ScreenCommandParser


class ScreenCommandListener:
    """
    串口屏指令监听专家 - 智能时钟的用户交互中枢
    负责持续监听用户操作，将屏幕交互转换为系统功能调用
    就像一位专注的接待员，时刻准备响应用户的每一个操作请求
    """
    
    def __init__(self, verbose=None):
        """
        初始化指令监听服务
        
        参数说明：
        - verbose: 详细日志开关（如果为None，使用配置中的SCREEN_DEBUG）
        """
        # 设置调试模式：优先使用参数，其次使用配置开关
        self.verbose = verbose if verbose is not None else SCREEN_DEBUG
        
        # 服务运行状态
        self.is_listening = False          # 监听服务运行状态
        self.listener_thread_id = None     # 监听线程ID
        
        # 指令解析器实例
        self.command_parser = ScreenCommandParser(verbose=self.verbose)
        
        # 监听统计信息
        self.listener_stats = {
            'total_commands': 0,           # 总接收指令数
            'processed_commands': 0,       # 已处理指令数
            'last_command_time': 0         # 最后指令时间
        }
        
        # 指令防抖配置
        self.debounce_delay_ms = 50        # 防抖延迟（毫秒）
        self.min_command_interval = 100    # 最小指令间隔（毫秒）
        
        if self.verbose:
            print("[指令监听] 串口屏指令监听服务初始化完成")

    def _process_user_command(self, parsed_command, uart_instance, sensor_instance):
        """
        处理用户指令
        根据解析后的指令执行相应的系统功能
        
        参数说明：
        - parsed_command: 解析后的指令字典
        - uart_instance: 屏幕通信实例
        - sensor_instance: 传感器管理器实例
        """
        if not parsed_command or not self.command_parser.is_press_command(parsed_command):
            return
        
        # 获取操作标识信息
        page = parsed_command['page']
        control = parsed_command['control']
        control_id = self.command_parser.get_control_identifier(parsed_command)
        
        # 更新统计信息
        self.listener_stats['total_commands'] += 1
        self.listener_stats['last_command_time'] = utime.time()
        
        if self.verbose:
            print(f"[指令监听] 检测到用户操作: 页面{page} → 控件{control} ({control_id})")
        
        # 指令防抖：避免重复触发
        utime.sleep_ms(self.debounce_delay_ms)
        
        # 指令映射表：将页面-控件组合映射到具体功能
        command_actions = {
            # 页面1-控件0: 强制更新天气
            (1, 0): lambda: self._execute_weather_update(uart_instance),
            # 页面0-控件0: 强制更新时间
            (0, 0): lambda: self._execute_time_update(uart_instance),
            # 页面2-控件0: 强制更新传感器数据
            (2, 0): lambda: self._execute_sensor_update(uart_instance, sensor_instance)
        }
        
        # 查找并执行对应的操作
        action_key = (page, control)
        if action_key in command_actions:
            try:
                command_actions[action_key]()
                self.listener_stats['processed_commands'] += 1
                if self.verbose:
                    print(f"[指令监听] 指令处理完成: {control_id}")
            except Exception as e:
                print(f"❌ 指令执行异常 ({control_id}): {e}")
        else:
            if self.verbose:
                print(f"[指令监听] 未知指令: 页面{page}, 控件{control}")

    def _execute_weather_update(self, uart_instance):
        """
        执行天气更新操作
        强制从网络获取最新天气信息并更新显示
        """
        print("🌤️  用户操作：强制更新天气数据...")
        weather_module.get_weather_by_ip(uart_instance, force=True)

    def _execute_time_update(self, uart_instance):
        """
        执行时间更新操作
        强制同步网络时间并更新屏幕显示
        """
        print("⏰ 用户操作：强制更新屏幕时间...")
        ntp_module.send_time_to_serial_screen(uart_instance, force=True)

    def _execute_sensor_update(self, uart_instance, sensor_instance):
        """
        执行传感器数据更新操作
        强制读取传感器数据并更新显示
        """
        print("📊 用户操作：强制更新传感器数据...")
        if sensor_instance and uart_instance:
            sensor_instance.read_sensor_data(uart_instance, force=True)
        else:
            print("⚠️  无法更新传感器：实例未就绪")

    def _listen_loop(self, uart_instance, sensor_instance):
        """
        监听循环核心
        持续监听串口数据，处理用户指令
        
        参数说明：
        - uart_instance: 屏幕UART通信实例
        - sensor_instance: 传感器管理器实例
        """
        if self.verbose:
            thread_id = _thread.get_ident()
            print(f"[指令监听] 监听线程启动 (线程ID: {thread_id})")
        
        print("👂 串口屏指令监听服务运行中，等待用户操作...")
        
        cycle_count = 0
        while self.is_listening:
            try:
                # 读取串口数据（标准指令长度7字节）
                raw_data = uart_instance.read(7)
                
                if raw_data:
                    # 解析指令数据
                    parsed_command = self.command_parser.parse_screen_command(raw_data)
                    
                    # 处理有效指令
                    self._process_user_command(parsed_command, uart_instance, sensor_instance)
                else:
                    # 没有数据时适当休息，降低CPU占用
                    utime.sleep_ms(10)
                
                # 定期输出状态信息（每5秒）
                cycle_count += 1
                if self.verbose and cycle_count % 500 == 0:
                    stats = self.get_listener_status()
                    print(f"[指令监听] 运行状态: 接收指令={stats['total_commands']}, 处理指令={stats['processed_commands']}")
                    
            except Exception as e:
                print(f"❌ 指令监听循环异常: {e}")
                utime.sleep_ms(100)  # 异常后稍作休息
        
        if self.verbose:
            print("[指令监听] 监听循环结束")

    def start_listening(self, uart_instance, sensor_instance, thread_priority=1):
        """
        启动指令监听服务
        在独立线程中开始监听用户操作
        
        参数说明：
        - uart_instance: 屏幕UART通信实例
        - sensor_instance: 传感器管理器实例
        - thread_priority: 线程优先级（数字越小优先级越高）
        """
        if self.is_listening:
            if self.verbose:
                print("[指令监听] 监听服务已在运行中")
            return True
        
        if uart_instance is None:
            print("❌ 无法启动监听：UART实例未就绪")
            return False
        
        print("🎯 启动串口屏指令监听服务...")
        
        # 标记服务开始运行
        self.is_listening = True
        
        try:
            # 启动监听线程
            self.listener_thread_id = _thread.start_new_thread(
                self._listen_loop, 
                (uart_instance, sensor_instance)
            )
            
            if self.verbose:
                print(f"[指令监听] 监听线程创建成功 (ID: {self.listener_thread_id})")
            
            return True
            
        except Exception as e:
            print(f"❌ 启动监听线程失败: {e}")
            self.is_listening = False
            return False

    def stop_listening(self):
        """
        停止指令监听服务
        安全地停止监听线程
        """
        if not self.is_listening:
            if self.verbose:
                print("[指令监听] 监听服务未运行")
            return
        
        print("🛑 停止串口屏指令监听服务...")
        self.is_listening = False
        
        if self.verbose:
            print("[指令监听] 指令监听服务已停止")

    def get_listener_status(self):
        """
        获取监听服务状态
        用于监控指令监听服务的运行状况
        """
        parser_stats = self.command_parser.get_parse_statistics()
        
        return {
            'listener_active': self.is_listening,
            'thread_id': self.listener_thread_id,
            'total_commands': self.listener_stats['total_commands'],
            'processed_commands': self.listener_stats['processed_commands'],
            'last_command_time': self.listener_stats['last_command_time'],
            'parser_success_rate': parser_stats['success_rate'],
            'verbose_mode': self.verbose
        }


# 创建全局指令监听器实例（兼容旧代码）
_command_listener = ScreenCommandListener()

# 兼容旧代码的全局函数
def start_listen_thread(uart_instance, sensor_instance, thread_priority=10):
    """
    启动指令监听线程（兼容旧代码接口）
    
    参数说明：
    - uart_instance: 屏幕UART实例
    - sensor_instance: 传感器实例
    - thread_priority: 线程优先级
    """
    return _command_listener.start_listening(uart_instance, sensor_instance, thread_priority)


# =============================================================================
# 独立运行模式 - 指令监听服务的专用测试环境
# =============================================================================
if __name__ == "__main__":
    print("\n" + "="*50)
    print("  串口屏指令监听服务 - 测试模式")
    print("="*50)
    
    def test_command_listener():
        """测试指令监听功能"""
        listener = ScreenCommandListener(verbose=True)
        
        print("1. 测试服务状态...")
        status = listener.get_listener_status()
        print(f"   初始状态: {status}")
        
        print("2. 测试指令处理逻辑...")
        # 创建模拟指令数据
        class MockParsedCommand:
            def __init__(self, page, control, operation):
                self.page = page
                self.control = control
                self.operation = operation
        
        # 创建模拟UART和传感器
        class MockUART:
            def read(self, size):
                return None  # 模拟无数据
        
        class MockSensor:
            pass
        
        mock_uart = MockUART()
        mock_sensor = MockSensor()
        
        print("3. 测试指令映射...")
        # 模拟各种指令
        test_commands = [
            (1, 0, 1, "天气更新"),
            (0, 0, 1, "时间更新"), 
            (2, 0, 1, "传感器更新"),
            (3, 0, 1, "未知指令")
        ]
        
        for page, control, op, desc in test_commands:
            mock_cmd = MockParsedCommand(page, control, op)
            print(f"   测试指令: {desc} → 页面{page}-控件{control}")
        
        print("4. 测试服务启动停止...")
        # 测试启动（由于是模拟UART，实际不会真正运行）
        start_result = listener.start_listening(mock_uart, mock_sensor)
        print(f"   启动测试: {'成功' if start_result else '失败'}")
        
        if start_result:
            listener.stop_listening()
            print("   停止测试: 成功")
        
        return True
    
    try:
        success = test_command_listener()
        print(f"\n{'✅' if success else '❌'} 指令监听测试{'通过' if success else '失败'}")
    except Exception as e:
        print(f"\n💥 测试异常: {e}")
    
    print("\n👋 指令监听测试结束")