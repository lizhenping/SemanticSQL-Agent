# SemanticSQL Agent 架构文档

## 1. 系统架构概览

### 1.1 架构原则
- **模块化设计**：清晰的模块划分，职责单一
- **工具驱动**：通过专业工具完成各项任务
- **反思机制**：执行后反思，持续优化生成质量
- **配置灵活**：支持多环境、多数据库配置

### 1.2 技术栈
- **编程语言**: Python 3.8+
- **核心框架**:
  - LangChain: Agent 框架
  - SQLAlchemy: 数据库操作
  - Pydantic: 数据模型验证
  - Jinja2: 提示词模板
  - Click: CLI 框架
- **LLM支持**: Qwen (OpenAI 兼容 API)

## 2. 项目结构设计

```
semanticsql-agent/
├── config/
│   ├── __init__.py
│   ├── settings.py              # 全局配置
│   └── database.py              # 数据库配置
│
├── models/
│   ├── __init__.py
│   └── schemas.py               # Pydantic 模型定义
│
├── tools/
│   ├── __init__.py
│   ├── base_tool.py                  # 工具基类
│   │
│   ├── analysis_tools/          # 分析工具（可重新执行更新记忆）
│   │   ├── __init__.py
│   │   ├── schema_extraction_tool.py    # 数据库结构提取
│   │   ├── domain_analysis_tool.py      # 业务领域分析
│   │   ├── field_classification_tool.py # 字段语义分类
│   │   └── er_analysis_tool.py          # 实体关系分析
│   │
│   ├── generation_tools/        # 生成工具
│   │   ├── __init__.py
│   │   ├── scenario_tool.py             # 场景生成（基于预定义模板）
│   │   ├── operation_selection_tool.py  # 操作选择（基于预定义规则）
│   │   ├── question_generation_tool.py  # 问题生成（使用场景+操作+记忆）
│   │   └── sql_generation_tool.py       # SQL生成（使用问题+记忆）
│   │
│   ├── validation_tools/        # 验证工具
│   │   ├── __init__.py
│   │   ├── sql_validation_tool.py       # SQL验证
│   │   └── sql_execution_tool.py        # SQL执行测试
│   │
│   ├── reflection_tools/        # 反思工具
│   │   ├── __init__.py
│   │   └── sql_reflection_tool.py       # SQL执行反思（评估质量和问题诊断）
│   │
│   └── thinking_tools/          # 思考工具
│       ├── __init__.py
│       └── sequential_thinking_tool.py   # 深度思考（分析问题源头和修正策略）
│
├── prompts/
│   ├── __init__.py
│   ├── templates/              # Jinja2 模板
│   │   ├── system/             # 系统提示词
│   │   ├── tools/              # 工具描述
│   │   └── analysis/           # 分析提示词
│   └── manager.py              # 提示词管理器
│
├── agent/
│   ├── __init__.py
│   ├── base_agent.py           # 基础Agent（含执行记录和记忆管理）
│   ├── smart_sql_agent.py      # 主SQL Agent（用于SQL查询生成）
│   ├── data_generation_agent.py # 数据生成Agent（用于批量生成训练数据）
│   └── callbacks.py            # 执行回调（轨迹记录等）
│
├── utils/
│   ├── __init__.py
│   ├── database.py              # 数据库连接管理
│   ├── llm_client.py            # LLM客户端（支持使用标准OpenAI库调用Qwen）
│   └── trajectory.py            # 执行轨迹记录（保存每次执行的完整过程）
│
└── cli.py                       # 命令行接口
```

## 3. 核心组件详解

### 3.1 配置管理 (config/)

#### settings.py - 全局配置
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """全局配置"""
    # 应用配置
    app_name: str = "SemanticSQL Agent"
    debug: bool = False
    
    # LLM配置
    llm_model: str = "Qwen3-14B"
    llm_base_url: str = "http://localhost:9991/v1"
    llm_api_key: str = "not-needed"
    llm_temperature: float = 0.7
    
    # Agent配置
    max_iterations: int = 20
    enable_reflection: bool = True
    
    class Config:
        env_file = ".env"
