# SemanticSQL Agent 设计规范

## 1. 项目概述

### 1.1 项目定位
SemanticSQL Agent 是一个基于 ReAct 智能体架构的 **NL2SQL 训练数据生成系统**。

**核心功能**：
- 📊 **智能数据库分析**：自动提取数据库结构、识别业务领域、分析表关系
- 🎯 **场景化数据生成**：基于业务场景批量生成自然语言问题和对应的 SQL 查询对
- ✅ **执行验证机制**：实际执行生成的 SQL，验证正确性和可行性
- 🔄 **智能反思优化**：分析执行结果，自动优化 SQL 质量和性能
- 📦 **标准化输出**：生成符合训练标准的 JSON/JSONL 格式数据集

**目标用途**：为 NL2SQL 模型训练提供高质量、大规模的合成训练数据，减少人工标注成本，提升模型在特定领域的表现。

### 1.2 核心价值
- **自动化生成**：减少人工标注成本，快速生成大量训练数据
- **高质量保证**：通过验证和反思机制确保数据质量
- **领域适应**：自动识别业务领域，生成符合领域特征的数据
- **灵活扩展**：基于工具的架构，易于添加新功能

### 1.3 设计原则
- **智能体驱动**：采用 ReAct 模式，智能体自主决策执行流程
- **模块化设计**：工具职责单一，通过智能体协调
- **简洁实用**：避免过度设计，保持代码简单高效
- **可追踪性**：完整记录执行过程，便于调试和优化

## 2. 功能规范

### 2.1 核心功能

#### 2.1.1 数据库分析
- **结构提取**：获取表、列、索引、约束等信息
- **领域识别**：基于表名和字段识别业务领域
- **字段分类**：将字段分类为标识符、时间戳、数值、分类、描述等类型
- **关系分析**：识别主外键关系，构建 ER 图

#### 2.1.2 智能体驱动的数据生成流程

**关键设计原则**：
- **❌ 错误**：流程步骤硬编码在代码中
- **✅ 正确**：流程完全由提示词引导，Agent自主决策

**ReAct 自主决策模式**：Agent通过思考-行动-观察循环，自主决定执行策略

**Agent的智能决策过程**：
1. **分析决策**：Agent根据任务需求，自主决定如何分析数据库
2. **生成策略**：基于分析结果，Agent智能选择生成策略和场景
3. **质量控制**：Agent自主决定何时执行SQL、何时反思、何时优化
4. **输出管理**：Agent根据质量评估结果，决定数据的取舍和格式化

**记忆机制**：
- **数据库分析结果必须完整记忆**：一次性分析数据库，结果贯穿整个过程
- **上下文保持**：Agent在整个执行过程中维护分析结果的记忆
- **避免重复分析**：已分析的结构信息在后续步骤中直接使用

**反思-修正循环机制**：
```
SQL生成 → SQL执行 → 反思分析 → 发现问题？
    ↑                              ↓ (是)
    └─── 修正并重新生成 ←──── 决定修正步骤
```

当反思发现问题时，Agent能够：
- **SQL错误** → 回到sql_generation重新生成
- **问题不合理** → 回到question_generation重新生成  
- **场景不适合** → 回到scenario_generation重新设计
- **需要深度分析** → 调用sequential_thinking工具

**思考工具调用时机**：
- **复杂业务场景分析**：当遇到复杂的表关系时
- **SQL优化决策**：当需要在多种SQL写法中选择时
- **错误诊断**：当SQL执行失败需要深度分析时
- **质量评估**：当需要综合评估生成数据质量时

**核心特点**：
- **动态适应**：Agent根据数据库特征调整生成策略
- **智能反思**：执行SQL后主动反思结果质量
- **自主优化**：根据反思结果自动优化或重新生成
- **完全自主**：所有决策由Agent基于提示词引导做出，无硬编码步骤

#### 2.1.3 验证与优化
- **语法验证**：检查 SQL 语法正确性
- **执行测试**：实际执行 SQL 验证可行性
- **反思优化**：分析执行结果，提供优化建议

### 2.2 数据生成规范

#### 2.2.1 场景类型
- **基础查询**：单表查询、条件筛选
- **关联查询**：多表 JOIN、子查询
- **聚合统计**：GROUP BY、聚合函数
- **时间分析**：时间范围、趋势分析
- **复杂查询**：窗口函数、CTE、复杂条件

#### 2.2.2 难度分布
```yaml
difficulty_distribution:
  easy: 30%    # 基础单表查询
  medium: 20%  # 关联和聚合查询
  hard: 30%    # 复杂查询和高级特性
  expert: 20%    # 专家级别查询和高级特性
```

#### 2.2.3 质量标准
- SQL 语法必须正确
- 问题表述自然流畅
- SQL 与问题语义匹配
- 执行结果合理有效

## 3. 实现规范

### 3.1 Agent实现规范

#### 3.1.1 DataGenerationAgent设计要求

