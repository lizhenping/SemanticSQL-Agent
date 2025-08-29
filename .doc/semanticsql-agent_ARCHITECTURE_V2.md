# SemanticSQL Agent 架构文档 V2

## 1. 系统架构概览

### 1.1 核心理念
- **ReAct模式**：Think → Act → Observe 循环
- **流水线架构**：分析 → 生成 → 验证反思
- **关注点分离**：工具单一职责，Agent负责编排
- **数据驱动**：完整的数据模型贯穿全流程

### 1.2 技术架构
```
┌─────────────────────────────────────────────────────────┐
│                      CLI Interface                       │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────┐
│                   Pipeline Layer                         │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │   Context   │  │ Orchestrator │  │    Stages     │  │
│  └─────────────┘  └──────────────┘  └───────────────┘  │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────┐
│                    Agent Layer                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │            ReactAgent (ReAct Pattern)            │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────────────┐ │   │
│  │  │ Think   │→ │  Act    │→ │    Observe      │ │   │
│  │  └─────────┘  └─────────┘  └─────────────────┘ │   │
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
│  │  Config  │  │ Database │  │ Prompt │  │  Logger  │ │
│  │  Manager │  │  Manager │  │ Loader │  │  System  │ │
│  └──────────┘  └──────────┘  └────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────┘
```

## 2. 核心组件详解

### 2.1 数据模型层 (core/models.py)

#### 完整的流程数据模型
```python
# 1. 输入阶段
TaskRequest → 任务配置

# 2. 分析阶段
SchemaAnalysis → 数据库结构
DomainAnalysis → 业务领域
FieldClassification → 字段分类
RelationshipAnalysis → 关系分析

# 3. 生成阶段
QueryScenario → 业务场景
GeneratedQuestion → 自然语言问题
GeneratedSQL → SQL查询

# 4. 验证反思阶段
ValidationResult → 验证结果
ExecutionResult → 执行结果
ReflectionResult → 反思改进

# 5. 执行跟踪
ReactStep → 单个ReAct步骤
ExecutionTrace → 完整执行轨迹

# 6. 最终输出
TrainingExample → 单个训练样本
TrainingDataset → 完整数据集
```

### 2.2 Agent层 - ReAct实现

#### ReactAgent核心设计
```python
class ReactAgent:
    """ReAct模式实现"""
    
    def __init__(self, tools: List[BaseTool], llm_client: LLMClient):
        self.tools = {tool.name: tool for tool in tools}
        self.llm = llm_client
        self.execution_trace = ExecutionTrace()
        self.max_steps = 20
    
    async def run_task(self, task: str, context: ExecutionContext) -> Any:
        """执行任务的主循环"""
        step_count = 0
        
        while step_count < self.max_steps:
            # 1. Think - 分析当前状态，决定下一步
            thought = await self._think(task, context, self.execution_trace)
            
            # 2. Act - 选择工具和参数
            action = await self._act(thought)
            
            # 3. Observe - 执行工具并观察结果
            observation = await self._observe(action)
            
            # 4. 记录步骤
            step = ReactStep(
                step_number=step_count + 1,
                thought=thought,
                action=action,
                observation=observation
            )
            self.execution_trace.steps.append(step)
            
            # 5. 判断是否完成
            if self._is_task_complete(observation):
                break
                
            step_count += 1
        
        return self._extract_final_result()
```

#### 思考-行动-观察实现
```python
async def _think(self, task: str, context: ExecutionContext, trace: ExecutionTrace) -> ThoughtStep:
    """思考下一步应该做什么"""
    prompt = self.prompt_manager.get_prompt(
        "react/thought",
        task=task,
        context=context.get_current_state(),
        history=trace.get_recent_steps(5)
    )
    
    thought_content = await self.llm.generate(prompt)
    
    return ThoughtStep(
        content=thought_content,
        timestamp=datetime.now()
    )

async def _act(self, thought: ThoughtStep) -> ActionStep:
    """基于思考决定行动"""
    prompt = self.prompt_manager.get_prompt(
        "react/action",
        thought=thought.content,
        available_tools=self._get_tool_descriptions()
    )
    
    action_response = await self.llm.generate(prompt)
    tool_name, tool_params = self._parse_action(action_response)
    
    return ActionStep(
        tool_name=tool_name,
        tool_input=tool_params,
        timestamp=datetime.now()
    )

async def _observe(self, action: ActionStep) -> ObservationStep:
    """执行行动并观察结果"""
    tool = self.tools.get(action.tool_name)
    
    if not tool:
        return ObservationStep(
            tool_output=None,
            success=False,
            error=f"Tool {action.tool_name} not found",
            timestamp=datetime.now()
        )
    
    try:
        # 执行工具
        result = await tool.run(**action.tool_input)
        
        return ObservationStep(
            tool_output=result,
            success=True,
            error=None,
            timestamp=datetime.now()
        )
    except Exception as e:
        return ObservationStep(
            tool_output=None,
            success=False,
            error=str(e),
            timestamp=datetime.now()
        )
```

