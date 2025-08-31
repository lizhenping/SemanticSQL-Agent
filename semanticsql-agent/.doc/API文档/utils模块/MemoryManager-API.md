# MemoryManager API 文档

记忆管理器，管理数据库分析结果的存储和检索。

## 类定义

```python
from langchain.memory import BaseMemory
from typing import Dict, Any, List, Optional
from semanticsql_agent.utils.memory import DatabaseAnalysisMemory

class DatabaseAnalysisMemory(BaseMemory):
    """
    数据库分析记忆管理
    
    继承自 LangChain BaseMemory，存储和管理数据库分析结果。
    
    Attributes:
        memory_key: 记忆键名
        storage: 内部存储字典
    """
```

## 构造函数

```python
def __init__(self, memory_key: str = "db_analysis"):
    """
    初始化记忆管理器
    
    Args:
        memory_key: 记忆在上下文中的键名
    
    Example:
        ```python
        memory = DatabaseAnalysisMemory()
        ```
    """
```

## 核心方法

### save_context

```python
def save_context(
    self,
    inputs: Dict[str, Any],
    outputs: Dict[str, Any]
) -> None:
    """
    保存分析结果到记忆
    
    Args:
        inputs: 输入信息（如工具名称）
        outputs: 分析结果
    
    Example:
        ```python
        memory.save_context(
            inputs={"tool": "schema_extraction"},
            outputs={
                "tables": ["orders", "customers"],
                "columns": {...}
            }
        )
        ```
    """
```

### load_memory_variables

```python
def load_memory_variables(
    self,
    inputs: Dict[str, Any]
) -> Dict[str, Any]:
    """
    加载记忆变量
    
    Args:
        inputs: 当前输入（用于过滤相关记忆）
    
    Returns:
        Dict[str, Any]: 记忆内容
    
    Example:
        ```python
        # 加载所有记忆
        memory_data = memory.load_memory_variables({})
        
        # 获取特定分析结果
        schema = memory_data["db_analysis"]["schema_info"]
        ```
    """
```

### update_analysis

```python
def update_analysis(
    self,
    analysis_type: str,
    data: Dict[str, Any],
    merge: bool = False
) -> None:
    """
    更新特定类型的分析结果
    
    Args:
        analysis_type: 分析类型
        data: 新的分析数据
        merge: 是否合并（True）或替换（False）
    
    Analysis Types:
        - schema_info: 数据库结构
        - domain_analysis: 领域分析
        - field_classification: 字段分类
        - column_meanings: 列含义
        - table_meanings: 表含义
        - er_analysis: 关系分析
    
    Example:
        ```python
        # 更新列含义分析
        memory.update_analysis(
            "column_meanings",
            {
                "orders.total_amount": {
                    "business_meaning": "订单总金额",
                    "calculation_logic": "商品总价 + 运费"
                }
            },
            merge=True
        )
        ```
    """
```

### get_analysis

```python
def get_analysis(
    self,
    analysis_type: str,
    default: Any = None
) -> Any:
    """
    获取特定类型的分析结果
    
    Args:
        analysis_type: 分析类型
        default: 默认值
    
    Returns:
        Any: 分析结果
    
    Example:
        ```python
        # 获取表含义
        table_meanings = memory.get_analysis("table_meanings")
        
        # 获取特定表的信息
        orders_meaning = table_meanings.get("orders", {})
        ```
    """
```

### clear

```python
def clear(self, analysis_types: Optional[List[str]] = None) -> None:
    """
    清除记忆
    
    Args:
        analysis_types: 要清除的分析类型列表，None 表示清除全部
    
    Example:
        ```python
        # 清除所有记忆
        memory.clear()
        
        # 只清除特定类型
        memory.clear(["column_meanings", "table_meanings"])
        ```
    """
```

## 记忆结构

```python
{
    "schema_info": {
        "database": "ecommerce",
        "tables": {...},
        "relationships": [...]
    },
    "domain_analysis": {
        "domain": "电商",
        "sub_domains": ["订单管理", "库存管理"],
        "key_entities": ["订单", "产品", "客户"]
    },
    "field_classification": {
        "classifications": {...},
        "field_types": {...}
    },
    "column_meanings": {
        "table.column": {
            "business_meaning": "...",
            "usage_scenarios": [...]
        }
    },
    "table_meanings": {
        "table_name": {
            "business_purpose": "...",
            "key_operations": [...]
        }
    },
    "er_analysis": {
        "relationships": [...],
        "entities": {...}
    }
}
```

## 高级功能

### 记忆持久化

```python
def save_to_file(self, file_path: str) -> None:
    """
    保存记忆到文件
    
    Args:
        file_path: 文件路径
    """

def load_from_file(self, file_path: str) -> None:
    """
    从文件加载记忆
    
    Args:
        file_path: 文件路径
    """
```

### 记忆压缩

```python
def compress_memory(
    self,
    keep_essential: bool = True
) -> Dict[str, Any]:
    """
    压缩记忆，保留关键信息
    
    Args:
        keep_essential: 是否保留基本信息
    
    Returns:
        Dict[str, Any]: 压缩后的记忆
    """
```

## 与 LangChain 集成

```python
# 在 Agent 中使用
from langchain.agents import AgentExecutor

memory = DatabaseAnalysisMemory()
agent = AgentExecutor(
    agent=agent,
    tools=tools,
    memory=memory,
    verbose=True
)

# 记忆会自动在工具调用间传递
result = agent.run("查询最近的订单")
```

## 使用示例

### 基本使用
```python
# 创建记忆管理器
memory = DatabaseAnalysisMemory()

# 保存分析结果
memory.update_analysis(
    "schema_info",
    {
        "tables": ["orders", "customers", "products"],
        "total_tables": 3
    }
)

# 获取分析结果
schema = memory.get_analysis("schema_info")
print(f"Tables: {schema['tables']}")
```

### 高级使用
```python
# 增量更新
memory.update_analysis(
    "column_meanings",
    {"orders.status": {"meaning": "订单状态"}},
    merge=True
)

# 持久化
memory.save_to_file("db_analysis.json")

# 恢复
new_memory = DatabaseAnalysisMemory()
new_memory.load_from_file("db_analysis.json")
```

## 注意事项

1. 记忆在 Agent 执行期间自动维护
2. 支持增量更新和完全替换
3. 可以持久化到文件
4. 与 LangChain 记忆系统兼容

---

相关文档：
- [SQLAgent API](../../agent模块/SQLAgent-API.md)
- [分析工具文档](../../tools模块/分析工具/)