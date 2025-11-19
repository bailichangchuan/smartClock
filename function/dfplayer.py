# ===DFPlayer Mini MP3 播放器控制模块=======
# 功能：通过软串口控制DFPlayer Mini MP3模块，支持SD卡音乐播放
# 提供完整的外部调用接口，支持播放控制、音量调节、循环模式等

import machine
import utime
import _thread

# 从config.py导入必要参数
from config import (
    DFPLAYER_DEFAULT_VOLUME,
    DFPLAYER_DEFAULT_MODE,
    DFPLAYER_RETRY_COUNT,
    DFPLAYER_RETRY_INTERVAL,
    DFPLAYER_AUTO_PLAY_ON_START,
    DFPLAYER_AUTO_PLAY_DELAY,
    DFPLAYER_START_DELAY,
    VERBOSE
)

# ===DFPlayer 命令定义=======
# DFPlayer Mini 串口通信协议命令
CMD_PLAY_NEXT = 0x01
CMD_PLAY_PREV = 0x02
CMD_PLAY_TRACK = 0x03
CMD_VOLUME_UP = 0x04
CMD_VOLUME_DOWN = 0x05
CMD_SET_VOLUME = 0x06
CMD_SET_EQ = 0x07
CMD_SET_PLAYBACK_MODE = 0x08
CMD_SET_PLAYBACK_SOURCE = 0x09
CMD_STANDBY = 0x0A
CMD_NORMAL = 0x0B
CMD_RESET = 0x0C
CMD_PLAY = 0x0D
CMD_PAUSE = 0x0E
CMD_PLAY_FOLDER_TRACK = 0x0F
CMD_VOLUME_ADJUST = 0x10
CMD_REPEAT_PLAY = 0x11
CMD_PLAY_MP3_FOLDER = 0x12  # 播放MP3文件夹曲目
CMD_PLAY_ADVERT = 0x13      # 插播广告
CMD_PLAY_FOLDER_1000 = 0x14 # 单个文件夹支持1000首
CMD_STOP_ADVERT = 0x15      # 停止广告播放
CMD_STOP = 0x16
CMD_PLAY_FOLDER_REPEAT = 0x17  # 指定文件夹循环播放
CMD_RANDOM_PLAY = 0x18        # 随机播放
CMD_REPEAT_CURRENT = 0x19     # 当前曲目循环播放
CMD_SET_DAC = 0x1A           # 开启/关闭DAC

# 播放模式定义
PLAY_MODE_REPEAT_ALL = 0      # 全部循环
PLAY_MODE_FOLDER_REPEAT = 1   # 文件夹循环  
PLAY_MODE_SINGLE_REPEAT = 2   # 单曲循环
PLAY_MODE_RANDOM = 3          # 随机播放

# 音效模式定义
EQ_NORMAL = 0
EQ_POP = 1
EQ_ROCK = 2
EQ_JAZZ = 3
EQ_CLASSIC = 4
EQ_BASS = 5

# 播放设备定义
DEVICE_U_DISK = 1    # U盘
DEVICE_SD_CARD = 2   # SD卡
DEVICE_AUX = 3       # AUX输入
DEVICE_FLASH = 4     # FLASH存储
DEVICE_SLEEP = 5     # 睡眠模式

