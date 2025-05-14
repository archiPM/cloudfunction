import os
import shutil
import yaml
from typing import List, Dict
import importlib.util
import subprocess
from dotenv import load_dotenv
import venv
import sys
from threading import Lock
from cloudfunction.utils.logger import get_logger
from cloudfunction.core.env import VENVS_DIR

# 设置日志
logger = get_logger(__name__)

class FunctionRegistry:
    def __init__(self, projects_dir):
        self.registry = {}
        self.projects_dir = projects_dir
        self.projects = {}  # 初始化 projects 字典
        self.venvs_dir = VENVS_DIR
        self.venv_lock = Lock()
        self._init_projects()  # 初始化项目列表
        self.scan_all_projects()

    def scan_all_projects(self):
        for project_name in os.listdir(self.projects_dir):
            project_path = os.path.join(self.projects_dir, project_name)
            if os.path.isdir(project_path):
                self.register_project_functions(project_name, project_path)

    def register_project_functions(self, project_name, project_path):
        for file in os.listdir(project_path):
            if file.endswith('.py'):
                func_name = file[:-3]
                file_path = os.path.join(project_path, file)
                self.registry[(project_name, func_name)] = {
                    "file_path": file_path,
                    "entry": "main"  # 默认入口名，可扩展
                }

    def get_function(self, project_name, function_name):
        return self.registry.get((project_name, function_name))

    def _init_projects(self):
        """初始化项目列表"""
        for project_name in os.listdir(self.projects_dir):
            project_path = os.path.join(self.projects_dir, project_name)
            if os.path.isdir(project_path):
                self.projects[project_name] = {
                    "path": project_path,
                    "functions": {},
                    "env_loaded": False
                }
                self._load_project_functions(project_name)

    def _load_project_functions(self, project_name: str):
        """加载项目中的函数"""
        project_path = self.projects[project_name]["path"]
        for file_name in os.listdir(project_path):
            if file_name.endswith('.py') and not file_name.startswith('test_'):
                func_name = os.path.splitext(file_name)[0]
                func_path = os.path.join(project_path, file_name)
                description = self._load_function_description(func_path)
                self.projects[project_name]["functions"][func_name] = {
                    "path": func_path,
                    "status": "deployed",
                    "description": description
                }
                logger.info(f"Loaded function {func_name} from project {project_name}")

    def _load_function_description(self, func_path: str) -> Dict:
        """加载函数的描述信息"""
        try:
            spec = importlib.util.spec_from_file_location("temp_module", func_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return getattr(module, "FUNCTION_DESCRIPTION", {
                "name": os.path.basename(func_path),
                "description": "No description provided"
            })
        except Exception as e:
            logger.warning(f"Error loading function description from {func_path}: {e}")
            return {
                "name": os.path.basename(func_path),
                "description": "Error loading description"
            }

    def _load_project_env(self, project_name: str):
        """加载项目的环境变量"""
        if project_name not in self.projects or self.projects[project_name]["env_loaded"]:
            return

        project_path = self.projects[project_name]["path"]
        env_path = os.path.join(project_path, ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path)
            self.projects[project_name]["env_loaded"] = True
            logger.info(f"Loaded environment variables for project {project_name}")

    def _get_venv_path(self, project_name: str) -> str:
        """获取项目的虚拟环境路径"""
        return os.path.join(self.venvs_dir, project_name)

    def _get_venv_python(self, project_name: str) -> str:
        """获取项目的虚拟环境 Python 解释器路径"""
        venv_path = self._get_venv_path(project_name)
        if sys.platform == "win32":
            return os.path.join(venv_path, "Scripts", "python.exe")
        else:
            return os.path.join(venv_path, "bin", "python")

    def _get_venv_pip(self, project_name: str) -> str:
        """获取项目的虚拟环境 pip 路径"""
        venv_path = self._get_venv_path(project_name)
        if sys.platform == "win32":
            return os.path.join(venv_path, "Scripts", "pip.exe")
        else:
            return os.path.join(venv_path, "bin", "pip")

    def _create_venv(self, project_name: str) -> bool:
        """创建项目的虚拟环境"""
        try:
            with self.venv_lock:
                venv_path = self._get_venv_path(project_name)
                if os.path.exists(venv_path):
                    logger.info(f"Virtual environment already exists for project {project_name}")
                    return True
                
                logger.info(f"Creating virtual environment for project {project_name}")
                venv.create(venv_path, with_pip=True)
                return True
        except Exception as e:
            logger.error(f"Error creating virtual environment for project {project_name}: {e}")
            return False

    def _install_requirements(self, project_name: str) -> bool:
        """安装项目的依赖"""
        try:
            with self.venv_lock:
                requirements_path = os.path.join(self.projects_dir, project_name, "requirements.txt")
                if not os.path.exists(requirements_path):
                    logger.info(f"No requirements.txt found for project {project_name}")
                    return True
                
                pip_path = self._get_venv_pip(project_name)
                logger.info(f"Installing requirements for project {project_name}")
                subprocess.run([pip_path, "install", "-r", requirements_path], check=True)
                return True
        except Exception as e:
            logger.error(f"Error installing requirements for project {project_name}: {e}")
            return False

    async def deploy_project(self, project_name: str) -> bool:
        """部署或更新整个项目"""
        try:
            # 创建或更新虚拟环境
            self._create_venv(project_name)
            
            # 动态加载项目
            await self.load_project(project_name)
            
            # 安装项目依赖
            self._install_requirements(project_name)

            # 重新加载所有函数
            for func_name in list(self.projects[project_name]["functions"].keys()):
                await self.deploy_function(project_name, func_name)

            logger.info(f"Project {project_name} deployed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error deploying project {project_name}: {e}", exc_info=True)
            raise

    async def deploy_function(self, project_name: str, function_name: str) -> bool:
        """部署或更新函数"""
        if project_name not in self.projects:
            raise ValueError(f"Project {project_name} does not exist")

        project_path = self.projects[project_name]["path"]
        func_path = os.path.join(project_path, f"{function_name}.py")
        
        if not os.path.exists(func_path):
            raise ValueError(f"Function {function_name}.py does not exist in project {project_name}")

        # 验证函数文件
        try:
            spec = importlib.util.spec_from_file_location("temp_module", func_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if not hasattr(module, "main"):
                raise ValueError(f"No main function found in {function_name}.py")
        except Exception as e:
            raise ValueError(f"Error validating function {function_name}: {e}")

        # 更新注册表
        description = self._load_function_description(func_path)
        self.projects[project_name]["functions"][function_name] = {
            "path": func_path,
            "status": "deployed",
            "description": description
        }

        logger.info(f"Function {function_name} in project {project_name} deployed successfully")
        return True

    def exists(self, project_name: str, function_name: str) -> bool:
        """检查函数是否存在"""
        return (project_name in self.projects and 
                function_name in self.projects[project_name]["functions"])

    def get_function_path(self, project_name: str, function_name: str) -> str:
        """获取函数的路径"""
        if not self.exists(project_name, function_name):
            raise ValueError(f"Function {function_name} not found in project {project_name}")
        return self.projects[project_name]["functions"][function_name]["path"]

    def list_projects(self) -> List[Dict]:
        """列出所有项目"""
        return [
            {
                "name": name,
                "path": info["path"],
                "function_count": len(info["functions"])
            }
            for name, info in self.projects.items()
        ]

    def list_project_functions(self, project_name: str) -> List[Dict]:
        """列出项目中的所有函数"""
        if project_name not in self.projects:
            raise ValueError(f"Project {project_name} does not exist")
        
        return [
            {
                "name": name,
                "status": info["status"],
                "description": info["description"]
            }
            for name, info in self.projects[project_name]["functions"].items()
        ]

    async def delete_project(self, project_name: str) -> bool:
        """删除整个项目"""
        if project_name not in self.projects:
            raise ValueError(f"Project {project_name} does not exist")
            
        project_path = self.projects[project_name]["path"]
        venv_path = self._get_venv_path(project_name)
        
        try:
            # 删除项目目录
            shutil.rmtree(project_path)
            # 删除虚拟环境
            if os.path.exists(venv_path):
                shutil.rmtree(venv_path)
            # 从注册表中移除
            del self.projects[project_name]
            logger.info(f"Project {project_name} deleted successfully")
            return True
        except Exception as e:
            logger.error(f"Error deleting project {project_name}: {e}", exc_info=True)
            raise

    async def delete_function(self, project_name: str, function_name: str) -> bool:
        """删除项目中的函数
        
        Args:
            project_name: 项目名称
            function_name: 函数名称
            
        Returns:
            bool: 是否成功删除
            
        Raises:
            ValueError: 项目或函数不存在
        """
        if project_name not in self.projects:
            raise ValueError(f"Project {project_name} does not exist")
            
        if function_name not in self.projects[project_name]["functions"]:
            raise ValueError(f"Function {function_name} does not exist in project {project_name}")
            
        try:
            # 删除函数文件
            func_path = self.projects[project_name]["functions"][function_name]["path"]
            os.remove(func_path)
            # 从注册表中移除
            del self.projects[project_name]["functions"][function_name]
            logger.info(f"Function {function_name} in project {project_name} deleted successfully")
            return True
        except Exception as e:
            logger.error(f"Error deleting function {function_name} in project {project_name}: {e}", exc_info=True)
            raise 