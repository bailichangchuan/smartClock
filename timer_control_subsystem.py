"""
定时器控制子系统 - 智能时钟的后台任务协调中心
功能：管理所有定时任务、传感器监控、智能调节功能
特点：运行在核心1，持续性功能通过独立线程运行，定时任务通过临时线程执行
"""

# 导入系统核心模块
from utime import time, sleep, ticks_ms, ticks_diff
import machine
import _thread

# 导入系统配置 - 使用面向用户的友好配置项
from config import (
    # 时间间隔配置
    WEATHER_UPDATE_INTERVAL, NTP_SYNC_INTERVAL, TIME_PRINT_INTERVAL, 
    SENSOR_READ_INTERVAL, SYSTEM_CHECK_INTERVAL,
    
    # 调试开关
    WEATHER_DEBUG, NTP_DEBUG, SENSOR_DEBUG, SYSTEM_DEBUG, GLOBAL_DEBUG,
    MOTION_DEBUG, LIGHT_SENSOR_DEBUG, PLAYER_DEBUG,
    
    # 系统配置
    DEVICE_NAME
)

# 导入功能模块 - 系统的各种智能能力
import function.weather as weather_module
import function.ntp_clock as ntp_module
import function.multi_sensor as sensor_module
import function.sr602 as sr602_module
import function.temt6000 as temt6000_module
import function.dfplayer as dfplayer_module


def bind_thread_to_core(core_id, thread_name=""):
    """
    将当前线程绑定到指定CPU核心
    确保线程在正确的核心上运行
    """
    try:
        _thread.set_core(_thread.get_ident(), core_id)
        if SYSTEM_DEBUG:
            print(f"[核心绑定] {thread_name} 绑定到核心{core_id}")
        return True
    except Exception as e:
        print(f"[核心绑定] 警告: {thread_name} 绑定失败: {e}")
        return False


