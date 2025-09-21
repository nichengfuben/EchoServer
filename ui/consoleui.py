from rich import print
from rich.text import Text
from rich.console import Console
from wcwidth import wcswidth, wcwidth
import datetime
import os
import sys
import time
import random
import asyncio

# 全局变量
NORMAL_PRINT_MODE = False  # 控制打印模式
LOG_FILE_PATH = r"E:\我的\python\new\Nbot0.4.0\nbot.log"  # 日志文件路径
GLOBAL_LINES = 0

# 全局命令注册字典
COMMAND_REGISTRY = {}

def register_command(name: str, func, description: str = ""):
    """注册命令到全局字典"""
    COMMAND_REGISTRY[name] = {
        'func': func,
        'description': description
    }

def write_to_log(content: str):
    """将内容写入日志文件"""
    try:
        file_name = os.path.splitext(os.path.basename(__file__))[0]
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as log_file:
            log_file.write(f"[{file_name}][{timestamp}] {content}\n")
    except Exception:
        pass

def extract_text_from_rich_object(obj):
    """从Rich对象中提取纯文本"""
    if isinstance(obj, Text):
        return str(obj.plain)
    elif isinstance(obj, str):
        return obj
    else:
        return str(obj)

def interpolate_color(start_rgb, end_rgb, factor):
    """颜色插值"""
    return tuple(int(start_rgb[i] + (end_rgb[i] - start_rgb[i]) * factor) for i in range(3))

def get_gradient_color(start_rgb, end_rgb, row, col, max_diag):
    """获取渐变颜色"""
    diag = row + col
    factor = diag / max_diag if max_diag > 0 else 0
    return interpolate_color(start_rgb, end_rgb, factor)

def print_gradient_banner(banner: str,next_line=True):
    """打印渐变横幅"""
    global NORMAL_PRINT_MODE
    
    if NORMAL_PRINT_MODE:
        print(banner)
        write_to_log(banner)
        return
    
    lines = banner.splitlines()
    height = len(lines)
    width = max(len(line) for line in lines) if lines else 0
    max_diag = height + width - 2 if height > 0 and width > 0 else 1

    # 渐变色定义
    light_start = (0, 170, 255)   # 青蓝
    light_end = (0, 255, 170)     # 青绿
    shadow_start = (0, 51, 102)   # 深蓝
    shadow_end = (0, 102, 51)     # 深绿

    # 边框字符使用深色渐变
    border_chars = {'╚','═','╝','╗','║','╔'}

    output_lines = []
    for row, line in enumerate(lines):
        if not line:
            output_lines.append("")
            continue
        text = Text()
        for col, char in enumerate(line):
            if char in border_chars:
                r, g, b = get_gradient_color(shadow_start, shadow_end, row, col, max_diag)
                style = f"rgb({r},{g},{b})"
            else:
                r, g, b = get_gradient_color(light_start, light_end, row, col, max_diag)
                style = f"rgb({r},{g},{b})"
            text.append(char, style=style)
        output_lines.append(text)
    
    # 写入日志
    log_content = []
    for line in output_lines:
        log_content.append(extract_text_from_rich_object(line))
    write_to_log("\n".join(log_content))
    
    # 打印输出
    for line in output_lines:
        print(line, end="", flush=True)
        if next_line:
            print()

def create_gradient_text(text: str, light_start=(0, 170, 255), light_end=(0, 255, 170)):
    """创建带渐变色的文本"""
    global NORMAL_PRINT_MODE
    
    if NORMAL_PRINT_MODE:
        return text
    
    gradient_text = Text()
    length = len(text)
    
    for i, char in enumerate(text):
        factor = i / (length - 1) if length > 1 else 0
        r = int(light_start[0] + (light_end[0] - light_start[0]) * factor)
        g = int(light_start[1] + (light_end[1] - light_start[1]) * factor)
        b = int(light_start[2] + (light_end[2] - light_start[2]) * factor)
        style = f"rgb({r},{g},{b})"
        gradient_text.append(char, style=style)
    
    return gradient_text