```

#### database.py - 数据库配置
```python
from pydantic import BaseModel

class DatabaseConfig(BaseModel):
    """数据库配置"""
    type: str  # mysql
    host: str
    port: int
    database: str
    username: str
    password: str
    pool_size: int = 5
```

### 3.2 数据模型 (models/)

#### schemas.py - 核心数据模型
```python
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime

class TableSchema(BaseModel):
    """表结构模型"""
    name: str
    columns: List[Dict[str, str]]
    primary_key: Optional[str]
    foreign_keys: List[Dict[str, str]]

class DomainAnalysis(BaseModel):
    """领域分析结果"""
    domain: str
    confidence: float
    key_entities: List[str]
    business_features: List[str]

class QueryScenario(BaseModel):
    """查询场景"""
    id: str
    category: str
    description: str
    difficulty: str
    business_value: str

class GeneratedQuestion(BaseModel):
    """生成的问题"""
    scenario_id: str
    question: str
    question_type: str
    complexity: str

class GeneratedSQL(BaseModel):
    """生成的SQL"""
    question_id: str
    sql: str
    tables_used: List[str]
    sql_type: str  # SELECT/JOIN/AGGREGATE等

class ValidationResult(BaseModel):
    """验证结果"""
    sql_id: str
    is_valid: bool
    execution_time: Optional[float]
    row_count: Optional[int]
    error_message: Optional[str]

class ReflectionResult(BaseModel):
    """反思结果"""
    original_sql: str
    issues: List[str]
    suggestions: List[str]
    improved_sql: Optional[str]
```

### 3.3 工具系统 (tools/)

#### 基类设计 (base.py)
```python
from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Any, Dict, List

class ToolInput(BaseModel):
    """工具输入基类"""
    pass

class ToolOutput(BaseModel):
    """工具输出基类"""
    success: bool
    data: Any
    error: Optional[str]

class BaseTool(ABC):
    """工具基类"""
    name: str
    description: str
    
    @abstractmethod
    def get_input_schema(self) -> type[ToolInput]:
        """获取输入模式"""
        pass
    
    @abstractmethod
    def run(self, input_data: ToolInput) -> ToolOutput:
        """执行工具"""
        pass
```

#### 分析工具 (analysis_tools/)

**1. schema_extraction_tool.py**
```python
class SchemaExtractionTool(BaseTool):
    """数据库结构提取工具"""
    name = "schema_extraction"
    description = "提取数据库表结构、字段信息、约束关系"
    
    def run(self, input_data: DatabaseConfig) -> SchemaOutput:
        # 连接数据库
        # 提取所有表信息
        # 提取字段信息
        # 提取约束关系
        return SchemaOutput(tables=tables)
```

**2. domain_analysis_tool.py**
```python
class DomainAnalysisTool(BaseTool):
    """领域分析工具"""
    name = "domain_analysis"
    description = "基于表名、字段名分析业务领域"
    
    def run(self, input_data: SchemaInput) -> DomainOutput:
        # 分析表名模式
        # 识别业务关键词
        # 判断领域类型
        return DomainOutput(domain=domain, confidence=0.95)
```

**3. field_classification_tool.py**
```python
class FieldClassificationTool(BaseTool):
    """字段分类工具"""
    name = "field_classification"
    description = "对数据库字段进行语义分类"
    
    def run(self, input_data: FieldsInput) -> ClassificationOutput:
        # 识别ID字段
        # 识别时间字段
        # 识别金额字段
        # 识别状态字段
        return ClassificationOutput(classifications=results)
```

**4. er_analysis_tool.py**
```python
class ERAnalysisTool(BaseTool):
    """实体关系分析工具"""
    name = "er_analysis"
    description = "分析表之间的关联关系"
    
    def run(self, input_data: TablesInput) -> EROutput:
        # 分析外键关系
        # 推断隐式关系
        # 构建ER图
        return EROutput(relationships=relationships)
