# Trae Agent 架构文档

## 1. 系统架构概览

### 1.1 架构原则
- **模块化设计**: 组件间低耦合，高内聚
- **插件化架构**: 工具和功能可独立扩展
- **异步优先**: 充分利用异步 I/O 提升性能
- **配置驱动**: 通过配置控制行为，减少代码修改

### 1.2 技术栈
- **编程语言**: Python 3.8+
- **核心依赖**:
  - Click: CLI 框架
  - Rich: 终端美化输出
  - OpenAI/Anthropic SDK: LLM 接口
  - PyYAML: 配置文件解析
  - python-dotenv: 环境变量管理
- **开发工具**:
  - pytest: 单元测试
  - black: 代码格式化
  - mypy: 类型检查
  - ruff: 代码质量检查

## 2. 分层架构详解

### 2.1 表示层 (Presentation Layer)

#### CLI 模块
```
cli.py                    # 主 CLI 入口点
├── 命令组
│   ├── init             # 初始化配置
│   ├── run              # 执行单个任务
│   ├── chat             # 交互式对话
│   ├── run-file         # 批量执行任务
│   └── replay           # 重放执行轨迹
└── 辅助功能
    ├── 配置解析
    ├── 输出格式化
    └── 错误处理
```

**CLI 控制台系统**:
```python
utils/cli.py
├── CLIConsole          # 控制台基类
├── ConsoleFactory      # 控制台工厂
├── ConsoleMode         # 控制台模式枚举
└── ConsoleType         # 控制台类型枚举
```

### 2.2 业务逻辑层 (Business Logic Layer)

#### Agent 模块架构
```
agent/
├── __init__.py         # 模块导出
├── agent_basics.py     # 基础数据结构
│   ├── AgentStep      # 执行步骤
│   ├── AgentStepState # 步骤状态
│   ├── AgentState     # Agent 状态
│   └── AgentExecution # 执行记录
├── base_agent.py       # 抽象基类
│   └── BaseAgent      # 定义 Agent 接口
├── trae_agent.py       # 默认实现
│   └── TraeAgent      # 标准 Agent 实现
└── agent.py            # 简化包装器
    └── Agent          # 用户友好的 API
```

**BaseAgent 核心方法**:
```python
class BaseAgent(ABC):
    @abstractmethod
    async def run_async(self, task: str) -> AgentExecution:
        """异步执行任务"""
        
    def run(self, task: str) -> AgentExecution:
        """同步执行任务（包装异步方法）"""
        
    @abstractmethod
    def _build_initial_messages(self, task: str) -> list[LLMMessage]:
        """构建初始消息"""
        
    async def _execute_steps(self) -> AgentExecution:
        """执行 Agent 步骤循环"""
```

### 2.3 工具层 (Tools Layer)

#### 工具系统架构
```
tools/
├── __init__.py              # 工具注册表
├── base.py                  # 工具基础设施
│   ├── Tool                # 工具抽象基类
│   ├── ToolCall            # 工具调用数据
│   ├── ToolResult          # 工具执行结果
│   └── ToolExecutor        # 工具执行器
├── bash_tool.py             # Bash 命令执行
├── edit_tool.py             # 文件编辑工具
├── json_edit_tool.py        # JSON 文件编辑
├── ckg_tool.py              # 代码知识图谱
├── sequential_thinking_tool.py  # 序列思考工具
├── mcp_tool.py              # 模型上下文协议
└── task_done_tool.py        # 任务完成标记
```

**工具接口定义**:
```python
class Tool(ABC):
    name: str                    # 工具唯一标识
    description: str             # 工具描述
    
    @abstractmethod
    def get_schema(self) -> dict:
        """返回工具参数 JSON Schema"""
        
    @abstractmethod
    def execute(self, tool_call: ToolCall) -> ToolResult:
        """执行工具逻辑"""
```

**工具注册机制**:
```python
# tools/__init__.py
tools_registry: dict[str, type[Tool]] = {
    "bash": BashTool,
    "str_replace_editor": EditTool,
    "json_editor": JSONEditTool,
    "ckg": CKGTool,
    "sequential_thinking": SequentialThinkingTool,
    "mcp": MCPTool,
    "task_done": TaskDoneTool,
}
```

### 2.4 基础设施层 (Infrastructure Layer)

#### 配置系统架构
```
utils/
├── config.py                # 现代配置系统
│   ├── ModelProvider       # 模型提供商配置
│   ├── ModelConfig         # 模型参数配置
│   ├── AgentConfig         # Agent 配置
│   ├── TraeAgentConfig     # 完整配置
│   └── Config              # 配置加载器
└── legacy_config.py         # 旧版配置兼容
    └── LegacyConfig        # 向后兼容支持
```

**配置层次结构**:
```yaml
# 完整配置示例
model_providers:
  openai:
    provider: openai
    api_key: ${OPENAI_API_KEY}
  
  anthropic:
    provider: anthropic
    api_key: ${ANTHROPIC_API_KEY}

models:
  gpt4:
    model: gpt-4-turbo-preview
    model_provider: openai
    max_tokens: 4096
    temperature: 0.7

agents:
  default:
    model: gpt4
    tools:
      - bash
      - str_replace_editor
      - ckg
    max_steps: 30
```

