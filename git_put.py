import subprocess
import os

# 切换到目标目录
os.chdir(r"E:\我的\python\new\Nbot0.4.0 - SERVER")

commands = [
    "git init",
    "git add .",
    "git commit -m \"first commit\"",
    "git branch -M main", 
    "git push -u origin main"
]

for cmd in commands:
    print(f"执行命令: {cmd}")
    print("-" * 50)
    
    # 实时输出，不捕获输出
    result = subprocess.run(cmd, shell=True)
    
    if result.returncode != 0:
        print(f"命令执行失败: {cmd}")
        break
        
    print()  # 空行分隔
