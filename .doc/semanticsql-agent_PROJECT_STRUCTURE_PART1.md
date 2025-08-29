# SemanticSQL Agent 项目结构设计 - 第一部分

## 1. 完整项目结构

```
semanticsql-agent/
├── README.md                    # 项目说明文档
├── setup.py                     # 安装配置
├── requirements.txt             # 依赖列表
├── .env.example                # 环境变量示例
├── .gitignore                  # Git忽略文件
│
├── config/                     # 配置模块
│   ├── __init__.py
│   ├── settings.py             # 全局配置管理
│   ├── database.py             # 数据库配置
│   └── example.yaml            # 配置示例文件
│
├── core/                       # 核心模块
│   ├── __init__.py
│   ├── models.py               # Pydantic数据模型
│   ├── exceptions.py           # 自定义异常
│   └── constants.py            # 常量定义
│
├── agent/                      # 智能体模块
│   ├── __init__.py
│   ├── base_agent.py           # 基础Agent类（ReAct实现）
│   ├── smart_sql_agent.py      # SQL智能体
│   ├── executor.py             # 执行器（含轨迹记录）
│   └── context.py              # 执行上下文管理
│
├── tools/                      # 工具模块
│   ├── __init__.py
│   ├── base.py                 # 工具基类
│   │
│   ├── analysis/               # 分析工具
│   │   ├── __init__.py
│   │   ├── schema_analyzer.py         # 数据库结构分析
│   │   ├── domain_analyzer.py         # 领域识别
│   │   ├── field_classifier.py        # 字段分类
│   │   └── relationship_analyzer.py   # 关系分析
│   │
│   ├── generation/             # 生成工具
│   │   ├── __init__.py
│   │   ├── scenario_generator.py      # 场景生成（基于规则）
│   │   ├── question_generator.py      # 问题生成
│   │   └── sql_generator.py          # SQL生成（一步完成）
│   │
│   ├── sql/                    # SQL操作工具
│   │   ├── __init__.py
│   │   ├── sql_executor.py            # SQL执行
│   │   ├── sql_validator.py           # SQL验证
│   │   └── sql_optimizer.py           # SQL优化建议
│   │
│   └── reflection/             # 反思工具
│       ├── __init__.py
│       ├── execution_analyzer.py      # 执行结果分析
│       └── quality_improver.py        # 质量改进建议
│
├── prompts/                    # 提示词管理
│   ├── __init__.py
│   ├── system.yaml             # 系统级提示词
│   ├── tools.yaml              # 工具提示词配置
│   ├── templates/              # 提示词模板
│   │   ├── __init__.py
│   │   ├── react/              # ReAct相关模板
│   │   │   ├── thought.j2
│   │   │   └── action.j2
│   │   ├── analysis/           # 分析类模板
│   │   │   ├── domain.j2
│   │   │   └── schema.j2
│   │   ├── generation/         # 生成类模板
│   │   │   ├── scenario.j2
│   │   │   ├── question.j2
│   │   │   └── sql.j2
│   │   └── reflection/         # 反思类模板
│   │       ├── execution.j2
│   │       └── quality.j2
│   └── loader.py               # 提示词加载器
│
├── utils/                      # 工具模块
│   ├── __init__.py
│   ├── database.py             # 数据库连接管理
│   ├── llm_client.py           # LLM客户端封装
│   ├── logger.py               # 日志工具
│   ├── validators.py           # 数据验证工具
│   └── helpers.py              # 辅助函数
│
├── output/                     # 输出处理
│   ├── __init__.py
│   ├── formatter.py            # 结果格式化
│   ├── exporter.py             # 导出器（JSON/CSV/SQL）
│   └── adapters/               # 导出适配器
│       ├── __init__.py
│       ├── huggingface.py      # HuggingFace格式
│       └── jsonl.py            # JSONL格式
│
├── cli/                        # 命令行接口
│   ├── __init__.py
│   ├── cli.py                  # 主CLI入口
│   ├── commands/               # CLI命令
│   │   ├── __init__.py
│   │   ├── analyze.py          # smart-analyze命令
│   │   ├── test.py             # 测试相关命令
│   │   └── config.py           # 配置相关命令
│   └── utils.py                # CLI工具函数
│
├── tests/                      # 测试模块
│   ├── __init__.py
│   ├── conftest.py             # pytest配置
│   ├── unit/                   # 单元测试
│   │   ├── __init__.py
│   │   ├── test_tools/         # 工具测试
│   │   ├── test_agent/         # 智能体测试
│   │   └── test_models.py      # 模型测试
│   ├── integration/            # 集成测试
│   │   ├── __init__.py
│   │   └── test_workflow.py    # 工作流测试
│   └── fixtures/               # 测试数据
│       ├── __init__.py
│       └── sample_data.py
│
├── examples/                   # 示例代码
│   ├── __init__.py
│   ├── basic_usage.py          # 基础使用示例
│   ├── custom_tool.py          # 自定义工具示例
│   └── advanced_agent.py       # 高级智能体示例
│
├── scripts/                    # 脚本
│   ├── setup_dev.sh           # 开发环境设置
│   ├── run_tests.sh           # 运行测试
│   └── build_docker.sh        # 构建Docker镜像
│
└── docs/                      # 文档
    ├── api/                   # API文档
    ├── tutorials/             # 教程
    └── deployment/            # 部署文档
```