**核心实现原则**：
```python
# ✅ 正确实现：提示词驱动的Agent
class DataGenerationAgent(BaseAgent):
    """
    完整的训练数据生成Agent
    - 拥有完整工具链：分析、生成、验证、反思、思考
    - 通过提示词引导完整流程
    - 自主决策工具调用顺序
    - 实现反思-修正循环
    """
    
    def _initialize_tools(self):
        """必须注册完整工具链"""
        # 分析工具
        self.register_tool("extract_schema", SchemaExtractionTool(...))
        self.register_tool("domain_analysis", DomainAnalysisTool(...))
        self.register_tool("field_classification", FieldClassificationTool(...))
        self.register_tool("er_analysis", ERAnalysisTool(...))
        
        # 生成工具
        self.register_tool("scenario_generation", ScenarioGenerationTool(...))
        self.register_tool("question_generation", QuestionGenerationTool(...))
        self.register_tool("sql_generation", SQLGenerationTool(...))
        
        # 验证工具
        self.register_tool("sql_execution", SQLExecutionTool(...))
        self.register_tool("sql_reflection", SQLReflectionTool(...))
        
        # 思考工具
        self.register_tool("sequential_thinking", SequentialThinkingTool(...))
    
    def generate_training_data(self, count: int, output_file: str):
        """
        ✅ 正确：完全由Agent自主执行，无硬编码步骤
        """
        task = f"生成{count}条高质量NL2SQL训练数据"
        execution = self.new_task(task)  # 进入ReAct循环
        return self._extract_results(execution)
    
    def get_system_prompt(self) -> str:
        """
        关键：提示词必须引导Agent执行完整流程
        包含：
        1. 数据库完整分析并记忆
        2. SQL执行后反思
        3. 反思发现问题时回退修正
        4. 思考工具使用时机
        """
        return comprehensive_prompt_template()
```

**❌ 错误实现：硬编码流程**
```python
# 不要这样做 - 违反Agent自主决策原则
def generate_training_data(self):
    schema = self.call_tool('extract_schema')    # 硬编码顺序
    domain = self.call_tool('domain_analysis')   # 硬编码顺序
    # ... 更多硬编码步骤
```

#### 3.1.2 提示词系统设计

**完整系统提示词必须包含**：
1. **数据库分析指导**：如何完整分析并记忆数据库结构
2. **生成流程指导**：如何基于分析结果生成数据
3. **执行验证指导**：如何执行SQL并获取反馈
4. **反思修正指导**：如何根据执行结果决定是否回退
5. **思考工具指导**：何时调用sequential_thinking进行深度分析

**记忆机制实现**：
```
Agent第一次调用extract_schema后：
├─ 记忆：数据库有5个表，主要是合同和援助业务
├─ 后续调用sql_generation时：
│  └─ 提示词引导：使用已记忆的数据库结构信息
└─ 无需重复调用extract_schema
```

#### 3.1.3 反思-修正循环实现

**执行后反思决策树**：
```
SQL执行完成
├─ 反思分析：执行时间、结果合理性、SQL质量
├─ 发现问题？
│  ├─ 是 → 决定修正策略：
│  │  ├─ SQL语法错误 → 重新调用sql_generation
│  │  ├─ 问题语义不清 → 重新调用question_generation
│  │  ├─ 场景不合适 → 重新调用scenario_generation
│  │  └─ 复杂分析需求 → 调用sequential_thinking
│  └─ 否 → 接受数据，继续生成下一条
```

## 4. 接口规范

### 3.1 工具接口

```python
class BaseTool(ABC):
    """工具基类接口规范"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """工具唯一标识，用于注册和调用"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """工具功能描述，用于 LLM 理解"""
        pass
    
    @abstractmethod
    def run(self, **kwargs) -> Dict[str, Any]:
        """
        工具执行接口
        
        返回格式：
        {
            "success": bool,      # 执行是否成功
            "data": Any,         # 成功时的返回数据
            "error": str,        # 失败时的错误信息
            "metadata": dict     # 可选的元数据
        }
        """
        pass
```

### 3.2 智能体接口

```python
class BaseAgent(ABC):
    """智能体基类接口规范"""
    
    @abstractmethod
    def run(self, task: str, context: Dict = None) -> AgentExecution:
        """执行任务"""
        pass
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        pass
    
    def register_tool(self, tool: BaseTool) -> None:
        """注册工具"""
        pass
```

### 3.3 命令行接口

```bash
# 基础生成命令
semanticsql-agent generate [OPTIONS]

Options:
  --config PATH           配置文件路径
  --count INTEGER        生成数据条数 [default: 100]
  --db-type TEXT         数据库类型 [mysql|postgresql|sqlite]
  --host TEXT            数据库主机
  --port INTEGER         数据库端口
  --database TEXT        数据库名称
  --username TEXT        用户名
  --password TEXT        密码
  --output PATH          输出文件路径
  --format TEXT          输出格式 [json|jsonl|csv]
  --verbose              详细输出
  --help                 显示帮助信息

# 其他命令
semanticsql-agent test-connection  # 测试数据库连接
semanticsql-agent init            # 初始化配置
semanticsql-agent version         # 显示版本信息
```

