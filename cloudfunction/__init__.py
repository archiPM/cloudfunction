"""
Cloud Function 服务
"""

# 使用工厂函数获取类，避免循环导入
from .core import (
    get_registry_class,
    get_executor_class,
    get_env_manager_class,
    get_project_process_class,
    get_project_manager_class,
    get_api_server_class,
    get_state_class,
    get_master_class,
    get_master
)

# 初始化类引用，确保向后兼容
FunctionRegistry = get_registry_class()
FunctionExecutor = get_executor_class()
EnvManager = get_env_manager_class()
ProjectProcess = get_project_process_class()
ProjectManager = get_project_manager_class()
APIServer = get_api_server_class()
ServerState = get_state_class()
Master = get_master_class()

from .utils import (
    get_logger,
    setup_logging,
    get_project_logger,
    get_db_manager,
    close_all_connections,
    get_connection_status,
    reset_connection_pool,
    get_llm_client
)

__all__ = [
    # 核心组件
    'FunctionRegistry',
    'FunctionExecutor',
    'EnvManager',
    'ProjectProcess',
    'ProjectManager',
    'APIServer',
    'ServerState',
    'Master',
    
    # 工具函数
    'get_logger',
    'setup_logging',
    'get_project_logger',
    'get_db_manager',
    'close_all_connections',
    'get_connection_status',
    'reset_connection_pool',
    'get_llm_client'
] 