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
import multiprocessing
import psutil
import concurrent.futures

# 设置日志
logger = get_logger(__name__)

class ProjectProcess:
    """项目处理类"""
    
    def __init__(self, name: str, queue: multiprocessing.Queue, event: multiprocessing.Event):
        """初始化项目处理类
        
        Args:
            name: 项目名称
            queue: 进程间通信队列
            event: 进程间事件
        """
        self.name = name
        self.queue = queue
        self.event = event
        self.function_registry = {}
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=10,
            thread_name_prefix=f"cloudfunction-{name}"
        )
        self.loop = None  # 事件循环
        
        # 初始化环境管理器
        self.env_manager = EnvManager()
        
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

    def run(self):
        """运行项目进程"""
        try:
            # 设置进程名称
            process = psutil.Process()
            process.name(f"cloudfunction-{self.name}")
            
            # 创建并设置事件循环
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            # 加载函数
            self._load_functions()
            
            # 标记进程已准备好
            self.event.set()
            
            # 运行事件循环
            self.loop.run_until_complete(self._run_async())
            
        except Exception as e:
            logger.error(f"项目进程异常退出: {self.name} - {str(e)}")
            # 通知主进程
            self.queue.put({
                "type": "error",
                "error": str(e)
            })
            
    async def _run_async(self):
        """异步运行项目"""
        while True:
            try:
                # 异步等待消息
                message = await self._get_message()
                
                if message["type"] == "execute":
                    # 创建协程任务
                    task = asyncio.create_task(
                        self.execute_function_async(
                            message["function_name"],
                            message["payload"]
                        )
                    )
                    # 等待任务完成
                    result = await task
                    await self._put_message(result)
                    
            except Exception as e:
                logger.error(f"处理消息失败: {str(e)}")
                await self._put_message({
                    "type": "error",
                    "error": str(e)
                })
                
    async def _get_message(self):
        """异步获取消息"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.queue.get)
        
    async def _put_message(self, message):
        """异步发送消息"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.queue.put, message)
        
    async def execute_function_async(self, function_name: str, payload: Dict[str, Any]) -> Any:
        """异步执行函数"""
        if function_name not in self.function_registry:
            raise ValueError(f"Function {function_name} not found in project {self.name}")
        
        try:
            # 获取函数处理器
            handler = self.function_registry[function_name]
            
            # 检查是否是异步函数
            if asyncio.iscoroutinefunction(handler):
                # 直接执行异步函数
                result = await handler(payload)
            else:
                # 同步函数在线程池中执行
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    self.executor,
                    handler,
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
        
        return await self.projects[project_name].execute_function_async(function_name, payload)

    def get_project(self, project_name: str) -> Optional[ProjectProcess]:
        """获取项目实例"""
        return self.projects.get(project_name)

    def list_projects(self) -> list:
        """列出所有运行中的项目"""
        return list(self.projects.keys()) 