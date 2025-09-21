import asyncio
import json
import os
from typing import Dict, Optional, Any
from dataclasses import dataclass
from communication.boxim import *
from printstream import print_stream

@dataclass
class BotConfig:
    """机器人配置类"""
    username: str
    password: str
    auto_reply_enabled: bool = True
    log_self_messages: bool = False
    
    @classmethod
    def from_env(cls):
        """从环境变量读取配置"""
        return cls(
            username=os.getenv('BOT_USERNAME', 'Nbot'),
            password=os.getenv('BOT_PASSWORD', 'a31415926535'),
            auto_reply_enabled=os.getenv('AUTO_REPLY', 'true').lower() == 'true',
            log_self_messages=os.getenv('LOG_SELF_MESSAGES', 'false').lower() == 'true'
        )

class MessageFormatter:
    """消息格式化工具类"""
    
    @staticmethod
    def format_message_type(msg_type: int) -> str:
        """格式化消息类型"""
        try:
            return MessageType(msg_type).name
        except ValueError:
            return f"未知类型({msg_type})"
    
    @staticmethod
    def parse_json_content(content: str, default_msg: str) -> str:
        """解析JSON格式的消息内容"""
        try:
            return json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return default_msg
    
    @classmethod
    def parse_image_content(cls, content: str) -> str:
        """解析图片消息"""
        data = cls.parse_json_content(content, {})
        return f"[图片] {data.get('originUrl', '无URL')}"
    
    @classmethod
    def parse_file_content(cls, content: str) -> str:
        """解析文件消息"""
        data = cls.parse_json_content(content, {})
        name = data.get('name', '未知文件')
        size = data.get('size', 0)
        return f"[文件] {name} ({size}字节)"
    
    @classmethod
    def parse_voice_content(cls, content: str) -> str:
        """解析语音消息"""
        data = cls.parse_json_content(content, {})
        duration = data.get('duration', 0)
        return f"[语音] {duration}秒"
    
    @classmethod
    def parse_video_content(cls, content: str) -> str:
        """解析视频消息"""
        data = cls.parse_json_content(content, {})
        return f"[视频] {data.get('videoUrl', '无URL')}"
    
    @classmethod
    def format_content_by_type(cls, content: str, msg_type: int) -> str:
        """根据消息类型格式化内容"""
        content_parsers = {
            MessageType.TEXT.value: lambda x: x,
            MessageType.IMAGE.value: cls.parse_image_content,
            MessageType.FILE.value: cls.parse_file_content,
            MessageType.VOICE.value: cls.parse_voice_content,
            MessageType.VIDEO.value: cls.parse_video_content,
        }
        
        parser = content_parsers.get(msg_type)
        if parser:
            return parser(content)
        else:
            type_name = cls.format_message_type(msg_type)
            return f"[{type_name}] {str(content)[:50]}..."

class ContactManager:
    """联系人管理器"""
    
    def __init__(self):
        self.friends: Dict[int, str] = {}
        self.groups: Dict[int, str] = {}
        self.user_id: Optional[int] = None
    
    async def initialize(self) -> bool:
        """初始化联系人信息"""
        try:
            print_stream("正在获取好友列表...")
            self.friends = await get_friend_list() or {}
            print_stream(f"获取到 {len(self.friends)} 个好友")
            
            print_stream("正在获取群组列表...")
            self.groups = await get_group_list() or {}
            print_stream(f"获取到 {len(self.groups)} 个群组")
            
            self.user_id = get_user_id()
            print_stream("联系人信息初始化完成!")
            return True
            
        except Exception as e:
            print_stream(f"初始化联系人失败: {e}")
            return False
    
    def get_friend_name(self, user_id: int) -> str:
        """获取好友名称"""
        if not user_id:
            return "未知用户"
        return self.friends.get(int(user_id), f"未知用户({user_id})")
    
    def get_group_name(self, group_id: int) -> str:
        """获取群组名称"""
        if not group_id:
            return "未知群组"
        return self.groups.get(int(group_id), f"未知群组({group_id})")
    
    def is_self_message(self, sender_id: int) -> bool:
        """判断是否是自己发送的消息"""
        return self.user_id and int(sender_id) == int(self.user_id)

class MessageCache:
    """消息缓存管理器"""
    
    def __init__(self, max_size: int = 1000):
        self.private_messages: Dict[int, str] = {}
        self.group_messages: Dict[int, str] = {}
        self.max_size = max_size
    
    def store_private_message(self, message_id: int, content: str):
        """存储私聊消息"""
        self._store_message(self.private_messages, message_id, content)
    
    def store_group_message(self, message_id: int, content: str):
        """存储群聊消息"""
        self._store_message(self.group_messages, message_id, content)
    
    def _store_message(self, storage: Dict[int, str], message_id: int, content: str):
        """存储消息的通用方法"""
        if len(storage) >= self.max_size:
            # 删除最旧的消息
            oldest_key = next(iter(storage))
            del storage[oldest_key]
        storage[message_id] = content
    
    def get_private_message(self, message_id: int) -> str:
        """获取私聊消息"""
        return self.private_messages.get(message_id, "未知消息")
    
    def get_group_message(self, message_id: int) -> str:
        """获取群聊消息"""
        return self.group_messages.get(message_id, "未知消息")

