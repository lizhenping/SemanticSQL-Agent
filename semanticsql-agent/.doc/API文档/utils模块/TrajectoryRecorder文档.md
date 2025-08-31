# TrajectoryRecorder API 文档

## 概述
`TrajectoryRecorder` 是用于记录和管理智能体执行轨迹的工具类。它可以保存、加载和分析智能体的执行历史，用于调试、分析和优化。

## 类定义
```python
class TrajectoryRecorder:
    """轨迹记录系统"""
```

## 构造函数
```python
def __init__(self, output_dir: str = "trajectories", max_trajectories: int = 100)
```

**参数：**
- `output_dir` (str): 轨迹文件输出目录
- `max_trajectories` (int): 最大保留轨迹数量

**初始化操作：**
- 创建输出目录（如果不存在）
- 设置日志记录器

## 主要方法

### `save_execution(execution: AgentExecution) -> str`
保存执行轨迹到文件。

**参数：**
- `execution` (AgentExecution): 执行记录对象

**返回：**
- `str`: 保存的文件路径

**文件命名格式：**
`execution_YYYYMMDD_HHMMSS_TASKID.json`

**保存的数据结构：**
```json
{
    "task_id": "uuid",
    "task": "任务描述",
    "started_at": "2024-01-01T10:00:00",
    "completed_at": "2024-01-01T10:05:00",
    "status": "completed",
    "final_result": {...},
    "error": null,
    "metadata": {...},
    "steps": [
        {
            "step_type": "thought",
            "content": "步骤内容",
            "timestamp": "2024-01-01T10:00:01",
            "tool_name": "tool_name",
            "tool_input": {...},
            "tool_output": {...},
            "error": null,
            "duration_ms": 100
        }
    ],
    "summary": {
        "task_id": "uuid",
        "task": "任务描述",
        "status": "completed",
        "total_steps": 10,
        "duration": 300.5,
        "tools_used": ["tool1", "tool2"],
        "error": null
    }
}
```

### `load_execution(filepath: str) -> Optional[AgentExecution]`
从文件加载执行轨迹。

**参数：**
- `filepath` (str): 轨迹文件路径

**返回：**
- `Optional[AgentExecution]`: 执行记录对象，加载失败返回 None

### `get_trajectories(limit: Optional[int] = None) -> List[str]`
获取轨迹文件路径列表。

**参数：**
- `limit` (Optional[int]): 返回的最大数量

**返回：**
- `List[str]`: 轨迹文件路径列表

### `get_trajectory_summary(filepath: str) -> Optional[Dict[str, Any]]`
获取轨迹摘要信息。

**参数：**
- `filepath` (str): 轨迹文件路径

**返回：**
- `Optional[Dict[str, Any]]`: 轨迹摘要，失败返回 None

### `export_trajectories(output_file: str, format: str = "json") -> bool`
导出轨迹数据。

**参数：**
- `output_file` (str): 输出文件路径
- `format` (str): 导出格式（目前仅支持 "json"）

**返回：**
- `bool`: 导出是否成功

## 内部方法

### `_serialize_tool_output(output: Any) -> Any`
序列化工具输出。

**功能：**
- 处理不可序列化的对象
- 转换日期时间为 ISO 格式
- 限制大对象的大小

### `_cleanup_old_trajectories() -> None`
自动清理超过最大数量限制的旧轨迹。

**策略：**
- 按时间排序
- 保留最新的 `max_trajectories` 个文件
- 删除多余的旧文件

## 使用示例

### 基本使用
```python
from utils.trajectory import TrajectoryRecorder
from models.schemas import AgentExecution

# 创建记录器
recorder = TrajectoryRecorder(
    output_dir="./trajectories",
    max_trajectories=100
)

# 保存执行轨迹
execution = AgentExecution(task="查询销售数据")
# ... 执行过程 ...
filepath = recorder.save_execution(execution)
print(f"轨迹已保存到: {filepath}")

# 加载轨迹
loaded_execution = recorder.load_execution(filepath)
if loaded_execution:
    print(f"任务: {loaded_execution.task}")
    print(f"步骤数: {len(loaded_execution.steps)}")
```

### 轨迹分析
```python
# 获取轨迹列表
trajectories = recorder.get_trajectories(limit=10)
print(f"最近 {len(trajectories)} 个轨迹")

# 查看轨迹摘要
for filepath in trajectories[:5]:
    summary = recorder.get_trajectory_summary(filepath)
    if summary:
        print(f"任务: {summary.get('task', 'N/A')}")
        print(f"状态: {summary.get('status', 'N/A')}")

# 导出轨迹
success = recorder.export_trajectories("all_trajectories.json")
if success:
    print("轨迹导出成功")
```



### 轨迹回放
```python
# 加载并回放执行过程
execution = recorder.load_execution("execution_20240101_100000_12345678.json")

if execution:
    print(f"任务: {execution.task}")
    print(f"开始时间: {execution.started_at}")
    
    # 逐步回放
    for i, step in enumerate(execution.steps):
        print(f"\n步骤 {i+1}: {step.step_type.value}")
        print(f"内容: {step.content[:100]}...")
        
        if step.tool_name:
            print(f"工具: {step.tool_name}")
            print(f"耗时: {step.duration_ms}ms")
        
        if step.error:
            print(f"错误: {step.error}")
    
    print(f"\n最终状态: {execution.status}")
    if execution.final_result:
        print(f"结果: {execution.final_result}")
```

### 轨迹对比
```python
# 对比两个执行轨迹
def compare_executions(filepath1: str, filepath2: str):
    exec1 = recorder.load_execution(filepath1)
    exec2 = recorder.load_execution(filepath2)
    
    if exec1 and exec2:
        print(f"执行1: {exec1.task}")
        print(f"  步骤数: {len(exec1.steps)}")
        print(f"  耗时: {exec1.get_duration()}秒")
        print(f"  状态: {exec1.status}")
        
        print(f"\n执行2: {exec2.task}")
        print(f"  步骤数: {len(exec2.steps)}")
        print(f"  耗时: {exec2.get_duration()}秒")
        print(f"  状态: {exec2.status}")
        
        # 比较工具使用
        tools1 = set(s.tool_name for s in exec1.steps if s.tool_name)
        tools2 = set(s.tool_name for s in exec2.steps if s.tool_name)
        
        print(f"\n共同使用的工具: {tools1 & tools2}")
        print(f"仅执行1使用: {tools1 - tools2}")
        print(f"仅执行2使用: {tools2 - tools1}")
```

## 配置建议

### 存储策略
```python
# 开发环境：保留更多轨迹用于调试
dev_recorder = TrajectoryRecorder(
    output_dir="./dev_trajectories",
    max_trajectories=1000
)

# 生产环境：限制存储空间
prod_recorder = TrajectoryRecorder(
    output_dir="./prod_trajectories",
    max_trajectories=50
)
```



## 性能考虑

1. **文件大小**
   - 大型执行可能产生较大的轨迹文件
   - 考虑压缩或分片存储

2. **I/O 操作**
   - 保存操作是同步的，可能影响性能
   - 考虑异步保存或后台任务

3. **内存使用**
   - 加载大型轨迹可能消耗较多内存
   - 考虑流式读取或分页加载

## 注意事项

1. 轨迹文件包含执行的完整信息，注意数据安全
2. 定期清理旧轨迹，避免磁盘空间不足
3. 轨迹文件使用 JSON 格式，便于分析但可能较大
4. 工具输出可能包含敏感信息，注意脱敏
5. 时间戳使用 ISO 格式，便于跨时区使用