import network
import usocket as socket
import ujson as json
import time
from config import WIFI_SSID, WIFI_PWD, API_DOMAIN, API_PATH, REFRESH_INTERVAL
from util.network import connect_wifi


def http_get_utf8(domain, path, timeout=10):
    """UTF-8编码HTTP请求，获取天气数据"""
    try:
        # 解析域名获取IP
        addr_info = socket.getaddrinfo(domain, 80)
        ip = addr_info[0][-1][0]
        
        # 创建并连接socket
        sock = socket.socket()
        sock.settimeout(timeout)
        sock.connect((ip, 80))
        
        # 发送HTTP请求（UTF-8编码）
        request = f"GET {path} HTTP/1.1\r\n"
        request += f"Host: {domain}\r\n"
        request += "Connection: close\r\n"
        request += "Accept-Charset: utf-8\r\n"
        request += "\r\n"
        sock.send(request.encode("utf-8"))
        
        # 接收响应数据
        response_data = b""
        while True:
            data = sock.recv(1024)
            if not data:
                break
            response_data += data
        sock.close()
        
        # 解析响应（UTF-8解码）
        response_str = response_data.decode("utf-8")
        if "\r\n\r\n" in response_str:
            headers, body = response_str.split("\r\n\r\n", 1)
            # 打印API编码信息（验证UTF-8）
            for line in headers.split("\r\n"):
                if "Content-Type" in line:
                    print(" API编码：", line)
            # 返回响应体（天气数据）
            if "HTTP/1.1 200 OK" in headers:
                return body
            else:
                status_code = headers.split()[1]
                print(" API请求失败，状态码：", status_code)
                return None
        else:
            print(" 响应格式错误，无数据分隔符")
            return None
    
    except OSError as e:
        print(" 网络异常：", type(e).__name__, "->", e)
    except Exception as e:
        print(" HTTP请求错误：", type(e).__name__, "->", e)
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
