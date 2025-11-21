# ==================== 用户配置中心 ====================
# 这个文件是系统的"设置面板"，所有可调参数都在这里
# 使用说明：修改等号右边的值，保存后重启系统即可生效
# 重要提示：字符串用双引号，数字直接写，引脚号必须和硬件一致

# ==================== 快速设置区（最常修改） ====================
# WiFi配置（必须修改，否则无法联网）
WIFI_SSID = "l888"        # WiFi名称：改成你的路由器2.4G网络名
WIFI_PWD = "12345678"     # WiFi密码：至少8位字符

# 天气API配置（必须修改，否则无法获取天气）
# 获取方法：访问https://www.seniverse.com/注册账号，免费获取API密钥
SENIVERSE_KEY = "xxxxxxx"      # API密钥：替换为你申请的密钥
LOCATION = "ip"                      # 城市定位："ip"=自动定位，或写"北京"、"上海"等



# ==================== 功能设置区（按需调整） ====================
# 天气更新频率（秒），建议≥10秒，避免频繁请求耗尽免费额度
WEATHER_REFRESH_INTERVAL = 60*2

# 时间校准频率（小时），建议≥1小时，减少网络请求
NTP_CALIBRATION_HOURS = 1

# 传感器读取频率（秒），建议≥10秒，给传感器休息时间
SENSOR_READ_INTERVAL = 10

# 人体检测频率（秒），建议1-5秒，平衡响应速度和CPU占用
DETECT_INTERVAL = 2

# 屏幕默认亮度（0-100），数字越大越亮
DEFAULT_SCREEN_BRIGHTNESS = 80

# ==================== 硬件连接区（检查接线后修改） ====================
# 空气质量传感器串口（接传感器）
UART_NUM = 1                         # 串口号：通常用1
UART_BAUDRATE = 9600                 # 波特率：必须和传感器一致
UART_TX_PIN = 3                      # TX引脚：接传感器RX（GPIO3）
UART_RX_PIN = 2                      # RX引脚：接传感器TX（GPIO2）

# 串口屏（接屏幕）
SERIAL_PORT = 2                      # 串口号：建议与传感器区分
SERIAL_BAUD_RATE = 115200            # 波特率：必须和屏幕一致
SERIAL_TX_PIN = 5                    # TX引脚：接屏幕RX（GPIO5）
SERIAL_RX_PIN = 4                    # RX引脚：接屏幕TX（GPIO4）

# SR602人体传感器（接模块）
SR602_DATA_PIN = 0                   # 数据引脚：接传感器输出线（GPIO0）

# ==================== 高级设置区（一般不用修改） ====================
# NTP服务器（除非阿里云不能用，否则不要改）
NTP_SERVER = "ntp.aliyun.com"        # 国内推荐，响应快
NTP_TIMEOUT = 10                     # 超时时间：10秒无响应就放弃
TIMEZONE_OFFSET = 8                  # 时区：中国UTC+8，固定值

# 屏幕亮度渐变速度（数字越小变化越慢）
FADE_STEP = 1                        # 步长：每次亮度变化1
FADE_DELAY = 0.02                    # 间隔：每0.02秒变化一次

# 天气API域名（不要修改）
API_DOMAIN = "api.seniverse.com"     # 知心天气官方域名

# ==================== 调试用VERBOSE开关（通常保持False） ====================
# 这些开关控制各模块的详细日志输出，True会打印大量信息，影响性能
VERBOSE_NETWORK = False     # 网络连接日志（WiFi/NTP）
VERBOSE_TIME_PRINT = False  # 控制台时间打印（调试用）
VERBOSE_SCREEN_SEND = False # 屏幕推送日志（显示每个指令）
VERBOSE_NTP = False         # NTP时间同步详细日志
VERBOSE_WEATHER = False     # 天气API请求/响应日志
VERBOSE_SR602 = False       # 人体检测详细日志
VERBOSE_SENSOR = False       # 空气质量传感器详细日志（新增）
VERBOSE_MAIN = False        # 主程序日志：True打印详细过程，False静默运行
VERBOSE_SCREEN = False      # 屏幕日志：True显示按键信息，False不显示