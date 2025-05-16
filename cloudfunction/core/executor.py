import os
import importlib.util
import sys
import asyncio
import time
from typing import Any, Dict, Optional
import logging
from dotenv import load_dotenv
from datetime import datetime
import json
from multiprocessing import Lock, Manager
from cloudfunction.core.env import EnvManager, VENVS_DIR
from concurrent.futures import ThreadPoolExecutor
from cloudfunction.utils.logger import get_logger
import shutil
import subprocess

logger = get_logger(__name__)

class FunctionExecutor:
    """函数执行器"""
    
    def __init__(self, project_name: str, registry):
        """初始化函数执行器
        
        Args:
            project_name: 项目名称
            registry: FunctionRegistry 实例
        """
        logger.info(f"初始化函数执行器: project={project_name}")
        self.project_name = project_name
        self.env_manager = EnvManager()
        self.env_manager.get_project_env(project_name)
        logger.debug(f"已加载项目环境变量: {self.env_manager.get_project_env(project_name)}")
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.running_functions = {}
        self.semaphore = asyncio.Semaphore(10)  # 限制并发执行数量
        self.registry = registry
        
        # 确保项目虚拟环境存在
        self._ensure_venv()
        
        # 启动清理任务
        asyncio.create_task(self._cleanup_task())

    def _get_venv_path(self) -> str:
        """获取虚拟环境路径"""
        return os.path.join(VENVS_DIR, self.project_name)

    def _get_venv_python(self) -> str:
        """获取项目虚拟环境的Python解释器路径"""
        if os.name == 'nt':  # Windows
            return os.path.join(self._get_venv_path(), "Scripts", "python.exe")
        return os.path.join(self._get_venv_path(), "bin", "python")

    def _get_venv_pip(self) -> str:
        """获取项目虚拟环境的pip路径"""
        if os.name == 'nt':  # Windows
            return os.path.join(self._get_venv_path(), "Scripts", "pip.exe")
        return os.path.join(self._get_venv_path(), "bin", "pip")

    def _ensure_venv(self):
        """确保项目虚拟环境存在"""
        venv_path = self._get_venv_path()
        if not os.path.exists(venv_path):
            logger.info(f"为项目 {self.project_name} 创建虚拟环境")
            import venv
            venv.create(venv_path, with_pip=True)

    async def _cleanup_task(self):
        """定期清理过期的函数记录"""
        while True:
            try:
                current_time = time.time()
                expired = []
                for func_id, info in self.running_functions.items():
                    if current_time - info['start_time'] > 3600:  # 1小时后清理
                        expired.append(func_id)
                
                for func_id in expired:
                    del self.running_functions[func_id]
                
                await asyncio.sleep(300)  # 每5分钟清理一次
            except Exception as e:
                logger.error(f"Error in cleanup task: {str(e)}")
                await asyncio.sleep(60)

    async def execute(self, function_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """执行函数
        
        Args:
            function_name: 函数名称
            payload: 函数参数
            
        Returns:
            函数执行结果
        """
        func_id = f"{self.project_name}:{function_name}:{time.time()}"
        
        try:
            # 使用信号量限制并发
            async with self.semaphore:
                # 记录开始执行
                self.running_functions[func_id] = {
                    'start_time': time.time(),
                    'status': 'running',
                    'function': function_name
                }
                
                # 加载环境变量
                env = self.env_manager.get_project_env(self.project_name)
                
                # 通过注册表查找函数文件路径和入口名
                func_info = self.registry.get_function(self.project_name, function_name)
                if not func_info:
                    raise Exception(f"Function {function_name} not found in project {self.project_name}")
                file_path = func_info["file_path"]
                entry = func_info.get("entry", "main")
                
                # 动态加载模块
                spec = importlib.util.spec_from_file_location(function_name, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                handler = getattr(module, entry, None)
                if handler is None:
                    raise Exception(f"No entry function '{entry}' found in {file_path}")
                
                # 支持 async 和 sync
                if asyncio.iscoroutinefunction(handler):
                    # 直接执行异步函数
                    result = await handler(payload)
                else:
                    # 同步函数在线程池中执行
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(self.executor, handler, payload)
                
                # 更新执行状态
                self.running_functions[func_id]['status'] = 'completed'
                self.running_functions[func_id]['end_time'] = time.time()
                
                return {
                    "status": "success",
                    "result": result
                }
                
        except Exception as e:
            # 更新执行状态
            self.running_functions[func_id]['status'] = 'failed'
            self.running_functions[func_id]['end_time'] = time.time()
            self.running_functions[func_id]['error'] = str(e)
            
            logger.error(f"Error executing function {function_name}: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }

    def get_function_status(self, func_id: str) -> Optional[Dict[str, Any]]:
        """获取函数执行状态
        
        Args:
            func_id: 函数ID
            
        Returns:
            函数执行状态信息
        """
        return self.running_functions.get(func_id)

    def list_running_functions(self) -> Dict[str, Dict[str, Any]]:
        """获取所有正在运行的函数
        
        Returns:
            正在运行的函数列表
        """
        return self.running_functions 

    async def deploy_function(
        self,
        function_name: str,
        code: bytes,
        requirements: Optional[bytes] = None,
        env_vars: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        logger.info(f"开始部署函数: {function_name}")
        try:
            # 验证代码内容
            if not code or len(code.strip()) == 0:
                raise ValueError("函数代码不能为空")
            
            # 验证代码格式
            try:
                code_str = code.decode('utf-8')
                compile(code_str, '<string>', 'exec')
            except (UnicodeDecodeError, SyntaxError) as e:
                raise ValueError(f"函数代码格式无效: {str(e)}")
            
            # 验证main函数
            if "async def main" not in code_str and "def main" not in code_str:
                raise ValueError("函数代码必须包含main函数")
            
            # 备份现有文件
            code_path = f"cloudfunction/projects/{self.project_name}/{function_name}.py"
            backup_path = f"{code_path}.bak"
            if os.path.exists(code_path):
                logger.debug(f"备份现有文件: {code_path} -> {backup_path}")
                shutil.copy2(code_path, backup_path)
            
            # 保存代码文件
            logger.debug(f"保存代码文件: {code_path}")
            with open(code_path, "wb") as f:
                f.write(code)
            
            # 处理项目依赖
            project_req_path = f"cloudfunction/projects/{self.project_name}/requirements.txt"
            if requirements:
                # 如果提供了新的依赖，更新项目级别的requirements.txt
                logger.debug(f"更新项目依赖文件: {project_req_path}")
                with open(project_req_path, "wb") as f:
                    f.write(requirements)
            
            # 安装项目依赖
            if os.path.exists(project_req_path):
                try:
                    pip_path = self._get_venv_pip()
                    logger.debug(f"安装项目依赖: {project_req_path}")
                    subprocess.run([pip_path, "install", "-r", project_req_path], check=True)
                except Exception as e:
                    logger.error(f"安装项目依赖失败: {str(e)}")
                    # 如果安装失败，恢复备份
                    if os.path.exists(backup_path):
                        logger.debug(f"恢复备份文件: {backup_path} -> {code_path}")
                        shutil.copy2(backup_path, code_path)
                    raise ValueError(f"安装项目依赖失败: {str(e)}")
            
            # 验证新文件
            try:
                # 重新加载模块
                import importlib
                import sys
                module_name = f"cloudfunction.projects.{self.project_name}.{function_name}"
                if module_name in sys.modules:
                    del sys.modules[module_name]
                
                # 将项目目录添加到 Python 路径
                project_dir = os.path.dirname(os.path.dirname(code_path))
                if project_dir not in sys.path:
                    sys.path.insert(0, project_dir)
                
                # 使用虚拟环境的Python解释器
                python_path = self._get_venv_python()
                spec = importlib.util.spec_from_file_location(module_name, code_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if not hasattr(module, "main"):
                    raise ValueError(f"函数代码中未找到main函数")
            except Exception as e:
                # 如果验证失败，恢复备份
                if os.path.exists(backup_path):
                    logger.debug(f"恢复备份文件: {backup_path} -> {code_path}")
                    shutil.copy2(backup_path, code_path)
                raise ValueError(f"函数代码验证失败: {str(e)}")
            
            # 删除备份文件
            if os.path.exists(backup_path):
                os.remove(backup_path)
            
            # 更新环境变量
            if env_vars:
                logger.debug(f"更新函数环境变量: {env_vars}")
                self.env_manager.update_project_env(self.project_name, env_vars)
            
            logger.info(f"函数部署完成: {function_name}")
            return {
                "status": "success",
                "message": f"Function {function_name} deployed successfully",
                "function_name": function_name
            }
            
        except Exception as e:
            logger.error(f"函数部署失败: {str(e)}")
            raise
    
    async def invoke_function(self, function_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"开始调用函数: {function_name}")
        try:
            # 导入函数模块
            module_path = f"cloudfunction.projects.{self.project_name}.{function_name}"
            logger.debug(f"导入函数模块: {module_path}")
            
            import importlib
            module = importlib.import_module(module_path)
            handler = getattr(module, "main")
            
            # 执行函数
            logger.debug(f"执行函数,输入数据: {data}")
            if asyncio.iscoroutinefunction(handler):
                result = await handler(data)
            else:
                result = handler(data)
            logger.info(f"函数执行完成: {function_name}")
            
            return {
                "status": "success",
                "result": result
            }
            
        except Exception as e:
            logger.error(f"函数调用失败: {str(e)}")
            raise
    
    async def list_functions(self) -> Dict[str, Any]:
        logger.info("获取函数列表")
        try:
            import os
            functions_dir = f"cloudfunction/projects/{self.project_name}"
            logger.debug(f"扫描函数目录: {functions_dir}")
            
            functions = []
            for file in os.listdir(functions_dir):
                if file.endswith(".py") and not file.endswith("_requirements.txt"):
                    function_name = file[:-3]
                    functions.append(function_name)
            
            logger.info(f"找到 {len(functions)} 个函数")
            return {
                "status": "success",
                "functions": functions
            }
            
        except Exception as e:
            logger.error(f"获取函数列表失败: {str(e)}")
            raise
    
    async def delete_function(self, function_name: str) -> Dict[str, Any]:
        logger.info(f"开始删除函数: {function_name}")
        try:
            import os
            
            # 删除代码文件
            code_path = f"cloudfunction/projects/{self.project_name}/{function_name}.py"
            logger.debug(f"删除代码文件: {code_path}")
            if os.path.exists(code_path):
                os.remove(code_path)
            
            # 删除依赖文件
            req_path = f"cloudfunction/projects/{self.project_name}/{function_name}_requirements.txt"
            logger.debug(f"删除依赖文件: {req_path}")
            if os.path.exists(req_path):
                os.remove(req_path)
            
            logger.info(f"函数删除完成: {function_name}")
            return {
                "status": "success",
                "message": f"Function {function_name} deleted successfully"
            }
            
        except Exception as e:
            logger.error(f"函数删除失败: {str(e)}")
            raise

    async def deploy_project(self, project_name: str) -> Dict[str, Any]:
        """部署整个项目
        
        Args:
            project_name: 项目名称
            
        Returns:
            部署结果
        """
        logger.info(f"收到项目部署请求，将转发到registry: {project_name}")
        try:
            # 调用registry的方法
            result = await self.registry.deploy_project(project_name)
            
            return {
                "status": "success",
                "message": f"Project {project_name} deployed successfully",
                "details": result
            }
        except Exception as e:
            logger.error(f"项目部署失败: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            } 