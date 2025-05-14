import os
import asyncio
import importlib.util
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional
import json
import sys
import venv
import subprocess
from .env import EnvManager, PROJECTS_DIR, VENVS_DIR
from cloudfunction.utils.logger import get_logger

# 设置日志
logger = get_logger(__name__)

class ProjectProcess:
    """项目处理类"""
    
    def __init__(self, name):
        """初始化项目处理类
        
        Args:
            name: 项目名称
        """
        self.name = name
        self.env_manager = EnvManager()
        self.env = self.env_manager.get_project_env(name)
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.function_registry = {}
        
        # 设置项目目录
        self.project_dir = os.path.join(PROJECTS_DIR, name)
        self.venv_dir = os.path.join(VENVS_DIR, name)
        
        # 检查项目目录是否存在
        if not os.path.exists(self.project_dir):
            raise FileNotFoundError(f"Project directory {self.project_dir} does not exist")
        
        # 添加项目目录到Python路径
        if self.project_dir not in sys.path:
            sys.path.append(self.project_dir)
        
        # 创建虚拟环境
        self._create_venv()
        
        # 安装依赖
        self._install_requirements()
        
        self._load_functions()

    def _get_venv_python(self) -> str:
        """获取项目的虚拟环境 Python 解释器路径"""
        if sys.platform == "win32":
            return os.path.join(self.venv_dir, "Scripts", "python.exe")
        else:
            return os.path.join(self.venv_dir, "bin", "python")

    def _get_venv_pip(self) -> str:
        """获取项目的虚拟环境 pip 路径"""
        if sys.platform == "win32":
            return os.path.join(self.venv_dir, "Scripts", "pip.exe")
        else:
            return os.path.join(self.venv_dir, "bin", "pip")

    def _create_venv(self):
        """创建项目虚拟环境"""
        try:
            # 创建项目级虚拟环境（如果不存在）
            if not os.path.exists(self.venv_dir):
                logger.info(f"Creating project virtual environment for project {self.name}")
                venv.create(self.venv_dir, with_pip=True)
                logger.info(f"Project virtual environment created at {self.venv_dir}")
            else:
                logger.info(f"Project virtual environment already exists at {self.venv_dir}")
            
        except Exception as e:
            logger.error(f"Error creating virtual environment: {str(e)}")
            raise

    def _install_requirements(self) -> bool:
        """安装项目依赖"""
        try:
            # 获取系统级依赖
            system_requirements_path = self.env_manager.get_system_requirements_path()
            system_requirements = []
            if os.path.exists(system_requirements_path):
                with open(system_requirements_path, "r") as f:
                    system_requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            
            # 获取项目级依赖
            project_requirements_path = self.env_manager.get_project_requirements_path(self.name)
            project_requirements = []
            if os.path.exists(project_requirements_path):
                with open(project_requirements_path, "r") as f:
                    project_requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            
            # 合并依赖，项目级覆盖系统级
            all_requirements = []
            project_packages = set()
            
            # 先添加项目级依赖
            for req in project_requirements:
                package = req.split("==")[0].split(">=")[0].split("<=")[0]
                project_packages.add(package)
                all_requirements.append(req)
            
            # 添加系统级依赖（排除被项目级覆盖的包）
            for req in system_requirements:
                package = req.split("==")[0].split(">=")[0].split("<=")[0]
                if package not in project_packages:
                    all_requirements.append(req)
            
            if not all_requirements:
                logger.info(f"No requirements to install for project {self.name}")
                return True
            
            # 创建临时requirements文件
            temp_requirements_path = os.path.join(self.project_dir, "_temp_requirements.txt")
            with open(temp_requirements_path, "w") as f:
                f.write("\n".join(all_requirements))
            
            try:
                # 使用项目级虚拟环境的pip安装依赖
                pip_cmd = [self.env_manager.get_venv_pip(self.name), "install", "-r", temp_requirements_path]
                
                result = subprocess.run(
                    pip_cmd,
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if result.returncode != 0:
                    logger.error(f"Error installing dependencies: {result.stderr}")
                    return False
                
                # 记录安装的依赖版本
                freeze_result = subprocess.run(
                    [self.env_manager.get_venv_pip(self.name), "freeze"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                # 保存依赖版本到文件
                with open(os.path.join(self.project_dir, "requirements.lock"), "w") as f:
                    f.write(freeze_result.stdout)
                
                logger.info(f"Dependencies installed successfully for project {self.name}")
                return True
                
            finally:
                # 删除临时文件
                if os.path.exists(temp_requirements_path):
                    os.remove(temp_requirements_path)
            
        except Exception as e:
            logger.error(f"Error installing requirements: {str(e)}")
            return False

    def _load_functions(self):
        """加载项目函数"""
        for file in os.listdir(self.project_dir):
            if file.endswith('.py') and not file.startswith('_'):
                function_name = file[:-3]
                try:
                    # 使用完整的模块路径
                    module_path = f"projects.{self.name}.{function_name}"
                    try:
                        module = importlib.import_module(module_path)
                    except ImportError:
                        # 如果导入失败，尝试使用文件路径加载
                        spec = importlib.util.spec_from_file_location(
                            f"{self.name}.{function_name}",
                            os.path.join(self.project_dir, file)
                        )
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                    
                    if hasattr(module, "main"):
                        # 检查是否有函数描述
                        if hasattr(module, "FUNCTION_DESCRIPTION"):
                            logger.info(f"Loaded function {function_name} with description from project {self.name}")
                        else:
                            logger.warning(f"Function {function_name} in project {self.name} has no description")
                        
                        self.function_registry[function_name] = module.main
                        logger.info(f"Loaded function {function_name} from project {self.name}")
                    else:
                        logger.warning(f"Function {function_name} in project {self.name} has no main function")
                except Exception as e:
                    logger.error(f"Error loading function {function_name}: {str(e)}")

    async def execute_function(self, function_name: str, payload: Dict[str, Any]) -> Any:
        """执行函数"""
        if function_name not in self.function_registry:
            raise ValueError(f"Function {function_name} not found in project {self.name}")
        
        try:
            # 在线程池中执行函数
            result = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                self.function_registry[function_name],
                payload
            )
            return result
        except Exception as e:
            logger.error(f"Error executing function {function_name}: {str(e)}")
            raise

class ProjectManager:
    def __init__(self):
        self.projects = {}
        self.env_manager = EnvManager()

    async def start_project(self, project_name: str) -> bool:
        """启动项目"""
        if project_name in self.projects:
            logger.warning(f"Project {project_name} is already running")
            return False
        
        try:
            project = ProjectProcess(project_name)
            self.projects[project_name] = project
            logger.info(f"Started project {project_name}")
            return True
        except Exception as e:
            logger.error(f"Error starting project {project_name}: {str(e)}")
            return False

    async def stop_project(self, project_name: str) -> bool:
        """停止项目"""
        if project_name not in self.projects:
            logger.warning(f"Project {project_name} is not running")
            return False
        
        try:
            del self.projects[project_name]
            self.env_manager.clear_project_env(project_name)
            logger.info(f"Stopped project {project_name}")
            return True
        except Exception as e:
            logger.error(f"Error stopping project {project_name}: {str(e)}")
            return False

    async def execute_function(self, project_name: str, function_name: str, payload: Dict[str, Any]) -> Any:
        """执行项目函数"""
        if project_name not in self.projects:
            raise ValueError(f"Project {project_name} is not running")
        
        return await self.projects[project_name].execute_function(function_name, payload)

    def get_project(self, project_name: str) -> Optional[ProjectProcess]:
        """获取项目实例"""
        return self.projects.get(project_name)

    def list_projects(self) -> list:
        """列出所有运行中的项目"""
        return list(self.projects.keys()) 