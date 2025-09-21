import asyncio
import pickle
import os
import time
import json
import sys
from datetime import datetime
from typing import Dict, List

# 添加父目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import communication.boxim as boxim

# 配置
MEMORY_FILE = r"E:\我的\python\new\Nbot0.4.0\data\memory.pkl"
EMBEDDINGS_FILE = r"E:\我的\python\new\Nbot0.4.0\data\memory_embeddings.pkl"

# 全局存储
_memory_data = []
_embeddings_data = []

def _ensure_data_dir():
    """确保数据目录存在"""
    data_dir = os.path.dirname(MEMORY_FILE)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

def _load_data():
    """加载数据"""
    global _memory_data, _embeddings_data
    
    _ensure_data_dir()
    
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, 'rb') as f:
                _memory_data = pickle.load(f)
        except:
            _memory_data = []
    else:
        _memory_data = []
    
    if os.path.exists(EMBEDDINGS_FILE):
        try:
            with open(EMBEDDINGS_FILE, 'rb') as f:
                _embeddings_data = pickle.load(f)
        except:
            _embeddings_data = []
    else:
        _embeddings_data = []

def _save_data():
    """保存数据"""
    _ensure_data_dir()
    
    with open(MEMORY_FILE, 'wb') as f:
        pickle.dump(_memory_data, f)
    
    with open(EMBEDDINGS_FILE, 'wb') as f:
        pickle.dump(_embeddings_data, f)

def _format_message_content(msg_type: int, content: str) -> str:
    """格式化消息内容"""
    if msg_type == 0:  # 文本
        return content
    elif msg_type == 1:  # 图片
        try:
            data = json.loads(content)
            url = data.get("originUrl", data.get("thumbUrl", ""))
            return f"[图片信息] {url}"
        except:
            return "[图片信息] 解析失败"
    elif msg_type == 2:  # 文件
        try:
            data = json.loads(content)
            name = data.get("name", "未知文件")
            url = data.get("url", "")
            return f"[文件信息] {name} {url}"
        except:
            return "[文件信息] 解析失败"
    elif msg_type == 3:  # 语音
        try:
            data = json.loads(content)
            duration = data.get("duration", 0)
            url = data.get("url", "")
            return f"[语音信息] 时长{duration}秒 {url}"
        except:
            return "[语音信息] 解析失败"
    elif msg_type == 4:  # 视频
        try:
            data = json.loads(content)
            url = data.get("videoUrl", data.get("coverUrl", ""))
            return f"[视频信息] {url}"
        except:
            return "[视频信息] 解析失败"
    elif msg_type == 5:  # 个人名片
        try:
            data = json.loads(content)
            nickname = data.get("nickName", "未知用户")
            user_id = data.get("userId", "")
            return f"[个人名片] {nickname}(ID: {user_id})"
        except:
            return "[个人名片] 解析失败"
    elif msg_type == 6:  # 群聊名片
        try:
            data = json.loads(content)
            group_name = data.get("groupName", "未知群组")
            group_id = data.get("groupId", "")
            return f"[群聊名片] {group_name}(ID: {group_id})"
        except:
            return "[群聊名片] 解析失败"
    else:
        return None

async def record_my_message(message: str):
    """记录自己发送的消息"""
    try:
        # 确保数据已加载
        if not _memory_data:
            _load_data()
        
        # 获取当前时间
        current_time = int(time.time() * 1000)
        current_time_str = datetime.fromtimestamp(current_time / 1000).strftime('%Y-%m-%d %H:%M:%S')
        
        # 获取自己的用户信息
        user_id = boxim.get_user_id()
        user_nickname = "Nbot"
        
        # 构建记录
        record = {
            "timestamp": current_time,
            "message_type": "我发送的消息",
            "send_time": current_time_str,
            "sender_id": user_id,
            "sender_nickname": user_nickname,
            "content": message,
            "msg_type": 0,
            "is_group": False,
            "is_self_sent": True
        }
        
        # 添加到数据
        _memory_data.append(record)
        
        # 保存数据
        _save_data()
        
        print(f"[消息记录] 我发送的消息: {message[:50]}{'...' if len(message) > 50 else ''}")
        
    except Exception as e:
        print(f"记录消息时出错: {e}")

async def message_handler(msg_data: Dict, is_group: bool):
    """消息处理器"""
    try:
        # 忽略自己发送的消息
        user_id = boxim.get_user_id()
        if user_id and msg_data.get('sendId') == user_id:
            return
        
        # 格式化消息
        send_time = msg_data.get('sendTime', int(time.time() * 1000))
        send_time_str = datetime.fromtimestamp(send_time / 1000).strftime('%Y-%m-%d %H:%M:%S')
        
        send_id = msg_data.get('sendId', 0)
        send_nickname = msg_data.get('sendNickName', f'用户{send_id}')
        msg_type = msg_data.get('type', 0)
        content = msg_data.get('content', '')
        
        formatted_content = _format_message_content(msg_type, content)
        if formatted_content is None:
            return
        
        # 构建记录
        record = {
            "timestamp": send_time,
            "message_type": "群组消息" if is_group else "私聊消息",
            "send_time": send_time_str,
            "sender_id": send_id,
            "sender_nickname": send_nickname,
            "content": formatted_content,
            "raw_content": content,
            "msg_type": msg_type,
            "is_group": is_group,
            "is_self_sent": False
        }
        
        if is_group:
            record["group_id"] = msg_data.get('groupId', 0)
        else:
            record["recv_id"] = msg_data.get('recvId', user_id)
        
        # 添加到数据
        _memory_data.append(record)
        
        # 保存数据
        _save_data()
        
        message_type = "群组消息" if is_group else "私聊消息"
        print(f"[消息记录] {message_type} - {send_nickname}: {formatted_content[:50]}{'...' if len(formatted_content) > 50 else ''}")
        
    except Exception as e:
        print(f"处理消息错误: {e}")

def get_latest_message() -> Dict:
    """获取最新的一条消息"""
    try:
        _ensure_data_dir()
        
        if not os.path.exists(MEMORY_FILE):
            return None
            
        with open(MEMORY_FILE, 'rb') as f:
            data = pickle.load(f)
        
        if not data:
            return None
        
        # 返回最新的消息
        return max(data, key=lambda x: x.get('timestamp', 0))
            
    except Exception as e:
        print(f"获取最新消息失败: {e}")
        return None

async def start_listening():
    """开始监听"""
    print("开始加载数据...")
    _load_data()
    print(f"已加载 {len(_memory_data)} 条消息记录")
    
    # 添加消息处理器
    boxim.add_message_handler(message_handler)
    
    # 开始监听
    print("开始监听消息...")
    await boxim.start_listening()

async def main():
    success = await boxim.login("Nbot", "a31415926535")
    if success:
        await start_listening()
    else:
        print("登录失败")

if __name__ == "__main__":
    asyncio.run(main())
