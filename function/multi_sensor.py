"""
多传感器数据管家 - 智能时钟的环境感知中心
功能：整合多种环境传感器数据，包括空气质量、温湿度等监测
特点：统一数据解析、智能缓存管理、多屏显控支持
"""

# 导入时间管理模块 - 系统的时间感知能力
import utime

# 导入系统配置 - 使用面向用户的友好配置项
from config import (
    # 传感器配置
    SENSOR_READ_INTERVAL, SENSOR_DEBUG, GLOBAL_DEBUG,
    # 通信配置
    SENSOR_UART_PORT, SENSOR_BAUD_RATE
)

# 导入UART通信管理 - 统一的数据收发系统
from util.uart_reader import UARTReader
from util.uart_senter import UARTSender

# 导入屏幕通信工具 - 数据展示的桥梁
from util import sent_to_screen


class MultiSensor:
    """
    多传感器数据管家 - 环境监测的智能中枢
    负责协调各种环境传感器的数据采集、解析和展示
    就像一位细心的环境观察员，时刻关注着周围的空气质量状况
    """
    
    # 传感器通信协议配置 - 与硬件设备对话的语言规则
    SENSOR_FRAME_HEADER = [0x3C, 0x02]  # 数据帧开始的特殊标记
    SENSOR_FRAME_LENGTH = 17            # 完整数据包的长度（字节）
    CHECKSUM_POSITION = 16              # 数据校验码的位置
    
    def __init__(self, uart_manager=None, verbose=None):
        """
        初始化多传感器系统，建立与环境监测设备的通信
        
        参数说明：
        - uart_manager: UART通信管理器（包含reader和sender）
        - verbose: 详细日志开关（如果为None，使用配置中的SENSOR_DEBUG）
        """
        # 设置调试模式：优先使用参数，其次使用配置开关
        self.verbose = verbose if verbose is not None else SENSOR_DEBUG
        
        # 数据读取器 - 专门负责从传感器接收数据
        self.data_reader = None
        
        # 数据发送器 - 专门负责向传感器发送指令（预留功能）
        self.data_sender = None
        
        # 时间控制 - 记录上次数据读取时间，避免过于频繁的请求
        self.last_read_time = 0
        
        # 数据缓存 - 记录已发送到屏幕的数据，避免重复传输
        self.screen_data_cache = {
            'pm25': None,      # 细颗粒物浓度
            'co2': None,       # 二氧化碳浓度  
            'tvoc': None,      # 总挥发性有机物
            'formaldehyde': None,  # 甲醛浓度（预留）
            'pm10': None,      # 可吸入颗粒物（预留）
            'temperature': None,   # 温度（预留）
            'humidity': None      # 湿度（预留）
        }
        
        # 建立传感器通信连接
        self._setup_sensor_communication(uart_manager)
        
        if self.verbose:
            print("[多传感器] 环境监测系统初始化完成")

    def _setup_sensor_communication(self, uart_manager):
        """
        建立与多传感器设备的通信连接
        为环境数据采集准备好通信通道
        """
        try:
            if uart_manager is None:
                raise ValueError("需要传入UART通信管理器来建立传感器连接")
            
            # 从通信管理器中获取数据读取器
            if 'reader' in uart_manager and uart_manager['reader'] is not None:
                self.data_reader = uart_manager['reader']
            else:
                raise ValueError("UART管理器中未找到有效的数据读取器")
            
            # 从通信管理器中获取数据发送器（可选功能）
            if 'sender' in uart_manager and uart_manager['sender'] is not None:
                self.data_sender = uart_manager['sender']
            
            if self.verbose:
                print("[多传感器] 传感器通信通道建立成功")
                
        except Exception as e:
            print(f"❌ 多传感器通信建立失败: {e}")
            if self.verbose:
                print("[多传感器] 系统将在无传感器数据模式下运行")

    def read_sensor_data(self, screen_uart, force_refresh=False):
        """
        读取并处理多传感器数据
        从环境监测设备获取最新数据，并更新显示
        
        参数说明：
        - screen_uart: 屏幕通信实例（用于更新显示）
        - force_refresh: 强制刷新标志（忽略时间间隔限制）
        """
        # 检查系统就绪状态
        if not self._check_system_ready(screen_uart):
            return False
        
        # 检查读取时间间隔（避免过于频繁请求数据）
        if not self._check_read_interval(force_refresh):
            return False
        
        if self.verbose:
            print("[多传感器] 开始读取环境传感器数据...")
        
        try:
            # 清空数据缓存，准备接收新数据
            self.data_reader.clear_buffers()
            
            # 从传感器读取原始数据帧
            sensor_frame = self._read_sensor_frame()
            if sensor_frame is None:
                return False
            
            # 验证数据完整性（校验和检查）
            if not self._validate_data_frame(sensor_frame):
                return False
            
            # 解析传感器数据（将原始字节转换为有意义的数值）
            parsed_data = self._parse_sensor_data(sensor_frame)
            if parsed_data is None:
                return False
            
            # 显示解析结果（控制台输出）
            self._display_sensor_readings(parsed_data)
            
            # 更新屏幕显示（将数据发送到串口屏）
            self._update_screen_display(screen_uart, parsed_data, force_refresh)
            
            # 完成读取，清空缓存准备下一次
            self.data_reader.clear_buffers()
            
            if self.verbose:
                print("[多传感器] 环境数据读取和处理完成")
            
            return True
            
        except Exception as e:
            print(f"❌ 传感器数据读取异常: {e}")
            # 发生异常时也要清空缓存
            if self.data_reader:
                self.data_reader.clear_buffers()
            return False

    def _check_system_ready(self, screen_uart):
        """
        检查系统就绪状态
        确保所有必要的组件都已准备就绪
        """
        if self.data_reader is None:
            if self.verbose:
                print("[多传感器] 数据读取器未就绪，跳过读取")
            return False
        
        if screen_uart is None:
            if self.verbose:
                print("[多传感器] 屏幕通信未就绪，跳过读取")
            return False
        
        return True

    def _check_read_interval(self, force_refresh):
        """
        检查读取时间间隔
        避免过于频繁地向传感器请求数据
        """
        current_time = utime.time()
        time_since_last_read = current_time - self.last_read_time
        
        # 如果强制刷新或已达到读取间隔，允许读取
        if force_refresh or time_since_last_read >= SENSOR_READ_INTERVAL:
            self.last_read_time = current_time
            return True
        
        # 时间间隔未到，跳过本次读取
        if self.verbose:
            remaining_time = SENSOR_READ_INTERVAL - time_since_last_read
            print(f"[多传感器] 未到读取间隔，{remaining_time:.1f}秒后重试")
        
        return False

    def _read_sensor_frame(self):
        """
        从传感器读取完整的数据帧
        耐心等待并接收传感器发送的完整数据包
        """
        if self.verbose:
            print("[多传感器] 等待传感器数据帧...")
        
        total_timeout = 5.0  # 总等待时间（秒）
        start_time = utime.time()
        
        while utime.time() - start_time < total_timeout:
            # 尝试查找符合格式的数据帧
            data_frame = self.data_reader.find_data_frame(
                frame_header=self.SENSOR_FRAME_HEADER,
                frame_length=self.SENSOR_FRAME_LENGTH,
                timeout=0.5  # 每次查找的超时时间
            )
            
            if data_frame is not None:
                if self.verbose:
                    hex_data = data_frame.hex().upper()
                    print(f"[多传感器] 找到有效数据帧: {hex_data}")
                return data_frame
            
            # 短暂休息，避免过度占用CPU
            utime.sleep(0.1)
        
        # 超时未找到有效数据
        if self.verbose:
            print("[多传感器] 传感器数据读取超时")
        return None

    def _validate_data_frame(self, data_frame):
        """
        验证数据帧的完整性
        通过校验和确保数据在传输过程中没有出错
        """
        # 计算校验和（数据帧前16字节的和，取低8位）
        calculated_checksum = sum(data_frame[:self.CHECKSUM_POSITION]) & 0xFF
        frame_checksum = data_frame[self.CHECKSUM_POSITION]
        
        if calculated_checksum == frame_checksum:
            if self.verbose:
                print(f"[多传感器] 数据校验通过 (0x{calculated_checksum:02X})")
            return True
        else:
            print(f"❌ 数据校验失败: 计算值=0x{calculated_checksum:02X}, 接收值=0x{frame_checksum:02X}")
            return False

    def _parse_sensor_data(self, data_frame):
        """
        解析传感器数据帧
        将原始的字节数据转换为有意义的物理量数值
        """
        try:
            # 定义字节合并函数：将高低字节合并为16位整数
            merge_bytes = lambda high_idx, low_idx: (data_frame[high_idx] << 8) | data_frame[low_idx]
            
            # 处理温度数据（支持负数）
            temp_integer = data_frame[12]
            if temp_integer & 0x80:  # 检查符号位
                temp_integer = -(temp_integer & 0x7F)  # 负数处理
            
            # 解析所有传感器参数
            sensor_data = {
                "co2": merge_bytes(2, 3),           # 二氧化碳浓度 (ppm)
                "formaldehyde": round(merge_bytes(4, 5) / 100.0),  # 甲醛浓度 (mg/m³)
                "tvoc": round(merge_bytes(6, 7) / 100.0),          # TVOC浓度 (mg/m³)
                "pm2_5": merge_bytes(8, 9),         # PM2.5浓度 (μg/m³)
                "pm10": merge_bytes(10, 11),        # PM10浓度 (μg/m³)
                "temperature": round(temp_integer + data_frame[13] * 0.1),  # 温度 (℃)
                "humidity": round(data_frame[14] + data_frame[15] * 0.1)    # 湿度 (%RH)
            }
            
            if self.verbose:
                print("[多传感器] 传感器数据解析完成")
            
            return sensor_data
            
        except Exception as e:
            print(f"❌ 传感器数据解析失败: {e}")
            return None

    def _display_sensor_readings(self, sensor_data):
        """
        在控制台显示传感器读数
        为用户提供清晰的环境数据概览
        """
        print("\n" + "="*50)
        print("        环境传感器实时数据")
        print("="*50)
        print(f" 🌫️  空气质量:")
        print(f"    • PM2.5: {sensor_data['pm2_5']} μg/m³")
        print(f"    • PM10:  {sensor_data['pm10']} μg/m³")
        print(f" 🌬️  气体浓度:")
        print(f"    • CO2:   {sensor_data['co2']} ppm")
        print(f"    • TVOC:  {sensor_data['tvoc']} mg/m³")
        print(f"    • 甲醛:   {sensor_data['formaldehyde']} mg/m³")
        print(f" 🌡️  环境条件:")
        print(f"    • 温度:   {sensor_data['temperature']} ℃")
        print(f"    • 湿度:   {sensor_data['humidity']} %RH")
        print("="*50)

    def _update_screen_display(self, screen_uart, sensor_data, force_update):
        """
        更新屏幕显示
        将最新的环境数据发送到串口屏展示
        """
        if self.verbose:
            print("[多传感器] 更新屏幕环境数据显示...")
        
        # 短暂延迟，确保屏幕就绪
        utime.sleep_ms(50)
        
        # PM2.5数据显示（控件t6）
        pm25_display = f"{sensor_data['pm2_5']} μg/m³"
        if force_update or pm25_display != self.screen_data_cache['pm25']:
            sent_to_screen.upload(screen_uart, pm25_display, control_name="t6", property_name="txt")
            self.screen_data_cache['pm25'] = pm25_display
            if self.verbose:
                print(f"[多传感器] 更新PM2.5显示: {pm25_display}")
        
        # CO2浓度显示（控件t7）
        co2_display = f"{sensor_data['co2']} ppm"
        if force_update or co2_display != self.screen_data_cache['co2']:
            sent_to_screen.upload(screen_uart, co2_display, control_name="t7", property_name="txt")
            self.screen_data_cache['co2'] = co2_display
            if self.verbose:
                print(f"[多传感器] 更新CO2显示: {co2_display}")
        
        # TVOC浓度显示（控件t8）
        tvoc_display = f"{sensor_data['tvoc']} mg/m³"
        if force_update or tvoc_display != self.screen_data_cache['tvoc']:
            sent_to_screen.upload(screen_uart, tvoc_display, control_name="t8", property_name="txt")
            self.screen_data_cache['tvoc'] = tvoc_display
            if self.verbose:
                print(f"[多传感器] 更新TVOC显示: {tvoc_display}")
        
        # 其他传感器数据显示（预留功能，取消注释即可启用）
        # 甲醛浓度显示（控件t9）
        # formaldehyde_display = f"{sensor_data['formaldehyde']} mg/m³"
        # if force_update or formaldehyde_display != self.screen_data_cache['formaldehyde']:
        #     sent_to_screen.upload(screen_uart, formaldehyde_display, control_name="t9", property_name="txt")
        #     self.screen_data_cache['formaldehyde'] = formaldehyde_display
        
        # PM10浓度显示（控件t10）
        # pm10_display = f"{sensor_data['pm10']} μg/m³"
        # if force_update or pm10_display != self.screen_data_cache['pm10']:
        #     sent_to_screen.upload(screen_uart, pm10_display, control_name="t10", property_name="txt")
        #     self.screen_data_cache['pm10'] = pm10_display
        
        # 温度显示（控件t11）
        # temp_display = f"{sensor_data['temperature']} ℃"
        # if force_update or temp_display != self.screen_data_cache['temperature']:
        #     sent_to_screen.upload(screen_uart, temp_display, control_name="t11", property_name="txt")
        #     self.screen_data_cache['temperature'] = temp_display
        
        # 湿度显示（控件t12）
        # humidity_display = f"{sensor_data['humidity']} %RH"
        # if force_update or humidity_display != self.screen_data_cache['humidity']:
        #     sent_to_screen.upload(screen_uart, humidity_display, control_name="t12", property_name="txt")
        #     self.screen_data_cache['humidity'] = humidity_display

    def get_system_status(self):
        """
        获取系统状态信息
        用于监控和调试多传感器系统
        """
        return {
            'data_reader_ready': self.data_reader is not None,
            'data_sender_ready': self.data_sender is not None,
            'last_read_time': self.last_read_time,
            'verbose_mode': self.verbose,
            'cache_size': len(self.screen_data_cache)
        }


