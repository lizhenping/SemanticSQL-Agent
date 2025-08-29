# SemanticSQL Agent 项目结构设计 V2

## 1. 重新思考的关键问题

### 1.1 模型定义完整性
需要覆盖整个流程的数据模型，包括：
- 输入模型（数据库配置、任务请求）
- 中间状态模型（分析结果、生成结果）
- 输出模型（训练数据集）
- 执行跟踪模型（ReAct步骤记录）

### 1.2 验证工具设计
- SQL执行工具应该独立存在（在sql_tools中）
- 验证工具只负责验证，不执行
- 避免功能重复

### 1.3 ReAct模式实现
- 思考(Thought)是ReAct的一部分，不需要独立的thinking_tools
- 反思(Reflection)是执行后的改进，与ReAct的思考不同
- 需要在Agent层实现ReAct循环

### 1.4 提示词组织
- 按功能而非类型组织
- 每个工具对应的提示词应该清晰
- 系统提示词独立管理

### 1.5 轨迹记录
- 应该在Agent层实现，而非callbacks
- 记录每个ReAct步骤（Thought, Action, Observation）

## 2. 优化后的项目结构

```
semanticsql-agent/
├── config/
│   ├── __init__.py
│   ├── settings.py              # 全局配置
│   └── database.py              # 数据库配置
│
├── core/                        # 核心模块
│   ├── __init__.py
│   ├── models.py                # 所有Pydantic模型定义
│   ├── exceptions.py            # 自定义异常
│   └── constants.py             # 常量定义
│
├── tools/
│   ├── __init__.py
│   ├── base.py                  # 工具基类
│   │
│   ├── analysis/                # 分析工具
│   │   ├── __init__.py
│   │   ├── schema_analyzer.py          # 数据库结构分析
│   │   ├── domain_analyzer.py          # 领域识别
│   │   ├── field_classifier.py         # 字段分类
│   │   └── relationship_analyzer.py    # 关系分析
│   │
│   ├── generation/              # 生成工具
│   │   ├── __init__.py
│   │   ├── scenario_generator.py       # 场景生成
│   │   ├── question_generator.py       # 问题生成
│   │   └── sql_generator.py           # SQL生成
│   │
│   ├── sql/                     # SQL操作工具
│   │   ├── __init__.py
│   │   ├── sql_executor.py            # SQL执行
│   │   ├── sql_validator.py           # SQL语法验证
│   │   └── sql_optimizer.py           # SQL优化建议
│   │
│   └── reflection/              # 反思改进工具
│       ├── __init__.py
│       ├── execution_analyzer.py      # 执行结果分析
│       └── quality_improver.py        # 质量改进建议
│
├── prompts/
│   ├── __init__.py
│   ├── system.yaml              # 系统级提示词
│   ├── tools.yaml               # 工具提示词配置
│   ├── templates/               # 提示词模板
│   │   ├── analysis.j2         # 分析类模板
│   │   ├── generation.j2       # 生成类模板
│   │   └── reflection.j2       # 反思类模板
│   └── loader.py                # 提示词加载器
│
├── agent/
│   ├── __init__.py
│   ├── base_agent.py            # ReAct基础Agent
│   ├── sql_agent.py             # SQL生成Agent
│   ├── planner.py               # 任务规划器
│   └── executor.py              # 执行器（含轨迹记录）
│
├── pipeline/                    # 流水线
│   ├── __init__.py
│   ├── stages.py                # 流水线阶段定义
│   ├── orchestrator.py          # 流程编排器
│   └── context.py               # 执行上下文
│
├── utils/
│   ├── __init__.py
│   ├── database.py              # 数据库工具
│   ├── logger.py                # 日志工具
│   └── helpers.py               # 辅助函数
│
├── output/                      # 输出处理
│   ├── __init__.py
│   ├── formatter.py             # 结果格式化
│   └── exporter.py              # 导出器
│
└── cli.py                       # 命令行接口
```

## 3. 核心模型定义 (core/models.py)

