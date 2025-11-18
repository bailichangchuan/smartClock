# ===导入依赖模块=======
# 网络通信模块：提供Socket接口，用于发送HTTP请求（天气API调用）
import usocket as socket
# JSON解析模块：用于解析天气API返回的JSON格式数据
import ujson as json
# 时间工具模块：提供毫秒级延时（异常处理中防抖）
import utime
# 配置文件导入：天气API域名和路径（统一管理，便于修改）
from config import API_DOMAIN, API_PATH
# 串口屏推送工具：封装串口屏数据上传逻辑（推送天气数据到指定控件）
from util import sent_to_screen

# ===模块配置与全局缓存=======
# DEBUG日志控制开关：当前为模块级开关，建议后续与main.py全局VERBOSE对齐（保持原逻辑不修改）
# 作用：控制API请求/响应的DEBUG日志输出，True启用，False关闭
VERBOSE = False

# 天气数据缓存：记录上一次推送至串口屏的数据（避免重复推送，减少串口通信量）
last_city = None          # 上一次推送的城市名称
last_weather = None       # 上一次推送的天气状况（如“晴”“阴”）
last_temperature = None   # 上一次推送的温度（含单位，如“25℃”）

# ===辅助函数：天气API HTTP GET请求=======
def weather_get(domain, path, timeout=10):
    """
    向天气API发送HTTP GET请求，获取原始响应数据
    :param domain: API域名（如config中配置的API_DOMAIN）
    :param path: API请求路径（如config中配置的API_PATH）
    :param timeout: 网络请求超时时间（单位：秒，默认10秒）
    :return: API响应体（JSON字符串）/ None（请求失败/响应格式错误）
    核心逻辑：
    1. 创建TCP Socket实例，设置超时时间
    2. 连接API服务器（80端口，HTTP协议默认端口）
    3. 构造标准HTTP GET请求头（指定Host、Connection、Accept等字段）
    4. 发送请求并接收响应数据（分段接收，拼接完整响应）
    5. 关闭Socket连接，解析响应头和响应体
    6. 校验响应状态码（仅200 OK时返回响应体，其他情况返回None）
    7. 异常处理：捕获网络异常、请求异常，输出错误信息
    """
    try:
        # 创建TCP Socket实例（默认AF_INET，SOCK_STREAM）
        sock = socket.socket()
        # 设置Socket超时时间（避免网络阻塞导致程序卡死）
        sock.settimeout(timeout)
        # 连接API服务器（域名+80端口，HTTP协议标准）
        sock.connect((domain, 80))
        
        # 构造HTTP GET请求头（符合HTTP 1.1协议规范）
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {domain}\r\n"
            "Connection: close\r\n"
            "Accept: application/json,*/*\r\n\r\n"
        )
        # DEBUG日志：仅VERBOSE=True时输出发送的请求内容
        if VERBOSE:
            print("天气API发送请求：\n", request)
        
        # 发送请求：编码为UTF-8字节串后发送
        sock.send(request.encode("utf-8"))
        
        # 接收响应：分段读取（每次1024字节），拼接完整响应数据
        response_data = b""
        while data := sock.recv(1024):
            response_data += data
        # 关闭Socket连接，释放网络资源
        sock.close()
        
        # 响应数据解码：UTF-8格式，忽略无法解码的字符（避免解析失败）
        response_str = response_data.decode("utf-8", "ignore")
        # 校验响应格式：必须包含“\r\n\r\n”（响应头与响应体分隔符）
        if "\r\n\r\n" not in response_str:
            print("天气API响应格式错误：未找到响应头与响应体分隔符")
            return None
        
        # 拆分响应头和响应体（仅拆分一次，避免多分隔符干扰）
        headers, body = response_str.split("\r\n\r\n", 1)
        # DEBUG日志：仅VERBOSE=True时输出响应头和前300字节响应体（避免日志过长）
        if VERBOSE:
            print("天气API响应头：", headers)
            print("天气API响应体（前300字节）：", body[:300])
        
        # 校验响应状态码：仅“HTTP/1.1 200 OK”表示请求成功
        if "HTTP/1.1 200 OK" in headers:
            if VERBOSE:
                print("天气API请求成功！")
            return body  # 返回响应体（JSON字符串）
        else:
            # 提取状态码（响应头第一行第二个字段），输出错误信息
            status_code = headers.split()[1]
            print(f"天气API请求失败，状态码：{status_code}")
            return None
    
    # 捕获网络异常（如超时、连接失败等）
    except OSError as e:
        print(f"天气API网络异常：{type(e).__name__} -> {e}")
    # 捕获其他通用异常（如编码错误、数据接收异常等）
    except Exception as e:
        print(f"天气API HTTP请求错误：{type(e).__name__} -> {e}")
    # 所有异常情况下返回None
    return None

