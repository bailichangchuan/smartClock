from uart_reader import UARTReader
from config import SENSOR_READ_INTERVAL
import utime

# === 传感器协议配置 ===
FRAME_HEADER = 0x3C          # 数据帧头
FRAME_LENGTH = 17            # 完整数据帧长度 单位字节
CHECKSUM_OFFSET = 16         # 校验和字节索引 从0开始

# === 核心功能 ===
class MultiSensor:
    def __init__(self, verbose=False):
        """初始化传感器读取器"""
        self.verbose = verbose
        self.uart_reader = None
        self.last_read = 0
        
        try:
            self.uart_reader = UARTReader(verbose=verbose)
            if self.verbose:
                print("[Sensor] 串口读取器初始化成功")
        except Exception as e:
            if self.verbose:
                print(f"[Sensor] 串口初始化失败：{str(e)}")

    def read_sensor_data(self):
        """读取解析传感器数据 内部输出 非阻塞"""
        if not self.uart_reader:
            return
        
        # 控制读取间隔
        current_time = utime.time()
        if current_time - self.last_read < SENSOR_READ_INTERVAL:
            return
        
        try:
            # 1. 读取有效数据帧
            frame = self.uart_reader.find_data_frame(FRAME_HEADER, FRAME_LENGTH, timeout=0.5)
            if not frame:
                if self.verbose:
                    print("[Sensor] 未找到有效帧")
                return
            
            # 2. 校验和验证
            if not (sum(frame[:CHECKSUM_OFFSET]) & 0xFF) == frame[CHECKSUM_OFFSET]:
                if self.verbose:
                    print("[Sensor] 校验和无效")
                self.uart_reader.clear_buffer()
                return
            
            # 3. 解析数据（合并高低字节+格式转换）
            merge = lambda h, l: (frame[h] << 8) | frame[l]
            temp_int = frame[12]
            temp_int = -(temp_int & 0x7F) if (temp_int & 0x80) else temp_int
            data = {
                "co2": merge(2, 3),
                "formaldehyde": merge(4, 5) / 100.0,
                "voc": merge(6, 7) / 100.0,
                "pm2_5": merge(8, 9),
                "pm10": merge(10, 11),
                "temperature": temp_int + frame[13] * 0.1,
                "humidity": frame[14] + frame[15] * 0.1
            }
            
            # 4. 更新时间戳+输出数据
            self.last_read = current_time
            self._print_data(data)
        
        except Exception as e:
            if self.verbose:
                print(f"[Sensor] 读取异常：{str(e)}")
            self.uart_reader.clear_buffer()

    def _print_data(self, data):
        """内部格式化输出数据"""
        print("\n==================================")
        print(" 传感器数据")
        print("==================================")
        print(f"CO2浓度：{data['co2']} ppm")
        print(f"甲醛浓度：{data['formaldehyde']:.2f} mg/m³")
        print(f"VOC浓度：{data['voc']:.2f} mg/m³")
        print(f"PM2.5浓度：{data['pm2_5']} μg/m³")
        print(f"PM10浓度：{data['pm10']} μg/m³")
        print(f"温度：{data['temperature']:.1f} ℃")
        print(f"湿度：{data['humidity']:.1f} %RH")
        print("==================================\n")