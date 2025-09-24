# AI Multi-Model Integration Server

A high-performance asynchronous AI multi-model integration server supporting various AI models including Tongyi Qianwen, OpenRouter, Cerebras, and more, providing a unified OpenAI-compatible API.

## ✨ Features

- 🚀 **Multi-Model Integration**: Support for 7+ mainstream AI models
- ⚡ **Async Processing**: High-performance asynchronous architecture based on asyncio
- 🎯 **Smart Selection**: KL-UCB algorithm for automatic optimal model selection
- 📊 **Streaming Response**: SSE streaming output support
- 🌐 **Multimodal**: Full support for text, images, audio, video, and documents
- 🔒 **High Concurrency**: Support for 100+ concurrent requests
- 📈 **Monitoring**: Detailed performance monitoring and statistics

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/your-username/ai-multi-model-server.git
cd ai-multi-model-server

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### Run

```bash
python main.py
```

The server will start at `http://localhost:8000`

### Test

```bash
# Test chat endpoint
curl -X POST http://localhost:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "auto_chat",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'
```

## 📖 Documentation

- [API Documentation](docs/api.md)
- [Deployment Guide](docs/deployment.md)
- [Development Guide](docs/development.md)
- [Architecture Design](docs/architecture.md)

## 🤝 Contributing

Contributions are welcome! Please check [CONTRIBUTING.md](CONTRIBUTING.md) to learn how to participate.

## 📄 License

MIT License - See [LICENSE](LICENSE) file for details

## 🙏 Acknowledgments

Thanks to all developers and open source communities who contributed to this project!