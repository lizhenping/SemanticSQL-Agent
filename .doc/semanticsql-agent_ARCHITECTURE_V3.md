# SemanticSQL Agent 架构文档 V3

## 1. 系统架构概览

### 1.1 核心理念
- **智能体驱动**：基于 ReAct（Reasoning + Acting）模式的自主智能体
- **工具协同**：智能体通过调用各种工具完成复杂任务
- **任务导向**：智能体根据任务目标自主规划和执行
- **轨迹记录**：完整记录智能体的思考和行动过程

### 1.2 技术架构
```
┌─────────────────────────────────────────────────────────┐
│                      CLI Interface                       │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────┐
│                    Agent System                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │              Smart SQL Agent                      │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │   │
│  │  │  Task    │  │  ReAct   │  │  Execution   │  │   │
│  │  │ Planning │→ │  Engine  │→ │   Tracker    │  │   │
│  │  └──────────┘  └──────────┘  └──────────────┘  │   │
│  └─────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────┐
│                    Tools Layer                           │
│  ┌──────────┐  ┌──────────┐  ┌────────┐  ┌──────────┐ │
│  │ Analysis │  │Generation│  │  SQL   │  │Reflection│ │
│  │  Tools   │  │  Tools   │  │ Tools  │  │  Tools   │ │
│  └──────────┘  └──────────┘  └────────┘  └──────────┘ │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────┐
│                 Infrastructure Layer                     │
│  ┌──────────┐  ┌──────────┐  ┌────────┐  ┌──────────┐ │
│  │  Config  │  │    LLM   │  │Database│  │  Prompt  │ │
│  │  Manager │  │  Client  │  │ Client │  │  Manager │ │
│  └──────────┘  └──────────┘  └────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────┘
```

## 2. 核心组件详解

### 2.1 智能体系统 (Agent System)

#### SmartSQLAgent - 主智能体
```python
class SmartSQLAgent(BaseAgent):
    """
    智能SQL数据生成Agent
    继承自BaseAgent，实现特定的NL2SQL数据生成任务
    """
    
    def __init__(self, config: TraeConfig):
        super().__init__(config)
        self._initialize_tools()
        
    def _initialize_tools(self):
        """初始化并注册所有工具"""
        # 分析工具
        self.register_tool("schema_extraction", SchemaExtractionTool())
        self.register_tool("domain_analysis", DomainAnalysisTool())
        self.register_tool("field_classification", FieldClassificationTool())
        self.register_tool("er_analysis", ERAnalysisTool())
        
        # 生成工具
        self.register_tool("scenario_generation", ScenarioGenerationTool())
        self.register_tool("question_generation", QuestionGenerationTool())
        self.register_tool("sql_generation", SQLGenerationTool())
        
        # SQL工具
        self.register_tool("sql_validation", SQLValidationTool())
        self.register_tool("sql_execution", SQLExecutionTool())
        
        # 反思工具
        self.register_tool("sql_reflection", SQLReflectionTool())
        
    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一个智能SQL训练数据生成专家。

你的任务是：
1. 分析数据库结构和业务领域
2. 生成高质量的自然语言问题和对应的SQL查询
3. 验证和优化生成的内容

使用ReAct模式工作：
- Thought: 分析当前状态，决定下一步行动
- Action: 选择并调用合适的工具
- Observation: 观察工具执行结果

可用工具：
{tools_description}

重要：
- 按照任务要求系统地完成各个阶段
- 确保生成的数据质量高、多样性好
- 遇到错误时合理处理并继续
"""
```

