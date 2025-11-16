import time
import network
from config import WIFI_SSID, WIFI_PWD

def connect_wifi():
    """连接WiFi，带中文提示"""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if not wlan.isconnected():
        print("正在连接 WiFi：", WIFI_SSID)
        wlan.connect(WIFI_SSID, WIFI_PWD)
        
        # 10秒超时等待
        timeout = 15
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
