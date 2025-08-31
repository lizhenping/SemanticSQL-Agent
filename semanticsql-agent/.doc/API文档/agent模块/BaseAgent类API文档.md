# BaseAgent 类 API 文档

## 概述
`BaseAgent` 是所有智能体的基类，实现了 ReAct（推理+行动）模式。它提供了基础的任务执行框架、工具管理和执行跟踪功能。

## 类定义
```python
class BaseAgent(ABC):
    """基础智能体类，实现 ReAct 模式"""
```

## 构造函数

### `__init__(self, settings: Settings, db_config: DatabaseConfig)`
初始化智能体实例。

**参数：**
- `settings` (Settings): 系统配置对象，包含 LLM 配置、执行参数等
- `db_config` (DatabaseConfig): 数据库配置对象

**初始化内容：**
- LLM 客户端配置
- 工具映射表
- 执行状态管理
- 回调函数列表
- 轨迹记录器（如果启用）

## 抽象方法（子类必须实现）

### `_initialize_tools(self) -> None`
初始化智能体工具。子类需要在此方法中注册所有需要使用的工具。

### `get_system_prompt(self) -> str`
获取系统提示词。返回用于引导 LLM 行为的系统提示。

## 核心方法

### `register_tool(self, name: str, tool_instance: Any, description: str) -> None`
注册工具到智能体。

**参数：**
- `name` (str): 工具名称
- `tool_instance` (Any): 工具实例对象
- `description` (str): 工具描述

### `add_callback(self, callback: ExecutionCallback) -> None`
添加执行回调函数。

**参数：**
- `callback` (ExecutionCallback): 回调函数实例

### `new_task(self, task: str) -> AgentExecution`
开始新任务执行。

**参数：**
- `task` (str): 任务描述

**返回：**
- `AgentExecution`: 执行记录对象

### `call_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]`
调用指定工具。

**参数：**
- `tool_name` (str): 工具名称
- `**kwargs`: 工具参数

**返回：**
- `Dict[str, Any]`: 工具执行结果

**异常：**
- 如果工具不存在，返回错误信息
- 如果工具执行失败，返回错误详情

## 内部方法

### `_execute_react_loop(self, task: str) -> Any`
执行 ReAct 循环的主要逻辑。

**流程：**
1. 生成下一步行动
2. 解析响应
3. 执行行动
4. 记录步骤
5. 检查是否需要反思
6. 重复直到完成或达到最大步骤数

### `_generate_next_action(self) -> str`
生成下一步行动计划。

**返回：**
- `str`: LLM 生成的行动描述

### `_parse_response(self, response: str) -> Tuple[Optional[str], Optional[str], Optional[Dict]]`
解析 LLM 响应，提取思考、行动和行动输入。

**参数：**
- `response` (str): LLM 响应文本

**返回：**
- `Tuple[Optional[str], Optional[str], Optional[Dict]]`: (思考内容, 行动名称, 行动参数)

### `_execute_action(self, action: str, action_input: Optional[Dict]) -> Any`
执行具体行动。

**参数：**
- `action` (str): 行动名称
- `action_input` (Optional[Dict]): 行动参数

**返回：**
- `Any`: 行动执行结果

### `_add_step(self, step_type: AgentStepType, content: str, **kwargs) -> None`
添加执行步骤记录。

**参数：**
- `step_type` (AgentStepType): 步骤类型
- `content` (str): 步骤内容
- `**kwargs`: 额外参数（如 tool_name, tool_input, tool_output 等）

### `_build_conversation_history(self) -> str`
构建对话历史记录。

**返回：**
- `str`: 格式化的对话历史

### `_format_tool_output(self, output: Any) -> str`
格式化工具输出。

**参数：**
- `output` (Any): 工具原始输出

**返回：**
- `str`: 格式化后的输出字符串

### `_reflect_on_progress(self) -> Optional[str]`
反思执行进度（如果启用反思功能）。

**返回：**
- `Optional[str]`: 反思内容或 None

### `_generate_final_result(self) -> Any`
生成最终结果。

**返回：**
- `Any`: 最终执行结果

### `_debug_object_for_slices(self, obj: Any, path: str = "") -> None`
调试对象切片（内部方法）。

**参数：**
- `obj` (Any): 要调试的对象
- `path` (str): 对象路径

**功能：**
- 检查对象是否包含切片
- 用于轨迹序列化调试

### `_serialize_for_storage(self, obj: Any) -> Any`
序列化对象用于存储（内部方法）。

**参数：**
- `obj` (Any): 要序列化的对象

**返回：**
- `Any`: 序列化后的对象

**功能：**
- 处理复杂对象的序列化
- 确保可以JSON序列化

## 使用示例

```python
from config.settings import Settings
from config.database import DatabaseConfig

# 创建配置
settings = Settings()
db_config = DatabaseConfig(
    host="localhost",
    port=3306,
    user="root",
    password="password",
    database="test_db"
)

# 创建智能体实例（使用具体子类）
agent = ConcreteAgent(settings, db_config)

# 添加回调
callback = MyExecutionCallback()
agent.add_callback(callback)

# 执行任务
result = agent.new_task("分析数据库表结构")
```

## 注意事项

1. `BaseAgent` 是抽象类，不能直接实例化
2. 子类必须实现 `_initialize_tools()` 和 `get_system_prompt()` 方法
3. 工具必须在 `_initialize_tools()` 中注册才能使用
4. 执行过程中的所有步骤都会被记录
5. 可以通过回调函数监控执行过程
6. 支持轨迹记录功能，用于调试和分析