## 2. 核心模块实现

### 2.1 数据模型 (core/models.py)

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

class AgentStepType(str, Enum):
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    REFLECTION = "reflection"

# ========== 输入模型 ==========
class TaskRequest(BaseModel):
    """任务请求"""
    database_config: Dict[str, Any]
    target_count: int = Field(default=100, description="目标生成数量")
    difficulty_distribution: Dict[DifficultyLevel, float] = Field(
        default={
            DifficultyLevel.EASY: 0.3,
            DifficultyLevel.MEDIUM: 0.5,
            DifficultyLevel.HARD: 0.2
        }
    )

# ========== 分析阶段模型 ==========
class TableInfo(BaseModel):
    """表信息"""
    name: str
    columns: List[Dict[str, Any]]
    primary_key: Optional[str] = None
    foreign_keys: List[Dict[str, str]] = Field(default_factory=list)
    row_count: Optional[int] = None
    comment: Optional[str] = None

class SchemaAnalysis(BaseModel):
    """数据库结构分析结果"""
    database_name: str
    database_type: DatabaseType
    tables: List[TableInfo]
    total_tables: int
    extracted_at: datetime = Field(default_factory=datetime.now)

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
    has_join: bool = False
    has_aggregation: bool = False
    has_subquery: bool = False

# ========== 验证和反思模型 ==========
class ExecutionResult(BaseModel):
    """SQL执行结果"""
    sql_id: str
    success: bool
    execution_time: float
    row_count: int
    error_message: Optional[str] = None
    sample_data: Optional[List[Dict]] = None

class ValidationResult(BaseModel):
    """验证结果"""
    sql_id: str
    syntax_valid: bool
    semantic_valid: bool
    performance_score: float
    issues: List[str] = Field(default_factory=list)

class ReflectionResult(BaseModel):
    """反思结果"""
    sql_id: str
    quality_score: float
    improvement_suggestions: List[str]
    optimized_sql: Optional[str] = None
    learning_points: List[str]

# ========== ReAct执行模型 ==========
class AgentStep(BaseModel):
    """智能体执行步骤"""
    step_type: AgentStepType
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[Any] = None
    error: Optional[str] = None

class AgentExecution(BaseModel):
    """智能体执行记录"""
    task_id: str
    task: str
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    steps: List[AgentStep] = Field(default_factory=list)
    final_result: Optional[Any] = None
    status: str = "running"  # running, completed, failed
    error: Optional[str] = None

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
    created_at: datetime = Field(default_factory=datetime.now)
    database_info: SchemaAnalysis
    domain_info: DomainAnalysis
    examples: List[TrainingExample]
    statistics: Dict[str, Any]
```

### 2.2 基础智能体 (agent/base_agent.py)

```python
"""
基础智能体类 - 实现ReAct模式
"""
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable
import uuid
from datetime import datetime

import openai
from core.models import AgentStep, AgentExecution, AgentStepType
from config.settings import Config
from utils.logger import get_logger


