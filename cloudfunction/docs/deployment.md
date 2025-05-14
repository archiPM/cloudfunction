# 部署指南

## 环境要求
- Python 3.8+
- pip 包管理器
- 操作系统：支持 Windows 和 Unix-like 系统

## 部署步骤

### 1. 环境准备
1. 克隆代码仓库
2. 创建并激活虚拟环境：
```bash
python -m venv cloudfunction_venv
source cloudfunction_venv/bin/activate  # Unix-like
# 或
.\cloudfunction_venv\Scripts\activate  # Windows
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

### 2. 环境变量配置
1. 复制环境变量模板：
```bash
cp .env.template .env
```

2. 根据实际环境编辑 `.env` 文件，配置必要的参数。

### 3. 服务启动
1. 启动主进程（包含 API 服务器和项目进程）：
```bash
python -m cloudfunction.core.master
```

这将启动：
- API 服务器进程（处理 HTTP 请求）
- 项目进程（执行函数）
- 进程间通信（Queue + Event）

## 配置说明

### 1. 服务器配置
服务器配置通过环境变量进行管理，主要配置项包括：

- 基本配置：
  - `HOST`: 监听地址（默认：0.0.0.0）
  - `PORT`: 监听端口（默认：8080）
  - `SERVER_URL`: 服务器 URL

- SSL 配置：
  - `SSL_ENABLED`: 是否启用 SSL（默认：false）
  - `SSL_KEYFILE`: SSL 密钥文件路径
  - `SSL_CERTFILE`: SSL 证书文件路径
  - `SSL_CA_CERTS`: SSL CA 证书文件路径

- 代理配置：
  - `PROXY_HEADERS`: 是否启用代理头（默认：true）
  - `TRUSTED_HOSTS`: 可信主机列表（默认：*）
  - `FORWARDED_ALLOW_IPS`: 允许的转发 IP（默认：*）

- 并发配置：
  - `MAX_CONCURRENT`: 最大并发数（默认：10）
  - `WORKERS`: 工作进程数（默认：1）
  - `BACKLOG`: 连接队列大小（默认：2048）

- 超时配置：
  - `TIMEOUT_KEEP_ALIVE`: 保持连接超时（默认：5秒）
  - `TIMEOUT_GRACEFUL_SHUTDOWN`: 优雅关闭超时（默认：10秒）
  - `TIMEOUT_NOTIFY`: 通知超时（默认：30秒）

- 清理配置：
  - `CLEANUP_INTERVAL`: 清理间隔（默认：300秒）

- 日志配置：
  - `LOG_LEVEL`: 日志级别（默认：info）
  - `ACCESS_LOG`: 是否启用访问日志（默认：true）

### 2. 日志配置
日志配置通过 `config/logging_config.yaml` 文件进行管理，支持以下配置：

- 日志格式：
  - 标准格式：`%(asctime)s [%(levelname)s] %(name)s: %(message)s`
  - JSON 格式：通过 `JSONFormatter` 格式化

- 日志处理器：
  - 控制台输出：标准格式，输出到 stdout
  - 服务器日志：标准格式，10MB 轮转，保留 5 个备份
  - 错误日志：标准格式，仅记录 ERROR 级别，10MB 轮转，保留 5 个备份
  - 项目日志：每个项目包含三种日志
    - 普通日志：标准格式，10MB 轮转，保留 5 个备份
    - 错误日志：标准格式，仅记录 ERROR 级别，10MB 轮转，保留 5 个备份
    - JSON 日志：JSON 格式，10MB 轮转，保留 5 个备份

- 日志目录结构：
  ```
  logs/
  ├── projects/                # 项目日志目录
  │   ├── project1/           # 项目1的日志
  │   │   ├── app.log        # 普通日志
  │   │   ├── error.log      # 错误日志
  │   │   └── json.log       # JSON格式日志
  │   └── project2/          # 项目2的日志
  ├── server.log             # 服务器日志
  └── error.log             # 全局错误日志
  ```

## 依赖管理

### 1. 系统依赖
系统级依赖在 `requirements.txt` 中定义，包括：
- FastAPI 和 Uvicorn：Web 服务器
- SQLAlchemy：数据库 ORM
- OpenAI：LLM 服务集成
- 其他工具库：python-dotenv, pyyaml, tenacity 等

### 2. 项目依赖
每个项目可以有自己的 `requirements.txt`，位于项目目录下：
```
projects/
└── project_name/
    ├── .env                # 项目环境变量
    └── requirements.txt    # 项目依赖
```

## 目录结构
```
cloudfunction/
├── config/                 # 配置文件
│   ├── logging_config.yaml # 日志配置
│   └── server.py          # 服务器配置
├── core/                  # 核心代码
├── utils/                 # 工具类
├── projects/             # 项目目录
├── venvs/               # 虚拟环境目录
├── logs/               # 日志目录
├── .env               # 环境变量
├── .env.template     # 环境变量模板
└── requirements.txt  # 系统依赖
``` 