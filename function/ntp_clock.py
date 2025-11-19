"""
NTP网络时间同步系统 - 智能时钟的时间管家
功能：从互联网时间服务器获取准确时间，确保时钟显示精准无误
特点：自动时区转换、智能重试机制、多格式时间显示
"""

# 导入硬件时钟模块 - 系统实时时钟的控制中心
from machine import RTC
import socket
import utime

# 导入系统配置 - 使用面向用户的友好配置项
from config import (
    # NTP配置
    NTP_SERVER, TIMEZONE_OFFSET, NTP_TIMEOUT, NTP_DEBUG, GLOBAL_DEBUG,
    # 系统配置
    DEVICE_NAME
)

# 导入屏幕通信工具 - 时间显示的桥梁
from util import sent_to_screen


class NTPTimeManager:
    """
    NTP时间管理器 - 智能时钟的时间校准专家
    负责从互联网时间服务器获取准确时间，确保时钟始终精准
    就像一位守时的管家，时刻确保所有时钟都指向正确的时间
    """
    
    def __init__(self, verbose=None):
        """
        初始化NTP时间管理系统
        
        参数说明：
        - verbose: 详细日志开关（如果为None，使用配置中的NTP_DEBUG）
        """
        # 设置调试模式：优先使用参数，其次使用配置开关
        self.verbose = verbose if verbose is not None else NTP_DEBUG
        
        # 系统实时时钟实例 - 硬件时钟的控制中心
        self.system_clock = RTC()
        
        # 显示缓存 - 记录已发送到屏幕的时间数据，避免重复传输
        self.display_cache = {
            'last_date': None,      # 上一次显示的日期
            'last_weekday': None,   # 上一次显示的星期
            'last_minute': None     # 上一次显示的分钟（用于判断是否需要更新）
        }
        
        if self.verbose:
            print("[NTP时间] 时间管理系统初始化完成")

    def sync_time_from_internet(self):
        """
        从互联网时间服务器同步系统时间
        就像给手表对时，确保我们的时钟与世界时间保持一致
        
        返回：元组 (同步是否成功, 时区偏移)
        """
        if self.verbose:
            print(f"[NTP时间] 开始从 {NTP_SERVER} 同步网络时间...")
        
        print("⏰ 正在同步网络时间...")
        
        # 从NTP服务器获取原始时间戳
        ntp_timestamp = self._fetch_ntp_timestamp()
        if ntp_timestamp is None:
            print("❌ 时间同步失败：无法从服务器获取时间")
            return False, TIMEZONE_OFFSET
        
        # 将NTP时间戳转换为本地时间
        local_time = self._convert_ntp_to_local(ntp_timestamp)
        if local_time is None:
            print("❌ 时间同步失败：时间转换错误")
            return False, TIMEZONE_OFFSET
        
        # 验证时间的合理性
        if not self._validate_time(local_time):
            print("❌ 时间同步失败：获取到无效的时间")
            return False, TIMEZONE_OFFSET
        
        # 将时间设置到系统硬件时钟
        self._set_system_time(local_time)
        
        # 显示同步成功信息
        formatted_time = self._format_time_display(local_time)
        print(f"✅ 时间同步成功: {formatted_time} (UTC+{TIMEZONE_OFFSET})")
        
        return True, TIMEZONE_OFFSET

    def _fetch_ntp_timestamp(self):
        """
        从NTP服务器获取原始时间戳
        与远程时间服务器进行通信，获取精确的时间信息
        """
        ntp_socket = None
        try:
            if self.verbose:
                print("[NTP时间] 正在连接NTP服务器...")
            
            # 解析NTP服务器地址
            server_address = socket.getaddrinfo(NTP_SERVER, 123)
            if not server_address:
                if self.verbose:
                    print("[NTP时间] 无法解析NTP服务器地址")
                return None
            
            # 获取服务器IP地址
            server_ip = server_address[0][-1][0]
            
            if self.verbose:
                print(f"[NTP时间] 连接到NTP服务器: {server_ip}")
            
            # 创建UDP socket连接
            ntp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            ntp_socket.settimeout(NTP_TIMEOUT)
            
            # 构建NTP请求数据包
            ntp_request = bytearray(48)
            ntp_request[0] = 0x23  # NTP协议版本和模式
            
            # 发送NTP请求
            ntp_socket.sendto(ntp_request, (server_ip, 123))
            
            # 接收NTP响应
            ntp_response = ntp_socket.recv(48)
            
            if len(ntp_response) != 48:
                if self.verbose:
                    print(f"[NTP时间] 无效的NTP响应长度: {len(ntp_response)}")
                return None
            
            # 从响应中提取时间戳（第40-43字节）
            timestamp = (ntp_response[40] << 24) | (ntp_response[41] << 16) | (ntp_response[42] << 8) | ntp_response[43]
            
            if self.verbose:
                print(f"[NTP时间] 获取到NTP时间戳: {timestamp}")
            
            return timestamp
            
        except OSError as e:
            if self.verbose:
                print(f"[NTP时间] 网络通信错误: {e}")
            return None
        except Exception as e:
            if self.verbose:
                print(f"[NTP时间] 获取时间戳异常: {e}")
            return None
        finally:
            # 确保socket连接被关闭
            if ntp_socket:
                ntp_socket.close()

    def _convert_ntp_to_local(self, ntp_timestamp):
        """
        将NTP时间戳转换为本地时间
        考虑时区偏移，将UTC时间转换为用户所在时区的时间
        """
        try:
            # 应用时区偏移（转换为秒）
            ntp_timestamp += int(TIMEZONE_OFFSET * 3600)
            
            # 计算总天数和当天剩余秒数
            seconds_per_day = 86400
            total_days = (ntp_timestamp + seconds_per_day - 1) // seconds_per_day
            remaining_seconds = ntp_timestamp % seconds_per_day
            
            # 计算时、分、秒
            hours = remaining_seconds // 3600
            minutes = (remaining_seconds % 3600) // 60
            seconds = remaining_seconds % 60
            
            # 从1900年开始计算实际年份
            year = 1900
            while True:
                is_leap_year = self._is_leap_year(year)
                days_in_year = 366 if is_leap_year else 365
                
                if total_days < days_in_year:
                    break
                
                total_days -= days_in_year
                year += 1
            
            # 计算月份和日期
            month_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
            if is_leap_year:
                month_days[1] = 29  # 闰年2月有29天
            
            month = 0
            while month < 11 and total_days >= month_days[month]:
                total_days -= month_days[month]
                month += 1
            
            month += 1  # 转换为1-12月
            day = total_days + 1  # 转换为1-31日
            
            # 计算星期（1900-01-01是星期一）
            weekday = (total_days - 1) % 7
            
            local_time = (year, month, day, hours, minutes, seconds, weekday)
            
            if self.verbose:
                print(f"[NTP时间] 转换后的本地时间: {local_time}")
            
            return local_time
            
        except Exception as e:
            if self.verbose:
                print(f"[NTP时间] 时间转换异常: {e}")
            return None

    def _is_leap_year(self, year):
        """
        判断是否为闰年
        遵循闰年规则：能被4整除但不能被100整除，或者能被400整除
        """
        return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)

    def _validate_time(self, time_data):
        """
        验证时间数据的合理性
        确保从服务器获取的时间在合理的范围内
        """
        year, month, day, hour, minute, second, weekday = time_data
        
        # 检查年份是否在合理范围内
        if not (1970 <= year <= 2100):
            if self.verbose:
                print(f"[NTP时间] 无效年份: {year}")
            return False
        
        # 检查月份是否在合理范围内
        if not (1 <= month <= 12):
            if self.verbose:
                print(f"[NTP时间] 无效月份: {month}")
            return False
        
        # 检查日期是否在合理范围内
        month_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        if self._is_leap_year(year):
            month_days[1] = 29
        
        if not (1 <= day <= month_days[month - 1]):
            if self.verbose:
                print(f"[NTP时间] 无效日期: {day}")
            return False
        
        # 检查时间是否在合理范围内
        if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
            if self.verbose:
                print(f"[NTP时间] 无效时间: {hour}:{minute}:{second}")
            return False
        
        return True

    def _set_system_time(self, time_data):
        """
        将时间设置到系统硬件时钟
        让我们的智能时钟显示准确的时间
        """
        year, month, day, hour, minute, second, weekday = time_data
        
        # RTC.datetime格式: (年, 月, 日, 星期, 时, 分, 秒, 微秒)
        # 注意：RTC的星期是1-7（1=星期一，7=星期日）
        rtc_weekday = weekday + 1
        
        self.system_clock.datetime((year, month, day, rtc_weekday, hour, minute, second, 0))
        
        if self.verbose:
            print(f"[NTP时间] 系统时钟已更新: {year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}")

    def _format_time_display(self, time_data):
        """
        格式化时间显示
        将时间数据转换为友好的显示格式
        """
        year, month, day, hour, minute, second, _ = time_data
        return f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"

    def get_current_time_string(self):
        """
        获取当前时间的格式化字符串
        用于在控制台显示或记录日志
        """
        time_data = self.system_clock.datetime()
        year, month, day, _, hour, minute, second, _ = time_data
        return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"

    def update_screen_display(self, screen_uart, force_update=False):
        """
        更新屏幕上的时间显示
        将当前时间发送到串口屏的各个时间控件
        
        参数说明：
        - screen_uart: 屏幕通信实例
        - force_update: 强制更新标志（忽略缓存直接更新）
        """
        if screen_uart is None:
            if self.verbose:
                print("[NTP时间] 屏幕通信未就绪，无法更新时间显示")
            return
        
        # 从系统时钟获取当前时间
        time_data = self.system_clock.datetime()
        year, month, day, weekday_num, hour, minute, second, _ = time_data
        
        # 准备显示数据
        current_date = f"{year:04d}-{month:02d}-{day:02d}"
        
        # 星期转换：1=星期一, 2=星期二, ..., 7=星期日
        weekday_chinese = ['一', '二', '三', '四', '五', '六', '日']
        current_weekday = weekday_chinese[weekday_num - 1] if 1 <= weekday_num <= 7 else '未知'
        
        current_minute = minute
        
        # 短暂延迟，确保屏幕就绪
        utime.sleep_ms(50)
        
        # 更新日期显示（控件t0）
        if force_update or current_date != self.display_cache['last_date']:
            sent_to_screen.upload(screen_uart, current_date, control_name="t0", property_name="txt")
            self.display_cache['last_date'] = current_date
            if self.verbose:
                print(f"[NTP时间] 更新日期显示: {current_date}")
        
        # 更新星期显示（控件t1）
        weekday_display = f"星期{current_weekday}"
        if force_update or current_weekday != self.display_cache['last_weekday']:
            sent_to_screen.upload(screen_uart, weekday_display, control_name="t1", property_name="txt")
            self.display_cache['last_weekday'] = current_weekday
            if self.verbose:
                print(f"[NTP时间] 更新星期显示: {weekday_display}")
        
        # 更新时间显示（控件t2）- 只在分钟变化时更新
        time_display = f"{hour:02d}:{minute:02d}"
        if force_update or current_minute != self.display_cache['last_minute']:
            sent_to_screen.upload(screen_uart, time_display, control_name="t2", property_name="txt")
            self.display_cache['last_minute'] = current_minute
            if self.verbose:
                print(f"[NTP时间] 更新时间显示: {time_display}")

    def get_system_status(self):
        """
        获取系统时间状态信息
        用于监控和调试时间同步系统
        """
        current_time = self.get_current_time_string()
        return {
            'current_time': current_time,
            'verbose_mode': self.verbose,
            'cache_status': self.display_cache
        }