class TimerSubsystem:
    """
    定时器子系统管理器 - 后台任务的智能协调中心
    负责协调时间同步、天气更新、传感器监控等所有周期性任务
    持续性功能通过独立线程运行，定时任务通过临时线程执行
    """
    
    def __init__(self):
        # 任务执行时间记录 - 记住每个任务上次执行的时间
        self.last_execution = {
            'ntp_sync': 0,           # NTP时间同步
            'weather_update': 0,      # 天气信息更新
            'sensor_read': 0,         # 传感器数据读取
            'time_display': 0,        # 时间显示更新
            'system_check': 0         # 系统状态检查
        }
        
        # 子系统运行状态
        self.is_running = True
        self.active_temp_threads = []  # 活跃临时线程跟踪
        self.continuous_services = {   # 持续性服务状态
            'motion_detection': False,
            'light_sensing': False,
            'player_monitoring': False
        }
        
        if SYSTEM_DEBUG:
            print("[定时器子系统] 初始化完成，准备协调后台任务")

    def should_execute(self, task_name, interval):
        """
        判断指定任务是否应该执行
        基于时间间隔的智能决策，避免任务过于频繁执行
        """
        current_time = time()
        time_since_last = current_time - self.last_execution[task_name]
        
        if time_since_last >= interval:
            self.last_execution[task_name] = current_time
            if SYSTEM_DEBUG:
                print(f"[任务协调] {task_name} 满足执行条件 (间隔: {interval}秒)")
            return True
        
        return False

    def start_temp_thread(self, target_function, args=(), thread_name="临时线程"):
        """
        启动临时独立线程执行指定功能
        临时线程运行在核心1，执行完毕后自动关闭
        """
        try:
            thread_id = _thread.start_new_thread(target_function, args)
            self.active_temp_threads.append(thread_id)
            
            if SYSTEM_DEBUG:
                print(f"[线程管理] 启动{thread_name}，ID: {thread_id}")
            
            return thread_id
        except Exception as e:
            print(f"[线程管理] {thread_name}启动失败: {e}")
            return None

    def start_continuous_service(self, target_function, args=(), service_name="持续性服务"):
        """
        启动持续性服务线程
        这些线程会持续运行，不会自动关闭
        """
        try:
            thread_id = _thread.start_new_thread(target_function, args)
            
            if SYSTEM_DEBUG:
                print(f"[服务管理] 启动{service_name}，ID: {thread_id}")
            
            return thread_id
        except Exception as e:
            print(f"[服务管理] {service_name}启动失败: {e}")
            return None

    def execute_time_sync(self, screen_uart):
        """
        执行网络时间同步任务（通过临时线程）
        确保智能时钟始终显示准确的时间
        """
        if not self.should_execute('ntp_sync', NTP_SYNC_INTERVAL * 3600):
            return
            
        def sync_time_task():
            # 临时线程也绑定到核心1
            bind_thread_to_core(1, "时间同步任务")
            
            if NTP_DEBUG:
                print("[时间同步] 开始NTP网络时间校准...")
            
            print("⏰ 同步网络时间...")
            success, timezone = ntp_module.sync_ntp_to_rtc()
            
            if success:
                print(f"✅ 时间同步完成 (时区 UTC+{timezone:.1f})")
                # 强制更新时间显示
                ntp_module.send_time_to_serial_screen(screen_uart, force=True)
            else:
                print("❌ 时间同步失败，将稍后重试")
        
        self.start_temp_thread(sync_time_task, (), "时间同步任务")

    def execute_weather_update(self, screen_uart):
        """
        执行天气信息更新任务（通过临时线程）
        从云端获取最新天气数据，让用户了解室外环境
        """
        if not self.should_execute('weather_update', WEATHER_UPDATE_INTERVAL):
            return
            
        def weather_update_task():
            # 临时线程也绑定到核心1
            bind_thread_to_core(1, "天气更新任务")
            
            if WEATHER_DEBUG:
                print("[天气更新] 开始获取最新天气信息...")
            
            print("🌤️  更新天气信息...")
            try:
                weather_module.get_weather_by_ip(screen_uart)
                if WEATHER_DEBUG:
                    print("[天气更新] 天气信息更新完成")
            except Exception as e:
                print(f"❌ 天气更新失败: {e}")
        
        self.start_temp_thread(weather_update_task, (), "天气更新任务")

    def execute_sensor_reading(self, sensor_manager, screen_uart):
        """
        执行传感器数据读取任务（通过临时线程）
        收集环境温度、湿度等数据，了解室内环境状况
        """
        if not self.should_execute('sensor_read', SENSOR_READ_INTERVAL):
            return
            
        def sensor_reading_task():
            # 临时线程也绑定到核心1
            bind_thread_to_core(1, "传感器读取任务")
            
            if SENSOR_DEBUG:
                print("[传感器读取] 开始读取环境传感器数据...")
            
            if sensor_manager and screen_uart:
                try:
                    sensor_manager.read_sensor_data(screen_uart)
                    if SENSOR_DEBUG:
                        print("[传感器读取] 传感器数据读取完成")
                except Exception as e:
                    print(f"❌ 传感器读取失败: {e}")
            else:
                if SENSOR_DEBUG:
                    print("[传感器读取] 传感器管理器不可用，跳过读取")
        
        self.start_temp_thread(sensor_reading_task, (), "传感器读取任务")

    def execute_time_display(self, screen_uart):
        """
        执行时间显示更新任务（通过临时线程）
        在控制台显示当前时间，并更新串口屏的时间显示
        """
        if not self.should_execute('time_display', TIME_PRINT_INTERVAL):
            return
            
        def time_display_task():
            # 临时线程也绑定到核心1
            bind_thread_to_core(1, "时间显示任务")
            
            if SYSTEM_DEBUG:
                print("[时间显示] 更新时间和屏幕显示...")
            
            try:
                # 获取格式化的当前时间
                current_time = ntp_module.get_current_formatted_time()
                print(f"🕒 当前时间: {current_time}")
                
                # 发送时间到串口屏
                ntp_module.send_time_to_serial_screen(screen_uart)
            except Exception as e:
                print(f"❌ 时间显示更新失败: {e}")
        
        self.start_temp_thread(time_display_task, (), "时间显示任务")

    def execute_system_health_check(self):
        """
        执行系统健康检查任务（通过临时线程）
        监控系统运行状态，确保所有组件正常工作
        """
        if not self.should_execute('system_check', SYSTEM_CHECK_INTERVAL):
            return
            
        def health_check_task():
            # 临时线程也绑定到核心1
            bind_thread_to_core(1, "系统检查任务")
            
            if SYSTEM_DEBUG:
                print("[系统检查] 执行系统健康检查...")
            
            # 检查活跃线程数量
            active_count = len(self.active_temp_threads)
            if active_count > 5:  # 如果活跃线程过多，清理一些
                self.cleanup_temp_threads()
            
            print(f"🔍 系统运行状态正常 (活跃临时线程: {active_count})")
        
        self.start_temp_thread(health_check_task, (), "系统检查任务")

    def start_continuous_services(self, screen_uart, sensor_uart, music_player):
        """
        启动持续性智能服务
        这些服务在独立的线程中持续运行，不会自动关闭
        """
        if SYSTEM_DEBUG:
            print("[持续性服务] 启动后台智能服务...")
        
        # 启动人体检测服务（持续性）
        def motion_detection_service():
            try:
                # 持续性服务线程绑定到核心1
                bind_thread_to_core(1, "人体检测服务")
                
                self.continuous_services['motion_detection'] = True
                print("🔍 启动人体检测服务...")
                
                sr602_module.start_sr602_detect(
                    uart_instance=screen_uart,
                    verbose=MOTION_DEBUG
                )
            except Exception as e:
                print(f"❌ 人体检测服务异常: {e}")
                self.continuous_services['motion_detection'] = False
        
        # 启动环境光检测服务（持续性）
        def light_sensing_service():
            try:
                # 持续性服务线程绑定到核心1
                bind_thread_to_core(1, "环境光检测服务")
                
                self.continuous_services['light_sensing'] = True
                print("💡 启动环境光检测服务...")
                
                temt6000_module.start_temt6000_detect(
                    verbose=LIGHT_SENSOR_DEBUG
                )
            except Exception as e:
                print(f"❌ 环境光检测服务异常: {e}")
                self.continuous_services['light_sensing'] = False
        
        # 启动音乐播放器监控服务（持续性）
        def player_monitoring_service():
            try:
                # 持续性服务线程绑定到核心1
                bind_thread_to_core(1, "播放器监控服务")
                
                self.continuous_services['player_monitoring'] = True
                
                if music_player and PLAYER_DEBUG:
                    print("🎵 启动播放器监控服务...")
                    # 这里可以添加播放器状态监控逻辑
                    while self.is_running and self.continuous_services['player_monitoring']:
                        # 播放器状态监控循环
                        sleep(5)  # 每5秒检查一次
            except Exception as e:
                print(f"❌ 播放器监控服务异常: {e}")
                self.continuous_services['player_monitoring'] = False
        
        # 启动所有持续性服务
        self.start_continuous_service(motion_detection_service, (), "人体检测服务")
        self.start_continuous_service(light_sensing_service, (), "环境光检测服务")
        self.start_continuous_service(player_monitoring_service, (), "播放器监控服务")
        
        print("✅ 持续性智能服务已启动")

    def run_all_scheduled_tasks(self, screen_uart, sensor_manager, sensor_uart, music_player):
        """
        执行所有已调度的任务
        每个任务都在独立的临时线程中执行，确保非阻塞
        """
        # 时间同步任务（每小时或按配置）
        self.execute_time_sync(screen_uart)
        
        # 天气更新任务
        self.execute_weather_update(screen_uart)
        
        # 传感器数据读取
        self.execute_sensor_reading(sensor_manager, screen_uart)
        
        # 时间显示更新
        self.execute_time_display(screen_uart)
        
        # 系统健康检查
        self.execute_system_health_check()

    def cleanup_temp_threads(self):
        """
        定期清理临时线程记录
        由于MicroPython无法直接管理线程状态，我们只清理记录列表
        """
        # 简化清理：定期重置活跃线程列表
        # 在实际运行中，线程执行完毕会自动结束
        if len(self.active_temp_threads) > 10:
            if SYSTEM_DEBUG:
                print(f"[线程清理] 清理线程记录，之前数量: {len(self.active_temp_threads)}")
            self.active_temp_threads = []
            if SYSTEM_DEBUG:
                print("[线程清理] 线程记录已重置")

    def stop_all_services(self):
        """
        停止所有服务
        安全地关闭所有持续性和临时性服务
        """
        self.is_running = False
        self.continuous_services = {
            'motion_detection': False,
            'light_sensing': False,
            'player_monitoring': False
        }
        
        if SYSTEM_DEBUG:
            print("[定时器子系统] 所有服务已停止")


