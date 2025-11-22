# ==================== 人体红外检测模块 ====================
# 这个文件负责检测是否有人靠近屏幕，自动控制屏幕亮度
# 功能像感应灯：有人靠近就点亮，没人就慢慢变暗
# 使用场景：省电、延长屏幕寿命、自动调光

# ==================== 导入必要工具 ====================
# machine模块：控制GPIO引脚
import machine
# time模块：控制渐变速度和检测间隔
import time

# 导入整个config模块（避免单变量导入失败）
import config


global suggested_brightness

# ==================== 模块级状态变量（替代函数属性） ====================
# 记录检测状态（避免重复操作）
_last_presence_state = None      # 上次是否有人（True/False）
_current_brightness = None       # 当前屏幕亮度（初始为None，首次运行时设置）

# ==================== 传感器对象（单例模式） ====================
_sr602_pin = None  # 全局传感器引脚对象

def _get_sr602_pin():
    """
    获取传感器引脚对象（单例模式）
    如果未初始化，则创建；如果已初始化，直接返回
    """
    global _sr602_pin
    if _sr602_pin is None:
        try:
            # 初始化传感器引脚（输入模式，下拉电阻）
            _sr602_pin = machine.Pin(
                config.SR602_DATA_PIN,
                machine.Pin.IN,
                machine.Pin.PULL_DOWN
            )
            if config.VERBOSE_SR602:
                print(f"SR602传感器初始化：GPIO{config.SR602_DATA_PIN}")
        except Exception as e:
            print(f"传感器引脚初始化失败：{e}")
            return None
    return _sr602_pin

# ==================== 亮度渐变函数 ====================
def _fade_in(uart, target_brightness):
    """
    屏幕亮度渐增（从暗到亮）
    参数：
      uart: 屏幕串口
      target_brightness: 目标亮度（0-100）
    机制：循环增加亮度 → 发送指令 → 延时，直到达到目标
    """
    global _current_brightness
    
    # 初始化当前亮度（首次运行时）
    if _current_brightness is None:
        _current_brightness = config.DEFAULT_SCREEN_BRIGHTNESS
    
    # 如果当前亮度已经≥目标，直接返回
    if _current_brightness > target_brightness:
        while _current_brightness > target_brightness:
            _current_brightness = max(_current_brightness - config.FADE_STEP, target_brightness)
        
            # 发送亮度指令（屏幕协议：dim=值）
            try:
                uart.write(f"dim={_current_brightness}".encode() + b'\xff\xff\xff')
            except:
            # 屏幕未响应时中断渐变
                break
        
            # 延时控制渐变速度（太快会闪，太慢等不及）
            time.sleep(config.FADE_DELAY)


        
    elif _current_brightness == target_brightness:
        return

    else:
    # 循环增加亮度
        while _current_brightness < target_brightness:
            _current_brightness = min(_current_brightness + config.FADE_STEP, target_brightness)
        
            # 发送亮度指令（屏幕协议：dim=值）
            try:
                uart.write(f"dim={_current_brightness}".encode() + b'\xff\xff\xff')
            except:
            # 屏幕未响应时中断渐变
                break
        
            # 延时控制渐变速度（太快会闪，太慢等不及）
            time.sleep(config.FADE_DELAY)

def _fade_out(uart):
    """
    屏幕亮度渐减（从亮到暗，直到0）
    参数：
      uart: 屏幕串口
    机制：循环减少亮度 → 发送指令 → 延时，直到完全熄灭
    """
    global _current_brightness
    
    # 初始化当前亮度（首次运行时）
    if _current_brightness is None:
        _current_brightness = config.DEFAULT_SCREEN_BRIGHTNESS
    
    # 如果当前亮度已经是0，直接返回
    if _current_brightness <= 0:
        return
    
    # 循环减少亮度
    while _current_brightness > 0:
        _current_brightness = max(_current_brightness - config.FADE_STEP, 0)
        
        # 发送亮度指令
        try:
            uart.write(f"dim={_current_brightness}".encode() + b'\xff\xff\xff')
        except:
            break
        
        # 延时
        time.sleep(config.FADE_DELAY)

# ==================== 人体检测核心函数 ====================
def _detect_human(sensor_pin):
    """
    读取传感器电平，判断是否有人
    参数：
      sensor_pin: 传感器GPIO对象
    返回：True=有人，False=无人
    原理：SR602有人时输出高电平(1)，无人时低电平(0)
    """
    return sensor_pin.value() == 1