### 2.3 工具系统设计

#### 工具基类
```python
class BaseTool(ABC):
    """工具基类"""
    name: str
    description: str
    
    @abstractmethod
    def get_input_schema(self) -> Type[BaseModel]:
        """返回输入参数的Pydantic模型"""
        pass
    
    @abstractmethod
    async def run(self, **kwargs) -> BaseModel:
        """执行工具逻辑"""
        pass
    
    def validate_input(self, **kwargs) -> Dict[str, Any]:
        """验证输入参数"""
        schema = self.get_input_schema()
        return schema(**kwargs).dict()
```

#### 工具分类和职责

**1. 分析工具 (tools/analysis/)**
- `schema_analyzer.py`: 提取数据库结构
- `domain_analyzer.py`: 识别业务领域
- `field_classifier.py`: 分类字段类型
- `relationship_analyzer.py`: 分析表关系

**2. 生成工具 (tools/generation/)**
- `scenario_generator.py`: 生成业务场景
- `question_generator.py`: 生成自然语言问题
- `sql_generator.py`: 一步生成SQL

**3. SQL工具 (tools/sql/)**
- `sql_executor.py`: 纯执行SQL
- `sql_validator.py`: 验证SQL正确性
- `sql_optimizer.py`: SQL优化建议

**4. 反思工具 (tools/reflection/)**
- `execution_analyzer.py`: 分析执行结果
- `quality_improver.py`: 提供改进建议

### 2.4 流水线设计

#### 执行上下文
```python
class ExecutionContext:
    """流水线执行上下文"""
    
    def __init__(self, request: TaskRequest):
        self.request = request
        self.results = {}  # 各阶段结果
        self.current_stage = None
        self.metadata = {}
        
    def save_stage_result(self, stage: str, result: Any):
        """保存阶段结果"""
        self.results[stage] = {
            "data": result,
            "timestamp": datetime.now()
        }
    
    def get_stage_result(self, stage: str) -> Any:
        """获取阶段结果"""
        return self.results.get(stage, {}).get("data")
    
    def get_current_state(self) -> Dict[str, Any]:
        """获取当前执行状态"""
        return {
            "stage": self.current_stage,
            "completed_stages": list(self.results.keys()),
            "request": self.request.dict()
        }
```

#### 流程编排器
```python
class PipelineOrchestrator:
    """流水线编排器"""
    
    def __init__(self, agent: ReactAgent):
        self.agent = agent
        self.stages = self._define_stages()
        
    def _define_stages(self) -> List[PipelineStage]:
        """定义流水线阶段"""
        return [
            # 分析阶段
            PipelineStage(
                name="analysis",
                tasks=[
                    Task("extract_schema", "schema_analyzer"),
                    Task("analyze_domain", "domain_analyzer"),
                    Task("classify_fields", "field_classifier"),
                    Task("analyze_relationships", "relationship_analyzer")
                ]
            ),
            
            # 生成阶段
            PipelineStage(
                name="generation",
                tasks=[
                    Task("generate_scenarios", "scenario_generator"),
                    Task("generate_questions", "question_generator"),
                    Task("generate_sql", "sql_generator")
                ]
            ),
            
            # 验证反思阶段
            PipelineStage(
                name="validation_reflection",
                tasks=[
                    Task("validate_sql", "sql_validator"),
                    Task("execute_sql", "sql_executor"),
                    Task("analyze_execution", "execution_analyzer"),
                    Task("improve_quality", "quality_improver")
                ]
            )
        ]
    
    async def run(self, request: TaskRequest) -> TrainingDataset:
        """执行完整流水线"""
        context = ExecutionContext(request)
        
        for stage in self.stages:
            context.current_stage = stage.name
            
            for task in stage.tasks:
                # Agent会自动处理ReAct循环
                result = await self.agent.run_task(
                    task=f"Execute {task.name}",
                    context=context
                )
                
                context.save_stage_result(task.name, result)
        
        # 组装最终结果
        return self._build_training_dataset(context)
```

### 2.5 提示词管理

#### 提示词组织结构
```
prompts/
├── system.yaml          # 系统级配置
├── tools.yaml           # 工具描述
├── templates/
│   ├── react/          # ReAct模板
│   │   ├── thought.j2
│   │   └── action.j2
│   ├── analysis/       # 分析模板
│   │   ├── domain.j2
│   │   └── schema.j2
│   ├── generation/     # 生成模板
│   │   ├── scenario.j2
│   │   ├── question.j2
│   │   └── sql.j2
│   └── reflection/     # 反思模板
│       ├── execution.j2
│       └── quality.j2
```

