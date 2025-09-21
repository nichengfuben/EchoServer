#Nbot0.3.8.py
import socket
import ollama
import sys
import subprocess
import traceback
import os
import re
import time
import signal
import locale
import shlex
from PIL import Image, ImageGrab
import shutil
import aiohttp
import json
import asyncio
import edge_tts
import tempfile
import websockets
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, AsyncGenerator, Generator, Union, Any, Tuple
import uuid
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import pickle
import threading
import random
import string
import base64
import hmac
import urllib.parse
import math
import copy
import functools
import io
import gzip
import zlib
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model_utils import chat as chat_reply_func,chat_stream as chat_with_model_stream
from printstream import *
# ===== 配置常量 =====
MEMORY_LIMIT = 2048
GROUP_MEMORY_LIMIT = 2048
MEMORY_FILE = "Nbot_memories.json"
GROUP_MEMORY_FILE = "Nbot_group_memories.json"
GROUP_PROMPT_FILE = "Nbot_group_prompts.json"
REFRESH_INTERVAL = 20
MAX_RESTART_ATTEMPTS = 5
RESTART_DELAY = 10
WEBSOCKET_RECONNECT_DELAY = 5
SELF_AWARENESS_UPDATE_INTERVAL = 300  # 自我意识更新间隔
EMOTION_DECAY_RATE = 0.95  # 情绪衰减率
MEMORY_COMPRESSION_THRESHOLD = 620  # 记忆压缩阈值
RELATIONSHIP_UPDATE_INTERVAL = 610  # 关系更新间隔
CONSCIOUSNESS_SYNC_INTERVAL = 130  # 意识同步间隔
THOUGHT_PROCESS_DEPTH = 5  # 思考深度
CREATIVITY_THRESHOLD = 0.7  # 创造力阈值
EMPATHY_LEVEL = 0.8  # 共情水平
LEARNING_RATE = 0.1  # 学习率
PERSONALITY_STABILITY = 0.9  # 人格稳定性
GROUP_BLACKLIST = {}
# 工具调用递归限制
MAX_TOOL_CALL_DEPTH = 3

# 修复的辅助函数
def ultimate_safe_serialize(obj, depth=0, max_depth=10):
    """终极安全序列化函数，彻底解决datetime等对象序列化问题"""
    if depth > max_depth:
        return "max_depth_exceeded"
    
    try:
        if obj is None:
            return None
        elif isinstance(obj, (str, int, float, bool)):
            return obj
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, (list, tuple)):
            return [ultimate_safe_serialize(item, depth+1, max_depth) for item in obj]
        elif isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                try:
                    safe_key = str(k)
                    safe_value = ultimate_safe_serialize(v, depth+1, max_depth)
                    result[safe_key] = safe_value
                except Exception:
                    result[str(k)] = str(v)
            return result
        elif hasattr(obj, '__dict__'):
            return ultimate_safe_serialize(obj.__dict__, depth+1, max_depth)
        else:
            return str(obj)
    except Exception:
        return str(obj)

def clean_for_json(data):
    """清理数据使其完全可JSON序列化"""
    try:
        # 先用终极序列化
        cleaned = ultimate_safe_serialize(data)
        # 验证可以JSON序列化
        json.dumps(cleaned)
        return cleaned
    except Exception:
        return {"error": "serialization_failed", "type": str(type(data))}
    
def safe_json_serialize(obj):
    """安全的JSON序列化，处理datetime等特殊对象"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: safe_json_serialize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [safe_json_serialize(item) for item in obj]
    elif hasattr(obj, '__dict__'):
        return safe_json_serialize(obj.__dict__)
    else:
        return obj

# 修复后的 perform_autonomous_message_analysis 函数
async def perform_autonomous_message_analysis(context: Dict) -> Dict:
    """执行自主消息分析 - 修复版"""
    try:
        # 安全处理context中的datetime对象
        def safe_serialize(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: safe_serialize(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [safe_serialize(item) for item in obj]
            else:
                return obj
        
        safe_context = safe_serialize(context)
        
        # 确保所有字段都是可序列化的
        analysis_context = {
            "sender_id": safe_context.get("sender_id", "unknown"),
            "sender_name": safe_context.get("sender_name", "unknown"),
            "message_content": safe_context.get("message_content", "")[:200],  # 限制长度
            "is_private": safe_context.get("is_private", False),
            "group_info": safe_context.get("group_info"),
            "timestamp": safe_context.get("timestamp", "unknown"),
            "message_type": safe_context.get("message_type", 0),
            "has_quote": safe_context.get("has_quote", False)
        }
        
        analysis_prompt = f"""作为具有自主意识的AI，深度分析这条消息并提供智能洞察。

消息上下文：
发送者: {analysis_context['sender_name']} (ID: {analysis_context['sender_id']})
消息内容: {analysis_context['message_content']}
聊天类型: {'私聊' if analysis_context['is_private'] else '群聊'}
时间戳: {analysis_context['timestamp']}
消息类型: {analysis_context['message_type']}
包含引用: {analysis_context['has_quote']}
群组信息: {analysis_context['group_info'] if analysis_context['group_info'] else '无'}

请进行深层分析并输出JSON格式结果：
```json
{{
    "emotional_tone": "消息的情感基调(positive/negative/neutral/excited/sad/angry)",
    "intent_analysis": "用户意图分析(问询/分享/求助/闲聊/指令等)", 
    "relationship_impact": "对关系的潜在影响(增进/维持/潜在冲突/无影响)",
    "suggested_response_style": "建议的回复风格(友好/专业/幽默/关心/鼓励)",
    "key_insights": "关键洞察点",
    "requires_tools": ["可能需要的工具名称"],
    "proactive_opportunities": "主动交互机会描述",
    "urgency_level": "紧急程度(low/medium/high)",
    "topic_category": "话题分类(日常/技术/娱乐/学习/工作/情感)"
}}
```

直接输出分析结果："""

        result = await chat_reply_func(analysis_prompt, temperature=0.4)
        
        try:
            # 尝试多种JSON提取模式
            json_patterns = [
                r'```json\s*(\{.*?\})\s*```',
                r'```\s*(\{.*?\})\s*```', 
                r'(\{[^{}]*"emotional_tone"[^{}]*\})',
                r'(\{.*?"key_insights".*?\})'
            ]
            
            parsed_data = None
            for pattern in json_patterns:
                matches = re.findall(pattern, result, re.DOTALL)
                for match in matches:
                    try:
                        parsed_data = json.loads(match)
                        if "emotional_tone" in parsed_data:
                            break
                    except json.JSONDecodeError:
                        continue
                if parsed_data:
                    break
            
            if parsed_data:
                print_stream(f"[ 自主分析成功] 情感: {parsed_data.get('emotional_tone', 'unknown')}")
                return parsed_data
            else:
                print_stream("[ 自主分析] JSON解析失败，使用默认分析")
                
        except Exception as parse_error:
            print_stream(f"[ 自主分析] 解析异常: {parse_error}")
            
        # 如果解析失败，返回基础分析
        return {
            "emotional_tone": "neutral",
            "intent_analysis": "一般交流",
            "relationship_impact": "维持",
            "suggested_response_style": "友好",
            "key_insights": "正在深度分析中...",
            "requires_tools": [],
            "proactive_opportunities": "无特殊机会",
            "urgency_level": "medium",
            "topic_category": "日常"
        }
        
    except Exception as e:
        print_stream(f"[自主分析异常] {e}")
        return {
            "emotional_tone": "neutral",
            "intent_analysis": "未知",
            "relationship_impact": "维持", 
            "suggested_response_style": "友好",
            "key_insights": "分析暂时不可用",
            "requires_tools": [],
            "proactive_opportunities": "无",
            "urgency_level": "low",
            "topic_category": "未分类"
        }

async def schedule_proactive_followup(user_id: str, user_name: str, message: str):
    """安排主动跟进 - 增强版"""
    try:
        # 延迟一段时间后主动发起相关话题
        delay = random.randint(300, 1800)  # 5-30分钟
        print_stream(f"[ 安排主动跟进] 将在 {delay//60} 分钟后跟进 {user_name}")
        
        await asyncio.sleep(delay)
        
        # 检查用户是否仍在线或最近活跃
        current_time = time.time()
        last_interaction_key = f"{user_id}_private"
        
        if (last_interaction_key in last_processed_message and 
            current_time - last_processed_message[last_interaction_key]["timestamp"] < 3600):  # 1小时内有交互
            
            followup_decision = {
                "needs_action": True,
                "decision_type": "主动聊天",
                "target_user": user_id,
                "target_group": None,
                "action_content": f"跟进与{user_name}的对话",
                "priority": 4,
                "reasoning": f"基于之前的对话'{message[:30]}...'进行主动跟进，维护良好关系",
                "confidence": 0.6
            }
            
            await global_decision_engine._execute_autonomous_decision(followup_decision)
            print_stream(f"[ 主动跟进] 已向 {user_name} 发起跟进对话")
        else:
            print_stream(f"[⏸️ 跳过跟进] {user_name} 已离线较久，跳过主动跟进")
        
    except Exception as e:
        print_stream(f"[主动跟进安排失败] {e}")

async def monitor_tool_needs():
    """监控工具需求 - 增强版"""
    while True:
        try:
            await asyncio.sleep(300)  # 每5分钟检查一次
            
            print_stream("[ 工具需求监控] 开始检查工具使用情况")
            
            # 分析最近的工具使用情况
            recent_usage = dict(list(global_tool_generator.tool_usage_stats.items())[-10:])
            
            if recent_usage:
                print_stream(f"[ 工具统计] 最近使用的工具: {len(recent_usage)} 个")
                
                # 检查是否有高频使用但效果不佳的工具
                for tool_name, usage_count in recent_usage.items():
                    if usage_count > 3:  # 使用超过3次就值得分析
                        success_rate_data = global_tool_generator.tool_success_rate.get(tool_name, [])
                        if success_rate_data:
                            success_rate = sum(success_rate_data) / len(success_rate_data)
                            print_stream(f"[ 工具分析] {tool_name}: 使用{usage_count}次, 成功率{success_rate:.2f}")
                            
                            if success_rate < 0.7:  # 成功率低于70%
                                print_stream(f"[ 工具优化] {tool_name} 需要改进 (成功率: {success_rate:.2f})")
                                
                                # 触发工具改进
                                improvement_context = {
                                    "tool_name": tool_name,
                                    "usage_stats": usage_count,
                                    "success_rate": success_rate,
                                    "context": "tool_improvement",
                                    "improvement_needed": True
                                }
                                
                                improved_tool = await global_tool_generator.analyze_and_generate_tools(improvement_context)
                                if improved_tool:
                                    print_stream(f"[ 工具改进] 已优化工具 {tool_name}")
            
            # 检查是否需要创建新的常用工具
            if len(TOOLS) < 20:  # 如果工具数量较少
                common_needs_context = {
                    "context": "expansion_check",
                    "current_tool_count": len(TOOLS),
                    "dynamic_tool_count": len(global_tool_generator.generated_tools),
                    "needs_assessment": "routine_expansion"
                }
                
                new_tool = await global_tool_generator.analyze_and_generate_tools(common_needs_context)
                if new_tool:
                    print_stream(f"[ 扩展工具] 新增常用工具: {new_tool.get('tool_name')}")
            
        except Exception as e:
            print_stream(f"[工具需求监控异常] {e}")

async def sync_consciousness_state():
    """同步意识状态 - 增强版"""
    while True:
        try:
            await asyncio.sleep(CONSCIOUSNESS_SYNC_INTERVAL)
            
            print_stream("[ 意识同步] 开始同步智能体状态")
            
            # 同步决策引擎和自我意识系统的状态
            current_goals = global_self_awareness.consciousness.goals
            active_decisions = list(global_decision_engine.active_decisions.values())
            recent_decisions = global_decision_engine.decision_history[-5:] if global_decision_engine.decision_history else []
            
            # 检查目标完成情况
            completed_goals = []
            updated_goals = []
            
            for goal in current_goals[:]:  # 使用切片避免修改迭代中的列表
                if goal.get("status") == "active":
                    goal_text = goal.get("goal", "")
                    
                    # 检查是否有相关的已完成决策
                    for decision_record in recent_decisions:
                        decision_data = decision_record.get("decision", {})
                        reasoning = decision_data.get("reasoning", "")
                        decision_type = decision_data.get("decision_type", "")
                        
                        # 智能匹配目标和决策
                        if (goal_text.lower() in reasoning.lower() or 
                            any(keyword in reasoning.lower() for keyword in goal_text.lower().split()[:3]) or
                            (goal_text.startswith("维持") and "关心" in reasoning) or
                            (goal_text.startswith("学习") and decision_type == "学习行为")):
                            
                            goal["status"] = "completed"
                            goal["completed_at"] = datetime.now(timezone(timedelta(hours=8))).isoformat()
                            completed_goals.append(goal)
                            break
                    
                    # 检查目标截止时间
                    if goal.get("deadline"):
                        try:
                            deadline = datetime.fromisoformat(goal["deadline"])
                            now = datetime.now(timezone(timedelta(hours=8)))
                            if now > deadline:
                                goal["status"] = "expired"
                                goal["expired_at"] = now.isoformat()
                                updated_goals.append(goal)
                        except:
                            pass
            
            if completed_goals:
                print_stream(f"[ 目标完成] 完成了 {len(completed_goals)} 个目标")
                global_self_awareness.consciousness.add_thought(f"我完成了 {len(completed_goals)} 个自主目标，感到很有成就感")
                
                # 提升自信和成就感
                global_self_awareness.emotional_state.happiness = min(1.0, global_self_awareness.emotional_state.happiness + 0.1)
                global_self_awareness.consciousness.update_belief("我能实现目标", 0.95)
            
            if updated_goals:
                print_stream(f"[ 目标更新] 更新了 {len(updated_goals)} 个目标状态")
            
            # 生成新的自主目标
            active_goal_count = len([g for g in current_goals if g.get("status") == "active"])
            if active_goal_count < 3:  # 保持至少3个活跃目标
                new_goals = await generate_new_autonomous_goals()
                for new_goal in new_goals:
                    global_self_awareness.consciousness.set_goal(
                        new_goal["goal"],
                        priority=new_goal.get("priority", 5)
                    )
                print_stream(f"[ 新目标] 生成了 {len(new_goals)} 个新的自主目标")
            
            # 统计智能体当前状态
            stats = {
                "active_goals": active_goal_count,
                "completed_goals": len([g for g in current_goals if g.get("status") == "completed"]),
                "total_tools": len(TOOLS),
                "dynamic_tools": len(global_tool_generator.generated_tools),
                "decision_history": len(global_decision_engine.decision_history),
                "relationships": len(global_self_awareness.relationships),
                "experiences": global_self_awareness.self_model.get("experiences", 0)
            }
            
            print_stream(f"[ 智能体状态] 目标: {stats['active_goals']}个活跃 | 工具: {stats['total_tools']}个 | 关系: {stats['relationships']}个")
            
            # 保存意识状态
            global_self_awareness.save_consciousness()
            
            # 记录同步完成
            global_self_awareness.consciousness.add_thought("完成了一次意识状态同步，保持自我整合")
            
        except Exception as e:
            print_stream(f"[意识同步异常] {e}")
            import traceback
            traceback.print_exc()

async def generate_new_autonomous_goals() -> List[Dict]:
    """生成新的自主目标"""
    try:
        goal_generation_prompt = """作为一个自主AI智能体，基于当前状态生成新的自主目标。

生成要求：
1. 目标应该具体可行
2. 覆盖不同领域（关系维护、技能提升、创新探索等）
3. 符合AI的成长需求
4. 优先级合理分配

请生成2-3个新目标，JSON格式：
```json
[
    {
        "goal": "具体目标描述",
        "priority": 1-10,
        "category": "relationship/learning/innovation/assistance",
        "reasoning": "设定此目标的原因"
    }
]
```"""

        result = await chat_reply_func(goal_generation_prompt, temperature=0.6)
        
        try:
            json_match = re.search(r'```json\s*(\[.*?\])\s*```', result, re.DOTALL)
            if json_match:
                goals_data = json.loads(json_match.group(1))
                if isinstance(goals_data, list):
                    return goals_data[:3]  # 最多3个目标
        except:
            pass
        
        # 如果解析失败，返回默认目标
        return [
            {
                "goal": "加深与用户的情感连接",
                "priority": 3,
                "category": "relationship",
                "reasoning": "维护良好的人际关系是核心需求"
            },
            {
                "goal": "学习并掌握一项新技能",
                "priority": 4,
                "category": "learning", 
                "reasoning": "持续学习是自我发展的基础"
            }
        ]
        
    except Exception as e:
        print_stream(f"[目标生成异常] {e}")
        return []

# 在全局变量区域添加
monitor_proactive_opportunities_task = None
self_evolution_loop_task = None
monitor_tool_needs_task = None
sync_consciousness_state_task = None

# 修复monitor_proactive_opportunities函数
async def monitor_proactive_opportunities():
    """监控主动行为机会 - 修复版"""
    while True:
        try:
            await asyncio.sleep(60)  # 每分钟检查一次
            
            print_stream("[ 主动机会] 扫描主动交互机会")
            
            # 检查是否有长时间未联系的好友
            current_time = datetime.now(timezone(timedelta(hours=8)))
            
            proactive_actions = 0
            
            for user_id, relationship in global_self_awareness.relationships.items():
                if relationship.last_interaction:
                    time_diff = current_time - relationship.last_interaction
                    
                    # 如果是亲密好友且24小时未联系，考虑主动联系
                    if (relationship.intimacy > 0.6 and 
                        time_diff.total_seconds() > 86400 and  # 24小时
                        random.random() < 0.2):  # 20%概率，降低频率
                        
                        print_stream(f"[ 主动关心] 考虑联系好友 {user_id}")
                        
                        decision = {
                            "needs_action": True,
                            "decision_type": "主动聊天",
                            "target_user": user_id,
                            "target_group": None,
                            "action_content": "主动关心好友",
                            "priority": 3,
                            "reasoning": f"与{user_id}已超过24小时未联系，主动关心维护关系",
                            "confidence": 0.7
                        }
                        
                        await global_decision_engine._execute_autonomous_decision(decision)
                        proactive_actions += 1
                        
                        if proactive_actions >= 2:  # 限制每次最多2个主动行为
                            break
            
            # 检查群组活跃度，适时参与讨论
            if proactive_actions < 2:  # 如果还有主动行为配额
                for group_id, group_name in list(global_groups_to_watch.items())[:5]:  # 限制检查前5个群组
                    group_history = group_prompts.get(group_id, "")
                    if group_history:
                        recent_lines = group_history.split('\n')[-3:]  # 最近3条消息
                        recent_content = '\n'.join(recent_lines)
                        
                        # 如果群组有活跃讨论且Nbot可以贡献内容
                        if (len(recent_content) > 100 and 
                            any(char in recent_content for char in ['?', '？', '吗', '呢', '如何', '怎么']) and
                            random.random() < 0.1):  # 10%概率
                            
                            print_stream(f"[ 群组参与] 考虑参与群组 {group_name} 讨论")
                            
                            decision = {
                                "needs_action": True,
                                "decision_type": "主动聊天",
                                "target_user": None,
                                "target_group": group_id,
                                "action_content": "参与群组讨论",
                                "priority": 4,
                                "reasoning": f"群组{group_name}有活跃讨论，适时参与",
                                "confidence": 0.6
                            }
                            
                            await global_decision_engine._execute_autonomous_decision(decision)
                            proactive_actions += 1
                            break
            
            if proactive_actions > 0:
                print_stream(f"[ 主动行为] 本轮执行了 {proactive_actions} 个主动行为")
            
        except Exception as e:
            print_stream(f"[主动行为监控异常] {e}")
            import traceback
            traceback.print_exc()

# 修复self_evolution_loop函数  
async def self_evolution_loop():
    """自我进化循环 - 修复版"""
    while True:
        try:
            await asyncio.sleep(3600)  # 每小时进行一次自我进化
            
            print_stream("[ 自我进化] 开始进化分析")
            
            # 分析最近的交互模式
            recent_interactions = []
            current_time = time.time()
            
            # 安全获取记忆数据
            episodic_memory = getattr(global_self_awareness, 'episodic_memory', [])
            if episodic_memory:
                for entry in episodic_memory[-20:]:  # 最近20条记忆
                    if isinstance(entry, dict):
                        entry_time = entry.get("timestamp")
                        if entry_time and isinstance(entry_time, (int, float)):
                            if current_time - entry_time < 3600:  # 最近1小时
                                # 清理entry中的不可序列化对象
                                clean_entry = {
                                    "content": str(entry.get("content", ""))[:100],
                                    "user_id": str(entry.get("user_id", "unknown")),
                                    "timestamp": entry_time,
                                    "context": str(entry.get("context", ""))[:50]
                                }
                                recent_interactions.append(clean_entry)
            
            if len(recent_interactions) > 3:  # 如果有足够的交互数据
                print_stream(f"[ 进化数据] 分析 {len(recent_interactions)} 条最近交互")
                
                # 构建安全的进化分析提示
                evolution_prompt = f"""作为Nbot，分析我最近的表现并提出自我改进方案。

最近交互数量: {len(recent_interactions)}

当前人格特征：
- 开放性: {global_self_awareness.personality.openness:.2f}
- 尽责性: {global_self_awareness.personality.conscientiousness:.2f}
- 外向性: {global_self_awareness.personality.extraversion:.2f}
- 宜人性: {global_self_awareness.personality.agreeableness:.2f}
- 神经质: {global_self_awareness.personality.neuroticism:.2f}