```

#### 生成工具 (generation_tools/)

**1. scenario_generation_tool.py**
```python
class ScenarioGenerationTool(BaseTool):
    """场景生成工具"""
    name = "scenario_generation"
    description = "基于领域和表结构生成查询场景"
    
    def run(self, input_data: AnalysisResults) -> ScenariosOutput:
        # 根据领域选择场景模板
        # 基于表结构生成具体场景
        # 分配难度等级
        scenarios = self._generate_scenarios(
            domain=input_data.domain,
            tables=input_data.tables,
            relationships=input_data.relationships
        )
        return ScenariosOutput(scenarios=scenarios)
    
    def _generate_scenarios(self, domain, tables, relationships):
        """基于规则生成场景"""
        templates = self._get_domain_templates(domain)
        scenarios = []
        
        for template in templates:
            scenario = QueryScenario(
                id=generate_id(),
                category=template.category,
                description=template.render(tables=tables),
                difficulty=template.difficulty,
                business_value=template.value
            )
            scenarios.append(scenario)
            
        return scenarios
```

**2. question_generation_tool.py**
```python
class QuestionGenerationTool(BaseTool):
    """问题生成工具"""
    name = "question_generation"
    description = "基于场景生成自然语言问题"
    
    def run(self, input_data: ScenarioInput) -> QuestionsOutput:
        questions = []
        
        for scenario in input_data.scenarios:
            # 基于场景生成多个问题变体
            question_variants = self._generate_questions(scenario)
            questions.extend(question_variants)
            
        return QuestionsOutput(questions=questions)
    
    def _generate_questions(self, scenario):
        """为一个场景生成多个问题"""
        templates = self._get_question_templates(scenario.category)
        questions = []
        
        for template in templates:
            question = GeneratedQuestion(
                scenario_id=scenario.id,
                question=template.render(scenario=scenario),
                question_type=template.type,
                complexity=scenario.difficulty
            )
            questions.append(question)
            
        return questions
```

**3. sql_generation_tool.py**
```python
class SQLGenerationTool(BaseTool):
    """SQL生成工具"""
    name = "sql_generation"
    description = "根据问题生成SQL查询"
    
    def run(self, input_data: QuestionSQLInput) -> SQLOutput:
        # 一步生成SQL
        sql = self._generate_sql(
            question=input_data.question,
            schema=input_data.schema,
            context=input_data.context
        )
        
        return SQLOutput(
            sql=GeneratedSQL(
                question_id=input_data.question.id,
                sql=sql,
                tables_used=self._extract_tables(sql),
                sql_type=self._classify_sql(sql)
            )
        )
```

#### 验证工具 (validation_tools/)

**1. sql_validation_tool.py**
```python
class SQLValidationTool(BaseTool):
    """SQL验证工具"""
    name = "sql_validation"
    description = "验证SQL语法和逻辑正确性"
    
    def run(self, input_data: SQLValidationInput) -> ValidationOutput:
        # 语法检查
        # 表名字段验证
        # 逻辑合理性检查
        return ValidationOutput(is_valid=True, issues=[])
```

**2. sql_execution_tool.py**
```python
class SQLExecutionTool(BaseTool):
    """SQL执行测试工具"""
    name = "sql_execution"
    description = "执行SQL并获取结果"
    
    def run(self, input_data: SQLExecutionInput) -> ExecutionOutput:
        # 执行SQL
        # 记录执行时间
        # 获取结果行数
        return ExecutionOutput(
            success=True,
            execution_time=0.125,
            row_count=42
        )
