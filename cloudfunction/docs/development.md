# 开发指南

## 快速开始

### 1. 创建函数
在 `cloudfunction/projects/your_project/` 目录下创建你的函数文件，例如 `hello.py`：

```python
import logging
from typing import Dict, Any
from cloudfunction.utils.logger import get_project_logger

# 配置日志
logger = get_project_logger('your_project')

async def main(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    入口函数
    
    Args:
        event: 输入事件数据，例如 {"name": "张三"}
    
    Returns:
        Dict[str, Any]: 处理结果，例如 {"status": "success", "result": {"message": "你好，张三"}}
    """
    try:
        # 获取输入参数
        name = event.get("name", "世界")
        
        # 返回结果
        return {
            "status": "success",
            "result": {
                "message": f"你好，{name}"
            }
        }
    except Exception as e:
        # 记录错误
        logger.error(f"函数执行失败: {str(e)}")
        # 返回错误信息
        return {
            "status": "error",
            "error": str(e)
        }
```

### 2. 配置环境
在 `cloudfunction/projects/your_project/` 目录下创建 `.env` 文件，配置你的环境变量：

```ini
# 你的环境变量
API_KEY=your_api_key
```

### 3. 安装依赖
在 `cloudfunction/projects/your_project/` 目录下创建 `requirements.txt` 文件，添加你需要的包：

```txt
requests==2.31.0
pandas==2.1.0
```

### 4. 测试函数
1. 启动服务：
```bash
python -m cloudfunction.core.master
```

2. 部署函数：
```bash
# 部署函数
curl -X POST http://localhost:8080/api/v1/functions/your_project/hello/deploy

# 查看已部署的函数列表
curl http://localhost:8080/api/v1/functions/your_project
```

3. 调用函数：
```bash
curl -X POST http://localhost:8080/api/v1/functions/your_project/hello/invoke \
  -H "Content-Type: application/json" \
  -d '{"name": "张三"}'
```

## 开发规范

### 1. 函数编写
- 必须包含 `main` 函数作为入口点
- 支持异步（`async def main`）和同步（`def main`）函数
- 函数参数必须是 `Dict[str, Any]` 类型，命名为 `event`
- 返回值必须是 `Dict[str, Any]` 类型
- 必须处理异常并返回标准格式的结果

### 2. 错误处理
```python
async def main(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    入口函数
    
    Args:
        event: 输入事件数据
        
    Returns:
        Dict[str, Any]: 处理结果
    """
    try:
        # 你的代码
        result = await process_data(event)
        return {
            "status": "success",
            "result": result
        }
    except Exception as e:
        # 记录错误
        logger.error(f"函数执行失败: {str(e)}")
        # 返回错误信息
        return {
            "status": "error",
            "error": str(e)
        }
```

### 3. 日志记录
```python
import logging
from cloudfunction.utils.logger import get_project_logger

# 配置日志
logger = get_project_logger('your_project')

# 记录日志
logger.info("开始处理")
logger.error("发生错误")
```

## 常见问题

### 1. 函数无法执行
- 检查函数是否包含 `main` 函数
- 检查函数参数和返回值类型是否正确
- 检查项目目录结构是否正确
- 检查环境变量是否配置
- 查看日志文件了解错误原因

### 2. 依赖安装失败
- 检查 `requirements.txt` 格式是否正确
- 确保依赖包名称和版本正确
- 检查网络连接是否正常

### 3. 环境变量不生效
- 确保 `.env` 文件在正确的位置
- 检查环境变量名称是否正确
- 重启服务使环境变量生效

