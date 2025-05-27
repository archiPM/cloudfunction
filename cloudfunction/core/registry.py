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
import ast
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
        """使用 AST 解析函数描述信息"""
        try:
            with open(func_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read())
            
            # 查找模块级别的变量赋值
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == 'FUNCTION_DESCRIPTION':
                            if isinstance(node.value, ast.Dict):
                                # 将 AST Dict 节点转换为实际的字典
                                description = {}
                                for key, value in zip(node.value.keys, node.value.values):
                                    if isinstance(key, ast.Constant):
                                        key_name = key.value
                                        if isinstance(value, ast.Constant):
                                            description[key_name] = value.value
                                return description
            
            # 如果没有找到 FUNCTION_DESCRIPTION，返回默认值
            return {
                "name": os.path.basename(func_path),
                "description": "No description provided"
            }
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
                project_dir = os.path.join(self.projects_dir, project_name)
                requirements_txt = os.path.join(project_dir, "requirements.txt")
                requirements_lock = os.path.join(project_dir, "requirements.lock")
                
                pip_path = self._get_venv_pip(project_name)
                
                # 检查文件是否存在
                txt_exists = os.path.exists(requirements_txt)
                lock_exists = os.path.exists(requirements_lock)
                
                # 如果两个文件都不存在，直接返回
                if not txt_exists and not lock_exists:
                    logger.info(f"未找到依赖文件：项目 {project_name} 没有 requirements.txt 或 requirements.lock")
                    return True
                
                # 检查txt文件是否比lock文件更新
                if txt_exists and lock_exists:
                    txt_mtime = os.path.getmtime(requirements_txt)
                    lock_mtime = os.path.getmtime(requirements_lock)
                    
                    if txt_mtime > lock_mtime:
                        logger.info(f"检测到 requirements.txt 更新，重新生成 lock 文件")
                        try:
                            # 检查是否安装了pip-compile
                            pip_compile_path = os.path.join(os.path.dirname(pip_path), "pip-compile")
                            if not os.path.exists(pip_compile_path):
                                logger.info("安装 pip-tools 用于生成 lock 文件")
                                subprocess.run([pip_path, "install", "pip-tools"], check=True)
                                pip_compile_path = os.path.join(os.path.dirname(pip_path), "pip-compile")
                            
                            # 重新生成lock文件
                            subprocess.run([pip_compile_path, requirements_txt, "--output-file", requirements_lock], check=True)
                            logger.info(f"成功更新 requirements.lock 文件")
                        except Exception as e:
                            logger.error(f"更新 lock 文件失败: {e}")
                            # 更新失败不影响后续安装
                
                # 安装依赖
                if lock_exists:
                    logger.info(f"从 requirements.lock 安装依赖: {project_name}")
                    subprocess.run([pip_path, "install", "-r", requirements_lock], check=True)
                elif txt_exists:
                    logger.info(f"从 requirements.txt 安装依赖: {project_name}")
                    subprocess.run([pip_path, "install", "-r", requirements_txt], check=True)
                
                return True
        except Exception as e:
            logger.error(f"安装项目 {project_name} 依赖时出错: {e}")
            return False

    async def deploy_project(self, project_name: str) -> bool:
        """部署或更新整个项目"""
        try:
            # 创建或更新虚拟环境
            self._create_venv(project_name)
            # 动态加载项目
            self._load_project_functions(project_name)
            # 安装项目依赖
            logger.info(f"安装项目依赖...")
            install_success = self._install_requirements(project_name)
            if not install_success:
                logger.warning(f"安装依赖过程中出现警告，但将继续部署")
            # 重新加载所有函数
            for func_name in list(self.projects[project_name]["functions"].keys()):
                await self.deploy_function(project_name, func_name)
            logger.info(f"Project {project_name} deployed successfully")
            # 部署后重启项目进程，确保新代码生效
            try:
                from cloudfunction.core.state import ServerState
                state = ServerState()
                state.terminate_process(project_name)
                state.start_project_process(project_name, None)
                logger.info(f"项目进程已重启: {project_name}")
            except Exception as e:
                logger.error(f"重启项目进程失败: {project_name} - {str(e)}")
            return True
        except Exception as e:
            logger.error(f"Error deploying project {project_name}: {e}", exc_info=True)
            raise

    async def deploy_function(self, project_name: str, function_name: str) -> bool:
        """部署或更新函数"""
        if project_name not in self.projects:
            logger.error(f"项目未找到: {project_name}")
            raise ValueError(f"Project {project_name} does not exist")
        project_path = self.projects[project_name]["path"]
        func_path = os.path.join(project_path, f"{function_name}.py")
        logger.info(f"部署函数: {project_name}/{function_name}，文件路径: {func_path}")
        if not os.path.exists(func_path):
            logger.error(f"函数文件不存在: {func_path}")
            raise ValueError(f"Function {function_name}.py does not exist in project {project_name}")
        # 首先安装项目依赖
        if not self._install_requirements(project_name):
            logger.error(f"项目 {project_name} 依赖安装失败")
            raise RuntimeError(f"Failed to install dependencies for project {project_name}")
        # 更新函数注册信息
        self.registry[(project_name, function_name)] = {
            "file_path": func_path,
            "entry": "main"  # 默认入口名，可扩展
        }
        # 更新项目函数信息
        description = self._load_function_description(func_path)
        self.projects[project_name]["functions"][function_name] = {
            "path": func_path,
            "status": "deployed",
            "description": description
        }
        logger.info(f"函数 {function_name} 部署成功")
        # 部署后重启项目进程，确保新代码生效
        try:
            from cloudfunction.core.state import ServerState
            state = ServerState()
            state.terminate_process(project_name)
            state.start_project_process(project_name, None)
            logger.info(f"项目进程已重启: {project_name}")
        except Exception as e:
            logger.error(f"重启项目进程失败: {project_name} - {str(e)}")
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