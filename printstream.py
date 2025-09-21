import threading
import time
import math
import sys
import atexit
from typing import Any

class PrintStream:
    """动态速度打印流系统"""
    def __init__(self):
        self.print_buffer = ""
        self.temp_buffer = ""
        self.lock = threading.Lock()
        self.running = False
        self.buffer_thread = None
        self.output_thread = None
        self.min_speed = 5.0
        self.max_speed = 50.0
        self.decay_factor = 20.0
        self.smoothing_factor = 0.8
        self.current_speed = self.min_speed
        self.accumulated_chars = 0.0
        self._started = False

    def start(self):
        """启动打印流系统"""
        if not self.running and not self._started:
            self.running = True
            self._started = True
            self.buffer_thread = threading.Thread(target=self._buffer_updater, daemon=True)
            self.output_thread = threading.Thread(target=self._output_processor, daemon=True)
            self.buffer_thread.start()
            self.output_thread.start()

    def stop(self):
        """停止打印流系统"""
        if self.running:
            self.running = False
            # 等待缓冲区输出完毕
            max_wait = 5.0  # 最多等待5秒
            start_time = time.time()
            while self.temp_buffer and (time.time() - start_time) < max_wait:
                time.sleep(0.1)
            
            if self.buffer_thread and self.buffer_thread.is_alive():
                self.buffer_thread.join(timeout=1)
            if self.output_thread and self.output_thread.is_alive():
                self.output_thread.join(timeout=1)

    def add_to_buffer(self, text: str):
        """添加文本到缓冲区"""
        if not self.running:
            self.start()
        
        with self.lock:
            self.print_buffer += str(text)

    def flush_remaining(self):
        """立即输出剩余缓冲区内容"""
        with self.lock:
            if self.print_buffer:
                self.temp_buffer += self.print_buffer
                self.print_buffer = ""
            if self.temp_buffer:
                sys.stdout.write(self.temp_buffer)
                sys.stdout.flush()
                self.temp_buffer = ""

    def _calculate_dynamic_speed(self, buffer_length: int) -> float:
        """计算动态输出速度"""
        if buffer_length <= 0:
            return self.min_speed
        exp_component = 1 - math.exp(-buffer_length / self.decay_factor)
        log_component = math.log(1 + buffer_length) / math.log(1 + self.decay_factor)
        combined_factor = 2 * exp_component * log_component / (exp_component + log_component + 1e-6)
        target_speed = self.min_speed + (self.max_speed - self.min_speed) * combined_factor
        smooth_speed = (self.smoothing_factor * self.current_speed + 
                       (1 - self.smoothing_factor) * target_speed)
        self.current_speed = smooth_speed
        return smooth_speed

    def _buffer_updater(self):
        """缓冲区更新线程"""
        while self.running:
            try:
                time.sleep(1)
                with self.lock:
                    if self.print_buffer:
                        self.temp_buffer += self.print_buffer
                        self.print_buffer = ""
            except Exception:
                pass  # 静默处理错误

    def _output_processor(self):
        """输出处理线程"""
        while self.running:
            try:
                with self.lock:
                    if self.temp_buffer:
                        buffer_length = len(self.temp_buffer)
                        dynamic_speed = self._calculate_dynamic_speed(buffer_length)
                        chars_to_output = buffer_length / dynamic_speed + self.accumulated_chars
                        actual_chars = int(chars_to_output)
                        self.accumulated_chars = chars_to_output - actual_chars
                        if actual_chars > 0:
                            chars_to_print = min(actual_chars, buffer_length)
                            to_print = self.temp_buffer[:chars_to_print]
                            self.temp_buffer = self.temp_buffer[chars_to_print:]
                            sys.stdout.write(to_print)
                            sys.stdout.flush()
                time.sleep(0.02)
            except Exception:
                pass  # 静默处理错误

    @property
    def buffer_size(self) -> int:
        """获取当前缓冲区大小"""
        with self.lock:
            return len(self.print_buffer) + len(self.temp_buffer)

    @property
    def is_running(self) -> bool:
        """检查系统是否正在运行"""
        return self.running

# 创建全局实例
_global_print_stream = PrintStream()

def print_stream(*args, sep: str = ' ', end: str = '\n', flush: bool = False) -> None:
    """
    动态速度打印函数
    
    Args:
        *args: 要打印的内容
        sep: 分隔符，默认为空格
        end: 结尾字符，默认为换行符
        flush: 是否立即刷新，默认为False
    """
    try:
        # 确保系统已启动
        if not _global_print_stream.is_running:
            _global_print_stream.start()
        
        # 组合输出内容
        text = sep.join(str(arg) for arg in args) + end
        
        if flush:
            # 立即输出
            sys.stdout.write(text)
            sys.stdout.flush()
        else:
            # 添加到缓冲区
            _global_print_stream.add_to_buffer(text)
            
    except Exception as e:
        # 如果出错，回退到标准打印
        print(*args, sep=sep, end=end)

def start_print_stream() -> None:
    """手动启动打印流系统"""
    _global_print_stream.start()

def stop_print_stream() -> None:
    """停止打印流系统"""
    _global_print_stream.stop()

def flush_print_stream() -> None:
    """立即输出所有缓冲区内容"""
    _global_print_stream.flush_remaining()

def get_buffer_size() -> int:
    """获取当前缓冲区大小"""
    return _global_print_stream.buffer_size

def is_print_stream_running() -> bool:
    """检查打印流系统是否正在运行"""
    return _global_print_stream.is_running

def set_print_speed(min_speed: float = 5.0, max_speed: float = 50.0) -> None:
    """
    设置打印速度范围
    
    Args:
        min_speed: 最小打印速度（字符/秒）
        max_speed: 最大打印速度（字符/秒）
    """
    _global_print_stream.min_speed = max(1.0, min_speed)
    _global_print_stream.max_speed = max(_global_print_stream.min_speed, max_speed)

def configure_print_stream(min_speed: float = 5.0, max_speed: float = 50.0, 
                          decay_factor: float = 20.0, smoothing_factor: float = 0.8) -> None:
    """
    配置打印流系统参数
    
    Args:
        min_speed: 最小打印速度
        max_speed: 最大打印速度  
        decay_factor: 衰减因子
        smoothing_factor: 平滑因子
    """
    _global_print_stream.min_speed = max(1.0, min_speed)
    _global_print_stream.max_speed = max(_global_print_stream.min_speed, max_speed)
    _global_print_stream.decay_factor = max(1.0, decay_factor)
    _global_print_stream.smoothing_factor = max(0.1, min(0.99, smoothing_factor))

# 注册退出时的清理函数
def _cleanup():
    """程序退出时的清理函数"""
    try:
        _global_print_stream.flush_remaining()
        _global_print_stream.stop()
    except Exception:
        pass

atexit.register(_cleanup)

# 导出的所有函数和类
__all__ = [
    'print_stream',
    'start_print_stream', 
    'stop_print_stream',
    'flush_print_stream',
    'get_buffer_size',
    'is_print_stream_running',
    'set_print_speed',
    'configure_print_stream',
    'PrintStream'
]
