"""
核心功能模块
"""

# 不直接导入其他模块，避免循环导入

def get_registry_class():
    """获取注册表类"""
    from .registry import FunctionRegistry
    return FunctionRegistry

def get_executor_class():
    """获取执行器类"""
    from .executor import FunctionExecutor
    return FunctionExecutor

def get_env_manager_class():
    """获取环境管理器类"""
    from .env import EnvManager
    return EnvManager

def get_state_class():
    """获取状态管理器类"""
    from .state import ServerState
    return ServerState

def get_project_process_class():
    """获取项目进程类"""
    from .project import ProjectProcess
    return ProjectProcess

def get_project_manager_class():
    """获取项目管理器类"""
    from .project import ProjectManager
    return ProjectManager

def get_api_server_class():
    """获取API服务器类"""
    from .server import APIServer
    return APIServer

def get_master_class():
    """获取主进程管理器类"""
    from .master import Master
    return Master

def get_master():
    """获取主进程实例"""
    from .state import ServerState
    return ServerState.get_master()

__all__ = [
    # 基础组件
    'FunctionRegistry',
    'FunctionExecutor',
    'EnvManager',
    'ServerState',
    
    # 项目管理
    'ProjectProcess',
    'ProjectManager',
    
    # API服务
    'APIServer',
    'Master',
] 