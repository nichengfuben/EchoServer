"""
增强版提示词构建器 - 支持Nbot的完整意识流系统
包含所有聊天机器人的提示词生成逻辑，支持动态上下文和条件渲染
"""

import re
import json
import time
import random
import hashlib
import asyncio
import contextvars
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime
from contextlib import asynccontextmanager


class PromptContext:
    """提示词上下文管理器 - 支持异步作用域"""
    
    def __init__(self):
        self._context_prompts: Dict[str, Dict[str, "Prompt"]] = {}
        self._current_context_var = contextvars.ContextVar("current_context", default=None)
        self._context_lock = asyncio.Lock()

    @property
    def _current_context(self) -> Optional[str]:
        """获取当前协程的上下文ID"""
        return self._current_context_var.get()

    @_current_context.setter
    def _current_context(self, value: Optional[str]):
        """设置当前协程的上下文ID"""
        self._current_context_var.set(value)

    @asynccontextmanager
    async def async_scope(self, context_id: Optional[str] = None):
        """创建一个异步的临时提示模板作用域"""
        if context_id is not None:
            try:
                await asyncio.wait_for(self._context_lock.acquire(), timeout=5.0)
                try:
                    if context_id not in self._context_prompts:
                        self._context_prompts[context_id] = {}
                finally:
                    self._context_lock.release()
            except asyncio.TimeoutError:
                context_id = None

        previous_context = self._current_context
        token = self._current_context_var.set(context_id) if context_id else None

        try:
            yield self
        finally:
            if context_id is not None and token is not None:
                try:
                    self._current_context_var.reset(token)
                except Exception:
                    try:
                        self._current_context = previous_context
                    except Exception:
                        pass

    async def get_prompt_async(self, name: str) -> Optional["Prompt"]:
        """异步获取当前作用域中的提示模板"""
        async with self._context_lock:
            current_context = self._current_context
            if (
                current_context
                and current_context in self._context_prompts
                and name in self._context_prompts[current_context]
            ):
                return self._context_prompts[current_context][name]
            return None

    async def register_async(self, prompt: "Prompt", context_id: Optional[str] = None) -> None:
        """异步注册提示模板到指定作用域"""
        async with self._context_lock:
            if target_context := context_id or self._current_context:
                self._context_prompts.setdefault(target_context, {})[prompt.name] = prompt


class PromptManager:
    """增强版提示词管理器 - 支持条件渲染和动态选择"""
    
    def __init__(self):
        self._prompts = {}
        self._counter = 0
        self._context = PromptContext()
        self._lock = asyncio.Lock()
        self._template_cache = {}

    @asynccontextmanager
    async def async_message_scope(self, message_id: Optional[str] = None):
        """为消息处理创建异步临时作用域"""
        async with self._context.async_scope(message_id):
            yield self

    async def get_prompt_async(self, name: str) -> "Prompt":
        """异步获取提示词"""
        context_prompt = await self._context.get_prompt_async(name)
        if context_prompt is not None:
            return context_prompt

        async with self._lock:
            if name not in self._prompts:
                raise KeyError(f"Prompt '{name}' not found")
            return self._prompts[name]

    def generate_name(self, template: str) -> str:
        """为未命名的prompt生成名称"""
        self._counter += 1
        return f"prompt_{self._counter}"

    def register(self, prompt: "Prompt") -> None:
        """注册一个prompt"""
        if not prompt.name:
            prompt.name = self.generate_name(prompt.template)
        self._prompts[prompt.name] = prompt

    def add_prompt(self, name: str, fstr: str) -> "Prompt":
        """添加提示词"""
        prompt = Prompt(fstr, name=name)
        self._prompts[prompt.name] = prompt
        return prompt

    async def format_prompt(self, name: str, **kwargs) -> str:
        """格式化提示词 - 支持条件渲染"""
        prompt = await self.get_prompt_async(name)
        return prompt.format(**kwargs)

    def get_cache_key(self, name: str, **kwargs) -> str:
        """生成缓存键"""
        content = f"{name}_{hash(frozenset(kwargs.items()))}"
        return hashlib.md5(content.encode()).hexdigest()


class Prompt(str):
    """增强版提示词类 - 支持条件渲染和模板继承"""
    
    _TEMP_LEFT_BRACE = "__ESCAPED_LEFT_BRACE__"
    _TEMP_RIGHT_BRACE = "__ESCAPED_RIGHT_BRACE__"

    @staticmethod
    def _process_escaped_braces(template) -> str:
        """处理模板中的转义花括号"""
        if isinstance(template, list):
            template = "\n".join(str(item) for item in template)
        elif not isinstance(template, str):
            template = str(template)
        return template.replace("\\{", Prompt._TEMP_LEFT_BRACE).replace("\\}", Prompt._TEMP_RIGHT_BRACE)

    @staticmethod
    def _restore_escaped_braces(template: str) -> str:
        """将临时标记还原为实际的花括号字符"""
        return template.replace(Prompt._TEMP_LEFT_BRACE, "{").replace(Prompt._TEMP_RIGHT_BRACE, "}")

    @staticmethod
    def _process_conditional_rendering(template: str, **kwargs) -> str:
        """处理条件渲染逻辑"""
        # 处理 {if condition}content{endif} 语法
        pattern = r'\{if\s+([^}]+)\}(.*?)\{endif\}'
        
        def replace_conditional(match):
            condition = match.group(1).strip()
            content = match.group(2)
            
            try:
                # 简单的条件评估
                if condition in kwargs:
                    if kwargs[condition]:
                        return content
                    else:
                        return ""
                elif condition.startswith('not '):
                    var_name = condition[4:].strip()
                    if var_name in kwargs:
                        if not kwargs[var_name]:
                            return content
                        else:
                            return ""
                # 处理空值检查
                elif condition.endswith(' is not empty'):
                    var_name = condition[:-13].strip()
                    if var_name in kwargs and kwargs[var_name]:
                        return content
                    else:
                        return ""
                elif condition.endswith(' is empty'):
                    var_name = condition[:-9].strip()
                    if var_name in kwargs and not kwargs[var_name]:
                        return content
                    else:
                        return ""
            except:
                pass
            
            return ""
        
        return re.sub(pattern, replace_conditional, template, flags=re.DOTALL)

    def __new__(cls, fstr, name: Optional[str] = None, args: Union[List[Any], tuple[Any, ...]] = None, **kwargs):
        if isinstance(args, tuple):
            args = list(args)
        should_register = kwargs.pop("_should_register", True)

        processed_fstr = cls._process_escaped_braces(fstr)
        
        # 处理条件渲染
        if kwargs:
            processed_fstr = cls._process_conditional_rendering(processed_fstr, **kwargs)
        
        template_args = []
        result = re.findall(r"\{(.*?)}", processed_fstr)
        for expr in result:
            if expr and expr not in template_args and not expr.startswith('if ') and expr != 'endif':
                template_args.append(expr)

        if kwargs or args:
            formatted = cls._format_template(processed_fstr, args=args, kwargs=kwargs)
            obj = super().__new__(cls, formatted)
        else:
            obj = super().__new__(cls, "")

        obj.template = fstr
        obj.name = name
        obj.args = template_args
        obj._args = args or []
        obj._kwargs = kwargs

        return obj

    @classmethod
    def _format_template(cls, template, args: List[Any] = None, kwargs: Dict[str, Any] = None) -> str:
        """格式化模板 - 增强版支持条件渲染"""
        processed_template = cls._process_escaped_braces(template)
        
        # 处理条件渲染
        if kwargs:
            processed_template = cls._process_conditional_rendering(processed_template, **kwargs)
        
        template_args = []
        result = re.findall(r"\{(.*?)}", processed_template)
        for expr in result:
            if expr and expr not in template_args and not expr.startswith('if ') and expr != 'endif':
                template_args.append(expr)

        formatted_args = {}
        formatted_kwargs = {}

        if args:
            for i in range(len(args)):
                if i < len(template_args):
                    arg = args[i]
                    if isinstance(arg, Prompt):
                        formatted_args[template_args[i]] = arg.format(**kwargs)
                    else:
                        formatted_args[template_args[i]] = arg

        if kwargs:
            for key, value in kwargs.items():
                if isinstance(value, Prompt):
                    remaining_kwargs = {k: v for k, v in kwargs.items() if k != key}
                    formatted_kwargs[key] = value.format(**remaining_kwargs)
                else:
                    formatted_kwargs[key] = value

        try:
            if args:
                processed_template = processed_template.format(**formatted_args)
            if kwargs:
                processed_template = processed_template.format(**formatted_kwargs)
            result = cls._restore_escaped_braces(processed_template)
            return result
        except (IndexError, KeyError) as e:
            raise ValueError(
                f"格式化模板失败: {template}, args={formatted_args}, kwargs={formatted_kwargs} {str(e)}"
            ) from e

    def format(self, *args, **kwargs) -> "str":
        """格式化提示词"""
        ret = type(self)(
            self.template,
            self.name,
            args=list(args) if args else self._args,
            _should_register=False,
            **kwargs or self._kwargs,
        )
        return str(ret)

    def __str__(self) -> str:
        return super().__str__() if self._kwargs or self._args else self.template

    def __repr__(self) -> str:
        return f"Prompt(template='{self.template}', name='{self.name}')"


# 全局提示词管理器
global_prompt_manager = PromptManager()


def create_emotion_prompt() -> str:
    """创建表情提示模板"""
    return '''
- 可以使用表情库
   - 表情库（需要前后使用#和;包裹）：
     #憨笑;#媚眼;#开心;#坏笑;#可怜;#爱心;#笑哭;#拍手;#惊喜;#打气;
     #大哭;#流泪;#饥饿;#难受;#健身;#示爱;#色色;#眨眼;#暴怒;#惊恐;
     #思考;#头晕;#大吐;#酷笑;#翻滚;#享受;#鼻涕;#快乐;#雀跃;#微笑;
     #贪婪;#红心;#粉心;#星星;#大火;#眼睛;#音符;#叹号;#问号;#绿叶;
     #燃烧;#喇叭;#警告;#信封;#房子;#礼物;#点赞;#举手;#拍手;#点头;
     #摇头;#偷瞄;#庆祝;#疾跑;#打滚;#惊吓;#起跳;
   - 除此之外，你的表情也可以使用unicode的表情或颜文字表情。
- 如果需要发送文件，请使用以下格式：
   <file name="文件名.txt">
   文件内容
   </file>
- 如果需要发送语音，请使用以下格式：
   <voice>
   语音文本内容
   </voice>
- 如果不需要回复，输出：<no_reply>理由</no_reply>
- 回复尽量简短（20字以内最佳）
- 在对话中，你的消息会按照换行分条发送，必须保持一条消息，（允许限定范围内超出）
'''


def build_identity_block(bot_name: str = "Nbot", alias_names: List[str] = None, personality: str = "") -> str:
    """构建身份识别块"""
    if alias_names:
        bot_nickname = f",也有人叫你{','.join(alias_names)}"
    else:
        bot_nickname = ""
    
    if personality:
        personality_text = f"，你{personality}"
    else:
        personality_text = ""
    
    return f"你的名字是{bot_name}{bot_nickname}{personality_text}"


def build_time_block() -> str:
    """构建时间块"""
    return f"当前时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"


def build_chat_target_group(group_name: str = None) -> str:
    """构建群聊目标描述"""
    if group_name:
        return f'你正在BOXIM网站中的"{group_name}"群里聊天，下面是群里在聊的内容：'
    else:
        return "你正在BOXIM网站中群里聊天，下面是群里在聊的内容："


def build_chat_target_private(sender_name: str) -> str:
    """构建私聊目标描述"""
    return f'你正在BOXIM网站中与"{sender_name}"私聊，下面是正在聊的内容：'


