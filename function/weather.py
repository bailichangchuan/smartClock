import usocket as socket
import ujson as json
from config import API_DOMAIN, API_PATH
VERBOSE = False

def weather_get(domain, path, timeout=10):
    """天气API GET请求"""
    try:
        # 创建socket并设置超时，直接用域名连接（底层自动DNS解析）
        sock = socket.socket()
        sock.settimeout(timeout)
        sock.connect((domain, 80))
        
        # 构造请求报文
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {domain}\r\n"
            "Connection: close\r\n"
            "Accept: application/json,*/*\r\n\r\n"
        )
        if VERBOSE:
            print("发送请求：\n", request)
        
        # 字符串转字节流发送
        sock.send(request.encode("utf-8"))
        
        # 接收响应数据
        response_data = b""
        while data := sock.recv(1024):
            response_data += data
        sock.close()
        
        # 字节流转字符串，忽略异常字符
        response_str = response_data.decode("utf-8", "ignore")
        if "\r\n\r\n" not in response_str:
            print("响应格式错误")
            return None
        
        # 拆分响应头和响应体
        headers, body = response_str.split("\r\n\r\n", 1)
        if VERBOSE:
            print("响应头：", headers)
            print("响应体：", body[:300])
        
        # 验证响应状态
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

def get_weather_by_ip():
    """根据IP自动获取所在地实时天气"""
    try:
        # 发起天气API请求
        json_str = weather_get(API_DOMAIN, API_PATH)
        if not json_str:
            return
        
        # 解析天气JSON数据
        weather_data = json.loads(json_str)
        result = weather_data["results"][0]
        location = result["location"]["name"]
        now = result["now"]
        weather = now["text"]
        temperature = now["temperature"]
        last_update = result["last_update"].split('+')[0]
        
        # 格式化输出天气信息
        weather_info = (
            "\n==================================\n"
            f"  城市：{location}\n"
            f"  天气：{weather}\n"
            f"  温度：{temperature}℃\n"
            f" 最后更新：{last_update}\n"
            "==================================\n"
        )
        print(weather_info)
    
    except ValueError as e:
        print(f"JSON解析失败：{e} | 响应片段：{json_str[:50]}")
    except KeyError as e:
        print(f"数据字段缺失：{e}")
    except Exception as e:
        print(f"天气查询异常：{type(e).__name__} -> {e}")