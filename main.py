# ==================== 程序主入口文件 ====================
# 这个文件是开机后第一个运行的代码，负责系统初始化和启动
# 功能流程：初始化硬件 → 连接网络 → 启动双线程系统
# 设计思路：只做一次准备，然后启动两个长期任务（屏幕控制 + 定时任务）

# ==================== 导入必要工具 ====================
# machine模块：硬件控制（串口、引脚）
import machine
# time模块：延时函数
import time
# _thread模块：创建新线程
import _thread

# 导入功能模块
import util.network as net_util          # WiFi连接功能
import function.ntp_clock as ntp_module  # 网络时间同步
import function.air_quality_sensor as sensor_module  # 空气质量传感器
import function.weather as weather_module  # 天气数据获取
import screen_control_subsystem          # 屏幕指令处理
import function.human_presence as sr602_module  # 人体检测
import function.lux_screenlight as lux_screenlight  # 自动亮度控制


import config
# 从配置文件读取参数
from config import (
    SERIAL_PORT, SERIAL_BAUD_RATE, SERIAL_TX_PIN, SERIAL_RX_PIN,
    UART_NUM, UART_BAUDRATE, UART_TX_PIN, UART_RX_PIN,
    VERBOSE_MAIN, VERBOSE_SENSOR, VERBOSE_SR602,
    WEATHER_REFRESH_INTERVAL,
    NTP_CALIBRATION_HOURS,
    SENSOR_READ_INTERVAL,
    DETECT_INTERVAL
)

# ==================== 初始化区域（开机只运行一次） ====================
def initialize_system():
    """
    开机初始化：像运动员比赛前的热身，只做一遍
    步骤：连WiFi → 初始化串口 → 启动传感器 → 同步时间 → 强制推送所有数据
    返回：三个硬件实例（屏幕串口、传感器、传感器串口）
    """
    print("="*50)
    print(" 系统启动中... 正在初始化硬件")
    print("="*50)
    
    # 1. 连接WiFi
    print("\n[步骤1/5] 连接WiFi网络...")
    try:
        if not net_util.connect_wifi():
            print("❌ WiFi连接失败，程序无法继续运行")
            print("✅ WiFi连接成功！\n")
    except Exception as e:
        print(f"WiFi连接线程启动失败：{e}")

    # 2. 初始化串口2（连接屏幕，用于显示数据）
    print("[步骤2/5] 初始化屏幕串口...")
    screen_uart = machine.UART(
        SERIAL_PORT, baudrate=SERIAL_BAUD_RATE,
        tx=machine.Pin(SERIAL_TX_PIN), rx=machine.Pin(SERIAL_RX_PIN),
        bits=8, parity=None, stop=1, timeout=100
    )
    # 发送测试数据验证串口工作
    test_cmd = "system_ready=1"
    screen_uart.write(test_cmd.encode() + b'\xff\xff\xff')
    
    # 3. 初始化串口1（连接传感器，读取空气质量）
    print("[步骤3/5] 初始化传感器串口...")
    sensor_uart = machine.UART(
        UART_NUM, baudrate=UART_BAUDRATE,
        tx=machine.Pin(UART_TX_PIN), rx=machine.Pin(UART_RX_PIN),
        bits=8, parity=None, stop=1, timeout=10
    )
    sensor_uart.write(b"")  # 清空串口缓存
    
    # 4. 初始化传感器对象（包含TVOC/甲醛/温湿度等所有功能）
    print("[步骤4/5] 初始化空气质量传感器...")
    sensor = sensor_module.MultiSensor(uart=sensor_uart, verbose=VERBOSE_SENSOR)
    
    # 5. 同步网络时间（让系统知道现在几点）
    print("[步骤5/5] 同步网络时间...")
    ntp_attempts = 0
    max_attempts = 5
    while ntp_attempts < max_attempts:
        success, tz = ntp_module.sync_ntp_to_rtc()
        if success:
            current_time = ntp_module.get_current_formatted_time()
            print(f"   ✅ 时间校准成功：{current_time} (UTC+{tz:.1f})")
            break
        ntp_attempts += 1
        print(f"   第{ntp_attempts}次校准失败，2秒后重试...")
        time.sleep(2)
    else:
        print("⚠️  时间校准失败，但程序将继续运行（时间可能不准确）")
    
    print("\n" + "="*50)
    print(" 硬件初始化完成！")
    print("="*50)
    
    # 6. 开机强制推送所有数据（确保屏幕显示最新信息）
    # 使用try-except防止失败阻塞启动
    print("\n[强制推送] 开机推送所有数据到屏幕...")
    try:
        if screen_uart and sensor_uart and sensor:
            # 强制推送时间（NTP已校准）
            ntp_module.send_time_to_serial_screen(screen_uart, force=True)
            print("   ✅ 时间已推送")
            
            # 强制推送天气（立即获取最新数据）
            weather_module.get_weather_by_ip(screen_uart, force=True)
            print("   ✅ 天气已推送")
            
            # 强制推送传感器（读取当前环境数据）
            sensor.read_sensor_data(screen_uart, force=True)
            print("   ✅ 传感器数据已推送")
    except Exception as e:
        print(f"   ⚠️  强制推送部分失败：{e}（不影响主程序运行，已跳过）")
    
    return screen_uart, sensor, sensor_uart

