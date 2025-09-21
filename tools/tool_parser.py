"""
工具解析器模块 - 解析和执行工具调用
遵循 DDD + TDD 原则，提供完整的工具调用解析和执行功能
"""

import asyncio
import json
import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime
import sys
import os
# 导入所有工具
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.tools import *

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tool_parser.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ==================== 异常定义 ====================

class ToolParseError(Exception):
    """工具解析异常"""
    pass


class ToolExecutionError(Exception):
    """工具执行异常"""
    pass


class InvalidToolCallError(ToolParseError):
    """无效工具调用异常"""
    pass


# ==================== 数据类定义 ====================

@dataclass
class ToolCall:
    """工具调用数据类"""
    tool: str
    args: Dict[str, Any]
    function_id: str = None
    
    def __post_init__(self):
        if self.function_id is None:
            self.function_id = self._generate_function_id()
    
    def _generate_function_id(self) -> str:
        """生成唯一的 Function ID"""
        return f"toolu_{uuid.uuid4().hex[:24]}"


@dataclass
class ToolResult:
    """工具执行结果数据类"""
    function_id: str
    tool_name: str
    arguments: Dict[str, Any]
    result: Any
    formatted_result: str
    execution_time: float
    success: bool
    error_message: Optional[str] = None


# ==================== 核心解析器类 ====================

