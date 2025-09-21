"""
Nbot - 基于意识流的智能聊天机器人
支持实时决策、自主思考、记忆管理和完整的工具库集成
"""

import asyncio
import os
import sys
import json
import time
import traceback
import signal
import threading
import math
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path
import aiohttp
import websockets
import tempfile
import logging
from printstream import *
from printstream import print_stream as smooth_print


# 导入所需模块
try:
    from prompt_builder import (
        prompt_builder, 
        build_reply_prompt,
        build_interrupted_reply_prompt,
        build_mood_prompt,
        build_planner_prompt,
        format_chat_messages,
        extract_json_from_llm_response,
        clean_llm_response
    )
except ImportError:
    print(" 无法导入 prompt_builder 模块")
    sys.exit(1)

try:
    sys.path.append(os.path.join(os.path.dirname(__file__), 'communication'))
    import boxim
except ImportError:
    print(" 无法导入 boxim 模块")
    sys.exit(1)

try:
    from model_utils import chat, chat_stream, text_to_speech, get_embedding, init_session, close_session
except ImportError:
    print(" 无法导入 model_utils 模块")
    sys.exit(1)

# ==================== 配置和常量 ====================

# 环境变量配置
BOXIM_USERNAME = os.getenv("BOXIM_USERNAME", "Nbot")
BOXIM_PASSWORD = os.getenv("BOXIM_PASSWORD", "a31415926535")

# LPMM知识库配置
RAG_CONFIG = {
    "rag_synonym_search_top_k": 10,
    "rag_synonym_threshold": 0.8,
    "info_extraction_workers": 3,
    "qa_relation_search_top_k": 10,
    "qa_relation_threshold": 0.5,
    "qa_paragraph_search_top_k": 1000,
    "qa_paragraph_node_weight": 0.05,
    "qa_ent_filter_top_k": 10,
    "qa_ppr_damping": 0.8,
    "qa_res_top_k": 3,
    "embedding_dimension": 1024
}

