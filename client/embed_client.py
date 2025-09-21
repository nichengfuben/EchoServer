# embed_client.py
import os
import time
import subprocess
import requests
import json
from typing import List, Optional, Dict, Any

# 全局变量用于存储ollama进程
global_ollama_process = None

class EmbedClient:
    def __init__(self, model: str = 'mxbai-embed-large:latest', base_url: str = "http://localhost:11434"):
        """
        初始化嵌入向量客户端
        
        Args:
            model: 使用的模型名称，默认为 'mxbai-embed-large'
            base_url: Ollama服务的基础URL
        """
        self.model = model
        self.base_url = base_url
        
        # 启动ollama服务
        print(self.start_ollama_service())
    
    def start_ollama_service(self, ollama_path: str = r"E:\Users\dell\AppData\Local\Programs\Programs\Ollama\ollama.exe", timeout: int = 10) -> str:
        """启动 Ollama 服务"""
        global global_ollama_process

        if not os.path.exists(ollama_path):
            return f"Ollama可执行文件未找到: {ollama_path}"

        try:
            global_ollama_process = subprocess.Popen(
                [ollama_path],
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    response = requests.get(f"{self.base_url}/api/tags", timeout=2)
                    if response.status_code == 200:
                        return "Ollama服务启动成功"
                except requests.exceptions.RequestException:
                    time.sleep(1)
    
            return f"服务启动超时({timeout}秒)，请手动检查"
    
        except Exception as e:
            return f"服务启动失败: {str(e)}"
    
    def get_embedding(self, text: str) -> List[float]:
        """
        获取单个文本的嵌入向量
        
        Args:
            text: 输入文本
            
        Returns:
            嵌入向量列表
        """
        try:
            url = f"{self.base_url}/api/embeddings"
            payload = {
                "model": self.model,
                "prompt": text
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result.get('embedding', [])
            
        except requests.exceptions.RequestException as e:
            print(f"网络请求错误: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            return []
        except Exception as e:
            print(f"获取嵌入向量时出错: {e}")
            return []
    
    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        批量获取多个文本的嵌入向量
        
        Args:
            texts: 文本列表
            
        Returns:
            嵌入向量列表的列表
        """
        embeddings = []
        for text in texts:
            embedding = self.get_embedding(text)
            embeddings.append(embedding)
            # 添加小延迟避免过快请求
            time.sleep(0.1)
        return embeddings
    
    def similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的余弦相似度
        
        Args:
            text1: 第一个文本
            text2: 第二个文本
            
        Returns:
            相似度分数 (0-1之间)
        """
        try:
            import numpy as np
            
            embedding1 = self.get_embedding(text1)
            embedding2 = self.get_embedding(text2)
            
            if not embedding1 or not embedding2:
                return 0.0
            
            # 计算余弦相似度
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            # 避免除零错误
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            cosine_sim = np.dot(vec1, vec2) / (norm1 * norm2)
            return float(cosine_sim)
        
        except ImportError:
            print("需要安装 numpy: pip install numpy")
            return 0.0
        except Exception as e:
            print(f"计算相似度时出错: {e}")
            return 0.0
    
    def similarity_without_numpy(self, text1: str, text2: str) -> float:
        """
        不使用numpy计算两个文本的余弦相似度
        
        Args:
            text1: 第一个文本
            text2: 第二个文本
            
        Returns:
            相似度分数 (0-1之间)
        """
        try:
            embedding1 = self.get_embedding(text1)
            embedding2 = self.get_embedding(text2)
            
            if not embedding1 or not embedding2 or len(embedding1) != len(embedding2):
                return 0.0
            
            # 手动计算余弦相似度
            dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
            norm1 = sum(a * a for a in embedding1) ** 0.5
            norm2 = sum(b * b for b in embedding2) ** 0.5
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            cosine_sim = dot_product / (norm1 * norm2)
            return float(cosine_sim)
        
        except Exception as e:
            print(f"计算相似度时出错: {e}")
            return 0.0
    
    def check_service_status(self) -> bool:
        """检查Ollama服务状态"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def list_models(self) -> List[str]:
        """列出可用的模型"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            response.raise_for_status()
            
            result = response.json()
            models = []
            for model in result.get('models', []):
                models.append(model.get('name', ''))
            return models
        except Exception as e:
            print(f"获取模型列表时出错: {e}")
            return []

# 使用示例
if __name__ == "__main__":
    # 创建客户端
    client = EmbedClient()
    
    # 检查服务状态
    if not client.check_service_status():
        print("Ollama服务未启动，请检查")
        exit()
    
    # 列出可用模型
    models = client.list_models()
    print(f"可用模型: {models}")
    
    # 获取单个嵌入向量
    embedding = client.get_embedding("你好")
    print(f"嵌入向量维度: {len(embedding)}")
    if embedding:
        print(f"前5个向量值: {embedding[:5]}")
    
    # 批量处理
    texts = ["你好", "Hello", "再见", "Goodbye"]
    embeddings = client.get_embeddings_batch(texts)
    print(f"批量处理了 {len(embeddings)} 个文本")
    
    # 计算相似度（使用numpy版本）
    try:
        similarity_score = client.similarity("你好", "Hello")
        print(f"'你好' 和 'Hello' 的相似度(numpy版本): {similarity_score:.4f}")
    except:
        pass
    
    # 计算相似度（不使用numpy版本）
    similarity_score_no_numpy = client.similarity_without_numpy("你好", "Hello")
    print(f"'你好' 和 'Hello' 的相似度(纯Python版本): {similarity_score_no_numpy:.4f}")
