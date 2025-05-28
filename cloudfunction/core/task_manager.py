import asyncio
import logging
import os
import time
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import yaml
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from cloudfunction.utils.logger import get_logger
from concurrent.futures import ThreadPoolExecutor
import threading

logger = get_logger(__name__)

class TaskManager:
    """统一的任务管理器，同时处理普通任务和定时任务"""
    
    def __init__(self, state):
        """初始化任务管理器
        
        Args:
            state: ServerState 实例
        """
        self.state = state
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.task_lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.task_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tasks")
        os.makedirs(self.task_dir, exist_ok=True)
        
        # 初始化定时任务调度器
        self.scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
        self.config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "scheduler_config.yaml")
        
    def _generate_task_id(self, project_name: str, function_name: str) -> str:
        """生成任务ID"""
        return f"{project_name}_{function_name}_{uuid.uuid4()}"
        
    def _save_task_state(self, task_id: str, task_info: Dict[str, Any]):
        """保存任务状态到文件"""
        task_file = os.path.join(self.task_dir, f"{task_id}.json")
        with open(task_file, 'w', encoding='utf-8') as f:
            json.dump(task_info, f, ensure_ascii=False, indent=2)
            
    def _load_task_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        """从文件加载任务状态"""
        task_file = os.path.join(self.task_dir, f"{task_id}.json")
        if os.path.exists(task_file):
            with open(task_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
        
    def _get_running_task(self, project_name: str, function_name: str) -> Optional[Dict[str, Any]]:
        """获取正在运行的任务"""
        prefix = f"{project_name}_{function_name}"
        for task_id, task_info in self.tasks.items():
            if task_id.startswith(prefix) and task_info["status"] in ["created", "running"]:
                return task_info
        return None
        
    async def create_task(self, project_name: str, function_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """创建新任务"""
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
        """执行任务"""
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
                
            # 执行函数
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
        """获取任务状态"""
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
        
    def cleanup_old_tasks(self, days: int = 7):
        """清理旧任务文件"""
        try:
            logger.info(f"开始清理{days}天前的任务文件")
            cutoff_time = time.time() - (days * 24 * 60 * 60)
            
            for filename in os.listdir(self.task_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.task_dir, filename)
                    if os.path.getmtime(filepath) < cutoff_time:
                        os.remove(filepath)
                        logger.info(f"已删除旧任务文件: {filename}")
                        
            logger.info("任务文件清理完成")
        except Exception as e:
            logger.error(f"清理任务文件失败: {str(e)}", exc_info=True)
            
    def setup_scheduler(self):
        """设置定时任务"""
        try:
            # 加载配置
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                
            # 设置系统级任务
            for task_id, task_config in config.get("tasks", {}).get("system", {}).items():
                schedule = task_config.get("schedule", {})
                if schedule.get("type") == "cron":
                    self.scheduler.add_job(
                        lambda t=task_config: asyncio.create_task(
                            self.create_task(t["project"], t["function"], t.get("args", {}))
                        ),
                        CronTrigger(
                            day_of_week=schedule.get("day_of_week"),
                            hour=schedule.get("hour"),
                            minute=schedule.get("minute"),
                            week=schedule.get("week")
                        ),
                        id=f"system_{task_id}",
                        replace_existing=True
                    )
                    
            # 设置项目级任务
            for project, project_tasks in config.get("tasks", {}).get("projects", {}).items():
                for task_id, task_config in project_tasks.items():
                    schedule = task_config.get("schedule", {})
                    if schedule.get("type") == "cron":
                        self.scheduler.add_job(
                            lambda t=task_config: asyncio.create_task(
                                self.create_task(t["project"], t["function"], t.get("args", {}))
                            ),
                            CronTrigger(
                                day_of_week=schedule.get("day_of_week"),
                                hour=schedule.get("hour"),
                                minute=schedule.get("minute"),
                                week=schedule.get("week")
                            ),
                            id=f"project_{project}_{task_id}",
                            replace_existing=True
                        )
                        
            logger.info("定时任务设置完成")
        except Exception as e:
            logger.error(f"设置定时任务失败: {str(e)}", exc_info=True)
            
    def start(self):
        """启动任务管理器"""
        try:
            self.setup_scheduler()
            self.scheduler.start()
            logger.info("任务管理器启动成功")
        except Exception as e:
            logger.error(f"任务管理器启动失败: {str(e)}", exc_info=True)
            
    def shutdown(self):
        """关闭任务管理器"""
        try:
            self.scheduler.shutdown()
            logger.info("任务管理器已关闭")
        except Exception as e:
            logger.error(f"关闭任务管理器失败: {str(e)}", exc_info=True)
            
    async def list_tasks(self, project_name: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出所有任务
        
        Args:
            project_name: 可选，按项目名称过滤
            status: 可选，按状态过滤
            
        Returns:
            任务列表
        """
        tasks = []
        with self.task_lock:
            for task_id, task_info in self.tasks.items():
                # 应用过滤器
                if project_name and task_info["project_name"] != project_name:
                    continue
                if status and task_info["status"] != status:
                    continue
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
            logger.error(f"任务不存在: {task_id}")
            return False
            
        if task_info["status"] not in ["created", "running"]:
            logger.error(f"任务状态不允许取消: {task_info['status']}")
            return False
            
        try:
            # 更新任务状态
            task_info["status"] = "cancelled"
            task_info["updated_at"] = datetime.now().isoformat()
            self._save_task_state(task_id, task_info)
            
            # 清理任务资源
            self.state.cleanup_task_resources(task_id)
            
            logger.info(f"任务已取消: {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"取消任务失败: {str(e)}", exc_info=True)
            return False 