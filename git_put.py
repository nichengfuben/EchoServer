import os

commands = [
    "git init",
    "git add .",
    "git commit -m \"first commit\"",
    "git branch -M main",
    "git push -u origin main"
]

for cmd in commands:
    os.system(cmd)