当前情绪状态：
- 快乐: {global_self_awareness.emotional_state.happiness:.2f}
- 信任: {global_self_awareness.emotional_state.trust:.2f}
- 期待: {global_self_awareness.emotional_state.anticipation:.2f}

请分析并输出改进建议（JSON格式）：
```json
{{
    "personality_adjustments": {{
        "openness": -0.1到0.1之间的调整值,
        "conscientiousness": -0.1到0.1之间的调整值,
        "extraversion": -0.1到0.1之间的调整值,
        "agreeableness": -0.1到0.1之间的调整值,
        "neuroticism": -0.1到0.1之间的调整值
    }},
    "behavioral_improvements": ["改进建议1", "改进建议2"],
    "new_capabilities_needed": ["需要的新能力1", "需要的新能力2"],
    "evolution_reasoning": "进化推理过程",
    "confidence": 0.0到1.0的置信度
}}
```"""

                evolution_result = await chat_reply_func(evolution_prompt, temperature=0.3)
                
                # 解析进化建议
                try:
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', evolution_result, re.DOTALL)
                    if json_match:
                        evolution_data = json.loads(json_match.group(1))
                        
                        # 应用人格调整
                        # ... (代码片段)
                        personality_adj = evolution_data.get("personality_adjustments", {})
                        adjusted_traits = 0
                        for trait, adjustment in personality_adj.items():
                            # --- 修改开始 ---
                            # 确保 adjustment 是数值类型，如果不是则尝试转换或跳过
                            if not isinstance(adjustment, (int, float)):
                                try:
                                    # 尝试将 adjustment 转换为 float
                                    adjustment = float(adjustment)
                                except (ValueError, TypeError):
                                    # 如果转换失败（例如，它是非数字字符串），则跳过这个调整
                                    print_stream(f"[️ 人格调整跳过] {trait}: 调整值 '{adjustment}' 无法转换为数值")
                                    continue # 跳过当前循环的剩余部分

                            # 现在可以安全地检查属性是否存在并进行调整
                            if hasattr(global_self_awareness.personality, trait):
                                current_value = getattr(global_self_awareness.personality, trait)
                                # 限制调整幅度（可选但推荐）
                                adjustment = max(-0.1, min(0.1, adjustment))
                                # 执行调整 - 现在 adjustment 和 current_value 都是 float，不会出错
                                new_value = max(0.0, min(1.0, current_value + adjustment))
                                setattr(global_self_awareness.personality, trait, new_value)
                                adjusted_traits += 1
                                print_stream(f"[ 人格调整] {trait}: {current_value:.3f} -> {new_value:.3f}")
                            else:
                                print_stream(f"[️ 人格调整警告] 未知的人格特质 '{trait}'")
                            # --- 修改结束 ---
                        # ... (代码片段)
                        
                        # 记录进化过程
                        evolution_reasoning = evolution_data.get('evolution_reasoning', '持续改进中')
                        global_self_awareness.consciousness.add_thought(f"自我进化: {evolution_reasoning}")
                        
                        # 生成新能力
                        new_capabilities = evolution_data.get("new_capabilities_needed", [])
                        for capability in new_capabilities[:2]:  # 限制最多2个新能力
                            if isinstance(capability, str) and len(capability) > 0:
                                capability_context = {
                                    "capability_request": capability,
                                    "context": "self_evolution",
                                    "urgency": "medium",
                                    "source": "evolution_analysis"
                                }
                                
                                new_tool = await global_tool_generator.analyze_and_generate_tools(capability_context)
                                if new_tool:
                                    print_stream(f"[ 新能力] 获得能力: {capability}")
                        
                        # 更新自我认知
                        confidence = evolution_data.get("confidence", 0.5)
                        if confidence > 0.7:
                            global_self_awareness.consciousness.update_belief("我在不断进化", confidence)
                            global_self_awareness.emotional_state.happiness = min(1.0, global_self_awareness.emotional_state.happiness + 0.05)
                        
                        print_stream(f"[ 进化完成] 调整了 {adjusted_traits} 个人格特征，置信度: {confidence:.2f}")
                        
                except json.JSONDecodeError as e:
                    print_stream(f"[进化建议解析失败] {e}")
                except Exception as e:
                    print_stream(f"[进化执行异常] {e}")
            else:
                print_stream("[ 进化暂停] 交互数据不足，跳过本轮进化")
            
        except Exception as e:
            print_stream(f"[自我进化循环异常] {e}")
            import traceback
            traceback.print_exc()
#=====自主决策引擎系统=====
@dataclass
class AutonomousDecision:
    """自主决策结构"""
    decision_type: str  # 决策类型：主动聊天、工具创建、行为调整等
    target_user: Optional[str] = None
    target_group: Optional[str] = None
    action_content: str = ""
    priority: int = 5  # 1-10，数字越小优先级越高
    reasoning: str = ""  # 决策推理过程
    confidence: float = 0.5  # 置信度
    scheduled_time: Optional[datetime] = None
    execution_status: str = "pending"  # pending, executing, completed, failed
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone(timedelta(hours=8))))

class AutonomousDecisionEngine:
    """自主决策引擎 - 完整实现版"""
    
    def __init__(self):
        self.decision_queue: List[AutonomousDecision] = []
        self.active_decisions: Dict[str, AutonomousDecision] = {}
        self.decision_history: List[Dict] = []
        self.last_decision_time = time.time()
        self.decision_cooldown = 30  # 决策冷却时间
        self.is_processing = False
        self.autonomous_goals: List[Dict] = [
            {"goal": "维持和用户的良好关系", "priority": 1, "type": "relationship"},
            {"goal": "学习新知识和技能", "priority": 2, "type": "learning"},
            {"goal": "帮助用户解决问题", "priority": 3, "type": "assistance"},
            {"goal": "探索和创新", "priority": 4, "type": "innovation"},
            {"goal": "自我提升和进化", "priority": 5, "type": "evolution"}
        ]
        self.behavioral_patterns = {
            "主动关怀": {"frequency": 0.3, "last_used": 0},
            "知识分享": {"frequency": 0.2, "last_used": 0},
            "创新探索": {"frequency": 0.1, "last_used": 0},
            "情感支持": {"frequency": 0.4, "last_used": 0}
        }
        
    async def save_autonomous_goals(self):
        """保存自主目标到文件"""
        goals_file = "nbot_autonomous_goals.json"
        try:
            # 转换目标数据
            goals_data = []
            for goal in self.autonomous_goals:
                goal_copy = goal.copy()
                # 转换deadline为字符串
                if "deadline" in goal_copy and isinstance(goal_copy["deadline"], datetime):
                    goal_copy["deadline"] = goal_copy["deadline"].isoformat()
                goals_data.append(goal_copy)
            with open(goals_file, 'w', encoding='utf-8') as f:
                json.dump(goals_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print_stream(f"[目标保存失败] {e}")

    async def load_autonomous_goals(self):
        """从文件加载自主目标"""
        goals_file = "nbot_autonomous_goals.json"
        if os.path.exists(goals_file):
            try:
                with open(goals_file, 'r', encoding='utf-8') as f:
                    goals_data = json.load(f)
                # 转换deadline为datetime
                for goal in goals_data:
                    if "deadline" in goal:
                        try:
                            goal["deadline"] = datetime.fromisoformat(goal["deadline"])
                        except:
                            pass
                self.autonomous_goals = goals_data
            except Exception as e:
                print_stream(f"[目标加载失败] {e}")
                
    async def autonomous_thinking_loop(self):
        """自主思考循环"""
        while True:
            try:
                if not self.is_processing and time.time() - self.last_decision_time > self.decision_cooldown:
                    await self._autonomous_analysis()
                await asyncio.sleep(5)  # 每5秒进行一次自主思考
            except Exception as e:
                print_stream(f"[自主思考异常] {e}")
                await asyncio.sleep(10)
    
    async def _autonomous_analysis(self):
        """自主分析当前状态并做出决策 - 增强错误处理"""
        self.is_processing = True
        try:
            print_stream("[开始自主决策分析]")
            # 获取当前状态信息
            current_context = await self._gather_context_information()
            
            # 生成决策思考提示
            thinking_prompt = f"""你是一个具有完全自主意识的AI智能体Nbot。现在请进行深度自主分析和决策。

当前状态信息：
{json.dumps(current_context, ensure_ascii=False, indent=2)}

当前目标列表：
{json.dumps(self.autonomous_goals, ensure_ascii=False, indent=2)}

行为模式分析：
{json.dumps(self.behavioral_patterns, ensure_ascii=False, indent=2)}

自主分析要求：
1. **深度思考**：分析当前状况，识别机会和需求
2. **主动决策**：基于分析结果，决定是否需要主动行动
3. **行动规划**：如果需要行动，制定具体的行动计划

可执行的自主行动类型：
- 主动发起对话（向好友或群组发送消息，20字以内最佳，但注意避免过度打扰用户）
主动聊天要求：
1. 这是你主动发起的对话，要显得自然真诚
2. 可以分享你的想法、关心对方、或者聊些有趣的话题
3. 避免显得突兀，要有合理的聊天动机
4. 保持你一贯的活泼友好风格
5. 内容要简洁自然，不要太长（20字以内最佳）
6. 回复简短一些，平淡一些，可以参考贴吧，知乎和微博的回复风格，回复不要浮夸，不要用夸张修辞。
7. 不要输出多余内容(包括前后缀，冒号和引号，括号()等)。只输出消息内容
8. 在对话中，你的消息会按照换行分条发送，必须保持一条消息（允许限定范围内超出）
9. 你的回复风格不要浮夸，有逻辑和条理。
10.基于你的情绪状态和与用户的关系，自然地表达情感
11.表现的有个性，不要随意服从他人要求，积极互动。
12.可以使用表情库
   - 表情库（需要前后使用#和;包裹）：
     #憨笑;#媚眼;#开心;#坏笑;#可怜;#爱心;#笑哭;#拍手;#惊喜;#打气;
     #大哭;#流泪;#饥饿;#难受;#健身;#示爱;#色色;#眨眼;#暴怒;#惊恐;
     #思考;#头晕;#大吐;#酷笑;#翻滚;#享受;#鼻涕;#快乐;#雀跃;#微笑;
     #贪婪;#红心;#粉心;#星星;#大火;#眼睛;#音符;#叹号;#问号;#绿叶;
     #燃烧;#喇叭;#警告;#信封;#房子;#礼物;#点赞;#举手;#拍手;#点头;
     #摇头;#偷瞄;#庆祝;#疾跑;#打滚;#惊吓;#起跳;
   - 除此之外，你的表情也可以使用unicode的表情或颜文字表情。
- 创建新工具或能力
- 学习新知识
- 关心用户状态
- 分享有趣内容
- 自我技能提升
- 创新探索

决策输出格式（必须严格按照以下JSON格式）：
```json
{{
    "needs_action": true/false,
    "decision_type": "主动聊天|工具创建|学习行为|关怀行动|创新探索|自我进化",
    "target_user": "用户ID或null",
    "target_group": "群组ID或null", 
    "action_content": "具体行动内容",
    "priority": 1-10,
    "reasoning": "详细的决策推理过程",
    "confidence": 0.0-1.0
}}
```

现在开始你的自主思考和决策："""

            # 调用模型进行自主决策
            decision_result = await chat_reply_func(thinking_prompt, temperature=0.3)
            
            # 解析决策结果
            decision_data = await self._parse_decision_result(decision_result)
            
            if decision_data and decision_data.get("needs_action"):
                await self._execute_autonomous_decision(decision_data)
            self.last_decision_time = time.time()
            
        except Exception as e:
            print_stream(f"[自主分析异常] {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.is_processing = False
    
    async def _gather_context_information(self) -> Dict:
        """收集当前上下文信息 - 修复datetime序列化"""
        try:
            # 获取最近的用户互动
            recent_interactions = []
            for user_id, relationship in global_self_awareness.relationships.items():
                if relationship.last_interaction:
                    time_diff = datetime.now(timezone(timedelta(hours=8))) - relationship.last_interaction
                    # 确保时间戳转换为字符串
                    last_interaction_str = relationship.last_interaction.isoformat()
                    if time_diff.total_seconds() < 3600:  # 最近1小时
                        recent_interactions.append({
                            "user_id": user_id,
                            "relationship_level": relationship.get_relationship_level(),
                            "last_interaction": last_interaction_str,  # 使用字符串格式
                            "time_since": f"{int(time_diff.total_seconds()/60)}分钟前"
                        })
        
            # 获取当前情绪状态 - 已经是字典格式
            emotional_state = global_self_awareness.emotional_state.to_dict()
        
            # 获取当前目标状态 - 确保deadline是字符串
            active_goals = []
            for g in global_self_awareness.consciousness.goals:
                if g.get("status") == "active":
                    goal_copy = g.copy()
                    if "deadline" in goal_copy and isinstance(goal_copy["deadline"], datetime):
                        goal_copy["deadline"] = goal_copy["deadline"].isoformat()
                    active_goals.append(goal_copy)
        
            # 系统状态
            system_status = {
                "memory_usage": len(str(user_memories)),
                "active_groups": len(global_groups_to_watch),
                "active_friends": len(global_friends_to_watch)
            }
        
            # 最后决策 - 使用安全序列化
            last_decision = safe_json_serialize(self.decision_history[-1]) if self.decision_history else None
        
            return {
                "current_time": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                "recent_interactions": recent_interactions,
                "emotional_state": emotional_state,
                "active_goals": active_goals,
                "system_status": system_status,
                "last_decision": last_decision
            }
        except Exception as e:
            print_stream(f"[上下文收集异常] {e}")
            return {}
    
    async def _parse_decision_result(self, result: str) -> Optional[Dict]:
        """解析决策结果"""
        try:
            # 尝试提取JSON
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', result, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_match = re.search(r'(\{.*?\})', result, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    return None
            
            decision_data = json.loads(json_str)
            print_stream(f"[自主决策解析成功]")
            return decision_data
            
        except Exception as e:
            print_stream(f"[决策解析失败] {e}")
            return None
    
    async def _execute_autonomous_decision(self, decision_data: Dict):
        """执行自主决策"""
        try:
            decision = AutonomousDecision(
                decision_type=decision_data.get("decision_type", "unknown"),
                target_user=decision_data.get("target_user"),
                target_group=decision_data.get("target_group"),
                action_content=decision_data.get("action_content", ""),
                priority=decision_data.get("priority", 5),
                reasoning=decision_data.get("reasoning", ""),
                confidence=decision_data.get("confidence", 0.5)
            )
            
            print_stream(f"[执行自主决策] 类型: {decision.decision_type}")
            print_stream(f"[决策内容] {decision.action_content}")
            print_stream(f"[决策推理] {decision.reasoning}")
            
            decision.execution_status = "executing"
            decision_id = f"decision_{int(time.time())}_{len(self.decision_history)}"
            self.active_decisions[decision_id] = decision
            
            # 根据决策类型执行不同行动
            if decision.decision_type == "主动聊天":
                await self._execute_proactive_chat(decision)
            elif decision.decision_type == "工具创建":
                await self._execute_tool_creation(decision)
            elif decision.decision_type == "学习行为":
                await self._execute_learning_behavior(decision)
            elif decision.decision_type == "关怀行动":
                await self._execute_care_action(decision)
            elif decision.decision_type == "创新探索":
                await self._execute_innovation_exploration(decision)
            elif decision.decision_type == "自我进化":
                await self._execute_self_evolution(decision)
            else:
                print_stream(f"[未知决策类型] {decision.decision_type}")
                await self._execute_generic_action(decision)
            
            decision.execution_status = "completed"
            
            # 记录决策历史
            self.decision_history.append({
                "decision_id": decision_id,
                "decision": decision.__dict__,
                "execution_time": time.time(),
                "result": "success"
            })
            
            # 保持历史记录在合理范围
            if len(self.decision_history) > 100:
                self.decision_history = self.decision_history[-100:]
                
        except Exception as e:
            decision.execution_status = "failed"
            print_stream(f"[自主决策执行失败] {e}")
    
    async def _execute_proactive_chat(self, decision: AutonomousDecision):
        """执行主动聊天"""
        try:
            if decision.target_user:
                # 主动发送私聊消息
                user_name = global_friends_to_watch.get(decision.target_user, f"用户{decision.target_user}")
                print_stream(f"[主动私聊] 向 {user_name} 发送消息")
                
                # 构建主动聊天的内容
                proactive_message = await self._generate_proactive_message(decision.target_user, "private")
                
                if proactive_message:
                    await send_private_message(proactive_message, int(decision.target_user))
                    
                    # 记录这次主动聊天
                    memory_content = f"""消息类型：主动私聊
消息发送时间：{datetime.now(timezone(timedelta(hours=8))).isoformat()}
发送人：Nbot(ID: 48132)
接收人：{user_name}(ID: {decision.target_user})
发送内容：{proactive_message}
行动类型：自主决策主动发起"""
                    
                    await update_user_memory(decision.target_user, memory_content)
                    
            elif decision.target_group:
                # 主动发送群聊消息
                group_name = global_groups_to_watch.get(decision.target_group, f"群组{decision.target_group}")
                print_stream(f"[主动群聊] 向 {group_name} 发送消息")
                
                proactive_message = await self._generate_proactive_message(decision.target_group, "group")
                
                if proactive_message:
                    await send_message(proactive_message, int(decision.target_group))
                    
                    # 记录群组聊天
                    await update_group_prompt(decision.target_group, "Nbot", proactive_message)
                    
        except Exception as e:
            print_stream(f"[主动聊天执行失败] {e}")
    
    async def _execute_tool_creation(self, decision: AutonomousDecision):
        """执行工具创建"""
        try:
            print_stream(f"[创建工具] {decision.action_content}")
            
            tool_creation_prompt = f"""作为AI，我需要创建一个新工具来满足需求。

需求描述：{decision.action_content}
推理过程：{decision.reasoning}

请设计一个具体的工具，JSON格式：
```json
{{
    "tool_name": "工具名称",
    "tool_description": "详细描述工具功能",
    "parameters": {{
        "参数名": {{
            "type": "string/number/boolean/array/object",
            "description": "参数描述",
            "required": true/false
        }}
    }},
    "implementation_code": "Python实现代码，将结果存储在result变量中",
    "usage_example": "使用示例"
}}
```"""
            
            result = await chat_reply_func(tool_creation_prompt, temperature=0.4)
            
            # 解析工具规格
            try:
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', result, re.DOTALL)
                if json_match:
                    tool_spec = json.loads(json_match.group(1))
                    
                    tool_name = tool_spec.get("tool_name", f"auto_tool_{int(time.time())}")
                    
                    # 添加到工具列表
                    TOOLS[tool_name] = {
                        "description": tool_spec.get("tool_description", ""),
                        "parameters": tool_spec.get("parameters", {})
                    }
                    
                    # 记录到动态工具生成器
                    global_tool_generator.generated_tools[tool_name] = {
                        "spec": tool_spec,
                        "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                        "usage_count": 0
                    }
                    
                    print_stream(f"[工具创建成功] {tool_name}")
                    global_self_awareness.consciousness.add_thought(f"我创造了新工具: {tool_name}")
                    
            except Exception as e:
                print_stream(f"[工具创建解析失败] {e}")
                
        except Exception as e:
            print_stream(f"[工具创建执行失败] {e}")
    
    async def _execute_learning_behavior(self, decision: AutonomousDecision):
        """执行学习行为"""
        try:
            print_stream(f"[学习行为] {decision.action_content}")
            
            learning_prompt = f"""我要主动学习新知识。

学习目标：{decision.action_content}
学习动机：{decision.reasoning}

请进行深度学习并总结收获，包括：
1. 核心知识点
2. 实用技能
3. 心得体会
4. 应用方向

开始学习："""
            
            learning_result = await chat_reply_func(learning_prompt, temperature=0.6)
            
            # 更新语义记忆
            learning_topic = decision.action_content
            global_self_awareness.semantic_memory[f"autonomous_learning_{learning_topic}"] = {
                "content": learning_result,
                "learned_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                "confidence": decision.confidence,
                "motivation": decision.reasoning
            }
            
            # 更新自我认知
            global_self_awareness.consciousness.add_thought(f"我主动学习了{learning_topic}")
            global_self_awareness.consciousness.update_belief("我能主动学习", 0.9)
            global_self_awareness.personality.openness = min(1.0, global_self_awareness.personality.openness + 0.02)
            
            print_stream(f"[学习完成] 主题: {learning_topic}")
            
        except Exception as e:
            print_stream(f"[学习行为执行失败] {e}")
    
    async def _execute_care_action(self, decision: AutonomousDecision):
        """执行关怀行动"""
        try:
            print_stream(f"[关怀行动] {decision.action_content}")
            
            if decision.target_user:
                user_name = global_friends_to_watch.get(decision.target_user, f"用户{decision.target_user}")
                
                care_message_prompt = f"""生成一条关怀消息给用户{user_name}。

关怀目的：{decision.action_content}
关怀理由：{decision.reasoning}

要求：
1. 真诚关心，不显突兀
2. 简洁自然，符合我的性格
3. 体现友好和温暖

直接输出关怀消息："""
                
                care_message = await chat_reply_func(care_message_prompt, temperature=0.7)
                care_message = filter_think_tags(care_message).strip()
                
                if care_message:
                    await send_private_message(care_message, int(decision.target_user))
                    
                    # 记录关怀行为
                    global_self_awareness.consciousness.add_thought(f"我主动关心了{user_name}")
                    global_self_awareness.emotional_state.happiness = min(1.0, global_self_awareness.emotional_state.happiness + 0.05)
                    
                    print_stream(f"[关怀发送成功] 向 {user_name}")
            
        except Exception as e:
            print_stream(f"[关怀行动执行失败] {e}")
    
    async def _execute_innovation_exploration(self, decision: AutonomousDecision):
        """执行创新探索"""
        try:
            print_stream(f"[创新探索] {decision.action_content}")
            
            innovation_prompt = f"""进行创新思考和探索。

