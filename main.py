import network
impport util.network as net_util
from functions.weather import get_hongkong_weather
from config import REFRESH_INTERVAL
import usocket as socket
import ujson as json
import time

def main():
    """主函数：启动程序并循环查询"""
    # 启动提示（中文）
    print("==================================")
    print(" 香港实时天气查询程序 - 启动成功")
    print("==================================")
    
    # 先连接WiFi，失败则退出
    if not net_util.connect_wifi():
        return
    
    # 循环查询天气
    print("\n 开始每", REFRESH_INTERVAL, "秒获取一次天气...\n")
    while True:
        get_hongkong_weather()
        time.sleep(REFRESH_INTERVAL)

if __name__ == "__main__":
    main()
