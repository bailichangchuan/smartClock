"""
环境光检测服务 - 智能时钟的光线感知专家
功能：通过TEMT6000传感器持续监测环境光照，提供智能亮度建议
特点：持续监测、自适应映射、平滑滤波、实时亮度建议
"""

# 导入硬件控制模块 - 与传感器直接对话的接口
import machine
import utime
import _thread

# 导入系统配置 - 使用面向用户的友好配置项
from config import (
    # 环境光检测配置
    LIGHT_SENSOR_PIN, LIGHT_CHECK_INTERVAL, 
    LIGHT_SENSOR_DEBUG, GLOBAL_DEBUG,
    # 亮度映射配置
    MIN_BRIGHTNESS, MAX_BRIGHTNESS,
    BRIGHTNESS_SMOOTHING
)


class AmbientLightService:
    """
    环境光检测服务 - 智能时钟的光线感知中枢
    作为定时器控制子系统的持续性服务，专门负责环境光监测和亮度建议
    就像一位敏锐的灯光师，根据环境光线自动调整合适的屏幕亮度
    """
    
    def __init__(self, verbose=None):
        """
        初始化环境光检测持续性服务
        
        参数说明：
        - verbose: 详细日志开关（如果为None，使用配置中的LIGHT_SENSOR_DEBUG）
        """
        # 设置调试模式：优先使用参数，其次使用配置开关
        self.verbose = verbose if verbose is not None else LIGHT_SENSOR_DEBUG
        
        # 传感器硬件状态
        self.adc_sensor = None           # ADC传感器实例
        self.adc_calibration = {         # ADC校准参数
            'min_value': 30,             # 最暗环境下的ADC读数
            'max_value': 150             # 最亮环境下的ADC读数
        }
        
        # 系统运行状态
        self.is_service_active = False   # 服务运行状态
        self.current_adc_reading = 0     # 当前ADC原始读数
        self.filtered_adc_value = 0      # 滤波后的ADC值
        self.suggested_brightness = 0    # 建议的屏幕亮度
        
        # 统计数据
        self.reading_count = 0           # 读数计数
        self.last_status_time = 0        # 上次状态输出时间
        
        if self.verbose:
            print("[环境光检测] 环境光检测持续性服务初始化完成")

    def initialize_hardware(self):
        """
        初始化环境光传感器硬件
        建立与TEMT6000传感器的稳定连接，准备开始持续监测
        """
        try:
            # 配置ADC引脚，设置合适的衰减和宽度
            self.adc_sensor = machine.ADC(machine.Pin(LIGHT_SENSOR_PIN))
            self.adc_sensor.atten(machine.ADC.ATTN_11DB)  # 0-3.3V量程
            self.adc_sensor.width(machine.ADC.WIDTH_12BIT)  # 12位精度
            
            print(f"✅ 环境光传感器就绪 (ADC引脚: GPIO{LIGHT_SENSOR_PIN})")
            return True
            
        except Exception as e:
            print(f"❌ 环境光传感器初始化失败: {e}")
            return False

    def read_ambient_light(self):
        """
        读取环境光强度
        获取ADC传感器的原始读数，反映当前环境光照强度
        """
        if self.adc_sensor is None:
            return 0
        
        try:
            # 读取ADC原始值（0-4095）
            raw_value = self.adc_sensor.read()
            return raw_value
        except Exception as e:
            if self.verbose:
                print(f"[环境光检测] 传感器读取异常: {e}")
            return 0

    def apply_smoothing_filter(self, new_value):
        """
        应用平滑滤波算法
        减少传感器读数的跳动，提供更稳定的亮度建议
        """
        # 首次读取时直接使用新值
        if self.filtered_adc_value == 0:
            return new_value
        
        # 应用指数平滑滤波
        smoothed_value = (new_value * BRIGHTNESS_SMOOTHING + 
                         self.filtered_adc_value * (1 - BRIGHTNESS_SMOOTHING))
        
        return int(smoothed_value)

    def calculate_brightness_suggestion(self, adc_value):
        """
        计算屏幕亮度建议
        将ADC读数映射到合适的屏幕亮度范围
        """
        # 限制ADC值在校准范围内
        clamped_adc = max(self.adc_calibration['min_value'], 
                         min(adc_value, self.adc_calibration['max_value']))
        
        # 计算归一化值（0.0 - 1.0）
        adc_range = self.adc_calibration['max_value'] - self.adc_calibration['min_value']
        if adc_range <= 0:
            normalized = 0.5  # 防止除零错误
        else:
            normalized = (clamped_adc - self.adc_calibration['min_value']) / adc_range
        
        # 确保在有效范围内
        normalized = max(0.0, min(1.0, normalized))
        
        # 线性映射到亮度范围
        brightness_range = MAX_BRIGHTNESS - MIN_BRIGHTNESS
        suggested = MIN_BRIGHTNESS + (normalized * brightness_range)
        
        return int(suggested)

    def perform_sensor_calibration(self):
        """
        执行传感器自动校准
        在服务启动时自动校准ADC范围，适应不同的光照环境
        """
        if self.verbose:
            print("[环境光检测] 开始传感器自动校准...")
        
        # 读取多次样本进行校准
        sample_count = 10
        samples = []
        
        for i in range(sample_count):
            raw_value = self.read_ambient_light()
            samples.append(raw_value)
            utime.sleep(0.1)  # 短暂延迟
        
        # 计算校准参数
        min_sample = min(samples)
        max_sample = max(samples)
        
        # 设置合理的校准范围（留有一定余量）
        self.adc_calibration['min_value'] = max(10, min_sample - 5)
        self.adc_calibration['max_value'] = min(2000, max_sample + 50)
        
        if self.verbose:
            print(f"[环境光检测] 传感器校准完成: ADC范围 {self.adc_calibration['min_value']}-{self.adc_calibration['max_value']}")

    def update_brightness_suggestion(self):
        """
        更新亮度建议
        执行完整的读取-滤波-计算流程，生成新的亮度建议
        """
        # 读取原始环境光强度
        raw_adc = self.read_ambient_light()
        
        # 应用平滑滤波
        self.filtered_adc_value = self.apply_smoothing_filter(raw_adc)
        
        # 计算新的亮度建议
        new_suggestion = self.calculate_brightness_suggestion(self.filtered_adc_value)
        
        # 检查亮度建议是否发生变化
        if new_suggestion != self.suggested_brightness:
            old_brightness = self.suggested_brightness
            self.suggested_brightness = new_suggestion
            
            if self.verbose:
                print(f"[环境光检测] 亮度建议更新: {old_brightness}% → {self.suggested_brightness}%")
            
            return True  # 亮度建议发生变化
        
        return False  # 亮度建议未变化

    def output_status_info(self):
        """
        输出状态信息
        定期在调试模式下输出传感器状态和亮度建议
        """
        current_time = utime.time()
        if current_time - self.last_status_time >= 30:  # 每30秒输出一次
            normalized = (self.filtered_adc_value - self.adc_calibration['min_value']) / \
                        (self.adc_calibration['max_value'] - self.adc_calibration['min_value'])
            
            print(f"[环境光检测] 状态: ADC={self.filtered_adc_value}, "
                  f"归一化={normalized:.2f}, 建议亮度={self.suggested_brightness}%")
            
            self.last_status_time = current_time

    def run_detection_cycle(self):
        """
        执行单次检测循环
        包含完整的环境光读取、滤波、计算和状态输出
        """
        # 更新读数计数
        self.reading_count += 1
        
        # 更新亮度建议
        brightness_changed = self.update_brightness_suggestion()
        
        # 定期输出状态信息
        if self.verbose and self.reading_count % 10 == 0:
            self.output_status_info()
        
        return brightness_changed

    def start_continuous_service(self):
        """
        启动环境光检测持续性服务
        作为定时器控制子系统的持续性服务持续运行
        """
        # 初始化传感器硬件
        if not self.initialize_hardware():
            print("❌ 环境光检测服务启动失败：传感器初始化失败")
            return
        
        print(f"💡 启动环境光检测持续性服务 (检测间隔: {LIGHT_CHECK_INTERVAL}秒)")
        
        # 执行传感器自动校准
        self.perform_sensor_calibration()
        
        # 初始亮度建议计算
        initial_adc = self.read_ambient_light()
        self.filtered_adc_value = initial_adc
        self.suggested_brightness = self.calculate_brightness_suggestion(initial_adc)
        
        print(f"✅ 环境光检测服务就绪 (初始建议亮度: {self.suggested_brightness}%)")
        
        # 标记服务为活跃状态
        self.is_service_active = True
        
        # 持续性服务主循环
        while self.is_service_active:
            # 执行单次检测循环
            self.run_detection_cycle()
            
            # 服务循环间隔
            utime.sleep(LIGHT_CHECK_INTERVAL)

    def stop_service(self):
        """
        停止环境光检测服务
        安全地关闭持续性服务
        """
        self.is_service_active = False
        if self.verbose:
            print("[环境光检测] 环境光检测持续性服务已停止")

    def get_suggested_brightness(self):
        """
        获取当前建议亮度
        供其他模块（如人体检测系统）调用的接口
        """
        return self.suggested_brightness

    def get_service_status(self):
        """
        获取服务状态信息
        用于监控和调试环境光检测系统
        """
        return {
            'sensor_ready': self.adc_sensor is not None,
            'service_active': self.is_service_active,
            'current_adc': self.filtered_adc_value,
            'suggested_brightness': self.suggested_brightness,
            'calibration_min': self.adc_calibration['min_value'],
            'calibration_max': self.adc_calibration['max_value'],
            'reading_count': self.reading_count,
            'verbose_mode': self.verbose
        }


