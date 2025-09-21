# cerebras_client.py
import asyncio
import random
from typing import AsyncGenerator, Optional, List
from concurrent.futures import ThreadPoolExecutor
from cerebras.cloud.sdk import Cerebras
import logging

# 配置常量
MODEL_NAME = "qwen-3-coder-480b"
MAX_COMPLETION_TOKENS = 65536

# API 密钥列表
API_KEYS = [
    "csk-kwvpx9ndvynjx9mnkemtnj248kphknh3kyc4f8mjddd45fhn",
    "csk-vpdrckhfhdk32thr62jxhjj5e9w3mxw8956vnd3n49dy9e8j",
    "csk-rm23dedtfytx4tt9nv482df4cndyvhd4m4d4hvhyry23nv2m",
    "csk-6dfc9r9cr528t24p356hdywhcfrrmwyp9dem2cpjwk996wxp",
    "csk-p85rdwxxkc9eff5ere3knd59w5jyn4649n8vy36d4n5y39fh",
    "csk-ndkk96499tcc4w9tv9n9cv58ry23nrwx94pctx536y68kmdf",
    "csk-8d38jvpdwye9vxcx2cpnynefmmmr68hccw56e5nhctpw9frx",
    "csk-6hwv3vvk525cm3hjj4vkvkdt4r2k8kxdy38jmp5h9p9hp853",
    "csk-3fyrcwhje9hvdejm3dy5pv6hkk6n8xe9mxjktt8942kw5xrj",
    "csk-twhtwj4n28c2yhkj5vwwnv2d8jcyr6mjrmy6njvvhp35fjr6"
]

