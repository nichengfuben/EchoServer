# AI Multi-Model Integration Server

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Quart](https://img.shields.io/badge/web-quart-orange.svg)](https://quart.palletsprojects.com/)

一个高性能的异步 AI 多模型集成服务器，支持通义千问、OpenRouter、Cerebras 等多种 AI 模型，提供统一的 OpenAI 兼容 API。

## ✨ 特性

- 🚀 **多模型集成**: 支持 7+ 种主流 AI 模型
- ⚡ **异步处理**: 基于 asyncio 的高性能异步架构
- 🎯 **智能选择**: KL-UCB 算法自动选择最优模型
- 📊 **流式响应**: 支持 SSE 流式输出
- 🌐 **多模态**: 文本、图像、音频、视频、文档全支持
- 🔒 **高并发**: 支持 100+ 并发请求
- 📈 **监控统计**: 详细的性能监控和统计

## 🚀 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/your-username/ai-multi-model-server.git
cd ai-multi-model-server

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt
```

### 运行

```bash
python main.py
```

服务器将在 `http://localhost:8000` 启动

### 测试

```bash
# 测试聊天接口
curl -X POST http://localhost:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "auto_chat",
    "messages": [{"role": "user", "content": "你好！"}],
    "stream": false
  }'
```

## 📖 文档

- [API 文档](docs/api.md)
- [部署指南](docs/deployment.md)
- [开发指南](docs/development.md)
- [架构设计](docs/architecture.md)

## 🤝 贡献

欢迎贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解如何参与。

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

感谢所有为这个项目做出贡献的开发者和开源社区！