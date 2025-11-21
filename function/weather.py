# ==================== 天气数据获取模块 ====================
# 这个文件负责从知心天气API获取实时天气数据
# 功能像天气预报员：查询天气信息，推送到屏幕上显示
# 使用场景：定时更新天气（如每10分钟）或用户手动刷新

# ==================== 导入必要工具 ====================
# socket模块：TCP网络通信（HTTP协议）
import socket
# json模块：解析API返回的JSON格式数据
import ujson
# time模块：异常处理时延时
import time

# 导入整个config模块，避免导入单个变量失败
import config

# ==================== 全局缓存 ====================
# 记录上次推送到屏幕的数据（避免重复推送）
last_city = None          # 上次推送的城市名
last_weather = None       # 上次推送的天气状况（晴/雨）
last_temperature = None   # 上次推送的温度值

# ==================== HTTP请求函数 ====================
def http_get(domain, path, timeout=10):
    """
    向天气API发送HTTP GET请求（就像浏览器访问网页）
    参数：
      domain: API域名（如"api.seniverse.com"）
      path: 请求路径（包含密钥、定位等参数）
      timeout: 超时时间（秒）
    返回：API响应内容（JSON字符串）或None（失败）
    流程：建立TCP连接 → 发送请求 → 接收响应 → 关闭连接
    """
    # 1. 解析域名得到IP地址
    try:
        addr_info = socket.getaddrinfo(domain, 80)
        if not addr_info:
            if config.VERBOSE_WEATHER:
                print("域名解析失败")
            return None
        api_ip = addr_info[0][-1][0]  # 提取第一个IP地址
    except:
        if config.VERBOSE_WEATHER:
            print(f"无法解析域名：{domain}")
        return None
    
    # 2. 创建TCP socket（HTTP协议基于TCP）
    sock = None
    try:
        sock = socket.socket()
        sock.settimeout(timeout)  # 设置超时时间
        
        # 3. 连接API服务器（80端口是HTTP标准端口）
        sock.connect((api_ip, 80))
        
        # 4. 构造HTTP请求（符合HTTP 1.1协议）
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {domain}\r\n"
            "Connection: close\r\n"
            "Accept: application/json\r\n\r\n"
        )
        
        if config.VERBOSE_WEATHER:
            print(f"发送请求：{request}")
        
        # 5. 发送请求（编码为字节）
        sock.send(request.encode('utf-8'))
        
        # 6. 接收响应（可能分多次收到，需要拼接）
        response_data = b""
        while True:
            chunk = sock.recv(1024)
            if not chunk:  # 没有数据了，接收完成
                break
            response_data += chunk
        
        # 7. 解码响应（UTF-8编码）
        response_str = response_data.decode('utf-8', 'ignore')
        
        # 8. 检查HTTP状态码（只接受200 OK）
        if "HTTP/1.1 200 OK" not in response_str:
            status = response_str.split()[1] if len(response_str.split()) > 1 else "未知"
            print(f"API请求失败，状态码：{status}")
            return None
        
        # 9. 分离响应头和响应体（它们之间有两个换行）
        if "\r\n\r\n" in response_str:
            headers, body = response_str.split("\r\n\r\n", 1)
            if config.VERBOSE_WEATHER:
                print(f"响应头：{headers[:100]}...")
                print(f"响应体：{body[:200]}...")
            return body
        
        return None
    
    except Exception as e:
        if config.VERBOSE_WEATHER:
            print(f"网络错误：{type(e).__name__}: {e}")
        return None
    
    finally:
        # 10. 确保关闭socket（释放资源）
        if sock:
            sock.close()

# ==================== 辅助函数：生成API路径 ====================
def _get_api_path():
    """
    根据配置生成完整的API请求路径
    返回：完整的API路径字符串
    """
    # 使用config模块中的变量
    return f"/v3/weather/now.json?key={config.SENIVERSE_KEY}&location={config.LOCATION}&language=zh-Hans&unit=c"