# 失败的密钥集合
failed_keys = set()

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CerebrasClient:
    def __init__(self, max_concurrent: int = 5):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent)
        
    def get_available_key(self) -> Optional[str]:
        """获取可用的API密钥"""
        available_keys = [key for key in API_KEYS if key not in failed_keys]
        if not available_keys:
            # 如果没有可用密钥，重置失败集合并重试
            if failed_keys:
                logger.info("重置失败的密钥集合")
                failed_keys.clear()
                available_keys = API_KEYS.copy()
            if not available_keys:
                return None
        return random.choice(available_keys)
    
    def _create_client(self, api_key: str) -> Cerebras:
        """创建Cerebras客户端"""
        return Cerebras(api_key=api_key)
    
    def _sync_chat_stream(self, api_key: str, prompt: str, 
                          temperature: float, top_p: float) -> list:
        """同步流式聊天（内部使用）"""
        client = self._create_client(api_key)
        chunks = []
        
        try:
            stream = client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model=MODEL_NAME,
                stream=True,
                max_completion_tokens=MAX_COMPLETION_TOKENS,
                temperature=temperature,
                top_p=top_p
            )
            
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    chunks.append(chunk.choices[0].delta.content)
                    
        except Exception as e:
            logger.error(f"流式调用失败: {e}")
            failed_keys.add(api_key)
            raise
            
        return chunks
    
    def _sync_chat(self, api_key: str, prompt: str, 
                   temperature: float, top_p: float) -> str:
        """同步非流式聊天（内部使用）"""
        client = self._create_client(api_key)
        
        try:
            response = client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model=MODEL_NAME,
                stream=False,
                max_completion_tokens=MAX_COMPLETION_TOKENS,
                temperature=temperature,
                top_p=top_p
            )
            
            if response.choices and response.choices[0].message:
                return response.choices[0].message.content
            return ""
            
        except Exception as e:
            logger.error(f"非流式调用失败: {e}")
            failed_keys.add(api_key)
            raise
    
    async def chat_stream(self, 
                         prompt: str,
                         temperature: float = 0.7,
                         top_p: float = 0.8) -> AsyncGenerator[str, None]:
        """异步流式聊天"""
        api_key = self.get_available_key()
        if not api_key:
            raise RuntimeError("没有可用的API密钥")
        
        async with self.semaphore:
            loop = asyncio.get_event_loop()
            
            try:
                # 在线程池中运行同步流式聊天
                chunks = await loop.run_in_executor(
                    self.executor,
                    self._sync_chat_stream,
                    api_key,
                    prompt,
                    temperature,
                    top_p
                )
                
                # 逐个yield返回内容
                for chunk in chunks:
                    yield chunk
                    
            except Exception as e:
                logger.error(f"异步流式调用异常: {e}")
                raise
    
    async def chat(self, 
                  prompt: str,
                  temperature: float = 0.7,
                  top_p: float = 0.8) -> str:
        """异步非流式聊天"""
        api_key = self.get_available_key()
        if not api_key:
            raise RuntimeError("没有可用的API密钥")
        
        async with self.semaphore:
            loop = asyncio.get_event_loop()
            
            try:
                # 在线程池中运行同步非流式聊天
                response = await loop.run_in_executor(
                    self.executor,
                    self._sync_chat,
                    api_key,
                    prompt,
                    temperature,
                    top_p
                )
                return response
                
            except Exception as e:
                logger.error(f"异步非流式调用异常: {e}")
                raise
    
    async def batch_chat(self, 
                        prompts: List[str],
                        temperature: float = 0.7,
                        top_p: float = 0.8) -> List[str]:
        """批量异步聊天"""
        tasks = [
            self.chat(prompt, temperature, top_p) 
            for prompt in prompts
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    def __del__(self):
        """清理资源"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)

# 便捷函数
async def quick_chat(prompt: str, 
                    temperature: float = 0.7,
                    top_p: float = 0.8) -> str:
    """快速聊天（非流式）"""
    client = CerebrasClient()
    return await client.chat(prompt, temperature, top_p)

async def quick_chat_stream(prompt: str, 
                           temperature: float = 0.7,
                           top_p: float = 0.8) -> AsyncGenerator[str, None]:
    """快速聊天（流式）"""
    client = CerebrasClient()
    async for chunk in client.chat_stream(prompt, temperature, top_p):
        yield chunk

# 示例使用
async def main():
    client = CerebrasClient()
    
    # 非流式示例
    print("=== 非流式聊天 ===")
    try:
        response = await client.chat("你好，请介绍一下自己，你是谁？")
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
    
    # 批量示例
    print("\n=== 批量聊天 ===")
    try:
        prompts = [
            "1+1等于多少？",
            "Python是什么？",
            "今天天气怎么样？"
        ]
        responses = await client.batch_chat(prompts)
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                print(f"问题 {i+1} 失败: {response}")
            else:
                print(f"问题 {i+1}: {prompts[i]}")
                print(f"回答: {response[:100]}...")  # 只显示前100个字符
                print("-" * 50)
    except Exception as e:
        print(f"批量处理错误: {e}")

# 高级示例：使用不同参数
async def advanced_example():
    client = CerebrasClient(max_concurrent=3)
    
    print("=== 高级示例：不同温度参数 ===")
    
    # 低温度（更确定性）
    print("\n--- 温度 0.2 (更确定) ---")
    response = await client.chat(
        "解释什么是机器学习",
        temperature=0.2,
        top_p=0.9
    )
    print(response[:200] + "...")
    
    # 高温度（更创造性）
    print("\n--- 温度 1.0 (更创造) ---")
    response = await client.chat(
        "解释什么是机器学习",
        temperature=1.0,
        top_p=0.95
    )
    print(response[:200] + "...")

# 错误处理示例
async def error_handling_example():
    client = CerebrasClient()
    
    print("=== 错误处理示例 ===")
    
    # 测试重试机制
    for i in range(3):
        try:
            print(f"\n尝试 {i+1}:")
            response = await client.chat("测试消息")
            print(f"成功: {response[:50]}...")
            break
        except Exception as e:
            print(f"失败: {e}")
            if i == 2:
                print("所有尝试都失败了")

if __name__ == "__main__":
    # 运行基础示例
    asyncio.run(main())
    
    # 运行高级示例
    # asyncio.run(advanced_example())
    
    # 运行错误处理示例
    # asyncio.run(error_handling_example())
