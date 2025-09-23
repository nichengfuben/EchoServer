import subprocess
import os

os.chdir(r"E:\我的\python\new\Nbot0.4.0 - SERVER")

commands = [
    "git init",
    "git add .",
    "git commit -m \"first commit\"",
    "git branch -M main",
    "git push -u origin main"
]

for cmd in commands:
    print(f">>> 执行: {cmd}")
    print("-" * 60)
    
    # 指定编码为gbk
    process = subprocess.Popen(cmd, shell=True, 
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,
                              text=True, bufsize=1,
                              encoding='utf-8')  # 添加编码参数
    
    # 实时读取输出
    for line in process.stdout:
        print(line, end='')
    
    process.wait()
    
    print()  # 空行分隔
