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

# API 密钥列表
API_KEYS = [
    "cpk_70904349dba84c3c925ce69073ae9b4a.981ca8d3a43e52499ddea8a143ff5b2e.eWI6WR2hbpQbhVnUxXWQ6cPnFOpTRe9C",
    "cpk_314776b8c72f47aa94915064d162ff32.bc67675a2add5ecdb629a67fbe4a696f.fV8LcaLLVCAVHTczOm5QGsZ1SC7MS9kK",
    "cpk_0a2820dba47449ccaa9b5662a276061f.c1963416b81a512e8f647dde72a25982.2MKMWu4xhb0veIxgysJ6Uevy2Kyx6bL0",
    "cpk_6f527339300e41bca7e6b8f01ec44a83.9be8071c5aa9553c98740b8eadac7548.bHHWvnozbBopyp7Qt6ZNJ6iErc7VH8rq",
    "cpk_f6e1434b53f94c12949f2f3392ddcf9c.fff65cec4ebb5fc38403ae87862eeef4.okpdUq7s8YUbRKJ7ZiFGhMWr2Am7QswX",
    "cpk_7fc233244b294c6cb2a007371e1a2c37.1e75159579d45e589ab420de5236a80c.4Se9h81o8W1fIo43VOtDWNDkQuz8YXLG",
    "cpk_e2f07d68aa5c448bbb991db88719ba65.fe2db66a0f88585e8abe6a3e93ecfa6e.orPo9hFFloxMxhkUDFkKZ3Krqczt83b1",
    "cpk_4db825732b544a4db0a28528a8b00016.69a2318bd5cd506287d552beba80efc7.v3pnldgfEoSsLKvAPun1jmhAN1K9BGTZ",
    "cpk_895f59b1e7f04c368c6f50ef5bdefd52.c0678258ab6a584a9ab1634de01b94a9.3CpAHzOmPjJLq0R7W6BYkehvMiV2qJrq",
    "cpk_f1cda143ee064350a722abe47ee48ebb.df97717739e555ba8d0b371e98074212.93iqdVxPnqr8oyfnRTuKgWX3cRpUwF8a",
    "cpk_4d09acc7d5454ab2b8c060ba59e8a9e9.578b1d99f61159339b1723658b743df8.5W4DXiD5lZg5QfB5g9nLduARV07ExlkZ",
    "cpk_0e44b056d16a46bba4632611457101ef.b203eec3cdaf56e69e04bad94db840d0.jau7icacF7QZkmqtOl5kM5FagKGKMGTl",
    "cpk_88434c77c443459684ec9d33a944bf76.8c5097cba29e5213a6fcc94d8de6ca53.D5IkbyO8ShxIAap3dl5tqjzOtMaeY8oh",
    "cpk_ece9b06b74864b319229c4979dcbaa82.0b615e7058265bef8c8ab42089fe69cd.Lay448kBE1EURQ7OAiN1vSf4PNkye45y",
    "cpk_6071ec521b8c4c6c97ae142e78710ff3.285840b8881352fd8edd9d35f0202adc.3N0zFASdb90GFKkMHEs4CnXZVstYdPNM",
    "cpk_c1bab9e543bb43578525d8ef086f889d.cf8a1974d0035408a2f6ba6f9767af2e.oOUvpXBAQUnpLafaSMvt36mALdNIHzWg",
    "cpk_5881712853cf4f5da3ee68190a8ab73f.04c83c1fe2d157ef8625d344477284ac.qzARAvfuYv2BApd9ZTtrYwRayufson42",
    "cpk_e2295994cde24e36827753367341e941.2e89714093f55d69a8c5b10cf08d028c.wIeYMZ3blMt1RJSljtgfocJYfoudpKVk",
    "cpk_30b976c0be3d4d0191703501c50b71e3.9b133f48caba534792da5d9ed40515d7.lGaoJwgha6A28QyXii69JRiHJeD6lMDT",
    "cpk_cab557d555fa4a70b22830ab6eafc86d.f563387a7461597d835b147ce62c8445.BbiGHKUftKCy5wZZF37tJfHQIUMz21z0",
    "cpk_a6a2ee4af917427996889d49af799ca0.1bb46f3b28195b24bc77ec874efa9783.UC68Jd7vxGs2qcuyKTcuDhbqRQvv6SRY",
    "cpk_6246eea3b01f456b91359ce5669a3e25.e09fadbf3c205c5b9c0a9f5ff2b81fe6.7Fn6TsPHjiWyZz0xEJWiKLOHJaqUI9TZ",
    "cpk_eca51b8d40d44302a5a711eee364fd5e.71310b7819d4559ebd93e61b5238e31b.mRcM2E203EMAZK4A5IOxJCSvex9k2nfW",
    "cpk_ea8068956ee149e48eb8c170e4a41609.d4710fefff5c570ba79f07c402277c3b.kXARyr8TqOZUPkjGU8oemzZQekuxAQS1",
    "cpk_edc52e7b2777444ebab54ba30e7e62f3.3d696a359c2358c6ad02d2f2c9bcaa8e.yH5Bwn8vwNuOKgomVYGBF1z6dsdSFhuN",
    "cpk_2a72f506266a4183a89e8c24149500e4.2740fe0885fb5bd48559622ac5b3bc57.Id884hgOKw2noAQ6e3i7mnHjDnN7rQLj",
    "cpk_8b46caa3a76a41e889dd34c94b56c503.cd7b791918145e8ab2b95152fe38734a.Mhh6VhQj6aBptnrARoDH3yv4Sln5a9MO",
    "cpk_951589ae5d9d4865ad4797fa20f94ba2.71d091d72dc95bcab747ae7a0cf3d9d4.jcoFlanPbBam4S0TTSY8ToGSBrZqLCOE",
    "cpk_9ba6ea4e52734f74a28e66c35a232e75.11db96d1075c50fc8f0a8d6046e90e02.tjpYIODHKu5lg8xbyxeutRVU1ZdmBhjl",
    "cpk_c8690965a39a40b7981e88400d3cfb96.221bc6de2dc658cbb959ad64fe46dfd8.TzA5rdegm9PvBvlx4TBAHFX0vdPTLDRr"
]

# 失败的密钥集合
failed_keys = set()

class ChutesClient:
    def __init__(self, max_concurrent: int = 5):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
    def get_available_key(self) -> Optional[str]:
        """获取可用的API密钥"""
        available_keys = [key for key in API_KEYS if key not in failed_keys]
        if not available_keys:
            return None
        return random.choice(available_keys)
    
    async def chat_stream(self, prompt: str, temperature: float = 0.2) -> AsyncGenerator[str, None]:
        """流式聊天"""
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