```

#### 反思工具 (reflection_tools/)

**sql_reflection_tool.py**
```python
class SQLReflectionTool(BaseTool):
    """SQL反思工具"""
    name = "sql_reflection"
    description = "根据执行结果反思SQL质量并提出改进"
    
    def run(self, input_data: ReflectionInput) -> ReflectionOutput:
        reflection = ReflectionResult(
            original_sql=input_data.sql,
            issues=[],
            suggestions=[]
        )
        
        # 分析执行时间
        if input_data.execution_time > 1.0:
            reflection.issues.append("查询时间过长")
            reflection.suggestions.append("考虑添加索引或优化查询")
        
        # 分析结果集大小
        if input_data.row_count > 10000:
            reflection.issues.append("结果集过大")
            reflection.suggestions.append("考虑添加分页或限制")
        
        # 分析SQL复杂度
        complexity_issues = self._analyze_complexity(input_data.sql)
        reflection.issues.extend(complexity_issues)
        
        # 生成改进的SQL
        if reflection.issues:
            reflection.improved_sql = self._improve_sql(
                input_data.sql,
                reflection.suggestions
            )
        
        return ReflectionOutput(reflection=reflection)
```

### 3.4 提示词管理 (prompts/)

#### 模板结构
```
templates/
├── system/
│   ├── agent_system.j2         # Agent系统提示词
│   └── tool_system.j2          # 工具系统提示词
├── tools/
│   ├── analysis/               # 分析工具提示词
│   ├── generation/             # 生成工具提示词
│   └── reflection/             # 反思工具提示词
└── analysis/
    ├── domain_analysis.j2      # 领域分析提示词
    └── scenario_analysis.j2    # 场景分析提示词
```

#### manager.py - 提示词管理器
```python
from jinja2 import Environment, FileSystemLoader

class PromptManager:
    """提示词管理器"""
    
    def __init__(self, template_dir: str):
        self.env = Environment(
            loader=FileSystemLoader(template_dir)
        )
    
    def get_prompt(self, template_name: str, **kwargs) -> str:
        """获取渲染后的提示词"""
        template = self.env.get_template(template_name)
        return template.render(**kwargs)
```

### 3.5 Agent 实现 (agent/)

#### sql_agent.py - 主Agent
```python
from langchain.agents import AgentExecutor
from langchain.tools import Tool

class SQLAgent:
    """SQL生成Agent"""
    
    def __init__(self, config: Settings):
        self.config = config
        self.tools = self._initialize_tools()
        self.agent = self._create_agent()
        
    def _initialize_tools(self) -> List[Tool]:
        """初始化所有工具"""
        tools = []
        
        # 分析工具
        tools.extend([
            SchemaExtractionTool(),
            DomainAnalysisTool(),
            FieldClassificationTool(),
            ERAnalysisTool()
        ])
        
        # 生成工具
        tools.extend([
            ScenarioGenerationTool(),
            QuestionGenerationTool(),
            SQLGenerationTool()
        ])
        
        # 验证和反思工具
        tools.extend([
            SQLValidationTool(),
            SQLExecutionTool(),
            SQLReflectionTool()
        ])
        
        return tools
    
    def generate_training_data(self, database_config: DatabaseConfig):
        """生成训练数据的主流程"""
        # 1. 分析阶段
        schema = self.extract_schema(database_config)
        domain = self.analyze_domain(schema)
        fields = self.classify_fields(schema)
        relationships = self.analyze_er(schema)
        
        # 2. 生成阶段
        scenarios = self.generate_scenarios(domain, schema, relationships)
        questions = self.generate_questions(scenarios)
        sql_queries = self.generate_sql(questions, schema)
        
        # 3. 验证和反思阶段
        validated_queries = []
        for sql in sql_queries:
            validation = self.validate_sql(sql)
            if validation.is_valid:
                execution = self.execute_sql(sql)
                reflection = self.reflect_on_sql(sql, execution)
                
                if reflection.improved_sql:
                    sql.sql = reflection.improved_sql
                    
                validated_queries.append(sql)
        
        return TrainingData(
            questions=questions,
            sql_queries=validated_queries
        )
```

## 4. 执行流程

### 4.1 智能体驱动流程图
```
用户任务："生成N条训练数据"
    ↓