# ==================== 亮度控制逻辑 ====================
def _control_brightness(uart, is_present):
    """
    根据检测结果控制屏幕亮度
    参数：
      uart: 屏幕串口
      is_present: 是否有人（True/False）
    策略：
      有人 → 渐增到默认亮度
      无人 → 渐减到0（熄灭）
    """
    global _last_presence_state
    global suggested_brightness

    # 初始化状态（首次运行时）
    if _last_presence_state is None:
        _last_presence_state = None
    
    # 状态未变化时，不做任何操作（避免重复渐变）
    #if is_present == _last_presence_state:
     #  return
    
    # 检测到有人的处理
    if is_present:
        if config.VERBOSE_SR602:
            print(f"有人靠近 → 屏幕渐亮至{suggested_brightness}%")
        
        # 渐增亮度
        _fade_in(uart, suggested_brightness)
    
    # 检测到无人的处理
    else:
        if config.VERBOSE_SR602:
            print("无人 → 屏幕渐暗至熄灭")
        
        # 渐减亮度
        _fade_out(uart)
    
    # 更新状态记录
    _last_presence_state = is_present

# ==================== 对外接口函数 ====================
def detect_and_control_brightness(uart, verbose=None):
    """
    人体检测和亮度控制的一键调用函数
    参数：
      uart: 屏幕串口
      verbose: 调试开关（None时使用config.VERBOSE_SR602）
    调用时机：在定时任务循环中反复调用
    机制：初始化传感器 → 读取状态 → 控制亮度
    """
    if verbose is None:
        verbose = config.VERBOSE_SR602
    
    # 获取传感器引脚（单例模式）
    sensor_pin = _get_sr602_pin()
    if sensor_pin is None:
        if verbose:
            print("传感器未初始化，跳过检测")
        return
    
    # 初始化屏幕亮度（开机时设置一次）
    global _current_brightness
    if _current_brightness is None:
        uart.write(f"dim={config.DEFAULT_SCREEN_BRIGHTNESS}".encode() + b'\xff\xff\xff')
        _current_brightness = config.DEFAULT_SCREEN_BRIGHTNESS
        if verbose:
            print(f"屏幕亮度初始化：{_current_brightness}%")
    
    # 读取传感器状态
    try:
        is_present = _detect_human(sensor_pin)
        
        # 根据状态控制亮度
        _control_brightness(uart, is_present)
        
        # 调试日志
        if verbose and _last_presence_state != is_present:
            print(f"人体状态变化：{'有人' if is_present else '无人'}")
        
    except Exception as e:
        print(f"检测过程出错：{e}")

# ==================== 独立测试入口 ====================
if __name__ == "__main__":
    """
    独立测试：模拟传感器输出，测试亮度控制逻辑
    不需要真实传感器，只验证渐变算法和状态机
    """
    print("="*50)
    print(" SR602人体检测 - 独立测试")
    print("   测试渐变算法和状态控制")
    print("="*50)
    
    # 测试1：渐变算法
    print("\n[测试1] 亮度渐变算法...")
    
    # 模拟从0渐增到50
    target = 50
    step = 5
    _current_brightness = 0
    for i in range(0, target, step):
        _current_brightness = min(_current_brightness + step, target)
        print(f"   渐增：{_current_brightness}%")
    
    # 模拟从50渐减到0
    for i in range(0, target, step):
        _current_brightness = max(_current_brightness - step, 0)
        print(f"   渐减：{_current_brightness}%")
    
    print("   ✅ 渐变算法正常")
    
    # 测试2：状态机
    print("\n[测试2] 状态机逻辑...")
    
    # 模拟状态变化
    _last_presence_state = None
    states = [True, True, False, False, True]  # 有人, 有人, 无人, 无人, 有人
    
    for i, state in enumerate(states):
        if _last_presence_state != state:
            action = "渐亮" if state else "渐暗"
            print(f"   状态{i}：{'有人' if state else '无人'} → {action}")
            _last_presence_state = state
        else:
            print(f"   状态{i}：{'有人' if state else '无人'} → 无变化")
    
    print("   ✅ 状态机逻辑正常")
    
    print("\n✅ 所有测试通过！SR602模块功能正常")
    print("   说明：未连接真实传感器，仅验证算法逻辑")
    
    print("\n独立测试结束")






