# =============================================================================
# 独立运行模式 - 多传感器系统的专用测试环境
# 当直接运行这个文件时，会进入测试模式，方便单独测试传感器功能
# =============================================================================
if __name__ == "__main__":
    """
    多传感器系统独立测试模式
    无需启动整个智能时钟系统，单独测试环境监测功能
    """
    print("\n" + "="*60)
    print("  多传感器环境监测系统 - 独立测试模式")
    print("="*60)
    
    def run_sensor_system_test():
        """运行多传感器系统的基本功能测试"""
        print("\n🧪 开始多传感器系统功能测试...")
        
        # 创建模拟UART管理器用于测试
        class MockUARTManager:
            """模拟UART管理器 - 用于测试通信功能"""
            def __init__(self):
                self.reader = None
                self.sender = None
        
        # 创建模拟屏幕UART用于测试
        class MockScreenUART:
            """模拟屏幕UART - 用于测试数据显示"""
            def write(self, data):
                if SENSOR_DEBUG:
                    print(f"[模拟屏幕] 接收数据: {data[:30]}...")
        
        print("1. 测试多传感器系统初始化...")
        mock_uart_manager = MockUARTManager()
        sensor_system = MultiSensor(uart_manager=mock_uart_manager, verbose=True)
        
        print("2. 测试系统状态查询...")
        status = sensor_system.get_system_status()
        print(f"   系统状态: {status}")
        
        print("3. 测试屏幕通信模拟...")
        mock_screen = MockScreenUART()
        
        print("4. 测试数据读取流程（模拟环境）...")
        # 注意：由于没有真实的传感器硬件，实际数据读取会失败
        # 但这可以测试系统的错误处理能力
        try:
            result = sensor_system.read_sensor_data(mock_screen, force_refresh=True)
            print(f"   数据读取结果: {'成功' if result else '失败（预期中）'}")
        except Exception as e:
            print(f"   数据读取异常: {e}")
        
        print("\n🎉 多传感器系统基本功能测试完成")
        return True
    
    try:
        # 运行测试
        success = run_sensor_system_test()
        
        if success:
            print("\n✅ 多传感器系统独立测试通过")
        else:
            print("\n❌ 多传感器系统测试失败")
            
    except Exception as e:
        print(f"\n💥 测试过程中发生异常: {e}")
        import sys
        sys.print_exception(e)
    
    print("\n👋 多传感器环境监测系统测试结束")