# ===导入依赖模块=======
# UART串口读取工具类：负责串口数据帧查找、缓存管理（依赖util/uart_reader.py）
from util.uart_reader import UARTReader
# 配置文件导入：传感器读取间隔（统一管理，避免硬编码）
from config import SENSOR_READ_INTERVAL
# 时间工具模块：提供时间戳（间隔控制）和延时（等待逻辑）功能
import utime
# 串口屏推送工具：封装串口屏数据上传逻辑（负责将传感器数据推送到屏幕控件）
from ui import sent_to_screen

# ===传感器通信协议配置=======
# 数据帧头：传感器输出数据的固定起始标识（多字节帧头，与传感器协议一致）
FRAME_HEADER = [0x3C, 0x02]
# 有效数据帧总长度：完整数据帧的字节数（包含帧头、数据段、校验和，共17字节）
FRAME_LENGTH = 17
# 校验和偏移量：校验和字段在数据帧中的索引（第16字节，0开始计数）
CHECKSUM_OFFSET = 16

# ===多传感器数据处理核心类=======
class MultiSensor:
    """
    多传感器数据处理类：整合传感器数据读取、解析、打印、串口屏推送功能
    核心特性：
    1. 支持CO2、甲醛、TVOC、PM2.5、PM10、温度、湿度7类数据解析
    2. 内置2秒读取间隔控制（避免频繁通信）、5秒帧查找超时（防止阻塞）
    3. 校验和验证（确保数据完整性）、读写前后缓存清空（避免数据干扰）
    4. 服从全局VERBOSE开关，统一控制DEBUG日志输出
    5. 预留未推送数据的串口屏推送逻辑（注释形式，便于后续启用）
    依赖：需外部传入传感器专用UART实例（main.py中初始化的串口1）
    """
    
    # ===类初始化方法=======
    def __init__(self, uart=None, verbose=True):
        """
        初始化多传感器处理实例
        :param uart: 传感器专用UART实例（main.py中初始化的machine.UART对象）
        :param verbose: DEBUG日志控制开关（接收main.py全局VERBOSE参数）
        初始化逻辑：
        1. 接收全局DEBUG控制开关，统一管控当前类所有日志输出
        2. 初始化UARTReader实例（串口数据读取核心）
        3. 初始化读取间隔控制时间戳（避免频繁读取）
        4. 初始化所有数据缓存（已推送/未推送数据，避免重复推送）
        5. 校验UART实例有效性，输出初始化成功/失败日志（受VERBOSE控制）
        """
        # 接收全局DEBUG控制开关（来自main.py，统一管控[Sensor]前缀日志）
        self.verbose = verbose
        # UART数据读取实例：封装串口帧查找、缓存管理逻辑
        self.uart_reader = None
        # 读取间隔控制：记录上一次读取时间戳（控制2秒间隔）
        self.last_read = 0
        # 数据缓存：记录上一次推送至串口屏的数据（避免重复推送）
        self.last_pm25 = None          # PM2.5缓存（已推送）
        self.last_co2 = None           # CO2缓存（已推送）
        self.last_tvoc = None          # TVOC缓存（已推送）
        self.last_formaldehyde = None  # 甲醛缓存（未推送，预留）
        self.last_pm10 = None          # PM10缓存（未推送，预留）
        self.last_temperature = None   # 温度缓存（未推送，预留）
        self.last_humidity = None      # 湿度缓存（未推送，预留）
        
        try:
            # 校验UART实例有效性（必须传入，否则无法与传感器通信）
            if uart is None:
                raise ValueError("必须传入传感器专用的UART实例（需在main中初始化串口1）")
            # 初始化UARTReader：传入传感器UART实例和DEBUG开关
            self.uart_reader = UARTReader(uart=uart, verbose=verbose)
            # DEBUG日志：仅VERBOSE=True时输出初始化成功信息
            if self.verbose:
                print("[Sensor] 传感器处理实例初始化完成（使用main传入的串口1）")
        
        except Exception as e:
            # DEBUG日志：仅VERBOSE=True时输出初始化失败原因
            if self.verbose:
                print(f"[Sensor] 初始化失败：{str(e)}")

    # ===核心方法：传感器数据读取与解析全流程=======
    def read_sensor_data(self, screen_uart, force=False):
        """
        传感器数据读取、解析、验证、推送全流程
        :param screen_uart: 串口屏专用UART实例（main.py中的串口2，用于数据推送）
        :param force: 强制读取标识（True=忽略2秒间隔，立即读取；False=遵循间隔）
        :return: 无返回值（解析成功自动推送至串口屏，失败输出日志）
        核心流程：
        1. 实例就绪校验（UARTReader、串口屏UART必须就绪）
        2. 读取间隔控制（force=False时，确保2秒内仅读取一次）
        3. 读取前缓存清空（避免旧数据干扰）
        4. 5秒总超时查找有效数据帧（循环调用UARTReader.find_data_frame）
        5. 校验和验证（确保数据传输无错误）
        6. 数据解析（拼接高低字节、处理温度正负、计算各参数值）
        7. 数据打印（控制台输出所有解析结果）
        8. 串口屏推送（已启用参数直接推送，未启用参数预留注释）
        9. 解析成功后缓存清空（避免残留数据）
        10. 异常处理（捕获所有异常，清空缓存，更新读取时间戳）
        """
        # 校验核心实例就绪状态（UARTReader=传感器通信，screen_uart=串口屏通信）
        if not self.uart_reader or not screen_uart:
            if self.verbose:
                print("[Sensor] 数据读取失败：UARTReader实例或串口屏UART未就绪")
            return
        
        # 读取间隔控制（非强制模式下，2秒内仅允许读取一次）
        current_time = utime.time()
        if not force:
            # 计算剩余间隔时间（上一次读取时间+2秒 - 当前时间）
            interval_remaining = self.last_read + 2 - current_time
            if interval_remaining > 0:
                if self.verbose:
                    print(f"[Sensor] 未到2秒读取间隔（剩余{interval_remaining:.1f}秒），跳过本次读取")
                return
        
        try:
            # 读取前清空缓存（软件+硬件缓存，避免旧数据干扰新数据解析）
            if self.verbose:
                print("[Sensor] 开始读取传感器数据 → 清空历史缓存")
            self.uart_reader.clear_buffer()
            
            # 5秒总超时查找有效数据帧（循环查找，每次子超时0.5秒）
            total_timeout = 5  # 总超时时间（秒）
            start_find_time = utime.time()  # 查找开始时间戳
            frame = None  # 存储找到的有效数据帧
            while utime.time() - start_find_time < total_timeout:
                # 调用UARTReader查找有效帧（帧头+固定长度匹配，子超时0.5秒）
                frame = self.uart_reader.find_data_frame(FRAME_HEADER, FRAME_LENGTH, timeout=0.5)
                if frame:  # 找到有效帧，跳出循环
                    break
                # DEBUG日志：仅VERBOSE=True时输出等待状态
                if self.verbose:
                    elapsed_time = utime.time() - start_find_time
                    print(f"[Sensor] 未找到有效数据帧，继续等待（已耗时{elapsed_time:.1f}秒）")
                utime.sleep(0.1)  # 短延时，降低CPU占用
            
            # 更新上一次读取时间戳（无论成功与否，避免重复触发）
            self.last_read = current_time
            # 超时未找到有效帧：输出日志并返回
            if not frame:
                if self.verbose:
                    print(f"[Sensor] 5秒总超时未找到有效数据帧（下次将在2秒后重试）")
                return
            
            # 校验和验证：确保数据传输过程无错误（和校验，仅校验低8位）
            # 计算校验和：帧头到校验和前一字节的所有字节求和，与0xFF按位与
            checksum_calc = sum(frame[:CHECKSUM_OFFSET]) & 0xFF
            # 读取帧中校验和字段（第16字节）
            checksum_frame = frame[CHECKSUM_OFFSET]
            # 校验失败：输出日志、清空缓存并返回
            if checksum_calc != checksum_frame:
                if self.verbose:
                    print(f"[Sensor] 数据校验失败：计算值0x{checksum_calc:02X}，帧中值0x{checksum_frame:02X}")
                self.uart_reader.clear_buffer()
                return
            
            # 数据解析：从有效帧中提取各传感器参数（按传感器协议定义的字节位置）
            # 匿名函数：拼接高低字节（高字节左移8位 + 低字节，得到16位数值）
            merge = lambda h, l: (frame[h] << 8) | frame[l]
            # 温度整数部分处理：最高位为1表示负数（补码逻辑）
            temp_int = frame[12]
            temp_int = -(temp_int & 0x7F) if (temp_int & 0x80) else temp_int
            # 解析所有传感器数据（含已推送/未推送字段，单位转换后保留整数）
            data = {
                "co2": merge(2, 3),  # CO2浓度（ppm，无需单位转换）
                "formaldehyde": round(merge(4, 5) / 100.0),  # 甲醛浓度（mg/m³，原始值/100取整）
                "tvoc": round(merge(6, 7) / 100.0),  # TVOC浓度（mg/m³，原始值/100取整）
                "pm2_5": merge(8, 9),  # PM2.5浓度（μg/m³，无需单位转换）
                "pm10": merge(10, 11),  # PM10浓度（μg/m³，无需单位转换）
                "temperature": round(temp_int + frame[13] * 0.1),  # 温度（℃，整数部分+小数部分*0.1取整）
                "humidity": round(frame[14] + frame[15] * 0.1)  # 湿度（%RH，整数部分+小数部分*0.1取整）
            }
            
            # 控制台打印所有解析数据（含未推送字段，便于调试和状态查看）
            self._print_data(data)
            # 推送已启用数据到串口屏（未启用字段预留注释，后续可直接启用）
            self._send_to_screen(screen_uart, data, force)
            
            # 解析成功后清空缓存（避免残留数据影响下一次读取）
            if self.verbose:
                print("[Sensor] 数据解析与推送完成 → 清空缓存")
            self.uart_reader.clear_buffer()
        
        except Exception as e:
            # 捕获所有异常：输出日志、清空缓存、更新读取时间戳
            if self.verbose:
                print(f"[Sensor] 数据读取/解析异常：{str(e)}")
            self.uart_reader.clear_buffer()
            self.last_read = current_time

    # ===辅助方法：控制台打印所有传感器数据=======
    def _print_data(self, data):
        """
        控制台打印所有解析后的传感器数据（含已推送/未推送字段）
        :param data: 解析后的传感器数据字典（key为参数名，value为数值+单位已处理）
        作用：直观展示传感器状态，便于调试（不受VERBOSE控制，必显核心数据）
        """
        print("\n==================================")
        print(" 传感器数据（有效帧解析结果）")
        print("==================================")
        print(f"CO2浓度：{data['co2']} ppm")
        print(f"甲醛浓度：{data['formaldehyde']} mg/m³")
        print(f"TVOC浓度：{data['tvoc']} mg/m³")
        print(f"PM2.5浓度：{data['pm2_5']} μg/m³")
        print(f"PM10浓度：{data['pm10']} μg/m³")
        print(f"温度：{data['temperature']} ℃")
        print(f"湿度：{data['humidity']} %RH")
        print("==================================\n")

    # ===核心方法：传感器数据推送至串口屏=======
    def _send_to_screen(self, screen_uart, data, force=False):
        """
        将传感器数据推送至串口屏指定控件（已启用3个字段，预留4个字段注释）
        :param screen_uart: 串口屏专用UART实例（main.py中的串口2）
        :param data: 解析后的传感器数据字典
        :param force: 强制推送标识（True=忽略缓存，强制更新；False=仅数据变化时推送）
        推送逻辑：
        1. 已启用字段：PM2.5→t6、CO2→t7、TVOC→t8（串口屏控件名称需与硬件配置一致）
        2. 预留字段：甲醛→t9、PM10→t10、温度→t11、湿度→t12（注释形式，启用时取消注释即可）
        3. 重复推送控制：对比缓存值，数据变化或force=True时才推送（减少串口通信量）
        4. DEBUG日志：仅VERBOSE=True时输出推送信息（受全局开关控制）
        """

        utime.sleep_ms(20)

        # 1. 已启用：PM2.5浓度 → 串口屏控件t6（单位：μg/m³）
        current_pm25 = f"{data['pm2_5']} μg/m³"
        # 数据变化或强制推送时执行
        if force or current_pm25 != self.last_pm25:
            # 调用串口屏推送工具，更新控件t6的文本属性
            sent_to_screen.upload(screen_uart, current_pm25, control_name="t6", property_name="txt")
            # 更新缓存值，避免重复推送
            self.last_pm25 = current_pm25
            # DEBUG日志：仅VERBOSE=True时输出推送状态
            if self.verbose:
                print(f"[Sensor] 推送PM2.5数据到串口屏控件t6：{current_pm25}")
        
        # 2. 已启用：CO2浓度 → 串口屏控件t7（单位：ppm）
        current_co2 = f"{data['co2']} ppm"
        if force or current_co2 != self.last_co2:
            sent_to_screen.upload(screen_uart, current_co2, control_name="t7", property_name="txt")
            self.last_co2 = current_co2
            if self.verbose:
                print(f"[Sensor] 推送CO2数据到串口屏控件t7：{current_co2}")
        
        # 3. 已启用：TVOC浓度 → 串口屏控件t8（单位：mg/m³）
        current_tvoc = f"{data['tvoc']} mg/m³"
        if force or current_tvoc != self.last_tvoc:
            sent_to_screen.upload(screen_uart, current_tvoc, control_name="t8", property_name="txt")
            self.last_tvoc = current_tvoc
            if self.verbose:
                print(f"[Sensor] 推送TVOC数据到串口屏控件t8：{current_tvoc}")
        
        # 4. 预留：甲醛浓度 → 串口屏控件t9（启用时取消以下注释，需确保控件t9存在）
        # current_formaldehyde = f"{data['formaldehyde']} mg/m³"
        # if force or current_formaldehyde != self.last_formaldehyde:
        #     sent_to_screen.upload(screen_uart, current_formaldehyde, control_name="t9", property_name="txt")
        #     self.last_formaldehyde = current_formaldehyde
        #     if self.verbose:
        #         print(f"[Sensor] 推送甲醛数据到串口屏控件t9：{current_formaldehyde}")
        
        # 5. 预留：PM10浓度 → 串口屏控件t10（启用时取消以下注释）
        # current_pm10 = f"{data['pm10']} μg/m³"
        # if force or current_pm10 != self.last_pm10:
        #     sent_to_screen.upload(screen_uart, current_pm10, control_name="t10", property_name="txt")
        #     self.last_pm10 = current_pm10
        #     if self.verbose:
        #         print(f"[Sensor] 推送PM10数据到串口屏控件t10：{current_pm10}")
        
        # 6. 预留：温度 → 串口屏控件t11（启用时取消以下注释）
        # current_temperature = f"{data['temperature']} ℃"
        # if force or current_temperature != self.last_temperature:
        #     sent_to_screen.upload(screen_uart, current_temperature, control_name="t11", property_name="txt")
        #     self.last_temperature = current_temperature
        #     if self.verbose:
        #         print(f"[Sensor] 推送温度数据到串口屏控件t11：{current_temperature}")
        
        # 7. 预留：湿度 → 串口屏控件t12（启用时取消以下注释）
        # current_humidity = f"{data['humidity']} %RH"
        # if force or current_humidity != self.last_humidity:
        #     sent_to_screen.upload(screen_uart, current_humidity, control_name="t12", property_name="txt")
        #     self.last_humidity = current_humidity
        #     if self.verbose:
        #         print(f"[Sensor] 推送湿度数据到串口屏控件t12：{current_humidity}")