import asyncio
import logging
import os
from typing import Dict, Any

# FastAPI组件
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import uvicorn

# 工具和配置
from cloudfunction.utils.logger import get_logger
from cloudfunction.config.server import (
    HOST, PORT, SERVER_URL, MAX_CONCURRENT, 
    CLEANUP_INTERVAL, WORKERS, BACKLOG, 
    TIMEOUT_KEEP_ALIVE, TIMEOUT_GRACEFUL_SHUTDOWN, 
    LOG_LEVEL, ACCESS_LOG
)

# 核心组件
from .state import ServerState
from cloudfunction.core.registry import FunctionRegistry
from cloudfunction.core.env import PROJECTS_DIR

# 设置日志
logger = get_logger(__name__)

class APIServer:
    """API服务器"""
    
    def __init__(self, state: ServerState):
        self.state = state
        self.project_manager = self.state.get_project_manager()
        self.master = self.state.get_master()
        
        # 创建并注册 registry 组件
        registry = FunctionRegistry(projects_dir=PROJECTS_DIR)
        self.state.register_component('registry', registry)
        
        # 创建 FastAPI 应用
        self.app = FastAPI(
            title="Cloud Function API",
            description="Cloud Function API Server",
            version="1.0.0"
        )
        
        # 注册路由
        self._register_routes()
        
        # 创建 uvicorn 配置
        self.config = uvicorn.Config(
            self.app,
            host=HOST,
            port=PORT,
            log_level="info"
        )

    def _register_routes(self):
        """注册路由"""
        # 将state的方法添加到app.state中，供路由使用
        self.app.state.get_executor = self.state.get_executor
        self.app.state.get_registry = self.state.get_registry
        self.app.state.get_master = self.state.get_master
        self.app.state.get_project_manager = self.state.get_project_manager
        self.app.state.get_task_manager = self.state.get_task_manager
        
        # 导入并注册 API 路由
        from .api import router as api_router
        self.app.include_router(api_router)
        
    async def start(self, host: str = HOST, port: int = PORT):
        """启动API服务器"""
        try:
            self.state._log_operation('info', 'api_server', 'start', f'正在启动服务器 {host}:{port}')
            self.state._log_operation('info', 'api_server', 'start', f'服务器配置: workers={WORKERS}, backlog={BACKLOG}')
            
            config = uvicorn.Config(
                self.app,
                host=host,
                port=port,
                workers=1,  # 确保只有一个worker
                backlog=BACKLOG,
                timeout_keep_alive=TIMEOUT_KEEP_ALIVE,
                timeout_graceful_shutdown=TIMEOUT_GRACEFUL_SHUTDOWN,
                log_level=LOG_LEVEL.lower(),
                access_log=ACCESS_LOG
            )
            server = uvicorn.Server(config)
            self.state._log_operation('info', 'api_server', 'start', '服务器配置完成,开始监听请求')
            await server.serve()
            
        except Exception as e:
            self.state._handle_error('api_server', 'start', e)
            raise

    def run(self, host: str = HOST, port: int = PORT):
        """运行API服务器（用于进程启动）"""
        try:
            self.state._log_operation('info', 'api_server', 'run', f'正在启动服务器 {host}:{port}')
            
            config = uvicorn.Config(
                self.app,
                host=host,
                port=port,
                workers=1,  # 确保只有一个worker
                backlog=BACKLOG,
                timeout_keep_alive=TIMEOUT_KEEP_ALIVE,
                timeout_graceful_shutdown=TIMEOUT_GRACEFUL_SHUTDOWN,
                log_level=LOG_LEVEL.lower(),
                access_log=ACCESS_LOG
            )
            server = uvicorn.Server(config)
            self.state._log_operation('info', 'api_server', 'run', '服务器配置完成,开始运行')
            server.run()
            
        except Exception as e:
            self.state._handle_error('api_server', 'run', e)
            raise

