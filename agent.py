from tools.tool_parser import *
from model_utils import *
import asyncio
import platform
from data.agent_prompt import *

def append_to_file(content, file_path=r"E:\我的\python\new\Nbot0.4.0 - SERVER\data\NBOT.md"):
    """
    在指定文件末尾追加内容
    
    Args:
        content (str): 要追加的内容
        file_path (str): 文件路径，默认为您的指定路径
    """
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # 以追加模式打开文件，使用utf-8编码确保中文支持
        with open(file_path, 'a', encoding='utf-8') as file:
            file.write(content + '\n')  # 自动添加换行符
            
        print(f"[记忆已更新]")
        return True
        
    except Exception as e:
        print(f"[记忆更新]出错: {e}")
        return False
def delete_file(file_path=r"E:\我的\python\new\Nbot0.4.0 - SERVER\data\NBOT.md"):
    """
    删除指定文件
    
    Args:
        file_path (str): 文件路径，默认为您的指定路径
    
    Returns:
        bool: 删除成功返回True，否则返回False
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return False
        
        # 确认是文件而不是目录
        if not os.path.isfile(file_path):
            return False
        
        # 删除文件
        os.remove(file_path)
        print(f"[开启新上下文]: {file_path}")
        return True
        
    except PermissionError:
        return False
    except Exception as e:
        return False
def clean_llm_response(res):
    res = re.sub(r'<tool_call>.*?</tool_call>', '', res, flags=re.DOTALL)
    n = len(res)
    for i in range(1, n//2 + 1):
        if res[:i] == res[i:2*i]: 
            return res[i:]
    res = re.sub(r'\n+', '\n', res)
    res = res.strip()
    return res
            
async def start_agent(task):
    delete_file()
    agent_stop = False
    while not agent_stop:
        res = await chat(get_system_prompt(task))
        print(clean_llm_response(res))
        if res == "[DONE]":
            agent_stop = True
            continue
        result = await parse_and_execute_tools(res)
        if not result:
            result = "[No results were received from any tool]<system_reminder>Please check your tool calling format carefully and strictly follow the correct tool calling format</system_reminder>"
        append_to_file(result)
        print(result)
    res = await chat(get_system_prompt())
    print(clean_llm_response(res))
                         
if __name__ == "__main__":
    asyncio.run(start_agent("获取电脑磁盘可用空间"))
