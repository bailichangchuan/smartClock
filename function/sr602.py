# ===SR602人体红外传感器检测模块=======
# 仅修复：1. 正确导入config参数；2. 恢复核心必显日志（解决无输出）；其他逻辑完全不变
import machine
import utime
import _thread

# 【修复点1：确保从config.py正确导入所有必要参数（配置分离后必须）】
from config import (
    SR602_DATA_PIN,
    DEFAULT_SCREEN_BRIGHTNESS,
    FADE_STEP,
    FADE_DELAY,
    DETECT_INTERVAL
)

# ===全局状态变量（完全保留原有）=======
last_presence_state = None
current_brightness = DEFAULT_SCREEN_BRIGHTNESS  # 初始化为config默认亮度

# ===对外接口：修改默认亮度（完全保留原有逻辑）=======
def set_screen_brightness(brightness):
    global DEFAULT_SCREEN_BRIGHTNESS
    brightness = max(0, min(100, int(brightness)))
    DEFAULT_SCREEN_BRIGHTNESS = brightness
    # 【恢复必显日志：解决无输出问题】
    print(f"[SR602] 屏幕默认亮度更新为：{DEFAULT_SCREEN_BRIGHTNESS}")

# ===渐变工具函数（完全保留原有逻辑，不改动）=======
def _fade_in(uart, target_brightness):
    global current_brightness
    while current_brightness < target_brightness:
        current_brightness = min(current_brightness + FADE_STEP, target_brightness)
        cmd = f"dim={current_brightness}".encode('utf-8') + b"\xff\xff\xff"
        uart.write(cmd)
        utime.sleep(FADE_DELAY)

def _fade_out(uart):
    global current_brightness
    while current_brightness > 0:
        current_brightness = max(current_brightness - FADE_STEP, 0)
        cmd = f"dim={current_brightness}".encode('utf-8') + b"\xff\xff\xff"
        uart.write(cmd)
        utime.sleep(FADE_DELAY)

# ===核心检测函数（完全保留原有逻辑）=======
def _detect_human(sensor_pin):
    return sensor_pin.value() == 1

# ===亮度控制函数（仅恢复必显日志，不改动逻辑）=======
def _control_screen_brightness(uart, is_present, verbose):
    global last_presence_state
    if is_present != last_presence_state:
        if not is_present:
            # 【恢复必显日志：状态变化告知】
            print(f"[SR602] 检测到无人 → 渐变关闭屏幕")
            if verbose:
                print(f"[SR602 DEBUG] 渐变参数：步长{FADE_STEP}，间隔{FADE_DELAY}s")
            _fade_out(uart)
        else:
            target_brightness = DEFAULT_SCREEN_BRIGHTNESS
            # 【恢复必显日志：状态变化告知】
            print(f"[SR602] 检测到有人 → 渐变开启屏幕（目标亮度：{target_brightness}）")
            if verbose:
                print(f"[SR602 DEBUG] 渐变参数：步长{FADE_STEP}，间隔{FADE_DELAY}s")
            _fade_in(uart, target_brightness)
        last_presence_state = is_present

# ===独立检测线程（仅恢复必显日志，不改动逻辑）=======
def sr602_detect_thread(uart, verbose):
    global current_brightness
    # 传感器初始化
    try:
        sr602_pin = machine.Pin(SR602_DATA_PIN, machine.Pin.IN, machine.Pin.PULL_DOWN)
        # 【恢复必显日志：初始化状态告知】
        print(f"[SR602] 传感器初始化成功 → 数据引脚：GPIO{SR602_DATA_PIN}")
        if verbose:
            print(f"[SR602 DEBUG] 引脚配置：输入模式+下拉电阻")
    except Exception as e:
        # 【恢复必显日志：错误告知】
        print(f"[SR602 ERROR] 传感器初始化失败：{e}（检查接线/引脚）")
        return
    
    # 开机初始化亮度
    current_brightness = DEFAULT_SCREEN_BRIGHTNESS
    boot_cmd = f"dim={current_brightness}".encode('utf-8') + b"\xff\xff\xff"
    uart.write(boot_cmd)
    # 【恢复必显日志：开机状态告知】
    print(f"[SR602] 开机初始化 → 屏幕亮度：{current_brightness}（默认值）")
    if verbose:
        print(f"[SR602 DEBUG] 开机指令：{boot_cmd} | 检测间隔：{DETECT_INTERVAL}s")
    
    # 循环检测（逻辑完全不变，检测间隔从config导入）
    print(f"[SR602] 开始人体检测 → 检测间隔：{DETECT_INTERVAL}s")
    while True:
        is_human_present = _detect_human(sr602_pin)
        _control_screen_brightness(uart, is_human_present, verbose)
        utime.sleep(DETECT_INTERVAL)

# ===对外启动接口（完全保留原有参数，与main.py调用匹配）=======
def start_sr602_detect(uart, verbose):
    if not uart:
        print(f"[SR602 ERROR] 串口未初始化，无法启动线程")
        return
    _thread.start_new_thread(sr602_detect_thread, (uart, verbose))