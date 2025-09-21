"""
工具集合模块 - 提供文件操作、系统执行、网络访问等功能的完整实现
遵循 DDD + TDD 原则，实现高质量、可维护的工具集
"""

import asyncio
import base64
import glob as glob_module
import io
import json
import logging
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import (
    Any, AsyncGenerator, Callable, Dict, List, Optional, 
    Protocol, Tuple, Union, TypeVar, Generic
)
from urllib.parse import parse_qs, quote, unquote, urlparse

# 第三方库导入
try:
    import aiofiles
    import aiohttp
    import chardet
    import fitz  # PyMuPDF for PDF
    import nbformat
    from PIL import Image
    from bs4 import BeautifulSoup
except ImportError as e:
    print(f"警告：某些依赖未安装 - {e}")
    print("请运行: pip install aiofiles aiohttp chardet PyMuPDF nbformat pillow beautifulsoup4")

# 导入提供的模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.bing_search import *
from model_utils import chat, chat_stream, text_to_speech, get_embedding, get_health, get_models

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tools.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 类型别名
T = TypeVar('T')
PathLike = Union[str, Path]
JsonDict = Dict[str, Any]

# 全局常量
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MAX_LINE_LENGTH = 2000
DEFAULT_LINE_LIMIT = 2000
BASH_DEFAULT_TIMEOUT = 120000  # 2分钟
BASH_MAX_TIMEOUT = 600000  # 10分钟
OUTPUT_MAX_LENGTH = 30000
CACHE_DURATION = timedelta(minutes=15)


# ==================== 基础类和异常定义 ====================

class ToolError(Exception):
    """工具执行异常基类"""
    pass


class FileOperationError(ToolError):
    """文件操作异常"""
    pass


class BashExecutionError(ToolError):
    """Bash执行异常"""
    pass


class NetworkError(ToolError):
    """网络相关异常"""
    pass


class ValidationError(ToolError):
    """参数验证异常"""
    pass


@dataclass
class BashSession:
    """Bash会话管理类"""
    id: str
    process: subprocess.Popen
    start_time: datetime
    command: str
    is_background: bool = False
    output_buffer: List[str] = field(default_factory=list)
    error_buffer: List[str] = field(default_factory=list)
    last_read_index: int = 0
    
    def is_running(self) -> bool:
        """检查进程是否运行中"""
        return self.process.poll() is None
    
    def get_new_output(self, filter_regex: Optional[str] = None) -> Tuple[List[str], List[str]]:
        """获取新输出，支持正则过滤"""
        stdout_lines = self.output_buffer[self.last_read_index:]
        stderr_lines = self.error_buffer[self.last_read_index:]
        self.last_read_index = len(self.output_buffer)
        
        if filter_regex:
            pattern = re.compile(filter_regex)
            stdout_lines = [line for line in stdout_lines if pattern.search(line)]
            stderr_lines = [line for line in stderr_lines if pattern.search(line)]
        
        return stdout_lines, stderr_lines


@dataclass
class TodoItem:
    """待办事项数据类"""
    id: str
    content: str
    status: str  # pending, in_progress, completed
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def update_status(self, new_status: str) -> None:
        """更新任务状态"""
        if new_status not in ['pending', 'in_progress', 'completed']:
            raise ValueError(f"Invalid status: {new_status}")
        self.status = new_status
        self.updated_at = datetime.now()


class SubagentType(Enum):
    """子代理类型枚举"""
    GENERAL_PURPOSE = "general-purpose"
    STATUSLINE_SETUP = "statusline-setup"
    OUTPUT_STYLE_SETUP = "output-style-setup"


# ==================== 工具基类 ====================

class BaseTool(ABC):
    """工具基类 - 提供通用功能"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._cache: Dict[str, Tuple[Any, datetime]] = {}
        
    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """执行工具的抽象方法"""
        pass
    
    def validate_params(self, params: Dict[str, Any], required: List[str]) -> None:
        """验证必需参数"""
        missing = [p for p in required if p not in params or params[p] is None]
        if missing:
            raise ValidationError(f"Missing required parameters: {missing}")
    
    def get_from_cache(self, key: str) -> Optional[Any]:
        """从缓存获取数据"""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if datetime.now() - timestamp < CACHE_DURATION:
                return value
            del self._cache[key]
        return None
    
    def set_cache(self, key: str, value: Any) -> None:
        """设置缓存数据"""
        self._cache[key] = (value, datetime.now())
    
    def clean_text(self, text: str) -> str:
        """清理文本内容"""
        if not text:
            return ""
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        # 移除特殊字符
        text = text.replace('\u200b', '').replace('\xa0', ' ')
        return text.strip()


# ==================== 核心工具管理器 ====================

class ToolManager:
    """工具管理器 - 统一管理所有工具实例"""
    
    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}
        self.bash_sessions: Dict[str, BashSession] = {}
        self.todo_list: List[TodoItem] = []
        self.file_read_history: set = set()  # 记录已读文件
        self._initialize_tools()
    
    def _initialize_tools(self) -> None:
        """初始化所有工具"""
        self.tools = {
            'Task': TaskTool(self),
            'Bash': BashTool(self),
            'Glob': GlobTool(self),
            'Grep': GrepTool(self),
            'LS': LSTool(self),
            'ExitPlanMode': ExitPlanModeTool(self),
            'Read': ReadTool(self),
            'Edit': EditTool(self),
            'MultiEdit': MultiEditTool(self),
            'Write': WriteTool(self),
            'NotebookEdit': NotebookEditTool(self),
            'WebFetch': WebFetchTool(self),
            'TodoWrite': TodoWriteTool(self),
            'WebSearch': WebSearchTool(self),
            'BashOutput': BashOutputTool(self),
            'KillBash': KillBashTool(self),
        }
    
    async def execute_tool(self, tool_name: str, **params) -> Any:
        """执行指定工具"""
        if tool_name not in self.tools:
            raise ToolError(f"Tool {tool_name} not found")
        
        tool = self.tools[tool_name]
        try:
            return await tool.execute(**params)
        except Exception as e:
            logger.error(f"Error executing {tool_name}: {e}")
            raise


# ==================== 具体工具实现 ====================

class TaskTool(BaseTool):
    """任务工具 - 启动新代理处理复杂任务"""
    
    def __init__(self, manager: ToolManager):
        super().__init__()
        self.manager = manager
        self.active_agents: Dict[str, Dict[str, Any]] = {}
    
    async def execute(
        self, 
        description: str, 
        prompt: str, 
        subagent_type: str
    ) -> Dict[str, Any]:
        """
        启动子代理执行任务
        
        Args:
            description: 任务简短描述
            prompt: 详细任务指令
            subagent_type: 子代理类型
            
        Returns:
            执行结果字典
        """
        self.validate_params(
            {'description': description, 'prompt': prompt, 'subagent_type': subagent_type},
            ['description', 'prompt', 'subagent_type']
        )
        
        # 验证子代理类型
        valid_types = ['general-purpose', 'statusline-setup', 'output-style-setup']
        if subagent_type not in valid_types:
            raise ValidationError(f"Invalid subagent_type: {subagent_type}")
        
        agent_id = str(uuid.uuid4())
        
        try:
            # 根据子代理类型执行不同策略
            if subagent_type == 'general-purpose':
                result = await self._execute_general_purpose(prompt)
            elif subagent_type == 'statusline-setup':
                result = await self._execute_statusline_setup(prompt)
            else:  # output-style-setup
                result = await self._execute_output_style_setup(prompt)
            
            # 记录代理执行历史
            self.active_agents[agent_id] = {
                'description': description,
                'subagent_type': subagent_type,
                'status': 'completed',
                'result': result,
                'timestamp': datetime.now().isoformat()
            }
            
            return {
                'agent_id': agent_id,
                'status': 'success',
                'result': result
            }
            
        except Exception as e:
            self.active_agents[agent_id] = {
                'description': description,
                'subagent_type': subagent_type,
                'status': 'failed',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            raise ToolError(f"Agent execution failed: {e}")
    
    async def _execute_general_purpose(self, prompt: str) -> str:
        """执行通用目的代理任务"""
        # 调用AI模型处理复杂任务
        full_prompt = f"""作为通用智能代理，请完成以下任务：