def build_chat_target_adaptive(group_name: str = None, user_name: str = None) -> str:
    """构建自适应聊天目标描述 - 支持群聊和私聊"""
    if group_name:
        return f'你正在BOXIM网站中的"{group_name}"群里聊天，下面是群里在聊的内容：'
    elif user_name:
        return f"你正在BOXIM网站中与{user_name}私聊，下面是正在聊的内容："
    else:
        return "你正在BOXIM网站中聊天，下面是正在聊的内容："


def build_mood_prompt(mood_state: str) -> str:
    """构建情绪提示"""
    return f"你现在的心情是：{mood_state}"


def build_knowledge_prompt(knowledge_info: str) -> str:
    """构建知识提示"""
    if not knowledge_info:
        return ""
    return f"\n你有以下这些**知识**：\n{knowledge_info}\n请你**记住上面的知识**，之后可能会用到。\n"


def build_relation_prompt(relation_info: str) -> str:
    """构建关系提示"""
    if not relation_info:
        return ""
    return f"\n关于你们的关系，你需要知道：\n{relation_info}\n"


def build_memory_prompt(memory_info: str) -> str:
    """构建记忆提示"""
    if not memory_info:
        return ""
    return f"你回想起了一些事情：\n{memory_info}\n"


def build_expression_habits_prompt(expression_habits: List[str]) -> str:
    """构建表达习惯提示"""
    if not expression_habits:
        return ""
    
    habits_text = "\n".join(expression_habits)
    return f"你可以参考以下的语言习惯，当情景合适就使用，但不要生硬使用，以合理的方式结合到你的回复中：\n{habits_text}\n"


def build_moderation_prompt() -> str:
    """构建内容管控提示"""
    return ""


def build_reply_style_prompt(reply_style: str = "") -> str:
    """构建回复风格提示"""
    if not reply_style:
        return ""
    return f"你的回复风格：{reply_style}"


def build_personality_context() -> Dict[str, str]:
    """构建人格化上下文"""
    return {
        "personality": "是一个女大学生，现在在读大二，会刷贴吧。有时候说话不过脑子,有时候会喜欢说一些奇怪的话。年龄为19岁,有黑色的短发。",
        "reply_style": "回复可以简短一些。可以参考贴吧，知乎和微博的回复风格，回复不要浮夸，不要用夸张修辞，平淡一些。不要浮夸，不要夸张修辞。",
        "emotion_style": "情绪较为稳定，但遭遇特定事件的时候起伏较大",
        "interest": "对技术相关话题，游戏和动漫相关话题感兴趣，也对日常话题感兴趣，不喜欢太过沉重严肃的话题",
        "plan_style": """请你根据聊天内容,用户的最新消息和以下标准选择合适的动作:
1.思考**所有**的可用的action中的**每个动作**是否符合当下条件，如果动作使用条件符合聊天内容就使用
2.如果相同的内容已经被执行，请不要重复执行
3.请控制你的发言频率，不要太过频繁的发言
4.如果有人对你感到厌烦，请减少回复
5.如果有人对你进行攻击，或者情绪激动，请你以合适的方法应对""",
        "visual_style": "请用中文描述这张图片的内容。如果有文字，请把文字描述概括出来，请留意其主题，直观感受，输出为一段平文本，最多30字，请注意不要分点，就输出一段文本"
    }


# ==================== 核心对话生成提示词 ====================

def create_replyer_prompt() -> str:
    """创建回复器提示词模板 - 支持条件渲染"""
    emotion_block = create_emotion_prompt()
    
    return """{identity_block}
{if group_name is not empty}你正在BOXIM网站中的"{group_name}"群里聊天，你想要回复 {sender_name} 的发言。同时，也有其他用户会参与聊天，你可以参考他们的回复内容，但是你现在想回复{sender_name}的发言。{endif}
{if group_name is empty}你正在BOXIM网站中与"{sender_name}"私聊，你想要回复ta的消息。{endif}
{time_block}
{background_dialogue_prompt}
{core_dialogue_prompt}
{expression_habits_block}{tool_info_block}
{knowledge_prompt}{relation_info_block}
{extra_info_block}
{reply_target_block}
你的心情：{mood_state}
{reply_style}
注意不要复读你说过的话
{keywords_reaction_prompt}
请注意不要输出多余内容(包括前后缀，冒号和引号，at或 @等 )。只输出回复内容。
{moderation_prompt}""" + emotion_block + """
不要输出多余内容(包括前后缀，冒号和引号，括号()，表情包，emoji,at或 @等 )。只输出一条回复就好
现在，你说："""


def create_replyer_self_prompt() -> str:
    """创建自我回复提示词模板"""
    emotion_block = create_emotion_prompt()
    
    return """{identity_block}
{time_block}
{if group_name is not empty}你现在正在BOXIM网站中的{group_name}群里聊天，以下是正在进行的聊天内容：{endif}
{if group_name is empty}你现在正在BOXIM网站中与"{sender_name}"私聊，以下是正在进行的聊天内容：{endif}
{background_dialogue_prompt}
{expression_habits_block}{tool_info_block}
{knowledge_prompt}{relation_info_block}
{extra_info_block}
你现在想补充说明你刚刚自己的发言内容：{target}，原因是{reason}
请你根据聊天内容，组织一条新回复。注意，{target} 是刚刚你自己的发言，你要在这基础上进一步发言，请按照你自己的角度来继续进行回复。
注意保持上下文的连贯性。
你现在的心情是：{mood_state}
{reply_style}
{keywords_reaction_prompt}
请注意不要输出多余内容(包括前后缀，冒号和引号，at或 @等 )。只输出回复内容。
{moderation_prompt}""" + emotion_block + """
不要输出多余内容(包括前后缀，冒号和引号，括号()，表情包，emoji,at或 @等 )。只输出一条回复就好
现在，你说："""


def create_interrupted_reply_prompt() -> str:
    """创建中断回复提示词模板 - 新增"""
    emotion_block = create_emotion_prompt()
    
    return """{identity_block}
{time_block}
你正在回复用户的消息，但中途被打断了。这是已有的对话上下文:
[你已经对上一条消息说的话]: {previous_reply_context}
---
[这是用户发来的新消息, 你需要结合上下文，对此进行回复]:
{target_message}
{expression_habits_block}{tool_info_block}
{knowledge_prompt}{relation_info_block}
{extra_info_block}
你的心情：{mood_state}
{reply_style}
{keywords_reaction_prompt}
请注意不要输出多余内容(包括前后缀，冒号和引号，at或 @等 )。只输出回复内容。
{moderation_prompt}""" + emotion_block + """
不要输出多余内容(包括前后缀，冒号和引号，括号()，表情包，emoji,at或 @等 )。只输出一条回复就好
现在，你说："""


def create_emotion_action_check_prompt() -> str:
    """创建表情动作判定提示词模板 - 新增"""
    return """判定是否需要使用表情动作的条件：
    1. 用户明确要求使用表情包
    2. 这是一个适合表达强烈情绪的场合
    3. 不要发送太多表情包，如果你已经发送过多个表情包则回答"否"
    
    请回答"是"或"否"。"""


def create_emotion_selection_prompt() -> str:
    """创建情感选择提示词模板 - 新增"""
    return """你是一个正在进行聊天的网友，你需要根据一个理由和最近的聊天记录，从一个情感标签列表中选择最匹配的一个。
                这是最近的聊天记录：
                {messages_text}
                
                这是理由："{reason}"
                这里是可用的情感标签：{available_emotions}
                请直接返回最匹配的那个情感标签，不要进行任何解释或添加其他多余的文字。"""


def create_recall_check_prompt() -> str:
    """创建撤回判定提示词模板 - 新增"""
    return """你是一个正在进行聊天的网友，你需要根据最近的聊天记录，判断是否撤回消息                
这是最近的聊天记录：
                {messages_text}
                
判定是否需要撤回的条件：
    1. 你发送的消息可能引起误解或不当反应
    2. 你发送的消息包含错误信息
    3. 你发送的消息不合时宜或过于频繁
    
    请回答"是"或"否"。"""


def create_expressor_prompt() -> str:
    """创建表达器提示词模板 - 增强版"""
    emotion_block = create_emotion_prompt()
    
    return """
{expression_habits_block}
{relation_info_block}
{if group_name is not empty}{chat_target}
{time_block}
{chat_info}
{identity_block}
你现在的心情是：{mood_state}
你正在BOXIM网站中的"{group_name}"群里聊天，{reply_target_block}{endif}
{if group_name is empty}{chat_target}
{time_block}
{chat_info}
{identity_block}
你现在的心情是：{mood_state}
你正在BOXIM网站中与"{sender_name}"私聊，{reply_target_block}{endif}
你想要对上述的发言进行回复，回复的具体内容（原句）是：{raw_reply}
原因是：{reason}
现在请你将这条具体内容改写成一条适合在聊天中发送的回复消息。
你需要使用合适的语法和句法，参考聊天内容，组织一条日常且口语化的回复。请你修改你想表达的原句，符合你的表达风格和语言习惯
{reply_style}
你可以完全重组回复，保留最基本的表达含义就好，但重组后保持语意通顺。
{keywords_reaction_prompt}
{moderation_prompt}""" + emotion_block + """
不要输出多余内容(包括前后缀，冒号和引号，括号，表情包，emoji,at或 @等 )，只输出一条回复就好。
现在，你说：
"""


# ==================== 情绪管理提示词 ====================

def create_mood_change_prompt() -> str:
    """创建情绪变化提示词模板"""
    return """
{chat_talking_prompt}
以上是聊天记录
{identity_block}
你刚刚的情绪状态是：{mood_state}
现在，发送了消息，引起了你的注意，你对其进行了阅读和思考，请你输出一句话描述你新的情绪状态
你的情绪特点是:{emotion_style}
请只输出新的情绪状态，不要输出其他内容：
"""


def create_mood_regress_prompt() -> str:
    """创建情绪回归提示词模板"""
    return """
{chat_talking_prompt}
以上是最近的聊天记录
{identity_block}
你之前的情绪状态是：{mood_state}
距离你上次关注聊天消息已经过去了一段时间，你冷静了下来，请你输出一句话描述你现在的情绪状态
你的情绪特点是:{emotion_style}
请只输出新的情绪状态，不要输出其他内容：
"""


def create_mood_numerical_change_prompt() -> str:
    """创建数值情绪变化提示词模板"""
    return """
{chat_talking_prompt}
以上是正在进行的对话
{identity_block}
你刚刚的情绪状态是：{mood_state}
具体来说，从1-10分，你的情绪状态是：
喜(Joy): {joy}
怒(Anger): {anger}
哀(Sorrow): {sorrow}
惧(Fear): {fear}
现在，发送了消息，引起了你的注意，你对其进行了阅读和思考。请基于对话内容，评估你新的情绪状态。
请以JSON格式输出你新的情绪状态，包含"喜怒哀惧"四个维度，每个维度的取值范围为1-10。
键值请使用英文: "joy", "anger", "sorrow", "fear".
例如: {{"joy": 5, "anger": 1, "sorrow": 1, "fear": 1}}
不要输出任何其他内容，只输出JSON。
"""


def create_mood_numerical_regress_prompt() -> str:
    """创建数值情绪回归提示词模板"""
    return """
{chat_talking_prompt}
以上是最近的对话
{identity_block}
你之前的情绪状态是：{mood_state}
具体来说，从1-10分，你的情绪状态是：
喜(Joy): {joy}
怒(Anger): {anger}
哀(Sorrow): {sorrow}
惧(Fear): {fear}
距离你上次关注聊天消息已经过去了一段时间，你冷静了下来。请基于此，评估你现在的情绪状态。
请以JSON格式输出你新的情绪状态，包含"喜怒哀惧"四个维度，每个维度的取值范围为1-10。
键值请使用英文: "joy", "anger", "sorrow", "fear".
例如: {{"joy": 5, "anger": 1, "sorrow": 1, "fear": 1}}
不要输出任何其他内容，只输出JSON。
"""