# ==================== 定时任务区域（持续运行，永不停止） ====================
def run_continuous_tasks(screen_uart, sensor, sensor_uart, screen_lock, sensor_lock):
    """
    定时任务：像闹钟一样，每隔一段时间响一次
    功能循环：更新天气 → 校准时间 → 读取传感器 → 检测人体 → 时间自动推送
    每个任务按自己的时间表执行，互不干扰
    """
    print("\n" + "="*50)
    print(" 定时任务系统启动！")
    print("="*50)

    # 记录上次执行时间（初始化为当前时间）
    last_weather = time.time()
    last_ntp = time.time()
    last_sensor = time.time()
    last_sr602 = time.time()
    last_time_check = time.time()  # 新增：时间自动推送检查
    
    # 主循环：不断检查是否到了该执行任务的时间
    while True:
        current_time = time.time()
        
        # 任务1：更新天气数据（按配置间隔）
        if current_time - last_weather >= WEATHER_REFRESH_INTERVAL:
            # 用锁保护屏幕串口，防止和屏幕控制线程冲突
            with screen_lock:
                weather_module.get_weather_by_ip(screen_uart, force=False)
            last_weather = current_time
        
        # 任务2：校准系统时间（按配置间隔）
        ntp_interval_seconds = NTP_CALIBRATION_HOURS * 3600
        if current_time - last_ntp >= ntp_interval_seconds:
            ntp_module.sync_ntp_to_rtc()
            last_ntp = current_time
        
        # 任务3：读取传感器数据（按配置间隔，含TVOC/甲醛/温湿度）
        if sensor and sensor_uart:
            if current_time - last_sensor >= SENSOR_READ_INTERVAL:
                # 用锁保护传感器串口
                sensor_uart.read(sensor_uart.any())
                with sensor_lock:
                    sensor.read_sensor_data(screen_uart, force=False)
                last_sensor = current_time
        
        # 任务4：人体检测（按配置间隔，控制屏幕亮度）
        if current_time - last_sr602 >= DETECT_INTERVAL:
            sr602_module.detect_and_control_brightness(screen_uart, verbose=VERBOSE_SR602)
            last_sr602 = current_time
        
        # 任务5：时间自动推送（每秒检查，有变化才推送）
        if current_time - last_time_check >= 1:
            ntp_module.send_time_to_serial_screen(screen_uart)
            last_time_check = current_time
        
        # 休息0.1秒再检查，让出空余位置给其他线程
        time.sleep(0.1)

# ==================== 主函数（程序入口） ====================
def main():
    """
    程序从这里开始运行
    就像电影的开幕，只做一次开场，然后交给演员表演
    """

    _thread.start_new_thread(
        lux_screenlight.lux_sensor_detect_thread,
        (config.VERBOSE_LUX_SENSOR,)
    )

        
    # 步骤1：执行一次性初始化
    screen_uart, sensor, sensor_uart = initialize_system()
    
    # 如果初始化失败，程序退出
    if screen_uart is None:
        print("\n系统初始化失败，程序终止运行")
        return
    
    # 步骤2：创建互斥锁（保护两个串口不被同时操作）
    screen_lock = _thread.allocate_lock()  # 保护屏幕串口
    sensor_lock = _thread.allocate_lock()  # 保护传感器串口
    
    # 步骤3：启动屏幕控制子系统（在独立线程运行）
    print("\n[线程管理] 启动屏幕控制子系统（独立线程）...")
    try:
        _thread.start_new_thread(
            screen_control_subsystem.run_screen_control_subsystem,
            (screen_uart, sensor, screen_lock)
        )
        print("屏幕控制线程启动成功")
    except Exception as e:
        print(f"屏幕控制线程启动失败：{e}")
        return
    
    # 步骤4：启动定时任务系统（在主线程运行）
    print("\n[线程管理] 启动定时任务系统（主线程）...")
    try:
        run_continuous_tasks(screen_uart, sensor, sensor_uart, screen_lock, sensor_lock)
    except KeyboardInterrupt:
        print("\n\n用户主动中断程序运行")
    except Exception as e:
        print(f"\n定时任务系统异常：{e}")

# ==================== 运行入口 ====================
# 当这个文件被运行时，启动完整系统
if __name__ == "__main__":

    print("\n" + "="*60)
    print("   按Ctrl+C可停止运行")
    print("="*60)
    
    # 直接启动主函数
    main()
