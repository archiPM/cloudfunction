import asyncio
import logging
import os
from multiprocessing import Process, Queue, Event
from typing import Dict, Any, Optional
import signal
import sys
import time
from queue import Empty

# 基础配置
from cloudfunction.config.server import HOST, PORT
from cloudfunction.utils.logger import get_logger

# 设置日志
logger = get_logger(__name__)

class Master:
    """主进程管理器"""
    
    def __init__(self, config_file: str = None):
        """初始化主进程管理器"""
        self._init_components()
        self._startup_status = {
            'api_server': False,
            'projects': {},
            'state': False
        }
        
    def _init_components(self):
        """初始化组件"""
        # 延迟导入，避免循环依赖
        from .state import ServerState
        from .project import ProjectManager
        from .task_manager import TaskManager
        
        self.state = ServerState()
        # 将主进程实例注册到状态管理器
        self.state.register_component('master', self)
        self.project_manager = ProjectManager(self.state)
        self.state.register_component('project_manager', self.project_manager)
        
        # 初始化任务管理器
        task_manager = TaskManager(self.state)
        self.state.register_component('task_manager', task_manager)
        
    def _start_project_process(self, project_name: str):
        """启动项目进程"""
        self.state.start_project_process(project_name, self._run_project_process)

    def _run_project_process(self, project_name: str, queue: Queue, event: Event):
        """运行项目进程"""
        try:
            # 设置项目进程日志
            pid = os.getpid()
            logger.info(f"项目进程启动: {project_name} [PID={pid}]")
            
            # 延迟导入，避免循环依赖
            from .project import ProjectProcess
            
            # 创建项目实例
            logger.info(f"正在初始化项目实例: {project_name}")
            project = None
            try:
                project = ProjectProcess(project_name, queue, event)
                logger.info(f"项目实例创建成功: {project_name}")
            except Exception as e:
                logger.error(f"项目实例创建失败: {project_name} - {str(e)}", exc_info=True)
                queue.put({"status": "error", "error": f"Failed to initialize project: {str(e)}"})
                event.set()  # 设置事件，表示进程已准备好(虽然失败)
                return
            
            # 设置事件，表示进程已准备好
            logger.info(f"项目进程准备就绪: {project_name}")
            event.set()
            
            # 创建事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 处理消息循环
            logger.info(f"开始项目消息循环: {project_name}")
            try:
                while True:
                    try:
                        if not queue.empty():
                            message = queue.get()
                            logger.info(f"收到消息: {project_name} - {message}")
                            
                            if message == "stop":
                                logger.info(f"收到停止信号，正在停止项目 {project_name}")
                                # 发送 SIGTERM 信号
                                os.kill(os.getpid(), signal.SIGTERM)
                                break
                            elif isinstance(message, dict):
                                if message.get("type") == "execute":
                                    function_name = message.get("function_name")
                                    payload = message.get("payload")
                                    logger.info(f"开始执行函数: {project_name}/{function_name}, 参数: {payload}")
                                    try:
                                        start_time = time.time()
                                        # 在现有事件循环中执行函数
                                        result = loop.run_until_complete(
                                            project.execute_function_async(function_name, payload)
                                        )
                                        elapsed_time = time.time() - start_time
                                        logger.info(f"函数执行完成: {project_name}/{function_name}, 耗时: {elapsed_time:.2f}秒")
                                        queue.put({"status": "success", "result": result})
                                    except Exception as e:
                                        logger.error(f"函数执行失败: {project_name}/{function_name} - {str(e)}", exc_info=True)
                                        queue.put({"status": "error", "error": str(e)})
                    except Exception as e:
                        logger.error(f"消息处理异常: {project_name} - {str(e)}", exc_info=True)
                        # 继续处理下一条消息
            finally:
                # 清理事件循环
                try:
                    loop.stop()
                    loop.close()
                except Exception as e:
                    logger.error(f"清理事件循环失败: {str(e)}", exc_info=True)
            
        except Exception as e:
            logger.error(f"项目进程异常: {project_name} - {str(e)}", exc_info=True)
            event.set()  # 确保事件被设置，即使发生错误
            queue.put({"status": "error", "error": str(e)})

    def _stop_project_process(self, project_name: str):
        """停止项目进程"""
        if not self.state.terminate_process(project_name):
            self.state._log_operation('warning', project_name, 'stop', '进程未正常停止')
        self.state.cleanup_project(project_name)
        self.state._log_operation('info', project_name, 'stop', '进程停止完成')

    async def _wait_for_component(self, component_name: str, check_func, timeout: int = 30):
        """等待组件就绪
        
        Args:
            component_name: 组件名称
            check_func: 检查函数
            timeout: 超时时间（秒）
            
        Returns:
            bool: 组件是否就绪
            
        Raises:
            TimeoutError: 等待超时
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            if check_func():
                logger.info(f"组件 {component_name} 已就绪")
                return True
            await asyncio.sleep(1)
        logger.error(f"等待组件 {component_name} 就绪超时")
        return False

    async def _check_api_server(self) -> bool:
        """检查API服务器状态"""
        try:
            api_server = self.state.get_api_server()
            if not api_server:
                return False
                
            # 检查服务器是否正在运行
            return True
        except Exception as e:
            logger.error(f"检查API服务器状态失败: {str(e)}", exc_info=True)
            return False

    async def _check_project_process(self, project_name: str) -> bool:
        """检查项目进程是否就绪"""
        try:
            if project_name not in self.state._processes:
                return False
            if not self.state._processes[project_name].is_alive():
                return False
                
            # 检查事件是否已设置
            event = self.state.get_event(project_name)
            if not event or not event.is_set():
                return False
                
            return True
        except Exception as e:
            logger.error(f"检查项目进程状态失败: {str(e)}", exc_info=True)
            return False

    async def start(self):
        """启动主进程"""
        logger.info("开始启动主进程")
        
        try:
            # 1. 初始化基础组件
            logger.info("1. 初始化基础组件")
            self._startup_status['state'] = True
            
            # 2. 启动 API 服务器
            logger.info("2. 启动 API 服务器")
            from .server import APIServer
            from .env import PROJECTS_DIR
            
            api_server = self.state.get_api_server()
            if not api_server:
                api_server = APIServer(self.state)
                self.state.register_component('api_server', api_server)
                asyncio.create_task(api_server.start())
                await self._wait_for_component('API服务器', self._check_api_server)
                self._startup_status['api_server'] = True
                logger.info(f"API 服务器已启动并监听 {HOST}:{PORT}")
            
            # 3. 启动项目进程并等待就绪
            logger.info("3. 启动项目进程")
            failed_projects = []
            for project_name in os.listdir(PROJECTS_DIR):
                project_path = os.path.join(PROJECTS_DIR, project_name)
                if os.path.isdir(project_path) and not project_name.startswith("__"):
                    logger.info(f"正在启动项目: {project_name}")
                    try:
                        self._start_project_process(project_name)
                        # 等待项目进程就绪（事件 set）
                        ready = await self._wait_for_component(
                            f"项目 {project_name}",
                            lambda: self.state.check_process_status(project_name),
                            timeout=30
                        )
                        if ready:
                            self._startup_status['projects'][project_name] = True
                            logger.info(f"项目 {project_name} 已启动并就绪")
                        else:
                            self._startup_status['projects'][project_name] = False
                            failed_projects.append(project_name)
                            logger.warning(f"项目 {project_name} 启动超时，未就绪")
                    except Exception as e:
                        logger.error(f"启动项目 {project_name} 失败: {str(e)}", exc_info=True)
                        self._startup_status['projects'][project_name] = False
                        failed_projects.append(project_name)
            # 启动检查结束后统一输出 warning
            if failed_projects:
                logger.warning(f"以下项目启动失败: {', '.join(failed_projects)}")
            
            logger.info("主进程启动完成")
            
        except Exception as e:
            logger.error(f"主进程启动失败: {str(e)}", exc_info=True)
            await self.stop()  # 清理资源
            raise

    async def stop(self):
        """停止主进程"""
        logger.info("正在停止主进程...")
        
        try:
            # 1. 先停止所有项目进程
            for project_name in list(self.state._processes.keys()):
                try:
                    self._stop_project_process(project_name)
                except Exception as e:
                    logger.error(f"停止项目 {project_name} 时出错: {str(e)}", exc_info=True)
            
            # 2. 停止API服务器
            try:
                api_server = self.state.get_api_server()
                if api_server:
                    api_server.stop()
                    self.state.unregister_component('api_server')
            except Exception as e:
                logger.error(f"停止API服务器时出错: {str(e)}", exc_info=True)
            
            # 3. 清理状态管理器资源
            try:
                self.state.cleanup_resources()
            except Exception as e:
                logger.error(f"清理状态管理器资源时出错: {str(e)}", exc_info=True)
            
            logger.info("主进程停止完成")
            
        except Exception as e:
            logger.error(f"停止主进程时出错: {str(e)}", exc_info=True)
            raise

    async def execute_function(self, project_name: str, function_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """执行函数
        
        Args:
            project_name: 项目名称
            function_name: 函数名称
            payload: 函数参数
            
        Returns:
            Dict[str, Any]: 函数执行结果
        """
        try:
            # 检查项目进程是否存在
            if project_name not in self.state._processes:
                self.state._log_operation('warning', project_name, 'execute', '项目未运行，尝试启动')
                try:
                    self._start_project_process(project_name)
                    self.state._log_operation('info', project_name, 'execute', '项目启动成功')
                except Exception as e:
                    self.state._handle_error(project_name, 'start_project', e)
                    raise ValueError(f"Project {project_name} is not running and could not be started")
                    
            # 检查进程是否活跃
            if not self.state.check_process_status(project_name):
                self.state._log_operation('warning', project_name, 'execute', '进程已退出，尝试重启')
                try:
                    # 清理旧进程
                    self.state.cleanup_project(project_name)
                    # 重新启动
                    self._start_project_process(project_name)
                    self.state._log_operation('info', project_name, 'execute', '项目重启成功')
                except Exception as e:
                    self.state._handle_error(project_name, 'restart_project', e)
                    raise ValueError(f"Project {project_name} process died and could not be restarted")
            
            # 等待项目进程准备好（无超时限制）
            self.state._log_operation('info', project_name, 'execute', '等待进程就绪')
            while not self.state.check_process_status(project_name):
                await asyncio.sleep(1)
            
            # 获取项目队列
            queue = self.state.get_queue(project_name)
            if not queue:
                raise ValueError(f"Queue not found for project {project_name}")
            
            # 发送执行消息
            message = {
                "type": "execute",
                "function_name": function_name,
                "payload": payload
            }
            logger.info(f"发送执行消息到项目 {project_name}: {message}")
            queue.put(message)
            
            # 等待结果（无超时限制）
            logger.info(f"等待项目 {project_name} 返回执行结果...")
            start_time = time.time()
            while True:
                try:
                    result = queue.get(timeout=1)  # 1秒超时，用于检查任务是否被取消
                    elapsed_time = time.time() - start_time
                    logger.info(f"收到项目 {project_name} 的响应，耗时: {elapsed_time:.2f}秒")
                    
                    if isinstance(result, dict):
                        if result.get("status") == "success":
                            logger.info(f"函数 {function_name} 执行成功")
                            return result.get("result")
                        elif result.get("status") == "error":
                            error_msg = result.get("error")
                            logger.error(f"函数 {function_name} 执行失败: {error_msg}")
                            raise Exception(error_msg)
                    else:
                        logger.warning(f"收到未知格式的响应: {result}")
                except Empty:
                    # 检查进程是否还活着
                    if not self.state.check_process_status(project_name):
                        raise Exception(f"Project {project_name} process died during execution")
                    continue
            
        except Exception as e:
            self.state._handle_error(project_name, 'execute_function', e)
            raise

async def main():
    master = Master()
    try:
        await master.start()
        # 保持主进程运行
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在停止服务...")
        await master.stop()
    except Exception as e:
        logger.error(f"服务异常退出: {str(e)}", exc_info=True)
        await master.stop()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 