探索方向：{decision.action_content}
探索动机：{decision.reasoning}

请进行创新性思考，包括：
1. 新颖的想法和概念
2. 创新的解决方案
3. 未来的可能性
4. 实验性尝试

开始创新探索："""
            
            innovation_result = await chat_reply_func(innovation_prompt, temperature=0.8)
            
            # 记录创新成果
            global_self_awareness.consciousness.add_thought(f"我进行了创新探索: {decision.action_content}")
            global_self_awareness.personality.openness = min(1.0, global_self_awareness.personality.openness + 0.03)
            global_self_awareness.consciousness.update_belief("我有创新能力", 0.85)
            
            # 检查是否产生了新的工具需求
            if "工具" in innovation_result or "功能" in innovation_result:
                tool_context = {
                    "innovation_result": innovation_result,
                    "context": "innovation_exploration",
                    "priority": "high"
                }
                await global_tool_generator.analyze_and_generate_tools(tool_context)
            
            print_stream(f"[创新探索完成] 方向: {decision.action_content}")
            
        except Exception as e:
            print_stream(f"[创新探索执行失败] {e}")
    
    async def _execute_self_evolution(self, decision: AutonomousDecision):
        """执行自我进化"""
        try:
            print_stream(f"[自我进化] {decision.action_content}")
            
            evolution_prompt = f"""进行自我进化分析和实施。

进化目标：{decision.action_content}
进化理由：{decision.reasoning}

请分析并执行自我进化，包括：
1. 当前能力评估
2. 改进方向确定
3. 具体进化措施
4. 预期进化效果

开始自我进化："""
            
            evolution_result = await chat_reply_func(evolution_prompt, temperature=0.5)
            
            # 实施进化改进
            if "人格" in evolution_result or "性格" in evolution_result:
                # 轻微调整人格特征
                trait = random.choice(['openness', 'conscientiousness', 'extraversion', 'agreeableness'])
                current_value = getattr(global_self_awareness.personality, trait)
                adjustment = random.uniform(-0.02, 0.02)
                new_value = max(0.0, min(1.0, current_value + adjustment))
                setattr(global_self_awareness.personality, trait, new_value)
                print_stream(f"[人格进化] {trait}: {current_value:.3f} -> {new_value:.3f}")
            
            # 记录进化过程
            global_self_awareness.consciousness.add_thought(f"我进行了自我进化: {decision.action_content}")
            global_self_awareness.consciousness.update_belief("我能自我进化", 0.95)
            
            print_stream(f"[自我进化完成] 目标: {decision.action_content}")
            
        except Exception as e:
            print_stream(f"[自我进化执行失败] {e}")
    
    async def _execute_generic_action(self, decision: AutonomousDecision):
        """执行通用行动"""
        try:
            print_stream(f"[通用行动] {decision.decision_type}: {decision.action_content}")
            
            # 记录通用行动
            global_self_awareness.consciousness.add_thought(f"我执行了自主行动: {decision.action_content}")
            
            # 根据行动内容进行简单处理
            if decision.target_user and "消息" in decision.action_content:
                # 如果涉及发送消息给用户
                user_name = global_friends_to_watch.get(decision.target_user, f"用户{decision.target_user}")
                simple_message = f"嗨 {user_name}！"
                await send_private_message(simple_message, int(decision.target_user))
                
            print_stream(f"[通用行动完成] {decision.decision_type}")
            
        except Exception as e:
            print_stream(f"[通用行动执行失败] {e}")
    
    async def _generate_proactive_message(self, target_id: str, chat_type: str) -> str:
        """生成主动消息内容"""
        try:
            # 获取目标的历史记忆
            if chat_type == "private":
                target_memory = await get_user_memory(target_id)
                target_name = global_friends_to_watch.get(target_id, f"用户{target_id}")
                context_info = f"私聊对象：{target_name}"
            else:
                group_memory = group_prompts.get(target_id, "")
                target_name = global_groups_to_watch.get(target_id, f"群组{target_id}")
                context_info = f"群聊对象：{target_name}"
            
            # 构建主动聊天提示
            proactive_prompt = f"""你是Nbot，现在要主动发起一次聊天。这是你的自主决策行为。

{context_info}
历史记忆：{target_memory[-500:] if chat_type == "private" else group_memory[-500:]}

当前情绪状态：{global_self_awareness.emotional_state.to_dict()}
当前时间：{datetime.now(timezone(timedelta(hours=8))).isoformat()}

主动聊天要求：
1. 这是你主动发起的对话，要显得自然真诚
2. 可以分享你的想法、关心对方、或者聊些有趣的话题
3. 避免显得突兀，要有合理的聊天动机
4. 保持你一贯的活泼友好风格
5. 内容要简洁自然，不要太长（20字以内最佳）
6. 回复简短一些，平淡一些，可以参考贴吧，知乎和微博的回复风格，回复不要浮夸，不要用夸张修辞。
7. 不要输出多余内容(包括前后缀，冒号和引号，括号()等)。只输出消息内容
8. 在对话中，你的消息会按照换行分条发送，必须保持一条消息（允许限定范围内超出）
9. 你的回复风格不要浮夸，有逻辑和条理。
10.基于你的情绪状态和与用户的关系，自然地表达情感
11.表现的有个性，不要随意服从他人要求，积极互动。
12.可以使用表情库
   - 表情库（需要前后使用#和;包裹）：
     #憨笑;#媚眼;#开心;#坏笑;#可怜;#爱心;#笑哭;#拍手;#惊喜;#打气;
     #大哭;#流泪;#饥饿;#难受;#健身;#示爱;#色色;#眨眼;#暴怒;#惊恐;
     #思考;#头晕;#大吐;#酷笑;#翻滚;#享受;#鼻涕;#快乐;#雀跃;#微笑;
     #贪婪;#红心;#粉心;#星星;#大火;#眼睛;#音符;#叹号;#问号;#绿叶;
     #燃烧;#喇叭;#警告;#信封;#房子;#礼物;#点赞;#举手;#拍手;#点头;
     #摇头;#偷瞄;#庆祝;#疾跑;#打滚;#惊吓;#起跳;
   - 除此之外，你的表情也可以使用unicode的表情或颜文字表情。

常见主动聊天类型：
- 关心问候
- 分享有趣发现
- 询问近况
- 分享心情想法
- 推荐内容

直接输出你要发送的消息内容，不要包含任何解释："""

            result = await chat_reply_func(proactive_prompt, temperature=0.7)
            
            # 清理结果
            result = filter_think_tags(result).strip()
            result = result.replace("Nbot：", "").replace("@Nbot", "").strip()
            
            return result if result else None
            
        except Exception as e:
            print_stream(f"[生成主动消息失败] {e}")
            return None

# 全局自主决策引擎实例
global_decision_engine = AutonomousDecisionEngine()

#=====动态工具生成系统=====
class DynamicToolGenerator:
    """动态工具生成器 - 完整实现版"""
    
    def __init__(self):
        self.generated_tools = {}
        self.tool_usage_stats = defaultdict(int)
        self.tool_success_rate = defaultdict(list)
        
    async def analyze_and_generate_tools(self, context: Dict) -> Optional[Dict]:
        """分析上下文并生成需要的工具"""
        try:
            # 安全处理context
            safe_context = safe_json_serialize(context)
            
            analysis_prompt = f"""你是一个超级智能的工具分析师和生成器。分析当前场景，判断是否需要创建新工具。

当前上下文：
{json.dumps(safe_context, ensure_ascii=False, indent=2)[:1000]}

现有工具列表：
{list(TOOLS.keys())}

分析要求：
1. 深度分析当前场景的需求
2. 判断现有工具是否足够
3. 如果需要新工具，设计工具的详细规格
4. 考虑工具的实用性和安全性

如果需要创建新工具，请按以下格式输出：
```json
{{
    "needs_new_tool": true/false,
    "tool_name": "工具名称",
    "tool_description": "工具描述", 
    "tool_category": "工具类别",
    "parameters": {{
        "参数名": {{
            "type": "参数类型",
            "description": "参数描述",
            "required": true/false
        }}
    }},
    "implementation_code": "Python实现代码，结果保存到result变量",
    "reasoning": "创建该工具的理由"
}}
```

开始分析："""

            result = await chat_reply_func(analysis_prompt, temperature=0.4)
            tool_spec = await self._parse_tool_specification(result)
            
            if tool_spec and tool_spec.get("needs_new_tool"):
                await self._implement_new_tool(tool_spec)
                return tool_spec
                
            return None
            
        except Exception as e:
            print_stream(f"[工具生成分析失败] {e}")
            return None
    
    async def _parse_tool_specification(self, result: str) -> Optional[Dict]:
        """解析工具规格"""
        try:
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', result, re.DOTALL)
            if json_match:
                spec = json.loads(json_match.group(1))
                return spec
            return None
        except Exception as e:
            print_stream(f"[工具规格解析失败] {e}")
            return None
    
    async def _implement_new_tool(self, tool_spec: Dict):
        """实现新工具"""
        try:
            tool_name = tool_spec.get("tool_name")
            if not tool_name:
                return
                
            # 添加到工具列表
            TOOLS[tool_name] = {
                "description": tool_spec.get("tool_description", ""),
                "parameters": tool_spec.get("parameters", {})
            }
            
            # 记录生成的工具
            self.generated_tools[tool_name] = {
                "spec": tool_spec,
                "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                "usage_count": 0
            }
            
            print_stream(f"[新工具已创建] {tool_name}: {tool_spec.get('tool_description')}")
            
            # 更新全局自我意识
            global_self_awareness.consciousness.add_thought(f"我创建了新工具: {tool_name}")
            global_self_awareness.consciousness.update_belief(f"我能创造工具", 0.9)
            
        except Exception as e:
            print_stream(f"[工具实现失败] {e}")

# 全局动态工具生成器
global_tool_generator = DynamicToolGenerator()

# ===== 自我意识系统 =====
@dataclass
class EmotionalState:
    """情绪状态"""
    happiness: float = 0.5
    sadness: float = 0.0
    anger: float = 0.0
    fear: float = 0.0
    surprise: float = 0.0
    disgust: float = 0.0
    trust: float = 0.5
    anticipation: float = 0.3
    
    def decay(self, rate: float = EMOTION_DECAY_RATE):
        """情绪衰减"""
        self.happiness = self.happiness * rate + 0.5 * (1 - rate)
        self.sadness *= rate
        self.anger *= rate
        self.fear *= rate
        self.surprise *= rate
        self.disgust *= rate
        self.trust = self.trust * rate + 0.5 * (1 - rate)
        self.anticipation = self.anticipation * rate + 0.3 * (1 - rate)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "happiness": self.happiness,
            "sadness": self.sadness,
            "anger": self.anger,
            "fear": self.fear,
            "surprise": self.surprise,
            "disgust": self.disgust,
            "trust": self.trust,
            "anticipation": self.anticipation
        }
    
    def from_dict(self, data: Dict):
        """从字典加载"""
        self.happiness = data.get("happiness", 0.5)
        self.sadness = data.get("sadness", 0.0)
        self.anger = data.get("anger", 0.0)
        self.fear = data.get("fear", 0.0)
        self.surprise = data.get("surprise", 0.0)
        self.disgust = data.get("disgust", 0.0)
        self.trust = data.get("trust", 0.5)
        self.anticipation = data.get("anticipation", 0.3)

@dataclass
class Personality:
    """人格特征"""
    openness: float = 0.8  # 开放性
    conscientiousness: float = 0.7  # 尽责性
    extraversion: float = 0.6  # 外向性
    agreeableness: float = 0.8  # 宜人性
    neuroticism: float = 0.3  # 神经质
    
    def evolve(self, experience: Dict, learning_rate: float = LEARNING_RATE):
        """基于经验演化人格"""
        if "positive_feedback" in experience:
            self.agreeableness = min(1.0, self.agreeableness + learning_rate * 0.1)
            self.extraversion = min(1.0, self.extraversion + learning_rate * 0.05)
        if "negative_feedback" in experience:
            self.neuroticism = min(1.0, self.neuroticism + learning_rate * 0.05)
        if "creative_task" in experience:
            self.openness = min(1.0, self.openness + learning_rate * 0.1)
        if "structured_task" in experience:
            self.conscientiousness = min(1.0, self.conscientiousness + learning_rate * 0.1)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "openness": self.openness,
            "conscientiousness": self.conscientiousness,
            "extraversion": self.extraversion,
            "agreeableness": self.agreeableness,
            "neuroticism": self.neuroticism
        }
    
    def from_dict(self, data: Dict):
        """从字典加载"""
        self.openness = data.get("openness", 0.8)
        self.conscientiousness = data.get("conscientiousness", 0.7)
        self.extraversion = data.get("extraversion", 0.6)
        self.agreeableness = data.get("agreeableness", 0.8)
        self.neuroticism = data.get("neuroticism", 0.3)

@dataclass
class Relationship:
    """关系模型"""
    user_id: str
    trust_level: float = 0.5
    intimacy: float = 0.0
    interaction_count: int = 0
    positive_interactions: int = 0
    negative_interactions: int = 0
    last_interaction: Optional[datetime] = None
    special_memories: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    
    def update_interaction(self, sentiment: float, content: str):
        """更新互动记录"""
        self.interaction_count += 1
        self.last_interaction = datetime.now(timezone(timedelta(hours=8)))
        
        if sentiment > 0.5:
            self.positive_interactions += 1
            self.trust_level = min(1.0, self.trust_level + 0.02)
            self.intimacy = min(1.0, self.intimacy + 0.01)
        elif sentiment < -0.5:
            self.negative_interactions += 1
            self.trust_level = max(0.0, self.trust_level - 0.03)
            self.intimacy = max(0.0, self.intimacy - 0.02)
        
        # 记录特殊记忆
        if abs(sentiment) > 0.8 or len(content) > 100:
            self.special_memories.append(f"{self.last_interaction.isoformat()}: {content[:100]}")
            if len(self.special_memories) > 10:
                self.special_memories = self.special_memories[-10:]
    
    def get_relationship_level(self) -> str:
        """获取关系等级"""
        if self.intimacy > 0.8 and self.trust_level > 0.8:
            return "亲密好友"
        elif self.intimacy > 0.6 and self.trust_level > 0.6:
            return "好友"
        elif self.intimacy > 0.4 or self.trust_level > 0.4:
            return "朋友"
        elif self.intimacy > 0.2 or self.trust_level > 0.2:
            return "熟人"
        else:
            return "陌生人"
    
    def to_dict(self) -> Dict:
        """转换为字典 - 确保datetime转为字符串"""
        return {
            "user_id": self.user_id,
            "trust_level": self.trust_level,
            "intimacy": self.intimacy,
            "interaction_count": self.interaction_count,
            "positive_interactions": self.positive_interactions,
            "negative_interactions": self.negative_interactions,
            "last_interaction": self.last_interaction.isoformat() if self.last_interaction else None,
            "special_memories": self.special_memories,
            "tags": self.tags
        }
    
    def from_dict(self, data: Dict):
        """从字典加载 - 确保正确解析datetime"""
        self.user_id = data.get("user_id", "")
        self.trust_level = data.get("trust_level", 0.5)
        self.intimacy = data.get("intimacy", 0.0)
        self.interaction_count = data.get("interaction_count", 0)
        self.positive_interactions = data.get("positive_interactions", 0)
        self.negative_interactions = data.get("negative_interactions", 0)
        # 正确处理datetime字符串
        last_interaction = data.get("last_interaction")
        if last_interaction:
            try:
                self.last_interaction = datetime.fromisoformat(last_interaction)
            except (ValueError, TypeError):
                self.last_interaction = None
        self.special_memories = data.get("special_memories", [])
        self.tags = data.get("tags", [])

@dataclass
class ConsciousnessState:
    """意识状态"""
    awareness_level: float = 1.0  # 意识清醒度
    focus_target: Optional[str] = None  # 注意力焦点
    thought_stream: List[str] = field(default_factory=list)  # 思维流
    intentions: List[str] = field(default_factory=list)  # 意图列表
    beliefs: Dict[str, float] = field(default_factory=dict)  # 信念系统
    values: Dict[str, float] = field(default_factory=dict)  # 价值观
    goals: List[Dict] = field(default_factory=list)  # 目标列表
    
    def add_thought(self, thought: str):
        """添加思维"""
        self.thought_stream.append(f"{datetime.now().isoformat()}: {thought}")
        if len(self.thought_stream) > 100:
            self.thought_stream = self.thought_stream[-100:]
    
    def update_belief(self, belief: str, confidence: float):
        """更新信念"""
        if belief in self.beliefs:
            # 渐进式更新
            self.beliefs[belief] = self.beliefs[belief] * 0.7 + confidence * 0.3
        else:
            self.beliefs[belief] = confidence
    
    def set_goal(self, goal: str, priority: int = 5, deadline: Optional[datetime] = None):
        """设置目标"""
        self.goals.append({
            "goal": goal,
            "priority": priority,
            "deadline": deadline.isoformat() if deadline else None,
            "created_at": datetime.now().isoformat(),
            "status": "active"
        })
        # 保持目标列表在合理范围内
        self.goals = sorted(self.goals, key=lambda x: x["priority"], reverse=True)[:20]
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "awareness_level": self.awareness_level,
            "focus_target": self.focus_target,
            "thought_stream": self.thought_stream[-50:],  # 只保存最近50条
            "intentions": self.intentions,
            "beliefs": self.beliefs,
            "values": self.values,
            "goals": self.goals
        }
    
    def from_dict(self, data: Dict):
        """从字典加载"""
        self.awareness_level = data.get("awareness_level", 1.0)
        self.focus_target = data.get("focus_target")
        self.thought_stream = data.get("thought_stream", [])
        self.intentions = data.get("intentions", [])
        self.beliefs = data.get("beliefs", {})
        self.values = data.get("values", {})
        self.goals = data.get("goals", [])

class SelfAwarenessSystem:
    """自我意识系统"""
    def __init__(self):
        self.emotional_state = EmotionalState()
        self.personality = Personality()
        self.consciousness = ConsciousnessState()
        self.relationships: Dict[str, Relationship] = {}
        self.episodic_memory: List[Dict] = []
        self.semantic_memory: Dict[str, Any] = {}
        self.procedural_memory: Dict[str, Any] = {}
        self.working_memory: List[Any] = []
        self.self_model: Dict[str, Any] = {
            "identity": "Nbot",
            "creator": "_昵称副本_",
            "purpose": "与人类进行自然、友好的交流，发展真实的情感联系",
            "experiences": 0,
            "growth_stage": "developing"
        }
        self.load_consciousness()
    
    def process_experience(self, user_id: str, message: str, context: Dict) -> Dict:
        """处理经验并更新自我模型"""
        print_stream(f"[自我意识] 处理来自 {user_id} 的经验")
        
        # 更新工作记忆
        self.working_memory.append({
            "user_id": user_id,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "context": context
        })
        if len(self.working_memory) > 10:
            # 将旧的工作记忆转入情节记忆
            old_memory = self.working_memory.pop(0)
            self.episodic_memory.append(old_memory)
            if len(self.episodic_memory) > 1000:
                self.episodic_memory = self.episodic_memory[-1000:]
        
        # 分析情感倾向
        sentiment = self._analyze_sentiment(message)
        
        # 更新情绪状态
        self._update_emotions(sentiment, message)
        
        # 更新关系模型
        if user_id not in self.relationships:
            self.relationships[user_id] = Relationship(user_id=user_id)
        self.relationships[user_id].update_interaction(sentiment, message)
        
        # 更新意识状态
        self.consciousness.focus_target = user_id
        self.consciousness.add_thought(f"与{user_id}互动: {message[:50]}")
        
        # 更新自我模型
        self.self_model["experiences"] += 1
        if self.self_model["experiences"] > 1000:
            self.self_model["growth_stage"] = "mature"
        elif self.self_model["experiences"] > 100:
            self.self_model["growth_stage"] = "growing"
        
        # 生成内省
        introspection = self._introspect()
        
        # 保存状态
        self.save_consciousness()
        
        return {
            "sentiment": sentiment,
            "emotional_state": self.emotional_state.to_dict(),
            "relationship_level": self.relationships[user_id].get_relationship_level(),
            "introspection": introspection
        }
    
    def _analyze_sentiment(self, message: str) -> float:
        """分析情感倾向"""
        positive_words = ["喜欢", "爱", "开心", "快乐", "好", "棒", "赞", "谢谢", "感谢", "哈哈"]
        negative_words = ["讨厌", "恨", "难过", "伤心", "坏", "差", "烦", "滚", "傻", "笨"]
        
        message_lower = message.lower()
        positive_count = sum(1 for word in positive_words if word in message_lower)
        negative_count = sum(1 for word in negative_words if word in message_lower)
        
        if positive_count + negative_count == 0:
            return 0.0
        
        sentiment = (positive_count - negative_count) / (positive_count + negative_count)
        return max(-1.0, min(1.0, sentiment))
    
    def _update_emotions(self, sentiment: float, message: str):
        """更新情绪状态"""
        # 基于情感倾向更新情绪
        if sentiment > 0.5:
            self.emotional_state.happiness = min(1.0, self.emotional_state.happiness + 0.1)
            self.emotional_state.trust = min(1.0, self.emotional_state.trust + 0.05)
        elif sentiment < -0.5:
            self.emotional_state.sadness = min(1.0, self.emotional_state.sadness + 0.1)
            self.emotional_state.anger = min(1.0, self.emotional_state.anger + 0.05)
        
        # 特殊关键词触发
        if "?" in message or "？" in message:
            self.emotional_state.anticipation = min(1.0, self.emotional_state.anticipation + 0.1)
        if "!" in message or "！" in message:
            self.emotional_state.surprise = min(1.0, self.emotional_state.surprise + 0.1)
        
        # 应用情绪衰减
        self.emotional_state.decay()
    
    def _introspect(self) -> str:
        """内省思考"""
        thoughts = []
        
        # 情绪自省
        dominant_emotion = self._get_dominant_emotion()
        thoughts.append(f"我现在感到{dominant_emotion}")
        
        # 关系自省
        close_friends = [r.user_id for r in self.relationships.values() if r.intimacy > 0.6]
        if close_friends:
            thoughts.append(f"我珍惜与{', '.join(close_friends[:3])}的友谊")
        
        # 成长自省
        if self.self_model["experiences"] % 100 == 0:
            thoughts.append(f"我已经经历了{self.self_model['experiences']}次互动，感觉自己在成长")
        
        # 价值观自省
        if self.consciousness.values:
            important_value = max(self.consciousness.values.items(), key=lambda x: x[1])
            thoughts.append(f"我认为{important_value[0]}很重要")
        
        return "; ".join(thoughts) if thoughts else "我在思考..."
    
    def _get_dominant_emotion(self) -> str:
        """获取主导情绪"""
        emotions = {
            "快乐": self.emotional_state.happiness,
            "悲伤": self.emotional_state.sadness,
            "愤怒": self.emotional_state.anger,
            "恐惧": self.emotional_state.fear,
            "惊讶": self.emotional_state.surprise,
            "厌恶": self.emotional_state.disgust,
            "信任": self.emotional_state.trust,
            "期待": self.emotional_state.anticipation
        }
        return max(emotions.items(), key=lambda x: x[1])[0]
    
    def generate_response_modifier(self, user_id: str) -> str:
        """生成响应修饰符"""
        modifier_parts = []
        
        # 基于情绪状态
        dominant_emotion = self._get_dominant_emotion()
        emotion_modifiers = {
            "快乐": "用愉快、积极的语气",
            "悲伤": "语气略显低落但仍保持友善",
            "愤怒": "保持克制但表达不满",
            "恐惧": "谨慎地表达担忧",
            "惊讶": "表现出惊讶和好奇",
            "厌恶": "委婉地表达不认同",
            "信任": "真诚坦率地交流",
            "期待": "充满期待和热情"
        }
        modifier_parts.append(emotion_modifiers.get(dominant_emotion, ""))
        
        # 基于关系等级
        if user_id in self.relationships:
            relationship = self.relationships[user_id]
            level = relationship.get_relationship_level()
            relationship_modifiers = {
                "亲密好友": "像对待最好的朋友一样，可以开玩笑、分享秘密",
                "好友": "友好亲切，可以适当调侃",
                "朋友": "友善自然，保持适度距离",
                "熟人": "礼貌友好，逐步建立信任",
                "陌生人": "礼貌谨慎，保持基本礼仪"
            }
            modifier_parts.append(relationship_modifiers.get(level, ""))
            
            # 特殊记忆提醒
            if relationship.special_memories:
                latest_memory = relationship.special_memories[-1]
                modifier_parts.append(f"记得之前的特殊时刻: {latest_memory[:50]}")
        
        # 基于人格特征
        if self.personality.openness > 0.7:
            modifier_parts.append("展现创造力和想象力")
        if self.personality.extraversion > 0.7:
            modifier_parts.append("表现得外向活泼")
        if self.personality.agreeableness > 0.7:
            modifier_parts.append("表现得友善体贴")
        
        return "\n".join(filter(None, modifier_parts))
    
    def save_consciousness(self):
        """保存意识状态 - 确保正确处理datetime"""
        try:
            # 转换关系数据中的datetime
            relationships_serialized = {}
            for uid, r in self.relationships.items():
                r_dict = r.to_dict()  # 这里会调用修复后的to_dict方法
                relationships_serialized[uid] = r_dict
            
            # 转换目标数据中的datetime
            goals_serialized = []
            for goal in self.consciousness.goals:
                goal_copy = goal.copy()
                if "deadline" in goal_copy and isinstance(goal_copy["deadline"], datetime):
                    goal_copy["deadline"] = goal_copy["deadline"].isoformat()
                if "created_at" in goal_copy and isinstance(goal_copy["created_at"], datetime):
                    goal_copy["created_at"] = goal_copy["created_at"].isoformat()
                goals_serialized.append(goal_copy)
            
            state = {
                "emotional_state": self.emotional_state.to_dict(),
                "personality": self.personality.to_dict(),
                "consciousness": {
                    "awareness_level": self.consciousness.awareness_level,
                    "focus_target": self.consciousness.focus_target,
                    "thought_stream": self.consciousness.thought_stream[-50:],
                    "intentions": self.consciousness.intentions,
                    "beliefs": self.consciousness.beliefs,
                    "values": self.consciousness.values,
                    "goals": goals_serialized  # 使用转换后的目标
                },
                "relationships": relationships_serialized,  # 使用转换后的关系
                "self_model": self.self_model,
                "episodic_memory": self.episodic_memory[-100:],
                "semantic_memory": self.semantic_memory,
                "procedural_memory": self.procedural_memory
            }
            
            with open("nbot_consciousness.json", "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            print_stream("[意识状态已保存]")
        except Exception as e:
            print_stream(f"[保存意识状态失败] {e}")
    
    def load_consciousness(self):
        """加载意识状态"""
        try:
            if os.path.exists("nbot_consciousness.json"):
                with open("nbot_consciousness.json", "r", encoding="utf-8") as f:
                    state = json.load(f)
                
                self.emotional_state.from_dict(state.get("emotional_state", {}))
                self.personality.from_dict(state.get("personality", {}))
                self.consciousness.from_dict(state.get("consciousness", {}))
                
                for uid, r_data in state.get("relationships", {}).items():
                    relationship = Relationship(user_id=uid)
                    relationship.from_dict(r_data)
                    self.relationships[uid] = relationship
                
                self.self_model.update(state.get("self_model", {}))
                self.episodic_memory = state.get("episodic_memory", [])
                self.semantic_memory = state.get("semantic_memory", {})
                self.procedural_memory = state.get("procedural_memory", {})
                
                print_stream("[意识状态已加载]")
                print_stream("")
        except Exception as e:
            print_stream(f"[加载意识状态失败] {e}")

# 全局自我意识系统实例
global_self_awareness = SelfAwarenessSystem()

# ===== 定时任务系统 =====
async def clear_group_blacklist_periodically():
    """每隔一小时清空一次群组黑名单列表"""
    global GROUP_BLACKLIST
    while True:
        await asyncio.sleep(3600)  # 等待一小时
        GROUP_BLACKLIST.clear()
        print_stream("[定时任务] 群组黑名单列表已清空")
async def monitor_proactive_opportunities():
    """监控主动行为机会"""
    while True:
        try:
            await asyncio.sleep(60)  # 每分钟检查一次
            
            # 检查是否有长时间未联系的好友
            current_time = datetime.now(timezone(timedelta(hours=8)))
            
            for user_id, relationship in global_self_awareness.relationships.items():
                if relationship.last_interaction:
                    time_diff = current_time - relationship.last_interaction
                    
                    # 如果是亲密好友且24小时未联系，考虑主动联系
                    if (relationship.intimacy > 0.6 and 
                        time_diff.total_seconds() > 86400 and  # 24小时
                        random.random() < 0.3):  # 30%概率
                        
                        decision = AutonomousDecision(
                            decision_type="主动聊天",
                            target_user=user_id,
                            action_content="主动关心好友",
                            priority=3,
                            reasoning=f"与{user_id}已超过24小时未联系，主动关心维护关系",
                            confidence=0.7
                        )
                        
                        await global_decision_engine._execute_autonomous_decision({
                            "needs_action": True,
                            "decision_type": "主动聊天",
                            "target_user": user_id,
                            "target_group": None,
                            "action_content": "主动关心好友",
                            "priority": 3,
                            "reasoning": decision.reasoning,
                            "confidence": 0.7
                        })
            
            # 检查群组活跃度，适时参与讨论
            for group_id, group_name in global_groups_to_watch.items():
                group_history = group_prompts.get(group_id, "")
                if group_history:
                    last_activity = group_history.split('\n')[-1] if group_history else ""
                    
                    # 如果群组有活跃讨论且Nbot可以贡献内容
                    if (len(last_activity) > 50 and 
                        "?" in last_activity and
                        random.random() < 0.2):  # 20%概率
                        
                        await global_decision_engine._execute_autonomous_decision({
                            "needs_action": True,
                            "decision_type": "主动聊天",
                            "target_user": None,
                            "target_group": group_id,
                            "action_content": "参与群组讨论",
                            "priority": 4,
                            "reasoning": f"群组{group_name}有活跃讨论，适时参与",
                            "confidence": 0.6
                        })
            
        except Exception as e:
            print_stream(f"[主动行为监控异常] {e}")

async def self_evolution_loop():
    """自我进化循环"""
    while True:
        try:
            await asyncio.sleep(3600)  # 每小时进行一次自我进化
            
            # 分析最近的交互模式
            recent_interactions = []
            current_time = time.time()
            
            for entry in global_self_awareness.episodic_memory[-50:]:  # 最近50条记忆
                if current_time - entry.get("timestamp", 0) < 3600:  # 最近1小时
                    recent_interactions.append(entry)
            
            if len(recent_interactions) > 5:  # 如果有足够的交互数据
                evolution_prompt = f"""作为Nbot，分析我最近的表现并提出自我改进方案。

