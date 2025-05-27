from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any, List, Optional
from cloudfunction.utils.logger import get_logger
from cloudfunction.core.executor import FunctionExecutor
import os
from cloudfunction.core.registry import FunctionRegistry
import datetime

logger = get_logger(__name__)

router = APIRouter()

@router.get("/")
async def root():
    """根路径"""
    return {
        "service": "Cloud Function API",
        "version": "1.0.0",
        "status": "running"
    }

@router.get("/health")
async def health_check(request: Request):
    """健康检查
    
    返回系统的基本健康状态，包括：
    - 服务状态
    - 主进程状态
    - 项目状态
    """
    try:
        # 获取主进程状态
        master = request.app.state.get_master()
        
        # 获取项目状态
        registry = request.app.state.get_registry()
        projects = registry.list_projects() if registry else []
        
        return {
            "status": "healthy",
            "master": master is not None,
            "projects": len(projects),
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"健康检查失败: {str(e)}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }

def get_project_files(project_name: str, function_name: str = None) -> Dict[str, List[bytes]]:
    """
    自动查找项目目录下的必要文件
    
    Args:
        project_name: 项目名称
        function_name: 可选的函数名称，如果提供则只返回该函数的文件
        
    Returns:
        包含代码文件和依赖文件内容的字典
    """
    project_path = f"cloudfunction/projects/{project_name}"
    code_files = []
    requirements_file = os.path.join(project_path, "requirements.txt")
    
    if function_name:
        # 如果指定了函数名，只查找该函数的文件
        function_file = os.path.join(project_path, f"{function_name}.py")
        if not os.path.exists(function_file):
            raise FileNotFoundError(f"函数文件 {function_file} 不存在")
        with open(function_file, 'rb') as f:
            code_files.append(f.read())
    else:
        # 否则查找所有 .py 文件
        for file in os.listdir(project_path):
            if file.endswith(".py"):
                with open(os.path.join(project_path, file), 'rb') as f:
                    code_files.append(f.read())
    
    if not code_files:
        raise FileNotFoundError(f"项目 {project_name} 中没有找到 .py 文件")
    if not os.path.exists(requirements_file):
        raise FileNotFoundError(f"依赖文件 {requirements_file} 不存在")
    
    return {
        "code_files": code_files,
        "requirements": open(requirements_file, 'rb').read()
    }

@router.post("/api/v1/projects/{project_name}/deploy")
async def deploy_project(project_name: str, request: Request):
    """部署整个项目
    
    Args:
        project_name: 项目名称
        request: 请求对象
    """
    logger.info(f"收到项目部署请求: {project_name}")
    try:
        # 获取执行器
        executor = request.app.state.get_executor(project_name)
        logger.debug(f"获取到执行器: {executor}")
        
        # 部署项目
        result = await executor.deploy_project(project_name)
        logger.info(f"项目部署完成: {result}")
        return result
        
    except Exception as e:
        logger.error(f"项目部署失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/v1/functions/{project_name}/{function_name}/deploy")
async def deploy_function(
    project_name: str,
    function_name: str,
    request: Request
):
    """部署特定函数
    
    Args:
        project_name: 项目名称
        function_name: 函数名称
        request: 请求对象
    """
    logger.info(f"收到函数部署请求: project={project_name}, function={function_name}")
    try:
        # 自动查找特定函数文件
        project_files = get_project_files(project_name, function_name)
        
        # 获取执行器
        executor = request.app.state.get_executor(project_name)
        logger.debug(f"获取到执行器: {executor}")
        
        # 部署特定函数
        result = await executor.deploy_function(
            function_name=function_name,
            code=project_files["code_files"][0],  # 使用函数对应的文件内容
            requirements=project_files["requirements"]
        )
        logger.info(f"函数部署成功: {result}")
        return result
        
    except Exception as e:
        logger.error(f"函数部署失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/v1/functions/{project_name}/{function_name}/invoke")
async def invoke_function_api(
    project_name: str,
    function_name: str,
    request: Request
):
    """调用函数（异步）
    
    Args:
        project_name: 项目名称
        function_name: 函数名称
        request: 请求对象
    """
    logger.info(f"收到函数调用请求: project={project_name}, function={function_name}")
    try:
        # 获取请求体
        payload = await request.json()
        
        # 获取任务管理器
        task_manager = request.app.state.get_task_manager()
        if not task_manager:
            raise HTTPException(
                status_code=500,
                detail="Task manager not initialized"
            )
            
        # 创建任务
        task_info = await task_manager.create_task(project_name, function_name, payload)
        logger.info(f"任务创建成功: {task_info['task_id']}")
        return {
            "status": "success",
            "task_id": task_info["task_id"],
            "message": "Task created successfully"
        }
        
    except Exception as e:
        logger.error(f"函数调用失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/v1/functions/{project_name}")
async def list_functions(project_name: str, request: Request):
    """获取函数列表
    
    Args:
        project_name: 项目名称
        request: 请求对象
    """
    logger.info(f"收到函数列表请求: project={project_name}")
    try:
        executor = request.app.state.get_executor(project_name)
        logger.debug(f"获取到执行器: {executor}")
        
        functions = await executor.list_functions()
        logger.info(f"获取函数列表成功: {len(functions)} 个函数")
        return functions
        
    except Exception as e:
        logger.error(f"获取函数列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/v1/functions/{project_name}/{function_name}")
async def delete_function(project_name: str, function_name: str, request: Request):
    """删除函数"""
    logger.info(f"收到函数删除请求: project={project_name}, function={function_name}")
    try:
        # 通过 state 获取 registry
        registry = request.app.state.get_registry()
        if not registry:
            raise HTTPException(status_code=500, detail="Registry not initialized")
            
        # 使用 registry 的删除方法
        success = await registry.delete_function(project_name, function_name)
        if not success:
            raise HTTPException(status_code=404, detail=f"函数 {function_name} 不存在")
            
        logger.info(f"函数删除成功: {function_name}")
        return {"message": f"函数 {function_name} 已成功删除"}
        
    except Exception as e:
        logger.error(f"函数删除失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/v1/projects/{project_name}")
async def delete_project(project_name: str, request: Request):
    """删除项目"""
    logger.info(f"收到项目删除请求: project={project_name}")
    try:
        # 通过 state 获取 registry
        registry = request.app.state.get_registry()
        if not registry:
            raise HTTPException(status_code=500, detail="Registry not initialized")
            
        success = await registry.delete_project(project_name)
        if not success:
            raise HTTPException(status_code=404, detail=f"项目 {project_name} 不存在")
            
        logger.info(f"项目删除成功: {project_name}")
        return {"message": f"项目 {project_name} 已成功删除"}
        
    except Exception as e:
        logger.error(f"项目删除失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/v1/tasks/{task_id}")
async def get_task_status(task_id: str, request: Request):
    """获取任务状态
    
    Args:
        task_id: 任务ID
        request: 请求对象
    """
    logger.info(f"收到任务状态查询请求: task_id={task_id}")
    try:
        # 获取任务管理器
        task_manager = request.app.state.get_task_manager()
        if not task_manager:
            raise HTTPException(
                status_code=500,
                detail="Task manager not initialized"
            )
            
        # 获取任务状态
        task_info = await task_manager.get_task_status(task_id)
        if not task_info:
            raise HTTPException(
                status_code=404,
                detail=f"Task {task_id} not found"
            )
            
        return task_info
        
    except Exception as e:
        logger.error(f"获取任务状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/v1/tasks")
async def list_tasks(request: Request, status: Optional[str] = None):
    """获取任务列表
    
    Args:
        request: 请求对象
        status: 可选的过滤状态
    """
    logger.info(f"收到任务列表请求: status={status}")
    try:
        # 获取任务管理器
        task_manager = request.app.state.get_task_manager()
        if not task_manager:
            raise HTTPException(
                status_code=500,
                detail="Task manager not initialized"
            )
            
        # 获取任务列表
        tasks = await task_manager.list_tasks(status)
        return tasks
        
    except Exception as e:
        logger.error(f"获取任务列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/v1/tasks/{task_id}")
async def cancel_task(task_id: str, request: Request):
    """取消任务
    
    Args:
        task_id: 任务ID
        request: 请求对象
    """
    logger.info(f"收到任务取消请求: task_id={task_id}")
    try:
        # 获取任务管理器
        task_manager = request.app.state.get_task_manager()
        if not task_manager:
            raise HTTPException(
                status_code=500,
                detail="Task manager not initialized"
            )
            
        # 取消任务
        success = await task_manager.cancel_task(task_id)
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Task {task_id} not found or cannot be cancelled"
            )
            
        return {"message": f"Task {task_id} cancelled successfully"}
        
    except Exception as e:
        logger.error(f"取消任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/v1/functions/{project_name}/{function_name}/tasks")
