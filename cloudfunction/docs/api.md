# API 文档

## 基础接口

### 健康检查
```bash
GET /health
```
响应:
```json
{
    "status": "healthy",
    "version": "1.0.0",
    "timestamp": "2024-03-21T10:00:00Z"
}
```

### 系统状态
```bash
GET /status
```
响应:
```json
{
    "status": "running",
    "uptime": "2h 30m",
    "active_projects": 3,
    "total_functions": 15,
    "memory_usage": "256MB"
}
```

## 项目管理接口

### 1. 启动项目
```bash
POST /api/v1/projects/{project_name}/start
```
- 功能：启动指定项目
- 参数：
  - `project_name`: 项目名称
- 响应：
  ```json
  {
    "status": "success",
    "message": "项目启动成功",
    "project": {
      "name": "project_name",
      "status": "running",
      "start_time": "2024-03-21T10:00:00Z"
    }
  }
  ```

### 2. 停止项目
```bash
POST /api/v1/projects/{project_name}/stop
```
- 功能：停止指定项目
- 参数：
  - `project_name`: 项目名称
- 响应：
  ```json
  {
    "status": "success",
    "message": "项目停止成功",
    "project": {
      "name": "project_name",
      "status": "stopped",
      "stop_time": "2024-03-21T10:00:00Z"
    }
  }
  ```

### 3. 获取项目列表
```bash
GET /api/v1/projects
```
- 功能：获取所有项目信息
- 响应：
  ```json
  {
    "status": "success",
    "data": [
      {
        "name": "project1",
        "status": "running",
        "functions": ["func1", "func2"],
        "created_at": "2024-03-21T10:00:00Z",
        "updated_at": "2024-03-21T10:00:00Z"
      }
    ]
  }
  ```

### 4. 获取项目详情
```bash
GET /api/v1/projects/{project_name}
```
- 功能：获取指定项目的详细信息
- 参数：
  - `project_name`: 项目名称
- 响应：
  ```json
  {
    "status": "success",
    "data": {
      "name": "project1",
      "status": "running",
      "functions": [
        {
          "name": "func1",
          "description": "函数1描述",
          "status": "active",
          "last_executed": "2024-03-21T10:00:00Z"
        }
      ],
      "env": {
        "key1": "value1"
      },
      "dependencies": [
        "requests>=2.31.0"
      ],
      "created_at": "2024-03-21T10:00:00Z",
      "updated_at": "2024-03-21T10:00:00Z"
    }
  }
  ```

## 函数管理接口

### 1. 部署函数
```bash
POST /api/v1/functions/{project_name}/deploy
Content-Type: multipart/form-data

function_name: 函数名称
code: 函数代码文件
requirements: 依赖文件（可选）
env_vars: 环境变量（可选）
```
响应:
```json
{
    "status": "success",
    "message": "Function deployed successfully",
    "function": {
        "name": "function_name",
        "project": "project_name",
        "status": "active",
        "deployed_at": "2024-03-21T10:00:00Z"
    }
}
```

### 2. 调用函数
```bash
POST /api/v1/functions/{project_name}/{function_name}/invoke
Content-Type: application/json

{
    "key": "value"
}
```
响应:
```json
{
    "status": "success",
    "result": "函数执行结果",
    "execution_time": "0.5s",
    "timestamp": "2024-03-21T10:00:00Z"
}
```

### 3. 获取函数列表
```bash
GET /api/v1/functions/{project_name}
```
响应:
```json
{
    "status": "success",
    "functions": [
        {
            "name": "function1",
            "description": "函数1描述",
            "status": "active",
            "last_executed": "2024-03-21T10:00:00Z"
        }
    ]
}
```

### 4. 获取函数详情
```bash
GET /api/v1/functions/{project_name}/{function_name}
```
响应:
```json
{
    "status": "success",
    "function": {
        "name": "function1",
        "description": "函数1描述",
        "parameters": {
            "param1": "参数1说明"
        },
        "status": "active",
        "created_at": "2024-03-21T10:00:00Z",
        "updated_at": "2024-03-21T10:00:00Z",
        "last_executed": "2024-03-21T10:00:00Z",
        "execution_count": 100
    }
}
```

### 5. 删除函数
```bash
DELETE /api/v1/functions/{project_name}/{function_name}
```
响应:
```json
{
    "status": "success",
    "message": "Function deleted successfully"
}
```

## 环境变量管理接口

### 1. 获取系统级环境变量
```bash
GET /api/v1/env/system
```
响应:
```json
{
    "status": "success",
    "data": {
        "DB_HOST": "localhost",
        "DB_PORT": "3306"
    }
}
```

### 2. 获取项目级环境变量
```bash
GET /api/v1/projects/{project_name}/env
```
响应:
```json
{
    "status": "success",
    "data": {
        "API_KEY": "your_api_key",
        "ENVIRONMENT": "development"
    }
}
```

## 依赖管理接口

### 1. 获取系统级依赖
```bash
GET /api/v1/dependencies/system
```
响应:
```json
{
    "status": "success",
    "data": [
        "requests>=2.31.0",
        "numpy>=1.24.0"
    ]
}
```

### 2. 获取项目级依赖
```bash
GET /api/v1/projects/{project_name}/dependencies
```
响应:
```json
{
    "status": "success",
    "data": [
        "pandas>=2.0.0",
        "scikit-learn>=1.3.0"
    ]
}
```

## 错误响应
所有接口在发生错误时都会返回统一的错误格式：
```json
{
    "status": "error",
    "code": "错误代码",
    "message": "错误描述",
    "details": {
        "field": "具体错误字段",
        "reason": "具体错误原因"
    }
}
```

常见错误代码：
- `PROJECT_NOT_FOUND`: 项目不存在
- `FUNCTION_NOT_FOUND`: 函数不存在
- `INVALID_PARAMETERS`: 参数无效
- `EXECUTION_ERROR`: 执行错误
- `ENV_ERROR`: 环境变量错误
- `DEPENDENCY_ERROR`: 依赖错误
- `AUTHENTICATION_ERROR`: 认证错误
- `AUTHORIZATION_ERROR`: 授权错误
- `RATE_LIMIT_ERROR`: 速率限制错误
- `INTERNAL_ERROR`: 内部服务器错误 