```python
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum

# ========== 枚举类型 ==========
class DatabaseType(str, Enum):
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"

class DifficultyLevel(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

class SQLType(str, Enum):
    SELECT = "select"
    JOIN = "join"
    AGGREGATE = "aggregate"
    SUBQUERY = "subquery"
    WINDOW = "window"

# ========== 输入模型 ==========
class TaskRequest(BaseModel):
    """任务请求"""
    database_config: Dict[str, Any]
    target_count: int = 100  # 目标生成数量
    difficulty_distribution: Dict[DifficultyLevel, float] = {
        DifficultyLevel.EASY: 0.3,
        DifficultyLevel.MEDIUM: 0.5,
        DifficultyLevel.HARD: 0.2
    }

# ========== 分析阶段模型 ==========
class TableInfo(BaseModel):
    """表信息"""
    name: str
    columns: List[Dict[str, Any]]
    primary_key: Optional[str]
    foreign_keys: List[Dict[str, str]]
    row_count: Optional[int]

class SchemaAnalysis(BaseModel):
    """数据库结构分析结果"""
    database_name: str
    database_type: DatabaseType
    tables: List[TableInfo]
    total_tables: int
    extracted_at: datetime

class DomainAnalysis(BaseModel):
    """领域分析结果"""
    domain: str
    confidence: float
    key_entities: List[str]
    business_features: List[str]
    domain_keywords: List[str]

class FieldClassification(BaseModel):
    """字段分类结果"""
    identifiers: List[str]
    timestamps: List[str]
    numerics: List[str]
    categoricals: List[str]
    descriptive: List[str]
    
class RelationshipAnalysis(BaseModel):
    """关系分析结果"""
    relationships: List[Dict[str, Any]]
    relationship_graph: Dict[str, List[str]]
    junction_tables: List[str]

# ========== 生成阶段模型 ==========
class QueryScenario(BaseModel):
    """查询场景"""
    id: str
    category: str
    business_purpose: str
    data_requirements: List[str]
    complexity: DifficultyLevel
    applicable_tables: List[str]

class GeneratedQuestion(BaseModel):
    """生成的问题"""
    id: str
    scenario_id: str
    question_text: str
    question_type: str
    expected_result_type: str
    complexity: DifficultyLevel

class GeneratedSQL(BaseModel):
    """生成的SQL"""
    id: str
    question_id: str
    sql_query: str
    sql_type: SQLType
    tables_used: List[str]
    columns_used: List[str]
    has_join: bool
    has_aggregation: bool
    has_subquery: bool

# ========== 验证和反思模型 ==========
class ExecutionResult(BaseModel):
    """SQL执行结果"""
    sql_id: str
    success: bool
    execution_time: float
    row_count: int
    error_message: Optional[str]
    sample_data: Optional[List[Dict]]

class ValidationResult(BaseModel):
    """验证结果"""
    sql_id: str
    syntax_valid: bool
    semantic_valid: bool
    performance_score: float
    issues: List[str]

class ReflectionResult(BaseModel):
    """反思结果"""
    sql_id: str
    quality_score: float
    improvement_suggestions: List[str]
    optimized_sql: Optional[str]
    learning_points: List[str]

# ========== ReAct执行模型 ==========
class ThoughtStep(BaseModel):
    """思考步骤"""
    content: str
    timestamp: datetime

class ActionStep(BaseModel):
    """行动步骤"""
    tool_name: str
    tool_input: Dict[str, Any]
    timestamp: datetime

class ObservationStep(BaseModel):
    """观察步骤"""
    tool_output: Any
    success: bool
    error: Optional[str]
    timestamp: datetime

class ReactStep(BaseModel):
    """ReAct步骤"""
    step_number: int
    thought: ThoughtStep
    action: ActionStep
    observation: ObservationStep

class ExecutionTrace(BaseModel):
    """执行轨迹"""
    task_id: str
    started_at: datetime
    completed_at: Optional[datetime]
    steps: List[ReactStep]
    final_result: Optional[Any]
    status: str  # running, completed, failed

# ========== 最终输出模型 ==========
class TrainingExample(BaseModel):
    """单个训练样本"""
    question: GeneratedQuestion
    sql: GeneratedSQL
    validation: ValidationResult
    execution: ExecutionResult
    quality_score: float

class TrainingDataset(BaseModel):
    """完整的训练数据集"""
    dataset_id: str
    created_at: datetime
    database_info: SchemaAnalysis
    domain_info: DomainAnalysis
    examples: List[TrainingExample]
    statistics: Dict[str, Any]
```

## 4. 工具系统重新设计

### 4.1 SQL工具分离
```python
# tools/sql/sql_executor.py
class SQLExecutor(BaseTool):
    """纯SQL执行工具，不做验证"""
    name = "sql_executor"
    description = "执行SQL查询并返回结果"
    
    def run(self, sql: str, limit: int = 100) -> ExecutionResult:
        # 只负责执行
        pass

# tools/sql/sql_validator.py
class SQLValidator(BaseTool):
    """SQL验证工具，不执行"""
    name = "sql_validator"
    description = "验证SQL语法和语义正确性"
    
    def run(self, sql: str, schema: SchemaAnalysis) -> ValidationResult:
        # 只负责验证
        pass
```

### 4.2 反思工具明确定位
```python
# tools/reflection/execution_analyzer.py
class ExecutionAnalyzer(BaseTool):
    """分析执行结果，提供改进建议"""
    name = "execution_analyzer"
    description = "分析SQL执行结果并提供优化建议"
    
    def run(self, sql: str, execution_result: ExecutionResult) -> ReflectionResult:
        # 不是ReAct的思考，而是执行后的分析
        pass
```

