"""
SmartClock 智能时钟系统 - 精简主程序入口
功能：仅负责硬件初始化和双核心子系统启动
特点：启动后立即结束，不阻塞任何核心
"""

import machine
import _thread
from config import (
    DEVICE_NAME, SYSTEM_DEBUG,
    SCREEN_UART_PORT, SCREEN_BAUD_RATE, SCREEN_TX_PIN, SCREEN_RX_PIN
)

# 导入子系统
import screen_control_subsystem
import timer_control_subsystem
import function.multi_sensor as sensor_module
import util.network as net_util


def initialize_screen_uart():
    """初始化串口屏通信通道"""
    try:
        screen_uart = machine.UART(
            SCREEN_UART_PORT,
            baudrate=SCREEN_BAUD_RATE,
            tx=machine.Pin(SCREEN_TX_PIN),
            rx=machine.Pin(SCREEN_RX_PIN),
            bits=8, parity=None, stop=1, timeout=100
        )
        print("✅ 串口屏通信通道建立成功")
        return screen_uart
    except Exception as e:
        print(f"❌ 串口屏通信初始化失败: {e}")
        return None


def initialize_basic_sensors():
    """初始化基础传感器系统"""
    try:
        sensor_system = sensor_module.MultiSensor(
            uart_manager=None,  # 简化初始化
            verbose=False
        )
        print("✅ 基础传感器系统初始化成功")
        return sensor_system
    except Exception as e:
        print(f"❌ 传感器系统启动失败: {e}")
        return None


def initialize_essential_hardware():
    """仅初始化最必要的硬件组件"""
    print(f"\n🎯 {DEVICE_NAME} - 系统启动")
    
    # 1. 建立网络连接
    print("📡 连接WiFi网络...")
    if not net_util.connect_wifi():
        return None
    
    # 2. 初始化屏幕通信（核心0必须）
    screen_uart = initialize_screen_uart()
    if not screen_uart:
        return None
    
    # 3. 初始化基础传感器
    sensor_system = initialize_basic_sensors()
    
    return {
        'screen_uart': screen_uart,
        'sensors': sensor_system
    }


def start_core1_timer_subsystem(hardware):
    """启动核心1定时器子系统（所有后台任务）"""
    def core1_main():
        print("🟢 核心1：定时器控制子系统启动")
        
        # 运行所有后台任务
        timer_control_subsystem.run_timer_control_subsystem(
            screen_uart=hardware['screen_uart'],
            sensor_manager=hardware['sensors'],
            sensor_uart_manager=None,
            music_player=None
        )
    
    # 在新线程中启动核心1子系统
    _thread.start_new_thread(core1_main, ())


def run_core0_screen_subsystem(hardware):
    """运行核心0屏幕子系统（独占核心0）"""
    print("🔵 核心0：屏幕控制子系统启动")
    
    # 独占核心0运行（在主线程中）
    screen_control_subsystem.run_screen_control_subsystem(
        sensor_manager=hardware['sensors'],
        screen_uart=hardware['screen_uart']
    )


def main():
    """主程序：仅初始化并启动，然后立即结束"""
    print("🚀 开始系统初始化...")
    
    # 1. 初始化必要硬件
    hardware = initialize_essential_hardware()
    if not hardware:
        print("❌ 硬件初始化失败")
        return
    
    # 2. 启动核心1定时器子系统（后台任务）
    start_core1_timer_subsystem(hardware)
    
    # 3. 运行核心0屏幕子系统（用户界面）- 这会阻塞主线程
    print("📋 启动双核心架构...")
    run_core0_screen_subsystem(hardware)
    
    # main.py 理论上不会到达这里，因为核心0会阻塞
    print("✅ 系统启动完成")


# 系统启动入口
if __name__ == "__main__":
    """
    程序启动点 - 从这里开始系统的生命旅程
    处理各种启动异常，确保优雅的故障处理
    """
    try:
        main()
    except KeyboardInterrupt:
        # 用户主动中断（如Ctrl+C）
        print("\n\n⚠️ 系统被用户中断")
    except Exception as e:
        # 捕获未预期的异常
        print(f"\n\n❌ 系统启动异常: {e}")
        import sys
        sys.print_exception(e)
    finally:
        # 无论发生什么，都要优雅地关闭系统
        print("\n👋 系统已关闭，感谢使用！")