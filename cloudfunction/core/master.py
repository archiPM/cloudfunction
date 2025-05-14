import asyncio
import logging
import os
from multiprocessing import Process, Queue, Event
from typing import Dict, Any

# 基础配置
from cloudfunction.config.server import HOST, PORT
from cloudfunction.utils.logger import get_logger

# 核心组件
from .state import ServerState
from .project import ProjectManager, ProjectProcess
from .server import APIServer

# 设置日志
logger = get_logger(__name__)

class Master:
    """主进程管理器"""
    
    def __init__(self):
        """初始化主进程管理器"""
        self._init_components()
        
    def _init_components(self):
        """初始化组件"""
        self.state = ServerState()
        self.project_manager = ProjectManager()
        self.api_server = None
        self.project_processes: Dict[str, Process] = {}
        self.project_queues: Dict[str, Queue] = {}
        self.project_events: Dict[str, Event] = {}

    def _start_project_process(self, project_name: str):
        """启动项目进程"""
        if project_name in self.project_processes:
            logger.warning(f"Project {project_name} is already running")
            return

        # 创建进程间通信队列和事件
        queue = Queue()
        event = Event()
        self.project_queues[project_name] = queue
        self.project_events[project_name] = event

        # 创建并启动项目进程
        process = Process(
            target=self._run_project_process,
            args=(project_name, queue, event)
        )
        process.start()
        self.project_processes[project_name] = process
        logger.info(f"Started project process for {project_name}")

    def _run_project_process(self, project_name: str, queue: Queue, event: Event):
        """运行项目进程"""
        try:
            # 创建项目实例
            project = ProjectProcess(project_name)
            
            # 设置事件，表示进程已准备好
            event.set()
            
            # 处理消息循环
            while True:
                if not queue.empty():
                    message = queue.get()
                    if message == "stop":
                        break
                    elif isinstance(message, dict):
                        if message.get("type") == "execute":
                            function_name = message.get("function_name")
                            payload = message.get("payload")
                            try:
                                result = asyncio.run(project.execute_function(function_name, payload))
                                queue.put({"status": "success", "result": result})
                            except Exception as e:
                                queue.put({"status": "error", "error": str(e)})
            
        except Exception as e:
            logger.error(f"Error in project process {project_name}: {e}")
            event.set()  # 确保事件被设置，即使发生错误
            queue.put({"status": "error", "error": str(e)})

    def _stop_project_process(self, project_name: str):
        """停止项目进程"""
        if project_name not in self.project_processes:
            logger.warning(f"Project {project_name} is not running")
            return

        # 发送停止消息
        self.project_queues[project_name].put("stop")
        
        # 等待进程结束
        self.project_processes[project_name].join()
        
        # 清理资源
        del self.project_processes[project_name]
        del self.project_queues[project_name]
        del self.project_events[project_name]
        
        logger.info(f"Stopped project process for {project_name}")

    async def start(self):
        """启动主进程"""
        logger.info("Starting master process")
        
        # 启动API服务器
        self.api_server = APIServer(master=self)
        self.api_process = Process(
            target=self.api_server.run,
            args=(HOST, PORT)
        )
        self.api_process.start()
        logger.info(f"API server started on {HOST}:{PORT}")
        
        # 自动启动所有项目
        projects_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "projects")
        if os.path.exists(projects_dir):
            for project_name in os.listdir(projects_dir):
                if os.path.isdir(os.path.join(projects_dir, project_name)):
                    self._start_project_process(project_name)
                    logger.info(f"Auto-started project {project_name}")

    async def stop(self):
        """停止主进程"""
        logger.info("Stopping master process")
        
        # 停止所有项目进程
        for project_name in list(self.project_processes.keys()):
            self._stop_project_process(project_name)
        
        # 停止API服务器
        if self.api_process:
            self.api_process.terminate()
            self.api_process.join()
        
        logger.info("Master process stopped")

    async def execute_function(self, project_name: str, function_name: str, payload: Dict = None) -> Any:
        """执行项目函数"""
        if project_name not in self.project_processes:
            raise ValueError(f"Project {project_name} is not running")
        
        # 等待项目进程准备好
        self.project_events[project_name].wait()
        
        # 发送执行消息
        self.project_queues[project_name].put({
            "type": "execute",
            "function_name": function_name,
            "payload": payload
        })
        
        # 等待结果
        result = self.project_queues[project_name].get()
        if result["status"] == "error":
            raise RuntimeError(result["error"])
        
        return result["result"]

async def main():
    master = Master()
    try:
        await master.start()
        # 保持主进程运行
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await master.stop()

if __name__ == "__main__":
    asyncio.run(main()) 