## 5. ReAct模式实现

### 5.1 在Agent层实现
```python
# agent/base_agent.py
class ReactAgent:
    """ReAct模式基础Agent"""
    
    def __init__(self, tools: List[BaseTool], llm_client: Any):
        self.tools = {tool.name: tool for tool in tools}
        self.llm = llm_client
        self.execution_trace = ExecutionTrace()
    
    def think(self, context: str) -> ThoughtStep:
        """生成思考"""
        prompt = self.build_thought_prompt(context)
        thought = self.llm.generate(prompt)
        return ThoughtStep(content=thought, timestamp=datetime.now())
    
    def act(self, thought: str) -> ActionStep:
        """决定行动"""
        prompt = self.build_action_prompt(thought)
        action = self.llm.generate(prompt)
        tool_name, tool_input = self.parse_action(action)
        return ActionStep(
            tool_name=tool_name,
            tool_input=tool_input,
            timestamp=datetime.now()
        )
    
    def observe(self, action: ActionStep) -> ObservationStep:
        """执行并观察"""
        tool = self.tools[action.tool_name]
        try:
            output = tool.run(**action.tool_input)
            return ObservationStep(
                tool_output=output,
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
    
    def run_step(self, context: str) -> ReactStep:
        """执行一个完整的ReAct步骤"""
        thought = self.think(context)
        action = self.act(thought.content)
        observation = self.observe(action)
        
        step = ReactStep(
            step_number=len(self.execution_trace.steps) + 1,
            thought=thought,
            action=action,
            observation=observation
        )
        
        self.execution_trace.steps.append(step)
        return step
```

## 6. 流水线设计

### 6.1 执行上下文
```python
# pipeline/context.py
class ExecutionContext:
    """流水线执行上下文"""
    
    def __init__(self, task_request: TaskRequest):
        self.request = task_request
        self.results = {}  # 存储各阶段结果
        self.current_stage = None
        self.start_time = datetime.now()
    
    def save_result(self, stage: str, result: Any):
        """保存阶段结果"""
        self.results[stage] = result
    
    def get_result(self, stage: str) -> Any:
        """获取阶段结果"""
        return self.results.get(stage)
```

### 6.2 流程编排
```python
# pipeline/orchestrator.py
class PipelineOrchestrator:
    """流水线编排器"""
    
    def __init__(self, agent: ReactAgent):
        self.agent = agent
        self.stages = self._define_stages()
    
    def _define_stages(self):
        return [
            # 分析阶段
            ("schema_analysis", ["schema_analyzer"]),
            ("domain_analysis", ["domain_analyzer"]),
            ("field_classification", ["field_classifier"]),
            ("relationship_analysis", ["relationship_analyzer"]),
            
            # 生成阶段
            ("scenario_generation", ["scenario_generator"]),
            ("question_generation", ["question_generator"]),
            ("sql_generation", ["sql_generator"]),
            
            # 验证反思阶段
            ("sql_validation", ["sql_validator"]),
            ("sql_execution", ["sql_executor"]),
            ("quality_reflection", ["execution_analyzer", "quality_improver"])
        ]
    
    def run(self, context: ExecutionContext):
        """执行完整流水线"""
        for stage_name, tools in self.stages:
            context.current_stage = stage_name
            
            for tool_name in tools:
                # Agent会自动执行ReAct循环
                result = self.agent.run_task(
                    task=f"Execute {tool_name} for {stage_name}",
                    context=context
                )
                context.save_result(f"{stage_name}_{tool_name}", result)
```

## 7. 提示词管理优化

```yaml
# prompts/system.yaml
agent:
  system_prompt: |
    You are an SQL training data generation expert.
    Follow the ReAct pattern: Thought -> Action -> Observation.
    
react:
  thought_template: |
    Based on the current context: {context}
    What should I do next to achieve: {goal}
    
  action_template: |
    Given my thought: {thought}
    Which tool should I use and with what parameters?

# prompts/tools.yaml
tools:
  schema_analyzer:
    description: "Extract database schema information"
    prompt_template: |
      Analyze the database structure and extract:
      - Table names and purposes
      - Column information
      - Constraints and relationships
      
  scenario_generator:
    description: "Generate query scenarios based on domain"
    prompt_template: |
      Based on domain: {domain}
      And tables: {tables}
      Generate business scenarios that require SQL queries
```

## 8. 关键改进总结

1. **模型完整性**：覆盖了整个流程的所有数据模型
2. **工具职责清晰**：SQL执行和验证分离，避免重复
3. **ReAct实现正确**：在Agent层实现，不需要thinking_tools
4. **反思定位明确**：是执行后的质量改进，不是ReAct的思考
5. **轨迹记录合理**：在Agent执行过程中自动记录
6. **提示词组织优化**：按功能组织，结构清晰

这个设计更加合理，避免了概念混淆和功能重复。