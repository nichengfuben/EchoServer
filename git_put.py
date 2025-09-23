import os

commands = [
    'cd /d "E:\\我的\\python\\new\\Nbot0.4.0 - SERVER"'
    "git init",
    "git add .",
    "git commit -m \"first commit\"",
    "git branch -M main",
    "git push -u origin main"
]

for cmd in commands:
    os.system(cmd)