## 4. 数据模型规范

### 4.1 核心数据结构

#### 4.1.1 执行记录
```python
@dataclass
class AgentStep:
    """单个执行步骤"""
    step_type: AgentStepType  # thought/action/observation
    content: str              # 步骤内容
    timestamp: datetime       # 时间戳
    tool_name: Optional[str]  # 使用的工具
    tool_output: Optional[Any]  # 工具输出
    error: Optional[str]      # 错误信息

@dataclass
class AgentExecution:
    """完整执行记录"""
    task_id: str              # 任务ID
    task: str                 # 任务描述
    started_at: datetime      # 开始时间
    completed_at: Optional[datetime]  # 结束时间
    steps: List[AgentStep]    # 执行步骤
    final_result: Optional[Any]  # 最终结果
    status: str               # running/completed/failed
    error: Optional[str]      # 错误信息
```

#### 4.1.2 生成数据
```python
@dataclass
class QueryScenario:
    """查询场景"""
    id: str
    category: str            # 场景类别
    business_purpose: str    # 业务目的
    complexity: str          # easy/medium/hard
    applicable_tables: List[str]

@dataclass
class GeneratedExample:
    """生成的训练样本"""
    id: str
    scenario_id: str
    question: str            # 自然语言问题
    sql: str                # SQL 查询
    difficulty: str          # 难度级别
    validation_result: Dict  # 验证结果
    execution_result: Dict   # 执行结果
    quality_score: float     # 质量分数
```

### 4.2 配置规范

```yaml
# 完整配置示例
database:
  type: mysql              # 数据库类型
  host: localhost         
  port: 3306              
  username: root          
  password: ${DB_PASSWORD}  # 支持环境变量
  database: shop_db       
  
llm:
  model: Qwen3-14B        # 模型名称
  base_url: http://192.168.200.216:9991/v1
  api_key: ${DASHSCOPE_API_KEY}
  temperature: 0.7        # 生成温度
  max_tokens: 4096        # 最大token数
  
agent:
  max_steps: 30           # 最大执行步骤
  enable_reflection: true # 启用反思
  verbose: true           # 详细日志
  
generation:
  scenarios_per_batch: 10      # 每批场景数
  questions_per_scenario: 5    # 每场景问题数
  sql_complexity_weights:      # SQL复杂度权重
    simple: 0.3
    medium: 0.5
    complex: 0.2
    
output:
  directory: ./output     # 输出目录
  format: json           # 默认格式
  save_intermediate: false  # 是否保存中间结果
```

## 5. 错误处理规范

### 5.1 错误分类
- **配置错误**：配置文件缺失、格式错误、必需参数缺失
- **连接错误**：数据库连接失败、LLM API 连接失败
- **执行错误**：工具执行失败、SQL 执行错误
- **验证错误**：SQL 语法错误、数据验证失败
- **系统错误**：内存不足、权限问题

### 5.2 错误处理策略
```python
# 工具级错误处理
def run(self, **kwargs) -> Dict[str, Any]:
    try:
        # 执行逻辑
        result = self._execute(**kwargs)
        return {
            "success": True,
            "data": result
        }
    except ValidationError as e:
        return {
            "success": False,
            "error": f"参数验证失败: {e}",
            "error_type": "validation"
        }
    except Exception as e:
        self.logger.error(f"工具执行失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "error_type": "execution"
        }

# Agent 级错误恢复
def _execute_with_retry(self, action: Dict, max_retries: int = 3):
    """带重试的执行"""
    for attempt in range(max_retries):
        try:
            return self._execute_tool(action)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            self.logger.warning(f"执行失败，重试 {attempt + 1}/{max_retries}")
            time.sleep(2 ** attempt)  # 指数退避
```

## 6. 日志规范

### 6.1 日志级别
- **DEBUG**：详细的调试信息，包括 LLM 交互
- **INFO**：正常的执行流程信息
- **WARNING**：警告信息，如重试、降级
- **ERROR**：错误信息，但不影响继续执行
- **CRITICAL**：严重错误，导致程序终止

### 6.2 日志格式
```python
# 日志配置
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'detailed': {
            'format': '%(asctime)s [%(levelname)s] %(name)s.%(funcName)s:%(lineno)d - %(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
            'stream': 'ext://sys.stdout'
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'detailed',
            'filename': 'semanticsql-agent.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console', 'file']
    }
}
```

## 7. 文档规范

### 7.1 代码文档
- 所有公共接口必须有 docstring
- 复杂逻辑添加行内注释
- 示例代码保持可运行

### 7.2 用户文档
- README.md：项目介绍和快速开始
- INSTALL.md：详细安装指南
- USAGE.md：使用教程
- API.md：API 参考

### 7.3 开发文档
- CONTRIBUTING.md：贡献指南
- DEVELOPMENT.md：开发环境搭建
- ARCHITECTURE.md：架构设计
- DESIGN.md：设计决策