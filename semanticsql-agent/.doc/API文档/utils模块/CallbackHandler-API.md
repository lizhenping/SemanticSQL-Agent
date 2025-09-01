# CallbackHandler API 文档

执行回调处理器，提供执行过程的钩子函数。

## 类定义

```python
from langchain.callbacks.base import BaseCallbackHandler
from typing import Dict, Any, List, Optional
from semanticsql_agent.utils.callbacks import (
    TrajectoryCallback,
    ProgressCallback,
    PerformanceCallback
)
```

## 基础回调类

### TrajectoryCallback

```python
class TrajectoryCallback(BaseCallbackHandler):
    """
    轨迹记录回调
    
    记录 Agent 执行的每个步骤，与 TrajectoryRecorder 配合使用。
    
    实现的 LangChain 回调方法：
    - on_agent_action: 记录 Agent 动作
    - on_agent_finish: 记录 Agent 完成
    - on_tool_start: 记录工具开始
    - on_tool_end: 记录工具结果
    - on_tool_error: 记录工具错误
    - on_llm_start: 记录 LLM 调用
    - on_llm_end: 记录 LLM 响应
    
    Attributes:
        recorder: TrajectoryRecorder 实例
        current_step: 当前步骤信息
    """
    
    def __init__(self, recorder: TrajectoryRecorder):
        """
        初始化轨迹回调
        
        Args:
            recorder: 轨迹记录器实例
        """
```

#### 核心方法

```python
def on_chain_start(
    self,
    serialized: Dict[str, Any],
    inputs: Dict[str, Any],
    **kwargs
) -> None:
    """链开始时调用"""

def on_chain_end(
    self,
    outputs: Dict[str, Any],
    **kwargs
) -> None:
    """链结束时调用"""

def on_tool_start(
    self,
    serialized: Dict[str, Any],
    input_str: str,
    **kwargs
) -> None:
    """工具开始执行时调用"""

def on_tool_end(
    self,
    output: str,
    **kwargs
) -> None:
    """工具执行结束时调用"""

def on_tool_error(
    self,
    error: Exception,
    **kwargs
) -> None:
    """工具执行出错时调用"""
```

### ProgressCallback

```python
class ProgressCallback(BaseCallbackHandler):
    """
    进度通知回调
    
    提供执行进度的实时反馈。
    
    Attributes:
        total_steps: 总步骤数
        current_step: 当前步骤
        callback_func: 进度回调函数
    """
    
    def __init__(
        self,
        callback_func: Optional[Callable[[int, int, str], None]] = None
    ):
        """
        初始化进度回调
        
        Args:
            callback_func: 自定义进度回调函数
                          参数: (current, total, message)
        """
```

#### 使用示例

```python
# 创建进度回调
def on_progress(current: int, total: int, message: str):
    print(f"进度: {current}/{total} - {message}")

progress_callback = ProgressCallback(callback_func=on_progress)

# 在 Agent 中使用
agent = SQLAgent(
    config,
    db_config,
    callbacks=[progress_callback]
)
```

### PerformanceCallback

```python
class PerformanceCallback(BaseCallbackHandler):
    """
    性能监控回调
    
    记录各个步骤的执行时间和资源使用。
    
    Attributes:
        metrics: 性能指标字典
        start_times: 开始时间记录
    """
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        获取性能指标
        
        Returns:
            Dict containing:
            - total_time: 总执行时间
            - tool_times: 各工具执行时间
            - llm_calls: LLM 调用次数
            - token_usage: Token 使用量
        """
```

## 自定义回调

### 创建自定义回调

```python
from semanticsql_agent.utils.callbacks import BaseCallbackHandler

class CustomCallback(BaseCallbackHandler):
    """自定义回调处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.events = []
    
    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs
    ) -> None:
        """LLM 调用开始"""
        self.events.append({
            "type": "llm_start",
            "prompts": prompts,
            "timestamp": datetime.now()
        })
    
    def on_llm_end(
        self,
        response: Any,
        **kwargs
    ) -> None:
        """LLM 调用结束"""
        self.events.append({
            "type": "llm_end",
            "response": str(response),
            "timestamp": datetime.now()
        })
```

### 组合多个回调

```python
from semanticsql_agent.utils.callbacks import CallbackManager

# 创建回调管理器
callback_manager = CallbackManager()

# 添加多个回调
callback_manager.add_handler(TrajectoryCallback(recorder))
callback_manager.add_handler(ProgressCallback())
callback_manager.add_handler(CustomCallback(config))

# 在 Agent 中使用
agent = SQLAgent(
    config,
    db_config,
    callbacks=callback_manager.handlers
)
```

## 内置回调事件

### Agent 生命周期
- `on_agent_start`: Agent 开始执行
- `on_agent_finish`: Agent 执行完成
- `on_agent_error`: Agent 执行出错

### 工具执行
- `on_tool_start`: 工具开始执行
- `on_tool_end`: 工具执行成功
- `on_tool_error`: 工具执行失败

### LLM 交互
- `on_llm_start`: LLM 调用开始
- `on_llm_end`: LLM 返回结果
- `on_llm_error`: LLM 调用失败

### Chain 执行
- `on_chain_start`: Chain 开始
- `on_chain_end`: Chain 结束
- `on_chain_error`: Chain 出错

## 实际应用示例

### 日志记录回调
```python
class LoggingCallback(BaseCallbackHandler):
    """记录详细日志的回调"""
    
    def __init__(self, logger):
        self.logger = logger
    
    def on_tool_start(self, serialized, input_str, **kwargs):
        self.logger.info(f"Tool {serialized['name']} started with input: {input_str}")
    
    def on_tool_end(self, output, **kwargs):
        self.logger.info(f"Tool completed with output: {output}")
    
    def on_tool_error(self, error, **kwargs):
        self.logger.error(f"Tool failed with error: {error}")
```

### 实时通知回调
```python
class NotificationCallback(BaseCallbackHandler):
    """发送实时通知的回调"""
    
    def __init__(self, notifier):
        self.notifier = notifier
    
    def on_agent_finish(self, finish, **kwargs):
        self.notifier.send(
            f"查询完成: {finish['output']}",
            level="success"
        )
    
    def on_agent_error(self, error, **kwargs):
        self.notifier.send(
            f"查询失败: {error}",
            level="error"
        )
```

### 统计回调
```python
class StatisticsCallback(BaseCallbackHandler):
    """收集执行统计的回调"""
    
    def __init__(self):
        self.stats = {
            "tool_calls": {},
            "errors": [],
            "total_time": 0
        }
    
    def on_tool_end(self, output, **kwargs):
        tool_name = kwargs.get("name", "unknown")
        self.stats["tool_calls"][tool_name] = \
            self.stats["tool_calls"].get(tool_name, 0) + 1
```

## 最佳实践

1. **轻量级处理**：回调中避免重操作
2. **异常处理**：回调错误不应影响主流程
3. **异步支持**：长时间操作使用异步
4. **资源管理**：及时释放资源

## 注意事项

1. 回调在主线程中同步执行
2. 回调异常会被捕获并记录
3. 支持 LangChain 的所有回调接口
4. 可以动态添加或移除回调

---

相关文档：
- [TrajectoryRecorder API](./TrajectoryRecorder-API.md)
- [BaseAgent API](../agent模块/BaseAgent-API.md)