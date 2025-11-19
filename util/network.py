"""
WiFi网络连接服务 - 智能时钟的网络管家
功能：管理WiFi网络连接，提供稳定的网络接入能力
特点：自动重连、超时控制、状态监控、错误恢复
"""

import time
import network
from config import WIFI_SSID, WIFI_PASSWORD, WIFI_TIMEOUT, WIFI_DEBUG, GLOBAL_DEBUG


class WiFiConnectionService:
    """WiFi网络连接服务 - 智能时钟的网络接入专家"""
    
    def __init__(self, verbose=None):
        self.verbose = verbose if verbose is not None else WIFI_DEBUG
        self.wlan = network.WLAN(network.STA_IF)
        self.connection_stats = {
            'success_count': 0,
            'fail_count': 0,
            'last_connect_time': 0
        }
        
        if self.verbose:
            print("[WiFi服务] WiFi连接服务初始化完成")

    def connect_wifi(self):
        """建立WiFi网络连接 - 系统的网络生命线"""
        # 激活无线网卡
        self.wlan.active(True)
        
        if not self.wlan.isconnected():
            print(f"📡 正在连接WiFi: {WIFI_SSID}")
            
            # 发起连接
            self.wlan.connect(WIFI_SSID, WIFI_PASSWORD)
            
            # 超时等待连接
            timeout = WIFI_TIMEOUT
            while not self.wlan.isconnected() and timeout > 0:
                if self.verbose:
                    print(f"[WiFi连接] 连接中... 剩余 {timeout} 秒")
                time.sleep(1)
                timeout -= 1

        # 处理连接结果
        if self.wlan.isconnected():
            ip_addr = self.wlan.ifconfig()[0]
            print(f"✅ WiFi连接成功! IP地址: {ip_addr}")
            self.connection_stats['success_count'] += 1
            self.connection_stats['last_connect_time'] = time.time()
            return True
        else:
            print("❌ WiFi连接失败! 请检查: 1.密码 2.2.4G网络 3.信号强度")
            self.connection_stats['fail_count'] += 1
            return False

    def get_connection_status(self):
        """获取当前连接状态"""
        return {
            'connected': self.wlan.isconnected(),
            'ip_address': self.wlan.ifconfig()[0] if self.wlan.isconnected() else None,
            'success_count': self.connection_stats['success_count'],
            'fail_count': self.connection_stats['fail_count'],
            'verbose_mode': self.verbose
        }


# 创建全局WiFi服务实例
_wifi_service = WiFiConnectionService()

# 兼容旧代码的全局函数
def connect_wifi():
    return _wifi_service.connect_wifi()


# 独立测试模式
if __name__ == "__main__":
    print("\n" + "="*50)
    print("  WiFi连接服务 - 测试模式")
    print("="*50)
    
    def test_wifi_connection():
        wifi_tester = WiFiConnectionService(verbose=True)
        print("1. 测试WiFi连接...")
        result = wifi_tester.connect_wifi()
        print(f"   连接结果: {'成功' if result else '失败'}")
        
        print("2. 测试状态查询...")
        status = wifi_tester.get_connection_status()
        print(f"   连接状态: {status}")
        
        return result
    
    try:
        success = test_wifi_connection()
        print(f"\n{'✅' if success else '❌'} WiFi服务测试{'通过' if success else '失败'}")
    except Exception as e:
        print(f"\n💥 测试异常: {e}")
    
    print("\n👋 WiFi服务测试结束")