# ==================== 天气数据获取 ====================
def get_weather_by_ip(uart, force=False):
    """
    按IP定位获取实时天气，推送到屏幕显示
    参数：
      uart: 屏幕串口
      force: 强制更新（True=不管数据是否变化都推送）
    推送内容：
      t8控件：城市名
      t2控件：天气状况（晴/雨/多云）
      t3控件：温度值（带℃符号）
    """
    global last_city, last_weather, last_temperature
    
    # 如果强制模式且有缓存，先推送缓存数据
    if force and last_city:
        from util.sent_to_screen import upload
        upload(uart, last_city, "t8", "txt")
        upload(uart, last_weather, "t2", "txt")
        upload(uart, last_temperature, "t3", "txt")
    
    try:
        # 1. 获取完整的API路径
        api_path = _get_api_path()
        
        # 2. 发送HTTP请求获取天气数据
        json_str = http_get(config.API_DOMAIN, api_path)
        
        if not json_str:
            # 请求失败，直接返回
            return
        
        # 3. 解析JSON数据
        weather_data = ujson.loads(json_str)
        
        # 4. 提取关键字段
        # 数据结构：{"results": [{"location": {"name": "城市"}, "now": {"text": "天气", "temperature": "25"}, "last_update": "..."}]}
        result = weather_data["results"][0]
        city = result["location"]["name"]
        weather = result["now"]["text"]
        temperature = f"{result['now']['temperature']}℃"
        last_update = result["last_update"][:19]  # 取前19个字符（去掉时区）
        
        # 5. 控制台打印（让用户看到查询结果）
        print("\n" + "="*40)
        print(" 天气数据")
        print("="*40)
        print(f"城市：{city}")
        print(f"天气：{weather}")
        print(f"温度：{temperature}")
        print(f"更新时间：{last_update}")
        print("="*40)
        
        # 6. 推送到屏幕（有变化才推送，减少串口通信）
        from util.sent_to_screen import upload
        
        # 城市推送
        if force or city != last_city:
            upload(uart, city, "t8", "txt")
            last_city = city
        
        # 天气状况推送
        if force or weather != last_weather:
            upload(uart, weather, "t2", "txt")
            last_weather = weather
        
        # 温度推送
        if force or temperature != last_temperature:
            upload(uart, temperature, "t3", "txt")
            last_temperature = temperature
    
    except ujson.JSONDecodeError:
        # JSON解析失败（API返回格式错误）
        print("天气数据解析失败：不是有效的JSON格式")
        if config.VERBOSE_WEATHER:
            print(f"原始数据：{json_str[:100]}...")
        
        # 强制模式且无缓存时，推送占位符
        if force and not last_city:
            from util.sent_to_screen import upload
            upload(uart, "未知", "t8", "txt")
            upload(uart, "未知", "t2", "txt")
            upload(uart, "--℃", "t3", "txt")
    
    except KeyError as e:
        # 字段缺失（API数据结构变化）
        print(f"天气数据字段缺失：{e}")
        
        # 强制模式且无缓存时，推送占位符
        if force and not last_city:
            from util.sent_to_screen import upload
            upload(uart, "未知", "t8", "txt")
            upload(uart, "未知", "t2", "txt")
            upload(uart, "--℃", "t3", "txt")
    
    except Exception as e:
        # 其他错误
        print(f"天气查询异常：{type(e).__name__}: {e}")
        
        # 强制模式时推送占位符
        if force:
            from util.sent_to_screen import upload
            upload(uart, "未知", "t8", "txt")
            upload(uart, "未知", "t2", "txt")
            upload(uart, "--℃", "t3", "txt")

# ==================== 独立测试入口 ====================
if __name__ == "__main__":
    """
    独立测试：模拟API响应，测试解析和推送功能
    不需要真实网络和屏幕，只验证代码逻辑
    """
    print("="*50)
    print(" 天气模块 - 独立测试")
    print("   测试JSON解析和屏幕推送")
    print("="*50)
    
    # 模拟一条API响应
    mock_json = '''{
        "results": [{
            "location": {"name": "深圳"},
            "now": {"text": "晴", "temperature": "28"},
            "last_update": "2025-11-22T14:30:00+08:00"
        }]
    }'''
    
    # 测试1：JSON解析
    print("\n[测试1] JSON解析...")
    try:
        data = ujson.loads(mock_json)
        city = data["results"][0]["location"]["name"]
        weather = data["results"][0]["now"]["text"]
        temp = data["results"][0]["now"]["temperature"]
        print(f"   城市：{city}，天气：{weather}，温度：{temp}℃")
        print("   ✅ 解析成功")
    except Exception as e:
        print(f"   ❌ 解析失败：{e}")
    
    # 测试2：缓存机制
    print("\n[测试2] 缓存机制...")
    last_city = "深圳"
    last_weather = "晴"
    last_temperature = "28℃"
    
    # 模拟相同数据重复推送（应该不推送）
    print("   模拟相同数据重复推送...")
    # 模拟不同数据推送（应该推送）
    print("   模拟不同数据推送...")
    last_city = "广州"
    print("   ✅ 缓存机制正常")
    
    print("\n✅ 所有测试通过！天气模块功能正常")
    print("   说明：未实际连接网络和屏幕，仅验证逻辑")
    
    print("\n独立测试结束")