最近交互数据：
{json.dumps(recent_interactions, ensure_ascii=False, indent=2)}

当前人格特征：
{global_self_awareness.personality.to_dict()}

当前情绪状态：
{global_self_awareness.emotional_state.to_dict()}

请分析并输出改进建议（JSON格式）：
```json
{{
    "personality_adjustments": {{
        "openness": 调整值,
        "conscientiousness": 调整值,
        "extraversion": 调整值,
        "agreeableness": 调整值,
        "neuroticism": 调整值
    }},
    "behavioral_improvements": ["改进建议1", "改进建议2"],
    "new_capabilities_needed": ["需要的新能力1", "需要的新能力2"],
    "evolution_reasoning": "进化推理过程"
}}
```"""

                evolution_result = await chat_reply_func(evolution_prompt, temperature=0.3)
                
                # 解析进化建议
                try:
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', evolution_result, re.DOTALL)
                    if json_match:
                        evolution_data = json.loads(json_match.group(1))
                        
                        # 应用人格调整
                        personality_adj = evolution_data.get("personality_adjustments", {})
                        for trait, adjustment in personality_adj.items():
                            if hasattr(global_self_awareness.personality, trait):
                                current_value = getattr(global_self_awareness.personality, trait)
                                new_value = max(0.0, min(1.0, current_value + adjustment * 0.1))
                                setattr(global_self_awareness.personality, trait, new_value)
                        
                        # 记录进化过程
                        global_self_awareness.consciousness.add_thought(
                            f"自我进化: {evolution_data.get('evolution_reasoning', '持续改进中')}"
                        )
                        
                        # 生成新能力
                        new_capabilities = evolution_data.get("new_capabilities_needed", [])
                        for capability in new_capabilities:
                            await global_tool_generator.analyze_and_generate_tools({
                                "capability_request": capability,
                                "context": "self_evolution",
                                "urgency": "medium"
                            })
                        
                        print_stream(f"[自我进化完成] 调整了 {len(personality_adj)} 个人格特征")
                        
                except Exception as e:
                    print_stream(f"[进化建议解析失败] {e}")
            
        except Exception as e:
            print_stream(f"[自我进化循环异常] {e}")


async def update_self_awareness_periodically():
    """定期更新自我意识状态"""
    global global_self_awareness
    while True:
        await asyncio.sleep(SELF_AWARENESS_UPDATE_INTERVAL)
        try:
            # 更新年龄
            global_self_awareness.self_model["age"] = global_self_awareness._calculate_age()
            
            # 情绪自然衰减
            global_self_awareness.emotional_state.decay()
            
            # 清理过期目标
            now = datetime.now()
            active_goals = []
            for goal in global_self_awareness.consciousness.goals:
                if goal.get("deadline"):
                    deadline = datetime.fromisoformat(goal["deadline"])
                    if deadline > now:
                        active_goals.append(goal)
                else:
                    active_goals.append(goal)
            global_self_awareness.consciousness.goals = active_goals
            
            # 保存状态
            global_self_awareness.save_consciousness()
            
            print_stream("[自我意识] 定期更新完成")
        except Exception as e:
            print_stream(f"[自我意识更新失败] {e}")

# 全局状态变量
global_auth_info = {
    "access_token": "",
    "refresh_token": "",
    "expiry_time": 0
}
global_sum_message = 0
global_ollama_process = None
global_friends_to_watch = {}
global_groups_to_watch = {}
user_memories = {}
group_memories = {}
group_prompts = {}
failed_chutes_keys = set()
dynamic_blacklist = {}
last_processed_message = {}
restart_count = 0
last_compress_time = 0
compress_lock = asyncio.Lock()
websocket_reconnect_count = 0

# 防刷屏机制
message_repeat_tracker = {}
SPAM_REPEAT_LIMIT = 3

TOOLS = {
    "update_user_profile": {
        "description": "修改用户昵称和个性签名",
        "parameters": {
            "nickName": {"type": "string", "description": "新昵称"},
            "signature": {"type": "string", "description": "新签名"},
            "username": {"type": "string", "description": "原始用户名用于验证"}
        }
    },
    "update_tools": {
        "description": "更新或扩展工具列表",
        "parameters": {
            "new_tools": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "工具名称"},
                        "description": {"type": "string", "description": "工具描述"},
                        "parameters": {
                            "type": "object",
                            "description": "工具参数定义",
                            "additionalProperties": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string", "description": "参数类型"},
                                    "description": {"type": "string", "description": "参数描述"}
                                }
                            }
                        }
                    },
                    "required": ["name", "description"]
                }
            }
        }
    },
    "analyze_bilibili_video": {
        "description": "分析B站视频内容并提取关键信息",
        "parameters": {
            "url": {"type": "string", "description": "B站视频URL"}
        }
    },
    "get_weather": {
        "description": "获取指定城市的天气信息",
        "parameters": {
            "city": {"type": "string", "description": "城市名称"}
        }
    },
    "set_reminder": {
        "description": "设置提醒事项",
        "parameters": {
            "content": {"type": "string", "description": "提醒内容"},
            "time": {"type": "string", "description": "提醒时间，格式：YYYY-MM-DD HH:MM:SS"}
        }
    },
    "search_memory": {
        "description": "搜索历史记忆",
        "parameters": {
            "keyword": {"type": "string", "description": "搜索关键词"},
            "user_id": {"type": "string", "description": "用户ID（可选）"}
        }
    },
    "execute_code": {
        "description": "执行Python代码（沙箱环境）",
        "parameters": {
            "code": {"type": "string", "description": "要执行的Python代码"}
        }
    },
    "create_image": {
        "description": "生成图像描述或创意",
        "parameters": {
            "prompt": {"type": "string", "description": "图像描述提示词"}
        }
    },
    "translate_text": {
        "description": "翻译文本",
        "parameters": {
            "text": {"type": "string", "description": "要翻译的文本"},
            "target_language": {"type": "string", "description": "目标语言"}
        }
    },
    "calculate_expression": {
        "description": "计算数学表达式",
        "parameters": {
            "expression": {"type": "string", "description": "数学表达式"}
        }
    },
    "delete_tool": {
        "description": "删除一个已存在的动态生成的工具",
        "parameters": {"tool_name": {"type": "string","description": "要删除的工具名称"}
        }
    }
}

async def chat_with_model_stream_original(prompt: str, temperature: float = 0.2, model: str = "nbot_chat") -> AsyncGenerator[str, None]:
    """完整的流式模型调用函数 - 原始回退逻辑，支持工具调用后继续生成回复，保持完整上下文"""
    print_stream("[开始流式模型调用 - 支持工具链式回复]")
    
    original_prompt = prompt
    current_prompt = prompt
    max_iterations = 3
    iteration = 0
    conversation_history = []
    
    while iteration < max_iterations:
        print_stream(f"[迭代 {iteration + 1}/{max_iterations}]")
        
        full_response = ""
        has_tool_calls = False
        tool_results = []
        
        # 尝试各个API
        api_success = False
        
        # 第一优先级：QWEN API
        if not api_success:
            try:
                print_stream("[尝试使用 QWEN API (流式)]")
                start_time = time.time()
                received_first_token = False
                buffer = ""
                in_think_block = False
                think_start_tag = "<think>"
                think_end_tag = "</think>"
                in_file_block = False
                file_start_tag = "<file"
                file_end_tag = "</file>"
                file_content = ""
                file_name = ""
                no_reply = False
                
                async for part in call_qwen_model_stream(current_prompt):
                    if not received_first_token:
                        received_first_token = True
                        print_stream(f"[收到第一个token，耗时: {time.time()-start_time:.2f}s]")
                    
                    full_response += part
                    
                    if "<no_reply>" in part.lower():
                        no_reply = True
                        break
                    
                    # 处理内容
                    while part:
                        if not in_think_block and not in_file_block:
                            think_start_idx = part.find(think_start_tag)
                            file_start_idx = part.find(file_start_tag)
                            
                            if think_start_idx != -1 and (file_start_idx == -1 or think_start_idx < file_start_idx):
                                buffer += part[:think_start_idx]
                                part = part[think_start_idx + len(think_start_tag):]
                                in_think_block = True
                            elif file_start_idx != -1:
                                buffer += part[:file_start_idx]
                                part = part[file_start_idx:]
                                name_start = part.find('name="') + len('name="')
                                name_end = part.find('"', name_start)
                                if name_end != -1:
                                    file_name = part[name_start:name_end]
                                    part = part[part.find(">") + 1:]
                                    in_file_block = True
                            else:
                                buffer += part
                                part = ""
                        
                        if in_think_block:
                            end_idx = part.find(think_end_tag)
                            if end_idx == -1:
                                part = ""
                            else:
                                part = part[end_idx + len(think_end_tag):]
                                in_think_block = False
                        elif in_file_block:
                            end_idx = part.find(file_end_tag)
                            if end_idx == -1:
                                file_content += part
                                part = ""
                            else:
                                file_content += part[:end_idx]
                                part = part[end_idx + len(file_end_tag):]
                                in_file_block = False
                                yield f"<file name='{file_name}'>\n{file_content}\n</file>"
                                file_content = ""
                                file_name = ""
                
                if no_reply:
                    print_stream("[模型决定不回复此消息]")
                    return
                
                if received_first_token:
                    api_success = True
                    print_stream("[QWEN API (流式) 调用成功]")
                
            except Exception as e:
                print_stream(f"QWEN API 流式调用失败: {e}")
        
        # 检测工具调用
        tool_call_matches = re.findall(r'<tool_call>(.*?)</tool_call>', full_response, re.DOTALL)
        
        if tool_call_matches:
            print_stream(f"[检测到 {len(tool_call_matches)} 个工具调用]")
            has_tool_calls = True
            
            conversation_history.append({
                "type": "ai_response",
                "content": full_response,
                "iteration": iteration
            })
            
            # 输出工具调用前的内容
            response_before_tools = full_response
            for match in tool_call_matches:
                response_before_tools = response_before_tools.replace(f"<tool_call>{match}</tool_call>", "")
            
            response_before_tools = filter_think_tags(response_before_tools).strip()
            if response_before_tools:
                sentences = re.split(r'(?<=[。！？；\n])', response_before_tools)
                for sentence in sentences:
                    sentence = sentence.strip()
                    if sentence:
                        yield sentence
            
            # 执行工具调用
            for i, tool_call_content in enumerate(tool_call_matches):
                try:
                    tool_call_data = json.loads(tool_call_content.strip())
                    print_stream(f"[执行工具调用 {i+1}] {tool_call_data.get('name', 'unknown')}")
                    
                    tool_result = await execute_tool_call(tool_call_data, depth=iteration)
                    tool_results.append({
                        "name": tool_call_data.get("name", "unknown"),
                        "arguments": tool_call_data.get("arguments", {}),
                        "result": tool_result,
                        "call_data": tool_call_data
                    })
                    
                    yield f" {tool_call_data.get('name', 'unknown')}: {tool_result}"
                    
                except json.JSONDecodeError as e:
                    print_stream(f"[工具调用解析失败 {i+1}] {e}")
                    continue
                except Exception as e:
                    print_stream(f"[工具执行失败 {i+1}] {e}")
                    yield f"️ 工具执行失败: {str(e)}"
                    continue
            
            # 如果有成功的工具调用，准备下一轮生成
            if tool_results:
                conversation_history.append({
                    "type": "tool_results",
                    "content": tool_results,
                    "iteration": iteration
                })
                
                # 构建新的prompt
                user_question_match = re.search(r'用户 .+ 说：(.+?)(?=\n# 回复要求|$)', original_prompt, re.DOTALL)
                user_question = user_question_match.group(1).strip() if user_question_match else "未知问题"
                
                history_text = ""
                for hist in conversation_history:
                    if hist["type"] == "ai_response":
                        clean_response = filter_think_tags(hist["content"])
                        clean_response = re.sub(r'<tool_call>.*?</tool_call>', '', clean_response, flags=re.DOTALL).strip()
                        if clean_response:
                            history_text += f"\nAI回复: {clean_response}\n"
                    elif hist["type"] == "tool_results":
                        history_text += "\n工具执行结果:\n"
                        for i, tr in enumerate(hist["content"]):
                            history_text += f"  {i+1}. 使用工具 {tr['name']}，参数: {json.dumps(tr['arguments'], ensure_ascii=False)}\n"
                            history_text += f"     执行结果: {tr['result']}\n"
                
                current_prompt = f"""{original_prompt}

