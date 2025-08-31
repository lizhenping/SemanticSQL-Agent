# 记忆管理 API 文档

基于 LangChain Memory 的数据库分析结果记忆管理系统。

## 核心类

### DatabaseAnalysisMemory

```python
from langchain.memory import BaseMemory
from typing import List, Dict, Any, Optional

class DatabaseAnalysisMemory(BaseMemory):
    """
    专门管理数据库分析结果的记忆系统
    
    继承自 LangChain BaseMemory，存储和管理六种分析结果：
    - schema_info: 数据库结构信息
    - domain_analysis: 业务领域分析
    - field_classification: 字段语义分类
    - column_meanings: 列业务含义
    - table_meanings: 表业务含义
    - er_analysis: 实体关系分析
    
    Attributes:
        memory_key: 记忆变量名称
        analysis_results: 存储分析结果的字典
        max_memory_size: 最大记忆大小（MB）
    """
```

## 构造函数

```python
def __init__(
    self,
    memory_key: str = "db_analysis",
    max_memory_size: int = 100,
    persist_path: Optional[str] = None
):
    """
    初始化记忆管理器
    
    Args:
        memory_key: 在 LLM 上下文中的变量名
        max_memory_size: 最大记忆大小（MB）
        persist_path: 持久化路径（可选）
    
    Example:
        ```python
        memory = DatabaseAnalysisMemory(
            memory_key="database_memory",
            max_memory_size=200,
            persist_path="./memory_cache.json"
        )
        ```
    """
```

## 核心方法

### load_memory_variables

```python
def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    加载记忆变量供 LLM 使用
    
    LangChain 会在每次 LLM 调用前调用此方法。
    
    Args:
        inputs: 当前输入（包含任务上下文）
    
    Returns:
        Dict[str, Any]: 包含记忆内容的字典
    
    Example:
        ```python
        variables = memory.load_memory_variables({"task": "generate SQL"})
        # variables = {
        #     "db_analysis": {
        #         "schema": {...},
        #         "domain": "e-commerce",
        #         "has_analysis": True
        #     }
        # }
        ```
    """
```

### save_context