async def list_function_tasks(
    project_name: str,
    function_name: str,
    request: Request,
    status: Optional[str] = None
):
    """获取特定函数的所有任务
    
    Args:
        project_name: 项目名称
        function_name: 函数名称
        request: 请求对象
        status: 可选的过滤状态
    """
    logger.info(f"收到函数任务列表请求: project={project_name}, function={function_name}")
    try:
        # 获取任务管理器
        task_manager = request.app.state.get_task_manager()
        if not task_manager:
            raise HTTPException(
                status_code=500,
                detail="Task manager not initialized"
            )
            
        # 获取任务列表
        tasks = await task_manager.list_tasks(status)
        # 过滤特定函数的任务
        function_tasks = [
            task for task in tasks 
            if task["project_name"] == project_name and task["function_name"] == function_name
        ]
        return function_tasks
        
    except Exception as e:
        logger.error(f"获取函数任务列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/v1/functions/{project_name}/{function_name}/tasks/{task_id}")
async def get_function_task(
    project_name: str,
    function_name: str,
    task_id: str,
    request: Request
):
    """获取特定函数的任务状态
    
    Args:
        project_name: 项目名称
        function_name: 函数名称
        task_id: 任务ID
        request: 请求对象
    """
    logger.info(f"收到函数任务状态查询请求: project={project_name}, function={function_name}, task_id={task_id}")
    try:
        # 获取任务管理器
        task_manager = request.app.state.get_task_manager()
        if not task_manager:
            raise HTTPException(
                status_code=500,
                detail="Task manager not initialized"
            )
            
        # 获取任务状态
        task_info = await task_manager.get_task_status(task_id)
        if not task_info:
            raise HTTPException(
                status_code=404,
                detail=f"Task {task_id} not found"
            )
            
        # 验证任务是否属于指定的函数
        if task_info["project_name"] != project_name or task_info["function_name"] != function_name:
            raise HTTPException(
                status_code=404,
                detail=f"Task {task_id} does not belong to function {function_name}"
            )
            
        return task_info
        
    except Exception as e:
        logger.error(f"获取函数任务状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/v1/functions/{project_name}/{function_name}/tasks/{task_id}")