#### BaseAgent - 基础智能体
```python
class BaseAgent(ABC):
    """
    智能体基础类 - 实现ReAct模式
    参考trae_agent的设计
    """
    
    def __init__(self, config: TraeConfig):
        self.config = config
        self.llm_client = self._create_llm_client()
        self.tools = {}
        self.current_execution = None
        self.max_steps = config.agent.max_steps
        
    def _create_llm_client(self):
        """创建LLM客户端"""
        return openai.OpenAI(
            api_key=self.config.llm.api_key,
            base_url=self.config.llm.base_url
        )
    
    def run(self, task: str) -> AgentExecution:
        """执行任务 - 核心ReAct循环"""
        self.current_execution = AgentExecution(task=task, steps=[])
        
        try:
            # 初始化任务上下文
            context = self._build_initial_context(task)
            
            # ReAct循环
            step_count = 0
            while step_count < self.max_steps:
                # 1. Thought - 思考
                thought = self._think(context)
                self._record_step(AgentStepType.THOUGHT, thought)
                
                # 2. 检查是否完成
                if self._should_finish(thought):
                    break
                
                # 3. Action - 行动
                action = self._decide_action(thought)
                self._record_step(AgentStepType.ACTION, action)
                
                # 4. Observation - 观察
                observation = self._execute_action(action)
                self._record_step(AgentStepType.OBSERVATION, observation)
                
                # 5. 更新上下文
                context = self._update_context(context, thought, action, observation)
                
                step_count += 1
            
            # 生成最终结果
            self.current_execution.final_result = self._generate_final_result()
            self.current_execution.success = True
            
        except Exception as e:
            self.logger.error(f"Agent execution failed: {e}")
            self.current_execution.success = False
            self.current_execution.error = str(e)
            
        return self.current_execution
    
    def _think(self, context: Dict[str, Any]) -> str:
        """思考下一步 - ReAct的Thought"""
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": self._format_thinking_prompt(context)}
        ]
        
        response = self.llm_client.chat.completions.create(
            messages=messages,
            **self.llm_config
        )
        
        return response.choices[0].message.content
    
    def _decide_action(self, thought: str) -> Dict[str, Any]:
        """基于思考决定行动"""
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": self._format_action_prompt(thought)}
        ]
        
        # 使用Function Calling
        response = self.llm_client.chat.completions.create(
            messages=messages,
            tools=self._get_tools_schema(),
            tool_choice="auto",
            **self.llm_config
        )
        
        # 解析工具调用
        tool_calls = response.choices[0].message.tool_calls
        if tool_calls:
            tool_call = tool_calls[0]
            return {
                "tool_name": tool_call.function.name,
                "tool_input": json.loads(tool_call.function.arguments)
            }
        
        return {"tool_name": "none", "tool_input": {}}
    
    def _execute_action(self, action: Dict[str, Any]) -> Any:
        """执行行动并返回观察结果"""
        tool_name = action["tool_name"]
        tool_input = action["tool_input"]
        
        if tool_name == "none":
            return "No action taken"
        
        if tool_name not in self.tools:
            return f"Error: Tool {tool_name} not found"
        
        try:
            tool = self.tools[tool_name]
            result = tool.run(**tool_input)
            return result
        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """获取系统提示词 - 子类必须实现"""
        pass
```

### 2.2 工具系统 (Tools Layer)

#### 工具基类设计
```python
class BaseTool(ABC):
    """工具基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""
        pass
    
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """获取Function Calling的schema"""
        pass
    
    @abstractmethod
    def run(self, **kwargs) -> Any:
        """执行工具"""
        pass
```

#### 工具分类

**1. 分析工具 (Analysis Tools)**
- **SchemaExtractionTool**: 提取数据库结构信息
- **DomainAnalysisTool**: 分析业务领域
- **FieldClassificationTool**: 分类字段类型
- **ERAnalysisTool**: 分析实体关系

**2. 生成工具 (Generation Tools)**
- **ScenarioGenerationTool**: 基于规则生成业务场景
- **QuestionGenerationTool**: 生成自然语言问题
- **SQLGenerationTool**: 一步生成SQL查询

**3. SQL工具 (SQL Tools)**
- **SQLValidationTool**: 验证SQL语法和语义
- **SQLExecutionTool**: 执行SQL查询

**4. 反思工具 (Reflection Tools)**
- **SQLReflectionTool**: 基于执行结果反思和改进

### 2.3 执行跟踪 (Execution Tracking)

```python
@dataclass
class AgentStep:
    """智能体执行步骤"""
    step_type: AgentStepType  # THOUGHT, ACTION, OBSERVATION, REFLECTION
    content: str
    timestamp: datetime
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[Any] = None
    error: Optional[str] = None

@dataclass
class AgentExecution:
    """智能体执行记录"""
    task: str
    steps: List[AgentStep]
    final_result: Optional[Any] = None
    success: bool = True
    total_steps: int = 0
    execution_time: float = 0.0
    error: Optional[str] = None
```

## 3. 工作流程

### 3.1 智能体执行流程

```
用户输入任务
    ↓
智能体初始化
    - 加载配置
    - 初始化工具
    - 设置系统提示词
    ↓
开始ReAct循环
    ┌─────────────────────────┐
    │                         │
    ↓                         │
Thought（思考）               │
    - 分析当前状态            │
    - 决定下一步              │
    ↓                         │
判断是否完成 ──是──→ 结束      │
    │                         │
    否                        │
    ↓                         │
Action（行动）                │
    - 选择工具                │
    - 准备参数                │
    ↓                         │
Observation（观察）           │
    - 执行工具                │
    - 获取结果                │
    ↓                         │
更新上下文 ───────────────────┘
    ↓
生成最终结果
```

### 3.2 具体任务执行示例

