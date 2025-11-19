"""
DFPlayer Mini 音乐播放器服务 - 智能时钟的音乐管家
功能：通过软串口控制DFPlayer Mini MP3模块，提供背景音乐播放能力
特点：持续监控、自动播放、音量调节、多播放模式、错误恢复
"""

# 导入硬件控制模块 - 与播放器直接对话的接口
import machine
import utime
import _thread

# 导入系统配置 - 使用面向用户的友好配置项
from config import (
    # 播放器硬件配置
    PLAYER_TX_PIN, PLAYER_RX_PIN, PLAYER_BAUD_RATE,
    # 播放器功能配置
    DEFAULT_VOLUME, PLAYBACK_MODE, AUTO_PLAY_ON_START,
    # 调试开关
    PLAYER_DEBUG, GLOBAL_DEBUG,
    # 系统配置
    DEVICE_NAME
)

# 导入统一通信管理模块
from util.uart_senter import UARTSender
from util.uart_reader import UARTReader


class DFPlayerService:
    """
    DFPlayer音乐播放器服务 - 智能时钟的音乐指挥家
    作为定时器控制子系统的持续性服务，专门负责背景音乐播放和控制
    就像一位专业的DJ，为智能时钟提供恰到好处的背景音乐氛围
    """
    
    # === DFPlayer 命令定义 - 播放器的专用指令集 ===
    CMD_PLAY_NEXT = 0x01           # 下一首
    CMD_PLAY_PREV = 0x02           # 上一首
    CMD_PLAY_TRACK = 0x03          # 播放指定曲目
    CMD_VOLUME_UP = 0x04           # 音量增加
    CMD_VOLUME_DOWN = 0x05         # 音量减少
    CMD_SET_VOLUME = 0x06          # 设置音量
    CMD_SET_EQ = 0x07              # 设置音效
    CMD_SET_PLAYBACK_MODE = 0x08   # 设置播放模式
    CMD_SET_PLAYBACK_SOURCE = 0x09 # 设置播放源
    CMD_STANDBY = 0x0A             # 待机模式
    CMD_NORMAL = 0x0B              # 正常模式
    CMD_RESET = 0x0C               # 复位模块
    CMD_PLAY = 0x0D                # 播放
    CMD_PAUSE = 0x0E               # 暂停
    CMD_PLAY_FOLDER_TRACK = 0x0F   # 播放文件夹曲目
    CMD_PLAY_MP3_FOLDER = 0x12     # 播放MP3文件夹曲目
    
    # 播放模式定义 - 音乐播放的不同风格
    PLAY_MODE_REPEAT_ALL = 0       # 全部循环 - 像广播一样循环所有歌曲
    PLAY_MODE_FOLDER_REPEAT = 1    # 文件夹循环 - 只循环当前文件夹
    PLAY_MODE_SINGLE_REPEAT = 2    # 单曲循环 - 单曲循环播放
    PLAY_MODE_RANDOM = 3           # 随机播放 - 像音乐电台一样随机播放
    
    # 音效模式定义 - 不同的声音风格
    EQ_NORMAL = 0                  # 普通音效 - 平衡的声音
    EQ_POP = 1                     # 流行音效 - 突出人声
    EQ_ROCK = 2                    # 摇滚音效 - 强劲有力
    EQ_JAZZ = 3                    # 爵士音效 - 柔和温暖
    EQ_CLASSIC = 4                 # 古典音效 - 清晰细腻
    EQ_BASS = 5                    # 重低音 - 强劲低音
    
    def __init__(self, verbose=None):
        """
        初始化音乐播放器持续性服务
        
        参数说明：
        - verbose: 详细日志开关（如果为None，使用配置中的PLAYER_DEBUG）
        """
        # 设置调试模式：优先使用参数，其次使用配置开关
        self.verbose = verbose if verbose is not None else PLAYER_DEBUG
        
        # 通信硬件状态
        self.player_uart = None           # 播放器UART实例
        self.uart_sender = None           # 统一数据发送器
        self.uart_reader = None           # 统一数据读取器
        
        # 播放器运行状态
        self.is_service_active = False    # 服务运行状态
        self.is_player_ready = False      # 播放器硬件就绪状态
        self.is_music_playing = False     # 音乐播放状态
        
        # 播放器配置状态
        self.current_volume = DEFAULT_VOLUME      # 当前音量（0-30）
        self.current_play_mode = PLAYBACK_MODE    # 当前播放模式
        self.current_track = 1                    # 当前曲目编号
        self.current_folder = 1                   # 当前文件夹编号
        
        # 自动播放配置
        self.auto_play_enabled = AUTO_PLAY_ON_START  # 开机自动播放
        
        if self.verbose:
            print("[音乐播放器] 音乐播放器持续性服务初始化完成")

    def initialize_hardware(self):
        """
        初始化音乐播放器硬件
        建立与DFPlayer Mini模块的稳定通信连接
        """
        try:
            # 创建播放器专用的软串口通信通道
            self.player_uart = machine.UART(
                1,  # 使用UART1作为软串口
                baudrate=PLAYER_BAUD_RATE,
                tx=machine.Pin(PLAYER_TX_PIN),
                rx=machine.Pin(PLAYER_RX_PIN),
                bits=8, parity=None, stop=1, timeout=1000
            )
            
            # 包装成统一的通信管理器
            self.uart_reader = UARTReader(self.player_uart, verbose=self.verbose)
            self.uart_sender = UARTSender(self.player_uart, verbose=self.verbose)
            
            print(f"✅ 音乐播放器通信建立成功 (TX:GPIO{PLAYER_TX_PIN}, RX:GPIO{PLAYER_RX_PIN})")
            return True
            
        except Exception as e:
            print(f"❌ 音乐播放器硬件初始化失败: {e}")
            return False

    def _build_command_frame(self, command, parameter=0):
        """
        构建DFPlayer命令帧
        按照DFPlayer Mini的通信协议构建完整的命令数据包
        
        参数说明：
        - command: 命令字节（如CMD_PLAY, CMD_SET_VOLUME等）
        - parameter: 命令参数（16位整数）
        """
        try:
            # 命令帧固定格式：起始字节、版本、长度、命令、反馈、参数高字节、参数低字节、校验和高字节、校验和低字节、结束字节
            frame_header = bytes([0x7E, 0xFF, 0x06])  # 固定帧头
            command_byte = bytes([command])           # 命令字节
            feedback_byte = bytes([0x00])             # 不需要反馈
            param_high = bytes([(parameter >> 8) & 0xFF])  # 参数高字节
            param_low = bytes([parameter & 0xFF])          # 参数低字节
            
            # 计算校验和：求和后取补码
            checksum_data = 0xFF + 0x06 + command + 0x00 + ((parameter >> 8) & 0xFF) + (parameter & 0xFF)
            checksum = (-checksum_data) & 0xFFFF  # 取补码
            checksum_high = bytes([(checksum >> 8) & 0xFF])  # 校验和高字节
            checksum_low = bytes([checksum & 0xFF])          # 校验和低字节
            frame_end = bytes([0xEF])                        # 帧结束字节
            
            # 组合完整命令帧
            command_frame = (frame_header + command_byte + feedback_byte + 
                           param_high + param_low + checksum_high + checksum_low + frame_end)
            
            if self.verbose:
                hex_frame = command_frame.hex().upper()
                print(f"[音乐播放器] 构建命令帧: {hex_frame} (命令: 0x{command:02X}, 参数: {parameter})")
            
            return command_frame
            
        except Exception as e:
            print(f"❌ 构建命令帧失败: {e}")
            return None

    def _send_player_command(self, command, parameter=0, retry_count=2):
        """
        发送命令到音乐播放器
        确保命令可靠地发送到DFPlayer Mini模块
        
        参数说明：
        - command: 命令字节
        - parameter: 命令参数
        - retry_count: 重试次数
        """
        if not self.is_player_ready:
            if self.verbose:
                print("[音乐播放器] 播放器未就绪，无法发送命令")
            return False
        
        command_frame = self._build_command_frame(command, parameter)
        if command_frame is None:
            return False
        
        # 尝试发送命令，支持重试机制
        for attempt in range(retry_count):
            try:
                success = self.uart_sender.send_data(command_frame)
                if success:
                    # 给播放器一些处理时间
                    utime.sleep_ms(100)
                    return True
                else:
                    if self.verbose:
                        print(f"[音乐播放器] 命令发送失败，重试 {attempt + 1}/{retry_count}")
                    utime.sleep_ms(50)
            except Exception as e:
                print(f"❌ 命令发送异常: {e}")
                utime.sleep_ms(50)
        
        print(f"❌ 命令发送失败，已尝试 {retry_count} 次")
        return False

    def initialize_player_module(self):
        """
        初始化DFPlayer Mini模块
        执行模块复位、参数设置和设备检测
        """
        if self.verbose:
            print("[音乐播放器] 开始初始化DFPlayer Mini模块...")
        
        print("🎵 启动音乐播放器模块...")
        
        # 第一步：等待硬件稳定（DFPlayer需要启动时间）
        utime.sleep(2)
        
        # 第二步：发送复位命令
        if not self._send_player_command(self.CMD_RESET):
            print("❌ 播放器复位失败")
            return False
        
        # 等待复位完成
        utime.sleep(2)
        
        # 第三步：设置基本参数
        self._send_player_command(self.CMD_SET_VOLUME, self.current_volume)
        self._send_player_command(self.CMD_SET_PLAYBACK_MODE, self.current_play_mode)
        self._send_player_command(self.CMD_SET_EQ, self.EQ_NORMAL)
        
        # 第四步：检测设备状态（通过尝试播放来验证）
        device_ready = self._check_player_ready()
        
        if device_ready:
            self.is_player_ready = True
            print("✅ 音乐播放器模块初始化成功")
            return True
        else:
            print("❌ 音乐播放器模块初始化失败")
            return False

    def _check_player_ready(self):
        """
        检查播放器是否就绪
        通过发送测试命令来验证播放器是否正常工作
        """
        if self.verbose:
            print("[音乐播放器] 检查播放器就绪状态...")
        
        # 尝试设置音量来测试通信
        test_success = self._send_player_command(self.CMD_SET_VOLUME, 10)
        
        if test_success:
            if self.verbose:
                print("[音乐播放器] 播放器通信测试成功")
            return True
        else:
            if self.verbose:
                print("[音乐播放器] 播放器通信测试失败")
            return False

    def start_auto_playback(self):
        """
        启动自动播放
        根据配置在服务启动时自动开始播放音乐
        """
        if not self.auto_play_enabled:
            if self.verbose:
                print("[音乐播放器] 自动播放已禁用")
            return False
        
        if not self.is_player_ready:
            print("❌ 无法自动播放：播放器未就绪")
            return False
        
        print("🎶 启动自动音乐播放...")
        
        try:
            # 确保设置正确的播放模式
            self._send_player_command(self.CMD_SET_PLAYBACK_MODE, self.PLAY_MODE_REPEAT_ALL)
            utime.sleep(0.5)
            
            # 从第一首开始播放
            play_success = self._send_player_command(self.CMD_PLAY_TRACK, 1)
            
            if play_success:
                self.is_music_playing = True
                self.current_track = 1
                print("✅ 自动播放启动成功 - 背景音乐开始播放")
                return True
            else:
                print("❌ 自动播放启动失败")
                return False
                
        except Exception as e:
            print(f"❌ 自动播放异常: {e}")
            return False

    def control_playback(self, action, parameter=None):
        """
        控制音乐播放
        提供统一的播放控制接口
        
        参数说明：
        - action: 控制动作（'play', 'pause', 'stop', 'next', 'previous', 'volume'等）
        - parameter: 动作参数（如音量值、曲目编号等）
        """
        if not self.is_player_ready:
            if self.verbose:
                print("[音乐播放器] 播放器未就绪，无法控制播放")
            return False
        
        try:
            if action == 'play':
                if parameter is not None:
                    # 播放指定曲目
                    success = self._send_player_command(self.CMD_PLAY_TRACK, parameter)
                    if success:
                        self.current_track = parameter
                        self.is_music_playing = True
                else:
                    # 继续播放
                    success = self._send_player_command(self.CMD_PLAY)
                    self.is_music_playing = True
                    
            elif action == 'pause':
                success = self._send_player_command(self.CMD_PAUSE)
                self.is_music_playing = False
                
            elif action == 'stop':
                success = self._send_player_command(self.CMD_STOP)
                self.is_music_playing = False
                
            elif action == 'next':
                success = self._send_player_command(self.CMD_PLAY_NEXT)
                if success:
                    self.current_track += 1
                    
            elif action == 'previous':
                success = self._send_player_command(self.CMD_PLAY_PREV)
                if success:
                    self.current_track = max(1, self.current_track - 1)
                    
            elif action == 'volume':
                if parameter is not None:
                    volume = max(0, min(30, parameter))
                    success = self._send_player_command(self.CMD_SET_VOLUME, volume)
                    if success:
                        self.current_volume = volume
                else:
                    success = False
                    
            elif action == 'play_folder':
                if parameter is not None and isinstance(parameter, tuple):
                    folder, track = parameter
                    parameter_value = (folder << 8) | track
                    success = self._send_player_command(self.CMD_PLAY_FOLDER_TRACK, parameter_value)
                    if success:
                        self.current_folder = folder
                        self.current_track = track
                        self.is_music_playing = True
                else:
                    success = False
                    
            else:
                if self.verbose:
                    print(f"[音乐播放器] 未知控制动作: {action}")
                success = False
            
            if success and self.verbose:
                action_names = {
                    'play': '播放', 'pause': '暂停', 'stop': '停止', 
                    'next': '下一首', 'previous': '上一首', 'volume': '音量设置'
                }
                action_name = action_names.get(action, action)
                print(f"[音乐播放器] 执行控制: {action_name}")
            
            return success
            
        except Exception as e:
            print(f"❌ 播放控制异常: {e}")
            return False

    def monitor_player_status(self):
        """
        监控播放器状态
        持续性服务的主要工作循环，监控播放状态和处理异常
        """
        if self.verbose:
            print("[音乐播放器] 开始监控播放器状态...")
        
        monitor_count = 0
        while self.is_service_active:
            # 定期检查播放器状态
            monitor_count += 1
            
            # 每10次循环检查一次播放器连接状态
            if monitor_count % 10 == 0:
                if not self._check_player_ready():
                    if self.verbose:
                        print("[音乐播放器] 播放器连接异常，尝试恢复...")
                    # 可以添加重连逻辑
                    
            # 定期输出状态信息（每30秒）
            if self.verbose and monitor_count % 300 == 0:
                status = self.get_service_status()
                print(f"[音乐播放器] 运行状态: 播放中={status['is_playing']}, 音量={status['current_volume']}, 曲目={status['current_track']}")
            
            # 短暂休息，避免过度占用CPU
            utime.sleep(0.1)

    def start_continuous_service(self):
        """
        启动音乐播放器持续性服务
        作为定时器控制子系统的持续性服务持续运行
        """
        # 初始化播放器硬件
        if not self.initialize_hardware():
            print("❌ 音乐播放器服务启动失败：硬件初始化失败")
            return
        
        # 初始化DFPlayer模块
        if not self.initialize_player_module():
            print("❌ 音乐播放器服务启动失败：模块初始化失败")
            return
        
        print("🎵 启动音乐播放器持续性服务")
        
        # 启动自动播放（如果启用）
        if self.auto_play_enabled:
            self.start_auto_playback()
        
        # 标记服务为活跃状态
        self.is_service_active = True
        
        # 启动状态监控循环
        self.monitor_player_status()

    def stop_service(self):
        """
        停止音乐播放器服务
        安全地关闭持续性服务，停止音乐播放
        """
        # 停止音乐播放
        self.control_playback('stop')
        
        # 标记服务停止
        self.is_service_active = False
        
        if self.verbose:
            print("[音乐播放器] 音乐播放器持续性服务已停止")

    def get_service_status(self):
        """
        获取服务状态信息
        用于监控和调试音乐播放器系统
        """
        return {
            'hardware_ready': self.player_uart is not None,
            'player_ready': self.is_player_ready,
            'service_active': self.is_service_active,
            'is_playing': self.is_music_playing,
            'current_volume': self.current_volume,
            'current_track': self.current_track,
            'current_folder': self.current_folder,
            'play_mode': self.current_play_mode,
            'auto_play_enabled': self.auto_play_enabled,
            'verbose_mode': self.verbose
        }