def set_normal_print_mode(enabled: bool):
    """设置打印模式"""
    global NORMAL_PRINT_MODE
    NORMAL_PRINT_MODE = enabled

def ascii_art(text):
    """将文本转换为ASCII艺术字"""
    
    char_map = {
        'A': [" █████╗ ", "██╔══██╗", "███████║", "██╔══██║", "██║  ██║", "╚═╝  ╚═╝"],
        'B': ["██████╗ ", "██╔══██╗", "██████╔╝", "██╔══██╗", "██████╔╝", "╚═════╝ "],
        'C': [" ██████╗", "██╔════╝", "██║     ", "██║     ", "╚██████╗", " ╚═════╝"],
        'D': ["██████╗ ", "██╔══██╗", "██║  ██║", "██║  ██║", "██████╔╝", "╚═════╝ "],
        'E': ["███████╗", "██╔════╝", "█████╗  ", "██╔══╝  ", "███████╗", "╚══════╝"],
        'F': ["███████╗", "██╔════╝", "█████╗  ", "██╔══╝  ", "██║     ", "╚═╝     "],
        'G': [" ██████╗ ", "██╔════╝ ", "██║  ███╗", "██║   ██║", "╚██████╔╝", " ╚═════╝ "],
        'H': ["██╗  ██╗", "██║  ██║", "███████║", "██╔══██║", "██║  ██║", "╚═╝  ╚═╝"],
        'I': ["██╗", "██║", "██║", "██║", "██║", "╚═╝"],
        'J': ["     ██╗", "     ██║", "     ██║", "██   ██║", "╚█████╔╝", " ╚════╝ "],
        'K': ["██╗  ██╗", "██║ ██╔╝", "█████╔╝ ", "██╔═██╗ ", "██║  ██╗", "╚═╝  ╚═╝"],
        'L': ["██╗     ", "██║     ", "██║     ", "██║     ", "███████╗", "╚══════╝"],
        'M': ["███╗   ███╗", "████╗ ████║", "██╔████╔██║", "██║╚██╔╝██║", "██║ ╚═╝ ██║", "╚═╝     ╚═╝"],
        'N': ["███╗   ██╗", "████╗  ██║", "██╔██╗ ██║", "██║╚██╗██║", "██║ ╚████║", "╚═╝  ╚═══╝"],
        'O': [" ██████╗ ", "██╔═══██╗", "██║   ██║", "██║   ██║", "╚██████╔╝", " ╚═════╝ "],
        'P': ["██████╗ ", "██╔══██╗", "██████╔╝", "██╔═══╝ ", "██║     ", "╚═╝     "],
        'Q': [" ██████╗ ", "██╔═══██╗", "██║   ██║", "██║▄▄ ██║", "╚██████╔╝", " ╚══▀▀═╝ "],
        'R': ["██████╗ ", "██╔══██╗", "██████╔╝", "██╔══██╗", "██║  ██║", "╚═╝  ╚═╝"],
        'S': ["███████╗", "██╔════╝", "███████╗", "╚════██║", "███████║", "╚══════╝"],
        'T': ["████████╗", "╚══██╔══╝", "   ██║   ", "   ██║   ", "   ██║   ", "   ╚═╝   "],
        'U': ["██╗   ██╗", "██║   ██║", "██║   ██║", "██║   ██║", "╚██████╔╝", " ╚═════╝ "],
        'V': ["██╗   ██╗", "██║   ██║", "██║   ██║", "╚██╗ ██╔╝", " ╚████╔╝ ", "  ╚═══╝  "],
        'W': ["██╗    ██╗", "██║    ██║", "██║ █╗ ██║", "██║███╗██║", "╚███╔███╔╝", " ╚══╝╚══╝ "],
        'X': ["██╗  ██╗", "╚██╗██╔╝", " ╚███╔╝ ", " ██╔██╗ ", "██╔╝ ██╗", "╚═╝  ╚═╝"],
        'Y': ["██╗   ██╗", "╚██╗ ██╔╝", " ╚████╔╝ ", "  ╚██╔╝  ", "   ██║   ", "   ╚═╝   "],
        'Z': ["███████╗", "╚══███╔╝", "  ███╔╝ ", " ███╔╝  ", "███████╗", "╚══════╝"],
        '0': [" ██████╗ ", "██╔═████╗", "██║██╔██║", "████╔╝██║", "╚██████╔╝", " ╚═════╝ "],
        '1': [" ██╗", "███║", "╚██║", " ██║", " ██║", " ╚═╝"],
        '2': ["██████╗ ", "╚════██╗", " █████╔╝", "██╔═══╝ ", "███████╗", "╚══════╝"],
        '3': ["██████╗ ", "╚════██╗", " █████╔╝", " ╚═══██╗", "██████╔╝", "╚═════╝ "],
        '4': ["██╗  ██╗", "██║  ██║", "███████║", "╚════██║", "     ██║", "     ╚═╝"],
        '5': ["███████╗", "██╔════╝", "███████╗", "╚════██║", "███████║", "╚══════╝"],
        '6': [" ██████╗ ", "██╔════╝ ", "███████╗ ", "██╔═══██╗", "╚██████╔╝", " ╚═════╝ "],
        '7': ["███████╗", "╚════██║", "    ██╔╝", "   ██╔╝ ", "   ██║  ", "   ╚═╝  "],
        '8': [" █████╗ ", "██╔══██╗", "╚█████╔╝", "██╔══██╗", "╚█████╔╝", " ╚════╝ "],
        '9': [" █████╗ ", "██╔══██╗", "╚██████║", " ╚═══██║", "██████╔╝", "╚═════╝ "],
        ' ': ["     ", "     ", "     ", "     ", "     ", "     "],
        '.': ["     ", "     ", "     ", "     ", " ██╗ ", " ╚═╝ "]
    }
    
    text = text.upper()
    lines = ["", "", "", "", "", ""]
    
    for char in text:
        if char in char_map:
            char_lines = char_map[char]
            for i in range(6):
                lines[i] += char_lines[i]
        else:
            for i in range(6):
                lines[i] += "█ "
    
    print_gradient_banner("\n".join(lines))