#### LLM 客户端架构
```
utils/llm_clients/
├── __init__.py
├── llm_basics.py           # 基础数据结构
│   ├── LLMMessage         # 消息格式
│   ├── LLMResponse        # 响应格式
│   └── LLMToolCall        # 工具调用格式
├── llm_client.py           # 统一客户端接口
│   └── LLMClient          # 多提供商支持
├── providers/              # 提供商实现
│   ├── openai_client.py
│   ├── anthropic_client.py
│   └── azure_client.py
└── llm_cache.py            # 响应缓存（可选）
```

#### 轨迹记录系统
```
utils/
└── trajectory_recorder.py
    ├── TrajectoryRecorder  # 轨迹记录器
    ├── Trajectory          # 轨迹数据结构
    └── TrajectoryPlayer    # 轨迹回放器
```

## 3. 核心流程架构

### 3.1 Agent 执行流程
```
任务输入
    ↓
初始化 Agent → 加载配置 → 注册工具
    ↓
构建初始消息（系统提示 + 任务描述）
    ↓
执行循环:
    ├─ 发送消息到 LLM
    ├─ 解析 LLM 响应
    ├─ 如果包含工具调用:
    │   ├─ 验证工具和参数
    │   ├─ 执行工具
    │   └─ 将结果添加到消息历史
    ├─ 如果是最终响应:
    │   └─ 结束执行
    └─ 检查步骤限制
    ↓
生成执行报告 → 保存轨迹 → 返回结果
```

### 3.2 工具执行流程
```
LLM 生成工具调用
    ↓
ToolExecutor 接收调用请求
    ↓
工具查找和验证:
    ├─ 检查工具是否存在
    ├─ 验证参数符合 Schema
    └─ 检查执行权限
    ↓
工具执行:
    ├─ 创建执行上下文
    ├─ 调用工具 execute 方法
    ├─ 捕获和处理异常
    └─ 格式化执行结果
    ↓
返回 ToolResult → 更新消息历史
```

### 3.3 配置加载流程
```
启动应用
    ↓
检查配置文件路径:
    ├─ 命令行参数指定
    ├─ 默认位置查找
    └─ 环境变量指定
    ↓
加载配置文件:
    ├─ 解析 YAML/JSON
    ├─ 验证配置格式
    └─ 处理环境变量替换
    ↓
配置验证和规范化:
    ├─ 检查必需字段
    ├─ 验证值的合法性
    ├─ 应用默认值
    └─ 解析引用关系
    ↓
创建配置对象 → 初始化组件
```

## 4. 数据模型架构

### 4.1 核心数据结构

#### Agent 执行模型
```python
@dataclass
class AgentStep:
    """单个执行步骤"""
    state: AgentStepState    # 步骤状态
    messages: list[LLMMessage]  # 消息历史
    start_time: float        # 开始时间
    end_time: float | None   # 结束时间
    error: str | None        # 错误信息

@dataclass
class AgentExecution:
    """完整执行记录"""
    task: str                # 任务描述
    steps: list[AgentStep]   # 执行步骤
    state: AgentState        # 最终状态
    start_time: float        # 开始时间
    end_time: float          # 结束时间
    
    @property
    def duration(self) -> float:
        """执行耗时"""
        return self.end_time - self.start_time
```

#### LLM 交互模型
```python
@dataclass
class LLMMessage:
    """LLM 消息"""
    role: str                # system/user/assistant/tool
    content: str | None      # 文本内容
    tool_calls: list[LLMToolCall] | None  # 工具调用
    tool_call_id: str | None # 工具调用 ID
    
@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str | None      # 响应文本
    tool_calls: list[LLMToolCall] | None  # 工具调用
    finish_reason: str       # 完成原因
    usage: dict | None       # Token 使用情况
```

#### 工具系统模型
```python
@dataclass
class ToolCall:
    """工具调用请求"""
    id: str                  # 调用 ID
    type: str = "function"   # 调用类型
    function: ToolCallFunction  # 函数信息
    
@dataclass
class ToolCallFunction:
    """工具函数信息"""
    name: str                # 工具名称
    arguments: dict          # 调用参数
    
@dataclass
class ToolResult:
    """工具执行结果"""
    tool_call_id: str        # 对应的调用 ID
    content: str             # 结果内容
    is_error: bool = False   # 是否错误
```

### 4.2 配置数据模型
```python
@dataclass
class ModelProvider:
    """模型提供商配置"""
    api_key: str             # API 密钥
    provider: str            # 提供商名称
    base_url: str | None     # 自定义端点
    api_version: str | None  # API 版本

@dataclass
class ModelConfig:
    """模型配置"""
    model: str               # 模型名称
    model_provider: ModelProvider  # 提供商
    max_tokens: int          # 最大 Token
    temperature: float       # 温度参数
    top_p: float            # Top-p 采样
    parallel_tool_calls: bool  # 并行工具调用

@dataclass
class AgentConfig:
    """Agent 配置"""
    model: ModelConfig       # 模型配置
    tools: list[str]         # 启用的工具
    max_steps: int          # 最大步骤数
    name: str               # Agent 名称
    description: str        # Agent 描述
```