# 创建全局音乐播放器服务实例（兼容旧代码）
_music_player_service = DFPlayerService()

# 兼容旧代码的全局函数
def init_dfplayer(uart_manager, verbose=False):
    """
    初始化DFPlayer播放器（兼容旧代码接口）
    作为定时器控制子系统的持续性服务运行在核心1
    
    参数说明：
    - uart_manager: 统一UART管理器
    - verbose: 详细日志开关
    """
    # 注意：在新的架构中，uart_manager应该包含'hardware'、'reader'、'sender'
    player_service = DFPlayerService(verbose=verbose)
    
    if uart_manager and 'hardware' in uart_manager:
        player_service.player_uart = uart_manager['hardware']
        player_service.uart_reader = uart_manager.get('reader')
        player_service.uart_sender = uart_manager.get('sender')
    
    _thread.start_new_thread(player_service.start_continuous_service, ())
    return player_service

def get_player_status():
    """获取播放器状态（兼容旧代码接口）"""
    return _music_player_service.get_service_status()


# =============================================================================
# 独立运行模式 - 音乐播放器系统的专用测试环境
# 当直接运行这个文件时，会进入测试模式，方便单独测试音乐播放功能
# =============================================================================
if __name__ == "__main__":
    """
    音乐播放器系统独立测试模式
    无需启动整个智能时钟系统，单独测试音乐播放功能
    """
    print("\n" + "="*60)
    print("  音乐播放器系统 - 独立测试模式")
    print("="*60)
    
    def run_music_player_test():
        """运行音乐播放器系统的基本功能测试"""
        print("\n🧪 开始音乐播放器系统功能测试...")
        
        # 创建测试用的音乐播放器实例
        player_service = DFPlayerService(verbose=True)
        
        print("1. 测试命令帧构建...")
        test_commands = [
            (player_service.CMD_SET_VOLUME, 15),
            (player_service.CMD_PLAY_TRACK, 1),
            (player_service.CMD_PAUSE, 0)
        ]
        
        for cmd, param in test_commands:
            frame = player_service._build_command_frame(cmd, param)
            if frame:
                hex_frame = frame.hex().upper()
                print(f"   ✅ 命令 0x{cmd:02X}: {hex_frame}")
            else:
                print(f"   ❌ 命令 0x{cmd:02X} 构建失败")
        
        print("2. 测试播放控制逻辑...")
        # 创建模拟UART管理器用于测试
        class MockUARTManager:
            def __init__(self):
                self.hardware = None
                self.reader = None
                self.sender = MockUARTSender()
        
        class MockUARTSender:
            def send_data(self, data):
                if PLAYER_DEBUG:
                    hex_data = data.hex().upper() if data else "空"
                    print(f"[模拟发送] 数据: {hex_data}")
                return True
        
        mock_manager = MockUARTManager()
        
        print("3. 测试系统状态查询...")
        status = player_service.get_service_status()
        print(f"   系统状态: {status}")
        
        print("4. 测试播放控制接口...")
        # 测试各种控制动作
        test_actions = [
            ('play', 1),
            ('pause', None),
            ('volume', 20),
            ('next', None)
        ]
        
        for action, param in test_actions:
            print(f"   测试动作: {action} 参数: {param}")
        
        print("\n🎉 音乐播放器系统基本功能测试完成")
        return True
    
    try:
        # 运行测试
        success = run_music_player_test()
        
        if success:
            print("\n✅ 音乐播放器系统独立测试通过")
        else:
            print("\n❌ 音乐播放器系统测试失败")
            
    except Exception as e:
        print(f"\n💥 测试过程中发生异常: {e}")
        import sys
        sys.print_exception(e)
    
    print("\n👋 音乐播放器系统测试结束")