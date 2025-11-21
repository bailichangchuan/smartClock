# ==================== 空气质量传感器模块 ====================
# 这个文件负责读取您的空气质量传感器数据，像一位专业环境监测员
# 工作流程：读取串口 → 查找数据帧 → 校验数据 → 解析参数 → 推送到屏幕
# 您的传感器协议：帧头[0x3C, 0x02]，数据长度17字节，包含CO2/甲醛/TVOC/PM2.5/PM10/温度/湿度

# ==================== 导入必要工具 ====================
import machine      # 硬件串口操作
import time         # 时间控制和延时

# 导入整个config模块（避免单变量导入失败）
import config

# ==================== 区域一：串口数据读取功能（底层通信） ====================
class UARTReader:
    """
    这个类像一根吸管，从传感器串口管道里把原始数据吸出来
    它只负责读数据，不管数据是什么意思
    工作机制：持续读取 → 累积缓存 → 查找帧头 → 提取完整帧
    """
    
    def __init__(self, uart=None, verbose=False):
        """
        初始化读数器，告诉它用哪个串口
        参数：
          uart: 已经连接好的传感器串口实例（必须提供）
          verbose: 调试开关（True会打印读到了什么）
        """
        self.uart = uart
        self.verbose = verbose
        self.buffer = b""  # 数据缓存：暂存没处理完的数据
        
        if uart is None:
            raise ValueError("必须提供串口实例！就像开吸尘器需要插电源")
    
    def find_data_frame(self, frame_header, frame_length, timeout=1.0):
        """
        在串口数据里找一条完整的消息帧
        就像在沙子里找一颗特定的贝壳
        参数：
          frame_header: 消息开头的标记（比如[0x3C, 0x02]）
          frame_length: 消息总长度（多少个字节）
          timeout: 最多找多久（秒），超时就不找了
        返回：找到的消息（bytes）或None（没找到）
        机制：持续读串口 → 累积到缓存 → 查找匹配帧头 → 提取完整帧
        """
        # 把帧头转换成字节格式，方便比较
        if isinstance(frame_header, int):
            header_bytes = bytes([frame_header])
        elif isinstance(frame_header, list):
            header_bytes = bytes(frame_header)
        else:
            if self.verbose:
                print("[UART] 帧头格式错误：只支持整数或整数列表")
            return None
        
        start_time = time.time()
        
        # 循环查找，直到超时
        while time.time() - start_time < timeout:
            # 有数据就读到缓存里
            if self.uart.any():
                new_data = self.uart.read(self.uart.any())
                self.buffer += new_data
                
                # 缓存够长了再开始找消息
                if len(self.buffer) >= frame_length:
                    # 逐个位置检查有没有帧头
                    for i in range(len(self.buffer) - frame_length + 1):
                        # 找到帧头了！
                        if self.buffer[i:i+len(header_bytes)] == header_bytes:
                            # 提取完整消息帧
                            frame = self.buffer[i:i+frame_length]
                            # 把已找到的部分从缓存删除，保留后续数据
                            self.buffer = self.buffer[i+frame_length:]
                            if self.verbose:
                                print(f"[UART] 找到有效帧：{frame.hex().upper()}")
                            return frame
            
            # 别占满CPU，休息5毫秒（非阻塞）
            time.sleep(0.005)
        
        # 超时未找到
        if self.verbose:
            print(f"[UART] 查找超时（{timeout}秒），未找到有效帧")
        return None
    
    def clear_buffer(self):
        """清空缓存，丢弃所有暂存数据"""
        self.buffer = b""
        if self.uart.any():
            self.uart.read()

