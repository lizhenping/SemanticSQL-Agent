# SemanticSQL Agent 架构文档（最终版）

## 1. 系统架构概览

### 1.1 核心设计原则
- **智能体驱动**：基于 ReAct 模式的自主决策
- **工具协同**：通过智能体协调各工具完成任务
- **执行追踪**：在 Agent 层统一记录执行轨迹
- **简洁实用**：避免过度设计，保持简单高效

### 1.2 系统架构图

```
┌─────────────────────────────────────────────────────────┐
│                      CLI 层                              │
│                   (用户交互接口)                          │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────┐
│                    Agent 层                              │
│  ┌─────────────────────────────────────────────────┐   │
│  │            SmartSQLAgent                         │   │
│  │   ┌─────────┐  ┌─────────┐  ┌──────────────┐  │   │
│  │   │  ReAct  │  │Execution│  │   Tools      │  │   │
│  │   │  Loop   │  │ Tracker │  │ Management   │  │   │
│  │   └─────────┘  └─────────┘  └──────────────┘  │   │
│  └─────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────┐
│                    Tools 层                              │
│  ┌──────────┐  ┌──────────┐  ┌────────┐  ┌──────────┐ │
│  │ Analysis │  │Generation│  │  SQL   │  │Reflection│ │
│  │  Tools   │  │  Tools   │  │ Tools  │  │  Tool    │ │
│  └──────────┘  └──────────┘  └────────┘  └──────────┘ │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────┐
│                 Infrastructure 层                        │
│  ┌──────────┐  ┌──────────┐  ┌────────┐  ┌──────────┐ │
│  │  Config  │  │   LLM    │  │Database│  │  Utils   │ │
│  │  System  │  │  Client  │  │ Client │  │  & Logs  │ │
│  └──────────┘  └──────────┘  └────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────┘
```

## 2. 数据生成流程

### 2.1 完整流程图

```
数据库连接
    ↓
[分析阶段]
    ├─→ 结构提取 (SchemaExtractionTool)
    ├─→ 领域分析 (DomainAnalysisTool)
    ├─→ 字段分类 (FieldClassificationTool)
    └─→ 关系分析 (ERAnalysisTool)
    ↓
[生成阶段]
    ├─→ 场景生成 (ScenarioTool)
    ├─→ 操作选择 (OperationSelectionTool)
    ├─→ 问题生成 (QuestionGenerationTool)
    └─→ SQL生成 (SQLGenerationTool)
    ↓
[验证阶段]
    ├─→ SQL验证 (SQLValidationTool)
    └─→ SQL执行 (SQLExecutionTool)
    ↓
[反思阶段]
    └─→ 反思优化 (SQLReflectionTool)
    ↓
输出数据集
```

### 2.2 关键流程说明

#### 2.2.1 场景→操作→问题→SQL
这是生成的核心流程：
1. **场景生成**：基于规则生成业务场景（如"销售统计"、"库存查询"）
2. **操作选择**：为场景选择SQL操作类型（SELECT、JOIN、GROUP BY等）
3. **问题生成**：基于场景和操作生成自然语言问题
4. **SQL生成**：一步生成对应的SQL查询

#### 2.2.2 执行记录
- 所有执行步骤在 Agent 层记录
- 使用 ExecutionTracker 统一管理
- 工具只返回执行结果，不负责记录

## 3. 核心组件设计

### 3.1 Agent 层

```python
class SmartSQLAgent(BaseAgent):
    """NL2SQL数据生成智能体"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.execution_tracker = ExecutionTracker()
        self._register_all_tools()
    
    def _register_all_tools(self):
        """注册所有工具"""
        # 分析工具
        self.register_tool(SchemaExtractionTool(self.config))
        self.register_tool(DomainAnalysisTool(self.config))
        self.register_tool(FieldClassificationTool(self.config))
        self.register_tool(ERAnalysisTool(self.config))
        
        # 生成工具
        self.register_tool(ScenarioTool(self.config))
        self.register_tool(OperationSelectionTool(self.config))
        self.register_tool(QuestionGenerationTool(self.config))
        self.register_tool(SQLGenerationTool(self.config))
        
        # SQL工具
        self.register_tool(SQLValidationTool(self.config))
        self.register_tool(SQLExecutionTool(self.config))
        
        # 反思工具
        self.register_tool(SQLReflectionTool(self.config))
```

### 3.2 执行追踪

```python
class ExecutionTracker:
    """执行轨迹记录器"""
    
    def __init__(self):
        self.execution_id = str(uuid.uuid4())
        self.steps = []
        self.start_time = None
        self.end_time = None
        self.metadata = {}
    
    def start(self, task: str):
        """开始记录"""
        self.start_time = datetime.now()
        self.metadata["task"] = task
        
    def record_step(self, step_type: AgentStepType, content: str, 
                   tool_name: str = None, tool_result: Any = None):
        """记录单个步骤"""
        step = AgentStep(
            step_type=step_type,
            content=content,
            timestamp=datetime.now(),
            tool_name=tool_name,
            tool_output=tool_result
        )
        self.steps.append(step)
    
    def end(self, status: str = "completed"):
        """结束记录"""
        self.end_time = datetime.now()
        self.metadata["status"] = status
        self.metadata["duration"] = (self.end_time - self.start_time).total_seconds()
    
    def to_execution(self) -> AgentExecution:
        """转换为执行记录"""
        return AgentExecution(
            task_id=self.execution_id,
            task=self.metadata.get("task", ""),
            started_at=self.start_time,
            completed_at=self.end_time,
            steps=self.steps,
            status=self.metadata.get("status", "unknown")
        )
```

