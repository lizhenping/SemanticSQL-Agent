# 异常类 API 文档

## 概述
`models.exceptions` 模块定义了 SemanticSQL Agent 系统中使用的所有自定义异常类。这些异常类提供了结构化的错误处理机制，使得错误信息更加清晰和易于调试。

## 异常类层次结构

```
SemanticSQLError (基类)
├── ConfigurationError
├── ToolExecutionError
├── DatabaseConnectionError
├── ValidationError
├── GenerationError
├── LLMError
├── SchemaExtractionError
├── SQLExecutionError
├── PromptError
└── AgentExecutionError
```

## 基础异常类

### SemanticSQLError
所有 SemanticSQL 异常的基类。

```python
class SemanticSQLError(Exception):
    """基础 SemanticSQL 异常类"""
    pass
```

**用途：**
- 作为所有自定义异常的基类
- 便于统一捕获所有 SemanticSQL 相关异常

**使用示例：**
```python
try:
    # 某些操作
    pass
except SemanticSQLError as e:
    # 捕获所有 SemanticSQL 异常
    logger.error(f"SemanticSQL错误: {e}")
```

## 配置异常

### ConfigurationError
配置相关错误。

```python
class ConfigurationError(SemanticSQLError):
    """配置错误"""
    pass
```

**触发场景：**
- 配置文件缺失或格式错误
- 必需的配置项未设置
- 配置值不合法

**使用示例：**
```python
if not settings.llm_api_key:
    raise ConfigurationError("LLM API密钥未配置")
```

## 工具执行异常

### ToolExecutionError
工具执行错误。

```python
class ToolExecutionError(SemanticSQLError):
    """工具执行错误"""
    def __init__(self, tool_name: str, message: str, original_error: Exception = None):
        self.tool_name = tool_name
        self.original_error = original_error
        super().__init__(f"工具 '{tool_name}' 执行失败: {message}")
```

**属性：**
- `tool_name` (str): 失败的工具名称
- `original_error` (Exception): 原始异常（如果有）

**触发场景：**
- 工具内部逻辑错误
- 工具参数验证失败
- 工具依赖服务不可用

**使用示例：**
```python
try:
    result = tool.execute(**params)
except Exception as e:
    raise ToolExecutionError(
        tool_name="sql_generation",
        message="SQL生成失败",
        original_error=e
    )
```

## 数据库异常

### DatabaseConnectionError
数据库连接错误。

```python
class DatabaseConnectionError(SemanticSQLError):
    """数据库连接错误"""
    pass
```

**触发场景：**
- 数据库服务器不可达
- 认证失败
- 数据库不存在
- 连接超时

**使用示例：**
```python
try:
    connection = mysql.connector.connect(**db_config)
except mysql.connector.Error as e:
    raise DatabaseConnectionError(f"无法连接到数据库: {e}")
```

### SchemaExtractionError
数据库模式提取错误。

```python
class SchemaExtractionError(SemanticSQLError):
    """数据库模式提取错误"""
    pass
```

**触发场景：**
- 权限不足
- 表或列信息查询失败
- 元数据不完整

**使用示例：**
```python
try:
    schema = extract_database_schema(connection)
except Exception as e:
    raise SchemaExtractionError(f"无法提取数据库模式: {e}")
```

### SQLExecutionError
SQL 执行错误。

```python
class SQLExecutionError(SemanticSQLError):
    """SQL 执行错误"""
    def __init__(self, sql: str, message: str, original_error: Exception = None):
        self.sql = sql
        self.original_error = original_error
        super().__init__(f"SQL执行失败: {message}\nSQL: {sql[:200]}...")
```

**属性：**
- `sql` (str): 执行失败的 SQL 语句
- `original_error` (Exception): 原始数据库异常

**触发场景：**
- SQL 语法错误
- 表或列不存在
- 权限不足
- 违反约束

**使用示例：**
```python
try:
    cursor.execute(sql)
except mysql.connector.Error as e:
    raise SQLExecutionError(
        sql=sql,
        message=str(e),
        original_error=e
    )
```

## 验证和生成异常

### ValidationError
验证错误。

```python
class ValidationError(SemanticSQLError):
    """验证错误"""
    pass
```

**触发场景：**
- 输入数据格式错误
- 业务规则验证失败
- SQL 语法验证失败

