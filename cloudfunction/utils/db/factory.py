"""
数据库管理器工厂
"""

from typing import Dict, Optional
from .project_db import ProjectDatabaseManager
import logging

logger = logging.getLogger(__name__)

class DatabaseManagerFactory:
    _instances: Dict[str, ProjectDatabaseManager] = {}
    
    @classmethod
    def get_manager(cls, project_name: str) -> ProjectDatabaseManager:
        """
        获取项目数据库管理器实例
        如果实例不存在，则创建新实例
        """
        if project_name not in cls._instances:
            logger.info(f"创建新的数据库管理器实例: {project_name}")
            cls._instances[project_name] = ProjectDatabaseManager(project_name)
        return cls._instances[project_name]
    
    @classmethod
    def close_all(cls):
        """关闭所有数据库连接"""
        for project_name, manager in cls._instances.items():
            try:
                manager.close()
                logger.info(f"已关闭项目 {project_name} 的数据库连接")
            except Exception as e:
                logger.error(f"关闭项目 {project_name} 的数据库连接时发生错误: {str(e)}")
        cls._instances.clear()
    
    @classmethod
    def get_status(cls) -> Dict[str, Dict]:
        """获取所有数据库连接的状态"""
        status = {}
        for project_name, manager in cls._instances.items():
            try:
                # 获取连接池状态
                pool = manager.engine.pool
                status[project_name] = {
                    'size': pool.size(),
                    'checkedin': pool.checkedin(),
                    'checkedout': pool.checkedout(),
                    'overflow': pool.overflow(),
                    'checkedin_overflow': pool.checkedin_overflow()
                }
            except Exception as e:
                logger.error(f"获取项目 {project_name} 的连接状态时发生错误: {str(e)}")
                status[project_name] = {'error': str(e)}
        return status
    
    @classmethod
    def reset_pool(cls, project_name: Optional[str] = None):
        """重置指定项目或所有项目的连接池"""
        if project_name:
            if project_name in cls._instances:
                try:
                    cls._instances[project_name].engine.dispose()
                    logger.info(f"已重置项目 {project_name} 的连接池")
                except Exception as e:
                    logger.error(f"重置项目 {project_name} 的连接池时发生错误: {str(e)}")
        else:
            for name, manager in cls._instances.items():
                try:
                    manager.engine.dispose()
                    logger.info(f"已重置项目 {name} 的连接池")
                except Exception as e:
                    logger.error(f"重置项目 {name} 的连接池时发生错误: {str(e)}") 