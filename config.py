# ==============================================================================
# SmartClock 智能时钟系统配置
# 说明：所有用户可自定义的设置都在此文件中配置
# 注意：修改后需要重启设备才能生效
# ==============================================================================

# ==================== 基础设置 ===================

# 设备名称（显示在系统日志中）
DEVICE_NAME = "我的智能时钟"

# 时区设置（中国一般为8）
TIMEZONE_OFFSET = 8

# 全局调试模式（True=开启详细日志，False=只显示重要信息）
GLOBAL_DEBUG = False


# ==================== 网络连接设置 ===================

# WiFi网络名称（2.4GHz网络）
WIFI_SSID = "l888"

# WiFi密码
WIFI_PASSWORD = "12345678"

# 网络连接超时（秒）
WIFI_TIMEOUT = 30

# 网络调试日志
WIFI_DEBUG = False


# ==================== 天气服务设置 ===================

# 知心天气API密钥（注册地址：https://www.seniverse.com/）
WEATHER_API_KEY = "xxxxxx"

# 天气查询位置（"ip"=自动定位，或直接输入城市名如"北京"）
WEATHER_LOCATION = "ip"

# 天气更新间隔（秒，建议不少于10秒）
WEATHER_UPDATE_INTERVAL = 10

# 天气服务调试日志
WEATHER_DEBUG = False


# ==================== 时间同步设置 ===================

# NTP时间服务器（推荐使用国内服务器）
NTP_SERVER = "ntp.aliyun.com"

# 时间同步间隔（小时）
NTP_SYNC_INTERVAL = 1

# 时间同步超时（秒）
NTP_TIMEOUT = 10

# 时间服务调试日志
NTP_DEBUG = False


# ==================== 屏幕显示设置 ===================

# 串口屏端口号
SCREEN_UART_PORT = 2

# 串口屏通信速率
SCREEN_BAUD_RATE = 115200

# 串口屏TX引脚（连接屏幕的RX）
SCREEN_TX_PIN = 5

# 串口屏RX引脚（连接屏幕的TX）
SCREEN_RX_PIN = 4

# 默认屏幕亮度（0-100）
DEFAULT_BRIGHTNESS = 50

# 屏幕控制调试日志
SCREEN_DEBUG = False


# ==================== 人体感应设置 ===================

# 人体传感器引脚
MOTION_SENSOR_PIN = 0

# 检测间隔（秒）
MOTION_CHECK_INTERVAL = 2

# 无人时自动关屏延迟（秒）
SCREEN_OFF_DELAY = 30

# 人体感应调试日志
MOTION_DEBUG = False


# ==================== 环境光感应设置 ===================

# 光线传感器引脚
LIGHT_SENSOR_PIN = 6

# 检测间隔（秒）
LIGHT_CHECK_INTERVAL = 5

# 最暗环境下的亮度（0-100）
MIN_BRIGHTNESS = 5

# 最亮环境下的亮度（0-100）
MAX_BRIGHTNESS = 90

# 亮度调节平滑度（0.1-1.0，越小越平滑）
BRIGHTNESS_SMOOTHING = 0.3

# 环境光感应调试日志
LIGHT_SENSOR_DEBUG = False


# ==================== 音乐播放设置 ===================

# 播放器TX引脚（连接DFPlayer的RX）
PLAYER_TX_PIN = 7

# 播放器RX引脚（连接DFPlayer的TX）
PLAYER_RX_PIN = 8

# 播放器通信速率
PLAYER_BAUD_RATE = 9600

# 默认音量（0-30）
DEFAULT_VOLUME = 20

# 播放模式（0=全部循环, 1=文件夹循环, 2=单曲循环, 3=随机播放）
PLAYBACK_MODE = 1

# 开机自动播放
AUTO_PLAY_ON_START = True

# 播放器调试日志
PLAYER_DEBUG = False


# ==================== 其他传感器设置 ===================

# 传感器串口端口
SENSOR_UART_PORT = 1

# 传感器通信速率
SENSOR_BAUD_RATE = 9600

# 传感器TX引脚
SENSOR_TX_PIN = 3

# 传感器RX引脚
SENSOR_RX_PIN = 2

# 传感器读取间隔（秒）
SENSOR_READ_INTERVAL = 10

# 传感器调试日志
SENSOR_DEBUG = False


# ==================== 系统性能设置 ===================

# 系统状态检查间隔（秒）
SYSTEM_CHECK_INTERVAL = 5

# 系统调试日志
SYSTEM_DEBUG = False


# ==================== 高级设置（一般用户无需修改） ===================

# 串口通信超时（毫秒）
UART_TIMEOUT = 100

# 串口缓冲区大小
UART_BUFFER_SIZE = 1024

# 临时线程栈大小
THREAD_STACK_SIZE = 8192

# 看门狗超时（秒，0=禁用）
WATCHDOG_TIMEOUT = 30


# ==============================================================================
# 配置说明结束
# 注意：修改此文件后需要重启设备才能生效
# ==============================================================================