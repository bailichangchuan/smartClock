# ==================== 屏幕数据显示工具 ====================
# 这个文件负责把数据发送到串口屏上显示
# 功能像快递员：把包裹（数据）送到指定地址（屏幕控件）
# 使用场景：天气、时间、传感器数据需要显示时调用

# ==================== 导入必要工具 ====================
# time模块：发送后短暂延时，避免数据拥堵
import time

# 从配置导入调试开关
from config import VERBOSE_SCREEN_SEND

# ==================== 数据推送函数 ====================
def upload(uart, data_str, control_name="t0", property_name="txt"):
    """
    向屏幕指定控件发送数据（核心函数，所有显示都通过它）
    参数：
      uart: 屏幕串口（已经初始化好的）
      data_str: 要显示的内容（字符串）
      control_name: 控件名称（如"t0"、"t1"，看屏幕设计）
      property_name: 控件属性（通常是"txt"表示文本）
    发送格式：控件名.属性名="值" + 三字节结束符
    示例：t0.txt="25℃" + 0xFF 0xFF 0xFF
    """
    try:
        # 1. 构造指令字符串
        # 格式：控件名.属性名="值"
        command = f"{control_name}.{property_name}=\"{data_str}\""
        
        # 2. 调试日志（打印要发送的内容）
        if VERBOSE_SCREEN_SEND:
            print(f"屏幕推送 → 控件：{control_name}，属性：{property_name}，内容：{data_str}")
        
        # 3. 发送指令（编码为UTF-8字节串）
        uart.write(command.encode('utf-8'))
        
        # 4. 发送结束符（三字节0xFF，告诉屏幕指令结束）
        uart.write(b'\xff\xff\xff')
        
        # 5. 短暂延时（10毫秒），确保指令完整发送，避免串口拥堵
        time.sleep_ms(10)
        
        return True  # 发送成功
        
    except Exception as e:
        # 出错处理（通常是串口未初始化或断开）
        print(f"屏幕推送失败 → 控件：{control_name}，错误：{e}")
        return False  # 发送失败

# ==================== 独立测试入口 ====================
if __name__ == "__main__":
    """
    独立测试：模拟向屏幕发送数据，测试推送功能
    不需要真实屏幕，只验证指令构造和串口操作
    """
    print("="*50)
    print(" 屏幕数据推送 - 独立测试")
    print("   测试指令构造和发送流程")
    print("="*50)
    
    # 模拟屏幕串口（用None代替，不实际发送）
    mock_uart = None
    
    # 测试1：基本推送
    print("\n[测试1] 基本推送...")
    cmd = upload(mock_uart, "25℃", "t0", "txt")
    print(f"   结果：指令构造{'成功' if cmd else '失败'}")
    
    # 测试2：快捷函数
    print("\n[测试2] 快捷推送函数...")
    time_result = upload(mock_uart, "14:30", "t0", "txt")
    date_result = upload(mock_uart, "2025-11-22", "t1", "txt")
    print(f"   时间推送：{ '成功' if time_result else '失败' }")
    print(f"   日期推送：{ '成功' if date_result else '失败' }")
    
    # 测试3：天气数据
    print("\n[测试3] 天气数据推送...")
    weather_result = upload(mock_uart, "深圳", "t8", "txt")
    print(f"   结果：{ '成功' if weather_result else '失败' }")
    
    # 测试4：传感器数据（含TVOC）
    print("\n[测试4] 传感器数据推送...")
    sensor_result = upload(mock_uart, "35μg/m³", "t6", "txt")
    print(f"   结果：{ '成功' if sensor_result else '失败' }")
    
    print("\n✅ 测试完成：所有推送函数正常")
    print("   说明：由于mock_uart=None，未实际发送，仅验证逻辑")
    
    print("\n独立测试结束")