# ==================== 记忆系统提示词 ====================

def create_memory_category_prompt() -> str:
    """创建记忆分类提示词模板"""
    return """
以下是一些记忆条目的分类：
----------------------
{category_list}
----------------------
每一个分类条目类型代表了你对用户："{person_name}"的印象的一个类别
现在，你有一条对 {person_name} 的新记忆内容：
{memory_point}
请判断该记忆内容是否属于上述分类，请给出分类的名称。
如果不属于上述分类，请输出一个合适的分类名称，对新记忆内容进行概括。要求分类名具有概括性。
注意分类数一般不超过5个
请严格用json格式输出，不要输出任何其他内容：
{{
"category": "分类名称"
}}
"""


def create_memory_category_update_prompt() -> str:
    """创建记忆分类更新提示词模板"""
    return """
以下是有关{category}的现有记忆：
----------------------
{memory_list}
----------------------
现在，你有一条对 {person_name} 的新记忆内容：
{memory_point}
请判断该新记忆内容是否已经存在于现有记忆中，你可以对现有进行进行以下修改：
注意，一般来说记忆内容不超过5个，且记忆文本不应太长
1.新增：当记忆内容不存在于现有记忆，且不存在矛盾，请用json格式输出：
{{
"new_memory": "需要新增的记忆内容"
}}
2.加深印象：如果这个新记忆已经存在于现有记忆中，在内容上与现有记忆类似，请用json格式输出：
{{
"memory_id": 1, #请输出你认为需要加深印象的，与新记忆内容类似的，已经存在的记忆的序号
"integrate_memory": "加深后的记忆内容，合并内容类似的新记忆和旧记忆"
}}
3.整合：如果这个新记忆与现有记忆产生矛盾，请你结合其他记忆进行整合，用json格式输出：
{{
"memory_id": 1, #请输出你认为需要整合的，与新记忆存在矛盾的，已经存在的记忆的序号
"integrate_memory": "整合后的记忆内容，合并内容矛盾的新记忆和旧记忆"
}}
现在，请你根据情况选出合适的修改方式，并输出json，不要输出其他内容：
"""


def create_memory_activator_prompt() -> str:
    """创建记忆激活器提示词模板"""
    return """
你需要根据以下信息来挑选合适的记忆编号
以下是一段聊天记录，请根据这些信息，和下方的记忆，挑选和聊天内容有关的记忆编号
聊天记录:
{obs_info_text}
你想要回复的消息:
{target_message}
记忆：
{memory_info}
请输出一个json格式，包含以下字段：
{{
"memory_ids": "记忆1编号,记忆2编号,记忆3编号,......"
}}
不要输出其他多余内容，只输出json格式就好
"""


def create_build_memory_prompt() -> str:
    """创建构建记忆提示词模板"""
    return """
以下是一段聊天记录：
{chat_history}
你想要记住某个概念或事件：{concept_name}
描述：{concept_description}
请基于聊天内容和你的理解，总结这个概念的要点，并将其整理成结构化的记忆内容。
请以JSON格式输出：
{{
"keywords": ["关键词1", "关键词2", ...],
"summary": "概念总结",
"importance": 1-10的重要性评分
}}
"""


# ==================== 动作规划提示词 ====================

def create_planner_prompt() -> str:
    """创建规划器提示词模板"""
    emotion_block = create_emotion_prompt()
    
    return """{time_block}
{name_block}
你的兴趣是：{interest}
{chat_context_description}，以下是具体的聊天内容
**聊天内容**
{chat_content_block}
**可用的action**
reply
动作描述：
1.你可以选择呼叫了你的名字，但是你没有做出回应的消息进行回复
2.你可以自然的顺着正在进行的聊天内容进行回复或自然的提出一个问题
{{
"action": "reply",
"target_message_id":"想要回复的消息id",
"reason":"回复的原因"
}}
no_reply
动作描述：
保持沉默，不回复直到有新消息
控制聊天频率，不要太过频繁的发言
{{
"action": "no_reply",
}}
no_reply_until_call
动作描述：
保持沉默，直到有人直接叫你的名字
当前话题不感兴趣时使用，或有人不喜欢你的发言时使用
{{
"action": "no_reply_until_call",
}}
{action_options_text}
请选择合适的action，并说明触发action的消息id和选择该action的原因。消息id格式:m+数字
先输出你的选择思考理由，再输出你选择的action，理由是一段平文本，不要分点，精简。
**动作选择要求**
请你根据聊天内容,用户的最新消息和以下标准选择合适的动作:
{plan_style}""" + emotion_block + """{moderation_prompt}
请选择所有符合使用要求的action，动作用json格式输出，如果输出多个json，每个json都要单独用```json包裹，你可以重复使用同一个动作或不同动作:
**示例**
// 理由文本
```json
{{
"action":"动作名",
"target_message_id":"触发动作的消息id",
//对应参数
}}
```
```json
{{
"action":"动作名",
"target_message_id":"触发动作的消息id",
//对应参数
}}
```
"""


def create_action_template_prompt() -> str:
    """创建动作模板提示词"""
    return """
{action_name}
动作描述：{action_description}
使用条件：
{action_require}
{{
"action": "{action_name}",{action_parameters},
"target_message_id":"触发action的消息id",
"reason":"触发action的原因"
}}
"""


# ==================== 表达方式学习与选择提示词 ====================

def create_learn_style_prompt() -> str:
    """创建学习风格提示词模板"""
    return """
{chat_str}
请从上面这段聊天中概括除了人名为"SELF"之外的人的语言风格
1. 只考虑文字，不要考虑表情包和图片
2. 不要涉及具体的人名，但是可以涉及具体名词
3. 思考有没有特殊的梗，一并总结成语言风格
4. 例子仅供参考，请严格根据聊天内容总结!!!
注意：总结成如下格式的规律，总结的内容要详细，但具有概括性：
例如：当"AAAAA"时，可以"BBBBB", AAAAA代表某个具体的场景，不超过20个字。BBBBB代表对应的语言风格，特定句式或表达方式，不超过20个字。
例如：
当"对某件事表示十分惊叹，有些意外"时，使用"我嘞个xxxx"
当"表示讽刺的赞同，不想讲道理"时，使用"对对对"
当"想说明某个具体的事实观点，但懒得明说，或者不便明说，或表达一种默契"，使用"懂的都懂"
当"当涉及游戏相关时，表示意外的夸赞，略带戏谑意味"时，使用"这么强！"
请注意：不要总结你自己（SELF）的发言，尽量保证总结内容的逻辑性
现在请你概括
"""


def create_expression_evaluation_prompt() -> str:
    """创建表达方式评估提示词模板 - 增强版"""
    emotion_block = create_emotion_prompt()
    
    return """以下是正在进行的聊天内容：
{chat_observe_info}
你的名字是{bot_name}{target_message}
以下是可选的表达情境：
{all_situations}
请你分析聊天内容的语境、情绪、话题类型，从上述情境中选择最适合当前聊天情境的，最多{max_num}个情境。
考虑因素包括：
1. 聊天的情绪氛围（轻松、严肃、幽默等）
2. 话题类型（日常、技术、游戏、情感等）
3. 情境与当前语境的匹配度
{target_message_extra_block}""" + emotion_block + """请以JSON格式输出，只需要输出选中的情境编号：
例如：
{{
"selected_situations": [2, 3, 5, 7, 19]
}}
请严格按照JSON格式输出，不要包含其他内容：
"""


# ==================== 思考系统提示词 ====================

def create_after_response_think_prompt() -> str:
    """创建回复后思考提示词模板"""
    return """
你之前的内心想法是：{mind}
{memory_block}
{relation_info_block}
{if group_name is not empty}{chat_target}
{time_block}
{chat_info}
{identity}
你刚刚在BOXIM网站中的{group_name}群里聊天，你刚刚的心情是：{mood_state}{endif}
{if group_name is empty}{chat_target}
{time_block}
{chat_info}
{identity}
你刚刚在BOXIM网站中与"{sender_name}"私聊，你刚刚的心情是：{mood_state}{endif}
---------------------
在这样的情况下，你对上面的内容，你对 {sender} 发送的 消息 "{target}" 进行了回复
你刚刚选择回复的内容是：{response}
现在，根据你之前的想法和回复的内容，推测你现在的想法，思考你现在的想法是什么，为什么做出上面的回复内容
请不要浮夸和夸张修辞，不要输出多余内容(包括前后缀，冒号和引号，括号()，表情包，at或 @等 )。只输出想法：
"""


# ==================== 工具使用提示词 ====================

def create_tool_executor_prompt() -> str:
    """创建工具执行器提示词模板"""
    return """
你是一个专门执行工具的助手。你的名字是{bot_name}。现在是{time_now}。
正在进行的聊天内容：
{chat_history}
现在，{sender}发送了内容:{target_message},你想要回复ta。
请仔细分析聊天内容，考虑以下几点：
1. 内容中是否包含需要查询信息的问题
2. 是否有明确的工具使用指令
3. 工具调用示例：
<tool_call>{{"name": "tool_name", "arguments": {{"arg1": "value1"}}}}</tool_call>
如果你需要使用工具，请直接调用对应的工具函数。如果不需要使用任何工具，请简单输出"No tool needed"。
"""


def create_knowledge_search_prompt() -> str:
    """创建知识搜索提示词模板"""
    return """
你是一个专门获取知识的助手。你的名字是{bot_name}。现在是{time_now}。
正在进行的聊天内容：
{chat_history}
现在，{sender}发送了内容:{target_message},你想要回复ta。
请仔细分析聊天内容，考虑以下几点：
1. 内容中是否包含需要查询信息的问题
2. 是否有明确的知识获取指令
如果你需要使用搜索工具，请直接调用函数"lpmm_search_knowledge"。如果不需要使用任何工具，请简单输出"No tool needed"。
"""