{prompt}

请提供详细的执行步骤和结果。"""
        
        result = await chat(full_prompt)
        return result
    
    async def _execute_statusline_setup(self, prompt: str) -> str:
        """执行状态栏设置任务"""
        config_prompt = f"""配置状态栏设置：

{prompt}

请生成相应的配置代码或设置。"""
        
        result = await chat(config_prompt)
        return result
    
    async def _execute_output_style_setup(self, prompt: str) -> str:
        """执行输出样式设置任务"""
        style_prompt = f"""创建输出样式配置：

{prompt}

请生成样式配置文件或代码。"""
        
        result = await chat(style_prompt)
        return result


class BashTool(BaseTool):
    """Bash工具 - 执行shell命令"""
    
    def __init__(self, manager: ToolManager):
        super().__init__()
        self.manager = manager
        self.current_dir = os.getcwd()
    
    async def execute(
        self,
        command: str,
        timeout: Optional[int] = None,
        description: Optional[str] = None,
        run_in_background: bool = False
    ) -> Dict[str, Any]:
        """
        执行bash命令
        
        Args:
            command: 要执行的命令
            timeout: 超时时间(毫秒)
            description: 命令描述
            run_in_background: 是否后台运行
            
        Returns:
            执行结果字典
        """
        self.validate_params({'command': command}, ['command'])
        
        # 验证超时设置
        if timeout is None:
            timeout = BASH_DEFAULT_TIMEOUT
        elif timeout > BASH_MAX_TIMEOUT:
            timeout = BASH_MAX_TIMEOUT
        
        timeout_seconds = timeout / 1000.0
        
        # 处理引号和路径
        command = self._process_command(command)
        
        if run_in_background:
            return await self._run_background(command, description)
        else:
            return await self._run_foreground(command, timeout_seconds, description)
    
    def _process_command(self, command: str) -> str:
        """处理命令中的引号和路径"""
        # 确保路径中的空格被正确引用
        # 这里使用简单的启发式方法
        parts = command.split()
        processed_parts = []
        
        for part in parts:
            # 检查是否是路径且包含空格
            if ' ' in part and (part.startswith('/') or part.startswith('C:\\') or part.startswith('./')):
                if not (part.startswith('"') and part.endswith('"')):
                    part = f'"{part}"'
            processed_parts.append(part)
        
        return ' '.join(processed_parts)
    
    async def _run_foreground(
        self, 
        command: str, 
        timeout: float, 
        description: Optional[str]
    ) -> Dict[str, Any]:
        """前台执行命令"""
        try:
            # 在Windows上使用shell=True，在Unix上使用shell=False更安全
            shell = sys.platform == 'win32'
            
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.current_dir,
                shell=shell
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise BashExecutionError(f"Command timed out after {timeout} seconds")
            
            # 解码输出
            stdout_text = self._decode_output(stdout)
            stderr_text = self._decode_output(stderr)
            
            # 截断过长输出
            if len(stdout_text) > OUTPUT_MAX_LENGTH:
                stdout_text = stdout_text[:OUTPUT_MAX_LENGTH] + "\n[Output truncated]"
            if len(stderr_text) > OUTPUT_MAX_LENGTH:
                stderr_text = stderr_text[:OUTPUT_MAX_LENGTH] + "\n[Output truncated]"
            
            return {
                'exit_code': process.returncode,
                'stdout': stdout_text,
                'stderr': stderr_text,
                'description': description or f"Executed: {command[:50]}..."
            }
            
        except Exception as e:
            raise BashExecutionError(f"Command execution failed: {e}")
    
    async def _run_background(
        self, 
        command: str, 
        description: Optional[str]
    ) -> Dict[str, Any]:
        """后台执行命令"""
        session_id = str(uuid.uuid4())
        
        try:
            # 创建后台进程
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                cwd=self.current_dir,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # 创建会话对象
            session = BashSession(
                id=session_id,
                process=process,
                start_time=datetime.now(),
                command=command,
                is_background=True
            )
            
            # 启动输出收集任务
            asyncio.create_task(self._collect_output(session))
            
            # 保存会话
            self.manager.bash_sessions[session_id] = session
            
            return {
                'bash_id': session_id,
                'status': 'running',
                'pid': process.pid,
                'description': description or f"Background: {command[:50]}..."
            }
            
        except Exception as e:
            raise BashExecutionError(f"Failed to start background process: {e}")
    
    async def _collect_output(self, session: BashSession) -> None:
        """异步收集后台进程输出"""
        try:
            while session.is_running():
                # 非阻塞读取输出
                if session.process.stdout:
                    line = session.process.stdout.readline()
                    if line:
                        session.output_buffer.append(line.rstrip())
                
                if session.process.stderr:
                    line = session.process.stderr.readline()
                    if line:
                        session.error_buffer.append(line.rstrip())
                
                await asyncio.sleep(0.1)
            
            # 读取剩余输出
            if session.process.stdout:
                remaining = session.process.stdout.read()
                if remaining:
                    session.output_buffer.extend(remaining.rstrip().split('\n'))
            
            if session.process.stderr:
                remaining = session.process.stderr.read()
                if remaining:
                    session.error_buffer.extend(remaining.rstrip().split('\n'))
                    
        except Exception as e:
            logger.error(f"Error collecting output for session {session.id}: {e}")
    
    def _decode_output(self, data: bytes) -> str:
        """智能解码输出"""
        if not data:
            return ""
        
        # 尝试多种编码
        encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
        
        for encoding in encodings:
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        
        # 使用chardet检测编码
        try:
            detected = chardet.detect(data)
            if detected['encoding']:
                return data.decode(detected['encoding'], errors='replace')
        except:
            pass
        
        # 最后手段：忽略错误
        return data.decode('utf-8', errors='ignore')


class GlobTool(BaseTool):
    """Glob工具 - 文件模式匹配"""
    
    def __init__(self, manager: ToolManager):
        super().__init__()
        self.manager = manager
    
    async def execute(
        self,
        pattern: str,
        path: Optional[str] = None
    ) -> List[str]:
        """
        执行文件模式匹配
        
        Args:
            pattern: glob模式
            path: 搜索路径
            
        Returns:
            匹配的文件路径列表
        """
        self.validate_params({'pattern': pattern}, ['pattern'])
        
        # 使用当前目录或指定路径
        search_path = Path(path) if path else Path.cwd()
        
        if not search_path.exists():
            raise FileOperationError(f"Path does not exist: {search_path}")
        
        if not search_path.is_dir():
            raise FileOperationError(f"Path is not a directory: {search_path}")
        
        try:
            # 构建完整的搜索模式
            if search_path != Path.cwd():
                full_pattern = str(search_path / pattern)
            else:
                full_pattern = pattern
            
            # 执行glob搜索
            matches = glob_module.glob(full_pattern, recursive=True)
            
            # 转换为绝对路径并排序（按修改时间）
            result = []
            for match in matches:
                path_obj = Path(match).resolve()
                if path_obj.exists():
                    result.append((str(path_obj), path_obj.stat().st_mtime))
            
            # 按修改时间排序
            result.sort(key=lambda x: x[1], reverse=True)
            
            return [path for path, _ in result]
            
        except Exception as e:
            raise FileOperationError(f"Glob pattern matching failed: {e}")


class GrepTool(BaseTool):
    """Grep工具 - 基于ripgrep的搜索"""
    
    def __init__(self, manager: ToolManager):
        super().__init__()
        self.manager = manager
    
    async def execute(
        self,
        pattern: str,
        path: Optional[str] = None,
        glob: Optional[str] = None,
        output_mode: str = "files_with_matches",
        B: Optional[int] = None,  # lines before
        A: Optional[int] = None,  # lines after
        C: Optional[int] = None,  # context lines
        n: bool = False,  # line numbers
        i: bool = False,  # case insensitive
        type: Optional[str] = None,
        head_limit: Optional[int] = None,
        multiline: bool = False
    ) -> Union[List[str], Dict[str, Any]]:
        """
        执行ripgrep搜索
        
        Args:
            pattern: 正则表达式模式
            path: 搜索路径
            glob: 文件过滤模式
            output_mode: 输出模式
            B, A, C: 上下文行数
            n: 显示行号
            i: 大小写不敏感
            type: 文件类型
            head_limit: 输出限制
            multiline: 多行模式
            
        Returns:
            搜索结果
        """
        self.validate_params({'pattern': pattern}, ['pattern'])
        
        # 构建ripgrep命令
        cmd = ['rg']
        
        # 添加模式
        if i:
            cmd.append('-i')
        
        if multiline:
            cmd.extend(['-U', '--multiline-dotall'])
        
        # 输出模式设置
        if output_mode == 'files_with_matches':
            cmd.append('-l')
        elif output_mode == 'count':
            cmd.append('-c')
        else:  # content
            if n:
                cmd.append('-n')
            if B is not None:
                cmd.extend(['-B', str(B)])
            if A is not None:
                cmd.extend(['-A', str(A)])
            if C is not None:
                cmd.extend(['-C', str(C)])
        
        # 文件类型和glob
        if type:
            cmd.extend(['--type', type])
        if glob:
            cmd.extend(['--glob', glob])
        
        # 添加模式和路径
        cmd.append(pattern)
        if path:
            cmd.append(path)
        
        try:
            # 执行ripgrep
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            output = result.stdout
            
            # 处理head_limit
            if head_limit and output:
                lines = output.split('\n')
                output = '\n'.join(lines[:head_limit])
            
            # 根据输出模式返回不同格式
            if output_mode == 'files_with_matches':
                return output.strip().split('\n') if output.strip() else []
            elif output_mode == 'count':
                counts = {}
                for line in output.strip().split('\n'):
                    if ':' in line:
                        file, count = line.rsplit(':', 1)
                        counts[file] = int(count)
                return counts
            else:
                return output
                
        except subprocess.TimeoutExpired:
            raise ToolError("Grep search timed out")
        except FileNotFoundError:
            # ripgrep未安装，回退到Python实现
            return await self._python_grep(
                pattern, path, glob, output_mode, 
                B, A, C, n, i, type, head_limit, multiline
            )
        except Exception as e:
            raise ToolError(f"Grep search failed: {e}")
    
    async def _python_grep(
        self,
        pattern: str,
        path: Optional[str] = None,
        glob_pattern: Optional[str] = None,
        output_mode: str = "files_with_matches",
        B: Optional[int] = None,
        A: Optional[int] = None,
        C: Optional[int] = None,
        n: bool = False,
        i: bool = False,
        file_type: Optional[str] = None,
        head_limit: Optional[int] = None,
        multiline: bool = False
    ) -> Union[List[str], Dict[str, Any], str]:
        """Python实现的grep功能"""
        search_path = Path(path) if path else Path.cwd()
        
        # 编译正则表达式
        flags = 0
        if i:
            flags |= re.IGNORECASE
        if multiline:
            flags |= re.MULTILINE | re.DOTALL
        
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            raise ValidationError(f"Invalid regex pattern: {e}")
        
        # 获取要搜索的文件
        files_to_search = []
        if search_path.is_file():
            files_to_search = [search_path]
        else:
            # 构建文件列表
            pattern_to_use = glob_pattern or "**/*"
            for file_path in search_path.glob(pattern_to_use):
                if file_path.is_file():
                    # 文件类型过滤
                    if file_type:
                        ext_map = {
                            'py': ['.py'],
                            'js': ['.js', '.jsx'],
                            'ts': ['.ts', '.tsx'],
                            'java': ['.java'],
                            'go': ['.go'],
                            'rust': ['.rs'],
                        }
                        if file_type in ext_map:
                            if not any(str(file_path).endswith(ext) for ext in ext_map[file_type]):
                                continue
                    files_to_search.append(file_path)
        
        # 执行搜索
        results = []
        file_matches = []
        counts = {}
        
        for file_path in files_to_search:
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                
                if output_mode == 'files_with_matches':
                    if regex.search(content):
                        file_matches.append(str(file_path))
                
                elif output_mode == 'count':
                    matches = regex.findall(content)
                    if matches:
                        counts[str(file_path)] = len(matches)
                
                else:  # content mode
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if regex.search(line):
                            # 构建上下文
                            start = max(0, i - (B or 0) - (C or 0))
                            end = min(len(lines), i + 1 + (A or 0) + (C or 0))
                            
                            for j in range(start, end):
                                line_str = lines[j]
                                if n:
                                    line_str = f"{j+1}:{line_str}"
                                results.append(line_str)
                            
                            if head_limit and len(results) >= head_limit:
                                break
                
                if head_limit:
                    if output_mode == 'files_with_matches' and len(file_matches) >= head_limit:
                        break
                    elif output_mode == 'content' and len(results) >= head_limit:
                        break
                        
            except Exception as e:
                logger.warning(f"Failed to search {file_path}: {e}")
                continue
        
        # 返回结果
        if output_mode == 'files_with_matches':
            return file_matches[:head_limit] if head_limit else file_matches
        elif output_mode == 'count':
            return counts
        else:
            result_str = '\n'.join(results[:head_limit] if head_limit else results)
            return result_str


class LSTool(BaseTool):
    """LS工具 - 列出目录内容"""
    
    def __init__(self, manager: ToolManager):
        super().__init__()
        self.manager = manager
    
    async def execute(
        self,
        path: str,
        ignore: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        列出目录内容
        
        Args:
            path: 绝对路径
            ignore: 忽略的glob模式列表
            
        Returns:
            文件和目录信息列表
        """
        self.validate_params({'path': path}, ['path'])
        
        # 验证路径
        dir_path = Path(path)
        if not dir_path.is_absolute():
            raise ValidationError(f"Path must be absolute: {path}")
        
        if not dir_path.exists():
            raise FileOperationError(f"Path does not exist: {path}")
        
        if not dir_path.is_dir():
            raise FileOperationError(f"Path is not a directory: {path}")
        
        ignore_patterns = ignore or []
        results = []
        
        try:
            for item in dir_path.iterdir():
                # 检查是否应该忽略
                should_ignore = False
                for pattern in ignore_patterns:
                    if item.match(pattern):
                        should_ignore = True
                        break
                
                if should_ignore:
                    continue
                
                # 获取文件信息
                stat = item.stat()
                info = {
                    'name': item.name,
                    'path': str(item.absolute()),
                    'type': 'directory' if item.is_dir() else 'file',
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                }
                
                # 添加额外信息
                if item.is_file():
                    info['extension'] = item.suffix
                    info['mime_type'] = mimetypes.guess_type(str(item))[0]
                
                results.append(info)
            
            # 排序：目录优先，然后按名称
            results.sort(key=lambda x: (x['type'] != 'directory', x['name'].lower()))
            
            return results
            
        except PermissionError as e:
            raise FileOperationError(f"Permission denied: {e}")
        except Exception as e:
            raise FileOperationError(f"Failed to list directory: {e}")