# 创建全局时间管理器实例（兼容旧代码）
_time_manager = NTPTimeManager()

# 兼容旧代码的全局函数
def sync_ntp_to_rtc():
    """同步NTP时间到RTC（兼容旧代码接口）"""
    return _time_manager.sync_time_from_internet()

def get_current_formatted_time():
    """获取当前格式化时间（兼容旧代码接口）"""
    return _time_manager.get_current_time_string()

def send_time_to_serial_screen(uart, force=False):
    """发送时间到串口屏（兼容旧代码接口）"""
    _time_manager.update_screen_display(uart, force)


# =============================================================================
# 独立运行模式 - NTP时间系统的专用测试环境
# 当直接运行这个文件时，会进入测试模式，方便单独测试时间同步功能
# =============================================================================
if __name__ == "__main__":
    """
    NTP时间系统独立测试模式
    无需启动整个智能时钟系统，单独测试时间同步功能
    """
    print("\n" + "="*60)
    print("  NTP网络时间同步系统 - 独立测试模式")
    print("="*60)
    
    def run_ntp_system_test():
        """运行NTP时间系统的基本功能测试"""
        print("\n🧪 开始NTP时间系统功能测试...")
        
        # 创建测试用的时间管理器实例
        ntp_manager = NTPTimeManager(verbose=True)
        
        print("1. 测试时间管理器初始化...")
        status = ntp_manager.get_system_status()
        print(f"   系统状态: {status}")
        
        print("2. 测试闰年判断功能...")
        test_years = [2000, 2020, 2024, 1900, 2023]
        for year in test_years:
            is_leap = ntp_manager._is_leap_year(year)
            print(f"   {year}年: {'闰年' if is_leap else '平年'}")
        
        print("3. 测试时间同步功能（需要网络连接）...")
        try:
            success, timezone = ntp_manager.sync_time_from_internet()
            print(f"   时间同步: {'成功' if success else '失败'}")
            if success:
                current_time = ntp_manager.get_current_time_string()
                print(f"   当前系统时间: {current_time}")
        except Exception as e:
            print(f"   时间同步测试异常: {e}")
        
        print("4. 测试时间显示功能...")
        # 创建模拟屏幕UART用于测试
        class MockScreenUART:
            def write(self, data):
                if NTP_DEBUG:
                    print(f"[模拟屏幕] 接收时间数据: {data[:30]}...")
        
        mock_screen = MockScreenUART()
        ntp_manager.update_screen_display(mock_screen, force_update=True)
        
        print("\n🎉 NTP时间系统基本功能测试完成")
        return True
    
    try:
        # 运行测试
        success = run_ntp_system_test()
        
        if success:
            print("\n✅ NTP时间系统独立测试通过")
        else:
            print("\n❌ NTP时间系统测试失败")
            
    except Exception as e:
        print(f"\n💥 测试过程中发生异常: {e}")
        import sys
        sys.print_exception(e)
    
    print("\n👋 NTP网络时间同步系统测试结束")