def get_display_width(text):
    """使用wcwidth计算显示宽度"""
    width = wcswidth(text)
    if width is None:
        width = 0
        for char in text:
            char_width = wcwidth(char)
            if char_width is not None:
                width += char_width
            else:
                width += 1
    return width

def box_font(text, extra_char="🔵"):
    """创建文本框 - 支持多行文本"""
    # 分割文本为行，去除首尾的完全空白行
    lines = text.strip().splitlines()
    if not lines:
        return
    
    extra_char_width = get_display_width(extra_char)
    
    # 处理每一行的内容并计算最大宽度
    processed_lines = []
    max_content_width = 0
    first_non_empty_processed = False
    
    for line in lines:
        line_content = line.rstrip()  # 去除行尾空格但保留行首空格
        
        if line_content.strip():  # 非空行
            if not first_non_empty_processed:
                # 第一个非空行：emoji + 空格 + 内容
                content = f"{extra_char} {line_content.lstrip()}"
                first_non_empty_processed = True
            else:
                # 后续非空行：两个空格 + 内容
                content = f"  {line_content.lstrip()}"
        else:
            # 空行
            content = ""
        
        processed_lines.append(content)
        content_width = get_display_width(content) if content else 0
        max_content_width = max(max_content_width, content_width)
    
    # 创建边框
    box_width = max_content_width + 2  # 左右各一个空格
    horizontal_line = "─" * box_width
    top_border = f"╭{horizontal_line}─╮"
    bottom_border = f"╰{horizontal_line}─╯"
    
    # 打印顶部边框
    print_gradient_banner(top_border, False)
    print()
    count = 0
    # 打印内容行
    for content in processed_lines:
        # 打印左边框
        print_gradient_banner('│ ', False)
        
        # 计算需要填充的空格数
        content_display_width = get_display_width(content) if content else 0
        padding_needed = max_content_width - content_display_width
        padding = " " * padding_needed
        
        # 打印内容（普通色）
        if count > 0:
            content = " "+content
            a = ""
        else:
            a = " "
        print(content + padding, end="", flush=True)
        count += 1
        
        # 打印右边框
        print_gradient_banner(a+' │', False)
        print()
    
    # 打印底部边框
    print_gradient_banner(bottom_border)

