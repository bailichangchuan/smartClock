# ===TEMT6000环境光传感器模块（仅计算建议亮度）=======
import machine
import utime
import _thread

from config import (
    TEMT6000_ADC_PIN,
    TEMT6000_READ_INTERVAL,
    TEMT6000_MIN_ADC,
    TEMT6000_MAX_ADC,
    TEMT6000_MIN_BRIGHTNESS,
    TEMT6000_MAX_BRIGHTNESS,
    TEMT6000_SMOOTHING_FACTOR,
)

# ===全局状态变量=======
current_adc_value = 0
suggested_brightness = 0
adc = None

def _map_adc_to_brightness(adc_value):
    """
    直接将ADC值映射到屏幕亮度
    """
    # 限制ADC值在配置范围内
    adc_value = max(TEMT6000_MIN_ADC, min(adc_value, TEMT6000_MAX_ADC))
    
    # 线性映射
    normalized = (adc_value - TEMT6000_MIN_ADC) / (TEMT6000_MAX_ADC - TEMT6000_MIN_ADC)
    
    # 确保在0-1范围内
    normalized = max(0, min(1, normalized))
    
    # 线性映射到亮度范围
    brightness = TEMT6000_MIN_BRIGHTNESS + normalized * (TEMT6000_MAX_BRIGHTNESS - TEMT6000_MIN_BRIGHTNESS)
    
    return int(brightness)

def _smooth_value(new_value, old_value):
    """应用指数平滑滤波"""
    return (new_value * TEMT6000_SMOOTHING_FACTOR + 
            old_value * (1 - TEMT6000_SMOOTHING_FACTOR))

def temt6000_detect_thread(verbose):
    """TEMT6000环境光检测独立线程"""
    global current_adc_value, suggested_brightness, adc
    
    # ADC初始化
    try:
        adc = machine.ADC(machine.Pin(TEMT6000_ADC_PIN))
        adc.atten(machine.ADC.ATTN_11DB)
        adc.width(machine.ADC.WIDTH_12BIT)
        
        print(f"[TEMT6000] 传感器初始化成功 → ADC引脚：GPIO{TEMT6000_ADC_PIN}")
        print(f"[TEMT6000] ADC映射范围: {TEMT6000_MIN_ADC}-{TEMT6000_MAX_ADC} → {TEMT6000_MIN_BRIGHTNESS}-{TEMT6000_MAX_BRIGHTNESS}%")
    except Exception as e:
        print(f"[TEMT6000 ERROR] 传感器初始化失败：{e}")
        return
    
    # 初始建议亮度计算
    suggested_brightness = (TEMT6000_MIN_BRIGHTNESS + TEMT6000_MAX_BRIGHTNESS) // 2
    print(f"[TEMT6000] 环境光检测启动 → 初始建议亮度：{suggested_brightness}%")
    
    # 主循环
    print(f"[TEMT6000] 开始环境光检测 → 检测间隔：{TEMT6000_READ_INTERVAL}s")
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
                print(f"[TEMT6000] 环境光变化 → 建议亮度: {old_brightness}% → {suggested_brightness}% (ADC: {current_adc_value})")
            
            # 定期输出调试信息
            cycle_count += 1
            if cycle_count % 5 == 0:  # 每5次循环输出一次
                normalized = (current_adc_value - TEMT6000_MIN_ADC) / (TEMT6000_MAX_ADC - TEMT6000_MIN_ADC)
                print(f"[TEMT6000 STATUS] ADC:{current_adc_value} Normalized:{normalized:.2f} Brightness:{suggested_brightness}%")
            
        except Exception as e:
            print(f"[TEMT6000 ERROR] 检测过程中出错：{e}")
        
        utime.sleep(TEMT6000_READ_INTERVAL)

def start_temt6000_detect(verbose):
    """启动TEMT6000环境光检测线程"""
    _thread.start_new_thread(temt6000_detect_thread, (verbose,))

def get_current_status():
    """获取当前ADC值和建议亮度状态"""
    return {
        'adc_value': current_adc_value,
        'suggested_brightness': suggested_brightness
    }

def get_suggested_brightness():
    """直接获取当前建议亮度"""
    return suggested_brightness