# 创建全局环境光检测服务实例（兼容旧代码）
_ambient_light_service = AmbientLightService()

# 兼容旧代码的全局函数
def start_temt6000_detect(verbose=False):
    """
    启动TEMT6000环境光检测持续性服务（兼容旧代码接口）
    作为定时器控制子系统的持续性服务运行在核心1
    
    参数说明：
    - verbose: 详细日志开关
    """
    service = AmbientLightService(verbose=verbose)
    _thread.start_new_thread(service.start_continuous_service, ())

def get_suggested_brightness():
    """获取当前建议亮度（兼容旧代码接口）"""
    return _ambient_light_service.get_suggested_brightness()

def get_current_status():
    """获取当前状态（兼容旧代码接口）"""
    status = _ambient_light_service.get_service_status()
    return {
        'adc_value': status['current_adc'],
        'suggested_brightness': status['suggested_brightness']
    }


# =============================================================================
# 独立运行模式 - 环境光检测系统的专用测试环境
# 当直接运行这个文件时，会进入测试模式，方便单独测试环境光检测功能
# =============================================================================
if __name__ == "__main__":
    """
    环境光检测系统独立测试模式
    无需启动整个智能时钟系统，单独测试环境光检测功能
    """
    print("\n" + "="*60)
    print("  环境光检测系统 - 独立测试模式")
    print("="*60)
    
    def run_ambient_light_test():
        """运行环境光检测系统的基本功能测试"""
        print("\n🧪 开始环境光检测系统功能测试...")
        
        # 创建测试用的环境光检测系统实例
        light_service = AmbientLightService(verbose=True)
        
        print("1. 测试传感器硬件初始化...")
        hardware_ready = light_service.initialize_hardware()
        print(f"   硬件状态: {'就绪' if hardware_ready else '未就绪'}")
        
        print("2. 测试传感器自动校准...")
        light_service.perform_sensor_calibration()
        calibration = light_service.adc_calibration
        print(f"   校准参数: ADC范围 {calibration['min_value']}-{calibration['max_value']}")
        
        print("3. 测试亮度建议计算...")
        test_adc_values = [50, 100, 500, 1000, 2000]
        for adc_value in test_adc_values:
            brightness = light_service.calculate_brightness_suggestion(adc_value)
            print(f"   ADC {adc_value} → 亮度 {brightness}%")
        
        print("4. 测试平滑滤波算法...")
        test_values = [100, 150, 130, 140, 135]
        filtered_result = 100  # 初始值
        for value in test_values:
            filtered_result = light_service.apply_smoothing_filter(value)
            print(f"   原始值: {value}, 滤波后: {filtered_result}")
        
        print("5. 测试系统状态查询...")
        status = light_service.get_service_status()
        print(f"   系统状态: {status}")
        
        print("\n🎉 环境光检测系统基本功能测试完成")
        return True
    
    try:
        # 运行测试
        success = run_ambient_light_test()
        
        if success:
            print("\n✅ 环境光检测系统独立测试通过")
        else:
            print("\n❌ 环境光检测系统测试失败")
            
    except Exception as e:
        print(f"\n💥 测试过程中发生异常: {e}")
        import sys
        sys.print_exception(e)
    
    print("\n👋 环境光检测系统测试结束")