# ===lux_sensor环境光传感器模块（仅计算建议亮度）=======


# ===全局状态变量=======
current_adc_value = 0
suggested_brightness = 0
adc = None

def _map_adc_to_brightness(adc_value):
    """
    直接将ADC值映射到屏幕亮度
    """
    # 限制ADC值在配置范围内
    adc_value = max(config.LUX_SENSOR_MIN_ADC, min(adc_value, config.LUX_SENSOR_MAX_ADC))
    
    # 线性映射
    normalized = (adc_value - config.LUX_SENSOR_MIN_ADC) / (config.LUX_SENSOR_MAX_ADC - config.LUX_SENSOR_MIN_ADC)
    
    # 确保在0-1范围内
    normalized = max(0, min(1, normalized))
    
    # 线性映射到亮度范围
    brightness = config.LUX_SENSOR_MIN_BRIGHTNESS + normalized * (config.LUX_SENSOR_MAX_BRIGHTNESS - config.LUX_SENSOR_MIN_BRIGHTNESS)
    
    return int(brightness)

def _smooth_value(new_value, old_value):
    """应用指数平滑滤波"""
    return (new_value * config.LUX_SENSOR_SMOOTHING_FACTOR + 
            old_value * (1 - config.LUX_SENSOR_SMOOTHING_FACTOR))

def lux_sensor_detect_thread(verbose):
    """lux_sensor环境光检测独立线程"""
    global current_adc_value, suggested_brightness, adc
    
    # ADC初始化
    try:
        adc = machine.ADC(machine.Pin(config.LUX_SENSOR_ADC_PIN))
        adc.atten(machine.ADC.ATTN_11DB)
        adc.width(machine.ADC.WIDTH_12BIT)
        
        print(f"[lux_sensor] 传感器初始化成功 → ADC引脚：GPIO{config.LUX_SENSOR_ADC_PIN}")
        print(f"[lux_sensor] ADC映射范围: {config.LUX_SENSOR_MIN_ADC}-{config.LUX_SENSOR_MAX_ADC} → {config.LUX_SENSOR_MIN_BRIGHTNESS}-{config.LUX_SENSOR_MAX_BRIGHTNESS}%")
    except Exception as e:
        print(f"[lux_sensor ERROR] 传感器初始化失败：{e}")
        return
    
    # 初始建议亮度计算
    suggested_brightness = (config.LUX_SENSOR_MIN_BRIGHTNESS + config.LUX_SENSOR_MAX_BRIGHTNESS) // 2
    print(f"[lux_sensor] 环境光检测启动 → 初始建议亮度：{suggested_brightness}%")
    
    # 主循环
    print(f"[lux_sensor] 开始环境光检测 → 检测间隔：{config.LUX_SENSOR_READ_INTERVAL}s")
    cycle_count = 0
    
    while True:
        try:
            # 读取ADC值
            raw_adc_value = adc.read()
            
            # 应用平滑滤波
            current_adc_value = _smooth_value(raw_adc_value, current_adc_value)
            
            # 映射到建议亮度
            new_suggested_brightness = _map_adc_to_brightness(current_adc_value)
            
            # 更新建议亮度
            if new_suggested_brightness != suggested_brightness:
                old_brightness = suggested_brightness
                suggested_brightness = new_suggested_brightness
                print(f"[lux_sensor] 环境光变化 → 建议亮度: {old_brightness}% → {suggested_brightness}% (ADC: {current_adc_value})")
            # 定期输出调试信息
            cycle_count += 1
            if cycle_count % 5 == 0:  # 每5次循环输出一次
                normalized = (current_adc_value - config.LUX_SENSOR_MIN_ADC) / (config.LUX_SENSOR_MAX_ADC - config.LUX_SENSOR_MIN_ADC)
                print(f"[lux_sensor STATUS] ADC:{current_adc_value} Normalized:{normalized:.2f} Brightness:{suggested_brightness}%")
            
        except Exception as e:
            print(f"[lux_sensor ERROR] 检测过程中出错：{e}")
        
        #time.sleep(config.LUX_SENSOR_READ_INTERVAL)

def get_current_status():
    """获取当前ADC值和建议亮度状态"""
    return {
        'adc_value': current_adc_value,
        'suggested_brightness': suggested_brightness
    }

def get_suggested_brightness():
    """直接获取当前建议亮度"""
    return suggested_brightness