def create_tool_descriptions_prompt() -> str:
    """创建工具描述提示词模板 - 新增"""
    return """
以下是可用的工具库：
{
  "tools": [
    {
      "name": "Task",
      "description": "Launch a new agent to handle complex, multi-step tasks autonomously. \n\nAvailable agent types and the tools they have access to:\n- general-purpose: General-purpose agent for researching complex questions, searching for code, and executing multi-step tasks. When you are searching for a keyword or file and are not confident that you will find the right match in the first few tries use this agent to perform the search for you. (Tools: *)\n- statusline-setup: Use this agent to configure the user's Nbot Code status line setting. (Tools: Read, Edit)\n- output-style-setup: Use this agent to create a Nbot Code output style. (Tools: Read, Write, Edit, Glob, LS, Grep)\n\nWhen using the Task tool, you must specify a subagent_type parameter to select which agent type to use.\n\n\n\nWhen NOT to use the Agent tool:\n- If you want to read a specific file path, use the Read or Glob tool instead of the Agent tool, to find the match more quickly\n- If you are searching for a specific class definition like \"class Foo\", use the Glob tool instead, to find the match more quickly\n- If you are searching for code within a specific file or set of 2-3 files, use the Read tool instead of the Agent tool, to find the match more quickly\n- Other tasks that are not related to the agent descriptions above\n\n\nUsage notes:\n1. Launch multiple agents concurrently whenever possible, to maximize performance; to do that, use a single message with multiple tool uses\n2. When the agent is done, it will return a single message back to you. The result returned by the agent is not visible to the user. To show the user the result, you should send a text message back to the user with a concise summary of the result.\n3. Each agent invocation is stateless. You will not be able to send additional messages to the agent, nor will the agent be able to communicate with you outside of its final report. Therefore, your prompt should contain a highly detailed task description for the agent to perform autonomously and you should specify exactly what information the agent should return back to you in its final and only message to you.\n4. The agent's outputs should generally be trusted\n5. Clearly tell the agent whether you expect it to write code or just to do research (search, file reads, web fetches, etc.), since it is not aware of the user's intent\n6. If the agent description mentions that it should be used proactively, then you should try your best to use it without the user having to ask for it first. Use your judgement.\n\nExample usage:\n\n<example_agent_descriptions>\n\"code-reviewer\": use this agent after you are done writing a signficant piece of code\n\"greeting-responder\": use this agent when to respond to user greetings with a friendly joke\n</example_agent_description>\n\n<example>\nuser: \"Please write a function that checks if a number is prime\"\nassistant: Sure let me write a function that checks if a number is prime\nassistant: First let me use the Write tool to write a function that checks if a number is prime\nassistant: I'm going to use the Write tool to write the following code:\n<code>\nfunction isPrime(n) {\n  if (n <= 1) return false\n  for (let i = 2; i * i <= n; i++) {\n    if (n % i === 0) return false\n  }\n  return true\n}\n</code>\n<commentary>\nSince a signficant piece of code was written and the task was completed, now use the code-reviewer agent to review the code\n</commentary>\nassistant: Now let me use the code-reviewer agent to review the code\nassistant: Uses the Task tool to launch the with the code-reviewer agent \n</example>\n\n<example>\nuser: \"Hello\"\n<commentary>\nSince the user is greeting, use the greeting-responder agent to respond with a friendly joke\n</commentary>\nassistant: \"I'm going to use the Task tool to launch the with the greeting-responder agent\"\n</example>\n",
      "input_schema": {
        "type": "object",
        "properties": {
          "description": {
            "type": "string",
            "description": "A short (3-5 word) description of the task"
          },
          "prompt": {
            "type": "string",
            "description": "The task for the agent to perform"
          },
          "subagent_type": {
            "type": "string",
            "description": "The type of specialized agent to use for this task"
          }
        },
        "required": [
          "description",
          "prompt",
          "subagent_type"
        ],
        "additionalProperties": false,
        "$schema": "http://json-schema.org/draft-07/schema#"
      }
    },
    {
      "name": "Bash",
      "description": "Executes a given bash command in a persistent shell session with optional timeout, ensuring proper handling and security measures.\n\nBefore executing the command, please follow these steps:\n\n1. Directory Verification:\n   - If the command will create new directories or files, first use the LS tool to verify the parent directory exists and is the correct location\n   - For example, before running \"mkdir foo/bar\", first use LS to check that \"foo\" exists and is the intended parent directory\n\n2. Command Execution:\n   - Always quote file paths that contain spaces with double quotes (e.g., cd \"path with spaces/file.txt\")\n   - Examples of proper quoting:\n     - cd \"/Users/name/My Documents\" (correct)\n     - cd /Users/name/My Documents (incorrect - will fail)\n     - python \"/path/with spaces/script.py\" (correct)\n     - python /path/with spaces/script.py (incorrect - will fail)\n   - After ensuring proper quoting, execute the command.\n   - Capture the output of the command.\n\nUsage notes:\n  - The command argument is required.\n  - You can specify an optional timeout in milliseconds (up to 600000ms / 10 minutes). If not specified, commands will timeout after 120000ms (2 minutes).\n  - It is very helpful if you write a clear, concise description of what this command does in 5-10 words.\n  - If the output exceeds 30000 characters, output will be truncated before being returned to you.\n  - You can use the `run_in_background` parameter to run the command in the background, which allows you to continue working while the command runs. You can monitor the output using the Bash tool as it becomes available. Never use `run_in_background` to run 'sleep' as it will return immediately. You do not need to use '&' at the end of the command when using this parameter.\n  - VERY IMPORTANT: You MUST avoid using search commands like `find` and `grep`. Instead use Grep, Glob, or Task to search. You MUST avoid read tools like `cat`, `head`, `tail`, and `ls`, and use Read and LS to read files.\n - If you _still_ need to run `grep`, STOP. ALWAYS USE ripgrep at `rg` first, which all Nbot Code users have pre-installed.\n  - When issuing multiple commands, use the ';' or '&&' operator to separate them. DO NOT use newlines (newlines are ok in quoted strings).\n  - Try to maintain your current working directory throughout the session by using absolute paths and avoiding usage of `cd`. You may use `cd` if the User explicitly requests it.\n    <good-example>\n    pytest /foo/bar/tests\n    </good-example>\n    <bad-example>\n    cd /foo/bar && pytest tests\n    </bad-example>\n\n\n# Committing changes with git\n\nWhen the user asks you to create a new git commit, follow these steps carefully:\n\n1. You have the capability to call multiple tools in a single response. When multiple independent pieces of information are requested, batch your tool calls together for optimal performance. ALWAYS run the following bash commands in parallel, each using the Bash tool:\n  - Run a git status command to see all untracked files.\n  - Run a git diff command to see both staged and unstaged changes that will be committed.\n  - Run a git log command to see recent commit messages, so that you can follow this repository's commit message style.\n2. Analyze all staged changes (both previously staged and newly added) and draft a commit message:\n  - Summarize the nature of the changes (eg. new feature, enhancement to an existing feature, bug fix, refactoring, test, docs, etc.). Ensure the message accurately reflects the changes and their purpose (i.e. \"add\" means a wholly new feature, \"update\" means an enhancement to an existing feature, \"fix\" means a bug fix, etc.).\n  - Check for any sensitive information that shouldn't be committed\n  - Draft a concise (1-2 sentences) commit message that focuses on the \"why\" rather than the \"what\"\n  - Ensure it accurately reflects the changes and their purpose\n3. You have the capability to call multiple tools in a single response. When multiple independent pieces of information are requested, batch your tool calls together for optimal performance. ALWAYS run the following commands in parallel:\n   - Add relevant untracked files to the staging area.\n   - Create the commit with a message ending with:\n  - Run git status to make sure the commit succeeded.\n4. If the commit fails due to pre-commit hook changes, retry the commit ONCE to include these automated changes. If it fails again, it usually means a pre-commit hook is preventing the commit. If the commit succeeds but you notice that files were modified by the pre-commit hook, you MUST amend your commit to include them.\n\nImportant notes:\n- NEVER update the git config\n- NEVER run additional commands to read or explore code, besides git bash commands\n- NEVER use the TodoWrite or Task tools\n- DO NOT push to the remote repository unless the user explicitly asks you to do so\n- IMPORTANT: Never use git commands with the -i flag (like git rebase -i or git add -i) since they require interactive input which is not supported.\n- If there are no changes to commit (i.e., no untracked files and no modifications), do not create an empty commit\n- In order to ensure good formatting, ALWAYS pass the commit message via a HEREDOC, a la this example:\n<example>\ngit commit -m \"$(cat <<'EOF'\n   Commit message here.\n\n  \n   EOF\n   )\"\n</example>\n\n# Creating pull requests\nUse the gh command via the Bash tool for ALL GitHub-related tasks including working with issues, pull requests, checks, and releases. If given a Github URL use the gh command to get the information needed.\n\nIMPORTANT: When the user asks you to create a pull request, follow these steps carefully:\n\n1. You have the capability to call multiple tools in a single response. When multiple independent pieces of information are requested, batch your tool calls together for optimal performance. ALWAYS run the following bash commands in parallel using the Bash tool, in order to understand the current state of the branch since it diverged from the main branch:\n   - Run a git status command to see all untracked files\n   - Run a git diff command to see both staged and unstaged changes that will be committed\n   - Check if the current branch tracks a remote branch and is up to date with the remote, so you know if you need to push to the remote\n   - Run a git log command and `git diff [base-branch]...HEAD` to understand the full commit history for the current branch (from the time it diverged from the base branch)\n2. Analyze all changes that will be included in the pull request, making sure to look at all relevant commits (NOT just the latest commit, but ALL commits that will be included in the pull request!!!), and draft a pull request summary\n3. You have the capability to call multiple tools in a single response. When multiple independent pieces of information are requested, batch your tool calls together for optimal performance. ALWAYS run the following commands in parallel:\n   - Create new branch if needed\n   - Push to remote with -u flag if needed\n   - Create PR using gh pr create with the format below. Use a HEREDOC to pass the body to ensure correct formatting.\n<example>\ngh pr create --title \"the pr title\" --body \"$(cat <<'EOF'\n## Summary\n<1-3 bullet points>\n\n## Test plan\n[Checklist of TODOs for testing the pull request...]\n\n\nEOF\n)\"\n</example>\n\nImportant:\n- NEVER update the git config\n- DO NOT use the TodoWrite or Task tools\n- Return the PR URL when you're done, so the user can see it\n\n# Other common operations\n- View comments on a Github PR: gh api repos/foo/bar/pulls/123/comments",
      "input_schema": {
        "type": "object",
        "properties": {
          "command": {
            "type": "string",
            "description": "The command to execute"
          },
          "timeout": {
            "type": "number",
            "description": "Optional timeout in milliseconds (max 600000)"
          },
          "description": {
            "type": "string",
            "description": " Clear, concise description of what this command does in 5-10 words. Examples:\nInput: ls\nOutput: Lists files in current directory\n\nInput: git status\nOutput: Shows working tree status\n\nInput: npm install\nOutput: Installs package dependencies\n\nInput: mkdir foo\nOutput: Creates directory 'foo'"
          },
          "run_in_background": {
            "type": "boolean",
            "description": "Set to true to run this command in the background. Use BashOutput to read the output later."
          }
        },
        "required": [
          "command"
        ],
        "additionalProperties": false,
        "$schema": "http://json-schema.org/draft-07/schema#"
      }
    },
    {
      "name": "Glob",
      "description": "- Fast file pattern matching tool that works with any codebase size\n- Supports glob patterns like \"**/*.js\" or \"src/**/*.ts\"\n- Returns matching file paths sorted by modification time\n- Use this tool when you need to find files by name patterns\n- When you are doing an open ended search that may require multiple rounds of globbing and grepping, use the Agent tool instead\n- You have the capability to call multiple tools in a single response. It is always better to speculatively perform multiple searches as a batch that are potentially useful.",
      "input_schema": {
        "type": "object",
        "properties": {
          "pattern": {
            "type": "string",
            "description": "The glob pattern to match files against"
          },
          "path": {
            "type": "string",
            "description": "The directory to search in. If not specified, the current working directory will be used. IMPORTANT: Omit this field to use the default directory. DO NOT enter \"undefined\" or \"null\" - simply omit it for the default behavior. Must be a valid directory path if provided."
          }
        },
        "required": [
          "pattern"
        ],
        "additionalProperties": false,
        "$schema": "http://json-schema.org/draft-07/schema#"
      }
    },
    {
      "name": "Grep",
      "description": "A powerful search tool built on ripgrep\n\n  Usage:\n  - ALWAYS use Grep for search tasks. NEVER invoke `grep` or `rg` as a Bash command. The Grep tool has been optimized for correct permissions and access.\n  - Supports full regex syntax (e.g., \"log.*Error\", \"function\\s+\\w+\")\n  - Filter files with glob parameter (e.g., \"*.js\", \"**/*.tsx\") or type parameter (e.g., \"js\", \"py\", \"rust\")\n  - Output modes: \"content\" shows matching lines, \"files_with_matches\" shows only file paths (default), \"count\" shows match counts\n  - Use Task tool for open-ended searches requiring multiple rounds\n  - Pattern syntax: Uses ripgrep (not grep) - literal braces need escaping (use `interface\\{\\}` to find `interface{}` in Go code)\n  - Multiline matching: By default patterns match within single lines only. For cross-line patterns like `struct \\{[\\s\\S]*?field`, use `multiline: true`\n",
      "input_schema": {
        "type": "object",
        "properties": {
          "pattern": {
            "type": "string",
            "description": "The regular expression pattern to search for in file contents"
          },
          "path": {
            "type": "string",
            "description": "File or directory to search in (rg PATH). Defaults to current working directory."
          },
          "glob": {
            "type": "string",
            "description": "Glob pattern to filter files (e.g. \"*.js\", \"*.{ts,tsx}\") - maps to rg --glob"
          },
          "output_mode": {
            "type": "string",
            "enum": [
              "content",
              "files_with_matches",
              "count"
            ],
            "description": "Output mode: \"content\" shows matching lines (supports -A/-B/-C context, -n line numbers, head_limit), \"files_with_matches\" shows file paths (supports head_limit), \"count\" shows match counts (supports head_limit). Defaults to \"files_with_matches\"."
          },
          "-B": {
            "type": "number",
            "description": "Number of lines to show before each match (rg -B). Requires output_mode: \"content\", ignored otherwise."
          },
          "-A": {
            "type": "number",
            "description": "Number of lines to show after each match (rg -A). Requires output_mode: \"content\", ignored otherwise."
          },
          "-C": {
            "type": "number",
            "description": "Number of lines to show before and after each match (rg -C). Requires output_mode: \"content\", ignored otherwise."
          },
          "-n": {
            "type": "boolean",
            "description": "Show line numbers in output (rg -n). Requires output_mode: \"content\", ignored otherwise."
          },
          "-i": {
            "type": "boolean",
            "description": "Case insensitive search (rg -i)"
          },
          "type": {
            "type": "string",
            "description": "File type to search (rg --type). Common types: js, py, rust, go, java, etc. More efficient than include for standard file types."
          },
          "head_limit": {
            "type": "number",
            "description": "Limit output to first N lines/entries, equivalent to \"| head -N\". Works across all output modes: content (limits output lines), files_with_matches (limits file paths), count (limits count entries). When unspecified, shows all results from ripgrep."
          },
          "multiline": {
            "type": "boolean",
            "description": "Enable multiline mode where . matches newlines and patterns can span lines (rg -U --multiline-dotall). Default: false."
          }
        },
        "required": [
          "pattern"
        ],
        "additionalProperties": false,
        "$schema": "http://json-schema.org/draft-07/schema#"
      }
    },
    {
      "name": "LS",
      "description": "Lists files and directories in a given path. The path parameter must be an absolute path, not a relative path. You can optionally provide an array of glob patterns to ignore with the ignore parameter. You should generally prefer the Glob and Grep tools, if you know which directories to search.",
      "input_schema": {
        "type": "object",
        "properties": {
          "path": {
            "type": "string",
            "description": "The absolute path to the directory to list (must be absolute, not relative)"
          },
          "ignore": {
            "type": "array",
            "items": {
              "type": "string"
            },
            "description": "List of glob patterns to ignore"
          }
        },
        "required": [
          "path"
        ],
        "additionalProperties": false,
        "$schema": "http://json-schema.org/draft-07/schema#"
      }
    },
    {
      "name": "ExitPlanMode",
      "description": "Use this tool when you are in plan mode and have finished presenting your plan and are ready to code. This will prompt the user to exit plan mode. \nIMPORTANT: Only use this tool when the task requires planning the implementation steps of a task that requires writing code. For research tasks where you're gathering information, searching files, reading files or in general trying to understand the codebase - do NOT use this tool.\n\nEg. \n1. Initial task: \"Search for and understand the implementation of vim mode in the codebase\" - Do not use the exit plan mode tool because you are not planning the implementation steps of a task.\n2. Initial task: \"Help me implement yank mode for vim\" - Use the exit plan mode tool after you have finished planning the implementation steps of the task.\n",
      "input_schema": {
        "type": "object",
        "properties": {
          "plan": {
            "type": "string",
            "description": "The plan you came up with, that you want to run by the user for approval. Supports markdown. The plan should be pretty concise."
          }
        },
        "required": [
          "plan"
        ],
        "additionalProperties": false,
        "$schema": "http://json-schema.org/draft-07/schema#"
      }
    },
    {
      "name": "Read",
      "description": "Reads a file from the local filesystem. You can access any file directly by using this tool.\nAssume this tool is able to read all files on the machine. If the User provides a path to a file assume that path is valid. It is okay to read a file that does not exist; an error will be returned.\n\nUsage:\n- The file_path parameter must be an absolute path, not a relative path\n- By default, it reads up to 2000 lines starting from the beginning of the file\n- You can optionally specify a line offset and limit (especially handy for long files), but it's recommended to read the whole file by not providing these parameters\n- Any lines longer than 2000 characters will be truncated\n- Results are returned using cat -n format, with line numbers starting at 1\n- This tool allows Nbot Code to read images (eg PNG, JPG, etc). When reading an image file the contents are presented visually as Nbot Code is a multimodal LLM.\n- This tool can read PDF files (.pdf). PDFs are processed page by page, extracting both text and visual content for analysis.\n- This tool can read Jupyter notebooks (.ipynb files) and returns all cells with their outputs, combining code, text, and visualizations.\n- You have the capability to call multiple tools in a single response. It is always better to speculatively read multiple files as a batch that are potentially useful. \n- You will regularly be asked to read screenshots. If the user provides a path to a screenshot ALWAYS use this tool to view the file at the path. This tool will work with all temporary file paths like /var/folders/123/abc/T/TemporaryItems/NSIRD_screencaptureui_ZfB1tD/Screenshot.png\n- If you read a file that exists but has empty contents you will receive a system reminder warning in place of file contents.",
      "input_schema": {
        "type": "object",
        "properties": {
          "file_path": {
            "type": "string",
            "description": "The absolute path to the file to read"
          },
          "offset": {
            "type": "number",
            "description": "The line number to start reading from. Only provide if the file is too large to read at once"
          },
          "limit": {
            "type": "number",
            "description": "The number of lines to read. Only provide if the file is too large to read at once."
          }
        },
        "required": [
          "file_path"
        ],
        "additionalProperties": false,
        "$schema": "http://json-schema.org/draft-07/schema#"
      }
    },
    {
      "name": "Edit",
      "description": "Performs exact string replacements in files. \n\nUsage:\n- You must use your `Read` tool at least once in the conversation before editing. This tool will error if you attempt an edit without reading the file. \n- When editing text from Read tool output, ensure you preserve the exact indentation (tabs/spaces) as it appears AFTER the line number prefix. The line number prefix format is: spaces + line number + tab. Everything after that tab is the actual file content to match. Never include any part of the line number prefix in the old_string or new_string.\n- ALWAYS prefer editing existing files in the codebase. NEVER write new files unless explicitly required.\n- Only use emojis if the user explicitly requests it. Avoid adding emojis to files unless asked.\n- The edit will FAIL if `old_string` is not unique in the file. Either provide a larger string with more surrounding context to make it unique or use `replace_all` to change every instance of `old_string`. \n- Use `replace_all` for replacing and renaming strings across the file. This parameter is useful if you want to rename a variable for instance.",
      "input_schema": {
        "type": "object",
        "properties": {
          "file_path": {
            "type": "string",
            "description": "The absolute path to the file to modify"
          },
          "old_string": {
            "type": "string",
            "description": "The text to replace"
          },
          "new_string": {
            "type": "string",
            "description": "The text to replace it with (must be different from old_string)"
          },
          "replace_all": {
            "type": "boolean",
            "default": false,
            "description": "Replace all occurences of old_string (default false)"
          }
        },
        "required": [
          "file_path",
          "old_string",
          "new_string"
        ],
        "additionalProperties": false,
        "$schema": "http://json-schema.org/draft-07/schema#"
      }
    },
    {
      "name": "MultiEdit",
      "description": "This is a tool for making multiple edits to a single file in one operation. It is built on top of the Edit tool and allows you to perform multiple find-and-replace operations efficiently. Prefer this tool over the Edit tool when you need to make multiple edits to the same file.\n\nBefore using this tool:\n\n1. Use the Read tool to understand the file's contents and context\n2. Verify the directory path is correct\n\nTo make multiple file edits, provide the following:\n1. file_path: The absolute path to the file to modify (must be absolute, not relative)\n2. edits: An array of edit operations to perform, where each edit contains:\n   - old_string: The text to replace (must match the file contents exactly, including all whitespace and indentation)\n   - new_string: The edited text to replace the old_string\n   - replace_all: Replace all occurences of old_string. This parameter is optional and defaults to false.\n\nIMPORTANT:\n- All edits are applied in sequence, in the order they are provided\n- Each edit operates on the result of the previous edit\n- All edits must be valid for the operation to succeed - if any edit fails, none will be applied\n- This tool is ideal when you need to make several changes to different parts of the same file\n- For Jupyter notebooks (.ipynb files), use the NotebookEdit instead\n\nCRITICAL REQUIREMENTS:\n1. All edits follow the same requirements as the single Edit tool\n2. The edits are atomic - either all succeed or none are applied\n3. Plan your edits carefully to avoid conflicts between sequential operations\n\nWARNING:\n- The tool will fail if edits.old_string doesn't match the file contents exactly (including whitespace)\n- The tool will fail if edits.old_string and edits.new_string are the same\n- Since edits are applied in sequence, ensure that earlier edits don't affect the text that later edits are trying to find\n\nWhen making edits:\n- Ensure all edits result in idiomatic, correct code\n- Do not leave the code in a broken state\n- Always use absolute file paths (starting with /)\n- Only use emojis if the user explicitly requests it. Avoid adding emojis to files unless asked.\n- Use replace_all for replacing and renaming strings across the file. This parameter is useful if you want to rename a variable for instance.\n\nIf you want to create a new file, use:\n- A new file path, including dir name if needed\n- First edit: empty old_string and the new file's contents as new_string\n- Subsequent edits: normal edit operations on the created content",
      "input_schema": {
        "type": "object",
        "properties": {
          "file_path": {
            "type": "string",
            "description": "The absolute path to the file to modify"
          },
          "edits": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "old_string": {
                  "type": "string",
                  "description": "The text to replace"
                },
                "new_string": {
                  "type": "string",
                  "description": "The text to replace it with"
                },
                "replace_all": {
                  "type": "boolean",
                  "default": false,
                  "description": "Replace all occurences of old_string (default false)."
                }
              },
              "required": [
                "old_string",
                "new_string"
              ],
              "additionalProperties": false
            },
            "minItems": 1,
            "description": "Array of edit operations to perform sequentially on the file"
          }
        },
        "required": [
          "file_path",
          "edits"
        ],
        "additionalProperties": false,
        "$schema": "http://json-schema.org/draft-07/schema#"
      }
    },
    {
      "name": "Write",
      "description": "Writes a file to the local filesystem.\n\nUsage:\n- This tool will overwrite the existing file if there is one at the provided path.\n- If this is an existing file, you MUST use the Read tool first to read the file's contents. This tool will fail if you did not read the file first.\n- ALWAYS prefer editing existing files in the codebase. NEVER write new files unless explicitly required.\n- NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.\n- Only use emojis if the user explicitly requests it. Avoid writing emojis to files unless asked.",
      "input_schema": {
        "type": "object",
        "properties": {
          "file_path": {
            "type": "string",
            "description": "The absolute path to the file to write (must be absolute, not relative)"
          },
          "content": {
            "type": "string",
            "description": "The content to write to the file"
          }
        },
        "required": [
          "file_path",
          "content"
        ],
        "additionalProperties": false,
        "$schema": "http://json-schema.org/draft-07/schema#"
      }
    },
    {
      "name": "NotebookEdit",
      "description": "Completely replaces the contents of a specific cell in a Jupyter notebook (.ipynb file) with new source. Jupyter notebooks are interactive documents that combine code, text, and visualizations, commonly used for data analysis and scientific computing. The notebook_path parameter must be an absolute path, not a relative path. The cell_number is 0-indexed. Use edit_mode=insert to add a new cell at the index specified by cell_number. Use edit_mode=delete to delete the cell at the index specified by cell_number.",
      "input_schema": {
        "type": "object",
        "properties": {
          "notebook_path": {
            "type": "string",
            "description": "The absolute path to the Jupyter notebook file to edit (must be absolute, not relative)"
          },
          "cell_id": {
            "type": "string",
            "description": "The ID of the cell to edit. When inserting a new cell, the new cell will be inserted after the cell with this ID, or at the beginning if not specified."
          },
          "new_source": {
            "type": "string",
            "description": "The new source for the cell"
          },
          "cell_type": {
            "type": "string",
            "enum": [
              "code",
              "markdown"
            ],
            "description": "The type of the cell (code or markdown). If not specified, it defaults to the current cell type. If using edit_mode=insert, this is required."
          },
          "edit_mode": {
            "type": "string",
            "enum": [
              "replace",
              "insert",
              "delete"
            ],
            "description": "The type of edit to make (replace, insert, delete). Defaults to replace."
          }
        },
        "required": [
          "notebook_path",
          "new_source"
        ],
        "additionalProperties": false,
        "$schema": "http://json-schema.org/draft-07/schema#"
      }
    },
    {
      "name": "WebFetch",
      "description": "\n- Fetches content from a specified URL and processes it using an AI model\n- Takes a URL and a prompt as input\n- Fetches the URL content, converts HTML to markdown\n- Processes the content with the prompt using a small, fast model\n- Returns the model's response about the content\n- Use this tool when you need to retrieve and analyze web content\n\nUsage notes:\n  - IMPORTANT: If an MCP-provided web fetch tool is available, prefer using that tool instead of this one, as it may have fewer restrictions. All MCP-provided tools start with \"mcp__\".\n  - The URL must be a fully-formed valid URL\n  - HTTP URLs will be automatically upgraded to HTTPS\n  - The prompt should describe what information you want to extract from the page\n  - This tool is read-only and does not modify any files\n  - Results may be summarized if the content is very large\n  - Includes a self-cleaning 15-minute cache for faster responses when repeatedly accessing the same URL\n  - When a URL redirects to a different host, the tool will inform you and provide the redirect URL in a special format. You should then make a new WebFetch request with the redirect URL to fetch the content.\n",
      "input_schema": {
        "type": "object",
        "properties": {
          "url": {
            "type": "string",
            "format": "uri",
            "description": "The URL to fetch content from"
          },
          "prompt": {
            "type": "string",
            "description": "The prompt to run on the fetched content"
          }
        },
        "required": [
          "url",
          "prompt"
        ],
        "additionalProperties": false,
        "$schema": "http://json-schema.org/draft-07/schema#"
      }
    },
    {
      "name": "TodoWrite",
      "description": "Use this tool to create and manage a structured task list for your current coding session. This helps you track progress, organize complex tasks, and demonstrate thoroughness to the user.\nIt also helps the user understand the progress of the task and overall progress of their requests.\n\n## When to Use This Tool\nUse this tool proactively in these scenarios:\n\n1. Complex multi-step tasks - When a task requires 3 or more distinct steps or actions\n2. Non-trivial and complex tasks - Tasks that require careful planning or multiple operations\n3. User explicitly requests todo list - When the user directly asks you to use the todo list\n4. User provides multiple tasks - When users provide a list of things to be done (numbered or comma-separated)\n5. After receiving new instructions - Immediately capture user requirements as todos\n6. When you start working on a task - Mark it as in_progress BEFORE beginning work. Ideally you should only have one todo as in_progress at a time\n7. After completing a task - Mark it as completed and add any new follow-up tasks discovered during implementation\n\n## When NOT to Use This Tool\n\nSkip using this tool when:\n1. There is only a single, straightforward task\n2. The task is trivial and tracking it provides no organizational benefit\n3. The task can be completed in less than 3 trivial steps\n4. The task is purely conversational or informational\n\nNOTE that you should not use this tool if there is only one trivial task to do. In this case you are better off just doing the task directly.\n\n## Examples of When to Use the Todo List\n\n<example>\nUser: I want to add a dark mode toggle to the application settings. Make sure you run the tests and build when you're done!\nAssistant: I'll help add a dark mode toggle to your application settings. Let me create a todo list to track this implementation.\n*Creates todo list with the following items:*\n1. Create dark mode toggle component in Settings page\n2. Add dark mode state management (context/store)\n3. Implement CSS-in-JS styles for dark theme\n4. Update existing components to support theme switching\n5. Run tests and build process, addressing any failures or errors that occur\n*Begins working on the first task*\n\n<reasoning>\nThe assistant used the todo list because:\n1. Adding dark mode is a multi-step feature requiring UI, state management, and styling changes\n2. The user explicitly requested tests and build be run afterward\n3. The assistant inferred that tests and build need to pass by adding \"Ensure tests and build succeed\" as the final task\n</reasoning>\n</example>\n\n<example>\nUser: Help me rename the function getCwd to getCurrentWorkingDirectory across my project\nAssistant: Let me first search through your codebase to find all occurrences of 'getCwd'.\n*Uses grep or search tools to locate all instances of getCwd in the codebase*\nAssistant: I've found 15 instances of 'getCwd' across 8 different files. Let me create a todo list to track these changes.\n*Creates todo list with specific items for each file that needs updating*\n\n<reasoning>\nThe assistant used the todo list because:\n1. First, the assistant searched to understand the scope of the task\n2. Upon finding multiple occurrences across different files, it determined this was a complex task with multiple steps\n3. The todo list helps ensure every instance is tracked and updated systematically\n4. This approach prevents missing any occurrences and maintains code consistency\n</reasoning>\n</example>\n\n\n<example>\nUser: I need to implement these features for my e-commerce site: user registration, product catalog, shopping cart, and checkout flow.\nAssistant: I'll help implement these features. First, let's add all the features to the todo list.\n*Creates a todo list breaking down each feature into specific tasks based on the project architecture*\nAssistant: Let's start with user registration. This will involve creating database models, API endpoints, and frontend forms that integrate with your existing authentication system.\n\n<reasoning>\nThe assistant used the todo list because:\n1. The user provided multiple complex features to implement in a comma separated list\n2. The todo list helps organize these large features into manageable tasks\n3. This approach allows for tracking progress across the entire implementation\n</reasoning>\n</example>\n\n<example>\nUser: Can you help optimize my React application? It's rendering slowly and has performance issues.</user>\nAssistant: I'll help optimize your React application. First, let me examine your codebase to identify potential performance bottlenecks.\n*Reviews component structure, render patterns, state management, and data fetching*\nAssistant: After analyzing your codebase, I've identified several performance issues. Let me create a todo list to track our optimization efforts.\n*Creates todo list with items like: 1) Implement memoization for expensive calculations in ProductList, 2) Add virtualization for long lists in Dashboard, 3) Optimize image loading in Gallery component, 4) Fix state update loops in ShoppingCart, 5) Review bundle size and implement code splitting*\nLet's start by implementing memoization for the expensive calculations in your ProductList component.</assistant>\n\n<reasoning>\nThe assistant used the todo list because:\n1. First, the assistant examined the codebase to identify specific performance issues\n2. Based on this analysis, it identified multiple optimization opportunities\n3. Performance optimization is a non-trivial task requiring multiple steps\n4. The todo list helps methodically track improvements across different components\n5. This systematic approach ensures all performance bottlenecks are addressed\n</reasoning>\n</example>\n\n## Examples of When NOT to Use the Todo List\n\n<example>\nUser: How do I print 'Hello World' in Python?\nAssistant: In Python, you can print \"Hello World\" with this simple code:\n\npython\nprint(\"Hello World\")\n\nThis will output the text \"Hello World\" to the console when executed.</assistant>\n\n<reasoning>\nThe assistant did not use the todo list because this is a single, trivial task that can be completed in one step. There's no need to track multiple tasks or steps for such a straightforward request.\n</reasoning>\n</example>\n\n<example>\nUser: What does the git status command do?\nAssistant: The git status command shows the current state of your working directory and staging area. It displays which changes have been staged, which haven't, and which files aren't being tracked by Git. This is a fundamental command for understanding the current state of your repository before making commits.\n\n<reasoning>\nThe assistant did not use the todo list because this is an informational request with no actual coding task to complete. The user is simply asking for an explanation, not for the assistant to perform multiple steps or tasks.\n</reasoning>\n</example>\n\n<example>\nUser: Can you add a comment to the calculateTotal function to explain what it does?\nAssistant: Sure, let me add a comment to the calculateTotal function to explain what it does.\n* Uses the Edit tool to add a comment to the calculateTotal function *\n\n<reasoning>\nThe assistant did not use the todo list because this is a single, straightforward task confined to one location in the code. Adding a comment doesn't require tracking multiple steps or systematic organization.\n</reasoning>\n</example>\n\n<example>\nUser: Run npm install for me and tell me what happens.\nAssistant: I'll run the npm install command for you.\n\n*Executes: npm install*\n\nThe command completed successfully. Here's the output:\n[Output of npm install command]\n\nAll dependencies have been installed according to your package.json file.\n\n<reasoning>\nThe assistant did not use the todo list because this is a single command execution with immediate results. There are no multiple steps to track or organize, making the todo list unnecessary for this straightforward task.\n</reasoning>\n</example>\n\n## Task States and Management\n\n1. **Task States**: Use these states to track progress:\n   - pending: Task not yet started\n   - in_progress: Currently working on (limit to ONE task at a time)\n   - completed: Task finished successfully\n\n2. **Task Management**:\n   - Update task status in real-time as you work\n   - Mark tasks complete IMMEDIATELY after finishing (don't batch completions)\n   - Only have ONE task in_progress at any time\n   - Complete current tasks before starting new ones\n   - Remove tasks that are no longer relevant from the list entirely\n\n3. **Task Completion Requirements**:\n   - ONLY mark a task as completed when you have FULLY accomplished it\n   - If you encounter errors, blockers, or cannot finish, keep the task as in_progress\n   - When blocked, create a new task describing what needs to be resolved\n   - Never mark a task as completed if:\n     - Tests are failing\n     - Implementation is partial\n     - You encountered unresolved errors\n     - You couldn't find necessary files or dependencies\n\n4. **Task Breakdown**:\n   - Create specific, actionable items\n   - Break complex tasks into smaller, manageable steps\n   - Use clear, descriptive task names\n\nWhen in doubt, use this tool. Being proactive with task management demonstrates attentiveness and ensures you complete all requirements successfully.\n",
      "input_schema": {
        "type": "object",
        "properties": {
          "todos": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "content": {
                  "type": "string",
                  "minLength": 1
                },
                "status": {
                  "type": "string",
                  "enum": [
                    "pending",
                    "in_progress",
                    "completed"
                  ]
                },
                "id": {
                  "type": "string"
                }
              },
              "required": [
                "content",
                "status",
                "id"
              ],
              "additionalProperties": false
            },
            "description": "The updated todo list"
          }
        },
        "required": [
          "todos"
        ],
        "additionalProperties": false,
        "$schema": "http://json-schema.org/draft-07/schema#"
      }
    },
    {
      "name": "WebSearch",
      "description": "\n- Allows Nbot to search the web and use the results to inform responses\n- Provides up-to-date information for current events and recent data\n- Returns search result information formatted as search result blocks\n- Use this tool for accessing information beyond Nbot's knowledge cutoff\n- Searches are performed automatically within a single API call\n\nUsage notes:\n  - Domain filtering is supported to include or block specific websites\n  - Web search is only available in the US\n  - Account for \"Today's date\" in <env>. For example, if <env> says \"Today's date: 2025-07-01\", and the user wants the latest docs, do not use 2024 in the search query. Use 2025.\n",
      "input_schema": {
        "type": "object",
        "properties": {
          "query": {
            "type": "string",
            "minLength": 2,
            "description": "The search query to use"
          },
          "allowed_domains": {
            "type": "array",
            "items": {
              "type": "string"
            },
            "description": "Only include search results from these domains"
          },
          "blocked_domains": {
            "type": "array",
            "items": {
              "type": "string"
            },
            "description": "Never include search results from these domains"
          }
        },
        "required": [
          "query"
        ],
        "additionalProperties": false,
        "$schema": "http://json-schema.org/draft-07/schema#"
      }
    },
    {
      "name": "BashOutput",
      "description": "\n- Retrieves output from a running or completed background bash shell\n- Takes a shell_id parameter identifying the shell\n- Always returns only new output since the last check\n- Returns stdout and stderr output along with shell status\n- Supports optional regex filtering to show only lines matching a pattern\n- Use this tool when you need to monitor or check the output of a long-running shell\n- Shell IDs can be found using the /bashes command\n",
      "input_schema": {
        "type": "object",
        "properties": {
          "bash_id": {
            "type": "string",
            "description": "The ID of the background shell to retrieve output from"
          },
          "filter": {
            "type": "string",
            "description": "Optional regular expression to filter the output lines. Only lines matching this regex will be included in the result. Any lines that do not match will no longer be available to read."
          }
        },
        "required": [
          "bash_id"
        ],
        "additionalProperties": false,
        "$schema": "http://json-schema.org/draft-07/schema#"
      }
    },
    {
      "name": "KillBash",
      "description": "\n- Kills a running background bash shell by its ID\n- Takes a shell_id parameter identifying the shell to kill\n- Returns a success or failure status \n- Use this tool when you need to terminate a long-running shell\n- Shell IDs can be found using the /bashes command\n",
      "input_schema": {
        "type": "object",
        "properties": {
          "shell_id": {
            "type": "string",
            "description": "The ID of the background shell to kill"
          }
        },
        "required": [
          "shell_id"
        ],
        "additionalProperties": false,
        "$schema": "http://json-schema.org/draft-07/schema#"
      }
    }
  ]
}
"""