async def cancel_function_task(
    project_name: str,
    function_name: str,
    task_id: str,
    request: Request
):
    """取消特定函数的任务
    
    Args:
        project_name: 项目名称
        function_name: 函数名称
        task_id: 任务ID
        request: 请求对象
    """
    logger.info(f"收到函数任务取消请求: project={project_name}, function={function_name}, task_id={task_id}")
    try:
        # 获取任务管理器
        task_manager = request.app.state.get_task_manager()
        if not task_manager:
            raise HTTPException(
                status_code=500,
                detail="Task manager not initialized"
            )
            
        # 获取任务状态
        task_info = await task_manager.get_task_status(task_id)
        if not task_info:
            raise HTTPException(
                status_code=404,
                detail=f"Task {task_id} not found"
            )
            
        # 验证任务是否属于指定的函数
        if task_info["project_name"] != project_name or task_info["function_name"] != function_name:
            raise HTTPException(
                status_code=404,
                detail=f"Task {task_id} does not belong to function {function_name}"
            )
            
        # 取消任务
        success = await task_manager.cancel_task(task_id)
        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Task {task_id} cannot be cancelled"
            )
            
        return {"message": f"Task {task_id} cancelled successfully"}
        
    except Exception as e:
        logger.error(f"取消函数任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

logger.info("API路由设置完成") 