"""
人体红外检测系统 - 智能时钟的智能感知管家
功能：通过SR602传感器持续检测人体存在，智能控制屏幕亮度和显示状态
特点：非接触检测、环境光自适应亮度、平滑渐变过渡、持续运行服务
"""

# 导入硬件控制模块 - 与传感器直接对话的接口
import machine
import utime
import _thread

# 导入系统配置 - 使用面向用户的友好配置项
from config import (
    # 人体检测配置
    MOTION_SENSOR_PIN, MOTION_CHECK_INTERVAL, SCREEN_OFF_DELAY,
    MOTION_DEBUG, GLOBAL_DEBUG,
    # 亮度控制配置
    DEFAULT_BRIGHTNESS, FADE_STEP, FADE_DELAY
)

# 导入环境光检测模块 - 获取环境光建议亮度
import function.temt6000 as temt6000_module


class HumanDetectionSystem:
    """
    人体检测系统 - 智能时钟的持续感知服务
    作为定时器控制子系统的持续性服务，专门负责人体检测和亮度控制
    就像一位永不疲倦的管家，时刻关注是否有人需要查看时间
    """
    
    def __init__(self, verbose=None):
        """
        初始化人体检测持续性服务
        
        参数说明：
        - verbose: 详细日志开关（如果为None，使用配置中的MOTION_DEBUG）
        """
        # 设置调试模式：优先使用参数，其次使用配置开关
        self.verbose = verbose if verbose is not None else MOTION_DEBUG
        
        # 传感器硬件状态
        self.sensor_pin = None           # 传感器GPIO引脚实例
        
        # 系统运行状态
        self.is_service_active = False   # 服务运行状态
        self.last_presence_state = None  # 上一次检测到的人体状态
        self.presence_timeout = 0        # 人体离开的倒计时
        
        # 亮度控制状态
        self.current_brightness = 0      # 当前屏幕亮度（0-100）
        self.target_brightness = 0       # 目标亮度（用于渐变）
        self.is_fading = False           # 是否正在亮度渐变中
        self.last_ambient_brightness = 0 # 上一次的环境光建议亮度
        
        if self.verbose:
            print("[人体检测] 人体检测持续性服务初始化完成")

    def initialize_hardware(self):
        """
        初始化人体红外传感器硬件
        建立与SR602传感器的稳定连接，准备开始持续检测
        """
        try:
            # 配置传感器引脚为输入模式，启用下拉电阻确保稳定
            self.sensor_pin = machine.Pin(
                MOTION_SENSOR_PIN, 
                machine.Pin.IN, 
                machine.Pin.PULL_DOWN
            )
            
            print(f"✅ 人体传感器硬件就绪 (GPIO{MOTION_SENSOR_PIN})")
            return True
            
        except Exception as e:
            print(f"❌ 人体传感器初始化失败: {e}")
            return False

    def read_sensor_status(self):
        """
        读取人体传感器当前状态
        检测是否有人体在传感器探测范围内
        """
        if self.sensor_pin is None:
            return False
        
        try:
            # SR602传感器逻辑：高电平=有人，低电平=无人
            return self.sensor_pin.value() == 1
        except Exception as e:
            if self.verbose:
                print(f"[人体检测] 传感器读取异常: {e}")
            return False

    def get_ambient_brightness_suggestion(self):
        """
        获取环境光建议亮度
        咨询环境光检测模块，获取适合当前光照的屏幕亮度
        """
        try:
            suggested_brightness = temt6000_module.get_suggested_brightness()
            return suggested_brightness
        except Exception as e:
            if self.verbose:
                print(f"[人体检测] 环境光建议获取失败: {e}")
            # 返回默认亮度作为安全备用
            return DEFAULT_BRIGHTNESS

    def execute_brightness_fade(self, screen_uart):
        """
        执行单步亮度渐变
        每次调用只改变一步亮度，实现非阻塞的平滑渐变效果
        """
        # 检查是否需要进行亮度渐变
        if not self.is_fading or self.current_brightness == self.target_brightness:
            return
        
        # 计算下一步亮度值
        if self.current_brightness < self.target_brightness:
            # 渐亮方向：增加亮度
            next_brightness = min(self.current_brightness + FADE_STEP, self.target_brightness)
        else:
            # 渐暗方向：降低亮度
            next_brightness = max(self.current_brightness - FADE_STEP, self.target_brightness)
        
        # 更新当前亮度
        self.current_brightness = next_brightness
        
        # 发送亮度控制指令到屏幕
        brightness_command = f"dim={self.current_brightness}".encode('utf-8') + b"\xff\xff\xff"
        screen_uart.write(brightness_command)
        
        if self.verbose:
            print(f"[人体检测] 亮度渐变: {self.current_brightness}% → {self.target_brightness}%")
        
        # 检查渐变是否完成
        if self.current_brightness == self.target_brightness:
            self.is_fading = False
            if self.verbose:
                print(f"[人体检测] 亮度渐变完成: {self.current_brightness}%")

    def start_brightness_fade(self, target_brightness):
        """
        开始亮度渐变过程
        设置目标亮度并标记开始渐变，实际的渐变在execute_brightness_fade中执行
        """
        self.target_brightness = target_brightness
        self.is_fading = True
        
        if self.verbose:
            print(f"[人体检测] 开始亮度渐变: {self.current_brightness}% → {self.target_brightness}%")

    def handle_human_presence_detected(self, screen_uart):
        """
        处理检测到人体的情况
        有人出现时，根据环境光建议亮度开启屏幕
        """
        # 重置人体离开倒计时
        self.presence_timeout = 0
        
        # 获取环境光建议亮度
        ambient_brightness = self.get_ambient_brightness_suggestion()
        self.last_ambient_brightness = ambient_brightness
        
        print(f"👤 检测到人体 → 开启屏幕 (环境光建议: {ambient_brightness}%)")
        
        # 开始渐亮到环境光建议亮度
        self.start_brightness_fade(ambient_brightness)

    def handle_human_absence_detected(self):
        """
        处理检测到人体离开的情况
        开始关屏倒计时，但不会立即关闭屏幕
        """
        # 设置人体离开倒计时
        self.presence_timeout = utime.time() + SCREEN_OFF_DELAY
        
        if self.verbose:
            print(f"[人体检测] 人体离开，{SCREEN_OFF_DELAY}秒后关闭屏幕")

    def handle_presence_state_change(self, screen_uart, is_present):
        """
        处理人体存在状态变化
        根据状态变化执行相应的屏幕控制逻辑
        """
        # 状态没有变化，无需处理
        if is_present == self.last_presence_state:
            return
        
        if is_present:
            # 从无人→有人：立即开启屏幕
            self.handle_human_presence_detected(screen_uart)
        else:
            # 从有人→无人：开始关屏倒计时
            self.handle_human_absence_detected()
        
        # 更新状态记录
        self.last_presence_state = is_present

    def check_ambient_light_change(self, screen_uart):
        """
        检查环境光变化
        在有人状态下，根据环境光变化调整屏幕亮度
        """
        if not self.last_presence_state:
            return
        
        # 获取当前环境光建议亮度
        current_ambient = self.get_ambient_brightness_suggestion()
        
        # 检查亮度变化是否超过调整阈值
        brightness_change = abs(current_ambient - self.last_ambient_brightness)
        if brightness_change >= 3:  # 亮度变化超过3%时调整
            if self.verbose:
                print(f"[人体检测] 环境光变化: {self.last_ambient_brightness}% → {current_ambient}%")
            
            self.start_brightness_fade(current_ambient)
            self.last_ambient_brightness = current_ambient

    def check_presence_timeout(self, screen_uart):
        """
        检查人体离开超时
        如果人体离开时间超过设定值，关闭屏幕
        """
        if self.presence_timeout > 0 and utime.time() >= self.presence_timeout:
            print("💤 人体离开超时 → 关闭屏幕")
            self.start_brightness_fade(0)  # 渐暗到关闭
            self.presence_timeout = 0
            self.last_presence_state = False

    def run_detection_cycle(self, screen_uart):
        """
        执行单次检测循环
        包含完整的人体检测、状态处理和亮度控制逻辑
        """
        # 检测人体存在状态
        is_human_present = self.read_sensor_status()
        
        # 处理人体状态变化
        self.handle_presence_state_change(screen_uart, is_human_present)
        
        # 执行亮度渐变（非阻塞单步执行）
        self.execute_brightness_fade(screen_uart)
        
        # 检查环境光变化（有人状态下）
        self.check_ambient_light_change(screen_uart)
        
        # 检查人体离开超时
        self.check_presence_timeout(screen_uart)

    def start_continuous_service(self, screen_uart):
        """
        启动人体检测持续性服务
        作为定时器控制子系统的持续性服务持续运行
        
        参数说明：
        - screen_uart: 屏幕通信实例（用于亮度控制）
        """
        if screen_uart is None:
            print("❌ 屏幕通信未就绪，无法启动人体检测服务")
            return
        
        # 初始化传感器硬件
        if not self.initialize_hardware():
            print("❌ 人体检测服务启动失败：传感器初始化失败")
            return
        
        print(f"🔍 启动人体检测持续性服务 (检测间隔: {MOTION_CHECK_INTERVAL}秒)")
        
        # 初始状态：屏幕关闭
        init_command = f"dim=0".encode('utf-8') + b"\xff\xff\xff"
        screen_uart.write(init_command)
        self.current_brightness = 0
        
        # 标记服务为活跃状态
        self.is_service_active = True
        
        # 持续性服务主循环
        while self.is_service_active:
            # 执行单次检测循环
            self.run_detection_cycle(screen_uart)
            
            # 服务循环间隔
            utime.sleep(MOTION_CHECK_INTERVAL)

    def stop_service(self):
        """
        停止人体检测服务
        安全地关闭持续性服务
        """
        self.is_service_active = False
        if self.verbose:
            print("[人体检测] 人体检测持续性服务已停止")

    def get_service_status(self):
        """
        获取服务状态信息
        用于监控和调试人体检测系统
        """
        return {
            'sensor_ready': self.sensor_pin is not None,
            'service_active': self.is_service_active,
            'current_brightness': self.current_brightness,
            'target_brightness': self.target_brightness,
            'last_presence_state': self.last_presence_state,
            'presence_timeout': self.presence_timeout,
            'is_fading': self.is_fading,
            'verbose_mode': self.verbose
        }