```
任务: 生成NL2SQL训练数据

Step 1 - 分析数据库
  Thought: 首先需要了解数据库结构
  Action: schema_extraction_tool
  Observation: 获得表结构信息

Step 2 - 分析领域
  Thought: 基于表结构分析业务领域
  Action: domain_analysis_tool with schema
  Observation: 识别为电商领域

Step 3 - 分类字段
  Thought: 需要对字段进行分类以便后续生成
  Action: field_classification_tool
  Observation: 字段分类完成

Step 4 - 分析关系
  Thought: 理解表之间的关系有助于生成复杂查询
  Action: er_analysis_tool
  Observation: 识别主外键关系

Step 5 - 生成场景
  Thought: 基于领域和结构生成查询场景
  Action: scenario_generation_tool
  Observation: 生成10个业务场景

Step 6 - 生成问题
  Thought: 为每个场景生成自然语言问题
  Action: question_generation_tool
  Observation: 生成50个问题

Step 7 - 生成SQL
  Thought: 为每个问题生成对应的SQL
  Action: sql_generation_tool
  Observation: 生成50条SQL

Step 8 - 验证SQL
  Thought: 验证生成的SQL语法
  Action: sql_validation_tool
  Observation: 45条通过，5条有语法错误

Step 9 - 执行测试
  Thought: 执行SQL测试实际效果
  Action: sql_execution_tool
  Observation: 执行结果和性能数据

Step 10 - 反思改进
  Thought: 基于执行结果进行反思
  Action: sql_reflection_tool
  Observation: 优化建议和改进的SQL

Step 11 - 完成
  Thought: 所有步骤完成，整理最终结果
  [Task Complete]
```

## 4. 关键设计特点

### 4.1 智能体自主性
- 智能体根据任务目标自主决定执行步骤
- 不是预定义的流水线，而是动态的执行路径
- 可以根据中间结果调整策略

### 4.2 工具协同
- 工具之间通过智能体协调
- 上一个工具的输出可以作为下一个工具的输入
- 智能体理解工具的功能并合理使用

### 4.3 错误处理
- 智能体可以识别错误并尝试恢复
- 通过反思机制改进结果
- 保持执行的连续性

### 4.4 可扩展性
- 新增工具只需实现BaseTool接口
- 智能体自动识别和使用新工具
- 可以为特定任务定制智能体

## 5. 与trae_agent的对齐

### 5.1 共同特点
- 基于ReAct模式的智能体架构
- 工具注册和调用机制
- 执行轨迹记录
- LLM驱动的决策

### 5.2 定制化部分
- 专注于NL2SQL数据生成任务
- 特定的工具集合
- 简化的配置（只支持Qwen）
- 业务相关的系统提示词

## 6. 配置管理

### 6.1 配置结构
```python
@dataclass
class TraeConfig:
    """统一配置"""
    database: DatabaseConfig    # 数据库连接
    llm: LLMConfig             # LLM配置（Qwen）
    agent: AgentConfig         # 智能体配置
    output: OutputConfig       # 输出配置
```

### 6.2 LLM配置
```python
@dataclass
class LLMConfig:
    """LLM配置 - 支持Qwen的OpenAI兼容API"""
    model: str = "qwen-plus"
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    api_key: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
```

## 7. 数据模型

### 7.1 核心数据模型
```python
# 输入
TaskRequest          # 任务请求

# 分析结果
SchemaAnalysis       # 数据库结构
DomainAnalysis       # 领域分析
FieldClassification  # 字段分类
RelationshipAnalysis # 关系分析

# 生成结果
QueryScenario        # 查询场景
GeneratedQuestion    # 自然语言问题
GeneratedSQL         # SQL查询

# 验证和执行
ValidationResult     # 验证结果
ExecutionResult      # 执行结果
ReflectionResult     # 反思结果

# 最终输出
TrainingExample      # 单个样本
TrainingDataset      # 完整数据集
```

## 8. 提示词管理

### 8.1 系统提示词
- 定义智能体的角色和能力
- 说明ReAct工作模式
- 列出可用工具

### 8.2 工具提示词
- 每个工具的使用说明
- 参数要求
- 输出格式

### 8.3 任务提示词
- 特定任务的指导
- 质量要求
- 约束条件

## 9. 最佳实践

### 9.1 智能体开发
- 清晰定义系统提示词
- 合理设置最大步骤数
- 实现有效的完成判断

### 9.2 工具开发
- 单一职责原则
- 清晰的输入输出
- 良好的错误处理

### 9.3 任务设计
- 明确的任务描述
- 可衡量的成功标准
- 合理的资源限制

## 10. 部署和监控

### 10.1 部署考虑
- 智能体实例管理
- 工具资源隔离
- 并发任务处理

### 10.2 监控指标
- 任务成功率
- 平均步骤数
- 工具调用频率
- LLM token使用
- 执行时间分布