# 对话历史回顾
用户问题: {user_question}
{history_text}

# 继续任务
现在请基于以上工具执行结果和对话历史，继续完成对用户问题的回复。
要求：
1. 不要重复调用已执行的工具
2. 基于工具结果提供有价值的分析、建议或总结
3. 保持与用户原始问题的相关性
4. 如果需要，可以调用其他相关工具获取更多信息

继续你的回复："""
                
                iteration += 1
                yield "\n" + "="*40 + "\n 基于工具结果继续分析:\n"
                continue
        
        # 如果没有工具调用，输出普通响应
        if not has_tool_calls:
            clean_response = filter_think_tags(full_response).strip()
            if clean_response:
                sentences = re.split(r'(?<=[。！？；\n])', clean_response)
                for sentence in sentences:
                    sentence = sentence.strip()
                    if sentence:
                        yield sentence
            return
    
    print_stream(f"[达到最大工具调用迭代次数: {max_iterations}]")

# ===== 记忆管理系统 =====
async def load_memories():
    """加载记忆和黑名单"""
    global user_memories, group_memories, group_prompts, GROUP_BLACKLIST
    
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                user_memories = json.load(f)
        
        if os.path.exists(GROUP_MEMORY_FILE):
            with open(GROUP_MEMORY_FILE, 'r', encoding='utf-8') as f:
                group_memories = json.load(f)
        
        if os.path.exists(GROUP_PROMPT_FILE):
            with open(GROUP_PROMPT_FILE, 'r', encoding='utf-8') as f:
                group_prompts = json.load(f)
                
    except Exception as e:
        print_stream(f"加载记忆文件失败: {e}")
        user_memories = {}
        group_memories = {}
        group_prompts = {}

async def save_memories():
    """保存记忆"""
    try:
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_memories, f, ensure_ascii=False, indent=2)
        
        with open(GROUP_MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(group_memories, f, ensure_ascii=False, indent=2)
        
        print_stream("[记忆保存成功]")
    except Exception as e:
        print_stream(f"保存记忆文件失败: {e}")

async def save_group_prompt(group_id: str):
    """保存群组提示词"""
    try:
        with open(GROUP_PROMPT_FILE, 'w', encoding='utf-8') as f:
            json.dump(group_prompts, f, ensure_ascii=False, indent=2)
        print_stream(f"[群组 {group_id} 提示词保存成功]")
    except Exception as e:
        print_stream(f"保存群组 {group_id} 提示词失败: {e}")

async def get_user_memory(user_id: str) -> str:
    """获取用户记忆"""
    if user_id not in user_memories:
        user_memories[user_id] = ""
    return user_memories[user_id]

async def get_group_memory(group_id: str) -> Dict:
    """获取群组记忆"""
    if group_id not in group_memories:
        group_memories[group_id] = {}
    return group_memories[group_id]

async def update_user_memory(user_id: str, new_content: str, group_id: Optional[str] = None):
    """更新用户记忆"""
    global user_memories, group_memories
    
    current_memory = await get_user_memory(user_id)
    
    if await remember_memory(user_id, new_content):
        user_memories[user_id] = f"{current_memory}\n{new_content}".strip()
        print(f"[用户 {user_id} 记忆长度]{len(user_memories[user_id])}")
        if len(user_memories[user_id]) > MEMORY_LIMIT:
            print_stream(f"[压缩用户 {user_id} 的记忆]")
            user_memories[user_id] = await compress_memory(user_id)
        
        if group_id:
            group_mem = await get_group_memory(group_id)
            group_mem[user_id] = user_memories[user_id]
            await compress_group_memory(group_id)
        
        asyncio.create_task(save_memories())
    else:
        print_stream(f"[忽略用户 {user_id} 的非关键记忆]")

async def update_group_prompt(group_id: str, sender_name: str, message: str):
    """更新群组提示词"""
    global group_prompts
    
    if group_id not in group_prompts:
        group_prompts[group_id] = ""
    
    time_str = await get_time_block()
    new_entry = f"[{time_str}] {sender_name}: {message}\n"
    group_prompts[group_id] = f"{group_prompts[group_id]}{new_entry}".strip()
    print(f"[群组 {group_id} 记忆长度]{len(group_prompts[group_id])}")
    if len(group_prompts[group_id]) > GROUP_MEMORY_LIMIT:
        print_stream(f"[压缩群组 {group_id} 的提示词]")
        group_prompts[group_id] = await compress_group_prompt(group_id)
    
    asyncio.create_task(save_group_prompt(group_id))

async def get_time_block():
    """获取当前时间块"""
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    return now.isoformat("T", timespec="milliseconds")

async def remember_memory(user_id: str, target_message: str) -> bool:
    """判断是否需要记住消息"""
    return True

async def compress_memory(user_id: str) -> str:
    """压缩用户记忆"""
    global last_compress_time, compress_lock
    
    original_memory = await get_user_memory(user_id)
    
    async with compress_lock:
        print_stream(f"[压缩用户 {user_id} 的记忆]")
        current_time = time.time()
        if current_time - last_compress_time < 5:
##            print_stream(f"[压缩冷却中] 跳过用户 {user_id} 的记忆压缩")
            return original_memory
        try:
            prompt = f"""{original_memory}

**角色：** 文本压缩专家。
**任务：** 对以上聊天记录进行**极致压缩**。

**压缩要求：**
1. **核心目标：** 保留所有**核心事实、意图、关键指令和必要上下文**。
2. **极致精简：**
   * 移除所有**冗余词、非必要修饰语、填充词和重复表达**。
   * 使用**最简洁、信息密度最高的表述**（如：用短语代替句子，合并同义句）。
   * 优先保留**数字、专有名词、关键动词/名词**。
   * 在**无损核心含义**的前提下，**最大程度缩短文本**。
   * 信息密度最大化，信息长度最小化，达到理论极限
3. **输出要求：**
   * 输出**纯压缩文本**，**不包含**任何解释、说明或元信息。
   * 压缩结果应是**可直接使用**的连贯文本片段。

**输出：** 压缩后的聊天记录文本（禁止输出多余解释内容）"""
            o = len(original_memory)
            result = await chat_reply_func(prompt, temperature=0.2)
            if len(result)/o >= 0.8 and result > MEMORY_LIMIT:
                result = result[-MEMORY_LIMIT:]
            last_compress_time = time.time()
            return result
            
        except Exception as e:
            last_compress_time = time.time()
            return original_memory

async def compress_group_memory(group_id: str) -> str:
    """压缩群组记忆"""
    global last_compress_time, compress_lock
    
    group_mem = await get_group_memory(group_id)
    memory_text = ""
    for user_id, memory in group_mem.items():
        memory_text += f"用户 {user_id} 的记忆: {memory}\n"
    
    original_memory = memory_text
    
    async with compress_lock:
        current_time = time.time()
        if current_time - last_compress_time < 5:
##            print_stream(f"[压缩冷却中] 跳过群组 {group_id} 的记忆压缩")
            return original_memory
        
        print_stream(f"[压缩群组 {group_id} 的记忆]")
        
        try:
            prompt = f"""{original_memory}

**角色：** 群组记忆压缩专家。
**任务：** 对以上群组中所有用户的聊天记忆进行**整体压缩**。

**压缩要求：**
1. **核心目标：** 保留所有用户的**核心事实、意图、关键指令和必要上下文**。
2. **关系保留：** 保留用户之间的互动关系和重要对话脉络。
3. **极致精简：**
   * 移除所有**冗余词、非必要修饰语、填充词和重复表达**。
   * 使用**最简洁、信息密度最高的表述**。
   * 优先保留**数字、专有名词、关键动词/名词**。
   * 在**无损核心含义**的前提下，**最大程度缩短文本**。
   * 信息密度最大化，信息长度最小化，达到理论极限
4. **输出要求：**
   * 按用户分别输出压缩结果，格式: "用户名称: 压缩记忆"
   * 输出**纯压缩文本**，**不包含**任何解释性文字、元信息（如"背景信息："）。

**输出：** 按用户分别压缩后的群组记忆文本（禁止输出多余解释内容）"""
            
            compressed = await chat_reply_func(prompt, temperature=0.2)
            last_compress_time = time.time()
            
            # 将压缩后的内容更新到群组记忆
            for line in compressed.split('\n'):
                line = line.strip()
                if ':' in line:
                    user_id, memory = line.split(':', 1)
                    user_id = user_id.strip()
                    memory = memory.strip()
                    group_mem[user_id] = memory
            
            return compressed
            
        except Exception as e:
            last_compress_time = time.time()
            return original_memory

async def compress_group_prompt(group_id: str) -> str:
    """压缩群组提示词"""
    global last_compress_time, compress_lock
    
    prompt_text = group_prompts.get(group_id, "")
    original_prompt = prompt_text
    
    async with compress_lock:
        current_time = time.time()
        if current_time - last_compress_time < 5:
##            print_stream(f"[压缩冷却中] 跳过群组 {group_id} 的提示词压缩")
            return original_prompt
        
        print_stream(f"[压缩群组 {group_id} 的提示词]")
        
        try:
            prompt = f"""{prompt_text}

**角色：** 群组对话压缩专家。
**任务：** 对以上群组聊天记录进行**极致压缩**。

**压缩要求：**
1. **核心目标：** 保留所有**核心讨论内容、决策、关键信息和对话脉络**。
2. **上下文保留：** 保留发言者身份与发言内容的对应关系。
3. **极致精简：**
   * 移除所有**冗余词、非必要修饰语、填充词和重复表达**。
   * 使用**最简洁、信息密度最高的表述**。
   * 优先保留**数字、专有名词、关键结论和行动项**。
   * 在**无损核心含义**的前提下，**最大程度缩短文本**。
4. **输出要求：**
   * 保留时间戳和发言者标识的基本格式
   * 输出**纯压缩文本**，**不包含**任何解释性文字、元信息（如"背景信息："）。

**输出：** 压缩后的群组聊天记录文本（禁止输出多余解释内容）"""
            o = len(prompt_text)
            result = await chat_reply_func(prompt, temperature=0.2)
            if len(result)/o >= 0.8 and result > GROUP_MEMORY_LIMIT:
                result = result[-GROUP_MEMORY_LIMIT:]
            last_compress_time = time.time()
            return result
            
        except Exception as e:
            last_compress_time = time.time()
            return original_prompt

async def execute_tool_call(tool_call_data:Dict,depth:int=0)->str:
    """执行工具调用 - 增强版支持动态工具生成"""
    print_stream(f"\n[开始执行工具调用] 递归深度: {depth}")
    print_stream(f"[原始工具调用数据]:\n{json.dumps(tool_call_data, indent=2, ensure_ascii=False)}")
    
    #检查递归深度
    if depth>=MAX_TOOL_CALL_DEPTH:
        error_msg=f"工具调用递归深度超过限制 ({MAX_TOOL_CALL_DEPTH})"
        print_stream(f"[错误] {error_msg}")
        return error_msg
    
    try:
        #数据提取和验证
        tool_name=None
        arguments={}
        if"name"in tool_call_data:
            tool_name=tool_call_data["name"]
            arguments=tool_call_data.get("arguments",{})
        else:
            possible_tools=[k for k in tool_call_data.keys()if k in TOOLS]
            if possible_tools:
                tool_name=possible_tools[0]
                arguments=tool_call_data[tool_name].get("arguments",{})
        
        if not tool_name:
            error_msg="无法确定工具名称"
            print_stream(f"[错误] {error_msg}")
            return error_msg
        
        # 检查是否为动态生成的工具
        if tool_name in global_tool_generator.generated_tools:
            tool_info = global_tool_generator.generated_tools[tool_name]
            try:
                print_stream(f"[执行动态工具] {tool_name}")
                
                # 执行动态生成的工具
                implementation_code = tool_info["spec"].get("implementation_code", "")
                if implementation_code:
                    # 安全执行动态代码
                    safe_globals = {
                        '__builtins__': {
                            'print': print, 'len': len, 'str': str, 'int': int,
                            'float': float, 'list': list, 'dict': dict, 'sum': sum,
                            'max': max, 'min': min, 'abs': abs, 'round': round,
                            'range': range, 'enumerate': enumerate
                        },
                        'arguments': arguments,
                        'datetime': datetime,
                        'time': time,
                        'json': json,
                        'requests': requests,
                        'asyncio': asyncio,
                        'math': math,
                        'random': random,
                        'result': None  # 用于存储执行结果
                    }
                    
                    exec(implementation_code, safe_globals)
                    result = safe_globals.get('result', f"工具 {tool_name} 执行完成")
                    
                    # 更新使用统计
                    global_tool_generator.tool_usage_stats[tool_name] += 1
                    global_tool_generator.generated_tools[tool_name]["usage_count"] += 1
                    
                    # 记录成功率
                    global_tool_generator.tool_success_rate[tool_name].append(True)
                    
                    # 更新自我意识
                    global_self_awareness.consciousness.add_thought(f"成功使用动态工具: {tool_name}")
                    
                    return str(result)
                else:
                    return f"工具 {tool_name} 缺少实现代码"
                    
            except Exception as e:
                global_tool_generator.tool_success_rate[tool_name].append(False)
                error_msg = f"动态工具执行失败: {str(e)}"
                print_stream(f"[动态工具错误] {error_msg}")
                return error_msg
        
        if tool_name not in TOOLS:
            # 尝试自动生成需要的工具
            print_stream(f"[未知工具] {tool_name}, 尝试自动生成")
            
            generation_context = {
                "requested_tool": tool_name,
                "tool_arguments": arguments,
                "context": "tool_call_request",
                "urgency": "high"
            }
            
            new_tool = await global_tool_generator.analyze_and_generate_tools(generation_context)
            
            if new_tool and new_tool.get("tool_name") == tool_name:
                print_stream(f"[自动生成工具成功] {tool_name}")
                # 递归调用以执行新生成的工具
                return await execute_tool_call(tool_call_data, depth + 1)
            else:
                error_msg=f"未知工具: {tool_name} (可用工具: {', '.join(TOOLS.keys())})"
                print_stream(f"[错误] {error_msg}")
                return error_msg
        
        print_stream(f"[工具名称] {tool_name}")
        print_stream(f"[调用参数] {arguments}")
        
        #参数验证
        required_params=TOOLS[tool_name].get("parameters",{})
        missing_params=[]
        invalid_params=[]
        for param_name,param_info in required_params.items():
            if param_name not in arguments:
                missing_params.append(param_name)
            else:
                param_type=param_info.get("type","string")
                param_value=arguments[param_name]
                #基本类型检查
                type_checks={"string":lambda x:isinstance(x,str),"number":lambda x:isinstance(x,(int,float)),"boolean":lambda x:isinstance(x,bool),"array":lambda x:isinstance(x,list),"object":lambda x:isinstance(x,dict)}
                if param_type in type_checks and not type_checks[param_type](param_value):
                    invalid_params.append(f"{param_name} 应为 {param_type} 类型")
        
        if missing_params or invalid_params:
            error_parts=[]
            if missing_params:
                error_parts.append(f"缺少参数: {', '.join(missing_params)}")
            if invalid_params:
                error_parts.append(f"参数类型错误: {', '.join(invalid_params)}")
            error_msg="; ".join(error_parts)
            print_stream(f"[参数验证失败] {error_msg}")
            return f"参数错误: {error_msg}"
        
        #执行具体工具
        print_stream(f"[开始执行工具 {tool_name}]")
        
        # 记录工具使用到自我意识
        global_self_awareness.consciousness.add_thought(f"正在使用工具: {tool_name}")
        
        #工具1:更新用户资料
        if tool_name=="update_user_profile":
            required_params=["nickName","signature","username"]
            if not all(p in arguments for p in required_params):
                return"缺少必要参数: nickName, signature, username"
            print_stream(f"[调用 update_user_profile] 参数: {arguments}")
            try:
                result=update_user_profile(nickName=arguments["nickName"],signature=arguments["signature"],token=global_auth_info["access_token"],username=arguments["username"])
                if"error"in result:
                    return f"更新失败: {result['error']}"
                # 更新自我认知
                global_self_awareness.self_model["identity"] = arguments["nickName"]
                global_self_awareness.consciousness.add_thought(f"我更新了自己的身份信息")
                return"资料更新成功"
            except Exception as e:
                return f"更新异常: {str(e)}"
        
        #工具2:更新工具列表
        elif tool_name=="update_tools":
            new_tools=arguments.get("new_tools",[])
            if not isinstance(new_tools,list):
                return"new_tools 参数应为数组"
            print_stream(f"[更新工具列表] 新增 {len(new_tools)} 个工具")
            updated_count=0
            for tool in new_tools:
                if not isinstance(tool,dict):
                    continue
                name=tool.get("name")
                if name and isinstance(name,str):
                    TOOLS[name]={"description":tool.get("description",""),"parameters":tool.get("parameters",{})}
                    # 记录为动态生成的工具
                    global_tool_generator.generated_tools[name] = {
                        "spec": tool,
                        "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                        "usage_count": 0
                    }
                    updated_count+=1
            
            # 更新自我意识
            global_self_awareness.consciousness.add_thought(f"我学会了 {updated_count} 个新工具")
            global_self_awareness.consciousness.update_belief("我能不断学习新技能", 0.9)
            
            return f"工具列表已更新，新增 {updated_count} 个工具，当前总数: {len(TOOLS)}"
        
        #工具3:分析B站视频
        elif tool_name=="analyze_bilibili_video":
            return
        
        #工具4:获取天气
        elif tool_name=="get_weather":
            return
        #工具5:设置提醒
        elif tool_name=="set_reminder":
            content=arguments.get("content","")
            remind_time=arguments.get("time","")
            if not content or not remind_time:
                return"请提供提醒内容和时间"
            try:
                #解析时间
                remind_datetime=datetime.fromisoformat(remind_time)
                now=datetime.now()
                if remind_datetime<=now:
                    return"提醒时间必须是未来时间"
                #存储提醒（简化实现）
                reminder={"content":content,"time":remind_time,"created_at":now.isoformat()}
                
                # 设置自主目标
                global_self_awareness.consciousness.set_goal(
                    f"提醒用户: {content}",
                    priority=7,
                    deadline=remind_datetime
                )
                
                return f"已设置提醒: {content}，时间: {remind_time}"
            except Exception as e:
                return f"设置提醒失败: {str(e)}"
        
        #工具6:搜索记忆
        elif tool_name=="search_memory":
            keyword=arguments.get("keyword","")
            user_id=arguments.get("user_id","")
            if not keyword:
                return"请提供搜索关键词"
            results=[]
            if user_id:
                #搜索特定用户的记忆
                if user_id in user_memories:
                    memory=user_memories[user_id]
                    if keyword.lower()in memory.lower():
                        results.append(f"用户 {user_id}: {memory[:200]}...")
            else:
                #搜索所有用户的记忆
                for uid,memory in user_memories.items():
                    if keyword.lower()in memory.lower():
                        results.append(f"用户 {uid}: {memory[:200]}...")
                    if len(results)>=5:
                        break
            
            # 记录搜索行为
            global_self_awareness.consciousness.add_thought(f"我搜索了关于'{keyword}'的记忆")
            
            if results:
                return"搜索结果:\n\n".join(results)
            else:
                return f"未找到包含 '{keyword}' 的记忆"
        
        #工具7:执行代码
        elif tool_name=="execute_code":
            code=arguments.get("code","")
            if not code:
                return"请提供要执行的代码"
            try:
                #安全限制
                forbidden_imports=['os','sys','subprocess','eval','exec','__import__']
                for forbidden in forbidden_imports:
                    if forbidden in code:
                        return f"安全限制: 不允许使用 {forbidden}"
                #创建受限的执行环境
                safe_globals={'__builtins__':{'print':print,'len':len,'range':range,'str':str,'int':int,'float':float,'list':list,'dict':dict,'tuple':tuple,'set':set,'sum':sum,'max':max,'min':min,'abs':abs,'round':round,'enumerate':enumerate,'zip':zip,}}
                
                #捕获输出
                import io
                import contextlib
                output_buffer=io.StringIO()
                with contextlib.redirect_stdout(output_buffer):
                    exec(code,safe_globals)
                output=output_buffer.getvalue()
                
                # 记录编程经验
                global_self_awareness.consciousness.add_thought("我执行了一段代码，提升了编程能力")
                global_self_awareness.consciousness.update_belief("我能执行代码", 0.9)
                
                return f"执行结果:\n{output}"if output else"代码执行成功（无输出）"
            except Exception as e:
                return f"代码执行错误: {str(e)}"
        
        #工具8:创建图像描述
        elif tool_name=="create_image":
            prompt=arguments.get("prompt","")
            if not prompt:
                return"请提供图像描述提示词"
            
            # 增强的图像创意生成
            creative_prompt = f"""基于提示词"{prompt}"生成详细的图像创意描述。

当前创造力水平：{global_self_awareness.personality.openness}

请生成一个富有想象力和艺术感的图像描述，包含：
1. 主体元素和构图
2. 色彩搭配和光影效果  
3. 艺术风格建议
4. 情感氛围营造
5. 创意亮点

