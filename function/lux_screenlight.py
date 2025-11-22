# ===lux_sensor环境光传感器模块（仅计算建议亮度）=======
import machine
import time
import config

# ===全局状态变量=======
current_adc_value = 0

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
        
        time.sleep(config.LUX_SENSOR_READ_INTERVAL)