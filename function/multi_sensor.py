from util.uart_reader import UARTReader
from config import SENSOR_READ_INTERVAL
import utime
from ui import sent_to_screen

# 传感器协议配置（保持不变）
FRAME_HEADER = [0x3C, 0x02]
FRAME_LENGTH = 17
CHECKSUM_OFFSET = 16

class MultiSensor:
    def __init__(self, uart=None, verbose=True):
        self.verbose = verbose
        self.uart_reader = None
        self.last_read = 0  # 2秒间隔控制
        # 缓存所有数据（包括未传屏幕的）
        self.last_pm25 = None
        self.last_co2 = None
        self.last_tvoc = None
        self.last_formaldehyde = None  # 甲醛缓存
        self.last_pm10 = None          # PM10缓存
        self.last_temperature = None   # 温度缓存
        self.last_humidity = None      # 湿度缓存
        
        try:
            if uart is None:
                raise ValueError("传感器UART实例未传入（需在main中初始化）")
            self.uart_reader = UARTReader(uart=uart, verbose=verbose)
            if self.verbose:
                print("[Sensor] 传感器初始化完成（使用main传入的串口1）")
        
        except Exception as e:
            if self.verbose:
                print(f"[Sensor] 初始化失败：{str(e)}")

    # 核心读取流程（保持之前调整好的逻辑：读前清缓存+2秒间隔+5秒超时）
    def read_sensor_data(self, screen_uart, force=False):
        if not self.uart_reader or not screen_uart:
            if self.verbose:
                print("[Sensor] 读取失败：UARTReader或串口屏未就绪")
            return
        
        # 2秒间隔控制
        current_time = utime.time()
        if not force:
            interval_remaining = self.last_read + 2 - current_time
            if interval_remaining > 0:
                if self.verbose:
                    print(f"[Sensor] 未到2秒间隔（剩余{interval_remaining:.1f}秒）")
                return
        
        try:
            # 读取前清空缓存（关键）
            if self.verbose:
                print("[Sensor] 开始读取 → 清空历史缓存")
            self.uart_reader.clear_buffer()
            
            # 5秒总超时查找有效帧
            total_timeout = 5
            start_find_time = utime.time()
            frame = None
            while utime.time() - start_find_time < total_timeout:
                frame = self.uart_reader.find_data_frame(FRAME_HEADER, FRAME_LENGTH, timeout=0.5)
                if frame:
                    break
                if self.verbose:
                    print(f"[Sensor] 未找到有效帧，继续等待（已耗时{utime.time()-start_find_time:.1f}秒）")
                utime.sleep(0.1)
            
            self.last_read = current_time
            if not frame:
                if self.verbose:
                    print(f"[Sensor] 5秒总超时未找到有效帧（下次2秒后重试）")
                return
            
            # 校验和验证
            checksum_calc = sum(frame[:CHECKSUM_OFFSET]) & 0xFF
            checksum_frame = frame[CHECKSUM_OFFSET]
            if checksum_calc != checksum_frame:
                if self.verbose:
                    print(f"[Sensor] 校验失败（计算0x{checksum_calc:02X}，帧中0x{checksum_frame:02X}）")
                self.uart_reader.clear_buffer()
                return
            
            # 数据解析（包含所有字段）
            merge = lambda h, l: (frame[h] << 8) | frame[l]
            temp_int = frame[12]
            temp_int = -(temp_int & 0x7F) if (temp_int & 0x80) else temp_int
            data = {
                "co2": merge(2, 3),
                "formaldehyde": round(merge(4, 5) / 100.0),  # 甲醛（未传屏幕）
                "tvoc": round(merge(6, 7) / 100.0),
                "pm2_5": merge(8, 9),
                "pm10": merge(10, 11),                       # PM10（未传屏幕）
                "temperature": round(temp_int + frame[13] * 0.1),  # 温度（未传屏幕）
                "humidity": round(frame[14] + frame[15] * 0.1)     # 湿度（未传屏幕）
            }
            
            self._print_data(data)
            self._send_to_screen(screen_uart, data, force)  # 推送数据到屏幕
            
            # 解析成功后清空缓存
            if self.verbose:
                print("[Sensor] 数据解析成功 → 清空缓存")
            self.uart_reader.clear_buffer()
        
        except Exception as e:
            if self.verbose:
                print(f"[Sensor] 读取异常：{str(e)}")
            self.uart_reader.clear_buffer()
            self.last_read = current_time

    # 数据打印（显示所有字段，包括未传屏幕的）
    def _print_data(self, data):
        print("\n==================================")
        print(" 传感器数据（有效帧）")
        print("==================================")
        print(f"CO2浓度：{data['co2']} ppm")
        print(f"甲醛浓度：{data['formaldehyde']} mg/m³")  # 显示未传屏幕的数据
        print(f"TVOC浓度：{data['tvoc']} mg/m³")
        print(f"PM2.5浓度：{data['pm2_5']} μg/m³")
        print(f"PM10浓度：{data['pm10']} μg/m³")        # 显示未传屏幕的数据
        print(f"温度：{data['temperature']} ℃")          # 显示未传屏幕的数据
        print(f"湿度：{data['humidity']} %RH")          # 显示未传屏幕的数据
        print("==================================\n")

    # ========== 核心修改：加入未传屏幕的数据（全部注释掉，留待启用） ==========
    def _send_to_screen(self, screen_uart, data, force=False):
        # 已启用：PM2.5 → t6
        current_pm25 = f"{data['pm2_5']} μg/m³"
        if force or current_pm25 != self.last_pm25:
            sent_to_screen.upload(screen_uart, current_pm25, control_name="t6", property_name="txt")
            self.last_pm25 = current_pm25
            if self.verbose:
                print(f"[Sensor] 发送PM2.5到t6：{current_pm25}")
        
        # 已启用：CO2 → t7
        current_co2 = f"{data['co2']} ppm"
        if force or current_co2 != self.last_co2:
            sent_to_screen.upload(screen_uart, current_co2, control_name="t7", property_name="txt")
            self.last_co2 = current_co2
            if self.verbose:
                print(f"[Sensor] 发送CO2到t7：{current_co2}")
        
        # 已启用：TVOC → t8
        current_tvoc = f"{data['tvoc']} mg/m³"
        if force or current_tvoc != self.last_tvoc:
            sent_to_screen.upload(screen_uart, current_tvoc, control_name="t8", property_name="txt")
            self.last_tvoc = current_tvoc
            if self.verbose:
                print(f"[Sensor] 发送TVOC到t8：{current_tvoc}")
        
        # ========== 注释掉：甲醛 → 预留屏幕控件（比如t9，需根据屏幕配置调整） ==========
        # current_formaldehyde = f"{data['formaldehyde']} mg/m³"
        # if force or current_formaldehyde != self.last_formaldehyde:
        #     sent_to_screen.upload(screen_uart, current_formaldehyde, control_name="t9", property_name="txt")
        #     self.last_formaldehyde = current_formaldehyde
        #     if self.verbose:
        #         print(f"[Sensor] 发送甲醛到t9：{current_formaldehyde}")
        
        # ========== 注释掉：PM10 → 预留屏幕控件（比如t10） ==========
        # current_pm10 = f"{data['pm10']} μg/m³"
        # if force or current_pm10 != self.last_pm10:
        #     sent_to_screen.upload(screen_uart, current_pm10, control_name="t10", property_name="txt")
        #     self.last_pm10 = current_pm10
        #     if self.verbose:
        #         print(f"[Sensor] 发送PM10到t10：{current_pm10}")
        
        # ========== 注释掉：温度 → 预留屏幕控件（比如t11） ==========
        # current_temperature = f"{data['temperature']} ℃"
        # if force or current_temperature != self.last_temperature:
        #     sent_to_screen.upload(screen_uart, current_temperature, control_name="t11", property_name="txt")
        #     self.last_temperature = current_temperature
        #     if self.verbose:
        #         print(f"[Sensor] 发送温度到t11：{current_temperature}")
        
        # ========== 注释掉：湿度 → 预留屏幕控件（比如t12） ==========
        # current_humidity = f"{data['humidity']} %RH"
        # if force or current_humidity != self.last_humidity:
        #     sent_to_screen.upload(screen_uart, current_humidity, control_name="t12", property_name="txt")
        #     self.last_humidity = current_humidity
        #     if self.verbose:
        #         print(f"[Sensor] 发送湿度到t12：{current_humidity}")