# 数据目录
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(DATA_DIR / "nbot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== 数据结构 ====================

@dataclass
class Message:
    """消息数据结构"""
    id: str
    sender_id: int
    sender_name: str
    content: str
    timestamp: float
    type: str  # 'group' or 'private'
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    message_type: int = 0  # 0: text, 1: image, 2: file, 3: voice, 4: video
    at_user_ids: List[int] = None
    processed_plain_text: str = ""
    is_system: bool = False
    
    def __post_init__(self):
        if self.at_user_ids is None:
            self.at_user_ids = []
        if not self.processed_plain_text:
            self.processed_plain_text = self.content

@dataclass
class UserMemory:
    """用户记忆数据结构"""
    user_id: int
    memories: Dict[str, List[str]]  # category -> memories
    last_interaction: float
    relation_info: str = ""
    expression_habits: List[str] = None
    
    def __post_init__(self):
        if self.expression_habits is None:
            self.expression_habits = []

@dataclass
class NbotState:
    """Nbot状态数据结构"""
    current_mood: str = "感觉很平静"
    mood_values: Dict[str, int] = None  # joy, anger, sorrow, fear
    last_mood_update: float = 0
    consciousness_level: float = 1.0
    message_queue: List[Message] = None
    active_conversations: Dict[str, List[Message]] = None
    thinking_context: str = ""
    last_action_time: float = 0
    decision_history: List[Dict] = None
    
    def __post_init__(self):
        if self.mood_values is None:
            self.mood_values = {"joy": 5, "anger": 1, "sorrow": 1, "fear": 1}
        if self.message_queue is None:
            self.message_queue = []
        if self.active_conversations is None:
            self.active_conversations = {}
        if self.decision_history is None:
            self.decision_history = []

# ==================== 记忆管理系统 ====================

class MemoryManager:
    """记忆管理系统"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.memories_file = data_dir / "memories.json"
        self.user_memories: Dict[int, UserMemory] = {}
        self.load_memories()
    
    def load_memories(self):
        """加载记忆数据"""
        try:
            if self.memories_file.exists():
                with open(self.memories_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for user_id_str, memory_data in data.items():
                        user_id = int(user_id_str)
                        self.user_memories[user_id] = UserMemory(
                            user_id=user_id,
                            memories=memory_data.get("memories", {}),
                            last_interaction=memory_data.get("last_interaction", 0),
                            relation_info=memory_data.get("relation_info", ""),
                            expression_habits=memory_data.get("expression_habits", [])
                        )
                logger.info(f"已加载 {len(self.user_memories)} 个用户的记忆数据")
        except Exception as e:
            logger.error(f"加载记忆数据失败: {e}")
    
    def save_memories(self):
        """保存记忆数据"""
        try:
            data = {}
            for user_id, memory in self.user_memories.items():
                data[str(user_id)] = asdict(memory)
            
            with open(self.memories_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug("记忆数据已保存")
        except Exception as e:
            logger.error(f"保存记忆数据失败: {e}")
    
    async def add_memory(self, user_id: int, category: str, memory_content: str):
        """添加用户记忆"""
        if user_id not in self.user_memories:
            self.user_memories[user_id] = UserMemory(
                user_id=user_id,
                memories={},
                last_interaction=time.time()
            )
        
        user_memory = self.user_memories[user_id]
        if category not in user_memory.memories:
            user_memory.memories[category] = []
        
        # 检查是否需要分类或更新记忆
        existing_memories = user_memory.memories[category]
        
        # 使用提示词进行记忆分类和更新
        if existing_memories:
            prompt = await prompt_builder.build_memory_category_prompt(
                person_name=str(user_id),
                memory_point=memory_content,
                category_list=list(user_memory.memories.keys())
            )
            
            try:
                response = await chat(prompt)
                json_result = extract_json_from_llm_response(response)
                if json_result:
                    result = json_result[0]
                    if "new_memory" in result:
                        user_memory.memories[category].append(result["new_memory"])
                    elif "integrate_memory" in result:
                        memory_id = result.get("memory_id", 0) - 1
                        if 0 <= memory_id < len(user_memory.memories[category]):
                            user_memory.memories[category][memory_id] = result["integrate_memory"]
            except Exception as e:
                logger.error(f"记忆处理失败: {e}")
                # 降级处理，直接添加
                user_memory.memories[category].append(memory_content)
        else:
            user_memory.memories[category].append(memory_content)
        
        # 限制记忆数量
        if len(user_memory.memories[category]) > 5:
            user_memory.memories[category] = user_memory.memories[category][-5:]
        
        user_memory.last_interaction = time.time()
        self.save_memories()
    
    async def get_relevant_memories(self, user_id: int, context: str) -> str:
        """获取相关记忆"""
        if user_id not in self.user_memories:
            return ""
        
        user_memory = self.user_memories[user_id]
        
        # 使用记忆激活器选择相关记忆
        all_memories = []
        for category, memories in user_memory.memories.items():
            for i, memory in enumerate(memories):
                all_memories.append(f"{category}_{i+1}: {memory}")
        
        if not all_memories:
            return ""
        
        try:
            prompt = await prompt_builder.build_memory_activator_prompt(
                obs_info_text=context,
                target_message="",
                memory_info="\n".join(all_memories)
            )
            
            response = await chat(prompt)
            json_result = extract_json_from_llm_response(response)
            if json_result and "memory_ids" in json_result[0]:
                selected_ids = json_result[0]["memory_ids"].split(",")
                selected_memories = []
                for memory_id in selected_ids:
                    memory_id = memory_id.strip()
                    for memory_line in all_memories:
                        if memory_line.startswith(memory_id + ":"):
                            selected_memories.append(memory_line.split(":", 1)[1].strip())
                            break
                return "\n".join(selected_memories)
        except Exception as e:
            logger.error(f"记忆激活失败: {e}")
        
        # 降级处理，返回最近的记忆
        recent_memories = []
        for category, memories in user_memory.memories.items():
            if memories:
                recent_memories.append(memories[-1])
        return "\n".join(recent_memories[-3:])  # 返回最近3条记忆
    
    def get_user_relation_info(self, user_id: int) -> str:
        """获取用户关系信息"""
        if user_id in self.user_memories:
            return self.user_memories[user_id].relation_info
        return ""
    
    def update_user_relation_info(self, user_id: int, relation_info: str):
        """更新用户关系信息"""
        if user_id not in self.user_memories:
            self.user_memories[user_id] = UserMemory(
                user_id=user_id,
                memories={},
                last_interaction=time.time()
            )
        
        self.user_memories[user_id].relation_info = relation_info
        self.user_memories[user_id].last_interaction = time.time()
        self.save_memories()
    
    def get_user_expression_habits(self, user_id: int) -> List[str]:
        """获取用户表达习惯"""
        if user_id in self.user_memories:
            return self.user_memories[user_id].expression_habits
        return []
    
    def update_user_expression_habits(self, user_id: int, habits: List[str]):
        """更新用户表达习惯"""
        if user_id not in self.user_memories:
            self.user_memories[user_id] = UserMemory(
                user_id=user_id,
                memories={},
                last_interaction=time.time()
            )
        
        self.user_memories[user_id].expression_habits = habits
        self.save_memories()

# ==================== 状态管理系统 ====================

class StateManager:
    """状态管理系统"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.state_file = data_dir / "nbot_state.json"
        self.state = NbotState()
        self.load_state()
    
    def load_state(self):
        """加载状态数据"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # 重建消息队列
                    message_queue = []
                    for msg_data in data.get("message_queue", []):
                        message = Message(**msg_data)
                        message_queue.append(message)
                    
                    # 重建活跃对话
                    active_conversations = {}
                    for conv_id, msgs_data in data.get("active_conversations", {}).items():
                        messages = []
                        for msg_data in msgs_data:
                            message = Message(**msg_data)
                            messages.append(message)
                        active_conversations[conv_id] = messages
                    
                    self.state = NbotState(
                        current_mood=data.get("current_mood", "感觉很平静"),
                        mood_values=data.get("mood_values", {"joy": 5, "anger": 1, "sorrow": 1, "fear": 1}),
                        last_mood_update=data.get("last_mood_update", 0),
                        consciousness_level=data.get("consciousness_level", 1.0),
                        message_queue=message_queue,
                        active_conversations=active_conversations,
                        thinking_context=data.get("thinking_context", ""),
                        last_action_time=data.get("last_action_time", 0),
                        decision_history=data.get("decision_history", [])
                    )
                logger.info("已加载Nbot状态数据")
        except Exception as e:
            logger.error(f"加载状态数据失败: {e}")
            self.state = NbotState()
    
    def save_state(self):
        """保存状态数据"""
        try:
            # 将Message对象转换为字典
            message_queue_data = []
            for msg in self.state.message_queue:
                message_queue_data.append(asdict(msg))
            
            active_conversations_data = {}
            for conv_id, messages in self.state.active_conversations.items():
                msgs_data = []
                for msg in messages:
                    msgs_data.append(asdict(msg))
                active_conversations_data[conv_id] = msgs_data
            
            data = {
                "current_mood": self.state.current_mood,
                "mood_values": self.state.mood_values,
                "last_mood_update": self.state.last_mood_update,
                "consciousness_level": self.state.consciousness_level,
                "message_queue": message_queue_data,
                "active_conversations": active_conversations_data,
                "thinking_context": self.state.thinking_context,
                "last_action_time": self.state.last_action_time,
                "decision_history": self.state.decision_history
            }
            
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug("状态数据已保存")
        except Exception as e:
            logger.error(f"保存状态数据失败: {e}")
    
    def add_message_to_queue(self, message: Message):
        """添加消息到队列"""
        self.state.message_queue.append(message)
        
        # 限制队列长度
        if len(self.state.message_queue) > 100:
            self.state.message_queue = self.state.message_queue[-50:]
        
        # 更新活跃对话
        if message.type == "group" and message.group_id:
            conv_id = f"group_{message.group_id}"
        else:
            conv_id = f"private_{message.sender_id}"
        
        if conv_id not in self.state.active_conversations:
            self.state.active_conversations[conv_id] = []
        
        self.state.active_conversations[conv_id].append(message)
        
        # 限制对话历史长度
        if len(self.state.active_conversations[conv_id]) > 50:
            self.state.active_conversations[conv_id] = self.state.active_conversations[conv_id][-30:]
        
        self.save_state()
    
    def get_conversation_history(self, conv_id: str, limit: int = 20) -> List[Message]:
        """获取对话历史"""
        if conv_id in self.state.active_conversations:
            return self.state.active_conversations[conv_id][-limit:]
        return []
    
    def update_mood(self, new_mood: str, mood_values: Dict[str, int] = None):
        """更新情绪状态"""
        self.state.current_mood = new_mood
        self.state.last_mood_update = time.time()
        
        if mood_values:
            self.state.mood_values.update(mood_values)
        
        self.save_state()
    
    def add_decision_to_history(self, decision: Dict[str, Any]):
        """添加决策到历史"""
        decision["timestamp"] = time.time()
        self.state.decision_history.append(decision)
        
        # 限制决策历史长度
        if len(self.state.decision_history) > 100:
            self.state.decision_history = self.state.decision_history[-50:]
        
        self.save_state()

# ==================== 工具库系统 ====================

class ToolLibrary:
    """完整的工具库系统"""
    
    def __init__(self, memory_manager: MemoryManager, state_manager: StateManager):
        self.memory_manager = memory_manager
        self.state_manager = state_manager
        self.tools = {}
        self._register_tools()
    
    def _register_tools(self):
        """注册所有工具"""
        self.tools = {
            "send_message": self.send_message,
            "send_file": self.send_file,
            "send_voice": self.send_voice,
            "send_image": self.send_image,
            "search_knowledge": self.search_knowledge,
            "recall_message": self.recall_message,
            "mark_as_read": self.mark_as_read,
            "get_user_info": self.get_user_info,
            "update_memory": self.update_memory,
            "get_conversation_history": self.get_conversation_history,
            "mute_user": self.mute_user,
            "update_mood": self.update_mood,
            "check_online_status": self.check_online_status
        }
    
    async def send_message(self, message: str, target_id: int, is_group: bool = False) -> Dict[str, Any]:
        """发送消息工具"""
        try:
            if is_group:
                result = await boxim.send_group_text(target_id, message)
            else:
                result = await boxim.send_private_text(target_id, message)
            
            if result:
                smooth_print(f" 消息已发送: {message[:30]}{'...' if len(message) > 30 else ''}\n")
                return {"success": True, "message_id": result}
            else:
                error = boxim.get_last_error()
                smooth_print(f" 消息发送失败: {error}\n")
                return {"success": False, "error": error}
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def send_file(self, file_content: str, file_name: str, target_id: int, is_group: bool = False) -> Dict[str, Any]:
        """发送文件工具"""
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=f"_{file_name}", encoding='utf-8') as tmp_file:
                tmp_file.write(file_content)
                tmp_path = tmp_file.name
            
            try:
                if is_group:
                    result = await boxim.send_group_file(target_id, tmp_path)
                else:
                    result = await boxim.send_private_file(target_id, tmp_path)
                
                if result:
                    smooth_print(f" 文件已发送: {file_name}\n")
                    return {"success": True, "message_id": result}
                else:
                    error = boxim.get_last_error()
                    return {"success": False, "error": error}
            finally:
                # 清理临时文件
                try:
                    os.unlink(tmp_path)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"发送文件失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def send_voice(self, voice_text: str, target_id: int, is_group: bool = False, duration: int = 3) -> Dict[str, Any]:
        """发送语音工具"""
        try:
            # 使用TTS生成语音
            voice_path = await text_to_speech(voice_text)
            
            if voice_path and os.path.exists(voice_path):
                if is_group:
                    result = await boxim.send_group_voice(target_id, voice_path, duration)
                else:
                    result = await boxim.send_private_voice(target_id, voice_path, duration)
                
                if result:
                    smooth_print(f" 语音已发送: {voice_text[:20]}{'...' if len(voice_text) > 20 else ''}\n")
                    return {"success": True, "message_id": result}
                else:
                    error = boxim.get_last_error()
                    return {"success": False, "error": error}
            else:
                return {"success": False, "error": "语音生成失败"}
                
        except Exception as e:
            logger.error(f"发送语音失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def send_image(self, image_path: str, target_id: int, is_group: bool = False) -> Dict[str, Any]:
        """发送图片工具"""
        try:
            if not os.path.exists(image_path):
                return {"success": False, "error": "图片文件不存在"}
            
            if is_group:
                result = await boxim.send_group_image(target_id, image_path)
            else:
                result = await boxim.send_private_image(target_id, image_path)
            
            if result:
                smooth_print(f"️ 图片已发送: {os.path.basename(image_path)}\n")
                return {"success": True, "message_id": result}
            else:
                error = boxim.get_last_error()
                return {"success": False, "error": error}
                
        except Exception as e:
            logger.error(f"发送图片失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def search_knowledge(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        """搜索知识工具"""
        try:
            # 这里应该接入真实的知识库搜索
            # 暂时使用模拟实现
            results = [
                {"content": f"关于'{query}'的知识点1", "score": 0.9},
                {"content": f"关于'{query}'的知识点2", "score": 0.8},
                {"content": f"关于'{query}'的知识点3", "score": 0.7}
            ]
            
            smooth_print(f" 知识搜索完成: {query}\n")
            return {"success": True, "results": results[:top_k]}
            
        except Exception as e:
            logger.error(f"知识搜索失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def recall_message(self, message_id: int, is_group: bool = False) -> Dict[str, Any]:
        """撤回消息工具"""
        try:
            if is_group:
                result = await boxim.recall_group_message(message_id)
            else:
                result = await boxim.recall_private_message(message_id)
            
            if result:
                smooth_print(f"️ 消息已撤回: {message_id}\n")
                return {"success": True}
            else:
                error = boxim.get_last_error()
                return {"success": False, "error": error}
                
        except Exception as e:
            logger.error(f"撤回消息失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def mark_as_read(self, friend_id: int) -> Dict[str, Any]:
        """标记消息已读工具"""
        try:
            result = await boxim.mark_private_as_read(friend_id)
            
            if result:
                smooth_print(f"️ 消息已标记为已读: {friend_id}\n")
                return {"success": True}
            else:
                error = boxim.get_last_error()
                return {"success": False, "error": error}
                
        except Exception as e:
            logger.error(f"标记已读失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_user_info(self, user_id: int) -> Dict[str, Any]:
        """获取用户信息工具"""
        try:
            # 从记忆系统获取用户信息
            memories = await self.memory_manager.get_relevant_memories(user_id, "用户信息查询")
            relation_info = self.memory_manager.get_user_relation_info(user_id)
            expression_habits = self.memory_manager.get_user_expression_habits(user_id)
            
            return {
                "success": True,
                "user_id": user_id,
                "memories": memories,
                "relation_info": relation_info,
                "expression_habits": expression_habits
            }
            
        except Exception as e:
            logger.error(f"获取用户信息失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def update_memory(self, user_id: int, category: str, memory_content: str) -> Dict[str, Any]:
        """更新记忆工具"""
        try:
            await self.memory_manager.add_memory(user_id, category, memory_content)
            smooth_print(f" 记忆已更新: {category} - {memory_content[:30]}{'...' if len(memory_content) > 30 else ''}\n")
            return {"success": True}
            
        except Exception as e:
            logger.error(f"更新记忆失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_conversation_history(self, conv_id: str, limit: int = 20) -> Dict[str, Any]:
        """获取对话历史工具"""
        try:
            history = self.state_manager.get_conversation_history(conv_id, limit)
            messages_data = []
            for msg in history:
                messages_data.append({
                    "id": msg.id,
                    "sender_name": msg.sender_name,
                    "content": msg.content,
                    "timestamp": msg.timestamp,
                    "type": msg.type
                })
            
            return {"success": True, "messages": messages_data}
            
        except Exception as e:
            logger.error(f"获取对话历史失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def mute_user(self, group_id: int, user_ids: List[int], is_muted: bool = True) -> Dict[str, Any]:
        """禁言用户工具"""
        try:
            result = await boxim.mute_group_members(group_id, user_ids, is_muted)
            
            if result.get("code") == 200:
                action = "禁言" if is_muted else "解禁"
                smooth_print(f" 用户{action}成功: {user_ids}\n")
                return {"success": True}
            else:
                return {"success": False, "error": result.get("message", "操作失败")}
                
        except Exception as e:
            logger.error(f"禁言操作失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def update_mood(self, new_mood: str, mood_values: Dict[str, int] = None) -> Dict[str, Any]:
        """更新情绪工具"""
        try:
            self.state_manager.update_mood(new_mood, mood_values)
            smooth_print(f" 情绪已更新: {new_mood}\n")
            return {"success": True}
            
        except Exception as e:
            logger.error(f"更新情绪失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def check_online_status(self, user_id: int) -> Dict[str, Any]:
        """检查用户在线状态工具"""
        try:
            # 这里应该有真实的在线状态检查逻辑
            # 暂时返回模拟数据
            return {
                "success": True,
                "user_id": user_id,
                "online": True,
                "terminal": 0  # 0: PC, 1: Mobile
            }
            
        except Exception as e:
            logger.error(f"检查在线状态失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def execute_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """执行工具"""
        if tool_name in self.tools:
            try:
                return await self.tools[tool_name](**kwargs)
            except Exception as e:
                logger.error(f"执行工具 {tool_name} 失败: {e}")
                return {"success": False, "error": str(e)}
        else:
            return {"success": False, "error": f"未知工具: {tool_name}"}

# ==================== 决策引擎 ====================

class DecisionEngine:
    """智能决策引擎"""
    
    def __init__(self, memory_manager: MemoryManager, state_manager: StateManager, tool_library: ToolLibrary):
        self.memory_manager = memory_manager
        self.state_manager = state_manager
        self.tool_library = tool_library
        self.available_actions = [
            {
                "name": "reply",
                "description": "回复消息",
                "requirements": ["有新消息", "消息内容有意义", "需要回应"]
            },
            {
                "name": "send_file",
                "description": "发送文件",
                "requirements": ["用户要求文件", "有相关文件内容"]
            },
            {
                "name": "send_voice",
                "description": "发送语音",
                "requirements": ["用户要求语音", "适合语音表达"]
            },
            {
                "name": "recall_message",
                "description": "撤回消息",
                "requirements": ["消息有误", "需要纠正"]
            },
            {
                "name": "search_knowledge",
                "description": "搜索知识",
                "requirements": ["用户询问问题", "需要查找信息"]
            },
            {
                "name": "update_memory",
                "description": "更新记忆",
                "requirements": ["获得新信息", "需要记住内容"]
            },
            {
                "name": "no_reply",
                "description": "保持沉默",
                "requirements": ["无需回应", "控制发言频率"]
            }
        ]
    
    async def analyze_context(self) -> str:
        """分析当前上下文"""
        try:
            # 获取最近的消息
            recent_messages = self.state_manager.state.message_queue[-10:]
            if not recent_messages:
                return "没有新消息"
            
            # 构建上下文文本
            context_lines = []
            for msg in recent_messages:
                if not msg.is_system:
                    context_lines.append(f"{msg.sender_name}: {msg.processed_plain_text}")
            
            context_text = "\n".join(context_lines)
            
            # 添加当前状态信息
            context_text += f"\n\n当前心情: {self.state_manager.state.current_mood}"
            context_text += f"\n消息队列长度: {len(self.state_manager.state.message_queue)}"
            
            return context_text
            
        except Exception as e:
            logger.error(f"分析上下文失败: {e}")
            return "上下文分析失败"
    
    async def generate_actions(self, context: str) -> List[Dict[str, Any]]:
        """生成可能的行动"""
        try:
            # 使用规划器提示词生成行动
            planner_prompt = await prompt_builder.build_planner_prompt(
                chat_content=context,
                available_actions=self.available_actions,
                context=prompt_builder.build_basic_context()
            )
            
            response = await chat(planner_prompt)
            actions = extract_json_from_llm_response(response)
            
            smooth_print(f" 决策思考: {len(actions)} 个可能行动\n")
            
            return actions
            
        except Exception as e:
            logger.error(f"生成行动失败: {e}")
            return [{"action": "no_reply", "reason": "决策系统错误"}]
    
    async def execute_actions(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """执行行动"""
        results = []
        
        for action_data in actions:
            try:
                action = action_data.get("action")
                if not action:
                    continue
                
                smooth_print(f" 执行行动: {action}\n")
                
                if action == "reply":
                    result = await self._execute_reply_action(action_data)
                elif action == "send_file":
                    result = await self._execute_send_file_action(action_data)
                elif action == "send_voice":
                    result = await self._execute_send_voice_action(action_data)
                elif action == "recall_message":
                    result = await self._execute_recall_action(action_data)
                elif action == "search_knowledge":
                    result = await self._execute_search_action(action_data)
                elif action == "update_memory":
                    result = await self._execute_update_memory_action(action_data)
                elif action == "no_reply":
                    result = {"success": True, "action": "no_reply"}
                else:
                    result = {"success": False, "error": f"未知行动: {action}"}
                
                result["action"] = action
                result["original_data"] = action_data
                results.append(result)
                
                # 记录决策历史
                self.state_manager.add_decision_to_history({
                    "action": action,
                    "data": action_data,
                    "result": result
                })
                
            except Exception as e:
                logger.error(f"执行行动失败: {e}")
                results.append({
                    "success": False,
                    "error": str(e),
                    "action": action_data.get("action", "unknown")
                })
        
        return results
    
    async def _execute_reply_action(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行回复行动"""
        try:
            # 获取目标消息
            target_message_id = action_data.get("target_message_id", "")
            reason = action_data.get("reason", "")
            
            # 查找目标消息
            target_message = None
            for msg in reversed(self.state_manager.state.message_queue):
                if f"m{msg.id}" == target_message_id or msg.id == target_message_id:
                    target_message = msg
                    break
            
            if not target_message:
                # 如果没有指定消息，回复最新消息
                recent_messages = [msg for msg in self.state_manager.state.message_queue if not msg.is_system]
                if recent_messages:
                    target_message = recent_messages[-1]
                else:
                    return {"success": False, "error": "没有可回复的消息"}
            
            # 构建回复上下文
            if target_message.type == "group":
                conv_id = f"group_{target_message.group_id}"
                chat_history = self.state_manager.get_conversation_history(conv_id, 15)
            else:
                conv_id = f"private_{target_message.sender_id}"
                chat_history = self.state_manager.get_conversation_history(conv_id, 15)
            
            # 格式化聊天历史
            formatted_history = format_chat_messages([asdict(msg) for msg in chat_history])
            
            # 获取用户相关信息
            memories = await self.memory_manager.get_relevant_memories(target_message.sender_id, target_message.content)
            relation_info = self.memory_manager.get_user_relation_info(target_message.sender_id)
            expression_habits = self.memory_manager.get_user_expression_habits(target_message.sender_id)
            
            # 构建回复提示词
            context = prompt_builder.build_basic_context(
                group_name=target_message.group_name if target_message.type == "group" else None,
                user_name=target_message.sender_name if target_message.type == "private" else None,
                mood_state=self.state_manager.state.current_mood
            )
            
            reply_prompt = await prompt_builder.build_reply_prompt(
                sender_name=target_message.sender_name,
                chat_history=formatted_history,
                target_message=target_message.content,
                context=context,
                expression_habits=expression_habits,
                knowledge_info="",
                relation_info=relation_info,
                extra_info=f"回复原因: {reason}"
            )
            
            # 生成回复
            reply_text = await chat(reply_prompt)
            reply_text = clean_llm_response(reply_text)
            
            # 检查是否需要发送文件或语音
            if "<file" in reply_text and "</file>" in reply_text:
                return await self._handle_file_response(reply_text, target_message)
            elif "<voice>" in reply_text and "</voice>" in reply_text:
                return await self._handle_voice_response(reply_text, target_message)
            elif "<no_reply>" in reply_text:
                return {"success": True, "action": "no_reply", "reason": reply_text}
            
            # 发送回复
            if target_message.type == "group":
                result = await self.tool_library.send_message(
                    reply_text, target_message.group_id, is_group=True
                )
                # 标记消息已读（对于群组消息，这里可能不需要）
            else:
                result = await self.tool_library.send_message(
                    reply_text, target_message.sender_id, is_group=False
                )
                # 标记私聊消息已读
                await self.tool_library.mark_as_read(target_message.sender_id)
            
            if result["success"]:
                # 记录回复到对话历史
                reply_message = Message(
                    id=str(result.get("message_id", int(time.time()))),
                    sender_id=boxim.get_user_id() or 0,
                    sender_name="Nbot",
                    content=reply_text,
                    timestamp=time.time(),
                    type=target_message.type,
                    group_id=target_message.group_id,
                    group_name=target_message.group_name,
                    processed_plain_text=reply_text
                )
                self.state_manager.add_message_to_queue(reply_message)
                
                # 更新记忆
                await self.memory_manager.add_memory(
                    target_message.sender_id,
                    "对话记录",
                    f"我回复了: {reply_text}"
                )
            
            return result
            
        except Exception as e:
            logger.error(f"执行回复行动失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _handle_file_response(self, response_text: str, target_message: Message) -> Dict[str, Any]:
        """处理文件响应"""
        try:
            # 解析文件内容
            import re
            file_match = re.search(r'<file name="([^"]+)">(.*?)</file>', response_text, re.DOTALL)
            if not file_match:
                return {"success": False, "error": "文件格式解析失败"}
            
            file_name = file_match.group(1)
            file_content = file_match.group(2).strip()
            
            # 发送文件
            if target_message.type == "group":
                return await self.tool_library.send_file(
                    file_content, file_name, target_message.group_id, is_group=True
                )
            else:
                return await self.tool_library.send_file(
                    file_content, file_name, target_message.sender_id, is_group=False
                )
                
        except Exception as e:
            logger.error(f"处理文件响应失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _handle_voice_response(self, response_text: str, target_message: Message) -> Dict[str, Any]:
        """处理语音响应"""
        try:
            # 解析语音内容
            import re
            voice_match = re.search(r'<voice>(.*?)</voice>', response_text, re.DOTALL)
            if not voice_match:
                return {"success": False, "error": "语音格式解析失败"}
            
            voice_text = voice_match.group(1).strip()
            
            # 发送语音
            if target_message.type == "group":
                return await self.tool_library.send_voice(
                    voice_text, target_message.group_id, is_group=True
                )
            else:
                return await self.tool_library.send_voice(
                    voice_text, target_message.sender_id, is_group=False
                )
                
        except Exception as e:
            logger.error(f"处理语音响应失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _execute_send_file_action(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行发送文件行动"""
        # 实现文件发送逻辑
        return {"success": True, "message": "文件发送功能待实现"}
    
    async def _execute_send_voice_action(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行发送语音行动"""
        # 实现语音发送逻辑
        return {"success": True, "message": "语音发送功能待实现"}
    
    async def _execute_recall_action(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行撤回行动"""
        try:
            # 检查是否需要撤回
            recent_messages = self.state_manager.state.message_queue[-5:]
            formatted_messages = format_chat_messages([asdict(msg) for msg in recent_messages])
            
            recall_prompt = await prompt_builder.build_recall_check_prompt(formatted_messages)
            response = await chat(recall_prompt)
            
            if "是" in response:
                # 查找最近发送的消息并撤回
                for msg in reversed(self.state_manager.state.message_queue):
                    if msg.sender_name == "Nbot":
                        is_group = msg.type == "group"
                        return await self.tool_library.recall_message(int(msg.id), is_group)
            
            return {"success": True, "action": "no_recall"}
            
        except Exception as e:
            logger.error(f"执行撤回行动失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _execute_search_action(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行搜索行动"""
        try:
            query = action_data.get("query", "")
            if not query:
                # 从最近消息中提取查询关键词
                recent_messages = self.state_manager.state.message_queue[-3:]
                for msg in reversed(recent_messages):
                    if not msg.is_system and "?" in msg.content:
                        query = msg.content
                        break
            
            if query:
                return await self.tool_library.search_knowledge(query)
            else:
                return {"success": False, "error": "没有找到查询内容"}
                
        except Exception as e:
            logger.error(f"执行搜索行动失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _execute_update_memory_action(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行更新记忆行动"""
        try:
            # 从最近的对话中提取需要记忆的内容
            recent_messages = self.state_manager.state.message_queue[-5:]
            for msg in reversed(recent_messages):
                if not msg.is_system:
                    await self.memory_manager.add_memory(
                        msg.sender_id,
                        "最近对话",
                        f"{msg.sender_name}说: {msg.content}"
                    )
                    break
            
            return {"success": True}
            
        except Exception as e:
            logger.error(f"执行更新记忆行动失败: {e}")
            return {"success": False, "error": str(e)}

# ==================== 意识流系统 ====================

class ConsciousnessSystem:
    """意识流系统 - 核心思考循环"""
    
    def __init__(self, memory_manager: MemoryManager, state_manager: StateManager, decision_engine: DecisionEngine):
        self.memory_manager = memory_manager
        self.state_manager = state_manager
        self.decision_engine = decision_engine
        self.running = False
        self.thinking_interval = 2.0  # 思考间隔（秒）
        self.last_thinking_time = 0
    
    async def start_consciousness_loop(self):
        """启动意识流循环"""
        self.running = True
        smooth_print(" 意识流系统启动\n")
        
        while self.running:
            try:
                await self._consciousness_cycle()
                await asyncio.sleep(self.thinking_interval)
                
            except Exception as e:
                logger.error(f"意识流循环出错: {e}")
                await asyncio.sleep(5)  # 错误后等待更长时间
    
    async def _consciousness_cycle(self):
        """意识流循环：收集上下文→生成行动→执行行动"""
        try:
            current_time = time.time()
            
            # 第一步：收集上下文
            context = await self.decision_engine.analyze_context()
            
            # 更新思考上下文
            self.state_manager.state.thinking_context = context
            
            # 检查是否有新内容需要处理
            if (self.state_manager.state.message_queue and 
                current_time - self.last_thinking_time > self.thinking_interval):
                
                smooth_print(" 进入深度思考...\n")
                
                # 第二步：生成行动
                actions = await self.decision_engine.generate_actions(context)
                
                # 第三步：执行行动
                if actions:
                    results = await self.decision_engine.execute_actions(actions)
                    
                    # 记录执行结果
                    success_count = sum(1 for r in results if r.get("success"))
                    smooth_print(f" 执行完成: {success_count}/{len(results)} 个行动成功\n")
                
                self.last_thinking_time = current_time
            
            # 定期进行情绪调节
            if current_time - self.state_manager.state.last_mood_update > 300:  # 5分钟
                await self._mood_regulation(context)
            
        except Exception as e:
            logger.error(f"意识流循环出错: {e}")
    
    async def _mood_regulation(self, context: str):
        """情绪调节"""
        try:
            current_mood = self.state_manager.state.current_mood
            
            if context and context != "没有新消息":
                # 有新内容时进行情绪更新
                mood_prompt = await prompt_builder.build_mood_change_prompt(
                    chat_history=context,
                    current_mood=current_mood,
                    context=prompt_builder.build_basic_context(mood_state=current_mood)
                )
            else:
                # 没有新内容时进行情绪回归
                mood_prompt = await prompt_builder.build_mood_regress_prompt(
                    chat_history=context,
                    current_mood=current_mood,
                    context=prompt_builder.build_basic_context(mood_state=current_mood)
                )
            
            response = await chat(mood_prompt)
            new_mood = clean_llm_response(response)
            
            if new_mood and new_mood != current_mood:
                self.state_manager.update_mood(new_mood)
                smooth_print(f" 情绪更新: {current_mood} → {new_mood}\n")
            
        except Exception as e:
            logger.error(f"情绪调节失败: {e}")
    
    def stop_consciousness_loop(self):
        """停止意识流循环"""
        self.running = False
        smooth_print(" 意识流系统停止\n")

# ==================== 消息处理系统 ====================

class MessageProcessor:
    """消息处理系统"""
    
    def __init__(self, memory_manager: MemoryManager, state_manager: StateManager):
        self.memory_manager = memory_manager
        self.state_manager = state_manager
    
    async def process_message(self, message_data: Dict[str, Any], is_group: bool = False):
        """处理收到的消息"""
        try:
            # 检查是否是系统消息
            if self._is_system_message(message_data):
                await self._handle_system_message(message_data)
                return
            
            # 构建消息对象
            message = self._build_message_object(message_data, is_group)
            
            # 添加到消息队列
            self.state_manager.add_message_to_queue(message)
            
            # 输出消息信息
            self._display_message(message)
            
            # 更新用户交互时间
            if message.sender_id in self.memory_manager.user_memories:
                self.memory_manager.user_memories[message.sender_id].last_interaction = time.time()
            
            # 标记私聊消息为已读
            if not is_group:
                asyncio.create_task(self._mark_private_message_read(message.sender_id))
            
        except Exception as e:
            logger.error(f"处理消息失败: {e}")
    
    def _is_system_message(self, message_data: Dict[str, Any]) -> bool:
        """检查是否是系统消息"""
        content = message_data.get("content", "")
        
        # 检查在线状态消息
        if message_data.get("type") == 82:
            try:
                content_json = json.loads(content)
                if "online" in content_json and "terminal" in content_json and "userId" in content_json:
                    return True
            except json.JSONDecodeError:
                pass
        
        return False
    
    async def _handle_system_message(self, message_data: Dict[str, Any]):
        """处理系统消息"""
        try:
            content = message_data.get("content", "")
            content_json = json.loads(content)
            
            if "online" in content_json:
                user_id = content_json["userId"]
                online_status = content_json["online"]
                terminal = content_json["terminal"]
                
                terminal_type = "PC" if terminal == 0 else "手机"
                status_text = "上线" if online_status else "离线"
                
                smooth_print(f" 用户状态: {user_id} {status_text} ({terminal_type})\n")
                
        except Exception as e:
            logger.error(f"处理系统消息失败: {e}")
    
    def _build_message_object(self, message_data: Dict[str, Any], is_group: bool) -> Message:
        """构建消息对象"""
        if is_group:
            return Message(
                id=str(message_data.get("id", int(time.time()))),
                sender_id=message_data.get("sendId", 0),
                sender_name=message_data.get("sendNickName", "未知用户"),
                content=message_data.get("content", ""),
                timestamp=message_data.get("sendTime", time.time() * 1000) / 1000,
                type="group",
                group_id=message_data.get("groupId"),
                group_name="群聊",  # 这里可以从群组缓存中获取
                message_type=message_data.get("type", 0),
                at_user_ids=message_data.get("atUserIds", []),
                processed_plain_text=message_data.get("content", "")
            )
        else:
            return Message(
                id=str(message_data.get("id", int(time.time()))),
                sender_id=message_data.get("sendId", 0),
                sender_name="好友",  # 这里可以从好友缓存中获取
                content=message_data.get("content", ""),
                timestamp=message_data.get("sendTime", time.time() * 1000) / 1000,
                type="private",
                message_type=message_data.get("type", 0),
                processed_plain_text=message_data.get("content", "")
            )
    
    def _display_message(self, message: Message):
        """显示消息"""
        timestamp_str = datetime.fromtimestamp(message.timestamp).strftime('%H:%M:%S')
        
        if message.type == "group":
            smooth_print(f"\n[群消息 {timestamp_str}] {message.group_name}({message.group_id})\n")
            smooth_print(f" {message.sender_name}({message.sender_id}): {message.content}\n")
            
            # 检查是否被@
            bot_user_id = boxim.get_user_id()
            if bot_user_id in message.at_user_ids or "nbot" in message.content.lower():
                smooth_print("️ [需要回复此消息]\n")
        else:
            smooth_print(f"\n[私聊消息 {timestamp_str}]\n")
            smooth_print(f" {message.sender_name}({message.sender_id}): {message.content}\n")
            smooth_print("️ [需要回复此消息]\n")
    
    async def _mark_private_message_read(self, friend_id: int):
        """标记私聊消息为已读"""
        try:
            await asyncio.sleep(0.5)  # 短暂延迟
            await boxim.mark_private_as_read(friend_id)
        except Exception as e:
            logger.error(f"标记消息已读失败: {e}")

# ==================== 主系统 ====================

class NbotSystem:
    """Nbot主系统"""
    
    def __init__(self):
        self.data_dir = DATA_DIR
        self.memory_manager = MemoryManager(self.data_dir)
        self.state_manager = StateManager(self.data_dir)
        self.tool_library = ToolLibrary(self.memory_manager, self.state_manager)
        self.decision_engine = DecisionEngine(self.memory_manager, self.state_manager, self.tool_library)
        self.consciousness_system = ConsciousnessSystem(self.memory_manager, self.state_manager, self.decision_engine)
        self.message_processor = MessageProcessor(self.memory_manager, self.state_manager)
        self.running = False
        self.websocket_task = None
        self.consciousness_task = None
    
    async def start(self):
        """启动Nbot系统"""
        try:
            smooth_print(" Nbot系统启动中...\n")
            
            # 初始化模型会话
            await init_session()
            
            # 登录BOXIM
            if not await self._login():
                smooth_print(" 登录失败，系统退出\n")
                return False
            
            # 启动消息监听
            self.websocket_task = asyncio.create_task(self._start_message_listening())
            
            # 启动意识流系统
            self.consciousness_task = asyncio.create_task(self.consciousness_system.start_consciousness_loop())
            
            self.running = True
            smooth_print(" Nbot系统启动成功\n")
            
            return True
            
        except Exception as e:
            logger.error(f"启动系统失败: {e}")
            smooth_print(f" 启动失败: {e}\n")
            return False
    
    async def stop(self):
        """停止Nbot系统"""
        try:
            smooth_print(" Nbot系统停止中...\n")
            
            self.running = False
            
            # 停止意识流系统
            if self.consciousness_system:
                self.consciousness_system.stop_consciousness_loop()
            
            # 停止WebSocket监听
            if self.websocket_task:
                self.websocket_task.cancel()
                try:
                    await self.websocket_task
                except asyncio.CancelledError:
                    pass
            
            # 停止BOXIM监听
            await boxim.stop_listening()
            
            # 保存状态
            self.state_manager.save_state()
            self.memory_manager.save_memories()
            
            # 关闭模型会话
            await close_session()
            
            # 停止打印流系统
            stop_smooth_printing()
            
            smooth_print(" Nbot系统已停止\n")
            
        except Exception as e:
            logger.error(f"停止系统失败: {e}")
    
    async def _login(self) -> bool:
        """登录BOXIM"""
        try:
            smooth_print(f" 正在登录BOXIM (用户: {BOXIM_USERNAME})\n")
            
            success = await boxim.login(BOXIM_USERNAME, BOXIM_PASSWORD)
            
            if success:
                user_id = boxim.get_user_id()
                smooth_print(f" 登录成功 (用户ID: {user_id})\n")
                return True
            else:
                error = boxim.get_last_error()
                smooth_print(f" 登录失败: {error}\n")
                return False
                
        except Exception as e:
            logger.error(f"登录过程出错: {e}")
            smooth_print(f" 登录出错: {e}\n")
            return False
    
    async def _start_message_listening(self):
        """启动消息监听"""
        try:
            smooth_print(" 开始监听消息...\n")
            
            # 注册消息处理器
            boxim.add_message_handler(self._handle_boxim_message)
            
            # 开始监听
            await boxim.start_listening()
            
        except Exception as e:
            logger.error(f"消息监听失败: {e}")
            smooth_print(f" 消息监听失败: {e}\n")
    
    async def _handle_boxim_message(self, message_data: Dict[str, Any], is_group: bool):
        """处理BOXIM消息"""
        try:
            await self.message_processor.process_message(message_data, is_group)
        except Exception as e:
            logger.error(f"处理BOXIM消息失败: {e}")
    
    async def run_forever(self):
        """运行系统直到被停止"""
        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            smooth_print("\n 收到停止信号\n")
        finally:
            await self.stop()

# ==================== 信号处理 ====================

nbot_system = None

def signal_handler(signum, frame):
    """信号处理器"""
    global nbot_system
    print("\n 收到停止信号，正在优雅关闭...")
    if nbot_system:
        try:
            # 创建新的事件循环来运行停止逻辑
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(nbot_system.stop())
            loop.close()
        except Exception as e:
            print(f"停止过程出错: {e}")
    sys.exit(0)

# 注册信号处理器
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ==================== 主函数 ====================

async def main():
    """主函数"""
    global nbot_system
    
    try:
        smooth_print(" 欢迎使用Nbot智能聊天机器人\n")
        smooth_print("="*50 + "\n")
        
        # 检查环境变量
        if BOXIM_USERNAME == "Nbot" and BOXIM_PASSWORD == "a31415926535":
            smooth_print("️ 使用默认账号密码，建议设置环境变量 BOXIM_USERNAME 和 BOXIM_PASSWORD\n")
        
        # 创建并启动系统
        nbot_system = NbotSystem()
        
        if await nbot_system.start():
            smooth_print(" 系统启动完成，开始自主运行\n")
            smooth_print("按 Ctrl+C 停止系统\n")
            smooth_print("="*50 + "\n")
            
            # 运行系统
            await nbot_system.run_forever()
        else:
            smooth_print(" 系统启动失败\n")
            sys.exit(1)
            
    except KeyboardInterrupt:
        smooth_print("\n 用户主动停止\n")
    except Exception as e:
        logger.error(f"主函数出错: {e}")
        smooth_print(f" 系统错误: {e}\n")
        traceback.print_exc()
    finally:
        if nbot_system:
            await nbot_system.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n 程序已停止")
    except Exception as e:
        print(f" 程序异常退出: {e}")
        traceback.print_exc()
