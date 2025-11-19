"""
天气信息服务系统 - 智能时钟的天气情报员
功能：从互联网获取实时天气信息，为用户提供准确的环境状况
特点：智能定位、自动更新、多数据展示、优雅降级
"""

# 导入网络通信模块 - 与天气服务器对话的桥梁
import usocket as socket
import ujson as json
import utime

# 导入系统配置 - 使用面向用户的友好配置项
from config import (
    # 天气服务配置
    WEATHER_API_KEY, WEATHER_LOCATION, WEATHER_UPDATE_INTERVAL,
    WEATHER_DEBUG, GLOBAL_DEBUG,
    # 网络配置
    WIFI_TIMEOUT
)

# 导入屏幕通信工具 - 天气信息展示的窗口
from util import sent_to_screen


class WeatherService:
    """
    天气信息服务 - 智能时钟的天气情报专家
    负责从云端获取最新天气数据，让用户随时了解室外环境状况
    就像一位贴心的气象播报员，时刻关注天气变化
    """
    
    def __init__(self, verbose=None):
        """
        初始化天气信息服务
        
        参数说明：
        - verbose: 详细日志开关（如果为None，使用配置中的WEATHER_DEBUG）
        """
        # 设置调试模式：优先使用参数，其次使用配置开关
        self.verbose = verbose if verbose is not None else WEATHER_DEBUG
        
        # 显示缓存 - 记录已发送到屏幕的天气数据，避免重复传输
        self.display_cache = {
            'city': None,        # 上一次显示的城市
            'weather': None,     # 上一次显示的天气状况
            'temperature': None  # 上一次显示的温度
        }
        
        # 构建天气API请求路径
        self.api_path = f"/v3/weather/now.json?key={WEATHER_API_KEY}&location={WEATHER_LOCATION}&language=zh-Hans&unit=c"
        self.api_domain = "api.seniverse.com"
        
        if self.verbose:
            print("[天气服务] 天气信息服务初始化完成")

    def fetch_weather_data(self, screen_uart, force_refresh=False):
        """
        获取并显示天气信息
        从云端天气服务获取最新数据，并更新屏幕显示
        
        参数说明：
        - screen_uart: 屏幕通信实例
        - force_refresh: 强制刷新标志（忽略缓存直接更新）
        """
        if self.verbose:
            print("[天气服务] 开始获取天气信息...")
        
        print("🌤️  正在获取天气信息...")
        
        try:
            # 从天气API获取原始数据
            api_response = self._request_weather_api()
            if api_response is None:
                # API请求失败，使用缓存或占位符
                self._handle_api_failure(screen_uart, force_refresh)
                return
            
            # 解析天气数据
            weather_info = self._parse_weather_data(api_response)
            if weather_info is None:
                # 数据解析失败，使用缓存或占位符
                self._handle_parse_failure(screen_uart, force_refresh)
                return
            
            # 显示天气信息（控制台输出）
            self._display_weather_report(weather_info)
            
            # 更新屏幕显示
            self._update_screen_display(screen_uart, weather_info, force_refresh)
            
            if self.verbose:
                print("[天气服务] 天气信息获取和显示完成")
            
        except Exception as e:
            print(f"❌ 天气服务异常: {e}")
            self._handle_general_failure(screen_uart, force_refresh)

    def _request_weather_api(self):
        """
        向天气API发送请求
        与远程服务器通信，获取最新的天气数据
        """
        if self.verbose:
            print(f"[天气服务] 连接天气API: {self.api_domain}")
        
        weather_socket = None
        try:
            # 创建TCP连接
            weather_socket = socket.socket()
            weather_socket.settimeout(WIFI_TIMEOUT)
            
            # 连接到天气服务器
            weather_socket.connect((self.api_domain, 80))
            
            # 构建HTTP请求
            http_request = (
                f"GET {self.api_path} HTTP/1.1\r\n"
                f"Host: {self.api_domain}\r\n"
                "Connection: close\r\n"
                "Accept: application/json,*/*\r\n\r\n"
            )
            
            if self.verbose:
                print(f"[天气服务] 发送HTTP请求: {http_request[:100]}...")
            
            # 发送请求
            weather_socket.send(http_request.encode("utf-8"))
            
            # 接收响应
            response_data = b""
            while True:
                chunk = weather_socket.recv(1024)
                if not chunk:
                    break
                response_data += chunk
            
            # 关闭连接
            weather_socket.close()
            
            # 解码响应
            response_text = response_data.decode("utf-8", "ignore")
            
            if self.verbose:
                print(f"[天气服务] 收到API响应，长度: {len(response_text)} 字符")
            
            # 分离HTTP头和响应体
            if "\r\n\r\n" not in response_text:
                print("❌ 天气API响应格式错误")
                return None
            
            headers, response_body = response_text.split("\r\n\r\n", 1)
            
            # 检查HTTP状态码
            if "HTTP/1.1 200 OK" not in headers:
                status_code = headers.split()[1] if len(headers.split()) > 1 else "未知"
                print(f"❌ 天气API请求失败，状态码: {status_code}")
                return None
            
            if self.verbose:
                print("[天气服务] API请求成功")
            
            return response_body
            
        except OSError as e:
            print(f"❌ 天气API网络错误: {e}")
            return None
        except Exception as e:
            print(f"❌ 天气API请求异常: {e}")
            return None
        finally:
            # 确保socket连接被关闭
            if weather_socket:
                weather_socket.close()

    def _parse_weather_data(self, api_response):
        """
        解析天气API响应数据
        从JSON格式的响应中提取有用的天气信息
        """
        try:
            if self.verbose:
                print("[天气服务] 解析天气数据...")
            
            # 解析JSON响应
            weather_data = json.loads(api_response)
            
            # 提取天气信息
            location_data = weather_data["results"][0]
            current_weather = location_data["now"]
            
            weather_info = {
                "city": location_data["location"]["name"],
                "weather": current_weather["text"],
                "temperature": f"{current_weather['temperature']}℃",
                "last_update": location_data["last_update"].split('+')[0]  # 移除时区信息
            }
            
            if self.verbose:
                print(f"[天气服务] 解析完成: {weather_info}")
            
            return weather_info
            
        except (ValueError, KeyError) as e:
            print(f"❌ 天气数据解析失败: {e}")
            if self.verbose:
                print(f"[天气服务] 原始响应: {api_response[:200]}...")
            return None
        except Exception as e:
            print(f"❌ 天气数据解析异常: {e}")
            return None

    def _display_weather_report(self, weather_info):
        """
        显示天气报告
        在控制台以友好的格式展示天气信息
        """
        print("\n" + "="*50)
        print("        实时天气报告")
        print("="*50)
        print(f" 🏙️  城市: {weather_info['city']}")
        print(f" ☁️  天气: {weather_info['weather']}")
        print(f" 🌡️  温度: {weather_info['temperature']}")
        print(f" 📅 更新: {weather_info['last_update']}")
        print("="*50)

    def _update_screen_display(self, screen_uart, weather_info, force_update):
        """
        更新屏幕天气显示
        将最新的天气信息发送到串口屏展示
        """
        if screen_uart is None:
            if self.verbose:
                print("[天气服务] 屏幕通信未就绪，无法更新天气显示")
            return
        
        if self.verbose:
            print("[天气服务] 更新屏幕天气显示...")
        
        # 短暂延迟，确保屏幕就绪
        utime.sleep_ms(50)
        
        # 更新城市显示（控件t3）
        if force_update or weather_info['city'] != self.display_cache['city']:
            sent_to_screen.upload(screen_uart, weather_info['city'], control_name="t3", property_name="txt")
            self.display_cache['city'] = weather_info['city']
            if self.verbose:
                print(f"[天气服务] 更新城市显示: {weather_info['city']}")
        
        # 更新天气状况显示（控件t4）
        if force_update or weather_info['weather'] != self.display_cache['weather']:
            sent_to_screen.upload(screen_uart, weather_info['weather'], control_name="t4", property_name="txt")
            self.display_cache['weather'] = weather_info['weather']
            if self.verbose:
                print(f"[天气服务] 更新天气显示: {weather_info['weather']}")
        
        # 更新温度显示（控件t5）
        if force_update or weather_info['temperature'] != self.display_cache['temperature']:
            sent_to_screen.upload(screen_uart, weather_info['temperature'], control_name="t5", property_name="txt")
            self.display_cache['temperature'] = weather_info['temperature']
            if self.verbose:
                print(f"[天气服务] 更新温度显示: {weather_info['temperature']}")

    def _handle_api_failure(self, screen_uart, force_refresh):
        """
        处理API请求失败的情况
        在无法获取新数据时，使用缓存数据或占位符
        """
        if self.verbose:
            print("[天气服务] 处理API请求失败...")
        
        # 如果有缓存数据且强制刷新，使用缓存数据
        if force_refresh and self.display_cache['city'] is not None:
            print("⚠️ 使用缓存的天气数据")
            self._update_screen_display(screen_uart, {
                'city': self.display_cache['city'],
                'weather': self.display_cache['weather'],
                'temperature': self.display_cache['temperature']
            }, True)
        elif force_refresh:
            # 没有缓存数据，使用占位符
            print("⚠️ 使用占位符天气数据")
            self._show_placeholder_data(screen_uart)

    def _handle_parse_failure(self, screen_uart, force_refresh):
        """
        处理数据解析失败的情况
        """
        if self.verbose:
            print("[天气服务] 处理数据解析失败...")
        
        if force_refresh:
            self._show_placeholder_data(screen_uart)

    def _handle_general_failure(self, screen_uart, force_refresh):
        """
        处理通用失败情况
        """
        if self.verbose:
            print("[天气服务] 处理通用失败...")
        
        if force_refresh:
            self._show_placeholder_data(screen_uart)

    def _show_placeholder_data(self, screen_uart):
        """
        显示占位符数据
        在无法获取真实天气数据时，显示友好的占位信息
        """
        if screen_uart is None:
            return
        
        placeholder_data = {
            'city': '未知',
            'weather': '未知',
            'temperature': '--℃'
        }
        
        self._update_screen_display(screen_uart, placeholder_data, True)
        
        if self.verbose:
            print("[天气服务] 显示占位符天气数据")

    def get_service_status(self):
        """
        获取服务状态信息
        用于监控和调试天气服务
        """
        return {
            'cache_city': self.display_cache['city'],
            'cache_weather': self.display_cache['weather'],
            'cache_temperature': self.display_cache['temperature'],
            'verbose_mode': self.verbose,
            'api_location': WEATHER_LOCATION
        }