class AutoReplyHandler:
    """自动回复处理器"""
    
    def __init__(self, config: BotConfig, contact_manager: ContactManager):
        self.config = config
        self.contact_manager = contact_manager
    
    async def handle_private_auto_reply(self, content: str, sender_id: int):
        """处理私聊自动回复"""
        if not self.config.auto_reply_enabled:
            return
        
        trigger_words = ['hello', 'hi', '你好', 'Hi', 'Hello']
        if any(word in content for word in trigger_words):
            sender_name = self.contact_manager.get_friend_name(sender_id)
            reply_text = f"Hello {sender_name}! 你好! 👋"
            await send_private_text(sender_id, reply_text)
            print_stream(f"🤖 自动回复给 {sender_name}")
    
    async def handle_group_auto_reply(self, content: str, sender_id: int, group_id: int, at_user_ids: list):
        """处理群聊自动回复"""
        if not self.config.auto_reply_enabled:
            return
        
        sender_name = self.contact_manager.get_friend_name(sender_id)
        group_name = self.contact_manager.get_group_name(group_id)
        
        # 命令式回复
        if content.startswith('/hello'):
            await send_group_text(group_id, f"Hello {sender_name}! 🎉")
            print_stream(f"在群 {group_name} 自动回复给 {sender_name}")
        
        # 被@时的回复
        elif self.contact_manager.user_id in at_user_ids and "你好" in content:
            await send_group_text(group_id, f"@{sender_name} 你好! 我是机器人 🤖")
            print_stream(f"回复@消息给 {sender_name}")

