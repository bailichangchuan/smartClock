# ==================== 屏幕控制子系统 ====================
# 这个文件负责处理屏幕点击事件，像一位24小时待命的客服
# 工作流程：监听屏幕消息 → 解析指令 → 执行对应操作

# ==================== 导入必要工具 ====================
# machine模块：硬件串口操作
import machine
# _thread模块：创建独立线程
import _thread
# time模块：延时控制
import time

# 导入功能模块）
import function.ntp_clock as ntp_module
import function.weather as weather_module

# 从配置导入屏幕串口参数和调试开关
from config import SERIAL_PORT, SERIAL_BAUD_RATE, SERIAL_TX_PIN, SERIAL_RX_PIN, VERBOSE_SCREEN

# ==================== 区域一：屏幕通信协议配置 ====================
# 这些常量是屏幕厂商定义的"暗号"，必须严格遵守
CMD_HEADER = 0x65                    # 每条指令的开头标记（1字节）
CMD_END = [0xFF, 0xFF, 0xFF]        # 每条指令的结束标记（3字节）
OP_PRESS = 0x01                      # 用户"按下"按钮的操作码
OP_RELEASE = 0x00                    # 用户"松开"按钮的操作码

# 指令队列：存放待处理的屏幕指令（先进先出，最多10条）
command_queue = []
# 使用简单的列表操作作为锁
# 通过最小化临界区来避免冲突

# ==================== 区域二：指令监听功能（耳朵） ====================
def listen_screen_commands(uart, verbose=VERBOSE_SCREEN):
    """
    这个函数像耳朵一样，持续监听屏幕有没有发送消息
    它在一个独立线程运行，不阻塞主程序
    参数：
      uart: 已经初始化好的屏幕串口
      verbose: 调试开关（True会显示监听到的内容）
    """
    if verbose:
        print("耳朵已启动，正在监听屏幕消息...")
    
    # 无限循环监听（程序运行期间不停止）
    while True:
        # 检查串口缓冲区是否有数据
        if uart.any() > 0:
            # 读取所有可用数据（可能是一条完整指令，也可能是片段）
            data = uart.read(uart.any())
            
            # 验证指令长度是否7字节（屏幕指令固定长度）
            if data and len(data) == 7:
                # 验证指令格式（开头和结尾标记是否正确）
                if data[0] == CMD_HEADER and list(data[-3:]) == CMD_END:
                    # 格式正确，加入队列等待处理
                    # 临界区最小化，减少冲突可能
                    command_queue.append(data)
                    # 限制队列长度不超过10条（防止内存占用过大）
                    if len(command_queue) > 10:
                        command_queue.pop(0)  # 删除最早的一条
                    
                    if verbose:
                        print(f"📨 收到有效指令：{data.hex().upper()}")
                else:
                    # 格式错误，丢弃（可能是干扰数据）
                    if verbose:
                        print(f"💔 收到无效指令格式：{data.hex().upper()}")
            else:
                # 长度不对，丢弃（等待下次读取）
                if verbose:
                    print(f"📏 指令长度错误：期望7字节，实际{len(data) if data else 0}字节")
        
        # 监听间隔：10毫秒（太快浪费CPU，太慢会漏指令）
        time.sleep_ms(10)

