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
import time
import signal
from multiprocessing import Process, Queue, Event

# 设置日志
logger = get_logger(__name__)

class ProjectProcess:
    """项目处理类"""
    
    def __init__(self, name: str, queue: multiprocessing.Queue, event: multiprocessing.Event):
        """初始化项目进程
        
        Args:
            name: 项目名称
            queue: 进程间通信队列
            event: 进程间通信事件
        """
        self.name = name
        self.queue = queue
        self.event = event
        self.function_registry = {}
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self.initialized = False
        self.env_manager = EnvManager()  # 初始化环境管理器
        
        # 设置项目目录
        self.project_dir = os.path.join(PROJECTS_DIR, name)
        if not os.path.exists(self.project_dir):
            raise ValueError(f"Project directory not found: {self.project_dir}")
            
        # 设置虚拟环境目录
        self.venv_dir = os.path.join(VENVS_DIR, name)
        
        try:
            # 1. 先创建虚拟环境
            self._create_venv()
            
            # 2. 安装依赖
            if not self._install_requirements():
                logger.error(f"项目 {name} 依赖安装失败")
                raise RuntimeError(f"Failed to install dependencies for project {name}")
                
            # 3. 添加虚拟环境路径到sys.path
            if sys.platform == "win32":
                venv_site_packages = os.path.join(self.venv_dir, "Lib", "site-packages")
            else:
                python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
                venv_site_packages = os.path.join(self.venv_dir, "lib", python_version, "site-packages")
            
            if os.path.exists(venv_site_packages):
                if venv_site_packages not in sys.path:
                    sys.path.insert(0, venv_site_packages)
                    logger.info(f"已添加虚拟环境路径到sys.path: {venv_site_packages}")
            else:
                logger.error(f"虚拟环境site-packages路径不存在: {venv_site_packages}")
                raise RuntimeError(f"Virtual environment site-packages not found: {venv_site_packages}")
            
            # 4. 最后加载函数
            self._register_functions()
            self._load_functions()
            
            self.initialized = True
            logger.info(f"项目 {name} 初始化成功")
            
        except Exception as e:
            logger.error(f"项目 {name} 初始化失败: {str(e)}", exc_info=True)
            self.initialized = False
            raise

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
                
                logger.info(f"项目 {self.name} 依赖项: {project_requirements}")
            else:
                logger.warning(f"项目 {self.name} 没有找到依赖文件: {project_requirements_path}")
            
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
            
            logger.info(f"准备安装依赖: {all_requirements}")
            
            # 创建临时requirements文件
            temp_requirements_path = os.path.join(self.project_dir, "_temp_requirements.txt")
            with open(temp_requirements_path, "w") as f:
                f.write("\n".join(all_requirements))
            
            try:
                # 使用项目级虚拟环境的pip安装依赖
                pip_path = self.env_manager.get_venv_pip(self.name)
                logger.info(f"使用pip路径: {pip_path}")
                
                # 先尝试升级pip
                upgrade_result = subprocess.run(
                    [pip_path, "install", "--upgrade", "pip"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                if upgrade_result.returncode != 0:
                    logger.warning(f"Pip升级失败 (忽略): {upgrade_result.stderr}")
                
                # 安装依赖
                pip_cmd = [pip_path, "install", "-r", temp_requirements_path]
                logger.info(f"执行安装命令: {' '.join(pip_cmd)}")
                
                result = subprocess.run(
                    pip_cmd,
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if result.returncode != 0:
                    error_msg = f"依赖安装失败，返回码: {result.returncode}, 错误: {result.stderr}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
                
                # 记录安装的依赖版本
                freeze_result = subprocess.run(
                    [pip_path, "freeze"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                # 保存依赖版本到文件
                with open(os.path.join(self.project_dir, "requirements.lock"), "w") as f:
                    f.write(freeze_result.stdout)
                
                logger.info(f"依赖安装成功: {self.name}")
                return True
                
            finally:
                # 删除临时文件
                if os.path.exists(temp_requirements_path):
                    os.remove(temp_requirements_path)
            
        except Exception as e:
            logger.error(f"依赖安装失败: {str(e)}", exc_info=True)
            # 将布尔返回值改为抛出异常，确保问题不被忽略
            raise RuntimeError(f"依赖安装失败: {str(e)}")

    def _register_functions(self):
        """注册项目函数（不导入）"""
        # 扫描项目目录中的Python文件
        functions_registered = 0
        logger.info(f"扫描项目 {self.name} 中的函数文件...")
        for file in os.listdir(self.project_dir):
            if file.endswith('.py') and not file.startswith('_'):
                function_name = file[:-3]
                logger.info(f"尝试注册函数: {function_name}")
                try:
                    # 读取文件内容
                    file_path = os.path.join(self.project_dir, file)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    # 检查是否有main函数
                    if 'def main(' in content:
                        # 检查是否有函数描述
                        desc = None
                        if 'FUNCTION_DESCRIPTION' in content:
                            try:
                                # 尝试提取描述
                                desc_start = content.find('FUNCTION_DESCRIPTION')
                                desc_end = content.find('\n', desc_start)
                                if desc_end != -1:
                                    desc_line = content[desc_start:desc_end].strip()
                                    desc = desc_line.split('=')[1].strip().strip('"\'')
                            except Exception as e:
                                logger.warning(f"提取函数描述失败: {str(e)}")
                        
                        if desc:
                            logger.info(f"注册函数 {function_name} (描述: {desc})")
                        else:
                            logger.info(f"注册函数 {function_name} (无描述)")
                        
                        # 注册函数信息（不导入）
                        self.function_registry[function_name] = {
                            'file_path': file_path,
                            'module_name': f"{self.name}.{function_name}",
                            'description': desc,
                            'loaded': False,
                            'function': None
                        }
                        functions_registered += 1
                    else:
                        logger.warning(f"函数 {function_name} 没有main入口点")
                except Exception as e:
                    logger.error(f"注册函数 {function_name} 失败: {str(e)}", exc_info=True)
        
        logger.info(f"项目 {self.name} 注册了 {functions_registered} 个函数")

    def _load_functions(self):
        """加载项目函数（导入模块）"""
        # 确保虚拟环境路径在sys.path的最前面
        if sys.platform == "win32":
            venv_site_packages = os.path.join(self.venv_dir, "Lib", "site-packages")
        else:
            python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
            venv_site_packages = os.path.join(self.venv_dir, "lib", python_version, "site-packages")
        
        if os.path.exists(venv_site_packages):
            if venv_site_packages not in sys.path:
                sys.path.insert(0, venv_site_packages)
                logger.info(f"已添加虚拟环境路径到sys.path: {venv_site_packages}")
            else:
                logger.info(f"虚拟环境路径已在sys.path中: {venv_site_packages}")
        else:
            logger.error(f"虚拟环境site-packages路径不存在: {venv_site_packages}")
            
        # 确保cloudfunction目录在Python路径中
        cloudfunction_dir = os.path.dirname(os.path.dirname(os.path.dirname(self.project_dir)))
        if cloudfunction_dir not in sys.path and os.path.exists(cloudfunction_dir):
            sys.path.insert(0, cloudfunction_dir)
            logger.info(f"已添加cloudfunction目录到Python路径: {cloudfunction_dir}")
            
        # 确保项目所在目录在Python路径中
        projects_parent_dir = os.path.dirname(self.project_dir)
        if projects_parent_dir not in sys.path:
            sys.path.insert(0, projects_parent_dir)
            logger.info(f"已添加项目父目录到Python路径: {projects_parent_dir}")
        
        # 导入已注册的函数
        functions_loaded = 0
        logger.info(f"开始导入项目 {self.name} 的函数...")
        for function_name, func_info in self.function_registry.items():
            if not func_info['loaded']:
                try:
                    # 导入模块并获取函数对象
                    module = importlib.import_module(func_info['module_name'])
                    func = getattr(module, 'main')
                    if callable(func):
                        func_info['function'] = func
                        func_info['loaded'] = True
                        functions_loaded += 1
                        logger.info(f"成功导入函数: {function_name}")
                    else:
                        logger.error(f"函数 {function_name} 不是可调用对象")
                except Exception as e:
                    logger.error(f"导入函数 {function_name} 失败: {str(e)}", exc_info=True)
        
        logger.info(f"项目 {self.name} 导入了 {functions_loaded} 个函数")

    def run(self):
        """运行项目进程"""
        try:
            # 设置进程名称
            process = psutil.Process()
            process.name(f"cloudfunction-{self.name}")
            
            # 创建并设置事件循环
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            # 如果初始化失败，提前标记事件
            if not self.initialized:
                logger.warning(f"项目 {self.name} 初始化失败，无法处理函数请求")
                self.event.set()  # 设置事件，表示进程已准备好（虽然失败）
                # 不要立即退出，等待主进程可能的停止命令
                
                # 简单消息循环，只处理停止命令
                while True:
                    if not self.queue.empty():
                        message = self.queue.get()
                        logger.debug(f"收到消息: {message}")
                        if message == "stop":
                            logger.info(f"收到停止信号，正在停止项目 {self.name}")
                            break
                    time.sleep(1)  # 简单轮询，减少CPU使用
                
                return
            
            # 标记进程已准备好
            self.event.set()
            
            # 运行事件循环
            self.loop.run_until_complete(self._run_async())
            
        except Exception as e:
            logger.error(f"项目进程异常退出: {self.name} - {str(e)}", exc_info=True)
            # 确保事件被设置，即使发生错误
            if not self.event.is_set():
                self.event.set()
            # 通知主进程
            self.queue.put({
                "status": "error",
                "type": "process_error",
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
        if not self.initialized:
            raise RuntimeError("Project not initialized")
            
        if function_name not in self.function_registry:
            raise ValueError(f"Function {function_name} not found")
            
        try:
            # 使用线程池执行函数
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                self._execute_function,
                function_name,
                payload
            )
            return result
        except Exception as e:
            logger.error(f"函数执行失败: {function_name} - {str(e)}", exc_info=True)
            raise

    def _execute_function(self, function_name: str, payload: Dict[str, Any]) -> Any:
        """在线程池中执行函数"""
        try:
            # 获取函数信息
            func_info = self.function_registry.get(function_name)
            if not func_info:
                raise ValueError(f"Function {function_name} not found")
            
            # 如果函数未加载，尝试加载
            if not func_info['loaded']:
                try:
                    module = importlib.import_module(func_info['module_name'])
                    func = getattr(module, 'main')
                    if callable(func):
                        func_info['function'] = func
                        func_info['loaded'] = True
                        logger.info(f"成功导入函数: {function_name}")
                    else:
                        raise ValueError(f"Function {function_name} is not callable")
                except Exception as e:
                    logger.error(f"导入函数 {function_name} 失败: {str(e)}", exc_info=True)
                    raise
            
            # 获取函数对象
            func = func_info['function']
            
            # 执行函数
            if asyncio.iscoroutinefunction(func):
                # 如果是异步函数，创建新的事件循环
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(func(payload))
                finally:
                    loop.close()
            else:
                # 如果是同步函数，直接执行
                result = func(payload)
                
            return result
        except Exception as e:
            logger.error(f"函数执行失败: {function_name} - {str(e)}", exc_info=True)
            raise

class ProjectManager:
    """项目管理器"""
    
    def __init__(self, state=None):
        """初始化项目管理器
        
        Args:
            state: 服务器状态对象，可选
        """
        self.state = state
        self.projects = {}
        
    async def start_project(self, project_name: str) -> bool:
        """启动项目
        
        Args:
            project_name: 项目名称
            
        Returns:
            bool: 是否成功启动
        """
        try:
            # 延迟导入，避免循环依赖
            from .master import get_master
            master = get_master()
            if not master:
                raise Exception("无法获取主进程实例")
                
            # 启动项目进程
            master._start_project_process(project_name)
            return True
            
        except Exception as e:
            logger.error(f"启动项目失败: {str(e)}")
            return False
            
    async def stop_project(self, project_name: str) -> bool:
        """停止项目
        
        Args:
            project_name: 项目名称
            
        Returns:
            bool: 是否成功停止
        """
        try:
            # 延迟导入，避免循环依赖
            from .master import get_master
            master = get_master()
            if not master:
                raise Exception("无法获取主进程实例")
                
            # 停止项目进程
            master._stop_project_process(project_name)
            return True
            
        except Exception as e:
            logger.error(f"停止项目失败: {str(e)}")
            return False
            
    async def execute_function(self, project_name: str, function_name: str, payload: Dict[str, Any]) -> Any:
        """执行函数
        
        Args:
            project_name: 项目名称
            function_name: 函数名称
            payload: 函数参数
            
        Returns:
            函数执行结果
        """
        try:
            # 延迟导入，避免循环依赖
            from .master import get_master
            master = get_master()
            if not master:
                raise Exception("无法获取主进程实例")
                
            # 执行函数
            return await master.execute_function(project_name, function_name, payload)
            
        except Exception as e:
            logger.error(f"执行函数失败: {str(e)}")
            raise
            
    def get_project(self, project_name: str) -> Optional[ProjectProcess]:
        """获取项目实例
        
        Args:
            project_name: 项目名称
            
        Returns:
            ProjectProcess: 项目实例，如果不存在返回None
        """
        return self.projects.get(project_name)
        
    def list_projects(self) -> list:
        """获取项目列表
        
        Returns:
            list: 项目列表
        """
        return list(self.projects.keys()) 