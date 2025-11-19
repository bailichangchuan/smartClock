# ===SR602人体红外传感器检测模块（统一控制亮度）=======
# 修改逻辑：有人时使用TEMT6000的环境光建议亮度，无人时关闭屏幕
# 所有亮度变化（包括环境光变化）都由SR602模块统一控制，确保丝滑渐变
import machine
import utime
import _thread

# 导入TEMT6000模块以获取环境光建议亮度
import function.temt6000 as temt6000_module

# 从config.py导入必要参数
from config import (
    SR602_DATA_PIN,
    FADE_STEP,
    FADE_DELAY,
    DETECT_INTERVAL
)

# ===全局状态变量=======
last_presence_state = None
current_brightness = 0  # 当前实际屏幕亮度
target_brightness = 0   # 目标亮度（用于渐变）
last_suggested_brightness = 0  # 上一次的环境光建议亮度
is_fading = False       # 是否正在渐变中

# ===渐变工具函数（增强版，支持任意方向的渐变）=======
def _fade_to_target(uart, new_target_brightness, verbose):
    """
    渐变到目标亮度（支持任意方向）
    """
    global current_brightness, target_brightness, is_fading
    
    target_brightness = new_target_brightness
    
    # 如果已经在渐变中，直接更新目标值，让渐变继续
    if is_fading:
        if verbose:
            print(f"[SR602 FADE] 更新渐变目标: {current_brightness}% → {target_brightness}%")
        return
    
    is_fading = True
    
    if verbose:
        print(f"[SR602 FADE] 开始渐变: {current_brightness}% → {target_brightness}%")
    
    while current_brightness != target_brightness:
        if current_brightness < target_brightness:
            # 渐亮
            current_brightness = min(current_brightness + FADE_STEP, target_brightness)
        else:
            # 渐暗
            current_brightness = max(current_brightness - FADE_STEP, target_brightness)
        
        cmd = f"dim={current_brightness}".encode('utf-8') + b"\xff\xff\xff"
        uart.write(cmd)
        
        if verbose:
            print(f"[SR602 FADE] 当前亮度: {current_brightness}%")
        
        utime.sleep(FADE_DELAY)
    
    is_fading = False
    if verbose:
        print(f"[SR602 FADE] 渐变完成: {current_brightness}%")

# ===核心检测函数=======
def _detect_human(sensor_pin):
    return sensor_pin.value() == 1

# ===获取环境光建议亮度=======
def _get_ambient_brightness():
    """
    从TEMT6000模块获取环境光建议亮度
    如果TEMT6000模块未就绪，返回备用亮度
    """
    try:
        suggested_brightness = temt6000_module.get_suggested_brightness()
        return suggested_brightness
    except Exception as e:
        print(f"[SR602 WARNING] 获取环境光亮度失败: {e}，使用备用亮度50")
        return 50

# ===检查环境光变化并调整亮度=======
def _check_and_adjust_ambient_light(uart, verbose):
    """
    在有人状态下检查环境光变化，如果变化明显则调整亮度
    """
    global last_suggested_brightness
    
    # 获取当前环境光建议亮度
    suggested_brightness = _get_ambient_brightness()
    
    # 如果环境光亮度变化超过阈值，则开始渐变
    brightness_diff = abs(suggested_brightness - last_suggested_brightness)
    if brightness_diff >= 3:  # 亮度变化超过3%时调整
        if verbose:
            print(f"[SR602] 环境光变化 → 开始渐变: {current_brightness}% → {suggested_brightness}%")
        
        # 开始渐变到新的目标亮度
        _fade_to_target(uart, suggested_brightness, verbose)
        last_suggested_brightness = suggested_brightness

# ===亮度控制函数（修改逻辑：有人时使用环境光亮度）=======
def _control_screen_brightness(uart, is_present, verbose):
    global last_presence_state, last_suggested_brightness
    if is_present != last_presence_state:
        if not is_present:
            # 检测到无人 → 渐变关闭屏幕
            print(f"[SR602] 检测到无人 → 渐变关闭屏幕")
            if verbose:
                print(f"[SR602 DEBUG] 渐变参数：步长{FADE_STEP}，间隔{FADE_DELAY}s")
            _fade_to_target(uart, 0, verbose)
        else:
            # 检测到有人 → 获取环境光建议亮度并渐变开启
            suggested_brightness = _get_ambient_brightness()
            last_suggested_brightness = suggested_brightness  # 记录当前环境光亮度
            print(f"[SR602] 检测到有人 → 渐变开启屏幕（环境光建议亮度：{suggested_brightness}）")
            if verbose:
                print(f"[SR602 DEBUG] 渐变参数：步长{FADE_STEP}，间隔{FADE_DELAY}s")
            _fade_to_target(uart, suggested_brightness, verbose)
        last_presence_state = is_present

# ===独立检测线程=======
def sr602_detect_thread(uart, verbose):
    global current_brightness, last_suggested_brightness
    # 传感器初始化
    try:
        sr602_pin = machine.Pin(SR602_DATA_PIN, machine.Pin.IN, machine.Pin.PULL_DOWN)
        print(f"[SR602] 传感器初始化成功 → 数据引脚：GPIO{SR602_DATA_PIN}")
        if verbose:
            print(f"[SR602 DEBUG] 引脚配置：输入模式+下拉电阻")
    except Exception as e:
        print(f"[SR602 ERROR] 传感器初始化失败：{e}（检查接线/引脚）")
        return
    
    # 开机初始化：屏幕保持关闭状态，等待人体检测
    current_brightness = 0
    boot_cmd = f"dim={current_brightness}".encode('utf-8') + b"\xff\xff\xff"
    uart.write(boot_cmd)
    print(f"[SR602] 开机初始化 → 屏幕亮度：{current_brightness}（等待人体检测）")
    if verbose:
        print(f"[SR602 DEBUG] 开机指令：{boot_cmd} | 检测间隔：{DETECT_INTERVAL}s")
    
    # 初始化环境光亮度记录
    last_suggested_brightness = _get_ambient_brightness()
    
    # 循环检测
    print(f"[SR602] 开始人体检测 → 检测间隔：{DETECT_INTERVAL}s")
    while True:
        is_human_present = _detect_human(sr602_pin)
        _control_screen_brightness(uart, is_human_present, verbose)
        
        # 如果当前有人，检查环境光变化
        if is_human_present:
            _check_and_adjust_ambient_light(uart, verbose)
        
        utime.sleep(DETECT_INTERVAL)

# ===对外启动接口=======
def start_sr602_detect(uart, verbose):
    if not uart:
        print(f"[SR602 ERROR] 串口未初始化，无法启动线程")
        return
    _thread.start_new_thread(sr602_detect_thread, (uart, verbose))