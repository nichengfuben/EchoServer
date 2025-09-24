# 项目依赖说明

## 核心依赖

### Web 框架
- **quart==0.19.4**: 异步 Web 框架，提供高性能的 HTTP 服务
- **aiohttp==3.9.1**: 异步 HTTP 客户端/服务器框架，用于处理外部 API 调用

### 数据处理
- **numpy==1.24.3**: 数值计算库，用于 KL-UCB 算法实现
- **requests==2.31.0**: 同步 HTTP 客户端，用于部分 API 调用

### 文件处理
- **python-multipart==0.0.6**: 处理 multipart/form-data 请求，支持文件上传

### 类型支持
- **typing-extensions==4.9.0**: 提供额外的类型注解支持

## 依赖版本说明

### 版本兼容性
- Python 3.8+: 项目基于 Python 3.8+ 的异步特性
- 所有依赖均选择稳定版本，确保兼容性

### 安全考虑
- 所有依赖均为最新稳定版本
- 定期更新以修复安全漏洞
- 使用虚拟环境隔离依赖

## 安装方式

### 生产环境
```bash
pip install -r requirements.txt
```

### 开发环境
```bash
pip install -r requirements-dev.txt
```

## 依赖管理

### 添加新依赖
1. 更新 `requirements.txt`
2. 测试兼容性
3. 更新文档

### 升级依赖
```bash
pip install --upgrade -r requirements.txt
pip freeze > requirements.txt
```

## 可选依赖

### 性能优化
- **uvloop**: 更快的 asyncio 事件循环
- **cchardet**: 更快的字符编码检测

### 监控和日志
- **prometheus-client**: Prometheus 监控集成
- **structlog**: 结构化日志记录

### 数据库支持
- **sqlalchemy**: ORM 框架
- **asyncpg**: PostgreSQL 异步驱动

## 依赖冲突解决

### 常见冲突
1. **aiohttp 版本冲突**: 确保使用兼容版本
2. **typing-extensions 冲突**: 使用最新版本

### 解决方案
- 使用虚拟环境
- 锁定依赖版本
- 定期更新和测试