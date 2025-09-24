# openrouter_client.py
import asyncio
import aiohttp
import json
import base64
import mimetypes
import os
from typing import AsyncGenerator, Optional, List, Union
from pathlib import Path

# 配置常量
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "x-ai/grok-4-fast:free"
TIMEOUT = 60
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.openrouter_accounts import *

# 失败的密钥集合
failed_keys = set()

class OpenRouterClient:
    def __init__(self, max_concurrent: int = 5):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
    def get_available_key(self) -> Optional[str]:
        """获取可用的API密钥"""
        global failed_keys
        available_keys = [key for key in API_KEYS if key not in failed_keys]
        if not available_keys:
            # 如果没有可用密钥，重置失败集合并重试
            if failed_keys:
                failed_keys.clear()
                available_keys = API_KEYS.copy()
            if not available_keys:
                return None
        return random.choice(available_keys)
    
    def _prepare_image_content(self, image_path_or_url: Union[str, Path]) -> dict:
        """准备图片内容，支持本地文件和URL"""
        if isinstance(image_path_or_url, Path):
            image_path_or_url = str(image_path_or_url)
        
        if image_path_or_url.startswith(('http://', 'https://')):
            # URL图片
            return {
                "type": "image_url",
                "image_url": {
                    "url": image_path_or_url
                }
            }
        else:
            # 本地文件图片
            if not os.path.exists(image_path_or_url):
                raise FileNotFoundError(f"图片文件不存在: {image_path_or_url}")
            
            # 读取图片并编码为base64
            with open(image_path_or_url, 'rb') as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
            
            # 获取MIME类型
            mime_type, _ = mimetypes.guess_type(image_path_or_url)
            if not mime_type:
                mime_type = "image/jpeg"  # 默认类型
            
            return {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{image_data}"
                }
            }
    
    async def chat_stream(self, 
                         prompt: str, 
                         image_paths: Optional[List[Union[str, Path]]] = None,
                         temperature: float = 0.2) -> AsyncGenerator[str, None]:
        """流式聊天，支持多模态"""
        global failed_keys
        api_key = self.get_available_key()
        if not api_key:
            raise RuntimeError("没有可用的API密钥")
            
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com",  # OpenRouter要求
            "X-Title": "OpenRouter Client"
        }
        
        # 构建消息内容
        content = [{"type": "text", "text": prompt}]
        
        # 添加图片内容
        if image_paths:
            for image_path in image_paths:
                image_content = self._prepare_image_content(image_path)
                content.append(image_content)
        
        body = {
            "model": MODEL_NAME,
            "messages": [
                {
                    "role": "user",
                    "content": content
                }
            ],
            "stream": True,
            "max_tokens": 4000,
            "temperature": temperature
        }
        
        async with self.semaphore:
            timeout = aiohttp.ClientTimeout(total=TIMEOUT)
            
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(OPENROUTER_URL, headers=headers, json=body) as response:
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
    
    async def chat(self, 
                  prompt: str, 
                  image_paths: Optional[List[Union[str, Path]]] = None,
                  temperature: float = 0.2) -> str:
        """非流式聊天，支持多模态"""
        global failed_keys
        api_key = self.get_available_key()
        if not api_key:
            raise RuntimeError("没有可用的API密钥")
            
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com",  # OpenRouter要求
            "X-Title": "OpenRouter Client"
        }
        
        # 构建消息内容
        content = [{"type": "text", "text": prompt}]
        
        # 添加图片内容
        if image_paths:
            for image_path in image_paths:
                image_content = self._prepare_image_content(image_path)
                content.append(image_content)
        
        body = {
            "model": MODEL_NAME,
            "messages": [
                {
                    "role": "user",
                    "content": content
                }
            ],
            "stream": False,
            "max_tokens": 4000,
            "temperature": temperature
        }
        
        async with self.semaphore:
            timeout = aiohttp.ClientTimeout(total=TIMEOUT)
            
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(OPENROUTER_URL, headers=headers, json=body) as response:
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
async def quick_chat(prompt: str, 
                    image_paths: Optional[List[Union[str, Path]]] = None,
                    temperature: float = 0.2) -> str:
    """快速聊天（非流式）"""
    client = OpenRouterClient()
    return await client.chat(prompt, image_paths, temperature)

async def quick_chat_stream(prompt: str, 
                           image_paths: Optional[List[Union[str, Path]]] = None,
                           temperature: float = 0.2) -> AsyncGenerator[str, None]:
    """快速聊天（流式）"""
    client = OpenRouterClient()
    async for chunk in client.chat_stream(prompt, image_paths, temperature):
        yield chunk

# 示例使用
async def main():
    client = OpenRouterClient()
    
    # 纯文本示例
    print("=== 纯文本聊天 ===")
    try:
        response = await client.chat("你好，请介绍一下自己")
        print(response)
    except Exception as e:
        print(f"错误: {e}")
    
    # 多模态示例（URL图片）
    print("\n=== 多模态聊天（URL图片）===")
    try:
        image_url = "https://ts1.cn.mm.bing.net/th/id/R-C.987f582c510be58755c4933cda68d525?rik=C0D21hJDYvXosw&riu=http%3a%2f%2fimg.pconline.com.cn%2fimages%2fupload%2fupc%2ftx%2fwallpaper%2f1305%2f16%2fc4%2f20990657_1368686545122.jpg&ehk=netN2qzcCVS4ALUQfDOwxAwFcy41oxC%2b0xTFvOYy5ds%3d&risl=&pid=ImgRaw&r=0"
        response = await client.chat("请用中文描述一下这张图片", [image_url])
        print(response)
    except Exception as e:
        print(f"错误: {e}")
    
    # 流式示例
    print("\n=== 流式聊天 ===")
    try:
        async for chunk in client.chat_stream("写一首关于春天的短诗"):
            print(chunk, end="", flush=True)
        print()  # 换行
    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    import random
    asyncio.run(main())