def run_timer_control_subsystem(screen_uart, sensor_manager, sensor_uart_manager, music_player):
    """
    启动定时器控制子系统 - 后台任务的指挥中心
    负责管理所有周期性任务和持续性智能功能
    
    参数说明：
    - screen_uart: 屏幕通信实例（用于显示更新）
    - sensor_manager: 传感器管理器实例
    - sensor_uart_manager: 传感器通信管理器
    - music_player: 音乐播放器实例
    """
    # 确保当前线程绑定到核心1
    bind_thread_to_core(1, "定时器控制子系统")
    
    if SYSTEM_DEBUG:
        print("[定时器子系统] 启动定时器控制子系统...")
    
    print("\n" + "="*50)
    print("  定时器控制子系统启动 (核心1)")
    print("="*50)
    print(f"  📅 定时任务配置:")
    print(f"     • 天气更新: 每 {WEATHER_UPDATE_INTERVAL} 秒")
    print(f"     • 时间同步: 每 {NTP_SYNC_INTERVAL} 小时") 
    print(f"     • 传感器读取: 每 {SENSOR_READ_INTERVAL} 秒")
    print(f"     • 时间显示: 每 {TIME_PRINT_INTERVAL} 秒")
    print(f"     • 系统检查: 每 {SYSTEM_CHECK_INTERVAL} 秒")
    print(f"  🔄 持续性服务:")
    print(f"     • 人体检测: 持续运行")
    print(f"     • 环境光检测: 持续运行")
    print(f"     • 播放器监控: 持续运行")
    print("="*50)
    
    # 创建定时器子系统管理器
    timer_system = TimerSubsystem()
    
    # 启动持续性智能服务（人体检测、环境光检测等）
    print("\n🚀 启动持续性智能服务...")
    timer_system.start_continuous_services(
        screen_uart=screen_uart,
        sensor_uart=sensor_uart_manager,
        music_player=music_player
    )
    
    print("✅ 定时器控制子系统就绪，开始任务调度")
    
    # 主循环 - 定时器子系统的核心工作状态
    cycle_count = 0
    try:
        while timer_system.is_running:
            # 执行所有已调度的任务
            timer_system.run_all_scheduled_tasks(
                screen_uart=screen_uart,
                sensor_manager=sensor_manager,
                sensor_uart=sensor_uart_manager,
                music_player=music_player
            )
            
            # 定期清理临时线程记录
            cycle_count += 1
            if cycle_count % 100 == 0:  # 每100个循环清理一次
                timer_system.cleanup_temp_threads()
            
            # 短暂休息，平衡任务执行和CPU占用
            sleep(0.1)  # 100毫秒的休息时间
            
    except KeyboardInterrupt:
        print("\n⚠️ 定时器控制子系统被用户中断")
    except Exception as e:
        print(f"❌ 定时器控制子系统异常: {e}")
        if GLOBAL_DEBUG:
            import sys
            sys.print_exception(e)
    finally:
        timer_system.stop_all_services()
        print("🛑 定时器控制子系统已停止")


