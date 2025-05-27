# 日志系统

## 日志配置

系统使用 YAML 配置文件管理日志设置，配置文件位于 `config/logging_config.yaml`。

### 日志格式

系统支持两种日志格式：

1. 标准格式：
```
%(asctime)s [%(levelname)s] %(name)s: %(message)s
```

2. JSON 格式：
```json
{
    "timestamp": "2024-01-01 12:00:00",
    "level": "INFO",
    "message": "日志消息",
    "extra": {},  // 额外的字段
    "exception": ""  // 异常信息（如果有）
}
```

### 日志处理器

系统配置了以下日志处理器：

1. 控制台输出（console）
   - 输出到标准输出
   - 使用标准格式

2. 服务器日志（server）
   - 文件：`cloudfunction/logs/server.log`
   - 最大大小：10MB
   - 保留数量：5个备份
   - 使用标准格式

3. 错误日志（error）
   - 文件：`cloudfunction/logs/error.log`
   - 最大大小：10MB
   - 保留数量：5个备份
   - 仅记录 ERROR 级别
   - 使用标准格式

4. 项目日志
   - 应用日志：`cloudfunction/logs/projects/{project_name}/app.log`
   - 错误日志：`cloudfunction/logs/projects/{project_name}/error.log`
   - JSON日志：`cloudfunction/logs/projects/{project_name}/json.log`
   - 每个文件最大 10MB，保留 5 个备份

## 使用日志

### 在函数中使用日志

```python
from cloudfunction.utils.logger import get_project_logger
import time

# 获取项目日志记录器
logger = get_project_logger('your_project')

# 记录不同级别的日志
logger.debug("调试信息")
logger.info("普通信息")
logger.warning("警告信息")
logger.error("错误信息")
logger.critical("严重错误信息")

# 记录异常
try:
    # 你的代码
    pass
except Exception as e:
    logger.error(f"发生错误: {str(e)}", exc_info=True)
```

### 在项目中使用日志

```python
from cloudfunction.utils.logger import get_project_logger

# 获取项目日志记录器
logger = get_project_logger("your_project")

# 记录日志
logger.info("项目日志信息")
```

## 日志目录结构

```
cloudfunction/
└── logs/
    ├── server.log
    ├── error.log
    └── projects/
        └── your_project/
            ├── app.log
            ├── error.log
            └── json.log
```

## 日志级别

系统使用以下日志级别：

1. INFO：记录正常流程信息
   - 开始/完成处理
   - 处理耗时
   - 处理结果统计

2. WARNING：记录需要注意但不影响系统运行的问题
   - 未找到数据
   - 数据不完整
   - 非关键错误

3. ERROR：记录错误信息
   - 数据库连接失败
   - API 调用失败
   - 数据处理错误
   - 系统异常

默认日志级别为 INFO。

