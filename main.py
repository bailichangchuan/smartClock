import network
import usocket as socket
import ujson as json
import time

# -------------------------- 配置参数--------------------------
WIFI_SSID = "l888"       # 替换为你的WiFi SSID
WIFI_PWD = "12345678"        # 替换为你的WiFi密码
SENIVERSE_KEY = "xxxxxx"  # 替换为你的知心天气API Key
LOCATION = "101320101"  # 香港固定城市ID
# 知心天气API的域名和路径
API_DOMAIN = "api.seniverse.com"
API_PATH = f"/v3/weather/now.json?key={SENIVERSE_KEY}&location={LOCATION}&language=zh-Hans&unit=c"
REFRESH_INTERVAL = 10  # 每10秒刷新（无需修改）

def connect_wifi():
    """连接WiFi，带中文提示"""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if not wlan.isconnected():
        print("正在连接 WiFi：", WIFI_SSID)
        wlan.connect(WIFI_SSID, WIFI_PWD)
        
        # 10秒超时等待
        timeout = 10
        while not wlan.isconnected() and timeout > 0:
            print("连接中... 剩余", timeout, "秒")
            time.sleep(1)
            timeout -= 1
    
    if wlan.isconnected():
        print(" WiFi连接成功！IP地址：", wlan.ifconfig()[0])
        return True
    else:
        print(" WiFi连接失败（仅支持2.4G，检查密码是否正确）")
        return False

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

def main():
    """主函数：启动程序并循环查询"""
    # 启动提示（中文）
    print("==================================")
    print(" 香港实时天气查询程序 - 启动成功")
    print("==================================")
    
    # 先连接WiFi，失败则退出
    if not connect_wifi():
        return
    
    # 循环查询天气
    print("\n 开始每", REFRESH_INTERVAL, "秒获取一次天气...\n")
    while True:
        get_hongkong_weather()
        time.sleep(REFRESH_INTERVAL)

if __name__ == "__main__":
    main()