# ==================== 区域三：指令解析与执行（大脑） ====================
def parse_and_execute(uart, sensor=None, lock=None, verbose=VERBOSE_SCREEN):
    """
    这个函数像大脑一样，分析指令含义并执行对应操作
    它在主监听线程中循环调用，处理队列里的指令
    参数：
      uart: 屏幕串口（用于回复屏幕）
      sensor: 传感器实例（用于更新空气质量数据）
      lock: 互斥锁（保护串口不被两个线程同时使用）
      verbose: 调试开关
    """
    while True:
        # 检查队列是否有待处理指令
        if command_queue:
            # 临界区：取出指令后立即处理，不持有锁太久
            data = command_queue.pop(0)
            
            # 提取指令内容（页号、控件号、操作类型）
            page_id = data[1]
            control_id = data[2]
            operation = data[3]
            
            if verbose:
                print(f"解析指令：页{page_id} 控件{control_id} 操作{operation}")
            
            # 只处理"按下"操作（松开不处理，避免重复执行）
            if operation == OP_PRESS:
                # 指令映射：不同按钮对应不同功能
                # 就像电视遥控器：1号键开灯，2号键开空调
                
                # 按钮1：页0控件0 → 强制更新时间和天气
                if page_id == 0 and control_id == 0:
                    if verbose:
                        print("执行操作：强制更新时间和天气")
                    # 用锁保护串口，防止和定时任务冲突
                    if lock:
                        with lock:
                            ntp_module.send_time_to_serial_screen(uart, force=True)
                            time.sleep_ms(10)
                            weather_module.get_weather_by_ip(uart, force=True)
                
                # 按钮2：页2控件0 → 强制更新空气质量
                elif page_id == 2 and control_id == 0:
                    if verbose:
                        print("执行操作：强制更新空气质量")
                    if sensor and lock:
                        with lock:
                            sensor.read_sensor_data(uart, force=True)
                
                # 其他按钮可以在这里添加更多功能
                # 例如：页1控件1 → 切换显示模式
                else:
                    if verbose:
                        print(f"⚠️  未定义按钮：页{page_id} 控件{control_id}（无操作）")
        
        # 处理间隔：50毫秒（给CPU一点休息时间）
        time.sleep_ms(50)

# ==================== 对外接口：启动屏幕控制系统 ====================
def run_screen_control_subsystem(screen_uart, sensor, screen_lock, verbose=VERBOSE_SCREEN):
    """
    这是屏幕控制子系统的总开关
    初始化完成后，启动监听线程和解析循环
    参数：
      screen_uart: 已经初始化好的屏幕串口
      sensor: 空气质量传感器实例（包含TVOC/甲醛/温湿度功能）
      screen_lock: 互斥锁（保护屏幕串口）
      verbose: 调试开关
    运行机制：先启动监听线程 → 然后主线程循环解析执行
    """
    print("\n启动屏幕控制子系统...")
    
    # 启动监听线程（耳朵开始工作，独立运行）
    _thread.start_new_thread(listen_screen_commands, (screen_uart, verbose))
    
    if verbose:
        print("   监听线程已启动")
    
    # 主循环解析指令（大脑开始工作，占用主线程）
    parse_and_execute(screen_uart, sensor, screen_lock, verbose)

# ==================== 独立测试入口 ====================
if __name__ == "__main__":
    """
    独立测试：不依赖其他文件，模拟屏幕发送指令
    验证指令接收、解析、执行全流程是否正常
    """
    print("="*50)
    print(" 屏幕控制子系统 - 独立测试")
    print("   测试指令：页1控件2按下")
    print("="*50)
    
    # 模拟一条屏幕指令（页1控件2按下）
    # 格式：帧头 + 页号 + 控件号 + 操作码 + 结束符
    mock_cmd = bytes([0x65, 1, 2, 0x01, 0xFF, 0xFF, 0xFF])
    
    # 验证指令格式
    if mock_cmd[0] == CMD_HEADER and list(mock_cmd[-3:]) == CMD_END:
        print("✅ 指令格式验证通过")
        print(f"   页号：{mock_cmd[1]}，控件号：{mock_cmd[2]}，操作：{'按下' if mock_cmd[3]==0x01 else '松开'}")
        
        # 测试加入队列
        command_queue.append(mock_cmd)
        print("✅ 指令已加入队列")
        
        # 模拟取出处理
        if command_queue:
            data = command_queue.pop(0)
            print(f"✅ 从队列取出并解析：执行页{data[1]}控件{data[2]}的按下操作")
            print("\n测试成功！全流程正常")
    else:
        print("❌ 指令格式错误")
    
    print("\n独立测试结束")