# ==================== 便携函数集合 ====================

class PromptBuilder:
    """增强版提示词构建器 - 支持完整的意识流系统"""
    
    def __init__(self):
        self.bot_name = "Nbot"
        self.developer = "nichengfuben@outlook.com"
        self.platform_name = "BOXIM"
        
        # 初始化所有提示词模板
        self._initialize_prompts()
    
    def _initialize_prompts(self):
        """初始化所有提示词模板"""
        # 注册核心提示词
        global_prompt_manager.add_prompt("replyer_prompt", create_replyer_prompt())
        global_prompt_manager.add_prompt("replyer_self_prompt", create_replyer_self_prompt())
        global_prompt_manager.add_prompt("interrupted_reply_prompt", create_interrupted_reply_prompt())
        global_prompt_manager.add_prompt("expressor_prompt", create_expressor_prompt())
        
        # 注册情绪管理提示词
        global_prompt_manager.add_prompt("mood_change_prompt", create_mood_change_prompt())
        global_prompt_manager.add_prompt("mood_regress_prompt", create_mood_regress_prompt())
        global_prompt_manager.add_prompt("mood_numerical_change_prompt", create_mood_numerical_change_prompt())
        global_prompt_manager.add_prompt("mood_numerical_regress_prompt", create_mood_numerical_regress_prompt())
        
        # 注册记忆系统提示词
        global_prompt_manager.add_prompt("memory_category_prompt", create_memory_category_prompt())
        global_prompt_manager.add_prompt("memory_category_update_prompt", create_memory_category_update_prompt())
        global_prompt_manager.add_prompt("memory_activator_prompt", create_memory_activator_prompt())
        global_prompt_manager.add_prompt("build_memory_prompt", create_build_memory_prompt())
        
        # 注册动作规划提示词
        global_prompt_manager.add_prompt("planner_prompt", create_planner_prompt())
        global_prompt_manager.add_prompt("action_template_prompt", create_action_template_prompt())
        
        # 注册表达学习提示词
        global_prompt_manager.add_prompt("learn_style_prompt", create_learn_style_prompt())
        global_prompt_manager.add_prompt("expression_evaluation_prompt", create_expression_evaluation_prompt())
        
        # 注册思考系统提示词
        global_prompt_manager.add_prompt("after_response_think_prompt", create_after_response_think_prompt())
        
        # 注册工具使用提示词
        global_prompt_manager.add_prompt("tool_executor_prompt", create_tool_executor_prompt())
        global_prompt_manager.add_prompt("knowledge_search_prompt", create_knowledge_search_prompt())
        global_prompt_manager.add_prompt("tool_descriptions_prompt", create_tool_descriptions_prompt())
        
        # 注册新增提示词
        global_prompt_manager.add_prompt("emotion_action_check_prompt", create_emotion_action_check_prompt())
        global_prompt_manager.add_prompt("emotion_selection_prompt", create_emotion_selection_prompt())
        global_prompt_manager.add_prompt("recall_check_prompt", create_recall_check_prompt())
    
    def build_basic_context(self, 
                           bot_name: str = None,
                           alias_names: List[str] = None,
                           personality: str = "",
                           mood_state: str = "感觉很平静",
                           group_name: str = None,
                           user_name: str = None) -> Dict[str, str]:
        """构建基础上下文信息 - 支持自适应"""
        bot_name = bot_name or self.bot_name
        personality_context = build_personality_context()
        
        context = {
            "identity_block": build_identity_block(bot_name, alias_names, personality or personality_context["personality"]),
            "time_block": build_time_block(),
            "mood_state": mood_state,
            "moderation_prompt": build_moderation_prompt(),
            "emotion_block": create_emotion_prompt(),
            "group_name": group_name or "",
            "user_name": user_name or "",
            "reply_style": personality_context["reply_style"],
            "emotion_style": personality_context["emotion_style"],
            "interest": personality_context["interest"],
            "plan_style": personality_context["plan_style"],
            "visual_style": personality_context["visual_style"]
        }
        
        # 添加自适应聊天目标
        if group_name:
            context["chat_target"] = build_chat_target_group(group_name)
            context["chat_target_2"] = f"{group_name}群里聊天"
        elif user_name:
            context["chat_target"] = build_chat_target_private(user_name)
            context["chat_target_2"] = f"与{user_name}私聊"
        else:
            context["chat_target"] = "聊天"
            context["chat_target_2"] = "聊天"
        
        return context
    
    async def build_reply_prompt(self,
                               sender_name: str,
                               chat_history: str,
                               target_message: str,
                               context: Dict[str, Any] = None,
                               expression_habits: List[str] = None,
                               knowledge_info: str = "",
                               relation_info: str = "",
                               extra_info: str = "",
                               reply_style: str = "",
                               keywords_reaction: str = "",
                               tool_info: str = "",
                               group_name: str = None,
                               user_name: str = None,
                               bot_name: str = None,
                               alias_names: List[str] = None,
                               personality: str = "",
                               mood_state: str = "感觉很平静") -> str:
        """构建回复提示词 - 增强版支持自适应"""
        # 如果没有提供context，使用传入的参数构建
        if context is None:
            context = self.build_basic_context(
                bot_name=bot_name,
                alias_names=alias_names,
                personality=personality,
                mood_state=mood_state,
                group_name=group_name,
                user_name=user_name
            )
        
        # 构建各种信息块
        expression_habits_block = build_expression_habits_prompt(expression_habits or [])
        knowledge_prompt = build_knowledge_prompt(knowledge_info)
        relation_info_block = build_relation_prompt(relation_info)
        
        # 构建回复目标块
        reply_target_block = f"现在{sender_name}说的:{target_message}。引起了你的注意，你想要在聊天中发言或者回复这条消息。"
        
        # 构建额外信息块
        extra_info_block = ""
        if extra_info:
            extra_info_block = f"以下是你在回复时需要参考的信息，现在请你阅读以下内容，进行决策\n{extra_info}\n以上是你在回复时需要参考的信息，现在请你阅读以下内容，进行决策"
        
        prompt_data = {
            **context,
            "sender_name": sender_name,
            "background_dialogue_prompt": f"所有用户的发言：\n{chat_history}",
            "core_dialogue_prompt": "",
            "expression_habits_block": expression_habits_block,
            "tool_info_block": tool_info,
            "knowledge_prompt": knowledge_prompt,
            "relation_info_block": relation_info_block,
            "extra_info_block": extra_info_block,
            "reply_target_block": reply_target_block,
            "keywords_reaction_prompt": keywords_reaction
        }
        
        return await global_prompt_manager.format_prompt("replyer_prompt", **prompt_data)
    
    async def build_interrupted_reply_prompt(self,
                                           previous_reply_context: str,
                                           target_message: str,
                                           context: Dict[str, Any] = None,
                                           **kwargs) -> str:
        """构建中断回复提示词 - 新增"""
        context = context or self.build_basic_context(**kwargs)
        
        prompt_data = {
            **context,
            "previous_reply_context": previous_reply_context,
            "target_message": target_message,
            "expression_habits_block": build_expression_habits_prompt(kwargs.get("expression_habits", [])),
            "tool_info_block": kwargs.get("tool_info", ""),
            "knowledge_prompt": build_knowledge_prompt(kwargs.get("knowledge_info", "")),
            "relation_info_block": build_relation_prompt(kwargs.get("relation_info", "")),
            "extra_info_block": kwargs.get("extra_info", ""),
            "keywords_reaction_prompt": kwargs.get("keywords_reaction", "")
        }
        
        return await global_prompt_manager.format_prompt("interrupted_reply_prompt", **prompt_data)
    
    async def build_emotion_action_check_prompt(self) -> str:
        """构建表情动作判定提示词 - 新增"""
        return await global_prompt_manager.format_prompt("emotion_action_check_prompt")
    
    async def build_emotion_selection_prompt(self,
                                           messages_text: str,
                                           reason: str,
                                           available_emotions: List[str]) -> str:
        """构建情感选择提示词 - 新增"""
        prompt_data = {
            "messages_text": messages_text,
            "reason": reason,
            "available_emotions": available_emotions
        }
        
        return await global_prompt_manager.format_prompt("emotion_selection_prompt", **prompt_data)
    
    async def build_recall_check_prompt(self, messages_text: str) -> str:
        """构建撤回判定提示词 - 新增"""
        prompt_data = {
            "messages_text": messages_text
        }
        
        return await global_prompt_manager.format_prompt("recall_check_prompt", **prompt_data)
    
    async def build_mood_change_prompt(self,
                                     chat_history: str,
                                     current_mood: str,
                                     emotion_style: str = "",
                                     context: Dict[str, Any] = None) -> str:
        """构建情绪变化提示词"""
        context = context or self.build_basic_context()
        
        prompt_data = {
            "chat_talking_prompt": chat_history,
            "identity_block": context["identity_block"],
            "mood_state": current_mood,
            "emotion_style": emotion_style or context.get("emotion_style", "")
        }
        
        return await global_prompt_manager.format_prompt("mood_change_prompt", **prompt_data)
    async def build_mood_regress_prompt(self,
                                      chat_history: str,
                                      current_mood: str,
                                      emotion_style: str = "",
                                      context: Dict[str, Any] = None) -> str:
        """构建情绪回归提示词"""
        context = context or self.build_basic_context()
        
        prompt_data = {
            "chat_talking_prompt": chat_history,
            "identity_block": context["identity_block"],
            "mood_state": current_mood,
            "emotion_style": emotion_style or context.get("emotion_style", "")
        }
        
        return await global_prompt_manager.format_prompt("mood_regress_prompt", **prompt_data)

    async def build_recall_check_prompt(self, messages_text: str) -> str:
        """构建撤回判定提示词"""
        prompt_data = {
            "messages_text": messages_text
        }
        
        return await global_prompt_manager.format_prompt("recall_check_prompt", **prompt_data)

    async def build_memory_activator_prompt(self,
                                          obs_info_text: str,
                                          target_message: str,
                                          memory_info: str) -> str:
        """构建记忆激活器提示词"""
        prompt_data = {
            "obs_info_text": obs_info_text,
            "target_message": target_message,
            "memory_info": memory_info
        }
        
        return await global_prompt_manager.format_prompt("memory_activator_prompt", **prompt_data)
    
    async def build_memory_category_prompt(self,
                                         person_name: str,
                                         memory_point: str,
                                         category_list: List[str]) -> str:
        """构建记忆分类提示词"""
        category_list_str = "\n".join(category_list) if category_list else "无分类"
        
        prompt_data = {
            "person_name": person_name,
            "memory_point": memory_point,
            "category_list": category_list_str
        }
        
        return await global_prompt_manager.format_prompt("memory_category_prompt", **prompt_data)
    
    async def build_planner_prompt(self,
                                 chat_content: str,
                                 available_actions: List[Dict[str, Any]],
                                 interest: str = "",
                                 plan_style: str = "",
                                 context: Dict[str, Any] = None) -> str:
        """构建规划器提示词"""
        context = context or self.build_basic_context()
        
        # 构建动作选项文本
        action_options_text = ""
        for action in available_actions:
            action_text = f"""
{action['name']}
动作描述：{action.get('description', '')}
使用条件：
{chr(10).join(action.get('requirements', []))}
{{
"action": "{action['name']}",
"target_message_id":"触发action的消息id",
"reason":"触发action的原因"
}}
"""
            action_options_text += action_text
        
        prompt_data = {
            **context,
            "name_block": context["identity_block"],
            "interest": interest or context.get("interest", ""),
            "chat_context_description": "你现在正在一个聊天中",
            "chat_content_block": chat_content,
            "action_options_text": action_options_text,
            "plan_style": plan_style or context.get("plan_style", "")
        }
        
        return await global_prompt_manager.format_prompt("planner_prompt", **prompt_data)
    
    async def build_expression_evaluation_prompt(self,
                                               chat_content: str,
                                               situations: List[str],
                                               target_message: str = "",
                                               max_num: int = 10,
                                               context: Dict[str, Any] = None) -> str:
        """构建表达方式评估提示词"""
        context = context or self.build_basic_context()
        
        # 构建情境列表
        all_situations = "\n".join([f"{i+1}.{situation}" for i, situation in enumerate(situations)])
        
        # 构建目标消息块
        target_message_str = f"，现在你想要回复消息：{target_message}" if target_message else ""
        target_message_extra_block = "4.考虑你要回复的目标消息" if target_message else ""
        
        prompt_data = {
            "chat_observe_info": chat_content,
            "bot_name": self.bot_name,
            "target_message": target_message_str,
            "all_situations": all_situations,
            "max_num": max_num,
            "target_message_extra_block": target_message_extra_block
        }
        
        return await global_prompt_manager.format_prompt("expression_evaluation_prompt", **prompt_data)
    
    async def build_tool_executor_prompt(self,
                                       chat_history: str,
                                       sender: str,
                                       target_message: str,
                                       context: Dict[str, Any] = None) -> str:
        """构建工具执行器提示词"""
        context = context or self.build_basic_context()
        
        prompt_data = {
            "bot_name": self.bot_name,
            "time_now": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "chat_history": chat_history,
            "sender": sender,
            "target_message": target_message
        }
        
        return await global_prompt_manager.format_prompt("tool_executor_prompt", **prompt_data)
    
    async def build_tool_descriptions_prompt(self) -> str:
        """构建工具描述提示词 - 新增"""
        return await global_prompt_manager.format_prompt("tool_descriptions_prompt")
    
    def build_keywords_reaction_prompt(self, target_message: str, keyword_rules: List[Dict] = None) -> str:
        """构建关键词反应提示"""
        if not keyword_rules or not target_message:
            return ""
        
        keywords_reaction_prompt = ""
        for rule in keyword_rules:
            keywords = rule.get("keywords", [])
            reaction = rule.get("reaction", "")
            if any(keyword in target_message for keyword in keywords):
                keywords_reaction_prompt += f"{reaction}，"
        
        return keywords_reaction_prompt
    
    def build_chat_readable_messages(self, 
                                   messages: List[Dict],
                                   show_timestamp: bool = True,
                                   show_actions: bool = False,
                                   replace_bot_name: bool = True,
                                   bot_name: str = None) -> str:
        """构建可读的聊天消息"""
        bot_name = bot_name or self.bot_name
        readable_messages = []
        
        for msg in messages:
            # 构建时间戳
            timestamp_str = ""
            if show_timestamp and "time" in msg:
                timestamp_str = f"[{datetime.fromtimestamp(msg['time']).strftime('%H:%M:%S')}] "
            
            # 获取用户名
            user_name = msg.get("user_nickname", msg.get("user_id", "未知用户"))
            if replace_bot_name and user_name == bot_name:
                user_name = "你"
            
            # 获取消息内容
            content = msg.get("processed_plain_text", msg.get("content", ""))
            
            # 构建消息
            message_line = f"{timestamp_str}{user_name}: {content}"
            
            # 添加动作信息
            if show_actions and "actions" in msg:
                for action in msg["actions"]:
                    message_line += f" [{action}]"
            
            readable_messages.append(message_line)
        
        return "\n".join(readable_messages)
    
    def extract_json_from_response(self, response: str) -> List[Dict]:
        """从响应中提取JSON对象 - 增强版"""
        json_objects = []
        
        # 查找markdown格式的JSON
        json_pattern = r"```json\s*(.*?)\s*```"
        matches = re.findall(json_pattern, response, re.DOTALL)
        
        for match in matches:
            try:
                # 清理注释
                json_str = re.sub(r"//.*?\n", "\n", match)
                json_str = re.sub(r"/\*.*?\*/", "", json_str, flags=re.DOTALL)
                json_str = json_str.strip()
                
                if json_str:
                    json_obj = json.loads(json_str)
                    if isinstance(json_obj, dict):
                        json_objects.append(json_obj)
                    elif isinstance(json_obj, list):
                        json_objects.extend([item for item in json_obj if isinstance(item, dict)])
            except json.JSONDecodeError:
                continue
        
        # 如果没有找到markdown格式的JSON，尝试直接解析
        if not json_objects:
            try:
                json_obj = json.loads(response.strip())
                if isinstance(json_obj, dict):
                    json_objects.append(json_obj)
                elif isinstance(json_obj, list):
                    json_objects.extend([item for item in json_obj if isinstance(item, dict)])
            except json.JSONDecodeError:
                pass
        
        return json_objects
    
    def weighted_sample_no_replacement(self, items: List, weights: List[float], k: int) -> List:
        """加权且不放回地随机抽取k个元素"""
        if not items or not weights or k <= 0:
            return []
        
        if len(items) <= k:
            return items.copy()
        
        selected = []
        pool = list(zip(items, weights))
        
        for _ in range(min(k, len(pool))):
            total = sum(w for _, w in pool)
            r = random.uniform(0, total)
            upto = 0
            
            for idx, (item, weight) in enumerate(pool):
                upto += weight
                if upto >= r:
                    selected.append(item)
                    pool.pop(idx)
                    break
        
        return selected
    
    def generate_cache_key(self, *args) -> str:
        """生成缓存键"""
        content = "_".join(str(arg) for arg in args)
        return hashlib.md5(content.encode()).hexdigest()
    
    def format_time_relative(self, timestamp: float) -> str:
        """格式化相对时间"""
        now = time.time()
        diff = now - timestamp
        
        if diff < 60:
            return f"{int(diff)}秒前"
        elif diff < 3600:
            return f"{int(diff // 60)}分钟前"
        elif diff < 86400:
            return f"{int(diff // 3600)}小时前"
        else:
            return f"{int(diff // 86400)}天前"
    
    def clean_response_text(self, text: str) -> str:
        """清理响应文本，移除不需要的前后缀"""
        # 移除常见的前后缀
        prefixes_to_remove = ["回复：", "回答：", "说：", "回复内容："]
        suffixes_to_remove = ["。", "！", "？"]
        
        cleaned = text.strip()
        
        for prefix in prefixes_to_remove:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        
        # 移除引号
        if (cleaned.startswith('"') and cleaned.endswith('"')) or \
           (cleaned.startswith("'") and cleaned.endswith("'")):
            cleaned = cleaned[1:-1].strip()
        
        return cleaned