```python
def save_context(
    self,
    inputs: Dict[str, Any],
    outputs: Dict[str, Any]
) -> None:
    """
    保存执行上下文到记忆
    
    LangChain 在工具执行后自动调用此方法。
    
    Args:
        inputs: 工具输入
        outputs: 工具输出
    
    Example:
        ```python
        # 自动保存 schema_extraction 的结果
        memory.save_context(
            inputs={"tool": "extract_schema", "database": "mydb"},
            outputs={"data": {"tables": [...], "columns": [...]}}
        )
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
    手动更新特定的分析结果
    
    Args:
        analysis_type: 分析类型（如 'schema_info'）
        data: 分析数据
        merge: 是否合并到现有数据
    
    Raises:
        ValueError: 无效的分析类型
    
    Example:
        ```python
        # 更新 schema 信息
        memory.update_analysis(
            'schema_info',
            {'tables': new_tables},
            merge=True
        )
        ```
    """
```

### get_analysis

```python
def get_analysis(self, analysis_type: str) -> Optional[Dict[str, Any]]:
    """
    获取特定的分析结果
    
    Args:
        analysis_type: 分析类型
    
    Returns:
        Optional[Dict[str, Any]]: 分析结果或 None
    
    Example:
        ```python
        schema = memory.get_analysis('schema_info')
        if schema:
            print(f"Tables: {len(schema['tables'])}")
        ```
    """
```

### clear

```python
def clear(self, analysis_types: Optional[List[str]] = None) -> None:
    """
    清空记忆
    
    Args:
        analysis_types: 要清空的分析类型列表，None 表示全部
    
    Example:
        ```python
        # 清空所有记忆
        memory.clear()
        
        # 只清空特定类型
        memory.clear(['schema_info', 'domain_analysis'])
        ```
    """
```

### get_summary

```python
def get_summary(self) -> Dict[str, Any]:
    """
    获取记忆摘要
    
    Returns:
        Dict[str, Any]: 包含各类分析的摘要信息
    
    Example:
        ```python
        summary = memory.get_summary()
        # {
        #     "total_tables": 10,
        #     "domain": "e-commerce",
        #     "analyzed_components": ["schema", "domain", "fields"],
        #     "memory_usage_mb": 2.5
        # }
        ```
    """
```

## 持久化方法

### save_to_file

```python
def save_to_file(self, filepath: str) -> None:
    """
    保存记忆到文件
    
    Args:
        filepath: 文件路径（JSON 格式）
    
    Example:
        ```python
        memory.save_to_file("database_analysis.json")
        ```
    """
```

### load_from_file

```python
def load_from_file(self, filepath: str) -> None:
    """
    从文件加载记忆
    
    Args:
        filepath: 文件路径
    
    Raises:
        FileNotFoundError: 文件不存在
        JSONDecodeError: 文件格式错误
    
    Example:
        ```python
        memory.load_from_file("database_analysis.json")
        ```
    """
```

## 内存管理

### check_memory_usage

```python
def check_memory_usage(self) -> float:
    """
    检查当前记忆使用量
    
    Returns:
        float: 使用的内存大小（MB）
    """
```

### compress_memory

```python
def compress_memory(self) -> None:
    """
    压缩记忆内容
    
    移除冗余数据，保留关键信息。
    """
```

## 集成示例

### 与 Agent 集成

```python
from langchain.agents import AgentExecutor

# 创建记忆
memory = DatabaseAnalysisMemory()

# 创建 Agent
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    memory=memory,
    verbose=True
)

# 执行任务（记忆自动管理）
result = agent_executor.run("分析数据库并生成报告")
```

### 手动管理记忆

```python
# 创建记忆管理器
memory = DatabaseAnalysisMemory(persist_path="./cache/")

# 手动更新分析结果
memory.update_analysis('schema_info', {
    'tables': ['users', 'orders', 'products'],
    'total_columns': 45,
    'constraints': {...}
})

# 检查记忆状态
summary = memory.get_summary()
print(f"Memory usage: {summary['memory_usage_mb']} MB")

# 保存到文件
memory.save_to_file("analysis_backup.json")
```

### 自定义记忆策略

```python
class SmartDatabaseMemory(DatabaseAnalysisMemory):
    """带智能清理的记忆管理器"""
    
    def save_context(self, inputs, outputs):
        # 检查内存使用
        if self.check_memory_usage() > self.max_memory_size * 0.8:
            self.compress_memory()
        
        # 正常保存
        super().save_context(inputs, outputs)
    
    def compress_memory(self):
        # 只保留关键信息
        for key in self.analysis_results:
            if self.analysis_results[key]:
                # 移除详细数据，保留摘要
                self.analysis_results[key] = self._extract_summary(
                    self.analysis_results[key]
                )
```

## 配置选项

### 记忆变量配置

```python
# 定义哪些分析结果包含在 LLM 上下文中
class SelectiveMemory(DatabaseAnalysisMemory):
    @property
    def memory_variables(self) -> List[str]:
        # 只返回核心信息
        return ["schema_summary", "domain_info"]
    
    def load_memory_variables(self, inputs):
        # 根据任务类型返回不同的记忆内容
        if "generate_sql" in str(inputs.get("task", "")):
            return {
                "schema_summary": self._get_schema_summary(),
                "domain_info": self.analysis_results.get("domain_analysis")
            }
        return {}
```

### 持久化配置

```python
# 自动持久化
memory = DatabaseAnalysisMemory(
    persist_path="./memory_cache.json",
    auto_persist=True,  # 每次更新自动保存
    persist_interval=10  # 每10次更新保存一次
)
```

## 最佳实践

1. **定期清理**：避免记忆无限增长
2. **选择性加载**：只在 LLM 上下文中包含必要信息
3. **压缩策略**：对大型分析结果进行摘要
4. **持久化**：重要分析结果及时保存
5. **版本控制**：为不同数据库维护独立记忆

## 故障排查

### 记忆未生效

```python
# 检查记忆是否正确加载
variables = memory.load_memory_variables({})
print(f"Loaded variables: {variables}")

# 检查工具是否正确保存
memory.save_context(
    {"tool": "extract_schema"},
    {"data": schema_data}
)
print(f"Schema saved: {memory.get_analysis('schema_info') is not None}")
```

### 内存溢出

```python
# 监控内存使用
usage = memory.check_memory_usage()
if usage > 50:  # MB
    print("Warning: High memory usage")
    memory.compress_memory()
    # 或清理旧数据
    memory.clear(['er_analysis'])  # 清理最大的分析结果
```

## 注意事项

1. 记忆内容会包含在每次 LLM 调用中，注意大小
2. 分析结果的键名必须匹配预定义的类型
3. 持久化文件可能包含敏感信息，注意安全
4. 大型数据库的分析结果可能很大，考虑压缩
5. 多个 Agent 共享记忆时注意同步问题

---

相关文档：
- [BaseAgent API](./BaseAgent-API.md)
- [LangChain Memory 文档](https://docs.langchain.com/docs/modules/memory/)
- [工具系统 API](../tools模块/)