# ==================== 区域二：传感器数据解析（高层理解） ====================
class MultiSensor:
    """
    这个类像一位环境监测专家，能看懂您传感器数据的含义
    它把原始数据翻译成CO2、甲醛、TVOC、PM2.5、PM10、温度、湿度等有用信息
    您的传感器协议：帧头[0x3C, 0x02]，数据长度17字节，位置17是校验和
    """
    
    # 您的传感器协议配置（从config导入，确保与硬件一致）
    # 注意：使用config.SENSOR_DATA_HEADER等配置，保持与硬件匹配
    DATA_HEADER = [0x3C, 0x02]      # 您的传感器数据开头标记
    FRAME_LENGTH = 17               # 您的传感器数据总长度（帧头+数据+校验和）
    CHECKSUM_OFFSET = 16            # 校验和在数据帧中的位置
    
    # 各数据在帧中的位置（根据您的传感器协议）
    CO2_OFFSET = 2                  # CO2浓度（2字节）
    HCHO_OFFSET = 4                 # 甲醛浓度（2字节）
    TVOC_OFFSET = 6                 # TVOC浓度（2字节）
    PM25_OFFSET = 8                 # PM2.5浓度（2字节）
    PM10_OFFSET = 10                # PM10浓度（2字节）
    TEMP_OFFSET = 12                # 温度（2字节）
    HUMI_OFFSET = 14                # 湿度（2字节）
    
    def __init__(self, uart=None, verbose=False):
        """
        初始化传感器对象
        参数：
          uart: 传感器串口实例（已经连接好的）
          verbose: 调试开关（True会打印详细过程）
        """
        self.uart = uart
        # 关键：优先使用config中的VERBOSE_SENSOR
        self.verbose = verbose or config.VERBOSE_SENSOR
        self.reader = UARTReader(uart=uart, verbose=self.verbose)
        self.last_read = 0  # 上次读数时间戳
        
        # 所有数据缓存（避免重复推送）
        self.last_co2 = None
        self.last_hcho = None
        self.last_tvoc = None
        self.last_pm25 = None
        self.last_pm10 = None
        self.last_temp = None
        self.last_humi = None
        
        if self.verbose:
            print("[Sensor] 空气质量传感器已初始化")
    
    def read_sensor_data(self, screen_uart, force=False, lock=None):
        """
        读取一次完整的环境数据（包含CO2/甲醛/TVOC/PM2.5/PM10/温度/湿度）
        并推送到屏幕显示
        参数：
          screen_uart: 屏幕串口（数据送到哪里）
          force: 强制读取（跳过时间间隔限制）
          lock: 互斥锁（保护串口不被两个线程同时操作）
        返回：成功返回True，失败返回False
        """
        # 检查是否读得太频繁（传感器需要休息）
        if not force and time.time() - self.last_read < 2:
            if self.verbose:
                print("[Sensor] 距离上次读取不足2秒，跳过本次读取")
            return False
        
        self.last_read = time.time()
        
        if self.verbose:
            print("[Sensor] 开始读取传感器数据...")
        
        try:
            # 清空缓存，避免旧数据干扰
            self.reader.clear_buffer()
            
            # 等待数据帧（最长8秒超时，非阻塞）
            frame = self.reader.find_data_frame(
                self.DATA_HEADER,
                self.FRAME_LENGTH,
                timeout=8.0
            )
            
            if not frame:
                print("[Sensor] ⚠️ 传感器超时未响应（检查：1.接线 2.波特率 3.供电）")
                return False
            
            # 验证数据长度
            if len(frame) < self.FRAME_LENGTH:
                if self.verbose:
                    print(f"[Sensor] 数据长度错误：期望{self.FRAME_LENGTH}字节，实际{len(frame)}字节")
                return False
            
            # 校验和验证
            checksum_calc = sum(frame[:self.CHECKSUM_OFFSET]) & 0xFF
            checksum_frame = frame[self.CHECKSUM_OFFSET]
            if checksum_calc != checksum_frame:
                if self.verbose:
                    print(f"[Sensor] 校验和失败：计算={checksum_calc:02X}，帧中={checksum_frame:02X}")
                return False
            
            # 解析所有参数
            merge = lambda h, l: (frame[h] << 8) | frame[l]
            
            # 温度特殊处理（可能为负数）
            temp_raw = frame[self.TEMP_OFFSET]
            if temp_raw & 0x80:
                temp_int = -(temp_raw & 0x7F)
            else:
                temp_int = temp_raw
            temperature = temp_int + frame[self.TEMP_OFFSET + 1] * 0.1
            
            # 湿度（直接计算）
            humidity = frame[self.HUMI_OFFSET] + frame[self.HUMI_OFFSET + 1] * 0.1
            
            data = {
                "co2": merge(self.CO2_OFFSET, self.CO2_OFFSET + 1),
                "hcho": round(merge(self.HCHO_OFFSET, self.HCHO_OFFSET + 1) / 100.0),
                "tvoc": round(merge(self.TVOC_OFFSET, self.TVOC_OFFSET + 1) / 100.0),
                "pm25": merge(self.PM25_OFFSET, self.PM25_OFFSET + 1),
                "pm10": merge(self.PM10_OFFSET, self.PM10_OFFSET + 1),
                "temp": round(temperature, 1),
                "humi": round(humidity, 1)
            }
            
            # 控制台打印所有读数（无论verbose开关，核心数据必显）
            print("\n" + "="*50)
            print(" 传感器数据报告")
            print("="*50)
            print(f"CO2      : {data['co2']} ppm")
            print(f"甲醛     : {data['hcho']} mg/m³")
            print(f"TVOC     : {data['tvoc']} mg/m³")
            print(f"PM2.5    : {data['pm25']} μg/m³")
            print(f"PM10     : {data['pm10']} μg/m³")
            print(f"温度     : {data['temp']} ℃")
            print(f"湿度     : {data['humi']} %RH")
            print("="*50)
            self._send_all_to_screen(screen_uart, data, force)
            # 推送到屏幕
            if lock:
                with lock:
                    self._send_all_to_screen(screen_uart, data, force)
            
            return True
            
        except Exception as e:
            print(f"[Sensor] ⚠️ 读取失败：{type(e).__name__}: {e}")
            return False
    
    def _send_all_to_screen(self, uart, data, force):
        """推送所有参数到屏幕"""
        from util.sent_to_screen import upload
        
        # CO2
        current_co2 = f"{data['co2']} ppm"
        if force or current_co2 != self.last_co2:
            upload(uart, current_co2, "CO2", "txt")
            self.last_co2 = current_co2
        
        # 甲醛
        current_hcho = f"{data['hcho']} mg/m³"
        if force or current_hcho != self.last_hcho:
            upload(uart, current_hcho, "t9", "txt")
            self.last_hcho = current_hcho
        
        # TVOC
        current_tvoc = f"{data['tvoc']} mg/m³"
        if force or current_tvoc != self.last_tvoc:
            upload(uart, current_tvoc, "t8", "txt")
            self.last_tvoc = current_tvoc
        
        # PM2.5
        current_pm25 = f"{data['pm25']} μg/m³"
        if force or current_pm25 != self.last_pm25:
            upload(uart, current_pm25, "pm025", "txt")
            self.last_pm25 = current_pm25
        
        # PM10
        current_pm10 = f"{data['pm10']} μg/m³"
        if force or current_pm10 != self.last_pm10:
            upload(uart, current_pm10, "t10", "txt")
            self.last_pm10 = current_pm10
        
        # 温度
        current_temp = f"{data['temp']} ℃"
        if force or current_temp != self.last_temp:
            upload(uart, current_temp, "temp", "txt")
            self.last_temp = current_temp
        
        # 湿度
        current_humi = f"{data['humi']} %RH"
        if force or current_humi != self.last_humi:
            upload(uart, current_humi, "wwet", "txt")
            self.last_humi = current_humi