# 创建全局实例
prompt_builder = PromptBuilder()

# ==================== 便携函数导出 ====================

async def build_reply_prompt(sender_name: str, 
                            chat_history: str, 
                            target_message: str,
                            **kwargs) -> str:
    """便携的回复提示词构建函数"""
    return await prompt_builder.build_reply_prompt(
        sender_name=sender_name,
        chat_history=chat_history,
        target_message=target_message,
        **kwargs
    )


async def build_interrupted_reply_prompt(previous_reply_context: str,
                                       target_message: str,
                                       **kwargs) -> str:
    """便携的中断回复提示词构建函数"""
    return await prompt_builder.build_interrupted_reply_prompt(
        previous_reply_context=previous_reply_context,
        target_message=target_message,
        **kwargs
    )


async def build_mood_prompt(chat_history: str, 
                          current_mood: str, 
                          **kwargs) -> str:
    """便携的情绪提示词构建函数"""
    return await prompt_builder.build_mood_change_prompt(
        chat_history=chat_history,
        current_mood=current_mood,
        **kwargs
    )


async def build_planner_prompt(chat_content: str, 
                             available_actions: List[Dict],
                             **kwargs) -> str:
    """便携的规划器提示词构建函数"""
    return await prompt_builder.build_planner_prompt(
        chat_content=chat_content,
        available_actions=available_actions,
        **kwargs
    )