class ExitPlanModeTool(BaseTool):
    """退出计划模式工具"""
    
    def __init__(self, manager: ToolManager):
        super().__init__()
        self.manager = manager
    
    async def execute(self, plan: str) -> Dict[str, Any]:
        """
        退出计划模式
        
        Args:
            plan: 制定的计划内容
            
        Returns:
            状态信息
        """
        self.validate_params({'plan': plan}, ['plan'])
        
        # 记录计划
        timestamp = datetime.now().isoformat()
        
        # 可以将计划保存到文件或发送给用户确认
        plan_data = {
            'timestamp': timestamp,
            'plan': plan,
            'status': 'ready_to_execute'
        }
        
        # 触发用户确认流程
        return {
            'message': 'Exiting plan mode',
            'plan_summary': plan[:500] + '...' if len(plan) > 500 else plan,
            'next_action': 'awaiting_user_confirmation',
            'data': plan_data
        }


class ReadTool(BaseTool):
    """Read工具 - 读取文件内容"""
    
    def __init__(self, manager: ToolManager):
        super().__init__()
        self.manager = manager
    
    async def execute(
        self,
        file_path: str,
        offset: Optional[int] = None,
        limit: Optional[int] = None
    ) -> Union[str, Dict[str, Any]]:
        """
        读取文件内容
        
        Args:
            file_path: 文件绝对路径
            offset: 起始行号
            limit: 读取行数限制
            
        Returns:
            文件内容或结构化数据
        """
        self.validate_params({'file_path': file_path}, ['file_path'])
        
        # 验证路径
        path = Path(file_path)
        if not path.is_absolute():
            raise ValidationError(f"Path must be absolute: {file_path}")
        
        # 记录已读文件
        self.manager.file_read_history.add(str(path))
        
        # 如果文件不存在，返回错误
        if not path.exists():
            raise FileOperationError(f"File does not exist: {file_path}")
        
        # 检查文件大小
        file_size = path.stat().st_size
        if file_size > MAX_FILE_SIZE:
            raise FileOperationError(f"File too large: {file_size} bytes (max: {MAX_FILE_SIZE})")
        
        # 根据文件类型选择读取方式
        suffix = path.suffix.lower()
        
        try:
            if suffix in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
                return await self._read_image(path)
            elif suffix == '.pdf':
                return await self._read_pdf(path)
            elif suffix == '.ipynb':
                return await self._read_notebook(path)
            else:
                return await self._read_text(path, offset, limit)
                
        except Exception as e:
            raise FileOperationError(f"Failed to read file: {e}")
    
    async def _read_text(
        self, 
        path: Path, 
        offset: Optional[int] = None, 
        limit: Optional[int] = None
    ) -> str:
        """读取文本文件"""
        try:
            # 检测编码
            with open(path, 'rb') as f:
                raw_data = f.read(10000)
                detected = chardet.detect(raw_data)
                encoding = detected.get('encoding', 'utf-8')
            
            # 读取文件
            async with aiofiles.open(path, 'r', encoding=encoding, errors='replace') as f:
                lines = await f.readlines()
            
            # 处理offset和limit
            start = (offset - 1) if offset else 0
            end = start + (limit or DEFAULT_LINE_LIMIT)
            
            selected_lines = lines[start:end]
            
            # 截断过长的行
            processed_lines = []
            for i, line in enumerate(selected_lines, start=start+1):
                if len(line) > MAX_LINE_LENGTH:
                    line = line[:MAX_LINE_LENGTH] + '... [truncated]\n'
                # 添加行号
                processed_lines.append(f"{i}\t{line.rstrip()}")
            
            return '\n'.join(processed_lines)
            
        except Exception as e:
            raise FileOperationError(f"Failed to read text file: {e}")
    
    async def _read_image(self, path: Path) -> Dict[str, Any]:
        """读取图片文件"""
        try:
            # 打开图片
            with Image.open(path) as img:
                # 获取图片信息
                info = {
                    'type': 'image',
                    'format': img.format,
                    'mode': img.mode,
                    'size': img.size,
                    'width': img.width,
                    'height': img.height,
                }
                
                # 转换为base64用于显示
                buffered = io.BytesIO()
                img.save(buffered, format=img.format or 'PNG')
                img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                
                info['base64'] = img_base64
                info['data_url'] = f"data:image/{img.format.lower()};base64,{img_base64}"
                
                return info
                
        except Exception as e:
            raise FileOperationError(f"Failed to read image: {e}")
    
    async def _read_pdf(self, path: Path) -> Dict[str, Any]:
        """读取PDF文件"""
        try:
            pdf_data = {
                'type': 'pdf',
                'pages': [],
                'metadata': {}
            }
            
            # 打开PDF
            pdf_document = fitz.open(str(path))
            
            # 获取元数据
            pdf_data['metadata'] = {
                'page_count': pdf_document.page_count,
                'title': pdf_document.metadata.get('title', ''),
                'author': pdf_document.metadata.get('author', ''),
                'subject': pdf_document.metadata.get('subject', ''),
                'keywords': pdf_document.metadata.get('keywords', ''),
            }
            
            # 读取每页内容
            for page_num in range(pdf_document.page_count):
                page = pdf_document[page_num]
                
                # 提取文本
                text = page.get_text()
                
                # 获取页面图像
                pix = page.get_pixmap()
                img_data = pix.tobytes("png")
                img_base64 = base64.b64encode(img_data).decode('utf-8')
                
                pdf_data['pages'].append({
                    'page_number': page_num + 1,
                    'text': text,
                    'image_base64': img_base64,
                })
            
            pdf_document.close()
            return pdf_data
            
        except Exception as e:
            raise FileOperationError(f"Failed to read PDF: {e}")
    
    async def _read_notebook(self, path: Path) -> Dict[str, Any]:
        """读取Jupyter Notebook"""
        try:
            # 读取notebook
            with open(path, 'r', encoding='utf-8') as f:
                nb = nbformat.read(f, as_version=4)
            
            notebook_data = {
                'type': 'notebook',
                'metadata': nb.metadata,
                'cells': []
            }
            
            # 处理每个cell
            for i, cell in enumerate(nb.cells):
                cell_data = {
                    'index': i,
                    'cell_type': cell.cell_type,
                    'source': cell.source,
                    'metadata': cell.metadata,
                }
                
                # 添加cell id
                if hasattr(cell, 'id'):
                    cell_data['id'] = cell.id
                
                # 处理代码cell的输出
                if cell.cell_type == 'code':
                    cell_data['outputs'] = []
                    for output in cell.outputs:
                        output_data = {
                            'output_type': output.output_type
                        }
                        
                        if hasattr(output, 'text'):
                            output_data['text'] = output.text
                        if hasattr(output, 'data'):
                            output_data['data'] = output.data
                        
                        cell_data['outputs'].append(output_data)
                
                notebook_data['cells'].append(cell_data)
            
            return notebook_data
            
        except Exception as e:
            raise FileOperationError(f"Failed to read notebook: {e}")


