"""
数据库管理模块
"""

import logging
from .factory import DatabaseManagerFactory
from .project_db import ProjectDatabaseManager

logger = logging.getLogger(__name__)

def get_db_manager(project_name: str = None):
    """
    获取数据库管理器实例
    
    Args:
        project_name: 项目名称，如果为None则使用默认项目
    """
    logger.info(f"正在获取数据库管理器实例，项目名称: {project_name}")
    try:
        manager = DatabaseManagerFactory.get_manager(project_name)
        logger.info(f"成功获取数据库管理器实例: {project_name}")
        return manager
    except Exception as e:
        logger.error(f"获取数据库管理器实例失败: {str(e)}")
        raise

def close_all_connections():
    """关闭所有数据库连接"""
    logger.info("正在关闭所有数据库连接")
    try:
        DatabaseManagerFactory.close_all()
        logger.info("成功关闭所有数据库连接")
    except Exception as e:
        logger.error(f"关闭数据库连接失败: {str(e)}")
        raise

def get_connection_status():
    """
    获取所有数据库连接的状态
    
    Returns:
        Dict[str, Dict]: 每个项目的连接状态
    """
    logger.info("正在获取数据库连接状态")
    try:
        status = DatabaseManagerFactory.get_status()
        logger.info(f"成功获取数据库连接状态: {status}")
        return status
    except Exception as e:
        logger.error(f"获取数据库连接状态失败: {str(e)}")
        raise

def reset_connection_pool(project_name: str = None):
    """
    重置指定项目或所有项目的连接池
    
    Args:
        project_name: 项目名称，如果为None则重置所有项目的连接池
    """
    logger.info(f"正在重置连接池，项目名称: {project_name}")
    try:
        DatabaseManagerFactory.reset_pool(project_name)
        logger.info(f"成功重置连接池: {project_name}")
    except Exception as e:
        logger.error(f"重置连接池失败: {str(e)}")
        raise

__all__ = [
    'get_db_manager',
    'close_all_connections',
    'get_connection_status',
    'reset_connection_pool'
]

# 记录模块加载信息
logger.info("数据库管理模块已加载") 