#### 提示词加载器
```python
class PromptLoader:
    """提示词加载和管理"""
    
    def __init__(self, prompt_dir: str):
        self.prompt_dir = Path(prompt_dir)
        self.env = Environment(loader=FileSystemLoader(prompt_dir))
        self.cache = {}
        
    def get_prompt(self, template_path: str, **kwargs) -> str:
        """获取渲染后的提示词"""
        template = self.env.get_template(f"{template_path}.j2")
        return template.render(**kwargs)
    
    def get_tool_description(self, tool_name: str) -> str:
        """获取工具描述"""
        tools_config = self._load_yaml("tools.yaml")
        return tools_config.get(tool_name, {}).get("description", "")
```

## 3. 执行流程

### 3.1 完整执行流程
```
1. CLI接收命令
    ↓
2. 创建TaskRequest
    ↓
3. 初始化Pipeline
    ↓
4. 执行分析阶段
    - 提取数据库结构 (ReAct循环)
    - 分析业务领域 (ReAct循环)
    - 分类字段 (ReAct循环)
    - 分析关系 (ReAct循环)
    ↓
5. 执行生成阶段
    - 生成场景 (ReAct循环)
    - 生成问题 (ReAct循环)  
    - 生成SQL (ReAct循环, 一步完成)
    ↓
6. 执行验证反思阶段
    - 验证SQL (ReAct循环)
    - 执行SQL (ReAct循环)
    - 分析结果 (ReAct循环)
    - 优化改进 (ReAct循环)
    ↓
7. 输出TrainingDataset
```

### 3.2 ReAct循环示例
```
任务: 生成SQL查询

Step 1:
  Thought: 我需要根据问题"查询最近30天的活跃用户"生成SQL
  Action: sql_generator with {question: "...", schema: {...}}
  Observation: Generated SQL: "SELECT DISTINCT user_id FROM orders WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)"

Step 2:  
  Thought: SQL已生成，但需要验证其正确性
  Action: sql_validator with {sql: "...", schema: {...}}
  Observation: Validation passed, no syntax errors

Step 3:
  Thought: SQL语法正确，现在执行测试
  Action: sql_executor with {sql: "...", limit: 10}
  Observation: Execution successful, returned 8 rows in 0.023s

Step 4:
  Thought: 执行成功但速度较快，检查是否需要优化
  Action: execution_analyzer with {sql: "...", execution_result: {...}}
  Observation: No optimization needed, query is efficient

Step 5:
  Thought: 任务完成，SQL查询有效且高效
  [Task Complete]
```

## 4. 关键设计决策

### 4.1 为什么不需要thinking_tools
- Think是ReAct模式的一部分，在Agent层实现
- 每个工具调用前都会有Think步骤
- 不需要独立的思考工具

### 4.2 SQL工具分离的原因
- 执行和验证是两个独立的关注点
- 验证不一定需要执行
- 执行可能用于其他目的（如测试）

### 4.3 反思vs思考的区别
- 思考(Think): ReAct中的推理步骤，决定下一个行动
- 反思(Reflection): 执行后的质量分析和改进
- 两者目的和时机完全不同

### 4.4 轨迹记录位置
- 在Agent层记录，因为ReAct循环在这里
- 每个Think-Act-Observe都被记录
- 提供完整的执行历史

## 5. 扩展性设计

### 5.1 添加新工具
```python
# 1. 创建工具类
class NewAnalysisTool(BaseTool):
    name = "new_analyzer"
    description = "新的分析工具"
    
    def get_input_schema(self):
        return NewAnalysisInput
    
    async def run(self, **kwargs):
        # 实现逻辑
        pass

# 2. 注册到工具列表
tools = [
    # ... existing tools
    NewAnalysisTool()
]

# 3. 在流水线中使用
# 在stages定义中添加新任务
```

### 5.2 自定义Agent行为
```python
class CustomReactAgent(ReactAgent):
    """自定义ReAct行为"""
    
    async def _think(self, task, context, trace):
        # 自定义思考逻辑
        # 可以加入领域知识
        pass
    
    def _is_task_complete(self, observation):
        # 自定义完成判断
        pass
```

## 6. 性能和监控

### 6.1 性能优化点
- 工具结果缓存
- 并行执行独立任务
- 批量处理相似请求
- LLM调用优化

### 6.2 监控指标
- 每个阶段耗时
- ReAct步骤数量
- 工具调用成功率
- 生成质量分数

## 7. 最佳实践

1. **工具设计**: 单一职责，清晰接口
2. **提示词管理**: 版本控制，模板化
3. **错误处理**: 优雅降级，详细日志
4. **测试策略**: 单元测试工具，集成测试流水线
5. **文档规范**: 工具必须有清晰描述和示例