class BaseAgent(ABC):
    """智能体基础类 - 实现ReAct模式"""
    
    def __init__(self, config: Config):
        """初始化智能体"""
        self.config = config
        self.logger = get_logger(self.__class__.__name__)
        
        # 初始化LLM客户端
        self.llm_client = openai.OpenAI(
            api_key=config.llm.api_key,
            base_url=config.llm.base_url
        )
        
        # LLM配置
        self.llm_config = {
            'model': config.llm.model,
            'temperature': config.llm.temperature,
            'max_tokens': config.llm.max_tokens
        }
        
        # 工具注册
        self.tools: Dict[str, Any] = {}
        self.tool_schemas: List[Dict[str, Any]] = []
        
        # 执行状态
        self.current_execution: Optional[AgentExecution] = None
        self.max_steps = config.agent.max_steps
        self.enable_reflection = config.agent.enable_reflection
        
    def register_tool(self, name: str, tool: Any) -> None:
        """注册工具"""
        self.tools[name] = tool
        self.tool_schemas.append(tool.get_schema())
        self.logger.info(f"Registered tool: {name}")
        
    @abstractmethod
    def get_system_prompt(self) -> str:
        """获取系统提示词 - 子类必须实现"""
        pass
    
    def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentExecution:
        """执行任务 - 核心ReAct循环"""
        # 初始化执行记录
        self.current_execution = AgentExecution(
            task_id=str(uuid.uuid4()),
            task=task,
            status="running"
        )
        
        try:
            # 初始化上下文
            exec_context = self._build_initial_context(task, context)
            
            # ReAct主循环
            step_count = 0
            while step_count < self.max_steps:
                # 1. Think - 思考
                thought = self._think(exec_context)
                self._record_step(AgentStepType.THOUGHT, thought)
                
                # 2. 检查是否完成
                if self._should_finish(thought):
                    self.logger.info("Task completed based on thought")
                    break
                
                # 3. Act - 行动
                action = self._decide_action(thought)
                if action["tool_name"] == "none":
                    self.logger.info("No action needed")
                    break
                    
                self._record_step(
                    AgentStepType.ACTION, 
                    f"Using tool: {action['tool_name']}",
                    tool_name=action["tool_name"],
                    tool_input=action["tool_input"]
                )
                
                # 4. Observe - 观察
                observation = self._execute_action(action)
                self._record_step(
                    AgentStepType.OBSERVATION,
                    str(observation),
                    tool_output=observation
                )
                
                # 5. 更新上下文
                exec_context = self._update_context(
                    exec_context, thought, action, observation
                )
                
                step_count += 1
            
            # 生成最终结果
            self.current_execution.final_result = self._generate_final_result()
            self.current_execution.status = "completed"
            self.current_execution.completed_at = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Agent execution failed: {e}", exc_info=True)
            self.current_execution.status = "failed"
            self.current_execution.error = str(e)
            self._record_step(AgentStepType.OBSERVATION, f"Error: {e}", error=str(e))
            
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
            tools=self.tool_schemas,
            tool_choice="auto",
            **self.llm_config
        )
        
        # 解析工具调用
        message = response.choices[0].message
        if message.tool_calls:
            tool_call = message.tool_calls[0]
            return {
                "tool_name": tool_call.function.name,
                "tool_input": json.loads(tool_call.function.arguments)
            }
        
        return {"tool_name": "none", "tool_input": {}}
    
    def _execute_action(self, action: Dict[str, Any]) -> Any:
        """执行行动并返回观察结果"""
        tool_name = action["tool_name"]
        tool_input = action["tool_input"]
        
        if tool_name not in self.tools:
            return f"Error: Tool {tool_name} not found"
        
        try:
            tool = self.tools[tool_name]
            result = tool.run(**tool_input)
            return result
        except Exception as e:
            self.logger.error(f"Tool execution failed: {e}", exc_info=True)
            return f"Error executing {tool_name}: {str(e)}"
    
    def _record_step(self, step_type: AgentStepType, content: str, **kwargs) -> None:
        """记录执行步骤"""
        step = AgentStep(
            step_type=step_type,
            content=content,
            **kwargs
        )
        self.current_execution.steps.append(step)
        
    def _build_initial_context(self, task: str, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """构建初始上下文"""
        return {
            "task": task,
            "user_context": context or {},
            "history": [],
            "results": {}
        }
    
    def _update_context(self, context: Dict[str, Any], thought: str, 
                       action: Dict[str, Any], observation: Any) -> Dict[str, Any]:
        """更新执行上下文"""
        context["history"].append({
            "thought": thought,
            "action": action,
            "observation": observation
        })
        
        # 保存工具结果
        if action["tool_name"] != "none":
            context["results"][action["tool_name"]] = observation
            
        return context
    
    def _should_finish(self, thought: str) -> bool:
        """判断是否应该结束任务"""
        finish_indicators = [
            "任务完成", "task completed", "done", "完成",
            "所有步骤已完成", "最终结果"
        ]
        
        thought_lower = thought.lower()
        return any(indicator in thought_lower for indicator in finish_indicators)
    
    def _generate_final_result(self) -> Any:
        """生成最终结果"""
        # 收集所有工具的输出
        results = {}
        for step in self.current_execution.steps:
            if step.step_type == AgentStepType.OBSERVATION and step.tool_output:
                if step.tool_name:
                    results[step.tool_name] = step.tool_output
                    
        return results
    
    def _format_thinking_prompt(self, context: Dict[str, Any]) -> str:
        """格式化思考提示词"""
        history_str = self._format_history(context.get("history", []))
        
        return f"""当前任务: {context['task']}

执行历史:
{history_str}

当前结果:
{json.dumps(context.get('results', {}), ensure_ascii=False, indent=2)}

请分析当前状态，思考下一步应该做什么。如果任务已完成，请明确说明。
"""
    
    def _format_action_prompt(self, thought: str) -> str:
        """格式化行动提示词"""
        return f"""基于以下思考:
{thought}

请决定下一步的行动。选择合适的工具并提供必要的参数。
如果不需要使用工具，请明确说明。
"""
    
    def _format_history(self, history: List[Dict[str, Any]]) -> str:
        """格式化历史记录"""
        if not history:
            return "无"
            
        lines = []
        for i, item in enumerate(history[-5:], 1):  # 只显示最近5步
            lines.append(f"步骤 {i}:")
            lines.append(f"  思考: {item['thought'][:100]}...")
            lines.append(f"  行动: {item['action']['tool_name']}")
            lines.append(f"  结果: {str(item['observation'])[:100]}...")
            
        return "\n".join(lines)
```