class DFPlayer:
    """
    DFPlayer Mini MP3 播放器控制类
    提供完整的MP3播放控制功能接口
    """
    
    def __init__(self, uart, verbose=VERBOSE):
        """
        初始化DFPlayer实例
        :param uart: 软串口实例
        :param verbose: 调试模式开关
        """
        self.uart = uart
        self.verbose = verbose
        self.current_volume = DFPLAYER_DEFAULT_VOLUME
        self.current_mode = DFPLAYER_DEFAULT_MODE
        self.current_track = 1
        self.current_folder = 1
        self.is_playing = False
        self.has_sd_card = False
        self.device_online = 0  # 设备在线状态
        self.auto_play_enabled = DFPLAYER_AUTO_PLAY_ON_START
        self.auto_play_delay = DFPLAYER_AUTO_PLAY_DELAY
        self.start_delay = DFPLAYER_START_DELAY
        
        if self.verbose:
            print(f"[DFPlayer] 初始化DFPlayer Mini MP3模块")
    
    def _send_command(self, cmd, parameter=0, feedback=0):
        """
        发送命令到DFPlayer
        :param cmd: 命令字节
        :param parameter: 参数（16位）
        :param feedback: 是否需要反馈(0-不需要,1-需要)
        :return: 发送成功标识
        """
        try:
            # DFPlayer命令格式：0x7E, 0xFF, 0x06, cmd, feedback, param_high, param_low, checksum_high, checksum_low, 0xEF
            param_high = (parameter >> 8) & 0xFF
            param_low = parameter & 0xFF
            
            # 计算校验和
            checksum = -(0xFF + 0x06 + cmd + feedback + param_high + param_low)
            checksum_high = (checksum >> 8) & 0xFF
            checksum_low = checksum & 0xFF
            
            # 构建命令帧
            command_frame = bytes([
                0x7E, 0xFF, 0x06, cmd, feedback, 
                param_high, param_low, 
                checksum_high, checksum_low, 0xEF
            ])
            
            # 发送命令
            self.uart.write(command_frame)
            
            if self.verbose:
                print(f"[DFPlayer CMD] 发送命令: 0x{cmd:02X}, 参数: {parameter:04X}, 反馈: {feedback}")
            
            # 等待命令处理
            utime.sleep(0.1)
            return True
            
        except Exception as e:
            print(f"[DFPlayer ERROR] 发送命令失败: {e}")
            return False

    # ==================== 核心初始化与自动播放接口 ====================
    
    def initialize(self):
        """初始化DFPlayer模块并处理自动播放"""
        print("[DFPlayer] 开始初始化DFPlayer Mini MP3模块...")
        
        # 等待硬件启动
        print(f"[DFPlayer] 等待硬件启动 {self.start_delay} 秒...")
        utime.sleep(self.start_delay)
        
        # 重置模块
        if not self._send_command(CMD_RESET):
            print("[DFPlayer ERROR] 重置模块失败")
            return False
        
        utime.sleep(2)  # 等待重置完成
        
        # 检测设备状态
        self._check_device_status()
        
        # 设置默认参数
        self.set_volume(DFPLAYER_DEFAULT_VOLUME)
        self.set_playback_mode(DFPLAYER_DEFAULT_MODE)
        self.set_eq(EQ_NORMAL)
        
        # 处理自动播放
        if self.auto_play_enabled and self.has_sd_card:
            print("[DFPlayer] 自动播放已启用，开始处理自动播放逻辑...")
            self._handle_autoplay()
        elif self.auto_play_enabled and not self.has_sd_card:
            print("[DFPlayer WARNING] 自动播放已启用但未检测到SD卡，跳过自动播放")
        else:
            print("[DFPlayer] 自动播放已禁用")
        
        if self.has_sd_card:
            print("[DFPlayer] 初始化完成 - SD卡就绪")
        else:
            print("[DFPlayer] 初始化完成 - 基本功能就绪（无SD卡）")
        
        return True
    
    def _handle_autoplay(self):
        """处理自动播放逻辑"""
        print(f"[DFPlayer] 自动播放配置：开机播放={self.auto_play_enabled}")
        
        if not self.auto_play_enabled:
            print("[DFPlayer] 自动播放已禁用")
            return False
            
        if not self.has_sd_card:
            print("[DFPlayer ERROR] 无法自动播放：SD卡未插入")
            return False
        
        # 等待自动播放延迟
        print(f"[DFPlayer] 等待 {self.auto_play_delay} 秒后开始播放...")
        utime.sleep(self.auto_play_delay)
        
        try:
            # 确保设置循环模式为全部循环
            print("[DFPlayer] 设置循环模式为全部循环")
            success = self.set_playback_mode(PLAY_MODE_REPEAT_ALL)
            if not success:
                print("[DFPlayer WARNING] 设置循环模式失败，继续尝试播放")
            
            utime.sleep(0.5)
            
            # 从第一首开始播放
            print("[DFPlayer] 开始播放第一首曲目")
            success = self.play(1)
            
            if success:
                print("✅ DFPlayer 自动播放启动成功 - 将连续播放所有曲目")
                self.is_playing = True
            else:
                print("❌ DFPlayer 自动播放启动失败")
            
            return success
            
        except Exception as e:
            print(f"[DFPlayer ERROR] 自动播放失败: {e}")
            return False

    # ==================== 基础播放控制接口 ====================
    
    def play(self, track=None):
        """
        播放指定曲目
        :param track: 曲目编号（1-2999），None则继续播放
        """
        if not self.has_sd_card:
            print("[DFPlayer ERROR] 无法播放：未检测到SD卡")
            return False
            
        if track is not None:
            if track < 1:
                track = 1
            self.current_track = track
            success = self._send_command(CMD_PLAY_TRACK, track)
        else:
            success = self._send_command(CMD_PLAY)
        
        if success:
            self.is_playing = True
            if self.verbose:
                print(f"[DFPlayer] 播放曲目: {self.current_track}")
        return success
    
    def pause(self):
        """暂停播放"""
        success = self._send_command(CMD_PAUSE)
        if success:
            self.is_playing = False
            if self.verbose:
                print("[DFPlayer] 暂停播放")
        return success
    
    def stop(self):
        """停止播放"""
        success = self._send_command(CMD_STOP)
        if success:
            self.is_playing = False
            if self.verbose:
                print("[DFPlayer] 停止播放")
        return success
    
    def next(self):
        """下一首"""
        if not self.has_sd_card:
            print("[DFPlayer ERROR] 无法切换：未检测到SD卡")
            return False
            
        success = self._send_command(CMD_PLAY_NEXT)
        if success:
            self.current_track += 1
            if self.verbose:
                print(f"[DFPlayer] 下一首: {self.current_track}")
        return success
    
    def previous(self):
        """上一首"""
        if not self.has_sd_card:
            print("[DFPlayer ERROR] 无法切换：未检测到SD卡")
            return False
            
        success = self._send_command(CMD_PLAY_PREV)
        if success:
            self.current_track = max(1, self.current_track - 1)
            if self.verbose:
                print(f"[DFPlayer] 上一首: {self.current_track}")
        return success

    # ==================== 音量控制接口 ====================
    
    def set_volume(self, volume):
        """
        设置音量
        :param volume: 音量值（0-30）
        """
        volume = max(0, min(30, volume))
        success = self._send_command(CMD_SET_VOLUME, volume)
        if success:
            self.current_volume = volume
            if self.verbose:
                print(f"[DFPlayer] 设置音量: {volume}/30")
        return success
    
    def volume_up(self):
        """音量增加"""
        new_volume = min(30, self.current_volume + 1)
        return self.set_volume(new_volume)
    
    def volume_down(self):
        """音量减小"""
        new_volume = max(0, self.current_volume - 1)
        return self.set_volume(new_volume)

    # ==================== 播放模式接口 ====================
    
    def set_playback_mode(self, mode):
        """
        设置播放模式
        :param mode: 播放模式（0-全部循环, 1-文件夹循环, 2-单曲循环, 3-随机播放）
        """
        mode = max(0, min(3, mode))
        success = self._send_command(CMD_SET_PLAYBACK_MODE, mode)
        if success:
            self.current_mode = mode
            mode_names = ["全部循环", "文件夹循环", "单曲循环", "随机播放"]
            if self.verbose:
                print(f"[DFPlayer] 设置播放模式: {mode_names[mode]}")
        return success
    
    def set_eq(self, eq_mode):
        """
        设置音效模式
        :param eq_mode: 音效模式（0-普通, 1-流行, 2-摇滚, 3-爵士, 4-古典, 5-重低音）
        """
        eq_mode = max(0, min(5, eq_mode))
        success = self._send_command(CMD_SET_EQ, eq_mode)
        if success:
            eq_names = ["普通", "流行", "摇滚", "爵士", "古典", "重低音"]
            if self.verbose:
                print(f"[DFPlayer] 设置音效: {eq_names[eq_mode]}")
        return success

    # ==================== 文件管理接口 ====================
    
    def play_folder(self, folder, track):
        """
        播放指定文件夹中的曲目
        :param folder: 文件夹编号（1-99）
        :param track: 曲目编号（1-255）
        """
        if not self.has_sd_card:
            print("[DFPlayer ERROR] 无法播放：未检测到SD卡")
            return False
            
        folder = max(1, min(99, folder))
        track = max(1, min(255, track))
        parameter = (folder << 8) | track
        success = self._send_command(CMD_PLAY_FOLDER_TRACK, parameter)
        if success:
            self.current_folder = folder
            self.current_track = track
            self.is_playing = True
            if self.verbose:
                print(f"[DFPlayer] 播放文件夹{folder}中的曲目{track}")
        return success
    
    def play_mp3_folder(self, track):
        """
        播放MP3文件夹中的曲目（支持0-9999首）
        :param track: 曲目编号（1-9999）
        """
        if not self.has_sd_card:
            print("[DFPlayer ERROR] 无法播放：未检测到SD卡")
            return False
            
        track = max(1, min(9999, track))
        success = self._send_command(CMD_PLAY_MP3_FOLDER, track)
        if success:
            self.current_track = track
            self.is_playing = True
            if self.verbose:
                print(f"[DFPlayer] 播放MP3文件夹中的曲目{track}")
        return success
    
    def play_folder_1000(self, folder, track):
        """
        播放指定文件夹中的曲目（支持1000首）
        :param folder: 文件夹编号（1-15）
        :param track: 曲目编号（1-1000）
        """
        if not self.has_sd_card:
            print("[DFPlayer ERROR] 无法播放：未检测到SD卡")
            return False
            
        folder = max(1, min(15, folder))
        track = max(1, min(1000, track))
        # 参数格式：高4位为文件夹编号，低12位为曲目编号
        parameter = ((folder & 0x0F) << 12) | (track & 0x0FFF)
        success = self._send_command(CMD_PLAY_FOLDER_1000, parameter)
        if success:
            self.current_folder = folder
            self.current_track = track
            self.is_playing = True
            if self.verbose:
                print(f"[DFPlayer] 播放文件夹{folder}中的曲目{track}（1000首模式）")
        return success

    # ==================== 高级播放功能接口 ====================
    
    def play_advert(self, track):
        """
        插播广告（暂停背景音乐，播放广告后恢复）
        :param track: 广告曲目编号（1-9999）
        """
        if not self.has_sd_card:
            print("[DFPlayer ERROR] 无法播放：未检测到SD卡")
            return False
            
        track = max(1, min(9999, track))
        success = self._send_command(CMD_PLAY_ADVERT, track)
        if success and self.verbose:
            print(f"[DFPlayer] 插播广告曲目: {track}")
        return success
    
    def stop_advert(self):
        """停止广告播放，恢复背景音乐"""
        success = self._send_command(CMD_STOP_ADVERT)
        if success and self.verbose:
            print("[DFPlayer] 停止广告播放，恢复背景音乐")
        return success
    
    def play_folder_repeat(self, folder):
        """
        指定文件夹循环播放
        :param folder: 文件夹编号（1-99）
        """
        if not self.has_sd_card:
            print("[DFPlayer ERROR] 无法播放：未检测到SD卡")
            return False
            
        folder = max(1, min(99, folder))
        success = self._send_command(CMD_PLAY_FOLDER_REPEAT, folder)
        if success:
            self.current_folder = folder
            self.is_playing = True
            if self.verbose:
                print(f"[DFPlayer] 循环播放文件夹{folder}")
        return success
    
    def set_random_play(self):
        """随机播放设备中的所有文件"""
        if not self.has_sd_card:
            print("[DFPlayer ERROR] 无法播放：未检测到SD卡")
            return False
            
        success = self._send_command(CMD_RANDOM_PLAY)
        if success:
            self.is_playing = True
            if self.verbose:
                print("[DFPlayer] 随机播放模式")
        return success
    
    def set_repeat_current(self, enable=True):
        """
        设置当前曲目循环播放
        :param enable: True-开启循环，False-关闭循环
        """
        parameter = 0 if enable else 1
        success = self._send_command(CMD_REPEAT_CURRENT, parameter)
        if success and self.verbose:
            state = "开启" if enable else "关闭"
            print(f"[DFPlayer] {state}当前曲目循环播放")
        return True

    # ==================== 设备控制接口 ====================
    
    def set_playback_device(self, device):
        """
        设置播放设备
        :param device: 设备类型（1-U盘, 2-SD卡, 3-AUX, 4-FLASH, 5-睡眠）
        """
        device = max(1, min(5, device))
        success = self._send_command(CMD_SET_PLAYBACK_SOURCE, device)
        if success:
            device_names = ["", "U盘", "SD卡", "AUX", "FLASH", "睡眠"]
            if self.verbose:
                print(f"[DFPlayer] 设置播放设备: {device_names[device]}")
            utime.sleep(0.2)  # 等待设备切换完成
        return success
    
    def set_dac(self, enable=True):
        """
        开启/关闭DAC输出
        :param enable: True-开启DAC，False-关闭DAC（高阻态）
        """
        parameter = 0 if enable else 1
        success = self._send_command(CMD_SET_DAC, parameter)
        if success and self.verbose:
            state = "开启" if enable else "关闭"
            print(f"[DFPlayer] {state}DAC输出")
        return success
    
    def reset(self):
        """复位模块"""
        success = self._send_command(CMD_RESET)
        if success:
            if self.verbose:
                print("[DFPlayer] 模块复位")
            utime.sleep(2)  # 等待复位完成
        return success
    
    def sleep(self):
        """进入睡眠模式"""
        success = self._send_command(CMD_STANDBY)
        if success and self.verbose:
            print("[DFPlayer] 进入睡眠模式")
        return success
    
    def wakeup(self):
        """从睡眠模式唤醒"""
        success = self._send_command(CMD_NORMAL)
        if success and self.verbose:
            print("[DFPlayer] 从睡眠模式唤醒")
        return success

    # ==================== 状态查询接口 ====================
    
    def _check_device_status(self):
        """检测设备状态"""
        print("[DFPlayer] 检测设备状态...")
        self.has_sd_card = False
        
        # 尝试与设备通信
        for i in range(DFPLAYER_RETRY_COUNT):
            # 尝试设置音量来检测设备响应
            if self._send_command(CMD_SET_VOLUME, 10):
                self.has_sd_card = True
                print("[DFPlayer] SD卡检测成功 - 设备响应正常")
                break
            
            print(f"[DFPlayer] 设备检测重试 {i+1}/{DFPLAYER_RETRY_COUNT}")
            utime.sleep(DFPLAYER_RETRY_INTERVAL)
        
        if not self.has_sd_card:
            print("[DFPlayer WARNING] 未检测到SD卡或设备无响应")
    
    def get_status(self):
        """
        获取播放器状态
        :return: 状态字典
        """
        return {
            'has_sd_card': self.has_sd_card,
            'is_playing': self.is_playing,
            'current_track': self.current_track,
            'current_folder': self.current_folder,
            'current_volume': self.current_volume,
            'current_mode': self.current_mode,
            'device_online': self.device_online
        }
    
    def print_status(self):
        """打印当前状态信息"""
        status = self.get_status()
        mode_names = ["全部循环", "文件夹循环", "单曲循环", "随机播放"]
        
        print("\n=== DFPlayer 状态信息 ===")
        print(f"SD卡状态: {'已插入' if status['has_sd_card'] else '未插入'}")
        print(f"播放状态: {'播放中' if status['is_playing'] else '暂停/停止'}")
        print(f"当前曲目: {status['current_track']}")
        print(f"当前文件夹: {status['current_folder']}")
        print(f"当前音量: {status['current_volume']}/30")
        print(f"播放模式: {mode_names[status['current_mode']]}")
        print("========================\n")

