WIFI_SSID = "l888"       # 替换为你的WiFi SSID

WIFI_PWD = "12345678"        # 替换为你的WiFi密码
SENIVERSE_KEY = "S-3j5IWHEJFx2GkZv"  # 替换为你的知心天气API Key
LOCATION = "101320101"  # 香港固定城市ID
# 知心天气API的域名和路径
API_DOMAIN = "api.seniverse.com"
API_PATH = f"/v3/weather/now.json?key={SENIVERSE_KEY}&location={LOCATION}&language=zh-Hans&unit=c"
REFRESH_INTERVAL = 10  # 每10秒刷新（无需修改）