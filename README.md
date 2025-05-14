# Cloud Function 服务

## 项目简介
Cloud Function 是一个轻量级、高性能的云函数服务框架，支持多项目部署、函数热部署、异步执行、并发控制、环境变量管理、依赖管理、日志系统、LLM 服务集成等功能。适用于需要快速部署、灵活扩展、高并发的场景，如数据处理、AI 推理、自动化任务等。

## 快速上手
1. 配置环境变量
   ```bash
   cp cloudfunction/.env.example cloudfunction/.env
   vim cloudfunction/.env
   ```

2. 构建环境
   ```bash
   # 方法一：使用构建脚本
   chmod +x build.sh
   ./build.sh

   # 方法二：手动构建
   python -m venv cloudfunction_venv
   source cloudfunction_venv/bin/activate
   pip install -r cloudfunction/requirements.txt
   ```

3. 启动服务
   ```bash
   # 方法一：使用启动脚本
   chmod +x entrypoint.sh
   ./entrypoint.sh

   # 方法二：手动启动
   export PYTHONPATH=/path/to/project
   python -m cloudfunction.core.master
   ```

## 核心功能特性
- 支持多项目部署
- 支持函数热部署
- 支持异步函数执行
- 支持并发控制（最大并发数可配置）
- 支持环境变量管理
- 支持依赖管理
- 完善的日志系统
- 支持多种 LLM 服务集成
- 灵活的配置管理
- 支持并发处理
- 支持数据库操作

## 目录结构
```
project/                           # 项目根目录
├── cloudfunction_venv/           # 系统级虚拟环境
├── entrypoint.sh                 # 服务入口脚本
├── build.sh                      # 构建脚本
└── cloudfunction/                # 服务目录
    ├── core/                     # 核心功能
    ├── projects/                 # 项目目录
    ├── venvs/                    # 项目虚拟环境目录
    ├── utils/                    # 工具类
    ├── config/                   # 配置文件目录
    ├── docs/                     # 文档目录
    └── logs/                     # 日志目录
```

## 详细文档
- [架构说明](docs/architecture.md)：系统架构、进程结构、环境管理等
- [API 文档](docs/api.md)：接口说明、请求/响应格式等
- [开发指南](docs/development.md)：函数开发、数据库操作、LLM 集成等
- [部署指南](docs/deployment.md)：项目部署、配置管理、日志管理等