# ===全局DFPlayer实例=======
dfplayer_instance = None

# ===外部调用接口函数=======
def init_dfplayer(uart, verbose=VERBOSE):
    """初始化DFPlayer模块"""
    global dfplayer_instance
    dfplayer_instance = DFPlayer(uart, verbose)
    return dfplayer_instance.initialize()  # 修复：直接调用initialize

# 基础播放控制接口
def play(track=None): return dfplayer_instance.play(track) if dfplayer_instance else False
def pause(): return dfplayer_instance.pause() if dfplayer_instance else False
def stop(): return dfplayer_instance.stop() if dfplayer_instance else False
def next_track(): return dfplayer_instance.next() if dfplayer_instance else False
def previous_track(): return dfplayer_instance.previous() if dfplayer_instance else False

# 音量控制接口
def set_volume(volume): return dfplayer_instance.set_volume(volume) if dfplayer_instance else False
def volume_up(): return dfplayer_instance.volume_up() if dfplayer_instance else False
def volume_down(): return dfplayer_instance.volume_down() if dfplayer_instance else False

# 播放模式接口
def set_playback_mode(mode): return dfplayer_instance.set_playback_mode(mode) if dfplayer_instance else False
def set_eq(eq_mode): return dfplayer_instance.set_eq(eq_mode) if dfplayer_instance else False

