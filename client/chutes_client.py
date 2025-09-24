#chutes_client.py
import asyncio
import aiohttp
import json
import time
import random
from typing import AsyncGenerator, Optional

# 配置常量
CHUTES_URL = "https://llm.chutes.ai/v1/chat/completions"
MODEL_NAME = "zai-org/GLM-4.5-Air"
TIMEOUT = 60
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.chutes_accounts import *

# 失败的密钥集合
failed_keys = set()

class ChutesClient:
    def __init__(self, max_concurrent: int = 5):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
    def get_available_key(self) -> Optional[str]:
        """获取可用的API密钥"""
        global failed_keys
        available_keys = [key for key in API_KEYS if key not in failed_keys]
        if not available_keys:
            return None
        return random.choice(available_keys)
    
    async def chat_stream(self, prompt: str, temperature: float = 0.2) -> AsyncGenerator[str, None]:
        """流式聊天"""
        global failed_keys
        api_key = self.get_available_key()
        if not api_key:
            failed_keys = set()
            api_key = self.get_available_key()
            
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        body = {
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "max_tokens": 10000,
            "temperature": temperature
        }
        
        async with self.semaphore:
            timeout = aiohttp.ClientTimeout(total=TIMEOUT)
            
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(CHUTES_URL, headers=headers, json=body) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            print(f"API错误 ({response.status}): {error_text}")
                            failed_keys.add(api_key)
                            raise RuntimeError(f"API调用失败: {error_text}")
                        
                        async for line in response.content:
                            line = line.decode("utf-8").strip()
                            if not line.startswith("data: "):
                                continue
                            
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            
                            try:
                                chunk = json.loads(data)
                                if chunk.get("choices"):
                                    delta = chunk["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                continue
                                
            except Exception as e:
                print(f"流式调用异常: {e}")
                failed_keys.add(api_key)
                raise
    
    async def chat(self, prompt: str, temperature: float = 0.2) -> str:
        """非流式聊天"""
        api_key = self.get_available_key()
        if not api_key:
            raise RuntimeError("没有可用的API密钥")
            
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        body = {
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "max_tokens": 10000,
            "temperature": temperature
        }
        
        async with self.semaphore:
            timeout = aiohttp.ClientTimeout(total=TIMEOUT)
            
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(CHUTES_URL, headers=headers, json=body) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            print(f"API错误 ({response.status}): {error_text}")
                            failed_keys.add(api_key)
                            raise RuntimeError(f"API调用失败: {error_text}")
                        
                        data = await response.json()
                        return data['choices'][0]['message']['content'].strip()
                        
            except Exception as e:
                print(f"非流式调用异常: {e}")
                failed_keys.add(api_key)
                raise

# 便捷函数
async def quick_chat(prompt: str, temperature: float = 0.2) -> str:
    """快速聊天（非流式）"""
    client = ChutesClient()
    return await client.chat(prompt, temperature)

async def quick_chat_stream(prompt: str, temperature: float = 0.2) -> AsyncGenerator[str, None]:
    """快速聊天（流式）"""
    client = ChutesClient()
    async for chunk in client.chat_stream(prompt, temperature):
        yield chunk

# 示例使用
async def main():
    client = ChutesClient()
    
    # 非流式示例
    print("=== 非流式聊天 ===")
    try:
        response = await client.chat("你好，请介绍一下自己")
        print(response)
    except Exception as e:
        print(f"错误: {e}")
    
    print("\n=== 流式聊天 ===")
    # 流式示例
    try:
        async for chunk in client.chat_stream("写一首关于春天的短诗"):
            print(chunk, end="", flush=True)
        print()  # 换行
    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    asyncio.run(main())
