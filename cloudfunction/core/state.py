"""
服务器状态管理模块
"""

import os
from multiprocessing import Manager, Lock
from cloudfunction.core.registry import FunctionRegistry
from cloudfunction.core.executor import FunctionExecutor

class ServerState:
    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.manager = Manager()
                cls._instance.registry = FunctionRegistry(projects_dir="cloudfunction/projects")
                # 初始化时不需要project_name,后续会动态创建
                cls._instance.executor = None
                cls._instance.main_process_id = os.getpid()
        return cls._instance

    def get_executor(self, project_name: str) -> FunctionExecutor:
        """获取项目执行器
        
        Args:
            project_name: 项目名称
            
        Returns:
            FunctionExecutor: 函数执行器实例
        """
        if self.executor is None or self.executor.project_name != project_name:
            self.executor = FunctionExecutor(project_name, self.registry)
        return self.executor

    def get_registry(self) -> FunctionRegistry:
        """获取注册表实例
        
        Returns:
            FunctionRegistry: 注册表实例
        """
        return self.registry 