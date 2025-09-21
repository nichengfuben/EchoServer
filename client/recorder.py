import time
import threading
import random
import queue
from pynput import mouse, keyboard
from pynput.mouse import Button, Listener as MouseListener
from pynput.keyboard import Key, Listener as KeyboardListener, KeyCode
from pynput.mouse import Controller as MouseController
from pynput.keyboard import Controller as KeyboardController

TIMES = 899

class ActionRecorder:
    def __init__(self):
        self.actions = []
        self.recording = False
        self.mouse_controller = MouseController()
        self.keyboard_controller = KeyboardController()
        self.ctrl_pressed = False
        self.last_mouse_pos = None
        self.action_queue = queue.Queue()
        self.processing_thread = None
        
    def start_recording(self):
        print("=== 键鼠动作录制与重放工具 ===")
        print("说明：")
        print("1. 按回车开始录制")
        print("2. 录制您的键盘和鼠标操作（操作间隔严格相等，所有操作严格一致）")
        print("3. 按Ctrl+C停止录制")
        print("4. 自动重放（不包括最后两个按键）")
        print("5. 每个鼠标位置随机偏移（-1, 1）")
        print("----------------------------------------")
        print("按回车键开始录制...")
        
        # 等待回车键
        input()
        
        print("开始录制... (按Ctrl+C停止)")
        self.recording = True
        self.actions = []
        self.last_mouse_pos = None
        
        # 启动处理线程
        self.processing_thread = threading.Thread(target=self.process_actions)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        
        # 开始监听 - 使用with语句确保监听器正确管理
        with MouseListener(
            on_move=self.on_mouse_move,
            on_click=self.on_mouse_click,
            on_scroll=self.on_mouse_scroll
        ) as mouse_listener, KeyboardListener(
            on_press=self.on_key_press,
            on_release=self.on_key_release
        ) as keyboard_listener:
            
            try:
                while self.recording:
                    time.sleep(0)  # 减小延迟，提高响应速度
            except KeyboardInterrupt:
                pass
        
        # 等待队列处理完成
        time.sleep(0.1)
        
        print("\n检测到Ctrl+C，停止录制...")
        print(f"\n录制完成! 共录制了 {len(self.actions)} 个动作")
        
        # 移除最后的Ctrl+C相关动作
        if len(self.actions) >= 2:
            # 查找最后的Ctrl和C键相关动作
            ctrl_c_actions = 0
            for i in range(len(self.actions) - 1, -1, -1):
                action = self.actions[i]
                if action['type'] in ['key_press', 'key_release']:
                    if action['key'] in [Key.ctrl_l, Key.ctrl_r] or \
                       (hasattr(action['key'], 'char') and action['key'].char == 'c'):
                        ctrl_c_actions += 1
                        if ctrl_c_actions >= 4:  # Ctrl按下、C按下、C释放、Ctrl释放
                            break
            
            if ctrl_c_actions > 0:
                self.actions = self.actions[:-ctrl_c_actions]
        
        print(f"开始重放... (共 {len(self.actions)} 个动作)")
        
        # 重放
        for i in range(TIMES):
            print(f"第 {i+1}/{TIMES} 遍重放...")
            self.replay_actions()
            if i < TIMES - 1:
                time.sleep(0.5)  # 每次重放之间稍微停顿
        
        print("重放完成!")
    
    def process_actions(self):
        """处理动作队列的线程"""
        while self.recording or not self.action_queue.empty():
            try:
                action = self.action_queue.get(timeout=0.01)
                self.actions.append(action)
            except queue.Empty:
                continue
    
    def on_mouse_move(self, x, y):
        if self.recording:
            self.action_queue.put({
                'type': 'mouse_move',
                'x': x,
                'y': y,
                'timestamp': time.perf_counter()  # 使用更精确的计时器
            })
            self.last_mouse_pos = (x, y)
    
    def on_mouse_click(self, x, y, button, pressed):
        if self.recording:
            self.action_queue.put({
                'type': 'mouse_click',
                'x': x,
                'y': y,
                'button': button,
                'pressed': pressed,
                'timestamp': time.perf_counter()
            })
    
    def on_mouse_scroll(self, x, y, dx, dy):
        if self.recording:
            self.action_queue.put({
                'type': 'mouse_scroll',
                'x': x,
                'y': y,
                'dx': dx,
                'dy': dy,
                'timestamp': time.perf_counter()
            })
    
    def on_key_press(self, key):
        if self.recording:
            # 检测Ctrl+C
            if key == Key.ctrl_l or key == Key.ctrl_r:
                self.ctrl_pressed = True
            elif hasattr(key, 'char') and key.char == 'c' and self.ctrl_pressed:
                # 先记录这个按键，然后停止
                self.action_queue.put({
                    'type': 'key_press',
                    'key': key,
                    'timestamp': time.perf_counter()
                })
                time.sleep(0.01)  # 确保动作被记录
                self.recording = False
                return
            
            self.action_queue.put({
                'type': 'key_press',
                'key': key,
                'timestamp': time.perf_counter()
            })
    
    def on_key_release(self, key):
        if self.recording:
            if key == Key.ctrl_l or key == Key.ctrl_r:
                self.ctrl_pressed = False
            
            self.action_queue.put({
                'type': 'key_release',
                'key': key,
                'timestamp': time.perf_counter()
            })
    
    def replay_actions(self):
        if not self.actions:
            return
        
        start_time = time.perf_counter()
        base_timestamp = self.actions[0]['timestamp']
        
        for i, action in enumerate(self.actions):
            # 计算应该等待的时间
            target_time = start_time + (action['timestamp'] - base_timestamp)
            current_time = time.perf_counter()
            
            if target_time > current_time:
                time.sleep(target_time - current_time)
            
            try:
                if action['type'] == 'mouse_move':
                    # 添加随机偏移
                    offset_x = random.randint(-1, 1)
                    offset_y = random.randint(-1, 1)
                    new_x = action['x'] + offset_x
                    new_y = action['y'] + offset_y
                    self.mouse_controller.position = (new_x, new_y)
                
                elif action['type'] == 'mouse_click':
                    # 添加随机偏移
                    offset_x = random.randint(-1, 1)
                    offset_y = random.randint(-1, 1)
                    new_x = action['x'] + offset_x
                    new_y = action['y'] + offset_y
                    
                    self.mouse_controller.position = (new_x, new_y)
                    if action['pressed']:
                        self.mouse_controller.press(action['button'])
                    else:
                        self.mouse_controller.release(action['button'])
                
                elif action['type'] == 'mouse_scroll':
                    # 添加随机偏移
                    offset_x = random.randint(-1, 1)
                    offset_y = random.randint(-1, 1)
                    new_x = action['x'] + offset_x
                    new_y = action['y'] + offset_y
                    self.mouse_controller.position = (new_x, new_y)
                    self.mouse_controller.scroll(action['dx'], action['dy'])
                
                elif action['type'] == 'key_press':
                    self.keyboard_controller.press(action['key'])
                
                elif action['type'] == 'key_release':
                    self.keyboard_controller.release(action['key'])
            
            except Exception as e:
                # 记录错误但继续执行
                print(f"警告: 动作 {i+1} 执行失败: {e}")
                continue

def main():
    recorder = ActionRecorder()
    try:
        recorder.start_recording()
    except Exception as e:
        print(f"程序出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
