# BaseTool 基类 API 文档

## 概述
`BaseTool` 是所有工具的抽象基类，定义了工具的标准接口和行为。所有具体工具都必须继承此类并实现相应的抽象方法。

## 类定义
```python
class BaseTool(ABC):
    """工具基类 - 符合架构规范"""
```

## 构造函数
```python
def __init__(self, config: Any = None)
```

**参数：**
- `config` (Any): 配置对象，可选

**初始化内容：**
- 日志记录器
- 执行统计计数器
- 错误计数器
- 总执行时长

## 抽象属性和方法（子类必须实现）

### `name` (property)
工具的唯一标识符。

```python
@property
@abstractmethod
def name(self) -> str:
    """工具唯一标识，用于注册和调用"""
    pass
```

### `description` (property)
工具功能描述。

```python
@property
@abstractmethod
def description(self) -> str:
    """工具功能描述，用于LLM理解"""
    pass
```

### `_execute(**kwargs) -> Any`
实际执行逻辑。

```python
@abstractmethod
def _execute(self, **kwargs) -> Any:
    """
    实际执行逻辑，子类必须实现
    
    Returns:
        执行结果数据
    """
    pass
```

## 可选属性

### `category` (property)
工具类别。

```python
@property
def category(self) -> str:
    """工具类别：analysis/generation/validation/reflection"""
    return "general"
```

**可选值：**
- `"analysis"`: 分析工具
- `"generation"`: 生成工具
- `"validation"`: 验证工具
- `"reflection"`: 反思工具
- `"general"`: 通用工具（默认）

### `parameters` (property)
工具参数定义。

```python
@property
def parameters(self) -> List[ToolParameter]:
    """定义工具参数"""
    return []
```

返回 `ToolParameter` 对象列表，定义工具接受的参数。

## 公共方法

### `run(**kwargs) -> Dict[str, Any]`
工具执行接口，提供标准化的返回格式。

**参数：**
- `**kwargs`: 工具执行参数

**返回格式：**
```python
{
    "success": bool,      # 执行是否成功
    "data": Any,         # 成功时的返回数据
    "error": str,        # 失败时的错误信息
    "metadata": dict     # 可选的元数据
}
```

**执行流程：**
1. 记录开始时间
2. 验证参数
3. 调用 `_execute()` 方法
4. 计算执行时间
5. 构造标准返回格式
6. 处理异常情况

### `get_parameter_schema() -> Dict[str, Any]`
获取工具参数的 JSON Schema。

**返回：**
符合 JSON Schema 规范的参数定义。

**示例返回：**
```json
{
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "查询语句"
        },
        "limit": {
            "type": "integer",
            "description": "返回结果数量限制",
            "default": 10
        }
    },
    "required": ["query"]
}
```

### `get_stats() -> Dict[str, Any]`
获取工具执行统计信息。

**返回：**
```python
{
    "execution_count": int,      # 总执行次数
    "error_count": int,          # 错误次数
    "success_rate": float,       # 成功率
    "average_duration_ms": float # 平均执行时间（毫秒）
}
```

### `reset_stats() -> None`
重置执行统计信息。

## 内部方法

### `_validate_parameters(kwargs: Dict[str, Any]) -> None`
验证输入参数。

**验证内容：**
1. 检查必需参数是否存在
2. 验证参数类型
3. 检查枚举值约束

**异常：**
- `ToolExecutionError`: 参数验证失败时抛出

### `_format_error(error: Exception) -> str`
格式化错误信息。

**参数：**
- `error` (Exception): 异常对象

**返回：**
- `str`: 格式化的错误信息

## ToolParameter 数据类

```python
@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str                              # 参数名称
    type: str                              # 参数类型
    description: str                       # 参数描述
    required: bool = True                  # 是否必需
    default: Any = None                    # 默认值
    enum: Optional[List[str]] = None       # 枚举值列表
```

**支持的类型：**
- `"string"`: 字符串
- `"integer"`: 整数
- `"number"`: 数字（浮点数）
- `"boolean"`: 布尔值
- `"object"`: 对象
- `"array"`: 数组

## 实现示例

```python
from tools.base_tool import BaseTool, ToolParameter
from typing import List, Any

class MySQLTool(BaseTool):
    """自定义 SQL 工具示例"""
    
    @property
    def name(self) -> str:
        return "my_sql_tool"
    
    @property
    def description(self) -> str:
        return "执行自定义 SQL 分析"
    
    @property
    def category(self) -> str:
        return "analysis"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="sql",
                type="string",
                description="要执行的 SQL 查询",
                required=True
            ),
            ToolParameter(
                name="database",
                type="string",
                description="目标数据库",
                required=True
            ),
            ToolParameter(
                name="limit",
                type="integer",
                description="结果数量限制",
                required=False,
                default=100
            ),
            ToolParameter(
                name="format",
                type="string",
                description="输出格式",
                required=False,
                default="json",
                enum=["json", "csv", "table"]
            )
        ]
    
    def _execute(self, sql: str, database: str, limit: int = 100, 
                 format: str = "json") -> Any:
        """执行 SQL 查询"""
        # 实现具体的执行逻辑
        try:
            # 连接数据库
            conn = self.get_connection(database)
            
            # 执行查询
            results = conn.execute(sql, limit=limit)
            
            # 格式化结果
            if format == "json":
                return results.to_dict()
            elif format == "csv":
                return results.to_csv()
            else:
                return results.to_table()
                
        except Exception as e:
            self.logger.error(f"SQL执行失败: {e}")
            raise
```

## 使用示例

```python
# 创建工具实例
tool = MySQLTool(config=settings)

# 执行工具
result = tool.run(
    sql="SELECT * FROM users WHERE created_at > '2024-01-01'",
    database="main_db",
    limit=50,
    format="json"
)

# 检查结果
if result["success"]:
    data = result["data"]
    print(f"查询返回 {len(data)} 条记录")
else:
    print(f"执行失败: {result['error']}")

# 获取执行统计
stats = tool.get_stats()
print(f"执行次数: {stats['execution_count']}")
print(f"成功率: {stats['success_rate']}%")
```

## 最佳实践

1. **参数验证**
   - 使用 `parameters` 属性定义所有参数
   - 利用基类的自动参数验证功能

2. **错误处理**
   - 在 `_execute` 中抛出明确的异常
   - 基类会自动捕获并格式化错误

3. **日志记录**
   - 使用 `self.logger` 记录重要信息
   - 遵循适当的日志级别

4. **性能监控**
   - 利用内置的统计功能
   - 定期检查执行性能

5. **文档编写**
   - 提供清晰的 `description`
   - 参数描述要准确详细

## 注意事项

1. 工具名称必须唯一
2. 参数类型必须是支持的类型之一
3. 执行时间会自动记录
4. 异常会被自动捕获并记录
5. 返回格式必须遵循标准结构