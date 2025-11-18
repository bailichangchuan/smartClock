import usocket as socket
import ujson as json
import utime
from config import API_DOMAIN, API_PATH
from ui import sent_to_screen
VERBOSE = False

# 存储上次天气信息 用于判断是否需要更新
last_city = None
last_weather = None
last_temperature = None

def weather_get(domain, path, timeout=10):
    """天气API GET请求"""
    try:
        sock = socket.socket()
        sock.settimeout(timeout)
        sock.connect((domain, 80))
        
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {domain}\r\n"
            "Connection: close\r\n"
            "Accept: application/json,*/*\r\n\r\n"
        )
        if VERBOSE:
            print("发送请求：\n", request)
        
        sock.send(request.encode("utf-8"))
        
        response_data = b""
        while data := sock.recv(1024):
            response_data += data
        sock.close()
        
        response_str = response_data.decode("utf-8", "ignore")
        if "\r\n\r\n" not in response_str:
            print("响应格式错误")
            return None
        
        headers, body = response_str.split("\r\n\r\n", 1)
        if VERBOSE:
            print("响应头：", headers)
            print("响应体：", body[:300])
        
        if "HTTP/1.1 200 OK" in headers:
            if VERBOSE:
                print("API请求成功！")
            return body
        else:
            status_code = headers.split()[1]
            print(f"API请求失败，状态码：{status_code}")
            return None
    
    except OSError as e:
        print(f"网络异常：{type(e).__name__} -> {e}")
    except Exception as e:
        print(f"HTTP请求错误：{type(e).__name__} -> {e}")
    return None

def get_weather_by_ip(uart, force=False):  # 核心：新增force参数，默认False（原有逻辑）
    """根据IP自动获取所在地实时天气 发送到串口屏t3/t4/t5；force=True时强制更新（忽略变化检测）"""
    global last_city, last_weather, last_temperature
    try:
        json_str = weather_get(API_DOMAIN, API_PATH)
        if not json_str:
            # 无API响应时，若强制更新且有缓存，用缓存发送
            if force and last_city is not None:
                print("强制更新天气（无API响应，使用缓存）")
                sent_to_screen.upload(uart, last_city, control_name="t3", property_name="txt")
                sent_to_screen.upload(uart, last_weather, control_name="t4", property_name="txt")
                sent_to_screen.upload(uart, last_temperature, control_name="t5", property_name="txt")
            return
        
        # 解析天气JSON数据
        weather_data = json.loads(json_str)
        result = weather_data["results"][0]
        current_city = result["location"]["name"]
        now = result["now"]
        current_weather = now["text"]
        current_temperature = f"{now['temperature']}℃"
        last_update = result["last_update"].split('+')[0]
        
        # 格式化输出天气信息
        weather_info = (
            "\n==================================\n"
            f"  城市：{current_city}\n"
            f"  天气：{current_weather}\n"
            f"  温度：{current_temperature}\n"
            f" 最后更新：{last_update}\n"
            "==================================\n"
        )
        print(weather_info)
        

        
        # ===城市 t3=== 强制更新或数据变化时发送
        if force or current_city != last_city:
            sent_to_screen.upload(uart, current_city, control_name="t3", property_name="txt")  # 传入uart
            last_city = current_city
      
        
        # ===天气 t4=== 强制更新或数据变化时发送
        if force or current_weather != last_weather:
            sent_to_screen.upload(uart, current_weather, control_name="t4", property_name="txt")  # 传入uart
            last_weather = current_weather
          
        
        # ===温度 t5=== 强制更新或数据变化时发送
        if force or current_temperature != last_temperature:
            sent_to_screen.upload(uart, current_temperature, control_name="t5", property_name="txt")  # 传入uart
            last_temperature = current_temperature
    
    except ValueError as e:
        print(f"JSON解析失败：{e} | 响应片段：{json_str[:50]}")
        # 解析失败时，若强制更新则用缓存/占位符发送
        if force:
            if last_city is not None:
                sent_to_screen.upload(uart, last_city, control_name="t3", property_name="txt")
                sent_to_screen.upload(uart, last_weather, control_name="t4", property_name="txt")
                sent_to_screen.upload(uart, last_temperature, control_name="t5", property_name="txt")
            else:
                sent_to_screen.upload(uart, "未知", control_name="t3", property_name="txt")
                sent_to_screen.upload(uart, "未知", control_name="t4", property_name="txt")
                sent_to_screen.upload(uart, "--℃", control_name="t5", property_name="txt")
    except KeyError as e:
        print(f"数据字段缺失：{e}")
        # 字段缺失时，强制更新或数据不一致时发送占位符
        if force or "未知" != last_city:
            sent_to_screen.upload(uart, "未知", control_name="t3", property_name="txt")  # 传入uart
            last_city = "未知"
        if force or "未知" != last_weather:
            sent_to_screen.upload(uart, "未知", control_name="t4", property_name="txt")  # 传入uart
            last_weather = "未知"
        if force or "--℃" != last_temperature:
            sent_to_screen.upload(uart, "--℃", control_name="t5", property_name="txt")  # 传入uart
            last_temperature = "--℃"
        utime.sleep_ms(50)
    except Exception as e:
        print(f"天气查询异常：{type(e).__name__} -> {e}")
        # 通用异常时，若强制更新则发送占位符
        if force:
            sent_to_screen.upload(uart, "未知", control_name="t3", property_name="txt")
            sent_to_screen.upload(uart, "未知", control_name="t4", property_name="txt")
            sent_to_screen.upload(uart, "--℃", control_name="t5", property_name="txt")