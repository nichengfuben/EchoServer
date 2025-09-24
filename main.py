import subprocess
import threading
import asyncio
import os
from printstream import *
from model_utils import chat_stream

# 启动服务器
def run_server():
    cmd = r'python.exe "client/client_server.py"'
    process = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='gbk',
        bufsize=1
    )
    for line in process.stdout:
        print(f"[SERVER] {line.strip()}")

# 异步调用模型一次
async def call_model_once():
    sentence = ""
    async for token in chat_stream(
        message="详细描述图片内容",
        files=["https://www.10wallpaper.com/wallpaper/1920x1080/1503/Beautiful_green_plain_bay-2015_Bing_theme_wallpaper_1920x1080.jpg"],
        model="auto_chat",
        temperature=0.7,
        generator_count=2
    ):
        sentence += token
    print(f"[NBOT] {sentence}")

# 主函数
async def main():
    # 启动服务器（后台线程）
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # 等待一小会儿让服务器启动（可选）
    await asyncio.sleep(1)

    # 调用模型一次
    await call_model_once()

    # 程序结束
    print("[INFO] 任务完成，程序退出")

if __name__ == "__main__":
    asyncio.run(main())
