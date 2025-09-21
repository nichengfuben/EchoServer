# main.py
import time
import json
import aiohttp
import asyncio
import subprocess
import sys
import os
from typing import *
from ui.consoleui import * 
# 导入你的服务器
from client.client_server import app

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

def start_server_sync(host='0.0.0.0', port=8000):
    """同步启动服务器"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(start_server_async(host, port))
    except Exception as e:
        print(f"同步启动服务器失败: {e}")
        return None

# 全局配置
BASE_URL = "http://localhost:8000"
session: Optional[aiohttp.ClientSession] = None

async def init_session():
    try:
        global session
        if session is None:
            session = aiohttp.ClientSession()
    except Exception as e:
        print(f"初始化会话失败: {e}")

async def close_session():
    try:
        global session
        if session:
            await session.close()
            session = None
    except Exception as e:
        print(f"关闭会话失败: {e}")

# 主要的两个便携函数
async def chat(message: str, files: Optional[List[str]] = None, model: str = "nbot_chat", temperature: float = 0.7) -> str:
    """非流式聊天"""
    try:
        await init_session()
        
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
    except aiohttp.ClientError as e:
        return f"网络连接错误: {e}"
    except json.JSONDecodeError as e:
        return f"JSON解析错误: {e}"
    except KeyError as e:
        return f"响应格式错误: {e}"
    except Exception as e:
        return f"聊天请求失败: {e}"

async def chat_stream(message: str, files: Optional[List[str]] = None, model: str = "nbot_chat", temperature: float = 0.7) -> AsyncGenerator[str, None]:
    """流式聊天"""
    try:
        await init_session()
        
        if files:
            content = [{"type": "text", "text": message}]
            for file_url in files:
                content.append({
                    "type": "file_url", 
                    "file_url": {"url": file_url}
                })
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
                try:
                    line_text = line.decode('utf-8').strip()
                    if not line_text:
                        continue
                    if line_text.startswith('data: '):
                        data = line_text[6:]
                        if data == '[DONE]':
                            break
                        chunk = json.loads(data)
                        if 'choices' in chunk and chunk['choices']:
                            delta = chunk['choices'][0].get('delta', {})
                            if 'content' in delta:
                                yield delta['content']
                except json.JSONDecodeError:
                    continue
                except (UnicodeDecodeError, KeyError, IndexError) as e:
                    yield f"[解析错误: {str(e)}]"
                    continue
    except aiohttp.ClientError as e:
        yield f"网络连接错误: {e}"
    except Exception as e:
        yield f"流式聊天失败: {e}"

# 其他功能函数
async def get_health() -> Dict[str, Any]:
    """获取健康状态"""
    try:
        await init_session()
        async with session.get(f"{BASE_URL}/v1/health") as response:
            if response.status == 200:
                return await response.json()
            else:
                return {"error": f"健康检查失败: {response.status}"}
    except aiohttp.ClientError as e:
        return {"error": f"网络连接错误: {e}"}
    except json.JSONDecodeError as e:
        return {"error": f"JSON解析错误: {e}"}
    except Exception as e:
        return {"error": f"健康检查异常: {e}"}

async def get_models() -> List[str]:
    """获取可用模型列表"""
    try:
        await init_session()
        async with session.get(f"{BASE_URL}/v1/models") as response:
            if response.status == 200:
                result = await response.json()
                return [model['id'] for model in result.get('data', [])]
            else:
                return [f"获取模型列表失败: {response.status}"]
    except aiohttp.ClientError as e:
        return [f"网络连接错误: {e}"]
    except json.JSONDecodeError as e:
        return [f"JSON解析错误: {e}"]
    except KeyError as e:
        return [f"响应格式错误: {e}"]
    except Exception as e:
        return [f"获取模型列表异常: {e}"]

async def text_to_speech(text: str, voice: str = "派蒙") -> str:
    """文本转语音"""
    try:
        await init_session()
        payload = {
            "model": "nbot_tts",
            "messages": [{"role": "user", "content": text}],
            "voice": voice
        }
        async with session.post(f"{BASE_URL}/v1/chat/completions", json=payload) as response:
            if response.status == 200:
                result = await response.json()
                return result.get('file_path', '音频路径未找到')
            else:
                return f"TTS请求失败: {response.status}"
    except aiohttp.ClientError as e:
        return f"网络连接错误: {e}"
    except json.JSONDecodeError as e:
        return f"JSON解析错误: {e}"
    except KeyError as e:
        return f"响应格式错误: {e}"
    except Exception as e:
        return f"TTS请求异常: {e}"

async def get_embedding(text: str) -> List[float]:
    """获取文本嵌入向量"""
    try:
        await init_session()
        payload = {
            "model": "nbot_embedding",
            "messages": [{"role": "user", "content": text}]
        }
        async with session.post(f"{BASE_URL}/v1/chat/completions", json=payload) as response:
            if response.status == 200:
                result = await response.json()
                return result['data'][0]['embedding']
            else:
                print(f"嵌入请求失败: {response.status}")
                return []
    except aiohttp.ClientError as e:
        print(f"网络连接错误: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
        return []
    except (KeyError, IndexError) as e:
        print(f"响应格式错误: {e}")
        return []
    except Exception as e:
        print(f"嵌入请求异常: {e}")
        return []

# Nbot相关变量
nbot_process = None
nbot_running = False

async def start_nbot():
    """启动Nbot智能体"""
    global nbot_process, nbot_running
    
    try:
        fontui(" Starting Nbot Intelligence Agent...", "color")
        
        # 确保服务器已启动
        if not server_instance.running:
            fontui(" Starting server first...")
            await start_server_async()
            await asyncio.sleep(2)  # 等待服务器完全启动
        
        # 检查Nbot0.3.8.py是否存在
        nbot_path = os.path.join(os.path.dirname(__file__), "Nbot0.3.8.py")
        if not os.path.exists(nbot_path):
            fontui(f" Error: Nbot0.3.8.py not found at {nbot_path}", "error")
            return
        
        # 启动Nbot进程
        if nbot_process is None or nbot_process.poll() is not None:
            try:
                nbot_process = subprocess.Popen(
                    [sys.executable, nbot_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                nbot_running = True
                fontui(" ✅ Nbot Intelligence Agent started successfully!", "color")
                fontui(f" Process ID: {nbot_process.pid}")
                
                # 启动输出监控任务
                asyncio.create_task(monitor_nbot_output())
                
            except Exception as e:
                fontui(f" Failed to start Nbot process: {e}", "error")
                nbot_running = False
        else:
            fontui(" Nbot is already running!", "color")
            
    except Exception as e:
        fontui(f" Error starting Nbot: {e}", "error")
        nbot_running = False

async def stop_nbot():
    """停止Nbot智能体"""
    global nbot_process, nbot_running
    
    try:
        if nbot_process and nbot_process.poll() is None:
            fontui(" Stopping Nbot Intelligence Agent...")
            nbot_process.terminate()
            
            # 等待进程结束
            try:
                nbot_process.wait(timeout=10)
                fontui(" ✅ Nbot stopped successfully!")
            except subprocess.TimeoutExpired:
                fontui(" Force killing Nbot process...")
                nbot_process.kill()
                nbot_process.wait()
                fontui(" ⚠️ Nbot force terminated!")
            
            nbot_process = None
            nbot_running = False
        else:
            fontui(" Nbot is not running!")
    except Exception as e:
        fontui(f" Error stopping Nbot: {e}", "error")

async def monitor_nbot_output():
    """监控Nbot输出"""
    global nbot_process, nbot_running
    
    try:
        if nbot_process:
            while nbot_process.poll() is None and nbot_running:
                try:
                    # 读取stdout
                    stdout_line = nbot_process.stdout.readline()
                    if stdout_line:
                        fontui(f" [Nbot] {stdout_line.strip()}")
                    
                    # 读取stderr
                    stderr_line = nbot_process.stderr.readline()
                    if stderr_line:
                        fontui(f" [Nbot Error] {stderr_line.strip()}", "error")
                    
                    await asyncio.sleep(0.1)
                except Exception as e:
                    fontui(f" Error reading Nbot output: {e}", "error")
                    break
            
            # 进程结束
            if nbot_process.poll() is not None:
                return_code = nbot_process.returncode
                if return_code == 0:
                    fontui(" Nbot exited normally")
                else:
                    fontui(f" Nbot exited with error code: {return_code}", "error")
                nbot_running = False
                
    except Exception as e:
        fontui(f" Monitor error: {e}", "error")
        nbot_running = False

async def check_nbot_status():
    """检查Nbot状态"""
    global nbot_process, nbot_running
    
    if nbot_process is None:
        return "Not started"
    elif nbot_process.poll() is None:
        return f"Running (PID: {nbot_process.pid})"
    else:
        return f"Stopped (Exit code: {nbot_process.returncode})"

async def restart_nbot():
    """重启Nbot"""
    fontui(" Restarting Nbot Intelligence Agent...")
    await stop_nbot()
    await asyncio.sleep(2)
    await start_nbot()

# 测试函数
async def main_test():
    """测试主函数"""
    try:     
        fontui(" Running test function...", "color")
        
        # 确保服务器运行
        if not server_instance.running:
            await start_server_async()
            await asyncio.sleep(2)
        
        # 基础聊天
        response = await chat("你好，介绍一下你自己")
        fontui(f" 回复: {response}")
        
        # 带图片的聊天
        image_url = "https://www.10wallpaper.com/wallpaper/1920x1080/1503/Beautiful_green_plain_bay-2015_Bing_theme_wallpaper_1920x1080.jpg"
        response = await chat("描述这张图片", files=[image_url])
        fontui(f" 图片描述: {response}")
        
        # 流式聊天
        fontui(" 流式回复:")
        print("  ", end="", flush=True)
        async for chunk in chat_stream("写一首关于AI的诗"):
            print(chunk, end="", flush=True)
        print()
        
        # 其他功能
        models = await get_models()
        fontui(f" 可用模型: {models}")
        
        audio_path = await text_to_speech("这是一个测试语音")
        fontui(f" 音频文件: {audio_path}")
        
        embedding = await get_embedding("测试文本")
        fontui(f" 嵌入维度: {len(embedding)}")
        
        fontui(" Test completed successfully!", "color")
    except Exception as e:
        fontui(f" 测试执行异常: {e}")
    finally:
        await close_session()

async def main_async():
    """异步主函数"""
    try:
        # 自动启动服务器
        fontui(" Auto-starting server...")
        await start_server_async()
        await asyncio.sleep(1)
        
        # 注册命令
        register_command("test", main_test, "Run test function")
        register_command("start", start_nbot, "Start Nbot Intelligence Agent")
        register_command("stop", stop_nbot, "Stop Nbot Intelligence Agent") 
        register_command("restart", restart_nbot, "Restart Nbot Intelligence Agent")
        register_command("status", lambda: fontui(f" Nbot Status: {asyncio.create_task(check_nbot_status())}", "color"), "Check Nbot status")
        
        # 运行控制台
        await console_main_async()
        
    except Exception as e:
        print(f"程序执行失败: {e}")

async def console_main_async():
    """异步版本的控制台主函数"""
    try:
        fontui(" Checking connectivity")
        time.sleep(0.5)
        fontui("Welcome to Nbot Chat!", "box")
        fontui()
        fontui("NBOT CHAT", "art")
        fontui()
        fontui(f"""
