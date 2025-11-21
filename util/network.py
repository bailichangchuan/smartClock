# ==================== 网络连接工具 ====================
# 这个文件负责连接WiFi网络，像手机的"WiFi设置"功能
# 功能说明：让设备能上网，才能获取天气和时间
# 使用场景：开机时调用一次，连接路由器

# ==================== 导入必要工具 ====================
# network模块：控制WiFi硬件（STA模式=连接路由器，AP模式=当热点）
import network
# time模块：延时等待，给WiFi连接留出时间
import time

# 从配置导入WiFi账号密码和调试开关
from config import WIFI_SSID, WIFI_PWD, VERBOSE_NETWORK

# ==================== WiFi连接函数 ====================
def connect_wifi():
    """
    连接WiFi路由器（就像手机连WiFi的操作）
    支持2.4G网络，不支持5G
    返回：True=连接成功，False=连接失败
    机制：激活网卡 → 发起连接 → 等待15秒 → 检查是否连上
    """
    # 1. 创建WiFi客户端（STA模式）
    # 就像打开手机的WiFi开关
    wlan = network.WLAN(network.STA_IF)
    
    # 2. 激活WiFi硬件
    wlan.active(True)
    
    # 3. 如果已经连接，直接返回成功
    if wlan.isconnected():
        ip = wlan.ifconfig()[0]
        if VERBOSE_NETWORK:
            print(f"WiFi已连接，IP地址：{ip}")
        return True
    
    # 4. 发起连接（就像手机点击WiFi名称输入密码）
    print(f"正在连接WiFi：{WIFI_SSID}...")
    wlan.connect(WIFI_SSID, WIFI_PWD)
    
    # 5. 等待连接结果（最多等15秒）
    # 就像手机连WiFi时转圈圈的等待过程
    timeout = 15
    while not wlan.isconnected() and timeout > 0:
        if VERBOSE_NETWORK:
            print(f"  连接中... {timeout}秒")
        time.sleep(1)
        timeout -= 1
    
    # 6. 检查连接结果
    if wlan.isconnected():
        # 成功：打印IP地址（就像手机显示已连接）
        ip = wlan.ifconfig()[0]
        print(f"✅ WiFi连接成功！设备IP：{ip}")
        return True
    else:
        # 失败：给出排查建议（就像手机提示密码错误）
        print("❌ WiFi连接失败！请检查：")
        print("   1. 密码是否正确")
        print("   2. WiFi是否为2.4G（不支持5G）")
        print("   3. 信号是否太弱")
        return False

# ==================== 独立测试入口 ====================
if __name__ == "__main__":
    """
    独立测试：直接运行这个文件，测试WiFi连接功能
    就像手机的"WiFi诊断"功能
    """
    print("="*40)
    print(" WiFi连接 - 独立测试")
    print("="*40)
    
    # 测试连接
    result = connect_wifi()
    
    if result:
        print("\n✅ 测试通过：WiFi连接成功")
        print("   设备可以正常上网")
    else:
        print("\n❌ 测试失败：无法连接WiFi")
        print("   请按提示检查配置")
    
    print("\n独立测试结束")