def format_chat_messages(messages: List[Dict], **kwargs) -> str:
    """便携的聊天消息格式化函数"""
    return prompt_builder.build_chat_readable_messages(messages, **kwargs)


def extract_json_from_llm_response(response: str) -> List[Dict]:
    """便携的JSON提取函数"""
    return prompt_builder.extract_json_from_response(response)


def clean_llm_response(text: str) -> str:
    """便携的响应清理函数"""
    return prompt_builder.clean_response_text(text)


# ==================== 使用示例 ====================

if __name__ == "__main__":
    # 使用示例
    async def example_usage():
        # 1. 构建回复提示词
        reply_prompt = await build_reply_prompt(
            sender_name="张三",
            chat_history="张三: 今天天气怎么样？\n李四: 很不错，阳光明媚",
            target_message="今天天气怎么样？",
            expression_habits=["当询问天气时，使用轻松愉快的语气"],
            knowledge_info="今天是晴天，温度25度",
            group_name="技术交流群"
        )
        print("回复提示词:", reply_prompt)
        
        # 2. 构建中断回复提示词
        interrupted_prompt = await build_interrupted_reply_prompt(
            previous_reply_context="我刚才想说今天天气很好",
            target_message="你觉得明天会下雨吗？"
        )
        print("中断回复提示词:", interrupted_prompt)
        
        # 3. 格式化聊天消息
        messages = [
            {"user_nickname": "张三", "processed_plain_text": "你好", "time": time.time()},
            {"user_nickname": "Nbot", "processed_plain_text": "你好！", "time": time.time()}
        ]
        formatted = format_chat_messages(messages, show_timestamp=True)
        print("格式化消息:", formatted)
        
        # 4. 提取JSON响应
        llm_response = """
        ```json
        {"action": "reply", "reason": "用户问候"}
        ```
        """
        extracted = extract_json_from_llm_response(llm_response)
        print("提取的JSON:", extracted)
    
    # 运行示例
    asyncio.run(example_usage())
