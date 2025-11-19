# DFPlayer 测试脚本
import machine
import utime
from function.dfplayer import DFPlayer
from config import DFPLAYER_TX_PIN, DFPLAYER_RX_PIN, DFPLAYER_BAUDRATE

def test_dfplayer():
    print("=== DFPlayer 测试脚本 ===")
    
    # 初始化UART
    uart = machine.UART(
        1,
        baudrate=DFPLAYER_BAUDRATE,
        tx=machine.Pin(DFPLAYER_TX_PIN),
        rx=machine.Pin(DFPLAYER_RX_PIN),
        bits=8,
        parity=None,
        stop=1,
        timeout=1000
    )
    
    # 创建播放器实例
    player = DFPlayer(uart, verbose=True)
    
    # 等待初始化
    utime.sleep(2)
    
    # 初始化
    if player.initialize():
        print("✅ 初始化成功")
        
        # 测试播放
        print("测试播放曲目1...")
        if player.play(1):
            print("✅ 播放命令发送成功")
            utime.sleep(5)  # 等待5秒听是否有声音
            
            # 测试暂停
            print("测试暂停...")
            player.pause()
            utime.sleep(2)
            
            # 测试继续播放
            print("测试继续播放...")
            player.play()
            utime.sleep(3)
            
            # 测试下一首
            print("测试下一首...")
            player.next()
            utime.sleep(3)
            
            player.print_status()
            
        else:
            print("❌ 播放失败")
    else:
        print("❌ 初始化失败")

if __name__ == "__main__":
    test_dfplayer()