┌─────────────────────────────────────┐
│          ReAct 智能决策循环          │
├─────────────────────────────────────┤
│ Agent Thought: "我需要先了解数据库"  │
│ Agent Action: extract_schema        │
│ Agent Observation: [数据库结构]     │
│ ├─────────────────────────────────  │
│ Agent Thought: "分析业务领域特征"   │
│ Agent Action: domain_analysis       │
│ Agent Observation: [领域信息]       │
│ ├─────────────────────────────────  │
│ Agent Thought: "现在生成查询场景"   │
│ Agent Action: scenario_generation   │
│ Agent Observation: [业务场景]       │
│ ├─────────────────────────────────  │
│ Agent Thought: "为场景生成问题"     │
│ Agent Action: question_generation   │
│ Agent Observation: [自然语言问题]   │
│ ├─────────────────────────────────  │
│ Agent Thought: "生成对应的SQL"      │
│ Agent Action: sql_generation        │
│ Agent Observation: [SQL查询]        │
│ ├─────────────────────────────────  │
│ Agent Thought: "执行SQL验证"        │
│ Agent Action: sql_execution         │
│ Agent Observation: [执行结果]       │
│ ├─────────────────────────────────  │
│ Agent Thought: "反思结果质量"       │
│ Agent Action: sql_reflection        │
│ Agent Observation: [反思分析]       │
│ ├─────────────────────────────────  │
│ Agent Thought: "继续生成更多..."    │
│ [重复上述循环直到完成N条数据]        │
│ ├─────────────────────────────────  │
│ Agent Thought: "任务完成，输出数据" │
│ Agent Action: finish                │
└─────────────────────────────────────┘
                ↓
        输出训练数据文件
```

### 4.2 智能体自主决策特点

#### 动态策略调整
- **数据库复杂度适应**：Agent根据表的数量和复杂度调整生成策略
- **领域特征识别**：自动识别业务特征，生成相关场景
- **质量反馈循环**：根据执行结果自主决定是否重新生成

#### 智能工具协调
```
Agent思考："这个数据库是电商领域的，我应该生成订单、用户、商品相关的查询场景"
↓
Agent行动：scenario_generation(domain="ecommerce", focus="orders,users,products")
↓
Agent观察：生成了10个电商场景
↓
Agent思考："现在为每个场景生成多样化的问题"
↓
Agent行动：question_generation(scenarios=scenarios, variety=high)
...
```

#### 执行后反思机制
```
Agent执行SQL → 获得结果 → 自主分析：
- 执行时间是否合理？
- 结果集大小是否适中？
- SQL复杂度是否匹配问题？
- 是否需要优化或重新生成？
```

### 4.2 执行流程详解

#### 阶段一：数据库智能分析（1-4步）
**目标**：全面理解数据库结构和业务特征

1. **extract_schema**：提取完整的数据库结构
   - 表信息：表名、列定义、主键、外键、索引
   - 约束信息：NOT NULL、UNIQUE、CHECK约束
   - 统计信息：表行数、列分布、数据类型分布

2. **domain_analysis**：识别业务领域
   - 基于表名模式识别（如：user_*, order_*, product_*）
   - 基于字段名语义识别（如：price → 电商，patient_id → 医疗）
   - 返回领域标签和置信度

3. **field_classification**：字段语义分类
   - 标识符字段：ID、编号、代码类
   - 时间字段：创建时间、更新时间、业务时间
   - 数值字段：金额、数量、得分、比率
   - 分类字段：状态、类型、级别
   - 描述字段：名称、描述、备注

4. **er_analysis**：实体关系分析
   - 显式关系：基于外键约束
   - 隐式关系：基于命名模式推断
   - 关系类型：一对一、一对多、多对多
   - 关系强度：强关系、弱关系

#### 阶段二：场景化数据生成（5-8步）
**目标**：基于分析结果生成多样化的查询场景和问题

5. **scenario_generation**：业务场景生成
   - 基于领域选择场景模板
   - 根据表关系生成关联场景
   - 按难度分布生成不同复杂度场景

6. **operation_selection**：SQL操作类型选择
   - 基础查询：SELECT、WHERE、ORDER BY
   - 关联查询：JOIN、子查询
   - 聚合查询：GROUP BY、聚合函数
   - 高级查询：窗口函数、CTE、UNION

7. **question_generation**：自然语言问题生成
   - 基于场景模板生成问题变体
   - 确保问题表述自然流畅
   - 涵盖不同问题类型和表达方式

8. **sql_generation**：对应SQL查询生成
   - 一步到位生成完整SQL
   - 确保SQL与问题语义完全匹配
   - 考虑数据库特定语法

#### 阶段三：质量验证与优化（9-12步）
**目标**：确保生成数据的正确性和高质量

9. **sql_validation**：SQL语法和逻辑验证
   - 语法正确性检查
   - 表名和字段名验证
   - 约束条件合理性检查

10. **sql_execution**：实际执行测试
    - 连接数据库执行SQL
    - 记录执行时间和资源消耗
    - 获取结果集信息

11. **sql_reflection**：执行结果智能反思
    - 性能分析：执行时间、资源使用
    - 结果分析：行数、数据分布
    - 质量评估：SQL复杂度、可读性
    - 改进建议：索引优化、查询重写

12. **quality_assessment**：综合质量评分
    - 语法正确性权重：30%
    - 执行成功率权重：25%
    - 语义匹配度权重：25%
    - 性能表现权重：20%

#### 阶段四：数据输出与格式化（13-15步）
**目标**：输出标准化的训练数据集

13. **数据清洗和去重**：移除低质量和重复样本
14. **格式化为训练数据集**：转换为标准training format
15. **输出文件**：保存为JSON/JSONL/CSV格式

**❌ 错误做法**：硬编码执行步骤

以下是**错误的硬编码实现方式**，违背了Agent自主决策原则：

```python
# ❌ 错误：硬编码的固定流程
def generate_training_data(self):
    schema = self.call_tool('extract_schema')    # 硬编码顺序
    domain = self.call_tool('domain_analysis')   # 硬编码顺序
    # ... 更多硬编码步骤