class EditTool(BaseTool):
    """Edit工具 - 编辑文件内容"""
    
    def __init__(self, manager: ToolManager):
        super().__init__()
        self.manager = manager
    
    async def execute(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False
    ) -> Dict[str, Any]:
        """
        编辑文件内容
        
        Args:
            file_path: 文件路径
            old_string: 要替换的内容
            new_string: 新内容
            replace_all: 是否替换所有匹配
            
        Returns:
            编辑结果
        """
        self.validate_params(
            {'file_path': file_path, 'old_string': old_string, 'new_string': new_string},
            ['file_path', 'old_string', 'new_string']
        )
        
        # 检查文件是否已读
        path = Path(file_path)
        if not path.is_absolute():
            raise ValidationError(f"Path must be absolute: {file_path}")
        
        if str(path) not in self.manager.file_read_history:
            raise ValidationError(f"File must be read before editing: {file_path}")
        
        if not path.exists():
            raise FileOperationError(f"File does not exist: {file_path}")
        
        if old_string == new_string:
            raise ValidationError("old_string and new_string cannot be the same")
        
        try:
            # 读取文件内容
            content = path.read_text(encoding='utf-8')
            
            # 检查old_string是否存在
            occurrences = content.count(old_string)
            if occurrences == 0:
                raise ValidationError(f"old_string not found in file")
            
            if not replace_all and occurrences > 1:
                raise ValidationError(
                    f"old_string appears {occurrences} times. "
                    "Use replace_all=True or provide more context to make it unique"
                )
            
            # 执行替换
            if replace_all:
                new_content = content.replace(old_string, new_string)
                replaced_count = occurrences
            else:
                new_content = content.replace(old_string, new_string, 1)
                replaced_count = 1
            
            # 备份原文件
            backup_path = path.with_suffix(path.suffix + '.bak')
            shutil.copy2(path, backup_path)
            
            # 写入新内容
            path.write_text(new_content, encoding='utf-8')
            
            return {
                'status': 'success',
                'file_path': str(path),
                'replacements': replaced_count,
                'backup_path': str(backup_path)
            }
            
        except Exception as e:
            raise FileOperationError(f"Edit failed: {e}")


