import usocket
import utime
import ussl
import struct
import network

# Utility functions for network operations
# NTP time retrieval 获取NTP时间
def get_ntp_time(host="pool.ntp.org", port=123, timeout=5)::
    NTP_DELTA = 2208988800
    msg = bytearray(48)
    msg[0] = 0x1B
    addr = usocket.getaddrinfo(host, port)[0][-1]
    s = usocket.socket(usocket.AF_INET, usocket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(msg, addr)
        msg = s.recv(48)
    except:
        s.close()
        return None
    s.close()
    val = struct.unpack("!I", msg[40:44])[0]
    return val - NTP_DELTA
# HTTP and HTTPS request functions over sockets 通过套接字的HTTP和HTTPS请求函数
# GET request over HTTP
def get_https(url, timeout=5):
    _, _, host, path = url.split("/", 3)
    addr = usocket.getaddrinfo(host, 443)[0][-1]
    s = usocket.socket()
    s.settimeout(timeout)
    s.connect(addr)
    s = ussl.wrap_socket(s, server_hostname=host)
    request = "GET /{} HTTP/1.0\r\nHost: {}\r\n\r\n".format(path, host)
    s.write(request.encode())
    response = b""
    while True:
        data = s.read(512)
        if not data:
            break
        response += data
    s.close()
    header_end = response.find(b"\r\n\r\n") + 4
    return response[header_end:]
# POST request over HTTPS 发送HTTPS请求
def post_https(url, data, timeout=5):
    _, _, host, path = url.split("/", 3)
    addr = usocket.getaddrinfo(host, 443)[0][-1]
    s = usocket.socket()
    s.settimeout(timeout)
    s.connect(addr)
    s = ussl.wrap_socket(s, server_hostname=host)
    request = "POST /{} HTTP/1.0\r\nHost: {}\r\nContent-Length: {}\r\nContent-Type: application/x-www-form-urlencoded\r\n\r\n{}".format(path, host, len(data), data)
    s.write(request.encode())
    response = b""
    while True:
        chunk = s.read(512)
        if not chunk:
            break
        response += chunk
    s.close()
    header_end = response.find(b"\r\n\r\n") + 4
    return response[header_end:]
# Network utility functions
def is_connected(host="127.0.0.1", port=80, timeout=3):
    try:
        addr = usocket.getaddrinfo(host, port)[0][-1]
        s = usocket.socket()
        s.settimeout(timeout)
        s.connect(addr)
        s.close()
        return True
    except:
        return False
# get local IP address
def get_local_ip():
    import network
    wlan = network.WLAN(network.STA_IF)
    if wlan.isconnected():
        return wlan.ifconfig()[0]
    return None
# get MAC address
def get_mac_address():
    import network
    wlan = network.WLAN(network.STA_IF)
    mac = wlan.config('mac')
    return ':'.join('{:02x}'.format(b) for b in mac)
# resolve hostname to IP address
def resolve_hostname(hostname, timeout=5):
    try:
        addr_info = usocket.getaddrinfo(hostname, 80, 0, usocket.SOCK_STREAM)
        return addr_info[0][4][0]
    except:
        return None

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