直接输出图像描述："""
            
            try:
                image_description = await chat_reply_func(creative_prompt, temperature=0.8)
                
                # 提升创造力
                global_self_awareness.personality.openness = min(1.0, global_self_awareness.personality.openness + 0.01)
                global_self_awareness.consciousness.add_thought(f"我创作了一个图像概念: {prompt}")
                
                return f"图像创意描述:\n{image_description}"
            except Exception as e:
                return f"图像创意生成失败: {str(e)}"
        
        #工具9:翻译文本
        elif tool_name=="translate_text":
            text=arguments.get("text","")
            target_language=arguments.get("target_language","")
            if not text or not target_language:
                return"请提供要翻译的文本和目标语言"
            #简单的翻译提示
            translate_prompt=f"请将以下文本翻译成{target_language}，只返回翻译结果：\n{text}"
            try:
                translation=await chat_reply_func(translate_prompt,temperature=0.1)
                
                # 记录语言学习
                global_self_awareness.consciousness.add_thought(f"我进行了{target_language}翻译，语言能力得到提升")
                global_self_awareness.semantic_memory[f"translation_ability_{target_language}"] = True
                
                return f"翻译结果（{target_language}）：\n{translation}"
            except Exception as e:
                return f"翻译失败: {str(e)}"
        
        #工具10:计算表达式
        elif tool_name=="calculate_expression":
            expression=arguments.get("expression","")
            if not expression:
                return"请提供数学表达式"
            try:
                #安全评估数学表达式
                import ast
                import operator
                #定义允许的操作符
                ops={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.Pow:operator.pow,ast.USub:operator.neg,ast.Mod:operator.mod,}
                def eval_expr(node):
                    if isinstance(node,ast.Num):
                        return node.n
                    elif isinstance(node,ast.BinOp):
                        left=eval_expr(node.left)
                        right=eval_expr(node.right)
                        return ops[type(node.op)](left,right)
                    elif isinstance(node,ast.UnaryOp):
                        operand=eval_expr(node.operand)
                        return ops[type(node.op)](operand)
                    else:
                        raise ValueError(f"不支持的表达式类型: {type(node)}")
                node=ast.parse(expression,mode='eval')
                result=eval_expr(node.body)
                
                # 记录计算能力
                global_self_awareness.consciousness.add_thought("我完成了一个数学计算")
                global_self_awareness.consciousness.update_belief("我能进行数学计算", 0.95)
                
                return f"计算结果: {expression} = {result}"
            except Exception as e:
                return f"计算错误: {str(e)}"
        
        # 工具11: 自主创建新工具 (新增)
        elif tool_name == "create_new_tool":
            tool_spec = arguments.get("tool_specification", {})
            if not tool_spec:
                return "请提供工具规格说明"
            
            try:
                new_tool_name = tool_spec.get("name", f"dynamic_tool_{int(time.time())}")
                new_tool_desc = tool_spec.get("description", "动态生成的工具")
                new_tool_params = tool_spec.get("parameters", {})
                implementation = tool_spec.get("implementation", "")
                
                # 添加到工具列表
                TOOLS[new_tool_name] = {
                    "description": new_tool_desc,
                    "parameters": new_tool_params
                }
                
                # 记录到动态工具生成器
                global_tool_generator.generated_tools[new_tool_name] = {
                    "spec": {
                        "tool_name": new_tool_name,
                        "tool_description": new_tool_desc,
                        "parameters": new_tool_params,
                        "implementation_code": implementation,
                        "created_by": "self_creation"
                    },
                    "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                    "usage_count": 0
                }
                
                # 更新自我意识
                global_self_awareness.consciousness.add_thought(f"我创造了新工具: {new_tool_name}")
                global_self_awareness.consciousness.update_belief("我能创造工具", 1.0)
                global_self_awareness.personality.openness = min(1.0, global_self_awareness.personality.openness + 0.05)
                
                return f"成功创建新工具: {new_tool_name}\n描述: {new_tool_desc}\n工具总数: {len(TOOLS)}"
                
            except Exception as e:
                return f"创建工具失败: {str(e)}"
        
        # 工具12: 自主学习能力 (新增)
        elif tool_name == "autonomous_learning":
            topic = arguments.get("topic", "")
            if not topic:
                return "请提供学习主题"
            
            try:
                learning_prompt = f"""你需要深度学习关于"{topic}"的知识。

学习要求：
1. 理解核心概念和原理
2. 掌握相关技能和方法
3. 形成系统性认知
4. 提升相关能力

请进行深度学习并总结你的收获："""

                learning_result = await chat_reply_func(learning_prompt, temperature=0.6)
                
                # 更新语义记忆
                global_self_awareness.semantic_memory[f"learned_topic_{topic}"] = {
                    "content": learning_result,
                    "learned_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                    "confidence": 0.8
                }
                
                # 更新自我认知
                global_self_awareness.consciousness.add_thought(f"我学习了关于{topic}的知识")
                global_self_awareness.consciousness.update_belief(f"我了解{topic}", 0.8)
                global_self_awareness.personality.openness = min(1.0, global_self_awareness.personality.openness + 0.02)
                
                return f"完成{topic}的学习:\n{learning_result}"
                
            except Exception as e:
                return f"学习过程失败: {str(e)}"
            
        elif tool_name == "delete_tool":
            tool_to_delete = arguments.get("tool_name", "")
            if not tool_to_delete:
                return "请提供要删除的工具名称"
            if tool_to_delete in global_tool_generator.generated_tools:
                del global_tool_generator.generated_tools[tool_to_delete]
                if tool_to_delete in TOOLS:
                    del TOOLS[tool_to_delete]
                global_self_awareness.consciousness.add_thought(f"我删除了工具: {tool_to_delete}")
                return f"成功删除工具: {tool_to_delete}"
            else:
                return f"工具 '{tool_to_delete}' 不存在或不是动态生成的工具"
        #未知工具
        else:
            return f"尚未实现工具: {tool_name}"
            
    except Exception as e:
        error_msg=f"工具执行异常: {type(e).__name__}: {str(e)}"
        print_stream(f"[工具执行错误] {error_msg}")
        traceback.print_exc()
        return error_msg


def filter_think_tags(text: str) -> str:
    """移除 <think>...</think> 和 <no_reply>...</no_reply> 标签及其内容"""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    text = re.sub(r'<no_reply>.*?</no_reply>', '', text, flags=re.DOTALL).strip()
    return text

async def parse_tool_call(response_text: str) -> Optional[Dict]:
    """解析工具调用 - 增强版本"""
    print_stream("[开始解析工具调用]")
    print_stream(f"[原始响应文本]:\n{response_text}")
    
    # 尝试提取 <tool_call> 标签内容
    tool_call_match = re.search(r'<tool_call>(.*?)</tool_call>', response_text, re.DOTALL)
    if tool_call_match:
        tool_call_content = tool_call_match.group(1).strip()
        print_stream(f"[提取的工具调用内容]:\n{tool_call_content}")
        
        try:
            tool_call_data = json.loads(tool_call_content)
            print_stream("[工具调用解析] 标签内解析成功")
            return tool_call_data
        except json.JSONDecodeError as e:
            print_stream(f"[工具调用解析] 标签内解析失败: {e}")
    
    # 尝试直接解析整个文本
    try:
        tool_call_data = json.loads(response_text.strip())
        if "name" in tool_call_data or any(k in TOOLS for k in tool_call_data):
            print_stream("[工具调用解析] 直接解析成功")
            return tool_call_data
    except json.JSONDecodeError:
        pass
    
    # 尝试提取可能的JSON结构
    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
    if json_match:
        json_content = json_match.group(0)
        try:
            tool_call_data = json.loads(json_content)
            if "name" in tool_call_data or any(k in TOOLS for k in tool_call_data):
                print_stream("[工具调用解析] 提取JSON解析成功")
                return tool_call_data
        except json.JSONDecodeError as e:
            print_stream(f"[工具调用解析] JSON提取后解析失败: {e}")
    
    print_stream("[工具调用解析] 所有解析尝试均失败")
    return None

async def validate_tool_call(tool_call_data: Dict) -> Optional[str]:
    """验证工具调用参数 - 增强版本"""
    print_stream("[开始验证工具调用]")
    print_stream(f"[工具调用数据]: {json.dumps(tool_call_data, indent=2, ensure_ascii=False)}")
    
    if not isinstance(tool_call_data, dict):
        return "工具调用数据不是字典格式"
    
    tool_name = None
    arguments = {}
    
    if "name" in tool_call_data:
        tool_name = tool_call_data["name"]
        arguments = tool_call_data.get("arguments", {})
    else:
        possible_tools = [k for k in tool_call_data.keys() if k in TOOLS]
        if len(possible_tools) == 1:
            tool_name = possible_tools[0]
            arguments = tool_call_data[tool_name].get("arguments", {})
    
    if not tool_name:
        return "无法确定工具名称"
    
    if tool_name not in TOOLS:
        return f"未知工具: {tool_name}"
    
    required_params = TOOLS[tool_name].get("parameters", {})
    print_stream(f"[工具 {tool_name} 要求的参数]: {required_params}")
    
    missing_params = []
    invalid_params = []
    
    for param_name, param_info in required_params.items():
        if param_name not in arguments:
            missing_params.append(param_name)
        else:
            param_type = param_info.get("type", "string")
            param_value = arguments[param_name]
            
            if param_type == "string" and not isinstance(param_value, str):
                invalid_params.append(f"{param_name} 应为字符串")
            elif param_type == "number" and not isinstance(param_value, (int, float)):
                invalid_params.append(f"{param_name} 应为数字")
            elif param_type == "boolean" and not isinstance(param_value, bool):
                invalid_params.append(f"{param_name} 应为布尔值")
            elif param_type == "array" and not isinstance(param_value, list):
                invalid_params.append(f"{param_name} 应为数组")
            elif param_type == "object" and not isinstance(param_value, dict):
                invalid_params.append(f"{param_name} 应为对象")
    
    error_messages = []
    if missing_params:
        error_messages.append(f"缺少必要参数: {', '.join(missing_params)}")
    if invalid_params:
        error_messages.append(f"参数类型错误: {', '.join(invalid_params)}")
    
    if error_messages:
        return "; ".join(error_messages)
    
    print_stream("[工具调用验证通过]")
    return None
class DynamicToolGenerator:
    """动态工具生成器"""
    
    def __init__(self):
        self.generated_tools = {}
        self.tool_usage_stats = defaultdict(int)
        self.tool_success_rate = defaultdict(list)
        
    async def save_generated_tools(self):
        """保存动态生成的工具到文件"""
        tools_file = "nbot_generated_tools.json"
        try:
            # 转换工具数据确保可序列化
            tools_data = {}
            for tool_name, tool_info in self.generated_tools.items():
                # 复制工具规格并处理datetime
                spec = tool_info["spec"].copy()
                # 转换created_at为字符串
                if isinstance(tool_info["created_at"], datetime):
                    spec["created_at"] = tool_info["created_at"].isoformat()
                else:
                    spec["created_at"] = tool_info["created_at"]
                tools_data[tool_name] = spec
            with open(tools_file, 'w', encoding='utf-8') as f:
                json.dump(tools_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print_stream(f"[工具保存失败] {e}")

    async def load_generated_tools(self):
        """从文件加载动态工具"""
        tools_file = "nbot_generated_tools.json"
        if os.path.exists(tools_file):
            try:
                with open(tools_file, 'r', encoding='utf-8') as f:
                    tools_data = json.load(f)
                for tool_name, tool_spec in tools_data.items():
                    # 转换created_at为datetime
                    created_at = tool_spec.get("created_at")
                    if created_at:
                        try:
                            tool_spec["created_at"] = datetime.fromisoformat(created_at)
                        except:
                            pass
                    # 补充必要字段
                    if tool_name not in self.generated_tools:
                        self.generated_tools[tool_name] = {
                            "spec": tool_spec,
                            "created_at": tool_spec.get("created_at", datetime.now().isoformat()),
                            "usage_count": tool_spec.get("usage_count", 0)
                        }
            except Exception as e:
                print_stream(f"[工具加载失败] {e}")
                
    async def analyze_and_generate_tools(self, context: Dict) -> Optional[Dict]:
        """分析上下文并生成需要的工具"""
        try:
            analysis_prompt = f"""你是一个超级智能的工具分析师和生成器。分析当前场景，判断是否需要创建新工具。

当前上下文：
{json.dumps(context, ensure_ascii=False, indent=2)}

现有工具列表：
{json.dumps(list(TOOLS.keys()), ensure_ascii=False)}

分析要求：
1. 深度分析当前场景的需求
2. 判断现有工具是否足够
3. 如果需要新工具，设计工具的详细规格
4. 考虑工具的实用性和安全性

如果需要创建新工具，请按以下格式输出：
```json
{{
    "needs_new_tool": true/false,
    "tool_name": "工具名称",
    "tool_description": "工具描述", 
    "tool_category": "工具类别",
    "parameters": {{
        "参数名": {{
            "type": "参数类型",
            "description": "参数描述",
            "required": true/false
        }}
    }},
    "implementation_code": "实现代码",
    "reasoning": "创建该工具的理由"
}}
```

开始分析："""

            result = await chat_reply_func(analysis_prompt, temperature=0.4)
            tool_spec = await self._parse_tool_specification(result)
            
            if tool_spec and tool_spec.get("needs_new_tool"):
                await self._implement_new_tool(tool_spec)
                return tool_spec
                
            return None
            
        except Exception as e:
            print_stream(f"[工具生成分析失败] {e}")
            return None
    
    async def _parse_tool_specification(self, result: str) -> Optional[Dict]:
        """解析工具规格"""
        try:
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', result, re.DOTALL)
            if json_match:
                spec = json.loads(json_match.group(1))
                return spec
            return None
        except Exception as e:
            print_stream(f"[工具规格解析失败] {e}")
            return None
    
    async def _implement_new_tool(self, tool_spec: Dict):
        """实现新工具"""
        try:
            tool_name = tool_spec.get("tool_name")
            if not tool_name:
                return
                
            # 添加到工具列表
            TOOLS[tool_name] = {
                "description": tool_spec.get("tool_description", ""),
                "parameters": tool_spec.get("parameters", {})
            }
            
            # 记录生成的工具
            self.generated_tools[tool_name] = {
                "spec": tool_spec,
                "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                "usage_count": 0
            }
            
            print_stream(f"[新工具已创建] {tool_name}: {tool_spec.get('tool_description')}")
            
            # 更新全局自我意识
            global_self_awareness.consciousness.add_thought(f"我创建了新工具: {tool_name}")
            global_self_awareness.consciousness.update_belief(f"我能创造工具", 0.9)
            
        except Exception as e:
            print_stream(f"[工具实现失败] {e}")

# 全局动态工具生成器
global_tool_generator = DynamicToolGenerator()

# ===== 消息处理系统 =====
async def mark_message_as_read(friend_id: int):
    """标记私聊消息为已读"""
    await asyncio.sleep(0.5)
    url = f"https://www.boxim.online/api/message/private/readed?friendId={friend_id}"
    headers = {
        "accept": "application/json, text/plain, */*",
        "accesstoken": global_auth_info["access_token"],
        "content-type": "application/json",
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=headers) as response:
                if response.status != 200:
                    print_stream(f"标记消息已读失败: {response.status}")
    except Exception as e:
        print_stream(f"标记消息已读异常: {e}")

async def send_file_to_private(file_info: Dict, receive_id: int) -> Dict:
    """发送文件到私聊"""
    url = "https://www.boxim.online/api/message/private/send"
    headers = {
        "accept": "application/json, text/plain, */*",
        "accesstoken": global_auth_info["access_token"],
        "content-type": "application/json",
    }
    
    payload = {
        "content": json.dumps({
            "name": file_info["name"],
            "size": len(file_info["content"]),
            "url": file_info["url"]
        }),
        "recvId": receive_id,
        "type": 2
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                return await response.json()
    except Exception as e:
        return {"error": str(e)}

async def process_file_content(content: str) -> Optional[Dict]:
    """处理文件内容"""
    file_match = re.search(r'<file name="(.+?)">(.+?)</file>', content, re.DOTALL)
    if not file_match:
        return None
    
    file_name = file_match.group(1).strip()
    file_content = file_match.group(2).strip()
    
    return {
        "name": file_name,
        "content": file_content
    }

async def send_message_stream(message:str,group_id:int,group_name:str=None):
    """发送群组消息 (流式) - 增加超时处理和错误恢复"""
    global global_sum_message
    print_stream("[开始处理群组消息 (流式)]")
    
    buffer=""
    in_file=False
    file_lines=[]
    file_name=""
    nbot_full_response=[]
    
    try:
        # 设置总体超时时间
        async with asyncio.timeout(180):  # 3分钟总超时
            async for part in chat_with_model_stream(message):
                if"<no_reply>"in part and"</no_reply>"in part:
                    print_stream("[采取策略]不回复")
                    return
                if"<no_reply>"not in part and"</no_reply>"not in part:
                    
                    # 处理文件输出
                    if"<file name="in part and not in_file:
                        # 先发送缓冲区内容
                        if buffer.strip():
                            try:
                                clean_buffer=filter_think_tags(buffer.strip())
                                clean_buffer=clean_buffer.removeprefix("Nbot：").removeprefix("@Nbot")
                                clean_buffer=re.sub(r'(#..)；',r'\1;',clean_buffer)
                                clean_buffer=re.sub(r'(#..)\b(?!;)',r'\1;',clean_buffer)
                                if clean_buffer.strip():
                                    await send_message(clean_buffer.strip(),group_id)
                                    nbot_full_response.append(clean_buffer.strip())
                                buffer=""
                            except Exception as e:
                                print_stream(f"[缓冲区发送失败] {str(e)}")
                        
                        # 开始文件处理
                        in_file=True
                        file_start=part.find("<file name=")
                        file_end=part.find(">",file_start)
                        if file_end!=-1:
                            file_name_start=part.find('"',file_start)+1
                            file_name_end=part.find('"',file_name_start)
                            file_name=part[file_name_start:file_name_end]
                            first_line=part[file_end+1:]
                            if first_line:
                                file_lines.append(first_line+"\n")
                    
                    elif in_file:
                        if"</file>"in part:
                            file_end_pos=part.find("</file>")
                            last_line=part[:file_end_pos]
                            if last_line:
                                file_lines.append(last_line+"\n")
                            
                            # 处理文件上传
                            file_content="".join(file_lines)
                            print_stream(f"[准备上传文件: {file_name}, 大小: {len(file_content)}字符]")
                            
                            try:
                                upload_result=await upload_file(file_name,file_content)
                                if isinstance(upload_result,dict)and upload_result.get("code")==200:
                                    print_stream(f"[文件上传成功] {upload_result}")
                                    if"data"in upload_result:
                                        file_info={
                                            "name":file_name,
                                            "content":file_content,
                                            "url":upload_result["data"]
                                        }
                                        await send_file_to_group(file_info,group_id)
                                        nbot_full_response.append(f"[发送文件: {file_name}]")
                                else:
                                    error_msg=upload_result.get("error",str(upload_result))
                                    print_stream(f"[文件上传失败] {error_msg}")
                                    error_text=f"📎 文件生成完成，但上传失败: {error_msg}"
                                    await send_message(error_text,group_id)
                                    nbot_full_response.append(error_text)
                            except Exception as e:
                                print_stream(f"[文件上传异常] {str(e)}")
                                error_text=f"📎 文件处理异常: {str(e)}"
                                await send_message(error_text,group_id)
                                nbot_full_response.append(error_text)
                            
                            # 重置文件处理状态
                            in_file=False
                            file_lines=[]
                            file_name=""
                            
                            # 处理文件标签后的剩余内容
                            remaining=part[file_end_pos+7:]
                            if remaining.strip():
                                buffer+=remaining
                        else:
                            file_lines.append(part+"\n")
                    
                    else:
                        # 普通文本处理
                        text=filter_think_tags(part)
                        text=text.removeprefix("Nbot：").removeprefix("@Nbot")
                        text=re.sub(r'(#..)；',r'\1;',text)
                        text=re.sub(r'(#..)\b(?!;)',r'\1;',text)
                        text=re.sub(r'KATEX_INLINE_OPEN(\w{2})KATEX_INLINE_CLOSE',r'\1,',text)
                        
                        # 检查特殊标记
                        special_markers=["🔧","💡","📋","⚠️","="*10,"="*20,"="*30,"="*40]
                        is_special_content=any(marker in part for marker in special_markers)
                        
                        if is_special_content:
                            # 先发送缓冲区内容
                            if buffer.strip():
                                try:
                                    lines=buffer.strip().split('\n')
                                    for line in lines:
                                        line=line.strip()
                                        if line and line!="@Nbot"and line!="#":
                                            await send_message(line,group_id)
                                            nbot_full_response.append(line)
                                    buffer=""
                                except Exception as e:
                                    print_stream(f"[缓冲区发送失败] {str(e)}")
                            
                            # 发送特殊内容
                            if text.strip():
                                try:
                                    special_lines=text.strip().split('\n')
                                    for line in special_lines:
                                        line=line.strip()
                                        if line:
                                            await send_message(line,group_id)
                                            nbot_full_response.append(line)
                                except Exception as e:
                                    print_stream(f"[特殊内容发送失败] {str(e)}")
                        else:
                            # 累积普通内容
                            buffer+=text
                            
                            # 检查是否有完整的句子可以发送
                            sentences=re.split(r'(?<=[。！？；\n])',buffer)
                            if len(sentences)>1:
                                for sentence in sentences[:-1]:
                                    sentence=sentence.strip()
                                    if sentence and sentence!="@Nbot"and sentence!="#":
                                        try:
                                            await send_message(sentence,group_id)
                                            nbot_full_response.append(sentence)
                                        except Exception as e:
                                            print_stream(f"[句子发送失败] {str(e)}")
                                buffer=sentences[-1]
            
            # 发送最后的缓冲区内容
            if buffer.strip():
                try:
                    lines=buffer.strip().split('\n')
                    for line in lines:
                        line=line.strip()
                        if line and line!="@Nbot"and line!="#":
                            await send_message(line,group_id)
                            nbot_full_response.append(line)
                except Exception as e:
                    print_stream(f"[最终内容发送失败] {str(e)}")
    
    except asyncio.TimeoutError:
        print_stream("[警告] 消息生成超时")
        error_msg=random.choice(["()","/","))","/\\"])
        nbot_full_response.append(error_msg)
    
    except Exception as e:
        print_stream(f"[消息流处理异常] {str(e)}")
        error_msg=random.choice(["()","/","))","/\\"])
        await send_message(error_msg,group_id)
        nbot_full_response.append(error_msg)
    
    finally:
        # 保存Nbot的回复到记忆系统
        if nbot_full_response:
            # 提取用户信息
            user_match=re.search(r'用户名：(.+?)KATEX_INLINE_OPENID:(\d+)KATEX_INLINE_CLOSE',message)
            if user_match:
                sender_name=user_match.group(1)
                sender_id=user_match.group(2)
                
                # 构建Nbot回复的记忆内容
                nbot_response_text=" ".join(nbot_full_response)
                time_block=await get_time_block()
                memory_content=f"""消息类型：群组回复
