# 文件名：suanli_client.py
import requests
import json
import time
from typing import Optional, Dict, Any, Generator, Tuple

class SuanliClient:
    """算力 API 客户端，支持流式和非流式聊天"""
    
    def __init__(self, 
                 api_key: str = "sk-W0rpStc95T7JVYVwDYc29IyirjtpPPby6SozFMQr17m8KWeo",
                 base_url: str = "https://api.suanli.cn/v1",
                 default_model: str = "free:Qwen3-30B-A3B",
                 timeout: int = 60):
        """
        初始化客户端
        
        Args:
            api_key: API 密钥
            base_url: API 基础 URL
            default_model: 默认模型名称
            timeout: 请求超时时间（秒）
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.default_model = default_model
        self.timeout = timeout
        
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def _build_messages(self, question: str, system: Optional[str] = None) -> list:
        """构建消息列表"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": question})
        return messages
    
    def chat_stream(self, 
                   question: str, 
                   model: Optional[str] = None,
                   system: Optional[str] = None,
                   show_stats: bool = True,
                   **kwargs) -> Optional[str]:
        """
        流式聊天，边生成边输出
        
        Args:
            question: 用户问题
            model: 模型名称，默认使用初始化时的模型
            system: 系统提示词
            show_stats: 是否显示统计信息
            **kwargs: 其他参数（temperature, max_tokens等）
            
        Returns:
            完整的回答文本，如果失败返回 None
        """
        url = f"{self.base_url}/chat/completions"
        model = model or self.default_model
        
        data = {
            "model": model,
            "messages": self._build_messages(question, system),
            "stream": True,
            **kwargs
        }
        
        try:
            if show_stats:
                print("📤 正在发送流式请求...")
            
            start_time = time.time()
            first_token_time = None
            answer = ""
            
            response = requests.post(
                url, headers=self.headers, json=data, 
                timeout=self.timeout, stream=True
            )
            
            if response.status_code != 200:
                error_msg = f"❌ 请求失败: {response.status_code}, {response.text}"
                if show_stats:
                    print(error_msg)
                return None
            
            if show_stats:
                print(f"✅ 已收到响应，状态码: {response.status_code}")
                print("💡 模型开始生成回答：\n")
            
            for line in response.iter_lines():
                if line:
                    text = line.decode('utf-8').strip()
                    if text.startswith("data:"):
                        data_str = text[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            content = chunk["choices"][0]["delta"].get("content", "")
                            if content:
                                # 记录第一个 token 的时间
                                if first_token_time is None:
                                    first_token_time = time.time()
                                    ttft = first_token_time - start_time
                                    if show_stats:
                                        print(f"\n⏱️  首包延迟（TTFT）: {ttft:.2f} 秒\n", end="", flush=True)
                                
                                if show_stats:
                                    print(content, end="", flush=True)
                                answer += content
                        except Exception as e:
                            if show_stats:
                                print(f"\n⚠️  解析 chunk 失败: {e}")
                            continue
            
            end_time = time.time()
            total_time = end_time - start_time
            
            if show_stats:
                print("\n\n✅ 流式回答结束。")
                print(f"📊 统计信息:")
                if first_token_time:
                    print(f"   └── 首包延迟（TTFT）: {ttft:.2f} 秒")
                print(f"   └── 总耗时: {total_time:.2f} 秒")
                print(f"   └── 回答长度: {len(answer)} 字符")
            
            return answer
            
        except requests.exceptions.ReadTimeout:
            total_time = time.time() - start_time
            error_msg = f"\n❌ 读取超时：服务器在 {self.timeout} 秒内未完成响应（总耗时: {total_time:.2f} 秒）"
            if show_stats:
                print(error_msg)
            return None
        except Exception as e:
            total_time = time.time() - start_time
            error_msg = f"\n❌ 异常: {e}（耗时: {total_time:.2f} 秒）"
            if show_stats:
                print(error_msg)
            return None
    
    def chat(self, 
             question: str, 
             model: Optional[str] = None,
             system: Optional[str] = None,
             show_stats: bool = True,
             **kwargs) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        非流式聊天，一次性返回完整结果
        
        Args:
            question: 用户问题
            model: 模型名称，默认使用初始化时的模型
            system: 系统提示词
            show_stats: 是否显示统计信息
            **kwargs: 其他参数（temperature, max_tokens等）
            
        Returns:
            (回答文本, 统计信息字典)，如果失败回答文本为 None
        """
        url = f"{self.base_url}/chat/completions"
        model = model or self.default_model
        
        data = {
            "model": model,
            "messages": self._build_messages(question, system),
            "stream": False,
            **kwargs
        }
        
        stats = {
            "success": False,
            "total_time": 0,
            "status_code": None,
            "token_count": 0,
            "answer_length": 0
        }
        
        try:
            if show_stats:
                print("📤 正在发送非流式请求...")
            
            start_time = time.time()
            
            response = requests.post(
                url, headers=self.headers, json=data, 
                timeout=self.timeout
            )
            
            end_time = time.time()
            total_time = end_time - start_time
            stats["total_time"] = total_time
            stats["status_code"] = response.status_code
            
            if response.status_code != 200:
                error_msg = f"❌ 请求失败: {response.status_code}, {response.text}"
                if show_stats:
                    print(error_msg)
                return None, stats
            
            result = response.json()
            answer = result["choices"][0]["message"]["content"]
            
            # 更新统计信息
            stats["success"] = True
            stats["answer_length"] = len(answer)
            if "usage" in result:
                stats["token_count"] = result["usage"].get("total_tokens", 0)
            
            if show_stats:
                print(f"✅ 请求成功，状态码: {response.status_code}")
                print(f"💡 完整回答：\n{answer}")
                print(f"\n📊 统计信息:")
                print(f"   └── 总耗时: {total_time:.2f} 秒")
                print(f"   └── 回答长度: {len(answer)} 字符")
                if stats["token_count"] > 0:
                    print(f"   └── Token 数量: {stats['token_count']}")
            
            return answer, stats
            
        except requests.exceptions.ReadTimeout:
            total_time = time.time() - start_time
            stats["total_time"] = total_time
            error_msg = f"\n❌ 请求超时：服务器在 {self.timeout} 秒内未响应（总耗时: {total_time:.2f} 秒）"
            if show_stats:
                print(error_msg)
            return None, stats
        except Exception as e:
            total_time = time.time() - start_time
            stats["total_time"] = total_time
            error_msg = f"\n❌ 异常: {e}（耗时: {total_time:.2f} 秒）"
            if show_stats:
                print(error_msg)
            return None, stats
    
    def chat_stream_generator(self, 
                            question: str, 
                            model: Optional[str] = None,
                            system: Optional[str] = None,
                            **kwargs) -> Generator[str, None, None]:
        """
        流式聊天生成器，逐个yield内容块
        
        Args:
            question: 用户问题
            model: 模型名称
            system: 系统提示词
            **kwargs: 其他参数
            
        Yields:
            每个内容块的文本
        """
        url = f"{self.base_url}/chat/completions"
        model = model or self.default_model
        
        data = {
            "model": model,
            "messages": self._build_messages(question, system),
            "stream": True,
            **kwargs
        }
        
        try:
            response = requests.post(
                url, headers=self.headers, json=data, 
                timeout=self.timeout, stream=True
            )
            
            if response.status_code != 200:
                yield f"❌ 请求失败: {response.status_code}"
                return
            
            for line in response.iter_lines():
                if line:
                    text = line.decode('utf-8').strip()
                    if text.startswith("data:"):
                        data_str = text[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            content = chunk["choices"][0]["delta"].get("content", "")
                            if content:
                                yield content
                        except Exception:
                            continue
                            
        except Exception as e:
            yield f"❌ 异常: {e}"


# === 使用示例 ===
if __name__ == "__main__":
    # 初始化客户端
    client = SuanliClient()
    
    question = "如何看待人工智能的发"
    
    print("=" * 50)
    print("🔄 测试流式聊天")
    print("=" * 50)
    print(f"❓ 提问: {question}\n")
    
    # 流式聊天
    stream_result = client.chat_stream(question)
    
    print("\n" + "=" * 50)
    print("📋 测试非流式聊天")
    print("=" * 50)
    print(f"❓ 提问: {question}\n")
    
    # 非流式聊天
    chat_result, stats = client.chat(question)
    
    print("\n" + "=" * 50)
    print("🔧 测试生成器模式")
    print("=" * 50)
    print(f"❓ 提问: {question}\n")
    print("💡 生成器输出：")
    
    # 生成器模式（适合自定义处理）
    for chunk in client.chat_stream_generator(question):
        print(chunk, end="", flush=True)
    
    print("\n\n✅ 所有测试完成！")