class MultiEditTool(BaseTool):
    """MultiEdit工具 - 批量编辑文件"""
    
    def __init__(self, manager: ToolManager):
        super().__init__()
        self.manager = manager
    
    async def execute(
        self,
        file_path: str,
        edits: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        执行多个编辑操作
        
        Args:
            file_path: 文件路径
            edits: 编辑操作列表
            
        Returns:
            编辑结果
        """
        self.validate_params(
            {'file_path': file_path, 'edits': edits},
            ['file_path', 'edits']
        )
        
        if not edits:
            raise ValidationError("edits list cannot be empty")
        
        path = Path(file_path)
        if not path.is_absolute():
            raise ValidationError(f"Path must be absolute: {file_path}")
        
        # 新文件特殊处理
        is_new_file = not path.exists()
        
        if not is_new_file:
            # 现有文件必须先读取
            if str(path) not in self.manager.file_read_history:
                raise ValidationError(f"File must be read before editing: {file_path}")
            
            # 读取内容
            content = path.read_text(encoding='utf-8')
            
            # 备份
            backup_path = path.with_suffix(path.suffix + '.bak')
            shutil.copy2(path, backup_path)
        else:
            # 新文件
            content = ""
            backup_path = None
            
            # 第一个编辑必须是空old_string
            if edits[0].get('old_string', '') != '':
                raise ValidationError(
                    "First edit for new file must have empty old_string"
                )
        
        try:
            # 顺序应用所有编辑
            total_replacements = 0
            
            for i, edit in enumerate(edits):
                old_string = edit.get('old_string', '')
                new_string = edit.get('new_string', '')
                replace_all = edit.get('replace_all', False)
                
                if old_string == new_string:
                    raise ValidationError(
                        f"Edit {i+1}: old_string and new_string cannot be the same"
                    )
                
                if i == 0 and is_new_file:
                    # 新文件的第一个编辑
                    content = new_string
                    total_replacements = 1
                else:
                    # 常规替换
                    occurrences = content.count(old_string)
                    
                    if occurrences == 0:
                        raise ValidationError(
                            f"Edit {i+1}: old_string not found in current content"
                        )
                    
                    if not replace_all and occurrences > 1:
                        raise ValidationError(
                            f"Edit {i+1}: old_string appears {occurrences} times. "
                            "Use replace_all=true or provide more context"
                        )
                    
                    if replace_all:
                        content = content.replace(old_string, new_string)
                        total_replacements += occurrences
                    else:
                        content = content.replace(old_string, new_string, 1)
                        total_replacements += 1
            
            # 确保父目录存在
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入最终内容
            path.write_text(content, encoding='utf-8')
            
            return {
                'status': 'success',
                'file_path': str(path),
                'edits_applied': len(edits),
                'total_replacements': total_replacements,
                'backup_path': str(backup_path) if backup_path else None
            }
            
        except Exception as e:
            # 如果出错，恢复备份
            if backup_path and backup_path.exists():
                shutil.copy2(backup_path, path)
            raise FileOperationError(f"MultiEdit failed: {e}")


class WriteTool(BaseTool):
    """Write工具 - 写入文件"""
    
    def __init__(self, manager: ToolManager):
        super().__init__()
        self.manager = manager
    
    async def execute(
        self,
        file_path: str,
        content: str
    ) -> Dict[str, Any]:
        """
        写入文件内容
        
        Args:
            file_path: 文件路径
            content: 要写入的内容
            
        Returns:
            写入结果
        """
        self.validate_params(
            {'file_path': file_path, 'content': content},
            ['file_path', 'content']
        )
        
        path = Path(file_path)
        if not path.is_absolute():
            raise ValidationError(f"Path must be absolute: {file_path}")
        
        # 如果是现有文件，必须先读取
        if path.exists() and str(path) not in self.manager.file_read_history:
            raise ValidationError(f"Existing file must be read before writing: {file_path}")
        
        try:
            # 确保父目录存在
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # 如果文件存在，先备份
            backup_path = None
            if path.exists():
                backup_path = path.with_suffix(path.suffix + '.bak')
                shutil.copy2(path, backup_path)
            
            # 写入内容
            async with aiofiles.open(path, 'w', encoding='utf-8') as f:
                await f.write(content)
            
            return {
                'status': 'success',
                'file_path': str(path),
                'bytes_written': len(content.encode('utf-8')),
                'backup_path': str(backup_path) if backup_path else None
            }
            
        except Exception as e:
            raise FileOperationError(f"Write failed: {e}")


class NotebookEditTool(BaseTool):
    """NotebookEdit工具 - 编辑Jupyter notebook"""
    
    def __init__(self, manager: ToolManager):
        super().__init__()
        self.manager = manager
    
    async def execute(
        self,
        notebook_path: str,
        cell_id: Optional[str] = None,
        new_source: str = "",
        cell_type: Optional[str] = None,
        edit_mode: str = "replace"
    ) -> Dict[str, Any]:
        """
        编辑Jupyter notebook单元格
        
        Args:
            notebook_path: notebook路径
            cell_id: 单元格ID
            new_source: 新内容
            cell_type: 单元格类型
            edit_mode: 编辑模式
            
        Returns:
            编辑结果
        """
        self.validate_params(
            {'notebook_path': notebook_path, 'new_source': new_source},
            ['notebook_path', 'new_source']
        )
        
        path = Path(notebook_path)
        if not path.is_absolute():
            raise ValidationError(f"Path must be absolute: {notebook_path}")
        
        if not path.exists():
            raise FileOperationError(f"Notebook does not exist: {notebook_path}")
        
        try:
            # 读取notebook
            with open(path, 'r', encoding='utf-8') as f:
                nb = nbformat.read(f, as_version=4)
            
            # 备份
            backup_path = path.with_suffix('.ipynb.bak')
            shutil.copy2(path, backup_path)
            
            # 根据编辑模式执行操作
            if edit_mode == "replace":
                # 替换单元格内容
                cell_found = False
                for cell in nb.cells:
                    if hasattr(cell, 'id') and cell.id == cell_id:
                        cell.source = new_source
                        if cell_type:
                            cell.cell_type = cell_type
                        cell_found = True
                        break
                
                if not cell_found:
                    raise ValidationError(f"Cell with id {cell_id} not found")
                    
            elif edit_mode == "insert":
                # 插入新单元格
                if not cell_type:
                    raise ValidationError("cell_type is required for insert mode")
                
                new_cell = nbformat.v4.new_code_cell() if cell_type == 'code' else nbformat.v4.new_markdown_cell()
                new_cell.source = new_source
                
                if cell_id:
                    # 在指定单元格后插入
                    insert_index = None
                    for i, cell in enumerate(nb.cells):
                        if hasattr(cell, 'id') and cell.id == cell_id:
                            insert_index = i + 1
                            break
                    
                    if insert_index is not None:
                        nb.cells.insert(insert_index, new_cell)
                    else:
                        raise ValidationError(f"Cell with id {cell_id} not found")
                else:
                    # 在开头插入
                    nb.cells.insert(0, new_cell)
                    
            elif edit_mode == "delete":
                # 删除单元格
                delete_index = None
                for i, cell in enumerate(nb.cells):
                    if hasattr(cell, 'id') and cell.id == cell_id:
                        delete_index = i
                        break
                
                if delete_index is not None:
                    del nb.cells[delete_index]
                else:
                    raise ValidationError(f"Cell with id {cell_id} not found")
            
            else:
                raise ValidationError(f"Invalid edit_mode: {edit_mode}")
            
            # 保存notebook
            with open(path, 'w', encoding='utf-8') as f:
                nbformat.write(nb, f)
            
            return {
                'status': 'success',
                'notebook_path': str(path),
                'edit_mode': edit_mode,
                'backup_path': str(backup_path)
            }
            
        except Exception as e:
            raise FileOperationError(f"NotebookEdit failed: {e}")


class WebFetchTool(BaseTool):
    """WebFetch工具 - 获取网页内容"""
    
    def __init__(self, manager: ToolManager):
        super().__init__()
        self.manager = manager
    
    async def execute(
        self,
        url: str,
        prompt: str
    ) -> str:
        """
        获取并处理网页内容
        
        Args:
            url: 目标URL
            prompt: 处理提示
            
        Returns:
            处理结果
        """
        self.validate_params(
            {'url': url, 'prompt': prompt},
            ['url', 'prompt']
        )
        
        # 验证URL
        parsed = urlparse(url)
        if not parsed.scheme:
            url = 'https://' + url
        elif parsed.scheme == 'http':
            url = url.replace('http://', 'https://', 1)
        
        # 检查缓存
        cache_key = f"{url}:{prompt}"
        cached = self.get_from_cache(cache_key)
        if cached:
            return cached
        
        try:
            # 获取网页内容
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    },
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    # 检查重定向
                    if str(response.url) != url:
                        original_host = urlparse(url).netloc
                        redirect_host = urlparse(str(response.url)).netloc
                        
                        if original_host != redirect_host:
                            return f"REDIRECT_DETECTED: The URL redirected to a different host: {response.url}"
                    
                    # 读取内容
                    content = await response.text()
            
            # 解析HTML
            soup = BeautifulSoup(content, 'html.parser')
            
            # 移除脚本和样式
            for script in soup(["script", "style"]):
                script.decompose()
            
            # 提取文本
            text = soup.get_text()
            
            # 清理文本
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            # 限制长度
            if len(text) > 50000:
                text = text[:50000] + "\n[Content truncated]"
            
            # 使用AI处理内容
            ai_prompt = f"""请分析以下网页内容并回答问题：

网页URL: {url}
网页内容:
{text}

问题/任务: {prompt}

请提供详细的分析和回答。"""
            
            result = await chat(ai_prompt)
            
            # 缓存结果
            self.set_cache(cache_key, result)
            
            return result
            
        except aiohttp.ClientError as e:
            raise NetworkError(f"Failed to fetch URL: {e}")
        except Exception as e:
            raise ToolError(f"WebFetch failed: {e}")


class TodoWriteTool(BaseTool):
    """TodoWrite工具 - 管理任务列表"""
    
    def __init__(self, manager: ToolManager):
        super().__init__()
        self.manager = manager
    
    async def execute(
        self,
        todos: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        更新任务列表
        
        Args:
            todos: 任务列表
            
        Returns:
            更新结果
        """
        self.validate_params({'todos': todos}, ['todos'])
        
        # 清空现有列表
        self.manager.todo_list.clear()
        
        # 验证并添加新任务
        for todo_data in todos:
            if 'content' not in todo_data or 'status' not in todo_data or 'id' not in todo_data:
                raise ValidationError("Each todo must have content, status, and id")
            
            if todo_data['status'] not in ['pending', 'in_progress', 'completed']:
                raise ValidationError(f"Invalid status: {todo_data['status']}")
            
            todo = TodoItem(
                id=todo_data['id'],
                content=todo_data['content'],
                status=todo_data['status']
            )
            
            self.manager.todo_list.append(todo)
        
        # 统计
        stats = {
            'total': len(self.manager.todo_list),
            'pending': sum(1 for t in self.manager.todo_list if t.status == 'pending'),
            'in_progress': sum(1 for t in self.manager.todo_list if t.status == 'in_progress'),
            'completed': sum(1 for t in self.manager.todo_list if t.status == 'completed'),
        }
        
        # 检查约束：只能有一个in_progress
        if stats['in_progress'] > 1:
            logger.warning(f"Multiple tasks in progress: {stats['in_progress']}")
        
        return {
            'status': 'success',
            'todos': [
                {
                    'id': t.id,
                    'content': t.content,
                    'status': t.status,
                    'created_at': t.created_at.isoformat(),
                    'updated_at': t.updated_at.isoformat()
                }
                for t in self.manager.todo_list
            ],
            'statistics': stats
        }


class WebSearchTool(BaseTool):
    """WebSearch工具 - 网页搜索"""
    
    def __init__(self, manager: ToolManager):
        super().__init__()
        self.manager = manager
        self.searcher = BingSearcher()
    
    async def execute(
        self,
        query: str,
        allowed_domains: Optional[List[str]] = None,
        blocked_domains: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        执行网页搜索
        
        Args:
            query: 搜索查询
            allowed_domains: 允许的域名列表
            blocked_domains: 阻止的域名列表
            
        Returns:
            搜索结果
        """
        self.validate_params({'query': query}, ['query'])
        
        if len(query) < 2:
            raise ValidationError("Query must be at least 2 characters long")
        
        try:
            # 执行搜索
            results = self.searcher.search(query, page=1)
            
            # 过滤结果
            if results.get('webPages') and results['webPages'].get('value'):
                filtered_results = []
                
                for result in results['webPages']['value']:
                    url = result.get('url', '')
                    domain = urlparse(url).netloc
                    
                    # 域名过滤
                    if allowed_domains:
                        if not any(domain.endswith(allowed) for allowed in allowed_domains):
                            continue
                    
                    if blocked_domains:
                        if any(domain.endswith(blocked) for blocked in blocked_domains):
                            continue
                    
                    filtered_results.append(result)
                
                results['webPages']['value'] = filtered_results
            
            # 格式化结果
            formatted_results = self._format_search_results(results)
            
            return formatted_results
            
        except Exception as e:
            raise NetworkError(f"Web search failed: {e}")
    
    def _format_search_results(self, raw_results: Dict[str, Any]) -> Dict[str, Any]:
        """格式化搜索结果"""
        formatted = {
            'query': raw_results.get('queryContext', {}).get('originalQuery', ''),
            'web_pages': [],
            'videos': [],
            'images': [],
            'related_searches': []
        }
        
        # 网页结果
        if raw_results.get('webPages'):
            for page in raw_results['webPages'].get('value', []):
                formatted['web_pages'].append({
                    'title': page.get('name', ''),
                    'url': page.get('url', ''),
                    'snippet': page.get('snippet', ''),
                    'display_url': page.get('displayUrl', '')
                })
        
        # 视频结果
        if raw_results.get('videos'):
            for video in raw_results['videos'].get('value', []):
                formatted['videos'].append({
                    'title': video.get('name', ''),
                    'url': video.get('webSearchUrl', ''),
                    'thumbnail': video.get('thumbnailUrl', ''),
                    'duration': video.get('duration', ''),
                    'publisher': video.get('publisher', [{}])[0].get('name', '')
                })
        
        # 图片结果
        if raw_results.get('images'):
            for image in raw_results['images'].get('value', []):
                formatted['images'].append({
                    'title': image.get('name', ''),
                    'url': image.get('hostPageUrl', ''),
                    'thumbnail': image.get('thumbnailUrl', ''),
                    'width': image.get('width', 0),
                    'height': image.get('height', 0)
                })
        
        # 相关搜索
        if raw_results.get('relatedSearches'):
            for related in raw_results['relatedSearches'].get('value', []):
                formatted['related_searches'].append({
                    'text': related.get('text', ''),
                    'url': related.get('webSearchUrl', '')
                })
        
        return formatted


class BashOutputTool(BaseTool):
    """BashOutput工具 - 获取后台bash输出"""
    
    def __init__(self, manager: ToolManager):
        super().__init__()
        self.manager = manager
    
    async def execute(
        self,
        bash_id: str,
        filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取后台bash会话输出
        
        Args:
            bash_id: 会话ID
            filter: 正则过滤模式
            
        Returns:
            输出结果
        """
        self.validate_params({'bash_id': bash_id}, ['bash_id'])
        
        if bash_id not in self.manager.bash_sessions:
            raise ValidationError(f"Bash session not found: {bash_id}")
        
        session = self.manager.bash_sessions[bash_id]
        
        # 获取新输出
        stdout_lines, stderr_lines = session.get_new_output(filter)
        
        # 检查进程状态
        is_running = session.is_running()
        exit_code = None if is_running else session.process.returncode
        
        return {
            'bash_id': bash_id,
            'status': 'running' if is_running else 'completed',
            'exit_code': exit_code,
            'stdout': '\n'.join(stdout_lines),
            'stderr': '\n'.join(stderr_lines),
            'lines_read': len(stdout_lines) + len(stderr_lines),
            'total_lines_buffered': len(session.output_buffer) + len(session.error_buffer)
        }


class KillBashTool(BaseTool):
    """KillBash工具 - 终止后台bash会话"""
    
    def __init__(self, manager: ToolManager):
        super().__init__()
        self.manager = manager
    
    async def execute(
        self,
        shell_id: str
    ) -> Dict[str, Any]:
        """
        终止后台bash会话
        
        Args:
            shell_id: 会话ID
            
        Returns:
            终止结果
        """
        self.validate_params({'shell_id': shell_id}, ['shell_id'])
        
        if shell_id not in self.manager.bash_sessions:
            raise ValidationError(f"Bash session not found: {shell_id}")
        
        session = self.manager.bash_sessions[shell_id]
        
        try:
            if session.is_running():
                # 尝试优雅终止
                session.process.terminate()
                
                # 等待进程结束
                try:
                    session.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # 强制终止
                    session.process.kill()
                    session.process.wait()
            
            # 收集最终输出
            final_stdout = '\n'.join(session.output_buffer)
            final_stderr = '\n'.join(session.error_buffer)
            
            # 移除会话
            del self.manager.bash_sessions[shell_id]
            
            return {
                'status': 'success',
                'shell_id': shell_id,
                'exit_code': session.process.returncode,
                'final_stdout': final_stdout[-5000:] if len(final_stdout) > 5000 else final_stdout,
                'final_stderr': final_stderr[-5000:] if len(final_stderr) > 5000 else final_stderr
            }
            
        except Exception as e:
            raise BashExecutionError(f"Failed to kill bash session: {e}")


# ==================== 工具集成和导出 ====================

# 创建全局工具管理器实例
tool_manager = ToolManager()


async def execute_tool(tool_name: str, **params) -> Any:
    """
    执行指定工具的公共接口
    
    Args:
        tool_name: 工具名称
        **params: 工具参数
        
    Returns:
        工具执行结果
    """
    return await tool_manager.execute_tool(tool_name, **params)


# 导出所有工具类和管理器
__all__ = [
    'ToolManager',
    'tool_manager',
    'execute_tool',
    'TaskTool',
    'BashTool',
    'GlobTool',
    'GrepTool',
    'LSTool',
    'ExitPlanModeTool',
    'ReadTool',
    'EditTool',
    'MultiEditTool',
    'WriteTool',
    'NotebookEditTool',
    'WebFetchTool',
    'TodoWriteTool',
    'WebSearchTool',
    'BashOutputTool',
    'KillBashTool',
    'ToolError',
    'FileOperationError',
    'BashExecutionError',
    'NetworkError',
    'ValidationError'
]


# ==================== 测试代码（可选） ====================

if __name__ == "__main__":
    # 测试工具功能
    async def test_tools():
        """测试所有工具的基本功能"""
        print("开始测试工具集...")
        
        # 测试LS工具
        try:
            result = await execute_tool('LS', path=os.getcwd())
            print(result)
            print(f"LS测试成功: 找到 {len(result)} 个项目")
        except Exception as e:
            print(f"LS测试失败: {e}")
        
        # 测试Glob工具
        try:
            result = await execute_tool('Glob', pattern="*.py")
            print(result)
            print(f"Glob测试成功: 找到 {len(result)} 个Python文件")
        except Exception as e:
            print(f"Glob测试失败: {e}")
        
        print("测试完成")
    
    # 运行测试
    asyncio.run(test_tools())
