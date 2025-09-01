# TrajectoryRecorder API 文档

执行轨迹记录器，记录 Agent 的完整执行过程。

## 类定义

```python
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
from semanticsql_agent.utils.trajectory import TrajectoryRecorder

class TrajectoryRecorder:
    """
    执行轨迹记录器
    
    记录 Agent 执行的每个步骤，用于调试、分析和复现。
    
    Attributes:
        output_dir: 轨迹文件保存目录
        current_execution: 当前执行记录
    """
```

## 构造函数

```python
def __init__(self, output_dir: str = "./trajectories"):
    """
    初始化轨迹记录器
    
    Args:
        output_dir: 轨迹文件保存目录
    
    Example:
        ```python
        recorder = TrajectoryRecorder(output_dir="./logs/trajectories")
        ```
    """
```

## 核心方法

### start_execution

```python
def start_execution(
    self,
    task: str,
    agent_type: str,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    开始新的执行记录
    
    Args:
        task: 任务描述
        agent_type: Agent 类型
        metadata: 额外的元数据
    
    Returns:
        str: 执行 ID
    
    Example:
        ```python
        exec_id = recorder.start_execution(
            task="生成查询最近订单的SQL",
            agent_type="SQLAgent",
            metadata={"user": "admin", "session": "123"}
        )
        ```
    """
```

### add_step

```python
def add_step(
    self,
    step_type: str,
    tool_name: Optional[str],
    input_data: Dict[str, Any],
    output_data: Dict[str, Any],
    duration: float,
    error: Optional[str] = None
) -> None:
    """
    添加执行步骤
    
    Args:
        step_type: 步骤类型 (thought/action/observation)
        tool_name: 使用的工具名称
        input_data: 输入数据
        output_data: 输出数据
        duration: 执行时长（秒）
        error: 错误信息（如果有）
    
    Example:
        ```python
        recorder.add_step(
            step_type="action",
            tool_name="sql_generation",
            input_data={"question": "查询订单"},
            output_data={"sql": "SELECT * FROM orders"},
            duration=0.5
        )
        ```
    """
```

### end_execution

```python
def end_execution(
    self,
    success: bool,
    final_result: Any,
    error: Optional[str] = None
) -> str:
    """
    结束执行记录
    
    Args:
        success: 是否成功
        final_result: 最终结果
        error: 错误信息（如果失败）
    
    Returns:
        str: 保存的轨迹文件路径
    
    Example:
        ```python
        file_path = recorder.end_execution(
            success=True,
            final_result={"sql": "SELECT ...", "result": [...]}
        )
        ```
    """
```

### save_execution

```python
def save_execution(self, execution_id: Optional[str] = None) -> str:
    """
    保存执行轨迹到文件
    
    Args:
        execution_id: 指定的执行 ID（可选）
    
    Returns:
        str: 保存的文件路径
    """
```

### load_execution

```python
@staticmethod
def load_execution(file_path: str) -> Dict[str, Any]:
    """
    从文件加载执行轨迹
    
    Args:
        file_path: 轨迹文件路径
    
    Returns:
        Dict[str, Any]: 执行记录
    
    Example:
        ```python
        execution = TrajectoryRecorder.load_execution(
            "./trajectories/exec_20240115_123456.json"
        )
        
        print(f"Task: {execution['task']}")
        print(f"Steps: {len(execution['steps'])}")
        ```
    """
```

## 数据结构

### AgentExecution
```python
{
    "execution_id": "exec_20240115_123456",
    "task": "生成查询SQL",
    "agent_type": "SQLAgent",
    "start_time": "2024-01-15T12:34:56",
    "end_time": "2024-01-15T12:35:10",
    "duration": 14.5,
    "success": true,
    "steps": [...],
    "final_result": {...},
    "metadata": {...}
}
```

### AgentStep
```python
{
    "step_id": 1,
    "timestamp": "2024-01-15T12:34:57",
    "step_type": "action",
    "tool_name": "schema_extraction",
    "input": {...},
    "output": {...},
    "duration": 0.3,
    "error": null
}
```

## 查询和分析

### get_trajectories

```python
def get_trajectories(
    self,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    agent_type: Optional[str] = None,
    success_only: bool = False
) -> List[Dict[str, Any]]:
    """
    查询轨迹记录
    
    Args:
        start_date: 开始时间
        end_date: 结束时间
        agent_type: Agent 类型筛选
        success_only: 只返回成功的执行
    
    Returns:
        List[Dict[str, Any]]: 符合条件的执行记录列表
    """
```

### analyze_performance

```python
def analyze_performance(
    self,
    execution_ids: List[str]
) -> Dict[str, Any]:
    """
    分析执行性能
    
    Args:
        execution_ids: 要分析的执行 ID 列表
    
    Returns:
        Dict[str, Any]: 性能分析结果
    
    Return Format:
        ```python
        {
            "total_executions": 10,
            "success_rate": 0.9,
            "avg_duration": 12.5,
            "tool_usage": {
                "sql_generation": {"count": 10, "avg_time": 0.5},
                "sql_validation": {"count": 8, "avg_time": 0.3}
            },
            "error_distribution": {...}
        }
        ```
    """
```

## 可视化支持

```python
def export_to_timeline(
    self,
    execution_id: str,
    output_format: str = "html"
) -> str:
    """
    导出执行时间线
    
    Args:
        execution_id: 执行 ID
        output_format: 输出格式 (html/mermaid)
    
    Returns:
        str: 导出的内容或文件路径
    """
```

## 使用示例

### 基本使用
```python
# 创建记录器
recorder = TrajectoryRecorder()

# 记录执行过程
exec_id = recorder.start_execution(
    task="查询本月销售额",
    agent_type="SQLAgent"
)

# 记录步骤
recorder.add_step(
    step_type="thought",
    tool_name=None,
    input_data={"thought": "需要先分析数据库结构"},
    output_data={"decision": "调用 schema_extraction"},
    duration=0.1
)

# 结束记录
file_path = recorder.end_execution(
    success=True,
    final_result={"sql": "SELECT SUM(amount) FROM orders WHERE ..."}
)
```

### 分析使用
```python
# 查询最近的执行
recent_trajectories = recorder.get_trajectories(
    start_date=datetime.now() - timedelta(days=1),
    success_only=True
)

# 分析性能
performance = recorder.analyze_performance(
    [t["execution_id"] for t in recent_trajectories]
)

print(f"Success rate: {performance['success_rate']:.2%}")
print(f"Average duration: {performance['avg_duration']:.2f}s")
```

## 注意事项

1. 轨迹文件以 JSON 格式保存
2. 支持大文件的流式写入
3. 自动清理旧的轨迹文件
4. 可用于调试和性能优化

---

相关文档：
- [BaseAgent API](../../agent模块/BaseAgent-API.md)
- [回调系统 API](../CallbackHandler-API.md)