class ToolParser:
    """工具解析器 - 解析和执行工具调用"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.tool_manager = tool_manager
        self.formatters = self._initialize_formatters()
    
    def _initialize_formatters(self) -> Dict[str, callable]:
        """初始化结果格式化器"""
        return {
            'Task': self._format_task_result,
            'Bash': self._format_bash_result,
            'Glob': self._format_glob_result,
            'Grep': self._format_grep_result,
            'LS': self._format_ls_result,
            'ExitPlanMode': self._format_exit_plan_result,
            'Read': self._format_read_result,
            'Edit': self._format_edit_result,
            'MultiEdit': self._format_multi_edit_result,
            'Write': self._format_write_result,
            'NotebookEdit': self._format_notebook_edit_result,
            'WebFetch': self._format_web_fetch_result,
            'TodoWrite': self._format_todo_write_result,
            'WebSearch': self._format_web_search_result,
            'BashOutput': self._format_bash_output_result,
            'KillBash': self._format_kill_bash_result,
        }
    
    def parse_tool_calls(self, text: str) -> List[ToolCall]:
        """
        从文本中解析所有工具调用
        
        Args:
            text: 包含工具调用的文本
            
        Returns:
            解析出的工具调用列表
        """
        # 匹配工具调用模式
        pattern = r'<tool_call>(.*?)</tool_call>'
        matches = re.findall(pattern, text, re.DOTALL)
        
        tool_calls = []
        
        for match in matches:
            try:
                # 清理和预处理 JSON 字符串
                cleaned_json = self._clean_json_string(match.strip())
                
                # 解析 JSON
                call_data = json.loads(cleaned_json)
                
                # 验证必需字段
                if 'tool' not in call_data:
                    raise InvalidToolCallError("Missing 'tool' field in tool call")
                
                # 创建工具调用对象
                tool_call = ToolCall(
                    tool=call_data['tool'],
                    args=call_data.get('args', {})
                )
                
                tool_calls.append(tool_call)
                
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON decode error: {e}")
                raise InvalidToolCallError(f"Invalid JSON in tool call: {e}")
            except Exception as e:
                self.logger.error(f"Error parsing tool call: {e}")
                raise ToolParseError(f"Failed to parse tool call: {e}")
        
        return tool_calls
    
    def _clean_json_string(self, json_str: str) -> str:
        """
        清理和预处理 JSON 字符串
        
        Args:
            json_str: 原始 JSON 字符串
            
        Returns:
            清理后的 JSON 字符串
        """
        # 移除多余的空白字符
        json_str = json_str.strip()
        
        # 处理 Windows 路径中的反斜杠
        # 先将 \\ 替换为临时标记，避免误处理
        json_str = json_str.replace('\\\\', '__DOUBLE_BACKSLASH__')
        # 将单个 \ 替换为 \\
        json_str = json_str.replace('\\', '\\\\')
        # 恢复双反斜杠
        json_str = json_str.replace('__DOUBLE_BACKSLASH__', '\\\\')
        
        # 处理常见的控制字符
        control_chars = {
            '\b': '\\b',
            '\f': '\\f',
            '\n': '\\n',
            '\r': '\\r',
            '\t': '\\t',
        }
        
        for char, escaped in control_chars.items():
            json_str = json_str.replace(char, escaped)
        
        return json_str
    
    async def execute_tool_call(self, tool_call: ToolCall) -> ToolResult:
        """
        执行单个工具调用
        
        Args:
            tool_call: 工具调用对象
            
        Returns:
            工具执行结果
        """
        start_time = datetime.now()
        
        try:
            # 验证工具是否存在
            if tool_call.tool not in self.tool_manager.tools:
                raise ToolExecutionError(f"Unknown tool: {tool_call.tool}")
            
            # 执行工具
            result = await self.tool_manager.execute_tool(
                tool_call.tool, 
                **tool_call.args
            )
            
            # 计算执行时间
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # 格式化结果
            formatted_result = self._format_result(tool_call.tool, result)
            
            return ToolResult(
                function_id=tool_call.function_id,
                tool_name=tool_call.tool,
                arguments=tool_call.args,
                result=result,
                formatted_result=formatted_result,
                execution_time=execution_time,
                success=True
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            
            self.logger.error(f"Tool execution failed: {e}")
            
            return ToolResult(
                function_id=tool_call.function_id,
                tool_name=tool_call.tool,
                arguments=tool_call.args,
                result=None,
                formatted_result=f"Tool execution failed: {str(e)}",
                execution_time=execution_time,
                success=False,
                error_message=str(e)
            )
    
    def _format_result(self, tool_name: str, result: Any) -> str:
        """
        格式化工具执行结果
        
        Args:
            tool_name: 工具名称
            result: 执行结果
            
        Returns:
            格式化的结果字符串
        """
        if tool_name in self.formatters:
            return self.formatters[tool_name](result)
        else:
            # 默认格式化
            return f"Tool '{tool_name}' executed successfully. Result: {str(result)}"
    
    # ==================== 结果格式化器 ====================
    
    def _format_task_result(self, result: Dict[str, Any]) -> str:
        """格式化 Task 工具结果"""
        if result.get('status') == 'success':
            return f"Subagent task completed successfully. Agent ID: {result.get('agent_id', 'unknown')}. Result: {result.get('result', 'No result')}"
        else:
            return f"Subagent task failed. Agent ID: {result.get('agent_id', 'unknown')}. Error: {result.get('error', 'Unknown error')}"
    
    def _format_bash_result(self, result: Dict[str, Any]) -> str:
        """格式化 Bash 工具结果"""
        if 'bash_id' in result:
            # 后台执行
            return f"Background bash session started successfully. Session ID: {result['bash_id']}, PID: {result.get('pid', 'unknown')}, Status: {result.get('status', 'unknown')}"
        else:
            # 前台执行
            exit_code = result.get('exit_code', -1)
            stdout = result.get('stdout', '').strip()
            stderr = result.get('stderr', '').strip()
            
            status_msg = f"Command executed with exit code {exit_code}"
            
            output_parts = []
            if stdout:
                output_parts.append(f"Output: {stdout}")
            if stderr:
                output_parts.append(f"Errors: {stderr}")
            
            if output_parts:
                return f"{status_msg}. {' | '.join(output_parts)}"
            else:
                return f"{status_msg}. No output."
    
    def _format_glob_result(self, result: List[str]) -> str:
        """格式化 Glob 工具结果"""
        if not result:
            return "No files found matching the pattern"
        
        count = len(result)
        if count == 1:
            return f"Found 1 file: {result[0]}"
        elif count <= 10:
            file_list = '\n'.join(f"  {file}" for file in result)
            return f"Found {count} files:\n{file_list}"
        else:
            first_files = '\n'.join(f"  {file}" for file in result[:10])
            return f"Found {count} files (showing first 10):\n{first_files}\n  ... and {count - 10} more files"
    
    def _format_grep_result(self, result: Union[List[str], Dict[str, Any], str]) -> str:
        """格式化 Grep 工具结果"""
        if isinstance(result, list):
            if not result:
                return "No matches found"
            count = len(result)
            return f"Found {count} matching files: {', '.join(result)}"
        
        elif isinstance(result, dict):
            total_matches = sum(result.values())
            return f"Found matches in {len(result)} files with {total_matches} total occurrences"
        
        elif isinstance(result, str):
            if not result.strip():
                return "No matches found"
            line_count = len(result.split('\n'))
            return f"Found matches in {line_count} lines. Content:\n{result}"
        
        else:
            return f"Search completed. Result: {str(result)}"
    
    def _format_ls_result(self, result: List[Dict[str, Any]]) -> str:
        """格式化 LS 工具结果"""
        if not result:
            return "Directory is empty"
        
        dirs = [item for item in result if item['type'] == 'directory']
        files = [item for item in result if item['type'] == 'file']
        
        summary_parts = []
        if dirs:
            summary_parts.append(f"{len(dirs)} directories")
        if files:
            summary_parts.append(f"{len(files)} files")
        
        summary = f"Listed directory contents: {', '.join(summary_parts)}"
        
        if len(result) <= 20:
            items = []
            for item in result:
                size_str = f" ({item['size']} bytes)" if item['type'] == 'file' else ""
                items.append(f"  {item['name']} [{item['type']}]{size_str}")
            return f"{summary}:\n" + '\n'.join(items)
        else:
            return f"{summary} (total {len(result)} items)"
    
    def _format_exit_plan_result(self, result: Dict[str, Any]) -> str:
        """格式化 ExitPlanMode 工具结果"""
        return f"Exited plan mode successfully. Plan summary: {result.get('plan_summary', 'No summary available')}. Status: {result.get('next_action', 'unknown')}"
    
    def _format_read_result(self, result: Union[str, Dict[str, Any]]) -> str:
        """格式化 Read 工具结果"""
        if isinstance(result, str):
            line_count = len(result.split('\n'))
            char_count = len(result)
            return f"File read successfully. Content: {line_count} lines, {char_count} characters"
        
        elif isinstance(result, dict):
            if result.get('type') == 'image':
                return f"Image file read successfully. Format: {result.get('format', 'unknown')}, Size: {result.get('width', 0)}x{result.get('height', 0)} pixels"
            
            elif result.get('type') == 'pdf':
                page_count = result.get('metadata', {}).get('page_count', 0)
                return f"PDF file read successfully. Pages: {page_count}, Title: {result.get('metadata', {}).get('title', 'Unknown')}"
            
            elif result.get('type') == 'notebook':
                cell_count = len(result.get('cells', []))
                return f"Jupyter notebook read successfully. Cells: {cell_count}"
            
            else:
                return f"Structured file read successfully. Type: {result.get('type', 'unknown')}"
        
        else:
            return f"File read completed. Result: {str(result)}"
    
    def _format_edit_result(self, result: Dict[str, Any]) -> str:
        """格式化 Edit 工具结果"""
        if result.get('status') == 'success':
            replacements = result.get('replacements', 0)
            file_path = result.get('file_path', 'unknown')
            backup_path = result.get('backup_path', '')
            
            backup_msg = f" (backup: {backup_path})" if backup_path else ""
            return f"File edited successfully at: {file_path}. Replacements made: {replacements}{backup_msg}"
        else:
            return f"File edit failed: {result}"
    
    def _format_multi_edit_result(self, result: Dict[str, Any]) -> str:
        """格式化 MultiEdit 工具结果"""
        if result.get('status') == 'success':
            edits_applied = result.get('edits_applied', 0)
            total_replacements = result.get('total_replacements', 0)
            file_path = result.get('file_path', 'unknown')
            backup_path = result.get('backup_path', '')
            
            backup_msg = f" (backup: {backup_path})" if backup_path else ""
            return f"File multi-edited successfully at: {file_path}. Edits applied: {edits_applied}, Total replacements: {total_replacements}{backup_msg}"
        else:
            return f"File multi-edit failed: {result}"
    
    def _format_write_result(self, result: Dict[str, Any]) -> str:
        """格式化 Write 工具结果"""
        if result.get('status') == 'success':
            file_path = result.get('file_path', 'unknown')
            bytes_written = result.get('bytes_written', 0)
            backup_path = result.get('backup_path', '')
            
            backup_msg = f" (backup: {backup_path})" if backup_path else ""
            return f"File created successfully at: {file_path}. Bytes written: {bytes_written}{backup_msg}"
        else:
            return f"File write failed: {result}"
    
    def _format_notebook_edit_result(self, result: Dict[str, Any]) -> str:
        """格式化 NotebookEdit 工具结果"""
        if result.get('status') == 'success':
            notebook_path = result.get('notebook_path', 'unknown')
            edit_mode = result.get('edit_mode', 'unknown')
            backup_path = result.get('backup_path', '')
            
            backup_msg = f" (backup: {backup_path})" if backup_path else ""
            return f"Jupyter notebook edited successfully at: {notebook_path}. Edit mode: {edit_mode}{backup_msg}"
        else:
            return f"Notebook edit failed: {result}"
    
    def _format_web_fetch_result(self, result: str) -> str:
        """格式化 WebFetch 工具结果"""
        if result.startswith("REDIRECT_DETECTED"):
            return f"Web fetch completed with redirect: {result}"
        else:
            content_length = len(result)
            return f"Web content fetched successfully. Content length: {content_length} characters. Analysis result: {result[:200]}{'...' if content_length > 200 else ''}"
    
    def _format_todo_write_result(self, result: Dict[str, Any]) -> str:
        """格式化 TodoWrite 工具结果"""
        if result.get('status') == 'success':
            stats = result.get('statistics', {})
            total = stats.get('total', 0)
            pending = stats.get('pending', 0)
            in_progress = stats.get('in_progress', 0)
            completed = stats.get('completed', 0)
            
            return f"Todo list updated successfully. Total tasks: {total} (Pending: {pending}, In Progress: {in_progress}, Completed: {completed})"
        else:
            return f"Todo update failed: {result}"
    
    def _format_web_search_result(self, result: Dict[str, Any]) -> str:
        """格式化 WebSearch 工具结果"""
        query = result.get('query', 'unknown')
        web_pages = result.get('web_pages', [])
        videos = result.get('videos', [])
        images = result.get('images', [])
        related_searches = result.get('related_searches', [])
        
        result_counts = []
        if web_pages:
            result_counts.append(f"{len(web_pages)} web pages")
        if videos:
            result_counts.append(f"{len(videos)} videos")
        if images:
            result_counts.append(f"{len(images)} images")
        if related_searches:
            result_counts.append(f"{len(related_searches)} related searches")
        
        if result_counts:
            return f"Web search completed for query '{query}'. Found: {', '.join(result_counts)}"
        else:
            return f"Web search completed for query '{query}'. No results found"
    
    def _format_bash_output_result(self, result: Dict[str, Any]) -> str:
        """格式化 BashOutput 工具结果"""
        bash_id = result.get('bash_id', 'unknown')
        status = result.get('status', 'unknown')
        lines_read = result.get('lines_read', 0)
        stdout = result.get('stdout', '').strip()
        stderr = result.get('stderr', '').strip()
        
        output_parts = []
        if stdout:
            output_parts.append(f"Output: {stdout}")
        if stderr:
            output_parts.append(f"Errors: {stderr}")
        
        base_msg = f"Bash session {bash_id} output retrieved. Status: {status}, Lines read: {lines_read}"
        
        if output_parts:
            return f"{base_msg}. {' | '.join(output_parts)}"
        else:
            return f"{base_msg}. No new output"
    
    def _format_kill_bash_result(self, result: Dict[str, Any]) -> str:
        """格式化 KillBash 工具结果"""
        if result.get('status') == 'success':
            shell_id = result.get('shell_id', 'unknown')
            exit_code = result.get('exit_code', 'unknown')
            
            final_stdout = result.get('final_stdout', '').strip()
            final_stderr = result.get('final_stderr', '').strip()
            
            output_parts = []
            if final_stdout:
                output_parts.append(f"Final output: {final_stdout}")
            if final_stderr:
                output_parts.append(f"Final errors: {final_stderr}")
            
            base_msg = f"Bash session {shell_id} terminated successfully. Exit code: {exit_code}"
            
            if output_parts:
                return f"{base_msg}. {' | '.join(output_parts)}"
            else:
                return f"{base_msg}. No final output"
        else:
            return f"Bash session termination failed: {result}"


# ==================== 主函数接口 ====================

async def parse_and_execute_tools(text: str) -> str:
    """
    解析文本中的工具调用并执行，返回格式化的结果
    
    Args:
        text: 包含工具调用的文本
        
    Returns:
        格式化的执行结果字符串
    """
    parser = ToolParser()
    
    try:
        # 解析工具调用
        tool_calls = parser.parse_tool_calls(text)
        
        if not tool_calls:
            return text  # 没有工具调用，返回原文本
        
        # 分割文本并插入执行结果
        result_parts = []
        last_end = 0
        
        # 重新查找工具调用位置以便正确插入结果
        pattern = r'<tool_call>(.*?)</tool_call>'
        matches = list(re.finditer(pattern, text, re.DOTALL))
        
        for i, (tool_call, match) in enumerate(zip(tool_calls, matches)):
            # 添加工具调用前的文本
            result_parts.append(text[last_end:match.start()])
            
            # 添加工具调用信息
            result_parts.append("Tools")
            result_parts.append(f"Function ID: {tool_call.function_id}")
            result_parts.append(f"Function Name: {tool_call.tool}")
            result_parts.append("Function Arguments:")
            
            # 格式化参数
            formatted_args = json.dumps(tool_call.args, indent=2, ensure_ascii=False)
            result_parts.append(formatted_args)
            
            result_parts.append("tool")
            
            # 执行工具
            execution_result = await parser.execute_tool_call(tool_call)
            
            # 添加执行结果
            result_parts.append(f"Tool ID: {execution_result.function_id}")
            result_parts.append(execution_result.formatted_result)
            
            last_end = match.end()
        
        # 添加剩余文本
        result_parts.append(text[last_end:])
        
        return '\n'.join(result_parts)
        
    except Exception as e:
        logger.error(f"Error parsing and executing tools: {e}")
        return f"{text}\n\nError executing tools: {str(e)}"


def parse_and_execute_tools_sync(text: str) -> str:
    """
    同步版本的工具解析和执行函数
    
    Args:
        text: 包含工具调用的文本
        
    Returns:
        格式化的执行结果字符串
    """
    return asyncio.run(parse_and_execute_tools(text))


# ==================== 测试代码 ====================

if __name__ == "__main__":
    async def test_all_tools():
        """测试所有工具的完整功能"""
        print("开始测试所有工具...")
        print("=" * 60)
        
        test_cases = [
            # 1. TaskTool 测试
            {
                "name": "TaskTool",
                "call": '''<tool_call>{"tool": "Task", "args": {"description": "Test subagent", "prompt": "Hello, this is a test task.", "subagent_type": "general-purpose"}}</tool_call>'''
            },
            
            # 2. BashTool 测试 - 前台执行
            {
                "name": "BashTool (foreground)",
                "call": '''<tool_call>{"tool": "Bash", "args": {"command": "echo Hello World", "description": "Test echo command"}}</tool_call>'''
            },
            
            # 3. BashTool 测试 - 后台执行
            {
                "name": "BashTool (background)",
                "call": '''<tool_call>{"tool": "Bash", "args": {"command": "ping -c 3 127.0.0.1", "run_in_background": true, "description": "Test background ping"}}</tool_call>'''
            },
            
            # 4. GlobTool 测试
            {
                "name": "GlobTool",
                "call": '''<tool_call>{"tool": "Glob", "args": {"pattern": "*.py"}}</tool_call>'''
            },
            
            # 5. LSTool 测试
            {
                "name": "LSTool",
                "call": f'''<tool_call>{{"tool": "LS", "args": {{"path": "{Path.cwd().as_posix()}"}}}}</tool_call>'''
            },
            
            # 6. WriteTool 测试
            {
                "name": "WriteTool",
                "call": f'''<tool_call>{{"tool": "Write", "args": {{"file_path": "{(Path.cwd() / 'test_file.txt').as_posix()}", "content": "This is a test file.\\nLine 2 of test content."}}}}</tool_call>'''
            },
            
            # 7. ReadTool 测试
            {
                "name": "ReadTool",
                "call": f'''<tool_call>{{"tool": "Read", "args": {{"file_path": "{(Path.cwd() / 'test_file.txt').as_posix()}"}}}}</tool_call>'''
            },
            
            # 8. EditTool 测试
            {
                "name": "EditTool",
                "call": f'''<tool_call>{{"tool": "Edit", "args": {{"file_path": "{(Path.cwd() / 'test_file.txt').as_posix()}", "old_string": "This is a test file.", "new_string": "This is an edited test file."}}}}</tool_call>'''
            },
            
            # 9. GrepTool 测试
            {
                "name": "GrepTool",
                "call": '''<tool_call>{"tool": "Grep", "args": {"pattern": "test", "output_mode": "files_with_matches"}}</tool_call>'''
            },
            
            # 10. MultiEditTool 测试
            {
                "name": "MultiEditTool",
                "call": f'''<tool_call>{{"tool": "MultiEdit", "args": {{"file_path": "{(Path.cwd() / 'test_multi.txt').as_posix()}", "edits": [{{"old_string": "", "new_string": "First line\\nSecond line\\nThird line"}}, {{"old_string": "Second", "new_string": "Modified"}}]}}}}</tool_call>'''
            },
            
            # 11. TodoWriteTool 测试
            {
                "name": "TodoWriteTool",
                "call": '''<tool_call>{"tool": "TodoWrite", "args": {"todos": [{"id": "1", "content": "Test task 1", "status": "pending"}, {"id": "2", "content": "Test task 2", "status": "in_progress"}]}}</tool_call>'''
            },
            
            # 12. ExitPlanModeTool 测试
            {
                "name": "ExitPlanModeTool",
                "call": '''<tool_call>{"tool": "ExitPlanMode", "args": {"plan": "This is a test plan with multiple steps: 1. Initialize project 2. Write code 3. Test functionality"}}</tool_call>'''
            },
            
            # 13. WebSearchTool 测试
            {
                "name": "WebSearchTool",
                "call": '''<tool_call>{"tool": "WebSearch", "args": {"query": "Python programming"}}</tool_call>'''
            },
            
            # 14. WebFetchTool 测试
            {
                "name": "WebFetchTool",
                "call": '''<tool_call>{"tool": "WebFetch", "args": {"url": "https://httpbin.org/get", "prompt": "Extract and summarize the response data"}}</tool_call>'''
            },
        ]
        
        # 执行所有测试用例
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n{i}. 测试 {test_case['name']}:")
            print("-" * 40)
            
            try:
                result = await parse_and_execute_tools(test_case['call'])
                print(result)
                print(f"✅ {test_case['name']} 测试成功")
                
                # 添加延迟避免请求过快
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"❌ {test_case['name']} 测试失败: {e}")
                logger.error(f"Test {test_case['name']} failed: {e}")
        
        print("\n" + "=" * 60)
        print("所有工具测试完成")
        
        # 清理测试文件
        try:
            test_files = [
                Path.cwd() / 'test_file.txt',
                Path.cwd() / 'test_file.txt.bak',
                Path.cwd() / 'test_multi.txt',
                Path.cwd() / 'test_multi.txt.bak'
            ]
            
            for file in test_files:
                if file.exists():
                    file.unlink()
                    print(f"已清理测试文件: {file}")
                    
        except Exception as e:
            print(f"清理测试文件时出错: {e}")
    
    # 运行测试
    asyncio.run(test_all_tools())