class BoxIMBot:
    """BoxIM机器人主类"""
    
    def __init__(self, config: BotConfig):
        self.config = config
        self.contact_manager = ContactManager()
        self.message_cache = MessageCache()
        self.auto_reply = AutoReplyHandler(config, self.contact_manager)
        self.formatter = MessageFormatter()
        self.is_running = False
    
    async def login(self) -> bool:
        """登录到BoxIM"""
        try:
            print_stream("正在登录...")
            success = await login(self.config.username, self.config.password)
            if not success:
                print_stream(f"登录失败: {get_last_error()}")
                return False
            
            print_stream(f"登录成功! 用户ID: {get_user_id()}")
            return True
            
        except Exception as e:
            print_stream(f"登录异常: {e}")
            return False
    
    async def initialize(self) -> bool:
        """初始化机器人"""
        if not await self.login():
            return False
        
        if not await self.contact_manager.initialize():
            return False
        
        self._register_handlers()
        self.is_running = True
        
        # 显示统计信息
        print_stream(f"统计信息:")
        print_stream(f"   好友数量: {len(self.contact_manager.friends)}")
        print_stream(f"   群组数量: {len(self.contact_manager.groups)}")
        print_stream(f"   当前用户ID: {self.contact_manager.user_id}")
        
        return True
    
    def _register_handlers(self):
        """注册消息处理器"""
        
        @on_private_message
        async def handle_private_message(message_data):
            await self._handle_private_message(message_data)
        
        @on_group_message  
        async def handle_group_message(message_data):
            await self._handle_group_message(message_data)
        
        @on_message_type(MessageType.IMAGE)
        async def handle_image_message(message_data, is_group):
            await self._handle_media_message(message_data, is_group, "🖼 图片")
        
        @on_message_type(MessageType.FILE)
        async def handle_file_message(message_data, is_group):
            await self._handle_media_message(message_data, is_group, "📁 文件")
        
        @on_message_type(MessageType.VOICE)
        async def handle_voice_message(message_data, is_group):
            await self._handle_media_message(message_data, is_group, "🎵 语音")
        
        @on_message_type(MessageType.VIDEO)
        async def handle_video_message(message_data, is_group):
            await self._handle_media_message(message_data, is_group, "🎬 视频")
    
    async def _handle_private_message(self, message_data: Dict[str, Any]):
        """处理私聊消息"""
        try:
            sender_id = message_data.get('sendId')
            content = message_data.get('content', '')
            message_id = message_data.get('id')
            content_data = json.loads(content)
            tmp_id = message_data.get('tmpId')
            online = content_data.get('online','')
            terminal = content_data.get('turminal','')
            userId = content_data.get('userId','')
            
            # 跳过系统消息和自己的消息
            if (not self.config.log_self_messages and 
                self.contact_manager.is_self_message(sender_id)):
                return
            
            sender_name = self.contact_manager.get_friend_name(sender_id)
            
            # 存储消息
            if message_id:
                self.message_cache.store_private_message(message_id, str(content))
            
            if online is not None and terminal is not None and userId is not None:
                print_stream(f'{sender_name}在{"PC" if terminal == "1" else "手机"}上{"上线" if online else "下线"}')
                return
            elif not tmp_id and content:
                recalled_content = self.message_cache.get_private_message(int(content))
                print_stream(f"🔄 {sender_name} 撤回了一条消息: {recalled_content}")
                return
                
            print_stream(f'💌 私聊消息 - {sender_name}: {content}')
            
            # 自动回复
            await self.auto_reply.handle_private_auto_reply(str(content), sender_id)
            
        except Exception as e:
            print_stream(f"处理私聊消息时出错: {e}")
    
    async def _handle_group_message(self, message_data: Dict[str, Any]):
        """处理群聊消息"""
        try:
            content = message_data.get('content', '')
            sender_id = message_data.get('sendId')
            group_id = message_data.get('groupId')
            message_id = message_data.get('id')
            quote_message = message_data.get('quoteMessage', {})
            at_user_ids = message_data.get('atUserIds', [])
            tmp_id = message_data.get('tmpId')
            
            # 跳过自己的消息
            if (not self.config.log_self_messages and 
                self.contact_manager.is_self_message(sender_id)):
                return
            
            sender_name = self.contact_manager.get_friend_name(sender_id)
            group_name = self.contact_manager.get_group_name(group_id)
            
            # 存储消息
            if message_id:
                self.message_cache.store_group_message(message_id, str(content))
            
            # 处理撤回消息
            if not tmp_id and message_id:
                recalled_content = self.message_cache.get_group_message(int(content))
                print_stream(f"🔄 {sender_name} 在 {group_name} 撤回了一条消息: {recalled_content}")
                return
            
            # 构建消息显示
            message_parts = [f"👥 群聊消息 - {group_name} - {sender_name}: {content}"]
            
            # 处理引用消息
            if quote_message and isinstance(quote_message, dict):
                quote_sender_id = quote_message.get('sendId')
                quote_content = quote_message.get('content', '')
                if quote_sender_id:
                    quote_sender_name = self.contact_manager.get_friend_name(quote_sender_id)
                    message_parts.append(f" [回复 {quote_sender_name}: {quote_content[:30]}...]")
            
            # 处理@信息
            if at_user_ids:
                at_names = [self.contact_manager.get_friend_name(uid) 
                           for uid in at_user_ids 
                           if uid != self.contact_manager.user_id]
                if at_names:
                    message_parts.append(f" [@{', '.join(at_names)}]")
                
                # 检查是否@了自己
                if self.contact_manager.user_id in at_user_ids:
                    print_stream(f"🔔 您在群 {group_name} 中被 {sender_name} @了!")
            
            print_stream(''.join(message_parts))
            
            # 自动回复
            await self.auto_reply.handle_group_auto_reply(
                str(content), sender_id, group_id, at_user_ids
            )
            
        except Exception as e:
            print_stream(f"处理群聊消息时出错: {e}")
    
    async def _handle_media_message(self, message_data: Dict[str, Any], is_group: bool, media_type: str):
        """处理媒体消息"""
        sender_id = message_data.get('sendId')
        
        if (not self.config.log_self_messages and 
            self.contact_manager.is_self_message(sender_id)):
            return
        
        sender_name = self.contact_manager.get_friend_name(sender_id)
        chat_type = "群聊" if is_group else "私聊"
        print_stream(f"{media_type} {chat_type}消息 - {sender_name}")
    
    async def start(self):
        """启动机器人"""
        try:
            print_stream("🚀 BoxIM 客户端启动中...")
            
            if not await self.initialize():
                print_stream("❌ 初始化失败，无法继续")
                return False
            
            print_stream("👂 开始监听消息...")
            print_stream("=" * 50)
            
            await start()
            
        except KeyboardInterrupt:
            print_stream("\n⏹️ 收到中断信号，正在停止...")
        except Exception as e:
            print_stream(f"❌ 运行出错: {e}")
            import traceback
            print_stream(f"详细错误信息: {traceback.format_exc()}")
        finally:
            await self.stop()
    
    async def stop(self):
        """停止机器人"""
        if self.is_running:
            print_stream("🛑 正在停止客户端...")
            await stop()
            self.is_running = False
            print_stream("✅ 客户端已停止")

def create_bot_from_config() -> BoxIMBot:
    """从配置创建机器人实例"""
    config = BotConfig.from_env()
    return BoxIMBot(config)

def run_bot_from_config():
    """便捷启动函数（从配置）"""
    bot = create_bot_from_config()
    
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        print_stream("\n👋 程序已退出")
    except Exception as e:
        print_stream(f"❌ 程序异常退出: {e}")

async def main():
    """主函数"""
    # 直接使用硬编码配置（向后兼容）
    config = BotConfig(
        username="Nbot",
        password="a31415926535",
        auto_reply_enabled=True
    )
    
    bot = BoxIMBot(config)
    await bot.start()

if __name__ == "__main__":
    # 优先尝试从环境变量读取配置
    if os.getenv('BOT_USERNAME','Nbot') and os.getenv('BOT_PASSWORD','a31415926535'):
        run_bot_from_config()
    else:
        # 使用硬编码配置
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print_stream("\n👋 程序已退出")
        except Exception as e:
            print_stream(f"❌ 程序异常退出: {e}")
