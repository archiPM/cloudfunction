"""
核心功能模块
"""

# 基础组件
from .registry import FunctionRegistry
from .executor import FunctionExecutor
from .env import EnvManager
from .state import ServerState

# 项目管理
from .project import ProjectProcess, ProjectManager

# API服务
from .server import APIServer

from .master import Master

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

def get_master():
    """延迟导入Master类"""
    from .master import Master
    return Master 