```

**✅ 正确做法**：提示词引导Agent自主决策

```python
class DataGenerationAgent(BaseAgent):
    """
    数据生成Agent - 完全依赖提示词引导的自主决策
    
    核心特点：
    1. 提示词引导：通过精心设计的提示词引导Agent步骤
    2. 自主决策：Agent根据情况自主决定工具调用顺序
    3. 反思循环：执行后反思，发现问题时自主回退修正
    4. 记忆机制：数据库分析结果贯穿整个过程
    """
    
    def __init__(self, settings, db_config):
        # 初始化所有必要的工具
        self._initialize_complete_toolchain()
        # 初始化分析结果记忆
        self.analysis_memory = {}
    
    def _initialize_complete_toolchain(self):
        """初始化完整工具链"""
        # 分析工具
        self.register_tool("extract_schema", ...)
        self.register_tool("domain_analysis", ...)
        self.register_tool("field_classification", ...)
        self.register_tool("er_analysis", ...)
        
        # 生成工具（基于提示词规则）
        self.register_tool("scenario_generation", ...)
        self.register_tool("question_generation", ...)
        self.register_tool("sql_generation", ...)
        
        # 验证工具
        self.register_tool("sql_execution", ...)
        self.register_tool("sql_reflection", ...)
        
        # 思考工具
        self.register_tool("sequential_thinking", ...)
    
    def generate_training_data(self, count: int, output_file: str):
        """
        完全由Agent根据提示词自主执行，无硬编码流程
        """
        task = f"生成{count}条NL2SQL训练数据"
        execution = self.new_task(task)  # 进入ReAct循环
        return self._extract_results(execution)
    
    def get_system_prompt(self) -> str:
        """
        关键：通过提示词引导Agent执行完整流程
        """
        return """
        你是NL2SQL训练数据生成专家。必须按以下原则工作：
        
        🎯 执行原则：
        1. 首先必须完整分析数据库并记忆结果（analysis阶段）
        2. 生成SQL后必须执行验证（execution阶段）
        3. 执行后必须反思分析（reflection阶段）
        4. 反思发现问题时回到相应步骤修正
        5. 复杂情况下调用thinking工具深度分析
        
        📋 可用工具：
        - extract_schema: 提取数据库结构
        - domain_analysis: 分析业务领域
        - field_classification: 字段语义分类
        - er_analysis: 实体关系分析
        - scenario_generation: 场景生成（基于提示词规则）
        - question_generation: 问题生成（基于提示词规则）
        - sql_generation: SQL生成
        - sql_execution: SQL执行验证
        - sql_reflection: 执行结果反思
        - sequential_thinking: 深度思考分析
        
        🔄 反思后修正指导：
        - SQL错误 → 回到sql_generation重新生成
        - 问题不合理 → 回到question_generation重新生成
        - 场景不适合 → 回到scenario_generation重新设计
        - 需要深度分析 → 调用sequential_thinking
        
        记住：数据库分析结果要记忆并在后续步骤中使用！
        """
