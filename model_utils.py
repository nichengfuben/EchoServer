# model_utils.py
import aiohttp
import asyncio
import json
import time
import sys
import os
from typing import Optional, List, Dict, Any, AsyncGenerator
from dotenv import load_dotenv
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if __name__ != "__main__":
    from __main__ import *
else:
    from printstream import *

BASE_URL = "http://localhost:8000"

async def chat(message: str, files: Optional[List[str]] = None, model: str = "auto_chat", temperature: float = 0.7) -> str:
    """非流式聊天"""
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
        
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{BASE_URL}/v1/chat/completions", json=payload) as response:
                result = await response.json()
                if response.status == 200:
                    return result['choices'][0]['message']['content']
                else:
                    return f"请求失败: {response.status}"
    except Exception as e:
        return f"聊天请求失败: {e}"

async def chat_stream_func(message: str, files: Optional[List[str]] = None, model: str = "auto_chat", temperature: float = 0.7) -> AsyncGenerator[str, None]:
    """流式聊天"""
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
        
        async with aiohttp.ClientSession() as session:
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

async def chat_stream(message: str, files: Optional[List[str]] = None, model: str = "auto_chat", temperature: float = 0.7, generator_count: int = 2) -> AsyncGenerator[str, None]:
    """带有冗余的流式聊天，提高响应速度"""
    start_time = time.time()
    async def stream_to_queue(gen_func, queue, gen_id):
        """将生成器的输出放入队列"""
        try:
            async for token in gen_func:
                await queue.put((gen_id, token))
            await queue.put((gen_id, None))  # 结束标记
        except Exception as e:
            await queue.put((gen_id, f"生成器{gen_id}错误: {e}"))
            await queue.put((gen_id, None))
    
    # 获取当前事件循环
    loop = asyncio.get_running_loop()
    queue = asyncio.Queue()
    tasks = []
    
    try:
        # 根据generator_count创建多个生成器
        for i in range(generator_count):
            gen = chat_stream_func(message, files, model, temperature)
            # 使用当前事件循环创建任务
            task = loop.create_task(stream_to_queue(gen, queue, i + 1))
            tasks.append(task)
        
        # 等待第一个token，选定最快的生成器
        chosen_gen_id = None
        first_token = None
        
        # 尝试从所有生成器中获取第一个有效token
        for _ in range(generator_count):
            gen_id, token = await queue.get()
            if token is not None and not isinstance(token, str) or (isinstance(token, str) and not token.startswith("生成器")):
                chosen_gen_id = gen_id
                first_token = token
                break
        
        if chosen_gen_id is None:
            yield "所有生成器都未能产生内容"
            return
        
        print_stream(f"[MODEL] 选中生成器{chosen_gen_id}号（共{generator_count}个），首包延迟：{time.time()-start_time:.3f}秒")
        yield first_token
        
        # 继续从选中的生成器获取token
        while True:
            try:
                gen_id, token = await asyncio.wait_for(queue.get(), timeout=30.0)
                
                if gen_id == chosen_gen_id:
                    if token is None:  # 选中的生成器结束
                        break
                    yield token
                # 忽略非选中生成器的token
                
            except asyncio.TimeoutError:
                yield "响应超时"
                break
                
    except Exception as e:
        yield f"聊天流失败: {e}"
    
    finally:
        # 清理所有任务
        for task in tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

async def text_to_speech(text: str, voice: str = "派蒙") -> str:
    """文本转语音"""
    try:
        payload = {
            "model": "auto_tts",
            "messages": [{"role": "user", "content": text}],
            "voice": voice
        }
        
        async with aiohttp.ClientSession() as session:
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
    try:
        payload = {
            "model": "auto_embedding", 
            "messages": [{"role": "user", "content": text}]
        }
        
        async with aiohttp.ClientSession() as session:
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
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/v1/health") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"error": f"健康检查失败: {response.status}"}
    except Exception as e:
        return {"error": f"健康检查异常: {e}"}

async def get_models() -> List[str]:
    """获取可用模型列表"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/v1/models") as response:
                if response.status == 200:
                    result = await response.json()
                    return [model['id'] for model in result.get('data', [])]
                else:
                    return [f"获取模型列表失败: {response.status}"]
    except Exception as e:
        return [f"获取模型列表异常: {e}"]