# ===核心函数：按IP定位获取天气并推送至串口屏=======
def get_weather_by_ip(uart, force=False):
    """
    按IP自动定位获取实时天气，推送至串口屏指定控件（t3=城市、t4=天气、t5=温度）
    :param uart: 串口屏专用UART实例（main.py中的串口2，用于数据推送）
    :param force: 强制更新标识（True=忽略数据变化检测，强制推送；False=仅数据变化时推送）
    :return: 无返回值（成功推送至串口屏，失败输出错误信息）
    核心逻辑：
    1. 调用weather_get获取API响应（JSON字符串）
    2. 无响应处理：force=True时用缓存推送，否则返回
    3. JSON解析：提取城市、天气状况、温度、最后更新时间
    4. 控制台打印天气信息（必显，便于用户查看）
    5. 串口屏推送：按控件映射推送，仅数据变化或force=True时执行
    6. 异常处理：JSON解析失败、字段缺失、通用异常，分别处理并推送占位符（force=True时）
    """
    # 引用模块级全局缓存变量（记录上一次推送数据）
    global last_city, last_weather, last_temperature
    try:
        # 调用API请求函数，获取JSON格式响应体
        json_str = weather_get(API_DOMAIN, API_PATH)
        if not json_str:  # API无响应（返回None）
            # 强制更新时：若有缓存数据，用缓存推送至串口屏
            if force and last_city is not None:
                print("强制更新天气（API无响应，使用缓存数据）")
                sent_to_screen.upload(uart, last_city, control_name="t3", property_name="txt")
                sent_to_screen.upload(uart, last_weather, control_name="t4", property_name="txt")
                sent_to_screen.upload(uart, last_temperature, control_name="t5", property_name="txt")
            # 非强制更新或无缓存，直接返回
            return
        
        # 解析JSON响应体：转换为字典格式，提取关键字段
        weather_data = json.loads(json_str)
        result = weather_data["results"][0]  # 第一个结果集（IP定位对应的城市天气）
        current_city = result["location"]["name"]  # 城市名称（如“香港”）
        now = result["now"]  # 当前天气数据
        current_weather = now["text"]  # 天气状况（如“晴”“多云”）
        current_temperature = f"{now['temperature']}℃"  # 温度（拼接单位，如“25℃”）
        last_update = result["last_update"].split('+')[0]  # 最后更新时间（去除时区信息）
        
        # 控制台打印格式化天气信息（必显，直观展示查询结果）
        weather_info = (
            "\n==================================\n"
            f"  城市：{current_city}\n"
            f"  天气：{current_weather}\n"
            f"  温度：{current_temperature}\n"
            f" 最后更新：{last_update}\n"
            "==================================\n"
        )
        print(weather_info)
        
        # 推送1：城市名称 → 串口屏控件t3（仅数据变化或强制更新时推送）
        if force or current_city != last_city:
            sent_to_screen.upload(uart, current_city, control_name="t3", property_name="txt")
            last_city = current_city  # 更新缓存，避免重复推送
        
        # 推送2：天气状况 → 串口屏控件t4（仅数据变化或强制更新时推送）
        if force or current_weather != last_weather:
            sent_to_screen.upload(uart, current_weather, control_name="t4", property_name="txt")
            last_weather = current_weather  # 更新缓存
        
        # 推送3：温度 → 串口屏控件t5（仅数据变化或强制更新时推送）
        if force or current_temperature != last_temperature:
            sent_to_screen.upload(uart, current_temperature, control_name="t5", property_name="txt")
            last_temperature = current_temperature  # 更新缓存
    
    # 异常1：JSON解析失败（如响应体格式错误、非JSON字符串）
    except ValueError as e:
        print(f"天气JSON解析失败：{e} | 响应片段：{json_str[:50]}")
        # 强制更新时：用缓存或占位符推送
        if force:
            if last_city is not None:
                # 有缓存：推送缓存数据
                sent_to_screen.upload(uart, last_city, control_name="t3", property_name="txt")
                sent_to_screen.upload(uart, last_weather, control_name="t4", property_name="txt")
                sent_to_screen.upload(uart, last_temperature, control_name="t5", property_name="txt")
            else:
                # 无缓存：推送占位符（“未知”“--℃”）
                sent_to_screen.upload(uart, "未知", control_name="t3", property_name="txt")
                sent_to_screen.upload(uart, "未知", control_name="t4", property_name="txt")
                sent_to_screen.upload(uart, "--℃", control_name="t5", property_name="txt")
    
    # 异常2：数据字段缺失（如API响应结构变化，缺少预期字段）
    except KeyError as e:
        print(f"天气数据字段缺失：{e}")
        # 强制更新或缓存与占位符不一致时，推送占位符
        if force or "未知" != last_city:
            sent_to_screen.upload(uart, "未知", control_name="t3", property_name="txt")
            last_city = "未知"  # 更新缓存为占位符
        if force or "未知" != last_weather:
            sent_to_screen.upload(uart, "未知", control_name="t4", property_name="txt")
            last_weather = "未知"  # 更新缓存
        if force or "--℃" != last_temperature:
            sent_to_screen.upload(uart, "--℃", control_name="t5", property_name="txt")
            last_temperature = "--℃"  # 更新缓存
        utime.sleep_ms(50)  # 防抖延时，避免重复触发
    
    # 异常3：通用异常（如串口通信失败、其他未捕获错误）
    except Exception as e:
        print(f"天气查询异常：{type(e).__name__} -> {e}")
        # 强制更新时：推送占位符
        if force:
            sent_to_screen.upload(uart, "未知", control_name="t3", property_name="txt")
            sent_to_screen.upload(uart, "未知", control_name="t4", property_name="txt")
            sent_to_screen.upload(uart, "--℃", control_name="t5", property_name="txt")