# 文件管理接口
def play_folder(folder, track): return dfplayer_instance.play_folder(folder, track) if dfplayer_instance else False
def play_mp3_folder(track): return dfplayer_instance.play_mp3_folder(track) if dfplayer_instance else False
def play_folder_1000(folder, track): return dfplayer_instance.play_folder_1000(folder, track) if dfplayer_instance else False

# 高级播放功能接口
def play_advert(track): return dfplayer_instance.play_advert(track) if dfplayer_instance else False
def stop_advert(): return dfplayer_instance.stop_advert() if dfplayer_instance else False
def play_folder_repeat(folder): return dfplayer_instance.play_folder_repeat(folder) if dfplayer_instance else False
def set_random_play(): return dfplayer_instance.set_random_play() if dfplayer_instance else False
def set_repeat_current(enable=True): return dfplayer_instance.set_repeat_current(enable) if dfplayer_instance else False

# 设备控制接口
def set_playback_device(device): return dfplayer_instance.set_playback_device(device) if dfplayer_instance else False
def set_dac(enable=True): return dfplayer_instance.set_dac(enable) if dfplayer_instance else False
def reset(): return dfplayer_instance.reset() if dfplayer_instance else False
def sleep(): return dfplayer_instance.sleep() if dfplayer_instance else False
def wakeup(): return dfplayer_instance.wakeup() if dfplayer_instance else False

# 状态查询接口
def get_status(): return dfplayer_instance.get_status() if dfplayer_instance else None
def print_status(): dfplayer_instance.print_status() if dfplayer_instance else print("[DFPlayer] 播放器未初始化")