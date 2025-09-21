# model_utils.py
import aiohttp
import asyncio
import json
import time
import sys
import os
from typing import Optional, List, Dict, Any, AsyncGenerator
from client.client_server import *
class Server:
    def __init__(self, host='0.0.0.0', port=8000):
        self.host = host
        self.port = port
        self.task: Optional[asyncio.Task] = None
        self.running = False

    async def _run(self):
        try:
            self.running = True
            await app.run_task(host=self.host, port=self.port)
        except Exception as e:
            print(f"服务器运行出错: {e}")
            self.running = False
            raise

    async def start(self):
        try:
            if self.task and not self.task.done():
                return self.task
            self.task = asyncio.create_task(self._run())
            await asyncio.sleep(0.1)
            return self.task
        except Exception as e:
            print(f"启动服务器失败: {e}")
            return None

    async def stop(self):
        try:
            if self.task and not self.task.done():
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    pass
                self.running = False
        except Exception as e:
            print(f"停止服务器失败: {e}")

# 全局实例
server_instance = Server()

async def start_server_async(host='0.0.0.0', port=8000):
    """异步启动服务器"""
    try:
        server_instance.host, server_instance.port = host, port
        return await server_instance.start()
    except Exception as e:
        print(f"异步启动服务器失败: {e}")
        return None
# 全局配置
BASE_URL = "http://localhost:8000"
session: Optional[aiohttp.ClientSession] = None

async def init_session():
    """初始化会话"""
    global session
    if session is None:
        session = aiohttp.ClientSession()

async def close_session():
    """关闭会话"""
    global session
    if session:
        await session.close()
        session = None

async def ensure_server_running():
    """确保服务器运行"""
    try:   
        # 检查服务器是否已运行
        try:
            await init_session()
            async with session.get(f"{BASE_URL}/v1/health", timeout=2) as response:
                if response.status == 200:
                    return True
        except:
            pass
        
        # 启动服务器
        print("[启动服务器]")
        await start_server_async()
        await asyncio.sleep(2)  # 等待服务器启动
        return True
    except Exception as e:
        print(f"启动服务器失败: {e}")
        return False

async def chat(message: str, files: Optional[List[str]] = None, model: str = "auto_chat", temperature: float = 0.7) -> str:
    """非流式聊天"""
    await ensure_server_running()
    await init_session()
    
    try:
        if files:
            content = [{"type": "text", "text": message}]
            for file_url in files:
                content.append({"type": "file_url", "file_url": {"url": file_url}})
            messages = [{"role": "user", "content": content}]
        else:
            messages = [{"role": "user", "content": message}]
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "temperature": temperature
        }
        
        async with session.post(f"{BASE_URL}/v1/chat/completions", json=payload) as response:
            result = await response.json()
            if response.status == 200:
                return result['choices'][0]['message']['content']
            else:
                return f"请求失败: {response.status}"
    except Exception as e:
        return f"聊天请求失败: {e}"

async def chat_stream(message: str, files: Optional[List[str]] = None, model: str = "auto_chat", temperature: float = 0.7) -> AsyncGenerator[str, None]:
    """流式聊天"""
    await ensure_server_running()
    await init_session()
    
    try:
        if files:
            content = [{"type": "text", "text": message}]
            for file_url in files:
                content.append({"type": "file_url", "file_url": {"url": file_url}})
            messages = [{"role": "user", "content": content}]
        else:
            messages = [{"role": "user", "content": message}]
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": temperature
        }
        
        async with session.post(f"{BASE_URL}/v1/chat/completions", json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                yield f"请求失败: {response.status} - {error_text}"
                return
            
            async for line in response.content:
                line_text = line.decode('utf-8').strip()
                if not line_text or not line_text.startswith('data: '):
                    continue
                
                data = line_text[6:]
                if data == '[DONE]':
                    break
                
                try:
                    chunk = json.loads(data)
                    if 'choices' in chunk and chunk['choices']:
                        delta = chunk['choices'][0].get('delta', {})
                        if 'content' in delta:
                            yield delta['content']
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        yield f"流式聊天失败: {e}"

async def text_to_speech(text: str, voice: str = "派蒙") -> str:
    """文本转语音"""
    await ensure_server_running()
    await init_session()
    
    try:
        payload = {
            "model": "auto_tts",
            "messages": [{"role": "user", "content": text}],
            "voice": voice
        }
        
        async with session.post(f"{BASE_URL}/v1/chat/completions", json=payload) as response:
            if response.status == 200:
                result = await response.json()
                return result.get('file_path', '音频路径未找到')
            else:
                return f"TTS请求失败: {response.status}"
    except Exception as e:
        return f"TTS请求异常: {e}"

async def get_embedding(text: str) -> List[float]:
    """获取文本嵌入向量"""
    await ensure_server_running()
    await init_session()
    
    try:
        payload = {
            "model": "auto_embedding", 
            "messages": [{"role": "user", "content": text}]
        }
        
        async with session.post(f"{BASE_URL}/v1/chat/completions", json=payload) as response:
            if response.status == 200:
                result = await response.json()
                return result['data'][0]['embedding']
            else:
                return []
    except Exception as e:
        return []

async def get_health() -> Dict[str, Any]:
    """获取健康状态"""
    await ensure_server_running()
    await init_session()
    
    try:
        async with session.get(f"{BASE_URL}/v1/health") as response:
            if response.status == 200:
                return await response.json()
            else:
                return {"error": f"健康检查失败: {response.status}"}
    except Exception as e:
        return {"error": f"健康检查异常: {e}"}

async def get_models() -> List[str]:
    """获取可用模型列表"""
    await ensure_server_running()
    await init_session()
    
    try:
        async with session.get(f"{BASE_URL}/v1/models") as response:
            if response.status == 200:
                result = await response.json()
                return [model['id'] for model in result.get('data', [])]
            else:
                return [f"获取模型列表失败: {response.status}"]
    except Exception as e:
        return [f"获取模型列表异常: {e}"]
##async def test():
##    print(await chat("你好"))
##asyncio.run(test())