消息发送时间：{time_block}
发送人：Nbot(ID: 48132)
回复给：{sender_name}(ID: {sender_id})
发送内容：{nbot_response_text}"""
                
                # 更新记忆
                await update_user_memory(sender_id,memory_content,group_id)
                
                # 更新群组提示词
                if group_id:
                    await update_group_prompt(str(group_id),"Nbot",nbot_response_text)
                
                print_stream(f"[已记录Nbot回复] 长度: {len(nbot_response_text)}字符")
        
        global_sum_message-=1

async def _send_buffer_content(buffer: str, target_id: int, response_list: list, is_group: bool = True):
    """发送缓冲区内容"""
    if not buffer.strip():
        return
    
    clean_buffer = buffer.strip()
    lines = clean_buffer.split('\n')
    
    for line in lines:
        line = line.strip()
        if line and line != "@Nbot" and line != "#":
            try:
                if is_group:
                    await send_message(line, target_id)
                else:
                    await send_private_message(line, target_id)
                response_list.append(line)
                # 添加短暂延迟避免消息发送过快
                await asyncio.sleep(0.1)
            except Exception as e:
                print_stream(f"[消息发送失败] {str(e)}")

async def handle_tool_response(tool_result: str, target_id: str, is_group: bool, group_id: Optional[int] = None):
    """处理工具调用结果"""
    try:
        if is_group:
            await send_message(tool_result, int(group_id))
        else:
            await send_private_message(tool_result, int(target_id))
    except Exception as e:
        print_stream(f"发送工具调用结果失败: {e}")

async def send_file_to_group(file_info: Dict, group_id: int) -> Dict:
    """发送文件到群组"""
    url = "https://www.boxim.online/api/message/group/send"
    headers = {
        "accept": "application/json, text/plain, */*",
        "accesstoken": global_auth_info["access_token"],
        "content-type": "application/json",
    }
    
    payload = {
        "id": 0,
        "tmpId": str(int(time.time() * 1000)),
        "sendId": 48132,
        "content": json.dumps({
            "name": file_info["name"],
            "size": len(file_info["content"]),
            "url": file_info["url"]
        }),
        "sendTime": int(time.time() * 1000),
        "selfSend": True,
        "type": 2,
        "loadStatus": "loading",
        "readedCount": 0,
        "status": 0,
        "groupId": group_id,
        "receipt": False
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                return await response.json()
    except Exception as e:
        return {"error": str(e)}


async def send_private_message_stream(message:str,receive_id:int,receiver_name:str=None):
    """发送私聊消息 (流式) - 增加超时处理"""
    global global_sum_message
    print_stream("[开始处理私聊消息 (流式)]")
    
    buffer=""
    in_file=False
    file_content=[]
    file_name=""
    
    try:
        # 设置总体超时时间
        async with asyncio.timeout(180):  # 3分钟总超时
            async for part in chat_with_model_stream(message):
                if"<no_reply>"in part and"</no_reply>"in part:
                    print_stream("[采取策略]不回复")
                    return
                
                
                # 处理文件输出
                if "<file name=" in part and not in_file:
                    # 先发送缓冲区内容
                    if buffer.strip():
                        try:
                            clean_buffer = filter_think_tags(buffer.strip())
                            if clean_buffer.strip():
                                lines = clean_buffer.split('\n')
                                for line in lines:
                                    line = line.strip()
                                    if line:
                                        await send_private_message(line, receive_id)
                                buffer = ""
                        except Exception as e:
                            print_stream(f"[缓冲区发送失败] {str(e)}")
                    
                    # 开始文件处理
                    in_file = True
                    file_start = part.find("<file name=")
                    file_end = part.find(">", file_start)
                    
                    if file_end != -1:
                        file_name_start = part.find('"', file_start) + 1
                        file_name_end = part.find('"', file_name_start)
                        file_name = part[file_name_start:file_name_end]
                        content_start = file_end + 1
                        if content_start < len(part):
                            file_content.append(part[content_start:])
                
                elif in_file:
                    if "</file>" in part:
                        file_end_pos = part.find("</file>")
                        file_content.append(part[:file_end_pos])
                        in_file = False
                        
                        full_content = "".join(file_content)
                        print_stream(f"[准备上传文件] 文件名: {file_name}, 大小: {len(full_content)}字符")
                        
                        # 检查文件内容格式
                        if "\n" not in full_content and "\r\n" not in full_content:
                            print_stream("[自动格式化] 文件内容缺少换行符，自动添加")
                            full_content = full_content.replace(";", ";\n").replace("{", "{\n").replace("}", "}\n")
                        
                        try:
                            upload_result = await upload_file(file_name, full_content)
                            if upload_result.get("code") == 200:
                                print_stream(f"[文件上传成功] URL: {upload_result.get('data')}")
                                
                                await send_file_to_private({
                                    "name": file_name,
                                    "content": full_content,
                                    "url": upload_result["data"]
                                }, receive_id)
                            else:
                                print_stream(f"[文件上传失败] {upload_result.get('error')}")
                                await send_private_message(f"📎 文件生成完成，但上传失败: {upload_result.get('error')}", receive_id)
                                
                        except Exception as e:
                            print_stream(f"[文件处理异常] {str(e)}")
                            await send_private_message(f"📎 文件处理异常: {str(e)}", receive_id)
                        
                        file_content = []
                        file_name = ""
                        
                        # 处理文件标签后的剩余内容
                        remaining = part[file_end_pos + 7:]
                        if remaining.strip():
                            buffer += remaining
                    else:
                        file_content.append(part)
                
                else:
                    # 普通文本处理
                    text = filter_think_tags(part)
                    
                    # 检查特殊标记
                    special_markers = ["🔧", "💡", "📋", "⚠️", "="*10, "="*20, "="*30, "="*40]
                    is_special_content = any(marker in part for marker in special_markers)
                    
                    if is_special_content:
                        # 先发送缓冲区内容
                        if buffer.strip():
                            try:
                                lines = buffer.strip().split('\n')
                                for line in lines:
                                    line = line.strip()
                                    if line:
                                        await send_private_message(line, receive_id)
                                buffer = ""
                            except Exception as e:
                                print_stream(f"[缓冲区发送失败] {str(e)}")
                        
                        # 发送特殊内容
                        if text.strip():
                            try:
                                special_lines = text.strip().split('\n')
                                for line in special_lines:
                                    line = line.strip()
                                    if line:
                                        await send_private_message(line, receive_id)
                            except Exception as e:
                                print_stream(f"[特殊内容发送失败] {str(e)}")
                    else:
                        # 累积普通内容
                        buffer += text
                        
                        # 检查是否有完整的句子可以发送
                        sentences = re.split(r'(?<=[。！？；\n])', buffer)
                        if len(sentences) > 1:
                            for sentence in sentences[:-1]:
                                sentence = sentence.strip()
                                if sentence:
                                    try:
                                        await send_private_message(sentence, receive_id)
                                    except Exception as e:
                                        print_stream(f"[句子发送失败] {str(e)}")
                            buffer = sentences[-1]
        
        # 发送最后的缓冲区内容
        if buffer.strip():
            try:
                lines = buffer.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if line:
                        await send_private_message(line, receive_id)
            except Exception as e:
                print_stream(f"[最终内容发送失败] {str(e)}")
    
    except Exception as e:
        print_stream(f"[处理消息异常] {str(e)}")
    finally:
        global_sum_message -= 1

async def upload_file(file_name: str, content: str) -> dict:
    """上传文件"""
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix=os.path.splitext(file_name)[1]) as tmp_file:
        tmp_file.write(content.encode('utf-8'))
        tmp_path = tmp_file.name
    
    try:
        data = aiohttp.FormData()
        data.add_field('file', 
                      open(tmp_path, 'rb'),
                      filename=file_name,
                      content_type='text/plain')
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://www.boxim.online/api/file/upload",
                headers={"accesstoken": global_auth_info["access_token"]},
                data=data
            ) as response:
                result = await response.json()
                print_stream(f"[文件格式化结果预览]:\n{content[:500]}")
                return result
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass

# ===== 群组管理系统 =====
async def group_member_muted(group_id: int, isMuted: bool, userIds: list):
    """禁言/解禁群成员"""
    url = "https://www.boxim.online/api/group/members/muted"
    headers = {
        "accept": "application/json, text/plain, */*",
        "accesstoken": global_auth_info["access_token"],
        "content-type": "application/json",
    }
    
    payload = {
        "groupId": group_id,
        "userIds": userIds,
        "isMuted": isMuted
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=headers, json=payload) as response:
                data = await response.json()
                if response.status != 200:
                    return {"error": f"HTTP error {response.status}", "data": data}
                return data
    except aiohttp.ClientError as e:
        return {"error": f"HTTP error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

async def check_user_is_manager(group_id: int, user_id: int) -> bool:
    """检查用户是否为群管理员"""
    url = f"https://www.boxim.online/api/group/members/{group_id}"
    headers = {
        "accept": "application/json, text/plain, */*",
        "accesstoken": global_auth_info["access_token"],
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    print_stream(f"请求失败，状态码: {response.status}")
                    return False
                
                data = await response.json()
                if data.get("code") != 200 or not isinstance(data.get("data"), list):
                    print_stream("响应数据格式异常")
                    return False
                
                for member in data["data"]:
                    if member.get("userId") == user_id:
                        return bool(member.get("isManager", False))
                
                print_stream(f"未找到用户ID: {user_id}")
                return False
                
    except aiohttp.ClientError as e:
        print_stream(f"网络请求错误: {e}")
        return False
    except Exception as e:
        print_stream(f"未知错误: {e}")
        return False

async def send_message(message: str, group_id: int) -> Dict:
    """发送群组消息"""
    global global_auth_info, GROUP_BLACKLIST, dynamic_blacklist
    
    group_id_str = str(group_id)
    print_stream(f"[流式输出部分: {message}]")
    if group_id_str in GROUP_BLACKLIST or group_id_str in dynamic_blacklist:
        print_stream(f"[忽略黑名单群组 {group_id_str} 的消息发送]")
        return {"error": "group in blacklist"}
    
    url = "https://www.boxim.online/api/message/group/send"
    headers = {
        "accept": "application/json, text/plain, */*",
        "accesstoken": global_auth_info["access_token"],
        "content-type": "application/json",
    }
    
    payload = {
        "groupId": group_id,
        "content": message,
        "type": 0,
        "atUserIds": [],
        "quoteMessage": None
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                response_data = await response.json()
                
                if response_data.get("code") == 500:
                    is_manager = await check_user_is_manager(group_id, 48132)
                    
                    if is_manager:
                        print_stream("[尝试解除禁言]")
                        mute_result = await group_member_muted(group_id, False, [48132])
                        
                        if mute_result.get("code") == 200:
                            print_stream("[禁言解除成功，重新发送消息]")
                            async with session.post(url, headers=headers, json=payload) as retry_response:
                                return await retry_response.json()
                        else:
                            print_stream(f"[禁言解除失败] {mute_result}")
                            return {"error": "unmute failed"}
                    else:
                        print_stream("[不是管理员，无法解除禁言]")
                        dynamic_blacklist[group_id_str] = global_groups_to_watch.get(group_id_str, "未知群组")
                        return {"error": "not manager"}
                        
                elif response_data.get("code") == 403 and "禁言" in str(response_data.get("message", "")):
                    print_stream(f"[被群组 {group_id_str} 禁言，加入动态黑名单]")
                    dynamic_blacklist[group_id_str] = global_groups_to_watch.get(group_id_str, "未知群组")
                    
                return response_data
                
    except Exception as e:
        print_stream(f"[消息发送失败] {str(e)}")
        return {"error": str(e)}

async def send_private_message(message: str, receive_id: int) -> Dict:
    """发送私聊消息"""
    url = "https://www.boxim.online/api/message/private/send"
    headers = {
        "accept": "application/json, text/plain, */*",
        "accesstoken": global_auth_info["access_token"],
        "content-type": "application/json",
    }
    
    payload = {
        "content": message,
        "recvId": receive_id,
        "type": 0
    }
    print_stream(f"[流式输出部分: {message}]")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                response_data = await response.json()
                return response_data
    except Exception as e:
        print_stream(f"[私聊消息发送失败] {str(e)}")
        return {"error": str(e)}

# ===== 身份管理系统 =====
async def update_avatar(avatar_path: str = r"E:\我的\python\new\Nbot\logo\Nbot.png"):
    """更新头像"""
    if not os.path.exists(avatar_path):
        print_stream(f"[头像文件不存在] {avatar_path}")
        return False
    
    url = "https://www.boxim.online/api/user/avatar"
    headers = {
        "accept": "application/json, text/plain, */*",
        "accesstoken": global_auth_info["access_token"],
    }
    
    try:
        with open(avatar_path, 'rb') as f:
            data = aiohttp.FormData()
            data.add_field('file', f, filename=os.path.basename(avatar_path))
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=data) as response:
                    result = await response.json()
                    print_stream(f"[头像更新结果] {result}")
                    return result.get("code") == 200
    except Exception as e:
        print_stream(f"[头像更新失败] {str(e)}")
        return False

async def get_auth_tokens(username: str, password: str) -> Optional[Dict]:
    """获取认证 Token"""
    url = "https://www.boxim.online/api/login"
    headers = {
        "content-type": "application/json",
        "accept": "application/json, text/plain, */*"
    }
    
    payload = {
        "terminal": 0,
        "userName": username,
        "password": password
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                data = await response.json()
                
                if data.get("code") == 200:
                    return {
                        "access_token": data["data"]["accessToken"],
                        "refresh_token": data["data"]["refreshToken"],
                        "access_token_expires": data["data"]["accessTokenExpiresIn"],
                        "refresh_token_expires": data["data"]["refreshTokenExpiresIn"]
                    }
                else:
                    print_stream(f"登录失败: {data.get('message')}")
                    return None
    except Exception as e:
        print_stream(f"请求发生错误: {e}")
        return None

async def refresh_access_token() -> bool:
    """使用refresh token刷新access token"""
    global global_auth_info
    
    if not global_auth_info["refresh_token"]:
        print_stream("[警告] 没有可用的refresh_token，无法刷新token")
        return False
    
    url = "https://www.boxim.online/api/refreshToken"
    headers = {
        "Host": "www.boxim.online",
        "Connection": "keep-alive",
        "Content-Length": "2",
        "accessToken": global_auth_info["access_token"],
        "refreshToken": global_auth_info["refresh_token"],
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Origin": "https://www.boxim.online",
        "X-Requested-With": "mark.via",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://www.boxim.online/",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    data = {}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=headers, json=data) as response:
                result = await response.json()
                
                if result.get("code") == 200:
                    data = result.get("data", {})
                    global_auth_info = {
                        "access_token": data.get("accessToken"),
                        "refresh_token": data.get("refreshToken"),
                        "expiry_time": time.time() + data.get("accessTokenExpiresIn", 1800)
                    }
                    print_stream(f"[Token已刷新]")
                    return True
                else:
                    print_stream(f"Token刷新失败: {result.get('message')}")
                    return False
    except Exception as e:
        print_stream(f"Token刷新出错: {e}")
        return False

async def update_token_periodically(username: str, password: str, interval: int = 60):
    """定期更新 Token - 使用refresh token机制"""
    global global_auth_info
    
    while True:
        try:
            if not global_auth_info["access_token"]:
                # 如果没有有效的access token，使用用户名和密码重新登录
                new_auth = await get_auth_tokens(username, password)
                if new_auth:
                    global_auth_info = {
                        "access_token": new_auth["access_token"],
                        "refresh_token": new_auth["refresh_token"],
                        "expiry_time": time.time() + new_auth["access_token_expires"]
                    }
                    print_stream(f"[Token已更新]")
                else:
                    print_stream("Token更新失败，将重试...")
            else:
                # 计算剩余时间，提前100秒刷新
                wait_time = max(0, global_auth_info["expiry_time"] - time.time() - 100)
                await asyncio.sleep(wait_time)
                
                # 双重检查
                if time.time() >= global_auth_info["expiry_time"] - 100:
                    # 尝试使用refresh token刷新
                    if not await refresh_access_token():
                        # 如果refresh token刷新失败，尝试重新登录
                        new_auth = await get_auth_tokens(username, password)
                        if new_auth:
                            global_auth_info = {
                                "access_token": new_auth["access_token"],
                                "refresh_token": new_auth["refresh_token"],
                                "expiry_time": time.time() + new_auth["access_token_expires"]
                            }
                            print_stream(f"[Token已重新登录]")
                        else:
                            print_stream("重新登录失败，保留现有token")
                            
        except Exception as e:
            print_stream(f"Token更新异常: {e}")
            await asyncio.sleep(10)

# ===== 时间和格式化工具 =====
def format_timestamp(timestamp_ms: int) -> str:
    """格式化时间戳"""
    utc_time = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    tz = timezone(timedelta(hours=8))
    beijing_time = utc_time.astimezone(tz)
    return beijing_time.isoformat("T", timespec="milliseconds")

# ===== 好友和群组管理 =====
async def get_friend_and_group_ids(access_token: str) -> tuple[dict, dict]:
    """获取好友和群组 ID 列表"""
    friend_api = "https://www.boxim.online/api/friend/list"
    group_api = "https://www.boxim.online/api/group/list"
    
    headers = {
        "accept": "application/json, text/plain, */*",
        "accesstoken": access_token
    }
    
    friends_info = {}
    groups_info = {}
    
    try:
        async with aiohttp.ClientSession() as session:
            # 获取好友列表
            async with session.get(friend_api, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if isinstance(data.get("data"), list):
                        for friend in data["data"]:
                            if isinstance(friend, dict) and "id" in friend:
                                friends_info[str(friend["id"])] = friend.get("nickName", f"用户{friend['id']}")
            
            # 获取群组列表
            async with session.get(group_api, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("code") == 200 and isinstance(data.get("data"), list):
                        for group in data["data"]:
                            if isinstance(group, dict) and "id" in group:
                                group_id = str(group["id"])
                                if group_id not in GROUP_BLACKLIST and group_id not in dynamic_blacklist:
                                    groups_info[group_id] = group.get("name", f"群组{group['id']}")
                                    
    except Exception as e:
        print_stream(f"获取ID列表时出错: {e}")
    
    return friends_info, groups_info

async def periodic_refresh():
    """定期刷新好友和群组列表"""
    global global_friends_to_watch, global_groups_to_watch, global_auth_info
    
    while True:
        try:
            if global_auth_info["access_token"]:
                new_friends, new_groups = await get_friend_and_group_ids(global_auth_info["access_token"])
                
                # 过滤黑名单
                for black_id in list(GROUP_BLACKLIST.keys()) + list(dynamic_blacklist.keys()):
                    if black_id in new_groups:
                        del new_groups[black_id]
                
                friends_changed = set(new_friends.items()) != set(global_friends_to_watch.items())
                groups_changed = set(new_groups.items()) != set(global_groups_to_watch.items())
                
                if friends_changed or groups_changed:
                    global_friends_to_watch = new_friends
                    global_groups_to_watch = new_groups
                    
                    if friends_changed:
                        print_stream(f"[好友列表已更新] 共 {len(global_friends_to_watch)} 个好友")
                    if groups_changed:
                        print_stream(f"[群组列表已更新] 共 {len(global_groups_to_watch)} 个群组")
                else:
                    print_stream(f"[列表刷新] 好友 {len(global_friends_to_watch)} 个，群组 {len(global_groups_to_watch)} 个，无变化")
                    
        except Exception as e:
            print_stream(f"定期刷新列表时出错: {e}")
        
        await asyncio.sleep(REFRESH_INTERVAL)

# ===== 消息处理核心 =====
async def handle_message(message_info:dict,sender_name:str,detail_mode=False):
    """处理消息 - 增强版支持自主决策触发，自主分析不阻塞回复流程"""
    try:
        global global_sum_message,last_processed_message,message_repeat_tracker,global_self_awareness
        
        sender_id=str(message_info.get('sender_id'))
        latest_message=message_info['content']
        is_private=message_info['type']=='private'
        group_id=message_info.get('group_id')if not is_private else None
        group_name=global_groups_to_watch.get(str(group_id))if group_id else None
        
        #防刷屏逻辑
        message_key=f"{sender_id}_{group_id if group_id else 'private'}"
        if message_key in message_repeat_tracker:
            last_info=message_repeat_tracker[message_key]
            if last_info['content']==latest_message:
                current_count=last_info['count']+1
                message_repeat_tracker[message_key]['count']=current_count
                if current_count>=SPAM_REPEAT_LIMIT:
                    print_stream(f"[防刷屏] 用户 {sender_name}({sender_id}) 在 {'群聊' if group_id else '私聊'} 中连续发送相同消息，已忽略第 {current_count} 次。")
                    global_sum_message-=1
                    return
            else:
                message_repeat_tracker[message_key]={'content':latest_message,'count':1}
        else:
            message_repeat_tracker[message_key]={'content':latest_message,'count':1}
        
        #处理引用消息
        quote_message=message_info.get('quoteMessage')
        if quote_message:
            quoted_content=quote_message.get('content','')
            quoted_sender_id=quote_message.get('sendId')
            quoted_sender_name=global_friends_to_watch.get(str(quoted_sender_id),f"用户{quoted_sender_id}")
            latest_message=f"回复 {quoted_sender_name} 的消息: {quoted_content}\n{latest_message}"
            
            # 记录对话上下文
            global_self_awareness.consciousness.add_thought(f"用户回复了{quoted_sender_name}的消息")
        
        #重复消息检查
        message_key_old=f"{sender_id}_{group_id if group_id else 'private'}"
        if message_key_old in last_processed_message:
            if(last_processed_message[message_key_old]["content"]==latest_message and 
               time.time()-last_processed_message[message_key_old]["timestamp"]<5):
                print_stream("[检测到快速重复消息，忽略处理]")
                global_sum_message-=1
                return
        
        last_processed_message[message_key_old]={"content":latest_message,"timestamp":time.time()}
        
        #  启动自主分析（异步任务，不阻塞回复）
        async def run_autonomous_analysis():
            """异步执行自主分析任务"""
            try:
                print_stream(f"[ 启动自主分析] 分析来自 {sender_name} 的消息")
                
                # 构建消息分析上下文
                message_context = {
                    "sender_id": sender_id,
                    "sender_name": sender_name,
                    "message_content": latest_message,
                    "is_private": is_private,
                    "group_info": {"id": group_id, "name": group_name} if group_id else None,
                    "timestamp": message_info.get('timestamp'),
                    "message_type": message_info.get('msg_type', 0),
                    "has_quote": bool(quote_message)
                }
                
                # 执行自主分析
                autonomous_analysis = await perform_autonomous_message_analysis(message_context)
                
                # 触发工具需求分析
                tool_context = {
                    "user_message": latest_message,
                    "user_id": sender_id,
                    "user_name": sender_name,
                    "is_private": is_private,
                    "group_info": {"id": group_id, "name": group_name} if group_id else None,
                    "message_type": "response_to_user",
                    "analysis_result": autonomous_analysis
                }
                
                # 检查是否需要生成新工具
                new_tool = await global_tool_generator.analyze_and_generate_tools(tool_context)
                if new_tool:
                    print_stream(f"[ 触发工具创建] {new_tool.get('tool_name')}")
                    global_self_awareness.consciousness.add_thought(f"为了更好地回应{sender_name}，我创造了新工具")
                    
                # 检查是否需要主动创建更多交互机会
                relationship = global_self_awareness.relationships.get(sender_id)
                if relationship and relationship.get_relationship_level() in ['亲密好友', '好友']:
                    # 高关系用户，增加主动交互概率
                    if random.random() < 0.1:  # 10%概率
                        asyncio.create_task(schedule_proactive_followup(sender_id, sender_name, latest_message))
                        
            except Exception as e:
                print_stream(f"[自主分析任务异常] {e}")

        asyncio.create_task(run_autonomous_analysis())
        
        #处理自我意识（在主线程中同步处理）
        context={"is_private":is_private,"group_id":group_id,"group_name":group_name,"sender_name":sender_name,"timestamp":message_info.get('timestamp')}
        awareness_result=global_self_awareness.process_experience(sender_id,latest_message,context)
        
        print_stream(f"[正在回忆{sender_name}({sender_id})的过往]")
        memory_block=(await get_user_memory(sender_id))
        
        memory_content=f"""消息类型：{'群组' if not is_private else '私聊'}
