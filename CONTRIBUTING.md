# 贡献指南

感谢您对 AI 多模型集成服务器项目的兴趣！我们欢迎各种形式的贡献。

## 🎯 贡献方式

### 🐛 报告问题
- 使用 [GitHub Issues](https://github.com/nichengfuben/EchoServer/issues) 报告 bug
- 提供详细的复现步骤和环境信息
- 添加相关日志和错误信息

### 💡 功能建议
- 在 [GitHub Discussions](https://github.com/nichengfuben/EchoServer/discussions) 中讨论新功能
- 说明功能的用途和预期行为
- 考虑向后兼容性

### 🔧 代码贡献
1. Fork 项目仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 📋 开发规范

### 代码风格
- 遵循 [PEP 8](https://pep8.org/) Python 编码规范
- 使用 [Black](https://black.readthedocs.io/) 格式化代码
- 使用 [isort](https://pycqa.github.io/isort/) 排序导入
- 添加类型注解（使用 `typing` 模块）

### 文档要求
- 为所有公共函数和类编写文档字符串
- 遵循 [Google Style Docstrings](https://google.github.io/styleguide/pyguide.html#383-functions-and-methods)
- 更新相关文档和示例

### 测试要求
- 为新功能编写单元测试
- 确保所有测试通过
- 保持测试覆盖率在 90% 以上

### 提交信息
- 使用清晰的提交信息
- 遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范
- 示例：`feat: add support for Claude model`

## 🚀 开发环境设置

### 1. 环境准备
```bash
# 克隆项目
git clone https://github.com/nichengfuben/EchoServer.git
cd ai-multi-model-server

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate     # Windows

# 安装开发依赖
pip install -r requirements-dev.txt
```

### 2. 代码质量检查
```bash
# 格式化代码
black src/
isort src/

# 类型检查
mypy src/

# 代码检查
flake8 src/
pylint src/

# 运行测试
pytest

# 生成测试报告
pytest --cov=src --cov-report=html
```

### 3. 预提交钩子
```bash
# 安装预提交钩子
pre-commit install

# 手动运行
pre-commit run --all-files
```

## 📁 项目结构

```
ai-multi-model-server/
├── src/
│   ├── client/          # 客户端实现
│   ├── data/           # 数据配置
│   ├── models/         # 模型定义
│   ├── services/       # 业务逻辑
│   └── utils/          # 工具函数
├── tests/
│   ├── unit/           # 单元测试
│   ├── integration/    # 集成测试
│   └── fixtures/       # 测试数据
├── docs/               # 文档
├── scripts/            # 脚本工具
└── config/             # 配置文件
```

## 🔧 开发指南

### 添加新模型
1. 在 `src/client/` 中创建新的客户端文件
2. 实现统一的接口方法（`quick_chat`, `quick_stream`）
3. 在 `client_server.py` 中注册新模型
4. 更新模型配置和文档
5. 添加相应的测试

### 性能优化
- 使用异步编程避免阻塞
- 合理使用缓存机制
- 优化数据库查询
- 使用连接池管理资源

### 错误处理
- 使用适当的异常类型
- 提供有用的错误信息
- 记录关键错误日志
- 实现优雅的错误恢复

## 📊 测试指南

### 测试类型
- **单元测试**: 测试单个函数和类
- **集成测试**: 测试模块间的交互
- **端到端测试**: 测试完整的用户流程

### 测试最佳实践
- 使用 pytest 作为测试框架
- 使用 fixtures 管理测试数据
- 使用 mocking 隔离外部依赖
- 测试边界条件和异常情况

### 示例测试
```python
import pytest
from src.client.qwen_client import quick_chat

@pytest.mark.asyncio
async def test_quick_chat():
    """测试通义千问聊天功能"""
    result = await quick_chat("你好")
    assert isinstance(result, str)
    assert len(result) > 0
    assert "错误" not in result
```

## 📋 Pull Request 模板

### PR 标题格式
```
类型: 简短描述

示例:
- feat: add support for Claude model
- fix: resolve timeout issue in stream processing
- docs: update API documentation
- test: add unit tests for new feature
```

### PR 描述模板
```markdown
## 描述
简要描述这个 PR 的目的和主要更改

## 更改类型
- [ ] Bug 修复
- [ ] 新功能
- [ ] 代码重构
- [ ] 文档更新
- [ ] 性能优化

## 测试
- [ ] 添加了新的测试
- [ ] 所有现有测试通过
- [ ] 手动测试完成

## 检查清单
- [ ] 代码遵循项目编码规范
- [ ] 添加了适当的文档
- [ ] 更新了相关测试
- [ ] 考虑了向后兼容性

## 截图（如适用）
如果更改涉及 UI，请添加截图

## 相关问题
关闭 #123
```

## 🏷️ 标签说明

- `bug`: Bug 修复
- `enhancement`: 功能增强
- `feature`: 新功能
- `documentation`: 文档更新
- `performance`: 性能优化
- `refactor`: 代码重构
- `test`: 测试相关
- `dependencies`: 依赖更新

## 📞 联系方式

如有问题，请通过以下方式联系：
- GitHub Issues
- GitHub Discussions
- 项目维护者邮箱

再次感谢您的贡献！ 🎉