def color_font(text, color=False):
    """打印彩色或普通文本"""
    if color:
        print_gradient_banner(text)
    else:
        print(text)

def fontui(text="", font_type="normal"):
    """统一字体输出接口"""
    global GLOBAL_LINES
    GLOBAL_LINES += text.count('\n') + 1
    if text:
        if font_type == "normal":
            color_font(text)
        elif font_type == "color":
            color_font(text, True)
        elif font_type == "art":
            ascii_art(text)
        elif font_type == "box":
            GLOBAL_LINES += 2
            box_font(text)
    else:
        print("\n")


def delete_last_line():
    sys.stdout.write('\033[F')  # 光标上移一行
    sys.stdout.write('\033[K')  # 清除该行
    sys.stdout.flush()

def show_help():
    """显示帮助信息"""
    fontui(" Nbot Chat v0.4.108", "color")
    fontui("""
 Always review Nbot's responses, especially when running code. Nbot has read access to files in the current
 directory and can run commands and edit files with your permission.

 Available commands:""")
    
    for cmd_name, cmd_info in COMMAND_REGISTRY.items():
        desc = cmd_info.get('description', 'No description')
        fontui(f"  {cmd_name}: {desc}")

async def run_command(command_name: str):
    """运行注册的命令"""
    if command_name in COMMAND_REGISTRY:
        try:
            func = COMMAND_REGISTRY[command_name]['func']
            if asyncio.iscoroutinefunction(func):
                await func()
            else:
                func()
        except Exception as e:
            fontui(f" Error running command '{command_name}': {e}")
    else:
        fontui(" (no content)")

def console_main():
    async def main_loop():
        try:
            fontui(" Checking connectivity")
            time.sleep(0.5)
            fontui("Welcome to Nbot Chat!", "box")
            fontui()
            fontui("NBOT CHAT", "art")
            fontui()
            fontui(f"""
 Welcome to Nbot Chat!
 >help for help, >exit or CTRL + C to quit
 cwd: {os.getcwd()}
""", "box")
            fontui()
            while True:
                try:
                    command = input(" nbot-console>")
                    fontui()
                    global GLOBAL_LINES
                    GLOBAL_LINES = 0
                    
                    if command == "exit":
                        break
                    elif command == "help":
                        show_help()
                    else:
                        await run_command(command)
                    
                    try:
                        input(" Press Enter to continue…")
                    except KeyboardInterrupt:
                        print()  # 换行，然后退出
                        break
                        
                    for i in range(GLOBAL_LINES+4):
                        delete_last_line()
                    GLOBAL_LINES = 0
                    
                except KeyboardInterrupt:
                    print()  # 换行使输出更整洁
                    break
                except EOFError:  # 处理 CTRL+D 的情况
                    print()
                    break
                    
        except KeyboardInterrupt:
            print()  # 在初始化阶段按 CTRL+C
        delete_last_line()
        fontui(" goodbye!")
    
    # 运行异步主循环
    asyncio.run(main_loop())

# 注册内置命令
register_command("help", show_help, "Show this help message")

if __name__ == "__main__":
    console_main()