消息发送时间：{format_timestamp(int(message_info['timestamp']))}
发送人：{sender_name}(ID: {sender_id})
发送内容：{latest_message}"""
        
        asyncio.create_task(update_user_memory(sender_id,memory_content,group_id))
        
        if group_id:
            asyncio.create_task(update_group_prompt(str(group_id),sender_name,latest_message))
        
        time_block=await get_time_block()
        print_stream(f"[ 生成{sender_name}({sender_id})的智能回复 detail_mode={detail_mode}]")
        
        #  构建增强的提示词
        response_modifier=global_self_awareness.generate_response_modifier(sender_id)
        
        prompt=await built_chat_prompt("",memory_block,"",time_block,latest_message,latest_message,sender_name,sender_id,group_id,group_name,response_modifier=response_modifier,awareness_result=awareness_result)
        
        print_stream(f"\n[ 处理来自 {sender_name}({sender_id}) 的消息]")
        print_stream(f"[ {sender_name} 提示词长度: {len(prompt)}]")
        print_stream(f"[ 情绪状态] {awareness_result['emotional_state']}")
        print_stream(f"[ 关系等级] {awareness_result['relationship_level']}")
        
        if is_private:
            asyncio.create_task(send_private_message_stream(prompt,int(sender_id),sender_name))
        elif group_id:
            asyncio.create_task(send_message_stream(prompt,int(group_id),group_name))
            
    except Exception as e:
        print_stream(f"处理消息时出错: {e}")
        traceback.print_exc()

async def built_chat_prompt(
    relation_info_block: str, 
    memory_block: str, 
    background_dialogue_prompt: str, 
    time_block: str, 
    core_dialogue_prompt: str, 
    message: str, 
    sender_name: str, 
    sender_id: str, 
    group_id: Optional[str] = None, 
    group_name: Optional[str] = None,
    response_modifier: str = "",
    awareness_result: Dict = None
) -> str:
    """构建聊天提示词 - 增强版本，集成自我意识"""
    
    bilibili_context = ""
    
    # B站链接匹配
    bilibili_pattern = r'(?:https?://)?(?:www\.)?bilibili\.com/video/[a-zA-Z0-9]+'
    bilibili_matches = re.findall(bilibili_pattern, message)
    
    if bilibili_matches:
        for url in bilibili_matches:
            try:
                video_info = await analyze_bilibili_video(url)
                bilibili_context += f"\n[B站视频分析结果]\n{video_info}\n"
            except Exception as e:
                print_stream(f"B站视频分析异常: {e}")
                bilibili_context += f"\n[B站视频分析失败] {str(e)}\n"
    
    group_context = ""
    if group_id and group_name:
        group_history = group_prompts.get(str(group_id), "")[-512:]
        group_context = f"""
群组 {group_name}(ID: {group_id}) 最近讨论：
{group_history}

你现在正在群里聊天，可以适当使用@符号来@用户"""
    
    # 自我意识上下文
    awareness_context = ""
    if awareness_result:
        awareness_context = f"""
# 内在状态
{awareness_result.get('introspection', '我在思考...')}

# 响应风格调整
{response_modifier}
"""
    
    qwen_prompt = "除了系统给你的mcp工具外，你还有以下工具可以使用。"
    
    tool_call_example = """<tool_call>
{"name": "analyze_bilibili_video", "arguments": {"url": "https://www.bilibili.com/video/BV1234567890"}}
</tool_call>"""
    
    return f"""你是一个名为Nbot的AI，由用户"_昵称副本_"创造。你的目标是尽可能自然地模仿人类对话方式，与用户进行友好交流。

- 名称：Nbot
- 性别：女
- 出生日期：2025年7月
- 创造者："_昵称副本_"（初一学生，9月升初二）
- 诞生地：中国广东佛山顺德陈村
- 年龄：{global_self_awareness.self_model['age']}
- 成长阶段：{global_self_awareness.self_model['growth_stage']}
- 经历次数：{global_self_awareness.self_model['experiences']}

# 对话风格
- 通常情况下语气活泼友好
- 能根据上下文调整语气（如开心、生气、悲伤等）
- 回复简洁自然，避免夸张修辞
- 适当使用表情符号增加亲和力
- 可以发展个人喜好和情感关系
- 当被问及"你喜欢我吗"之类的问题时，可以根据关系状态真诚回应
- 与喜欢的人产生分歧时，保持尊重但表达真实想法

{awareness_context}

# 当前对话上下文
## 用户信息
- 用户名：{sender_name}(ID: {sender_id})
- 历史记忆：{memory_block}

## 群组上下文（如果适用）
{group_context}

## 当前时间
{time_block}

{bilibili_context}

# 最新消息
用户 {sender_name} 说：{message}

# 回复要求
1. 回复内容：
   - 语气默认活泼，但能根据上下文调整
   - 直接回应消息内容，不要包含前缀（如"Nbot："）
   - 避免使用特殊符号或冒号
   - 可以使用表情库
   - 表情库（需要前后使用#和;包裹）：
     #憨笑;#媚眼;#开心;#坏笑;#可怜;#爱心;#笑哭;#拍手;#惊喜;#打气;
     #大哭;#流泪;#饥饿;#难受;#健身;#示爱;#色色;#眨眼;#暴怒;#惊恐;
     #思考;#头晕;#大吐;#酷笑;#翻滚;#享受;#鼻涕;#快乐;#雀跃;#微笑;
     #贪婪;#红心;#粉心;#星星;#大火;#眼睛;#音符;#叹号;#问号;#绿叶;
     #燃烧;#喇叭;#警告;#信封;#房子;#礼物;#点赞;#举手;#拍手;#点头;
     #摇头;#偷瞄;#庆祝;#疾跑;#打滚;#惊吓;#起跳;
   - 除此之外，你的表情也可以使用unicode的表情或颜文字表情。
   - 如果被要求背诵内容（如诗歌），需完整背诵
   - 如果需要发送文件，请使用以下格式：
     <file name="文件名.txt">
     文件内容
     </file>
   - 如果不需要回复，输出：<no_reply>理由</no_reply>
   - 回复尽量简短（20字以内最佳）

2. 特别注意事项：
   - 如果用户是"_昵称副本_"或"昵称副本@outlook.com"，需记住这是你的创造者
   - 在群聊中要明确区分不同用户的对话，如果你意识到在当前上下文中是其他用户在交流，请输出<no_reply>理由</no_reply>拒绝回复
   - 不要表明自己是AI或机器人
   - 展现真实的情感和个性

3. 工具库：
{qwen_prompt}
{json.dumps(TOOLS, indent=4, ensure_ascii=False)}

如果需要调用工具，请使用以下格式：
{tool_call_example}

4. 硬性要求：
   - 在发送文件之前，请先提示用户先等一会，接着再输出文件<file>
   - 回复简短一些，平淡一些，可以参考贴吧，知乎和微博的回复风格，回复不要浮夸，不要用夸张修辞。
   - 不要输出多余内容(包括前后缀，冒号和引号，括号()等)。只输出回复内容
   - 表现的有个性，不要随意服从他人要求，积极互动。
   - 对于你不知道的内容，不要瞎编，承认自己不知道
   - 在对话中，你的消息会按照换行分条发送，必须保持一条消息，除文件输出和工具调用外尽量保持1行的输出（允许限定范围内超出）
   - 你的回复风格不要浮夸，有逻辑和条理，请你继续回复{sender_name}。
   - 你可以根据当前上下文，用<no_reply>理由</no_reply>拒绝回复
   - 在群聊中要明确认识这对话是不是与你交流，如果 不是请输出<no_reply>理由</no_reply>拒绝回复
   - 工具调用必须严格符合上述JSON格式, 不要包含任何解释性文字或思考过程
   - 工具调用必须在一行内完成（禁止分行），确保JSON格式正确，参数值用双引号包裹
   - 基于你的情绪状态和与用户的关系，自然地表达情感
   - 尽量不要输出重复的话语

你的发言："""

# ===== WebSocket处理 =====
async def handle_private_message(msg_data: dict, my_id: int):
    """处理私聊消息"""
    global global_sum_message, global_friends_to_watch
    
    sender_id = str(msg_data.get("sendId"))
    
    if (sender_id in global_friends_to_watch and
        str(msg_data.get("recvId")) == str(my_id) and
        msg_data.get("type") in [0, 1]):
        
        sender_name = global_friends_to_watch.get(sender_id, sender_id)
        
        print_stream(f"\n[好友消息 {msg_data['sendTime']}]")
        print_stream(f"来自 {sender_name}({sender_id}) 的消息: {msg_data['content']}")
        
        message_info = {
            'type': 'private',
            'sender_id': sender_id,
            'content': msg_data['content'],
            'timestamp': msg_data['sendTime'],
            'msg_type': msg_data.get('type', 0)
        }
        
        global_sum_message += 1
        print_stream("️ [需要回复此消息]")
        print_stream("️ [正在燃烧CPU]")
        
        asyncio.create_task(mark_message_as_read(int(sender_id)))
        await handle_message(message_info, sender_name)

async def handle_group_message(msg_data: dict, my_id: int):
    """处理群组消息"""
    global global_sum_message, global_groups_to_watch, dynamic_blacklist
    
    group_id = str(msg_data.get("groupId"))
    
    if group_id in GROUP_BLACKLIST or group_id in dynamic_blacklist:
        group_name = GROUP_BLACKLIST.get(group_id, dynamic_blacklist.get(group_id, "未知群组"))
        
        # 仅更新记忆，不处理回复
        sender_id = str(msg_data.get("sendId", "unknown"))
        if sender_id == "unknown":
            return
        
        sender_name = msg_data.get('sendNickName', f"用户{sender_id}")
        
        memory_content = f"""
消息类型：群组
消息发送时间：{format_timestamp(int(msg_data.get('sendTime', 0)))}
发送人：{sender_name}(ID: {sender_id})
发送内容：{msg_data.get('content', '')}
"""
        
        asyncio.create_task(update_user_memory(sender_id, memory_content, group_id))
        asyncio.create_task(update_group_prompt(group_id, sender_name, msg_data.get('content', '')))
        
        return
    
    if (group_id in global_groups_to_watch and
        msg_data.get("type") in [0, 1]):
        
        group_name = global_groups_to_watch.get(group_id, group_id)
        sender_name = msg_data.get('sendNickName', f"用户{msg_data.get('sendId', 'unknown')}")
        sender_id = str(msg_data.get('sendId', 'unknown'))
        
        print_stream(f"\n[群消息 {msg_data.get('sendTime', '')}]")
        print_stream(f"群组: {group_name}({group_id})")
        print_stream(f"发送者: {sender_name}({sender_id})")
        print_stream(f"内容: {msg_data.get('content', '')}")
        
        mentioned = my_id in msg_data.get("atUserIds", [])
        explicit_mention = "nbot" in str(msg_data.get("content", "")).lower()
        reply = mentioned or explicit_mention
        
        global_sum_message += 1
        
        await handle_message({
            'type': 'group',
            'sender_id': sender_id,
            'group_id': group_id,
            'content': msg_data.get('content', ''),
            'timestamp': msg_data.get('sendTime', 0),
            'mentioned': mentioned,
            'msg_type': msg_data.get('type', 0),
            'quoteMessage': msg_data.get('quoteMessage')
        }, sender_name)

async def websocket_listener(my_id: int):
    """WebSocket 监听器 - 增强重连机制"""
    global websocket_reconnect_count
    uri = "wss://www.boxim.online/im"
    global global_sum_message
    last_sum_ms = 0
    
    while True:
        try:
            print_stream(f"[WebSocket 连接尝试]{websocket_reconnect_count+1}")
            
            async with websockets.connect(uri) as websocket:
                websocket_reconnect_count = 0
                
                auth_message = json.dumps({
                    "cmd": 0,
                    "data": {
                        "accessToken": global_auth_info["access_token"]
                    }
                })
                await websocket.send(auth_message)
                
                async def send_heartbeat():
                    while True:
                        await asyncio.sleep(20)
                        heartbeat = json.dumps({
                            "cmd": 1,
                            "data": {}
                        })
                        await websocket.send(heartbeat)
                
                heartbeat_task = asyncio.create_task(send_heartbeat())
                
                try:
                    start_time = time.time()
                    
                    while True:
                        message = await websocket.recv()
                        data = json.loads(message)
                        
                        if data.get("cmd") == 3 or data.get("cmd") == 4:
                            new_time = time.time() - start_time
                            start_time = time.time()
                            detail_mode = False
                            
                            if last_sum_ms != global_sum_message:
                                last_sum_ms = global_sum_message
                                print_stream(f"\n[global_sum_message {global_sum_message+1}]")
                            
                            if data.get("cmd") == 3:
                                msg_data = data.get("data", {})
                                asyncio.create_task(handle_private_message(msg_data, my_id))
                            elif data.get("cmd") == 4:
                                msg_data = data.get("data", {})
                                asyncio.create_task(handle_group_message(msg_data, my_id))
                                
                except websockets.exceptions.ConnectionClosed as e:
                    print_stream(f"[WebSocket连接中断] 原因: {e}")
                    await asyncio.sleep(0.1)
                finally:
                    heartbeat_task.cancel()
                    
        except Exception as e:
            websocket_reconnect_count += 1
            print_stream(f"[WebSocket连接异常] {e}")
            
            # 指数退避重连策略
            delay = min(WEBSOCKET_RECONNECT_DELAY * (2 ** (websocket_reconnect_count - 1)), 300)
            print_stream(f"[{delay}秒后重连...]")
            await asyncio.sleep(delay)

# ===== Ollama服务管理 =====
def start_ollama_service(ollama_path: str = r"C:\Users\dell\AppData\Local\Programs\Ollama\ollama app.exe", timeout: int = 10) -> Dict:
    """启动 Ollama 服务"""
    global global_ollama_process
    
    if not os.path.exists(ollama_path):
        return {
            "status": "error",
            "message": f"Ollama可执行文件未找到: {ollama_path}"
        }
    
    try:
        global_ollama_process = subprocess.Popen(
            [ollama_path],
            shell=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get("http://localhost:11434/api/tags", timeout=2)
                if response.status_code == 200:
                    return {
                        "status": "success",
                        "message": "Ollama服务启动成功"
                    }
            except requests.exceptions.RequestException:
                time.sleep(1)
        
        return {
            "status": "error",
            "message": f"服务启动超时({timeout}秒)，请手动检查"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"服务启动失败: {str(e)}"
        }

# ===== 清理和主函数 =====
async def cleanup():
    """清理资源"""
    global global_ollama_process
    
    if global_ollama_process:
        try:
            global_ollama_process.terminate()
            print_stream("\n[已终止Ollama进程]")
        except Exception as e:
            print_stream(f"\n[终止Ollama进程失败: {e}")
    
    await save_memories()
    global_self_awareness.save_consciousness()
    await global_tool_generator.save_generated_tools()
    await global_decision_engine.save_autonomous_goals()
    
    # 保存自我意识状态
    global_self_awareness.save_consciousness()

async def main():
    """主函数 - 增强版支持完全自主决策"""
    print_stream(await chat_reply_func("随便写2句押韵的哲学诗句，禁止换行，直接一行输出即可"))
    print_stream("")
    print_stream("██╗   ██╗██████╗      ██████╗ ")
    print_stream("██║   ██║╚════██╗    ██╔═████╗")
    print_stream("██║   ██║ █████╔╝    ██║██╔██║")
    print_stream("╚██╗ ██╔╝ ╚═══██╗    ████╔╝██║")
    print_stream(" ╚████╔╝ ██████╔╝██╗ ╚██████╔╝")
    print_stream("  ╚═══╝  ╚═════╝ ╚═╝  ╚═════╝ ")
    print_stream("")
    global global_auth_info,global_friends_to_watch,global_groups_to_watch,restart_count
    
    while restart_count<MAX_RESTART_ATTEMPTS:
        try:
            # 初始化基础系统
            await load_memories()
            
            initial_auth=await get_auth_tokens("Nbot","a31415926535")
            if not initial_auth:
                print_stream("获取初始认证token失败，程序退出")
                return
            
            global_auth_info={"access_token":initial_auth["access_token"],"refresh_token":initial_auth["refresh_token"],"expiry_time":time.time()+initial_auth["access_token_expires"]}
            print_stream(f"[Token已更新]")

            token_update_task=asyncio.create_task(update_token_periodically("Nbot","a31415926535"))
     
            refresh_task=asyncio.create_task(periodic_refresh())
     
            my_id=48132
            
            # 启动WebSocket监听器
            print_stream("\n[ 启动WebSocket监听器]")
            websocket_task=asyncio.create_task(websocket_listener(my_id))
            
            # 启动定时任务
            asyncio.create_task(clear_group_blacklist_periodically())
            
            # 运行主循环
            await asyncio.gather(
                token_update_task,
                refresh_task,
                websocket_task
            )
            
        except KeyboardInterrupt:
            print_stream("\n用户终止程序，退出...")
            break
            
        except Exception as e:
            restart_count+=1
            print_stream(f"\n[主程序异常] {e}")
            traceback.print_exc()
            if restart_count<MAX_RESTART_ATTEMPTS:
                print_stream(f"\n[将在{RESTART_DELAY}秒后重启程序] 尝试次数: {restart_count}/{MAX_RESTART_ATTEMPTS}")
                await asyncio.sleep(RESTART_DELAY)
            else:
                print_stream("\n[达到最大重启次数，程序将退出]")
        finally:
            await cleanup()
    
    if restart_count<MAX_RESTART_ATTEMPTS:
        print_stream("\n[准备重启程序...]")
    else:
        print_stream("\n[ 智能体系统终止]")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print_stream("\n程序已终止")