Welcome to Nbot Chat!
Available commands:
>help     - Show help
>test     - Run test function  
>start    - Start Nbot Intelligence Agent
>stop     - Stop Nbot Intelligence Agent
>restart  - Restart Nbot Intelligence Agent
>status   - Check Nbot status
>exit     - Exit or CTRL + C to quit

Current directory: {os.getcwd()}
Server Status: {'Running' if server_instance.running else 'Stopped'}
""", "box")
        fontui()
        
        while True:
            try:
                command = input(" nbot-console>")
                fontui()
                global GLOBAL_LINES
                GLOBAL_LINES = 0
                
                if command == "exit":
                    # 退出前停止Nbot
                    if nbot_running:
                        await stop_nbot()
                    break
                elif command == "help":
                    show_help()
                else:
                    await run_command(command)
                
                try:
                    input(" Press Enter to continue…")
                except KeyboardInterrupt:
                    print()
                    break
                
                for i in range(GLOBAL_LINES+4):
                    delete_last_line()
                GLOBAL_LINES = 0
                
            except KeyboardInterrupt:
                print()
                break
            except EOFError:
                print()
                break
                
    except KeyboardInterrupt:
        print()
        delete_last_line()
        fontui(" goodbye!")
        # 确保停止Nbot
        if nbot_running:
            await stop_nbot()

def main():
    """同步主函数入口"""
    try:
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(main_async())
            print("检测到正在运行的事件循环，请直接调用异步函数")
            return task
        except RuntimeError:
            asyncio.run(main_async())
    except Exception as e:
        print(f"程序执行失败: {e}")
    finally:
        # 确保清理资源
        try:
            if nbot_running:
                import signal
                if nbot_process:
                    nbot_process.terminate()
        except:
            pass

if __name__ == "__main__":
    main()
