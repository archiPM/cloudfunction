# 工具库使用指南

本文档介绍 CloudFunction 框架中 `utils` 目录下提供的各种工具模块，帮助开发者更高效地开发云函数。

## 目录

- [大语言模型 (LLM)](#大语言模型-llm)
- [数据库管理](#数据库管理)
- [日志系统](#日志系统)

## 大语言模型 (LLM)

CloudFunction 框架集成了多个大语言模型 API，提供统一的接口，便于在云函数中使用 LLM 能力。

### 客户端初始化

```python
from utils.llm import get_llm_client

# 获取默认 LLM 客户端（由环境变量 DEFAULT_LLM_PROVIDER 指定）
llm_client = get_llm_client()

# 指定使用特定提供商的客户端
deepseek_client = get_llm_client('deepseek')
doubao_client = get_llm_client('doubao')
minimax_client = get_llm_client('minimax')
```

### API 调用

```python
# 调用 LLM API
response = llm_client.call_api(
    messages=[
        {"role": "system", "content": "你是一个专业的助手。"},
        {"role": "user", "content": "请简要介绍一下人工智能。"}
    ],
    model="deepseek-r1-distill-qwen-32b-250120",  # 可选，默认使用提供商的默认模型
    temperature=0.7,                             # 可选，控制生成的随机性
    max_tokens=1000                              # 可选，控制生成的最大token数
)

# 获取生成的内容
content = response.choices[0].message.content
print(content)
```

### 支持的模型提供商

系统目前支持以下 LLM 提供商：

| 提供商 | 标识符 | 默认模型 | 上下文窗口 |
|-------|-------|---------|----------|
| DeepSeek | `deepseek` | deepseek-r1-250120 | 64K tokens |
| 豆包 | `doubao` | doubao-lite | 32K tokens |
| MiniMax | `minimax` | abab6.5-chat | 32K tokens |

### 环境配置

在项目的 `.env` 文件中配置相关 API 密钥和默认提供商：

```bash
# 默认 LLM 提供商
DEFAULT_LLM_PROVIDER=deepseek

# DeepSeek API 配置
ARK_API_KEY=your_deepseek_api_key

# 豆包 API 配置
DOUBAO_API_KEY=your_doubao_api_key

# MiniMax API 配置
MINIMAX_API_KEY=your_minimax_api_key
MINIMAX_GROUP_ID=your_minimax_group_id
```

### JSON 处理

LLM 客户端提供了 JSON 解析辅助函数，方便从模型响应中提取 JSON 数据：

```python
# 解析响应中的 JSON 内容
try:
    json_data = llm_client.parse_json_response(response)
    print(f"解析成功: {json_data}")
except Exception as e:
    print(f"解析失败: {e}")
```

### 复杂 JSON 响应处理

当 LLM 返回的 JSON 内容嵌套在其他文本中时，可以使用以下处理方式：

```python
# 手动处理 LLM 响应，提取 JSON 部分
if hasattr(response, 'choices') and len(response.choices) > 0:
    content = response.choices[0].message.content
    
    # 尝试直接解析
    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        # 如果直接解析失败，尝试提取 JSON 部分
        import re
        
        # 方法1：查找最外层的方括号内容 (适用于返回数组)
        json_match = re.search(r'\[[\s\S]*\]', content)
        if json_match:
            result = json.loads(json_match.group())
            
        # 方法2：查找最外层的花括号内容 (适用于返回对象)
        else:
            brace_match = re.search(r'\{[\s\S]*\}', content)
            if brace_match:
                result = json.loads(brace_match.group())
```

### 文本分析

```python
# 分析文本并提取信息
analysis_result = llm_client.analyze_text(
    text="需要分析的文本内容",
    system_prompt="你是一个专业的文本分析助手，请从以下文本中提取关键信息，以JSON格式返回。",
    temperature=0.3
)

print(analysis_result)
```

## 数据库管理

CloudFunction 框架提供了简单易用的数据库管理模块，支持项目级数据库连接管理。

### 数据库管理器初始化

```python
from utils.db import get_db_manager

# 获取指定项目的数据库管理器
db_manager = get_db_manager('media_data_process')
```

### 会话使用

```python
# 使用 with 语句自动管理数据库会话
with db_manager.get_session() as session:
    # 执行 SQL 查询
    result = session.execute(
        "SELECT * FROM users WHERE id = :user_id",
        {'user_id': 1}
    )
    user = result.first()
    print(user)
    
    # 使用 SQLAlchemy ORM
    from sqlalchemy import text
    query = text("SELECT * FROM posts LIMIT :limit")
    posts = session.execute(query, {'limit': 10})
    for post in posts:
        print(post)
```

### 环境配置

在项目目录的 `.env` 文件中配置数据库连接信息：

```bash
# 数据库连接配置
DB_HOST=localhost
DB_PORT=3306
DB_USER=dbuser
DB_PASSWORD=dbpassword
DB_NAME=dbname

# 连接池配置（可选）
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600
```

### 连接管理

系统提供了以下函数来管理数据库连接：

```python
# 关闭所有数据库连接（通常在函数退出前调用）
from utils.db import close_all_connections
close_all_connections()

# 获取数据库连接状态
from utils.db import get_connection_status
status = get_connection_status()
print(status)

# 重置连接池（当连接出现问题时使用）
from utils.db import reset_connection_pool
reset_connection_pool('media_data_process')  # 重置特定项目的连接池
reset_connection_pool()  # 重置所有连接池
```

### 事务管理

框架的数据库会话管理器会自动处理事务：

- 当会话正常结束时，自动提交事务
- 当会话抛出异常时，自动回滚事务
- 在任何情况下，都会关闭数据库连接

```python
try:
    with db_manager.get_session() as session:
        # 执行数据库操作
        session.execute(...)
        # 如果没有异常，事务会自动提交
except Exception as e:
    # 如果有异常，事务会自动回滚
    print(f"数据库操作失败: {e}")
# 无论如何，会话都会自动关闭
```

## 日志系统

CloudFunction 提供了强大的日志管理功能，详细文档请参考 [日志系统文档](logging.md)。

在工具库中使用日志的简要示例：

```python
from utils.logger import get_project_logger

# 获取项目日志记录器
logger = get_project_logger('media_data_process')

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

## 最佳实践

### LLM 使用最佳实践

1. **设置合理的温度值**
   - 需要准确、确定性回答时，使用较低的温度值（0.1-0.3）
   - 需要创造性、多样性回答时，使用较高的温度值（0.7-0.9）

2. **有效处理 JSON 响应**
   - 在提示词中明确要求模型返回 JSON 格式
   - 使用框架提供的 JSON 解析辅助函数
   - 对解析结果进行验证，确保所需字段存在且类型正确

3. **错误处理和重试**
   - 对 LLM 调用进行异常捕获
   - 实现重试机制处理临时性错误

4. **性能优化**
   - 合理设置最大token数，避免不必要的开销
   - 根据需求选择合适的模型，不要过度使用高级模型
   - 合理设计提示词，减少交互轮次

### 数据库使用最佳实践

1. **连接管理**
   - 使用上下文管理器（`with`语句）自动管理会话
   - 在函数结束时调用`close_all_connections()`释放连接
   
2. **避免长时间事务**
   - 将大型操作拆分为多个小事务
   - 避免在事务中执行耗时的非数据库操作

3. **参数化查询**
   - 始终使用参数化查询防止 SQL 注入
   - 对用户输入进行验证和过滤

4. **连接池管理**
   - 适当设置连接池大小，避免资源浪费
   - 定期检查连接状态，处理潜在的连接泄漏 