# 创建全局天气服务实例（兼容旧代码）
_weather_service = WeatherService()

# 兼容旧代码的全局函数
def get_weather_by_ip(uart, force=False):
    """获取天气信息（兼容旧代码接口）"""
    _weather_service.fetch_weather_data(uart, force)


# =============================================================================
# 独立运行模式 - 天气服务的专用测试环境
# 当直接运行这个文件时，会进入测试模式，方便单独测试天气功能
# =============================================================================
if __name__ == "__main__":
    """
    天气服务独立测试模式
    无需启动整个智能时钟系统，单独测试天气信息功能
    """
    print("\n" + "="*60)
    print("  天气信息服务系统 - 独立测试模式")
    print("="*60)
    
    def run_weather_service_test():
        """运行天气服务的基本功能测试"""
        print("\n🧪 开始天气服务功能测试...")
        
        # 创建测试用的天气服务实例
        weather_system = WeatherService(verbose=True)
        
        print("1. 测试天气服务初始化...")
        status = weather_system.get_service_status()
        print(f"   服务状态: {status}")
        
        print("2. 测试API路径构建...")
        print(f"   API路径: {weather_system.api_path}")
        
        print("3. 测试屏幕显示功能...")
        # 创建模拟屏幕UART用于测试
        class MockScreenUART:
            def write(self, data):
                if WEATHER_DEBUG:
                    print(f"[模拟屏幕] 接收天气数据: {data[:30]}...")
        
        mock_screen = MockScreenUART()
        
        print("4. 测试占位符显示...")
        weather_system._show_placeholder_data(mock_screen)
        
        print("5. 测试天气数据获取（需要网络连接）...")
        try:
            weather_system.fetch_weather_data(mock_screen, force_refresh=True)
        except Exception as e:
            print(f"   天气获取测试异常: {e}")
        
        print("\n🎉 天气服务基本功能测试完成")
        return True
    
    try:
        # 运行测试
        success = run_weather_service_test()
        
        if success:
            print("\n✅ 天气服务独立测试通过")
        else:
            print("\n❌ 天气服务测试失败")
            
    except Exception as e:
        print(f"\n💥 测试过程中发生异常: {e}")
        import sys
        sys.print_exception(e)
    
    print("\n👋 天气信息服务系统测试结束")