from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any, List
from cloudfunction.utils.logger import get_logger
from cloudfunction.core.executor import FunctionExecutor
import os
from cloudfunction.core.registry import FunctionRegistry

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
async def health_check():
    """健康检查"""
    return {"status": "healthy"}

def get_project_files(project_name: str) -> Dict[str, List[bytes]]:
    """自动查找项目目录下的必要文件"""
    project_path = f"cloudfunction/projects/{project_name}"
    code_files = []
    requirements_file = os.path.join(project_path, "requirements.txt")
    
    # 查找所有 .py 文件
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
    logger.info(f"收到项目部署请求: project={project_name}")
    try:
        # 自动查找项目文件
        project_files = get_project_files(project_name)
        
        # 获取执行器
        executor = request.app.state.get_executor(project_name)
        logger.debug(f"获取到执行器: {executor}")
        
        # 部署整个项目
        result = await executor.deploy_project(project_name)
        logger.info(f"项目部署成功: {result}")
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
        # 自动查找项目文件
        project_files = get_project_files(project_name)
        
        # 获取执行器
        executor = request.app.state.get_executor(project_name)
        logger.debug(f"获取到执行器: {executor}")
        
        # 部署特定函数
        result = await executor.deploy_function(
            function_name=function_name,
            code=project_files["code_files"][0],  # 使用第一个文件的字节内容
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
    """调用特定函数
    
    Args:
        project_name: 项目名称
        function_name: 函数名称
        request: 请求对象
    """
    logger.info(f"收到函数调用请求: project={project_name}, function={function_name}")
    try:
        # 获取请求体
        payload = await request.json()
        
        # 获取执行器
        executor = request.app.state.get_executor(project_name)
        if not executor:
            # 如果执行器不存在，创建新的执行器
            registry = request.app.state.registry
            if not registry:
                raise HTTPException(
                    status_code=500,
                    detail="Registry not initialized"
                )
            executor = FunctionExecutor(project_name, registry)
            
        logger.debug(f"获取到执行器: {executor}")
        
        # 调用函数
        result = await executor.execute(function_name, payload)
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["error"])
            
        logger.info(f"函数调用成功: {result}")
        return result
        
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

logger.info("API路由设置完成") 