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

# 设置日志
logger = get_logger(__name__)

class APIServer:
    """API服务器"""
    
    def __init__(self, master=None):
        """初始化API服务器
        
        Args:
            master: 主进程管理器实例，可选
        """
        self._init_components(master)
        self._setup_middleware()
        self._setup_routes()
        
    def _init_components(self, master):
        """初始化组件"""
        logger.info("初始化API服务器组件")
        self.app = FastAPI(title="Cloud Function API")
        self.master = master
        self.state = master.state if master else ServerState()
        self.executors = {}  # 项目名称 -> FunctionExecutor
        logger.info("API服务器组件初始化完成")

    def _setup_middleware(self):
        """设置中间件"""
        logger.info("设置中间件")
        
        # 添加CORS中间件
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # 添加可信主机中间件
        self.app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
        
        # 添加请求日志中间件
        @self.app.middleware("http")
        async def log_requests(request: Request, call_next):
            logger.info(f"收到请求: {request.method} {request.url.path}")
            logger.debug(f"请求头: {dict(request.headers)}")
            
            try:
                response = await call_next(request)
                logger.info(f"请求处理完成: {request.method} {request.url.path} - 状态码: {response.status_code}")
                return response
            except Exception as e:
                logger.error(f"请求处理异常: {request.method} {request.url.path} - 错误: {str(e)}")
                raise
                
        logger.info("中间件设置完成")

    def _setup_routes(self):
        """设置路由"""
        # 将state的方法添加到app.state中，供路由使用
        self.app.state.get_executor = self.state.get_executor
        self.app.state.get_registry = self.state.get_registry
        
        # 健康检查
        @self.app.get("/health")
        async def health_check():
            return {"status": "healthy"}
        
        # 导入并注册 API 路由
        from .api import router as api_router
        self.app.include_router(api_router)
        
    async def start(self, host: str = HOST, port: int = PORT):
        """启动API服务器"""
        logger.info(f"正在启动API服务器 {host}:{port}")
        logger.info(f"服务器配置: workers={WORKERS}, backlog={BACKLOG}")
        
        config = uvicorn.Config(
            self.app,
            host=host,
            port=port,
            workers=WORKERS,
            backlog=BACKLOG,
            timeout_keep_alive=TIMEOUT_KEEP_ALIVE,
            timeout_graceful_shutdown=TIMEOUT_GRACEFUL_SHUTDOWN,
            log_level=LOG_LEVEL.lower(),  # 转换为小写
            access_log=ACCESS_LOG
        )
        server = uvicorn.Server(config)
        logger.info("服务器配置完成,开始监听请求")
        await server.serve()

    def run(self, host: str = HOST, port: int = PORT):
        """运行API服务器（用于进程启动）"""
        asyncio.run(self.start(host, port))

