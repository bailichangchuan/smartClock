import usocket as socket
import ujson as json
from config import API_DOMAIN, API_PATH
VERBOSE = False

def http_get_utf8(domain, path, timeout=10):
    """UTF-8编码HTTP请求"""
    try:
        # 解析域名（纯位置参数）
        addr_info = socket.getaddrinfo(domain, 80)
        ip = addr_info[0][-1][0]
        if VERBOSE:
            print("解析域名 " + domain + " → IP: " + ip)
        
        # 创建socket并连接（纯位置参数）
        sock = socket.socket()
        sock.settimeout(timeout)
        sock.connect((ip, 80))
        
        # 发送HTTP请求（精简必要头，无多余配置）
        request = "GET " + path + " HTTP/1.1\r\n"
        request += "Host: " + domain + "\r\n"
        request += "Connection: close\r\n"
        request += "Accept: application/json,*/*\r\n"
        request += "Accept-Charset: utf-8\r\n"
        request += "\r\n"  # 必须保留的请求结束符
        
        if VERBOSE:
            print("发送请求：")
            print(request)
        
        sock.send(request.encode("utf-8"))
        
        # 接收响应
        response_data = b""
        while True:
            data = sock.recv(1024)
            if not data:
                break
            response_data += data
        sock.close()
        
        response_str = response_data.decode("utf-8", "ignore")  
        if "\r\n\r\n" in response_str:
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
                print("API请求失败，状态码：" + status_code)
                return None
        else:
            print("响应格式错误")
            return None
    
    except OSError as e:
        print("网络异常：", type(e).__name__, "->", e)
    except Exception as e:
        print("HTTP请求错误：", type(e).__name__, "->", e)
    return None

def get_hongkong_weather():
    """获取并打印香港实时天气（全中文显示）"""
    try:
        json_str = http_get_utf8(API_DOMAIN, API_PATH)
        if not json_str:
            return
        
        # 解析JSON天气数据
        weather_data = json.loads(json_str)
        result = weather_data["results"][0]
        location = result["location"]["name"]  # 城市名（中文）
        now = result["now"]
        weather = now["text"]  # 天气状况（中文）
        temperature = now["temperature"]  # 温度
        last_update = result["last_update"].split('+')[0]  # 更新时间（去除时区）
        
        # 格式化中文输出（带分隔线，清晰易读）
        weather_info = (
            "\n==================================\n"
            "  城市：" + location + "\n"
            "  天气：" + weather + "\n"
            "  温度：" + temperature + "℃\n"  # 恢复℃符号，screen支持
            " 最后更新：" + last_update + "\n"
            "==================================\n"
        )
        print(weather_info)
    
    except ValueError as e:
        print(" JSON解析失败：", e, "| 响应片段：", json_str[:50])
    except KeyError as e:
        print(" 数据字段缺失：", e, "（检查API Key是否有效）")
    except Exception as e:
        print(" 天气查询异常：", type(e).__name__, "->", e)
