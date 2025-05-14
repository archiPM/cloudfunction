import os
from typing import Dict, Any
from dotenv import load_dotenv
from cloudfunction.utils.logger import get_logger

# 设置日志
logger = get_logger(__name__)

# 基础目录
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# 项目目录
PROJECTS_DIR = os.path.join(BASE_DIR, "projects")
VENVS_DIR = os.path.join(BASE_DIR, "venvs")
SYSTEM_VENV_DIR = os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)), "cloudfunction_venv")

# 日志目录
LOG_DIR = os.path.join(BASE_DIR, "logs")

SYSTEM_ENV_PATH = os.path.join(BASE_DIR, ".env")
SYSTEM_REQUIREMENTS_PATH = os.path.join(BASE_DIR, "requirements.txt")

class EnvManager:
    """环境变量管理器"""
    
    def __init__(self):
        """初始化环境变量管理器"""
        self.system_env = {}
        self.project_envs = {}
        self._load_system_env()

    def _load_system_env(self):
        """加载系统级环境变量"""
        system_env_path = os.path.join(BASE_DIR, ".env")
        if os.path.exists(system_env_path):
            load_dotenv(system_env_path)
            # 读取所有系统环境变量
            for key, value in os.environ.items():
                self.system_env[key] = value
            logger.info("Loaded system environment variables")
        else:
            logger.warning(f"System environment file not found at {SYSTEM_ENV_PATH}")

    def get_project_env(self, project_name: str) -> Dict[str, str]:
        """获取项目环境变量
        
        Args:
            project_name: 项目名称
            
        Returns:
            Dict[str, str]: 项目环境变量
        """
        if project_name not in self.project_envs:
            self._load_project_env(project_name)
        return self.project_envs[project_name]

    def _load_project_env(self, project_name: str):
        """加载项目环境变量
        
        Args:
            project_name: 项目名称
        """
        # 首先复制系统环境变量
        project_env = self.system_env.copy()
        
        # 加载项目级环境变量
        project_env_path = os.path.join(PROJECTS_DIR, project_name, ".env")
        if os.path.exists(project_env_path):
            # 临时保存当前环境变量
            current_env = os.environ.copy()
            
            # 加载项目环境变量
            load_dotenv(project_env_path)
            
            # 更新项目环境变量
            for key, value in os.environ.items():
                project_env[key] = value
            
            # 恢复系统环境变量
            os.environ.clear()
            os.environ.update(current_env)
            
            logger.info(f"Loaded environment variables for project {project_name}")
        
        self.project_envs[project_name] = project_env

    def clear_project_env(self, project_name: str):
        """清除项目环境变量
        
        Args:
            project_name: 项目名称
        """
        if project_name in self.project_envs:
            del self.project_envs[project_name]
            logger.info(f"Cleared environment variables for project {project_name}")

    def update_project_env(self, project_name: str, env_vars: Dict[str, str]):
        """更新项目环境变量
        
        Args:
            project_name: 项目名称
            env_vars: 环境变量字典
        """
        if project_name not in self.project_envs:
            self._load_project_env(project_name)
        
        self.project_envs[project_name].update(env_vars)
        logger.info(f"Updated environment variables for project {project_name}")

    @staticmethod
    def get_venv_path(project_name: str) -> str:
        """获取项目的虚拟环境路径
        
        Args:
            project_name: 项目名称
            
        Returns:
            虚拟环境路径
        """
        return os.path.join(VENVS_DIR, project_name)

    @staticmethod
    def get_system_venv_path() -> str:
        """获取系统级虚拟环境路径
        
        Returns:
            系统级虚拟环境路径
        """
        return SYSTEM_VENV_DIR

    @staticmethod
    def get_venv_python(project_name: str) -> str:
        """获取项目的虚拟环境 Python 解释器路径
        
        Args:
            project_name: 项目名称
            
        Returns:
            Python 解释器路径
        """
        venv_path = EnvManager.get_venv_path(project_name)
        if os.name == "nt":  # Windows
            return os.path.join(venv_path, "Scripts", "python.exe")
        else:  # Unix-like
            return os.path.join(venv_path, "bin", "python")

    @staticmethod
    def get_system_venv_python() -> str:
        """获取系统级虚拟环境 Python 解释器路径
        
        Returns:
            系统级 Python 解释器路径
        """
        venv_path = EnvManager.get_system_venv_path()
        if os.name == "nt":  # Windows
            return os.path.join(venv_path, "Scripts", "python.exe")
        else:  # Unix-like
            return os.path.join(venv_path, "bin", "python")

    @staticmethod
    def get_venv_pip(project_name: str) -> str:
        """获取项目的虚拟环境 pip 路径
        
        Args:
            project_name: 项目名称
            
        Returns:
            pip 路径
        """
        venv_path = EnvManager.get_venv_path(project_name)
        if os.name == "nt":  # Windows
            return os.path.join(venv_path, "Scripts", "pip.exe")
        else:  # Unix-like
            return os.path.join(venv_path, "bin", "pip")

    @staticmethod
    def get_system_venv_pip() -> str:
        """获取系统级虚拟环境 pip 路径
        
        Returns:
            系统级 pip 路径
        """
        venv_path = EnvManager.get_system_venv_path()
        if os.name == "nt":  # Windows
            return os.path.join(venv_path, "Scripts", "pip.exe")
        else:  # Unix-like
            return os.path.join(venv_path, "bin", "pip")

    @staticmethod
    def get_project_requirements_path(project_name: str) -> str:
        """获取项目的依赖文件路径
        
        Args:
            project_name: 项目名称
            
        Returns:
            依赖文件路径
        """
        return os.path.join(PROJECTS_DIR, project_name, "requirements.txt")

    @staticmethod
    def get_system_requirements_path() -> str:
        """获取系统级依赖文件路径
        
        Returns:
            系统级依赖文件路径
        """
        return SYSTEM_REQUIREMENTS_PATH 