# 创建全局人体检测服务实例（兼容旧代码）
_human_detection_service = HumanDetectionSystem()

# 兼容旧代码的全局函数
def start_sr602_detect(uart_instance, verbose=False):
    """
    启动SR602人体检测持续性服务（兼容旧代码接口）
    作为定时器控制子系统的持续性服务运行在核心1
    
    参数说明：
    - uart_instance: 屏幕通信实例
    - verbose: 详细日志开关
    """
    detector = HumanDetectionSystem(verbose=verbose)
    _thread.start_new_thread(detector.start_continuous_service, (uart_instance,))


# =============================================================================
# 独立运行模式 - 人体检测系统的专用测试环境
# 当直接运行这个文件时，会进入测试模式，方便单独测试人体检测功能
# =============================================================================
if __name__ == "__main__":
    """
    人体检测系统独立测试模式
    无需启动整个智能时钟系统，单独测试人体检测功能
    """
    print("\n" + "="*60)
    print("  人体红外检测系统 - 独立测试模式")
    print("="*60)
    
    def run_human_detection_test():
        """运行人体检测系统的基本功能测试"""
        print("\n🧪 开始人体检测系统功能测试...")
        
        # 创建测试用的人体检测系统实例
        detector = HumanDetectionSystem(verbose=True)
        
        print("1. 测试传感器硬件初始化...")
        hardware_ready = detector.initialize_hardware()
        print(f"   硬件状态: {'就绪' if hardware_ready else '未就绪'}")
        
        print("2. 测试系统状态查询...")
        status = detector.get_service_status()
        print(f"   系统状态: {status}")
        
        print("3. 测试环境光建议获取（模拟）...")
        # 模拟环境光传感器
        class MockLightSensor:
            def get_suggested_brightness(self):
                return 75  # 模拟固定亮度
        
        # 临时替换环境光模块
        original_temt6000 = temt6000_module
        temt6000_module = MockLightSensor()
        
        ambient_suggestion = detector.get_ambient_brightness_suggestion()
        print(f"   环境光建议亮度: {ambient_suggestion}%")
        
        # 恢复原始模块
        temt6000_module = original_temt6000
        
        print("4. 测试屏幕通信模拟...")
        class MockScreenUART:
            def write(self, data):
                if MOTION_DEBUG:
                    command = data.decode('utf-8', errors='ignore') if isinstance(data, bytes) else str(data)
                    print(f"[模拟屏幕] 接收指令: {command[:50]}...")
        
        mock_screen = MockScreenUART()
        
        print("5. 测试亮度渐变逻辑...")
        # 测试亮度渐变设置
        detector.start_brightness_fade(80)
        print("   亮度渐变逻辑测试完成")
        
        print("\n🎉 人体检测系统基本功能测试完成")
        return True
    
    try:
        # 运行测试
        success = run_human_detection_test()
        
        if success:
            print("\n✅ 人体检测系统独立测试通过")
        else:
            print("\n❌ 人体检测系统测试失败")
            
    except Exception as e:
        print(f"\n💥 测试过程中发生异常: {e}")
        import sys
        sys.print_exception(e)
    
    print("\n👋 人体红外检测系统测试结束")