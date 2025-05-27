"""
服务器状态管理模块
"""

import os
from multiprocessing import Manager, Lock, Queue, Event, Process
from typing import Dict, Any, Optional
from cloudfunction.utils.logger import get_logger

# 设置日志
logger = get_logger(__name__)

class ServerState:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            # 初始化管理器
            self._manager = Manager()
            
            # 核心系统组件管理
            # 这些组件是系统基础设施，使用注册机制确保有序初始化和访问
            self._components = {
                'registry': None,      # 函数注册表
                'master': None,        # 主进程管理器
                'project_manager': None,  # 项目管理器
                'api_server': None,    # API服务器
                'task_manager': None,  # 任务管理器（新增）
            }
            
            # 项目执行器管理
            # 执行器是动态创建的，与具体项目绑定，使用普通字典管理
            self._executors = {}
            
            # 进程管理（使用普通字典，因为进程对象不需要跨进程共享）
            self._processes = {}
            
            # 进程间通信对象
            self._shared = {
                'project_queues': {},    # 项目队列
                'project_events': {},    # 项目事件
                'task_queues': {},       # 任务队列（新增）
                'task_events': {},       # 任务事件（新增）
            }
            
            # 进程锁
            self._process_locks = {}
            
            self._initialized = True

    def _log_operation(self, level: str, project_name: str, operation: str, message: str, exc_info: bool = False) -> None:
        """统一的日志记录
        
        Args:
            level: 日志级别 (debug, info, warning, error, critical)
            project_name: 项目名称
            operation: 操作名称
            message: 日志消息
            exc_info: 是否记录异常信息
        """
        log_message = f"[{project_name}] {operation}: {message}"
        getattr(logger, level)(log_message, exc_info=exc_info)

    def _handle_error(self, project_name: str, operation: str, error: Exception, raise_error: bool = True) -> None:
        """统一的错误处理
        
        Args:
            project_name: 项目名称
            operation: 操作名称
            error: 异常对象
            raise_error: 是否抛出异常
        """
        self._log_operation('error', project_name, operation, str(error), exc_info=True)
        if raise_error:
            raise error

    def register_component(self, name: str, component: Any) -> None:
        """注册核心系统组件
        
        核心系统组件是系统基础设施，包括：
        - registry: 函数注册表
        - master: 主进程管理器
        - project_manager: 项目管理器
        - api_server: API服务器
        
        Args:
            name: 组件名称，必须是预定义的组件类型之一
            component: 组件实例
        """
        if name not in self._components:
            raise ValueError(f"Unknown component type: {name}")
        self._components[name] = component

    def get_component(self, name: str) -> Any:
        """获取组件"""
        logger.debug(f"获取组件: {name}, 当前组件列表: {list(self._components.keys())}")
        component = self._components.get(name)
        logger.debug(f"组件 {name} 的值: {component}")
        return component

    def get_master(self) -> 'Master':
        """获取主进程管理器"""
        return self.get_component('master')

    def get_registry(self) -> 'FunctionRegistry':
        """获取函数注册表"""
        registry = self.get_component('registry')
        logger.debug(f"获取registry组件: {registry}")
        return registry

    def get_project_manager(self) -> 'ProjectManager':
        """获取项目管理器"""
        return self.get_component('project_manager')

    def get_api_server(self) -> 'APIServer':
        """获取API服务器"""
        return self.get_component('api_server')

    def get_task_manager(self) -> 'TaskManager':
        """获取任务管理器"""
        return self.get_component('task_manager')

    def get_shared(self, name: str) -> Any:
        """获取共享对象"""
        if name not in self._shared:
            raise ValueError(f"Unknown shared object: {name}")
        return self._shared[name]

    def create_queue(self, project_name: str) -> Queue:
        """创建项目队列"""
        if project_name not in self._shared['project_queues']:
            self._shared['project_queues'][project_name] = Queue()
        return self._shared['project_queues'][project_name]

    def create_event(self, project_name: str) -> Event:
        """创建项目事件"""
        if project_name not in self._shared['project_events']:
            self._shared['project_events'][project_name] = Event()
        return self._shared['project_events'][project_name]

    def get_queue(self, project_name: str) -> Optional[Queue]:
        """获取项目队列"""
        return self._shared['project_queues'].get(project_name)

    def get_event(self, project_name: str) -> Optional[Event]:
        """获取项目事件"""
        return self._shared['project_events'].get(project_name)

    def create_task_queue(self, task_id: str) -> Queue:
        """创建任务队列"""
        if task_id not in self._shared['task_queues']:
            self._shared['task_queues'][task_id] = Queue()
        return self._shared['task_queues'][task_id]

    def create_task_event(self, task_id: str) -> Event:
        """创建任务事件"""
        if task_id not in self._shared['task_events']:
            self._shared['task_events'][task_id] = Event()
        return self._shared['task_events'][task_id]

    def get_task_queue(self, task_id: str) -> Optional[Queue]:
        """获取任务队列"""
        return self._shared['task_queues'].get(task_id)

    def get_task_event(self, task_id: str) -> Optional[Event]:
        """获取任务事件"""
        return self._shared['task_events'].get(task_id)

    def check_process_status(self, project_name: str) -> bool:
        """检查项目进程状态"""
        if project_name not in self._processes:
            return False
            
        process = self._processes[project_name]
        if not process.is_alive():
            return False
            
        # 检查事件是否已设置
        event = self.get_event(project_name)
        if not event or not event.is_set():
            return False
            
        return True

    def start_project_process(self, project_name: str, target_func, args: tuple = None) -> bool:
        """启动项目进程"""
        try:
            # 检查进程是否已存在
            if project_name in self._processes:
                if self.check_process_status(project_name):
                    self._log_operation('warning', project_name, 'start', '进程已运行')
                    return True
                else:
                    # 如果进程已死，清理资源
                    self._log_operation('warning', project_name, 'start', '进程已死，清理资源')
                    self.cleanup_project(project_name)

            # 创建进程间通信队列和事件
            queue = self.create_queue(project_name)
            event = self.create_event(project_name)

            # 创建并启动项目进程
            process = Process(
                target=target_func,
                args=(project_name, queue, event) + (args or ()),
                daemon=True
            )
            process.start()
            self._processes[project_name] = process
            self._log_operation('info', project_name, 'start', '进程启动成功')
            return True
            
        except Exception as e:
            self._handle_error(project_name, 'start_process', e, raise_error=False)
            return False

    def terminate_process(self, project_name: str) -> bool:
        """终止项目进程"""
        try:
            if project_name not in self._processes:
                self._log_operation('warning', project_name, 'terminate', '进程不存在')
                return True

            # 发送停止消息
            queue = self.get_queue(project_name)
            if queue:
                queue.put("stop")
            
            # 等待进程结束，设置超时
            self._processes[project_name].join(timeout=10)
            
            # 如果进程还在运行，强制终止
            if self._processes[project_name].is_alive():
                self._log_operation('warning', project_name, 'terminate', '进程未正常停止，强制终止')
                self._processes[project_name].terminate()
                self._processes[project_name].join(timeout=5)
            
            self._log_operation('info', project_name, 'terminate', '进程终止成功')
            return True
            
        except Exception as e:
            self._handle_error(project_name, 'terminate_process', e, raise_error=False)
            return False

    def cleanup_project(self, project_name: str) -> None:
        """清理项目资源"""
        try:
            # 终止进程
            self.terminate_process(project_name)
            
            # 清理队列和事件
            if project_name in self._shared['project_queues']:
                del self._shared['project_queues'][project_name]
            if project_name in self._shared['project_events']:
                del self._shared['project_events'][project_name]
                
            # 清理进程记录
            if project_name in self._processes:
                del self._processes[project_name]
                
            # 清理执行器
            if project_name in self._executors:
                del self._executors[project_name]
            
            self._log_operation('info', project_name, 'cleanup', '资源清理完成')
            
        except Exception as e:
            self._handle_error(project_name, 'cleanup_project', e)

    def get_executor(self, project_name: str) -> Any:
        """获取项目执行器
        
        执行器是动态创建的，与具体项目绑定。
        每个项目都有自己的执行器实例，用于处理该项目的函数调用。
        
        Args:
            project_name: 项目名称
            
        Returns:
            Any: 项目执行器实例
        """
        if project_name not in self._executors:
            # 延迟导入，避免循环依赖
            from .executor import FunctionExecutor
            # 获取函数注册表
            logger.debug(f"正在获取registry组件...")
            registry = self.get_registry()
            logger.debug(f"获取到的registry: {registry}")
            if not registry:
                raise RuntimeError("Registry not initialized")
            # 创建执行器，传入所需参数
            executor = FunctionExecutor(project_name, registry, self)
            self._executors[project_name] = executor
        return self._executors[project_name]

    def cleanup_task_resources(self, task_id: str) -> None:
        """清理任务资源"""
        if task_id in self._shared['task_queues']:
            del self._shared['task_queues'][task_id]
        if task_id in self._shared['task_events']:
            del self._shared['task_events'][task_id]

    def cleanup_resources(self):
        """清理状态管理器资源
        
        按顺序清理所有资源：
        1. 清理所有项目进程
        2. 清理共享资源（队列和事件）
        3. 清理执行器
        4. 清理组件
        5. 清理管理器
        """
        try:
            # 1. 清理所有进程
            for project_name in list(self._processes.keys()):
                try:
                    self.terminate_process(project_name)
                    self.cleanup_project(project_name)
                except Exception as e:
                    logger.error(f"清理项目 {project_name} 时出错: {str(e)}", exc_info=True)
            
            # 2. 清理共享资源
            try:
                for queue in self._shared['project_queues'].values():
                    queue.close()
                for event in self._shared['project_events'].values():
                    event.clear()
                self._shared['project_queues'].clear()
                self._shared['project_events'].clear()
            except Exception as e:
                logger.error(f"清理共享资源时出错: {str(e)}", exc_info=True)
            
            # 3. 清理执行器
            try:
                for executor in self._executors.values():
                    if hasattr(executor, 'executor'):
                        executor.executor.shutdown(wait=True)
                self._executors.clear()
            except Exception as e:
                logger.error(f"清理执行器时出错: {str(e)}", exc_info=True)
            
            # 4. 清理组件
            try:
                for name, component in self._components.items():
                    if component and hasattr(component, 'stop'):
                        try:
                            component.stop()
                        except Exception as e:
                            logger.error(f"停止组件 {name} 时出错: {str(e)}", exc_info=True)
                    self._components[name] = None
            except Exception as e:
                logger.error(f"清理组件时出错: {str(e)}", exc_info=True)
            
            # 5. 清理管理器
            try:
                if hasattr(self, '_manager') and self._manager is not None:
                    self._manager.shutdown()
                    self._manager = None
            except Exception as e:
                logger.error(f"清理管理器时出错: {str(e)}", exc_info=True)
            
            logger.info("状态管理器资源清理完成")
            
        except Exception as e:
            logger.error(f"清理状态管理器资源时出错: {str(e)}", exc_info=True)
            raise 