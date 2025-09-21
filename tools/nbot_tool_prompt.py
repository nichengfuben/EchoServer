def get_tool_description(tool_name: str) -> str:
    """获取工具描述"""
    
    tool_descriptions = {
        "mcp__ide__executeCode": """
工具名称：执行IDE代码
工具描述：在IDE环境中执行代码片段
调用前请遵循以下步骤：

执行：
   - 始终验证代码安全性
   - 确保执行环境隔离后执行

使用说明：
  - code为必填项（要执行的代码）
  - language为可选项（编程语言，默认python）
  - 返回执行结果和输出
    [正确示例]
    {"tool": "mcp__ide__executeCode", "args": {"code": "print(1+1)", "language": "python"}}
    [错误示例]
    {"tool": "mcp__ide__executeCode", "args": {}}  # 缺少代码
    [错误示例]
""",
        "task": """
工具名称：任务分发
工具描述：启动新代理处理复杂任务
调用前请遵循以下步骤：

执行：
   - 提供详细的任务描述
   - 指定具体的任务提示词
   - 选择合适的子代理类型

使用说明：
  - description为必填项（任务详细描述）
  - prompt为必填项（任务提示词）
  - subagent_type为可选项（子代理类型，默认为general-purpose）
  - 支持的类型：general-purpose, programming, analysis, creative, research, debugging, documentation, testing
    [正确示例]
    {"tool": "task", "args": {"description": "编写一个Python函数", "prompt": "实现快速排序算法", "subagent_type": "programming"}}
    [错误示例]
    {"tool": "task", "args": {"description": "编写函数"}}  # 缺少prompt
    [错误示例]
"""
    }
    
    return tool_descriptions.get(tool_name, f"工具名称：{tool_name}\n工具描述：未知工具，请检查工具名称是否正确")
