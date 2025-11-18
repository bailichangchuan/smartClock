# ==================== WiFi 配置 ====================
WIFI_SSID = "l888"                # 替换为你的WiFi SSID
WIFI_PWD = "12345678"             # 替换为你的WiFi密码

# ==================== 知心天气配置 ====================
SENIVERSE_KEY = "xxxxx"  # 替换为你的知心天气API Key
LOCATION = "ip"                      # 定位方式：ip=自动IP定位，也可填写具体城市名
API_DOMAIN = "api.seniverse.com"     # 知心天气API域名 无需修改
API_PATH = f"/v3/weather/now.json?key={SENIVERSE_KEY}&location={LOCATION}&language=zh-Hans&unit=c"
WEATHER_REFRESH_INTERVAL = 10        # 天气数据刷新间隔 单位：秒

# ==================== NTP时钟配置 ====================
NTP_SERVER = "ntp.aliyun.com"        # 国内稳定NTP服务器 阿里云
NTP_TIMEOUT = 10                     # NTP同步超时时间 单位：秒
TIMEZONE_OFFSET = 8                  # 时区偏移 单位：小时 UTC+8

# ==================== 系统调度配置 ====================
NTP_CALIBRATION_HOURS = 1            # NTP校准周期 单位：小时
TIME_PRINT_INTERVAL = 5              # 串口时间输出间隔 单位：秒

# ==================== 串口1配置 ====================
UART_NUM = 1                          # ESP32串口编号 可选0/1/2
UART_BAUDRATE = 9600                  # 传感器波特率 需与传感器手册一致
UART_TX_PIN = 3                      # ESP32 TX引脚 连接传感器RX引脚
UART_RX_PIN = 2                      # ESP32 RX引脚 连接传感器TX引脚

# ==================== 传感器读取配置 ====================
SENSOR_READ_INTERVAL = 2              # 传感器数据读取间隔 单位：秒

# ==================== 串口2配置 ====================
# 可复用传感器串口
SERIAL_PORT = 2               # 串口屏使用的ESP32串口编号
SERIAL_BAUD_RATE = 115200            # 串口屏波特率 需与串口屏配置一致
SERIAL_TX_PIN = 5           # ESP32 TX引脚 连接串口屏RX引脚
SERIAL_RX_PIN = 4          # ESP32 RX引脚 连接串口屏TX引脚