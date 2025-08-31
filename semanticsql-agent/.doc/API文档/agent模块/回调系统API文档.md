# 回调系统 API 文档

## 概述
回调系统提供了一种灵活的方式来监控和记录智能体的执行过程。通过回调机制，可以在执行的各个阶段插入自定义逻辑，用于日志记录、性能监控、轨迹保存等。

## ExecutionCallback 基类

### 类定义
```python
class ExecutionCallback:
    """执行回调的基类"""
```

### 回调方法

#### `on_execution_start(self, execution: AgentExecution) -> None`
在执行开始时调用。

**参数：**
- `execution` (AgentExecution): 执行记录对象

#### `on_execution_complete(self, execution: AgentExecution) -> None`
在执行完成时调用。

**参数：**
- `execution` (AgentExecution): 包含完整执行历史的执行记录对象

#### `on_step_start(self, execution: AgentExecution, step: AgentStep) -> None`
在步骤开始时调用。

**参数：**
- `execution` (AgentExecution): 当前执行记录
- `step` (AgentStep): 即将开始的步骤

#### `on_step_complete(self, execution: AgentExecution, step: AgentStep) -> None`
在步骤完成时调用。

**参数：**
- `execution` (AgentExecution): 当前执行记录
- `step` (AgentStep): 已完成的步骤

#### `on_tool_call(self, execution: AgentExecution, tool_name: str, tool_input: Dict[str, Any], tool_output: Dict[str, Any]) -> None`
在工具调用时调用。

**参数：**
- `execution` (AgentExecution): 当前执行记录
- `tool_name` (str): 工具名称
- `tool_input` (Dict[str, Any]): 工具输入参数
- `tool_output` (Dict[str, Any]): 工具输出结果

#### `on_error(self, execution: AgentExecution, error: Exception) -> None`
在发生错误时调用。

**参数：**
- `execution` (AgentExecution): 当前执行记录
- `error` (Exception): 发生的异常

## TrajectoryCallback 类

### 类定义
```python
class TrajectoryCallback(ExecutionCallback):
    """用于记录执行轨迹的回调"""
```

### 构造函数
```python
def __init__(self, trajectory_recorder: TrajectoryRecorder)
```

**参数：**
- `trajectory_recorder` (TrajectoryRecorder): 轨迹记录器实例

### 功能特性
- 记录任务开始和完成
- 保存完整执行轨迹到文件
- 记录每个步骤的完成情况
- 跟踪工具调用的成功/失败状态
- 记录执行过程中的错误

### 日志级别
- INFO: 任务开始、完成、工具调用状态
- DEBUG: 步骤完成详情
- WARNING: 工具调用错误
- ERROR: 执行错误、轨迹保存失败

## LoggingCallback 类

### 类定义
```python
class LoggingCallback(ExecutionCallback):
    """详细日志记录回调"""
```

### 构造函数
```python
def __init__(self, log_level: str = "INFO")
```

**参数：**
- `log_level` (str): 日志级别（默认 "INFO"）

### 功能特性
- 提供比 TrajectoryCallback 更详细的日志
- 记录步骤内容的更多细节
- 格式化输出工具调用参数和结果
- 支持自定义日志级别

### 日志格式
```
[EXECUTION START] Task: {task}
[STEP] {step_type}: {content}
[TOOL CALL] {tool_name}
  Input: {formatted_input}
  Output: {formatted_output}
[EXECUTION COMPLETE] Duration: {duration}s
```

## MetricsCallback 类

### 类定义
```python
class MetricsCallback(ExecutionCallback):
    """性能指标收集回调"""
```

### 构造函数
```python
def __init__(self)
```

### 收集的指标
- 执行总时长
- 各类型步骤的数量统计
- 工具调用次数和成功率
- 每个工具的平均执行时间
- 错误发生次数

### 获取指标
```python
def get_metrics(self) -> Dict[str, Any]
```

**返回的指标结构：**
```python
{
    "total_executions": int,
    "total_duration": float,
    "average_duration": float,
    "step_counts": {
        "thinking": int,
        "action": int,
        "observation": int,
        ...
    },
    "tool_metrics": {
        "tool_name": {
            "calls": int,
            "successes": int,
            "failures": int,
            "average_duration": float
        },
        ...
    },
    "error_count": int
}
```

## 使用示例

### 基本使用
```python
from agent.callbacks import TrajectoryCallback, LoggingCallback, MetricsCallback
from utils.trajectory import TrajectoryRecorder

# 创建智能体
agent = SmartSQLAgent(settings, db_config)

# 添加轨迹记录回调
trajectory_recorder = TrajectoryRecorder("./trajectories")
agent.add_callback(TrajectoryCallback(trajectory_recorder))

# 添加详细日志回调
agent.add_callback(LoggingCallback(log_level="DEBUG"))

# 添加性能监控回调
metrics_callback = MetricsCallback()
agent.add_callback(metrics_callback)

# 执行任务
result = agent.new_task("查询销售数据")

# 获取性能指标
metrics = metrics_callback.get_metrics()
print(f"执行时间: {metrics['average_duration']}秒")
```

### 自定义回调
```python
class CustomCallback(ExecutionCallback):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    def on_execution_complete(self, execution: AgentExecution):
        # 发送执行结果到 webhook
        import requests
        data = {
            "task": execution.task,
            "success": execution.success,
            "duration": execution.total_duration,
            "steps": len(execution.steps)
        }
        requests.post(self.webhook_url, json=data)
    
    def on_error(self, execution: AgentExecution, error: Exception):
        # 发送错误通知
        import requests
        data = {
            "task": execution.task,
            "error": str(error),
            "timestamp": datetime.now().isoformat()
        }
        requests.post(f"{self.webhook_url}/errors", json=data)

# 使用自定义回调
agent.add_callback(CustomCallback("https://api.example.com/webhook"))
```

## 最佳实践

1. **组合使用多个回调**
   - TrajectoryCallback 用于持久化存储
   - LoggingCallback 用于实时监控
   - MetricsCallback 用于性能分析

2. **避免阻塞操作**
   - 回调方法应该快速返回
   - 耗时操作应该异步处理

3. **错误处理**
   - 回调中的错误不应影响主流程
   - 使用 try-except 保护回调逻辑

4. **性能考虑**
   - 大量日志可能影响性能
   - 生产环境适当调整日志级别

## 注意事项

1. 回调按注册顺序依次执行
2. 回调异常会被捕获并记录，不会中断执行
3. 某些回调可能产生大量输出，注意磁盘空间
4. MetricsCallback 会在内存中保存所有指标数据