**使用示例：**
```python
if not is_valid_sql(sql):
    raise ValidationError(f"无效的SQL语句: {sql}")
```

### GenerationError
生成错误。

```python
class GenerationError(SemanticSQLError):
    """生成错误"""
    pass
```

**触发场景：**
- SQL 生成失败
- 问题生成失败
- 场景生成失败

**使用示例：**
```python
if not generated_sql:
    raise GenerationError("无法生成符合要求的SQL查询")
```

## LLM 相关异常

### LLMError
LLM 调用错误。

```python
class LLMError(SemanticSQLError):
    """LLM 调用错误"""
    pass
```

**触发场景：**
- API 调用失败
- 超时
- 配额超限
- 响应格式错误

**使用示例：**
```python
try:
    response = llm_client.chat.completions.create(**params)
except Exception as e:
    raise LLMError(f"LLM调用失败: {e}")
```

### PromptError
提示词相关错误。

```python
class PromptError(SemanticSQLError):
    """提示词相关错误"""
    pass
```

**触发场景：**
- 提示词模板缺失
- 变量替换失败
- 提示词过长

**使用示例：**
```python
if not prompt_template:
    raise PromptError("找不到指定的提示词模板")
```

## 智能体执行异常

### AgentExecutionError
智能体执行错误。

```python
class AgentExecutionError(SemanticSQLError):
    """智能体执行错误"""
    def __init__(self, step: str, message: str, original_error: Exception = None):
        self.step = step
        self.original_error = original_error
        super().__init__(f"智能体在步骤 '{step}' 执行失败: {message}")
```

**属性：**
- `step` (str): 失败的执行步骤
- `original_error` (Exception): 原始异常

**触发场景：**
- 执行步骤超时
- 工具调用失败
- 解析响应失败

**使用示例：**
```python
try:
    result = agent._execute_action(action, params)
except Exception as e:
    raise AgentExecutionError(
        step="tool_execution",
        message="工具执行失败",
        original_error=e
    )
```

## 异常处理最佳实践

### 1. 分层异常处理
```python
def execute_query(natural_language_query: str):
    try:
        # 验证输入
        if not natural_language_query:
            raise ValidationError("查询不能为空")
        
        # 生成SQL
        try:
            sql = generate_sql(natural_language_query)
        except LLMError as e:
            raise GenerationError(f"SQL生成失败: {e}")
        
        # 执行SQL
        try:
            result = execute_sql(sql)
        except DatabaseConnectionError:
            raise  # 直接向上传递连接错误
        except Exception as e:
            raise SQLExecutionError(sql, str(e), e)
            
        return result
        
    except SemanticSQLError:
        raise  # SemanticSQL异常直接向上传递
    except Exception as e:
        # 其他未预期的异常
        raise SemanticSQLError(f"查询执行失败: {e}")
```

### 2. 异常信息增强
```python
try:
    result = risky_operation()
except SpecificError as e:
    # 添加上下文信息
    raise ToolExecutionError(
        tool_name="my_tool",
        message=f"操作失败，输入参数: {params}",
        original_error=e
    )
```

### 3. 异常日志记录
```python
import logging

logger = logging.getLogger(__name__)

try:
    result = operation()
except SemanticSQLError as e:
    logger.error(f"操作失败: {e}", exc_info=True)
    # 根据异常类型决定是否重试
    if isinstance(e, DatabaseConnectionError):
        # 可能需要重试
        return retry_operation()
    else:
        raise
```

### 4. 用户友好的错误处理
```python
def handle_user_query(query: str):
    try:
        return process_query(query)
    except ValidationError as e:
        return {"error": f"输入错误: {e}", "type": "validation"}
    except DatabaseConnectionError:
        return {"error": "数据库连接失败，请稍后重试", "type": "connection"}
    except GenerationError:
        return {"error": "无法理解您的查询，请换个方式描述", "type": "generation"}
    except SemanticSQLError as e:
        return {"error": f"处理失败: {e}", "type": "general"}
```

## 注意事项

1. **保留原始异常**：使用 `original_error` 参数保留原始异常信息
2. **提供上下文**：在异常消息中包含足够的上下文信息
3. **分类明确**：选择最合适的异常类，便于上层处理
4. **避免过度包装**：不要将所有异常都包装成自定义异常
5. **文档化异常**：在函数文档中说明可能抛出的异常