# =============================================================================
# 独立运行模式 - 定时器子系统的专用测试环境
# 当直接运行这个文件时，会进入测试模式，方便单独测试定时任务
# =============================================================================
if __name__ == "__main__":
    """
    定时器控制子系统独立测试模式
    无需启动整个智能时钟系统，单独测试定时任务功能
    """
    print("\n" + "="*60)
    print("  定时器控制子系统 - 独立测试模式")
    print("="*60)
    
    # 创建模拟组件用于测试
    class MockScreenUART:
        """模拟屏幕UART - 用于测试通信"""
        def write(self, data):
            if SYSTEM_DEBUG:
                print(f"[模拟UART] 发送数据: {data[:20]}...")
    
    class MockSensorManager:
        """模拟传感器管理器 - 用于测试传感器读取"""
        def read_sensor_data(self, uart):
            if SENSOR_DEBUG:
                print("[模拟传感器] 读取传感器数据")
            return True
    
    class MockMusicPlayer:
        """模拟音乐播放器 - 用于测试播放器功能"""
        def __init__(self):
            self.is_playing = True
    
    print("🧪 进入测试模式，使用模拟硬件组件...")
    
    # 创建模拟实例
    test_screen_uart = MockScreenUART()
    test_sensor_manager = MockSensorManager() 
    test_music_player = MockMusicPlayer()
    
    # 模拟传感器UART管理器
    test_sensor_uart = {
        'reader': None,
        'sender': None,
        'hardware': None
    }
    
    try:
        # 启动定时器控制子系统（测试版本）
        run_timer_control_subsystem(
            screen_uart=test_screen_uart,
            sensor_manager=test_sensor_manager,
            sensor_uart_manager=test_sensor_uart,
            music_player=test_music_player
        )
    except KeyboardInterrupt:
        print("\n✅ 定时器子系统测试完成（用户主动结束）")
    except Exception as e:
        print(f"\n❌ 定时器子系统测试异常: {e}")
    
    print("👋 定时器控制子系统测试结束")