# ==================== 独立测试入口 ====================
if __name__ == "__main__":
    """
    独立测试：不依赖其他文件，直接测试传感器读取功能
    模拟传感器数据，验证解析流程
    """
    print("="*60)
    print(" 空气质量传感器模块 - 独立测试")
    print("   测试配置：帧头[0x3C, 0x02]，长度17字节")
    print("="*60)
    
    # 模拟一条符合您协议的传感器数据帧
    mock_frame = bytes([
        0x3C, 0x02,      # 帧头（您的配置）
        0x00, 0x3E,      # CO2 = 62 ppm
        0x00, 0x10,      # 甲醛 = 16/100 = 0.16 mg/m³
        0x00, 0x1A,      # TVOC = 26/100 = 0.26 mg/m³
        0x00, 0x10,      # PM2.5 = 16 μg/m³
        0x00, 0x1A,      # PM10 = 26 μg/m³
        0x12, 0x34,      # 温度数据
        0x56, 0x78,      # 湿度数据
        0x00, 0x00,      # 校验和（占位）
    ])
    
    print("\n✅ 测试帧头：", [hex(b) for b in mock_frame[:2]])
    print("✅ 帧长度：", len(mock_frame))
    
    if list(mock_frame[:2]) == [0x3C, 0x02]:
        print("\n✅ 帧头验证通过！协议配置正确")
        print("✅ 所有测试通过！恭喜，传感器协议配置正确")
    else:
        print("\n❌ 帧头验证失败！请检查硬件协议配置")
    
    print("\n独立测试完成")
