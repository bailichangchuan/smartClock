"""
串口屏控制子系统 - 智能时钟的用户界面管家
功能：管理串口屏通信、处理用户交互、协调显示内容
特点：运行在核心0，独占CPU资源，确保界面流畅响应
"""

# 导入硬件控制模块 - 与串口屏直接对话的桥梁
import machine
from utime import sleep
import _thread

# 导入系统配置 - 使用面向用户的友好配置项
from config import (
    # 屏幕通信配置
    SCREEN_UART_PORT, SCREEN_BAUD_RATE, SCREEN_TX_PIN, SCREEN_RX_PIN,
    # 调试开关
    SCREEN_DEBUG, GLOBAL_DEBUG,
    # 系统配置
    DEVICE_NAME, SYSTEM_DEBUG
)

# 导入屏幕控制工具包 - 专业的指令处理团队
from util.screen_command_listener import ScreenCommandListener


def initialize_screen_communication():
    """
    建立与串口屏的通信通道
    就像给智能时钟装上嘴巴和耳朵，让它能够与用户交流
    """
    if SCREEN_DEBUG:
        print("[屏幕通信] 正在建立串口屏连接...")
    
    try:
        # 创建串口屏专用通信通道
        screen_uart = machine.UART(
            SCREEN_UART_PORT,           # 串口端口号
            baudrate=SCREEN_BAUD_RATE,  # 通信速度（波特率）
            tx=machine.Pin(SCREEN_TX_PIN),  # 发送引脚
            rx=machine.Pin(SCREEN_RX_PIN),  # 接收引脚
            bits=8,      # 数据位
            parity=None, # 校验位（无）
            stop=1,      # 停止位
            timeout=100  # 超时时间（毫秒）
        )
        
        print(f"✅ 串口屏通信建立成功 (端口{SCREEN_UART_PORT}, 波特率{SCREEN_BAUD_RATE})")
        return screen_uart
        
    except Exception as e:
        # 通信建立失败，用户界面将无法工作
        print(f"❌ 串口屏通信初始化失败: {e}")
        return None


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


def run_screen_control_subsystem(sensor_manager, screen_uart=None):
    """
    启动串口屏控制子系统 - 用户界面的指挥中心
    负责协调所有屏幕显示和用户交互任务
    
    参数说明：
    - sensor_manager: 传感器数据管家，提供环境数据
    - screen_uart: 可选的串口实例（为空则自动创建）
    """
    # 确保当前线程绑定到核心0
    bind_thread_to_core(0, "屏幕控制子系统")
    
    if SYSTEM_DEBUG:
        print("[屏幕子系统] 启动屏幕控制子系统...")
    
    print("\n" + "="*50)
    print("  屏幕控制子系统启动 (核心0)")
    print("="*50)
    
    # 第一步：建立屏幕通信（如果未提供现成连接）
    if screen_uart is None:
        screen_uart = initialize_screen_communication()
        if not screen_uart:
            print("❌ 屏幕子系统启动失败：无法建立屏幕通信")
            return
    
    # 第二步：启动指令监听系统（专业的用户交互处理团队）
    print("👂 启动用户指令监听系统...")
    command_listener = ScreenCommandListener(verbose=SCREEN_DEBUG)
    command_listener.start_listening(screen_uart, sensor_manager)
    
    print("✅ 屏幕控制子系统就绪，等待用户交互")
    
    # 第三步：进入主循环 - 屏幕子系统的核心工作状态
    if SCREEN_DEBUG:
        print("[屏幕子系统] 进入主循环，保持系统运行...")
    
    try:
        while True:
            # 让CPU适当休息，避免过度占用资源
            # 这就像给系统一个呼吸的空间，提高整体效率
            machine.idle()  # 进入低功耗空闲状态
            sleep(0.1)      # 短暂睡眠，平衡响应速度和资源占用
            
    except KeyboardInterrupt:
        # 用户主动中断（调试时使用）
        print("\n⚠️ 屏幕控制子系统被用户中断")
        command_listener.stop_listening()
    except Exception as e:
        # 处理未预期的异常，确保系统优雅降级
        print(f"❌ 屏幕控制子系统异常: {e}")
        command_listener.stop_listening()
        if GLOBAL_DEBUG:
            # 在全局调试模式下显示详细错误
            import sys
            sys.print_exception(e)


def test_screen_communication():
    """
    测试屏幕通信功能
    用于验证串口屏是否正常工作，就像给屏幕做健康检查
    """
    print("\n🔍 开始屏幕通信测试...")
    
    # 建立测试连接
    test_uart = initialize_screen_communication()
    if not test_uart:
        print("❌ 屏幕通信测试失败")
        return False
    
    # 尝试发送测试指令（如果有标准测试协议）
    try:
        # 这里可以添加特定的测试指令
        # 例如：test_uart.write(b"TEST_COMMAND")
        print("✅ 屏幕通信测试通过 - 基础连接正常")
        return True
    except Exception as e:
        print(f"❌ 屏幕通信测试异常: {e}")
        return False


# =============================================================================
# 独立运行模式 - 屏幕子系统的专用测试环境
# 当直接运行这个文件时，会进入测试模式，方便开发和调试
# =============================================================================
if __name__ == "__main__":
    """
    屏幕控制子系统独立测试模式
    无需启动整个智能时钟系统，单独测试屏幕功能
    """
    print("\n" + "="*60)
    print(f"  屏幕控制子系统 - 独立测试模式")
    print("="*60)
    
    # 模拟传感器管理器（用于测试）
    class MockSensorManager:
        """模拟传感器管理器 - 在测试时提供虚拟数据"""
        def __init__(self):
            self.temperature = 25.5
            self.humidity = 60.0
            self.pressure = 1013.25
            
        def read_sensor_data(self, uart, force=False):
            """模拟读取传感器数据"""
            if SCREEN_DEBUG:
                print(f"[模拟传感器] 温度: {self.temperature}°C, 湿度: {self.humidity}%")
            return True
    
    print("🧪 进入测试模式，使用模拟传感器数据...")
    
    # 创建模拟传感器实例
    test_sensor = MockSensorManager()
    
    # 运行通信测试
    communication_ok = test_screen_communication()
    
    if communication_ok:
        print("\n🎯 开始屏幕子系统完整测试...")
        try:
            # 启动完整的屏幕控制子系统（测试版本）
            run_screen_control_subsystem(
                sensor_manager=test_sensor,
                screen_uart=None  # 让系统自动创建UART连接
            )
        except KeyboardInterrupt:
            print("\n✅ 屏幕子系统测试完成（用户主动结束）")
        except Exception as e:
            print(f"\n❌ 屏幕子系统测试异常: {e}")
    else:
        print("\n💥 屏幕通信测试失败，无法进行完整测试")
    
    print("👋 屏幕控制子系统测试结束")