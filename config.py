# ==================== WiFi 配置 ====================
WIFI_SSID = "l888"                # 替换为你的WiFi SSID
WIFI_PWD = "12345678"             # 替换为你的WiFi密码

# ==================== 知心天气配置 ====================
SENIVERSE_KEY = "xxxxx  # 替换为你的知心天气API Key
LOCATION = "ip"                      # 定位方式：ip=自动IP定位，也可填写具体城市名（如"北京"）
API_DOMAIN = "api.seniverse.com"     # 知心天气API域名（无需修改）
API_PATH = f"/v3/weather/now.json?key={SENIVERSE_KEY}&location={LOCATION}&language=zh-Hans&unit=c"
WEATHER_REFRESH_INTERVAL = 10        # 天气数据刷新间隔（单位：秒）

# ==================== NTP时钟配置 ====================
NTP_SERVER = "ntp.aliyun.com"        # 国内稳定NTP服务器（阿里云，访问速度快）
NTP_TIMEOUT = 10                     # NTP同步超时时间（单位：秒）
TIMEZONE_OFFSET = 8                  # 时区偏移（单位：小时，固定UTC+8）

# ==================== 系统调度配置 ====================
NTP_CALIBRATION_HOURS = 1            # NTP校准周期（单位：小时，支持小数）
TIME_PRINT_INTERVAL = 5              # 串口时间输出间隔（单位：秒）

# ==================== 传感器串口配置 ====================
UART_NUM = 2                          # ESP32串口编号（可选0/1/2，根据硬件接线调整）
UART_BAUDRATE = 9600                  # 传感器波特率（需与传感器手册一致，默认9600）
UART_TX_PIN = 17                      # ESP32 TX引脚（连接传感器RX引脚，根据硬件调整）
UART_RX_PIN = 16                      # ESP32 RX引脚（连接传感器TX引脚，根据硬件调整）

# ==================== 传感器读取配置 ====================
SENSOR_READ_INTERVAL = 2              # 传感器数据读取间隔（单位：秒，可根据需求调整）