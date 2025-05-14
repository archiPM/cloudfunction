import os
import yaml
import logging.config
import json
from pathlib import Path
from typing import Any, Dict, Optional
import copy
import logging

class JSONFormatter(logging.Formatter):
    """JSON 格式化器"""
    def format(self, record):
        # 创建基础日志记录
        log_record = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'message': record.getMessage(),
        }
        
        # 添加 extra 字段
        if hasattr(record, 'extra'):
            log_record.update(record.extra)
        
        # 添加异常信息
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_record, ensure_ascii=False)

class ProjectLoggerManager:
    """项目日志管理器"""
    
    def __init__(self):
        self.project_loggers = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """加载日志配置"""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'config',
            'logging_config.yaml'
        )
        with open(config_path, 'rt', encoding='utf-8') as f:
            self.config = yaml.safe_load(f.read())
    
    def _create_project_logger(self, project_name: str) -> logging.Logger:
        """为项目创建日志记录器
        
        Args:
            project_name: 项目名称
            
        Returns:
            logging.Logger: 项目日志记录器
            
        Raises:
            OSError: 当无法创建必要的目录或文件时
            ValueError: 当项目名称无效时
        """
        if not project_name or not isinstance(project_name, str):
            raise ValueError("项目名称必须是非空字符串")
            
        # 创建项目日志目录
        base_dir = os.path.dirname(os.path.dirname(__file__))
        project_log_dir = Path(os.path.join(base_dir, 'logs', 'projects', project_name))
        
        try:
            # 创建目录结构
            project_log_dir.mkdir(parents=True, exist_ok=True)
            project_log_dir.chmod(0o755)
        except OSError as e:
            raise OSError(f"无法创建项目日志目录: {str(e)}")
        
        # 复制并修改配置
        project_config = copy.deepcopy(self.config)
        
        # 配置日志处理器
        for handler_name in ['project_log_template', 'project_error_template', 'project_json_template']:
            if handler_name in project_config['handlers']:
                handler = project_config['handlers'][handler_name]
                try:
                    # 设置日志文件路径
                    # 从配置中获取相对路径，并替换项目名称
                    relative_path = handler['filename'].format(project_name=project_name)
                    # 移除开头的 cloudfunction/ 前缀（如果存在）
                    if relative_path.startswith('cloudfunction/'):
                        relative_path = relative_path[len('cloudfunction/'):]
                    # 构建完整路径
                    log_file = os.path.join(base_dir, relative_path)
                    handler['filename'] = log_file
                    
                    # 确保日志文件存在
                    log_path = Path(log_file)
                    if not log_path.exists():
                        log_path.touch()
                    log_path.chmod(0o644)
                    
                except OSError as e:
                    raise OSError(f"无法创建或配置日志文件 {log_file}: {str(e)}")
        
        # 创建项目特定的日志记录器
        logger_name = f'cloudfunction.projects.{project_name}'
        
        # 确保日志记录器配置存在
        if 'loggers' not in project_config:
            project_config['loggers'] = {}
        
        # 使用基础项目日志记录器配置
        project_config['loggers'][logger_name] = project_config['loggers']['cloudfunction.projects']
        
        # 应用配置
        logging.config.dictConfig(project_config)
        
        return logging.getLogger(logger_name)
    
    def get_project_logger(self, project_name: str) -> logging.Logger:
        """获取项目日志记录器
        
        Args:
            project_name: 项目名称
            
        Returns:
            logging.Logger: 项目日志记录器
            
        Raises:
            ValueError: 当项目名称无效时
            OSError: 当无法创建必要的目录或文件时
        """
        if project_name not in self.project_loggers:
            self.project_loggers[project_name] = self._create_project_logger(project_name)
        return self.project_loggers[project_name]

# 创建全局项目日志管理器实例
project_logger_manager = ProjectLoggerManager()

def setup_logging(
    default_path: str = 'config/logging_config.yaml',
    default_level: int = logging.INFO,
    env_key: str = 'LOG_CFG'
) -> None:
    """设置日志配置
    
    Args:
        default_path: 默认配置文件路径
        default_level: 默认日志级别
        env_key: 环境变量键名
    """
    try:
        # 获取基础目录
        base_dir = os.path.dirname(os.path.dirname(__file__))
        
        # 确保日志目录存在并设置权限
        log_dir = Path(os.path.join(base_dir, 'logs'))
        log_dir.mkdir(exist_ok=True)
        log_dir.chmod(0o755)  # 设置目录权限
        
        # 获取配置文件路径
        path = default_path
        value = os.getenv(env_key, None)
        if value:
            path = value

        # 获取配置文件的绝对路径
        config_path = os.path.join(base_dir, path)

        if os.path.exists(config_path):
            with open(config_path, 'rt', encoding='utf-8') as f:
                try:
                    config = yaml.safe_load(f.read())
                    # 确保所有日志文件路径都存在
                    for handler in config.get('handlers', {}).values():
                        if 'filename' in handler:
                            log_file = handler['filename']
                            log_dir = os.path.dirname(log_file)
                            if log_dir:
                                os.makedirs(log_dir, exist_ok=True)
                                Path(log_dir).chmod(0o755)
                    # 应用配置
                    logging.config.dictConfig(config)
                except Exception as e:
                    print(f'日志配置错误: {e}')
                    print('使用默认日志配置')
                    setup_default_logging(default_level)
        else:
            print('配置文件不存在，使用默认日志配置')
            setup_default_logging(default_level)
    except Exception as e:
        print(f'设置日志时发生错误: {e}')
        print('使用默认日志配置')
        setup_default_logging(default_level)

def setup_default_logging(level: int = logging.INFO) -> None:
    """设置默认日志配置
    
    Args:
        level: 日志级别
    """
    # 获取基础目录
    base_dir = os.path.dirname(os.path.dirname(__file__))
    
    # 确保日志目录存在
    log_dir = Path(os.path.join(base_dir, 'logs'))
    log_dir.mkdir(exist_ok=True)
    
    # 设置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # 添加控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    ))
    root_logger.addHandler(console_handler)

def get_logger(name: str) -> logging.Logger:
    """获取logger实例
    
    Args:
        name: logger名称
        
    Returns:
        logging.Logger: logger实例
    """
    return logging.getLogger(name)

def get_project_logger(project_name: str) -> logging.Logger:
    """获取项目日志记录器
    
    Args:
        project_name: 项目名称
        
    Returns:
        logging.Logger: 项目日志记录器
    """
    return project_logger_manager.get_project_logger(project_name) 