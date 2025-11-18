# ===导入依赖模块=======
# 时间工具模块：提供秒级延时（WiFi连接超时等待）
import time
# 网络控制模块：提供WLAN接口（WiFi连接核心，支持STA客户端模式）
import network
# 配置文件导入：WiFi账号密码（统一管理，避免硬编码）
from config import WIFI_SSID, WIFI_PWD

# ===模块配置=======
# DEBUG日志控制开关：需与main.py全局VERBOSE对齐（建议在main中传入或统一赋值）
# 作用：控制连接过程中的详细日志（如“连接中...剩余X秒”），True启用，False关闭
VERBOSE = False

# ===核心函数：WiFi连接（STA客户端模式）=======
def connect_wifi():
    """
    连接指定WiFi网络（STA客户端模式，仅支持2.4G网络）
    核心特性：
    1. 自动激活网卡，检查当前连接状态
    2. 15秒超时等待（避免无限阻塞）
    3. 详细状态提示（必显核心状态，DEBUG日志受VERBOSE控制）
    4. 连接失败时给出明确排查建议（密码/网络频段）
    :return: 连接结果标识 → True=连接成功，False=连接失败
    连接流程：
    1. 初始化WLAN为STA客户端模式（非AP热点模式）
    2. 激活无线网卡
    3. 未连接时，发起WiFi连接（使用config配置的SSID和密码）
    4. 超时循环等待：每秒检查连接状态，输出剩余时间（受VERBOSE控制）
    5. 连接成功：输出IP地址（必显），返回True
    6. 连接失败：输出排查建议（必显），返回False
    """
    # 步骤1：初始化WLAN为STA客户端模式（network.STA_IF=客户端，用于连接路由器）
    wlan = network.WLAN(network.STA_IF)
    # 步骤2：激活无线网卡（True=激活，False=关闭）
    wlan.active(True)
    
    # 步骤3：检查当前连接状态，未连接则发起连接
    if not wlan.isconnected():
        # 核心状态输出（必显，告知用户正在连接的WiFi名称）
        print(f"正在连接 WiFi：{WIFI_SSID}（仅支持2.4G网络）")
        # 发起WiFi连接（传入SSID和密码，底层自动完成认证）
        wlan.connect(WIFI_SSID, WIFI_PWD)
        
        # 步骤4：15秒超时等待（循环检查连接状态）
        timeout = 15  # 超时时间（秒）
        while not wlan.isconnected() and timeout > 0:
            # DEBUG日志：仅VERBOSE=True时输出连接进度（剩余时间）
            if VERBOSE:
                print(f"[WIFI DEBUG] 连接中... 剩余 {timeout} 秒")
            time.sleep(1)  # 每秒检查一次，降低CPU占用
            timeout -= 1  # 超时倒计时
    
    # 步骤5：判断连接结果并返回
    if wlan.isconnected():
        # 核心状态输出（必显，告知用户连接成功及设备IP地址）
        ip_addr = wlan.ifconfig()[0]  # 提取IP地址（ifconfig返回：(IP,子网掩码,网关,DNS)）
        print(f"WiFi连接成功！设备IP地址：{ip_addr}")
        return True
    else:
        # 核心状态输出（必显，告知用户连接失败及排查建议）
        print("WiFi连接失败！请排查：1. 密码是否正确；2. 网络是否为2.4G（不支持5G）；3. 信号是否稳定")
        return False