## 5. 工具架构详解

### 5.1 Bash 工具
```python
class BashTool(Tool):
    """执行 shell 命令"""
    
    功能:
    - 执行任意 shell 命令
    - 支持管道和重定向
    - 工作目录管理
    - 超时控制
    
    安全措施:
    - 命令白名单（可选）
    - 危险命令警告
    - 资源限制
```

### 5.2 编辑工具
```python
class EditTool(Tool):
    """文件编辑工具"""
    
    功能:
    - 创建新文件
    - 编辑现有文件
    - 支持多种编辑模式
    - 备份和恢复
    
    编辑模式:
    - str_replace: 字符串替换
    - line_edit: 行编辑
    - patch: 补丁应用
```

### 5.3 CKG 工具
```python
class CKGTool(Tool):
    """代码知识图谱工具"""
    
    功能:
    - 代码结构分析
    - 依赖关系提取
    - 知识图谱构建
    - 查询和检索
    
    支持语言:
    - Python
    - JavaScript/TypeScript
    - Java
    - Go
```

### 5.4 序列思考工具
```python
class SequentialThinkingTool(Tool):
    """引导 LLM 进行结构化思考"""
    
    功能:
    - 问题分解
    - 步骤规划
    - 逻辑推理
    - 决策树构建
    
    思考模式:
    - 分析-综合
    - 假设-验证
    - 比较-选择
```

## 6. 扩展点架构

### 6.1 工具扩展
```python
# 1. 创建新工具
class MyCustomTool(Tool):
    name = "my_tool"
    description = "自定义工具"
    
    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "param1": {"type": "string"}
            }
        }
    
    def execute(self, tool_call: ToolCall) -> ToolResult:
        # 实现工具逻辑
        pass

# 2. 注册工具
tools_registry["my_tool"] = MyCustomTool

# 3. 在配置中启用
agents:
  custom:
    tools:
      - my_tool
```

### 6.2 LLM 提供商扩展
```python
# 1. 实现提供商客户端
class CustomLLMProvider:
    def create_completion(self, messages, **kwargs):
        # 调用自定义 API
        pass

# 2. 注册到 LLMClient
LLMClient.register_provider("custom", CustomLLMProvider)

# 3. 在配置中使用
model_providers:
  my_provider:
    provider: custom
    api_key: xxx
```

### 6.3 Agent 行为扩展
```python
# 1. 继承 BaseAgent
class SpecializedAgent(BaseAgent):
    def _build_initial_messages(self, task: str) -> list[LLMMessage]:
        # 自定义系统提示
        pass
    
    async def _execute_steps(self) -> AgentExecution:
        # 自定义执行逻辑
        pass

# 2. 使用自定义 Agent
agent = SpecializedAgent(config)
result = agent.run("特殊任务")
```

## 7. 性能架构

### 7.1 异步执行架构
- 所有 I/O 操作异步化
- 工具并发执行
- 流式响应处理
- 连接复用

### 7.2 缓存架构
```
缓存层次:
├── LLM 响应缓存
│   ├─ 内存缓存（LRU）
│   └─ 磁盘缓存（可选）
├── 工具结果缓存
│   └─ 基于参数哈希
└── 文件内容缓存
    └─ 基于修改时间
```

### 7.3 资源管理
- 内存使用监控
- 进程数量限制
- 网络连接池
- 磁盘空间检查

## 8. 安全架构

### 8.1 权限控制
- 文件系统访问限制
- 网络访问控制
- 进程执行权限
- API 访问限制

### 8.2 数据保护
- API 密钥加密存储
- 敏感信息脱敏
- 日志隐私保护
- 轨迹数据加密

### 8.3 执行隔离
- 工具执行沙箱（可选）
- 资源使用限制
- 超时机制
- 错误隔离

## 9. 监控和日志架构

### 9.1 日志系统
```python
# 日志级别
- DEBUG: 详细调试信息
- INFO: 一般信息
- WARNING: 警告信息
- ERROR: 错误信息
- CRITICAL: 严重错误

# 日志内容
- Agent 执行步骤
- 工具调用详情
- LLM 交互记录
- 性能指标
```

### 9.2 监控指标
- 任务执行时间
- 工具调用频率
- LLM Token 使用
- 错误率统计

### 9.3 轨迹系统
- 完整执行记录
- 可重放格式
- 压缩存储
- 查询检索

## 10. 部署架构

### 10.1 单机部署
```
trae-agent/
├── 可执行文件
├── 配置文件
├── 工具插件
└── 日志目录
```

### 10.2 容器化部署
```dockerfile
# 多阶段构建
# 运行时优化
# 安全加固
```

### 10.3 服务化部署（未来）
- REST API 服务
- gRPC 接口
- WebSocket 支持
- 负载均衡