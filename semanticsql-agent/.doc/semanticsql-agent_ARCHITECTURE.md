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
│   ├── base.py                  # 工具基类
│   │
│   ├── analysis_tools/          # 分析工具（核心）
│   │   ├── __init__.py
│   │   ├── schema_extraction_tool.py    # 数据库结构提取
│   │   ├── domain_analysis_tool.py      # 领域分析
│   │   ├── field_classification_tool.py # 字段分类
│   │   └── er_analysis_tool.py          # 实体关系分析
│   │
│   ├── generation_tools/        # 生成工具
│   │   ├── __init__.py
│   │   ├── scenario_generation_tool.py  # 场景生成
│   │   ├── sql_generation_tool.py       # SQL生成
│   │   └── question_generation_tool.py  # 问题生成
│   │
│   ├── validation_tools/        # 验证工具
│   │   ├── __init__.py
│   │   ├── sql_validation_tool.py       # SQL验证
│   │   └── sql_execution_tool.py        # SQL执行测试
│   │
│   ├── reflection_tools/        # 反思工具
│   │   ├── __init__.py
│   │   └── sql_reflection_tool.py       # SQL执行反思
│   │
│   └── thinking_tools/          # 思考工具（可选）
│       ├── __init__.py
│       └── sequential_thinking_tool.py   # 深度思考
│
├── prompts/
│   ├── __init__.py
│   ├── templates/               # Jinja2 模板
│   │   ├── system/             # 系统提示词
│   │   ├── tools/              # 工具描述
│   │   └── analysis/           # 分析提示词
│   └── manager.py               # 提示词管理器
│
├── agent/
│   ├── __init__.py
│   ├── sql_agent.py             # 主 SQL Agent
│   └── callbacks.py             # 轨迹记录回调
│
├── utils/
│   ├── __init__.py
│   ├── database.py              # 数据库连接管理
│   └── trajectory.py            # 轨迹记录
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
    llm_base_url: str = "http://localhost:9009/v1"
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
    type: str  # mysql/postgresql/sqlite
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

### 4.1 完整流程图
```
数据库连接
    ↓
┌─────────────────────────┐
│      分析阶段           │
├─────────────────────────┤
│ 1. 结构提取             │
│ 2. 领域分析             │
│ 3. 字段分类             │
│ 4. 关系分析             │
└───────────┬─────────────┘
            ↓
┌─────────────────────────┐
│      生成阶段           │
├─────────────────────────┤
│ 5. 场景生成             │
│ 6. 问题生成             │
│ 7. SQL生成(一步)        │
└───────────┬─────────────┘
            ↓
┌─────────────────────────┐
│    验证反思阶段         │
├─────────────────────────┤
│ 8. SQL验证              │
│ 9. SQL执行              │
│ 10. 执行反思            │
│ 11. SQL优化             │
└───────────┬─────────────┘
            ↓
        输出训练数据
```

### 4.2 工具调用顺序
```python
# 分析阶段
schema = schema_extraction_tool.run(db_config)
domain = domain_analysis_tool.run(schema)
fields = field_classification_tool.run(schema)
er = er_analysis_tool.run(schema)

# 生成阶段
scenarios = scenario_generation_tool.run(
    AnalysisResults(domain, fields, er)
)
questions = question_generation_tool.run(scenarios)
sql_queries = sql_generation_tool.run(questions, schema)

# 验证反思阶段
for sql in sql_queries:
    valid = sql_validation_tool.run(sql)
    if valid:
        result = sql_execution_tool.run(sql)
        reflection = sql_reflection_tool.run(sql, result)
        if reflection.improved_sql:
            sql = reflection.improved_sql
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
LLM_BASE_URL=http://localhost:9009/v1
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



