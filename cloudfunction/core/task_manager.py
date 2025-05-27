import asyncio
import logging
import os
import time
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
import json
from cloudfunction.utils.logger import get_logger
from concurrent.futures import ThreadPoolExecutor
import threading

logger = get_logger(__name__)

class TaskManager:
    """任务管理器，用于处理长时间运行的云函数任务"""
    
    def __init__(self, state=None):
        """初始化任务管理器
        
        Args:
            state: ServerState 实例，可选
        """
        self.state = state
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.task_lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.task_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tasks")
        os.makedirs(self.task_dir, exist_ok=True)
        
    def _generate_task_id(self, project_name: str, function_name: str) -> str:
        """生成任务ID，使用项目名和函数名作为前缀
        
        Args:
            project_name: 项目名称
            function_name: 函数名称
            
        Returns:
            任务ID
        """
        return f"{project_name}_{function_name}_{uuid.uuid4()}"
        
    def _save_task_state(self, task_id: str, task_info: Dict[str, Any]):
        """保存任务状态到文件
        
        Args:
            task_id: 任务ID
            task_info: 任务信息
        """
        task_file = os.path.join(self.task_dir, f"{task_id}.json")
        with open(task_file, 'w', encoding='utf-8') as f:
            json.dump(task_info, f, ensure_ascii=False, indent=2)
            
    def _load_task_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        """从文件加载任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务信息，如果不存在则返回 None
        """
        task_file = os.path.join(self.task_dir, f"{task_id}.json")
        if os.path.exists(task_file):
            with open(task_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
        
    def _get_running_task(self, project_name: str, function_name: str) -> Optional[Dict[str, Any]]:
        """获取正在运行的任务
        
        Args:
            project_name: 项目名称
            function_name: 函数名称
            
        Returns:
            正在运行的任务信息，如果没有则返回 None
        """
        prefix = f"{project_name}_{function_name}"
        for task_id, task_info in self.tasks.items():
            if task_id.startswith(prefix) and task_info["status"] in ["created", "running"]:
                return task_info
        return None
        
    async def create_task(self, project_name: str, function_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """创建新任务
        
        Args:
            project_name: 项目名称
            function_name: 函数名称
            payload: 函数参数
            
        Returns:
            任务信息
        """
        # 检查是否有正在运行的任务
        running_task = self._get_running_task(project_name, function_name)
        if running_task:
            return running_task
                
        task_id = self._generate_task_id(project_name, function_name)
        task_info = {
            "task_id": task_id,
            "project_name": project_name,
            "function_name": function_name,
            "payload": payload,
            "status": "created",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "result": None,
            "error": None
        }
        
        with self.task_lock:
            self.tasks[task_id] = task_info
            self._save_task_state(task_id, task_info)
            
        # 创建任务队列和事件
        self.state.create_task_queue(task_id)
        self.state.create_task_event(task_id)
            
        # 启动任务执行
        asyncio.create_task(self._execute_task(task_id))
        
        return task_info
        
    async def _execute_task(self, task_id: str):
        """执行任务
        
        Args:
            task_id: 任务ID
        """
        task_info = self.tasks.get(task_id)
        if not task_info:
            logger.error(f"任务不存在: {task_id}")
            return
            
        try:
            # 更新任务状态
            task_info["status"] = "running"
            task_info["updated_at"] = datetime.now().isoformat()
            self._save_task_state(task_id, task_info)
            
            # 获取主进程实例
            master = self.state.get_master()
            if not master:
                raise Exception("无法获取主进程实例")
                
            # 执行函数（不设置超时）
            result = await master.execute_function(
                task_info["project_name"],
                task_info["function_name"],
                task_info["payload"]
            )
            
            # 更新任务状态
            task_info["status"] = "completed"
            task_info["result"] = result
            task_info["updated_at"] = datetime.now().isoformat()
            
        except Exception as e:
            logger.error(f"任务执行失败: {str(e)}", exc_info=True)
            task_info["status"] = "failed"
            task_info["error"] = str(e)
            task_info["updated_at"] = datetime.now().isoformat()
            
        finally:
            self._save_task_state(task_id, task_info)
            # 清理任务资源
            self.state.cleanup_task_resources(task_id)
            
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务信息，如果不存在则返回 None
        """
        # 先从内存中查找
        task_info = self.tasks.get(task_id)
        if task_info:
            return task_info
            
        # 如果内存中不存在，尝试从文件加载
        task_info = self._load_task_state(task_id)
        if task_info:
            with self.task_lock:
                self.tasks[task_id] = task_info
            return task_info
            
        return None
        
    async def list_tasks(self, status: Optional[str] = None) -> list:
        """列出所有任务
        
        Args:
            status: 可选的过滤状态
            
        Returns:
            任务列表
        """
        tasks = []
        for task_id in os.listdir(self.task_dir):
            if task_id.endswith('.json'):
                task_info = self._load_task_state(task_id[:-5])
                if task_info and (status is None or task_info["status"] == status):
                    tasks.append(task_info)
        return tasks
        
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功取消
        """
        task_info = self.tasks.get(task_id)
        if not task_info:
            task_info = self._load_task_state(task_id)
            if not task_info:
                return False
                
        if task_info["status"] not in ["created", "running"]:
            return False
            
        task_info["status"] = "cancelled"
        task_info["updated_at"] = datetime.now().isoformat()
        self._save_task_state(task_id, task_info)
        
        with self.task_lock:
            self.tasks[task_id] = task_info
            
        return True
        
    def cleanup_old_tasks(self, days: int = 7):
        """清理旧任务
        
        Args:
            days: 保留天数
        """
        current_time = datetime.now()
        for task_id in os.listdir(self.task_dir):
            if task_id.endswith('.json'):
                task_info = self._load_task_state(task_id[:-5])
                if task_info:
                    created_at = datetime.fromisoformat(task_info["created_at"])
                    if (current_time - created_at).days > days:
                        os.remove(os.path.join(self.task_dir, task_id))
                        with self.task_lock:
                            self.tasks.pop(task_id[:-5], None) 