### 3.3 工具设计

#### 3.3.1 工具基类
```python
class BaseTool(ABC):
    """工具基类 - 简洁版"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = get_logger(self.__class__.__name__)
    
    @property
    @abstractmethod
    def name(self) -> str:
        """工具唯一标识"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """工具功能描述"""
        pass
    
    @abstractmethod
    def run(self, **kwargs) -> Dict[str, Any]:
        """
        执行工具
        统一返回格式：
        {
            "success": bool,
            "data": Any,         # 成功时的数据
            "error": str,        # 失败时的错误信息
            "metadata": dict     # 可选的元数据
        }
        """
        pass
```

#### 3.3.2 生成工具链
```python
# 1. 场景生成
class ScenarioTool(BaseTool):
    """生成业务场景"""
    name = "scenario_generator"
    description = "基于数据库结构生成业务场景"

# 2. 操作选择
class OperationSelectionTool(BaseTool):
    """选择SQL操作"""
    name = "operation_selector"
    description = "为场景选择合适的SQL操作类型"

# 3. 问题生成
class QuestionGenerationTool(BaseTool):
    """生成自然语言问题"""
    name = "question_generator"
    description = "将场景和操作转换为自然语言问题"

# 4. SQL生成
class SQLGenerationTool(BaseTool):
    """生成SQL查询"""
    name = "sql_generator"
    description = "根据问题生成对应的SQL"
```

### 3.4 简化的输出处理

```python
# utils/output_handler.py
def save_training_dataset(dataset: Dict, output_path: str, format: str = "json"):
    """保存训练数据集"""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    if format == "json":
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)
    elif format == "jsonl":
        with open(output_path, "w", encoding="utf-8") as f:
            for example in dataset.get("examples", []):
                f.write(json.dumps(example, ensure_ascii=False) + "\n")
    elif format == "csv":
        import csv
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            if dataset.get("examples"):
                writer = csv.DictWriter(f, fieldnames=["question", "sql"])
                writer.writeheader()
                for example in dataset["examples"]:
                    writer.writerow({
                        "question": example["question"],
                        "sql": example["sql"]
                    })

def format_for_huggingface(dataset: Dict) -> List[Dict]:
    """转换为HuggingFace格式"""
    return [
        {
            "instruction": example["question"],
            "input": "",
            "output": example["sql"]
        }
        for example in dataset.get("examples", [])
    ]
```

## 4. 配置管理

### 4.1 配置结构
```yaml
# config/config.yaml
database:
  type: mysql
  host: localhost
  port: 3306
  username: root
  password: ${DB_PASSWORD}
  database: shop_db

llm:
  model: qwen-plus
  base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
  api_key: ${DASHSCOPE_API_KEY}
  temperature: 0.7
  max_tokens: 4096

agent:
  max_steps: 30
  enable_reflection: true
  verbose: true

generation:
  scenarios_per_batch: 10
  questions_per_scenario: 5
  sql_complexity_weights:
    simple: 0.3
    medium: 0.5
    complex: 0.2
```

## 5. 使用示例

### 5.1 命令行使用
```bash
# 基础使用
semanticsql-agent generate --count 100

# 指定数据库
semanticsql-agent generate \
    --db-type mysql \
    --host localhost \
    --database shop_db \
    --count 200 \
    --output data.json

# 使用配置文件
semanticsql-agent generate --config my_config.yaml
```

### 5.2 代码使用
```python
from semanticsql_agent import SmartSQLAgent
from config import Config

# 创建配置
config = Config.from_yaml("config.yaml")

# 创建智能体
agent = SmartSQLAgent(config)

# 生成数据
result = agent.generate_training_data(
    target_count=100,
    database_config={
        "type": "mysql",
        "host": "localhost",
        "database": "shop_db"
    }
)

# 保存结果
if result["success"]:
    save_training_dataset(result["dataset"], "output/data.json")
```

## 6. 关键特性

### 6.1 智能体自主性
- Agent 根据任务自主决定执行步骤
- 动态调整策略
- 错误自动恢复

### 6.2 工具模块化
- 每个工具单一职责
- 统一的接口规范
- 易于扩展新工具

### 6.3 执行可追踪
- 完整的执行轨迹
- 每步都有记录
- 便于调试和优化

### 6.4 输出灵活
- 多种输出格式
- 便于集成到训练流程
- 支持自定义格式

## 7. 性能优化

### 7.1 并行处理
- 场景批量生成
- SQL批量验证
- 异步LLM调用

### 7.2 缓存机制
- 数据库结构缓存
- LLM响应缓存
- 中间结果缓存

### 7.3 资源管理
- 连接池管理
- 内存优化
- 批次大小控制

## 8. 最佳实践

### 8.1 工具开发
- 遵循统一接口
- 完善错误处理
- 提供详细日志

### 8.2 配置管理
- 使用环境变量保护敏感信息
- 提供合理的默认值
- 支持多环境配置

### 8.3 监控运维
- 记录关键指标
- 设置告警阈值
- 定期性能分析

这个最终架构设计更加清晰、实用，解决了之前的问题，并保持了系统的灵活性和可扩展性。