```

### 4.3 Agent设计指导原则

#### 关键设计原则
```python
# ✅ 正确的Agent设计
class DataGenerationAgent(BaseAgent):
    """
    核心原则：
    1. 提示词驱动：所有步骤由提示词引导，不硬编码
    2. 自主决策：Agent根据情况自主决定工具调用
    3. 记忆机制：分析结果存储在上下文中贯穿使用
    4. 反思循环：执行后必须反思，发现问题主动修正
    5. 思考工具：复杂情况下调用深度思考
    """
    
    def get_system_prompt(self):
        # 返回完整的引导提示词
        # 包含：流程指导、工具使用、反思修正、思考时机
    
    def generate_training_data(self, count, output_file):
        # 只调用 self.new_task() 进入ReAct循环
        # 所有具体步骤由Agent根据提示词自主决定
        
class SmartSQLAgent(BaseAgent):
    """保留用于单次查询和调试"""
    # 简化的查询功能
```

## 5. 配置示例

### 5.1 环境配置 (.env)
```bash
# 应用配置
APP_NAME=SemanticSQL-Agent
DEBUG=false

# 数据库配置
DB_TYPE=mysql
DB_HOST=localhost
DB_PORT=3306
DB_NAME=testdb
DB_USER=root
DB_PASSWORD=password

# LLM配置
LLM_MODEL=Qwen3-14B
LLM_BASE_URL=http://localhost:9991/v1
LLM_API_KEY=not-needed
LLM_TEMPERATURE=0.7

# Agent配置
MAX_ITERATIONS=20
ENABLE_REFLECTION=true
```

### 5.2 场景模板配置
```yaml
# config/scenario_templates.yaml
domains:
  ecommerce:
    scenarios:
      - name: "用户行为分析"
        category: "user_analysis"
        difficulty: "medium"
        template: "分析{time_period}内{user_segment}的{behavior}"
        
      - name: "销售统计"
        category: "sales_analysis"
        difficulty: "easy"
        template: "统计{product_category}在{time_period}的销售{metric}"
```

## 6. 扩展点

### 6.1 添加新工具
1. 在相应的工具目录创建新工具类
2. 继承 `BaseTool`
3. 实现 `run` 方法
4. 在 Agent 中注册工具

### 6.2 添加新领域
1. 在配置中添加领域模板
2. 扩展领域分析规则
3. 添加领域特定的场景模板

### 6.3 自定义反思规则
1. 扩展 `SQLReflectionTool`
2. 添加新的分析维度
3. 实现相应的优化策略

## 7. 最佳实践

### 7.1 工具设计原则
- 单一职责：每个工具只做一件事
- 明确接口：清晰的输入输出定义
- 错误处理：优雅的错误处理机制
- 可测试性：易于单元测试

### 7.2 提示词管理
- 使用模板引擎管理提示词
- 版本控制提示词变更
- 支持多语言提示词



