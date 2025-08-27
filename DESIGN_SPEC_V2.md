# SemanticSQL-Agent 核心组件设计规范（TRAEAgent 模式）

## 1. 智能体基础类型定义

### 1.1 核心状态和类型（参考 TRAEAgent）

```python
# models/agent_basics.py
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel

class AgentState(Enum):
    """智能体执行状态"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"

class AgentStepState(Enum):
    """步骤执行状态 - 体现 TAO 循环"""
    THINKING = "thinking"          # Thought 阶段
    CALLING_TOOL = "calling_tool"  # Action 阶段
    REFLECTING = "reflecting"      # 增强的 Observation
    COMPLETED = "completed"
    ERROR = "error"

@dataclass
class LLMMessage:
    """LLM 消息"""
    role: str  # system, user, assistant
    content: str
    tool_result: Optional['ToolResult'] = None

@dataclass
class ToolCall:
    """工具调用"""
    id: str
    name: str
    arguments: Dict[str, Any]

@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    usage: Optional[Dict[str, int]] = None

@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    tool_name: Optional[str] = None
    execution_time: Optional[float] = None

@dataclass
class AgentStep:
    """执行步骤记录"""
    step_number: int
    state: AgentStepState
    llm_response: Optional[LLMResponse] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_results: Optional[List[ToolResult]] = None
    reflection: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

@dataclass
class AgentExecution:
    """完整的执行记录"""
    task: str
    steps: List[AgentStep]
    agent_state: AgentState = AgentState.IDLE
    final_result: Optional[str] = None
    success: bool = False
    total_tokens: Optional[int] = None
    execution_time: Optional[float] = None
    metadata: Dict[str, Any] = None
```

### 1.2 NL2SQL 特定模型

```python
# models/schemas.py
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional

class DatabaseInfo(BaseModel):
    """数据库信息"""
    name: str
    host: str
    port: int
    tables_count: int
    total_rows: Optional[int] = None

class TableSchema(BaseModel):
    """表结构信息"""
    name: str
    comment: Optional[str] = None
    columns: List[Dict[str, Any]]
    primary_key: Optional[List[str]] = None
    foreign_keys: List[Dict[str, Any]] = []
    indexes: List[Dict[str, Any]] = []
    row_count: Optional[int] = None
    
class DomainAnalysis(BaseModel):
    """领域分析结果"""
    domain: str = Field(description="业务领域")
    description: str = Field(description="领域描述")
    key_entities: List[str] = Field(description="关键实体")
    business_rules: List[str] = Field(description="业务规则")
    terminology: Dict[str, str] = Field(description="专业术语")

class FieldClassification(BaseModel):
    """字段分类结果"""
    dimensions: Dict[str, List[str]] = Field(description="维度字段")
    measures: Dict[str, List[str]] = Field(description="度量字段")
    identifiers: Dict[str, List[str]] = Field(description="标识字段")
    timestamps: Dict[str, List[str]] = Field(description="时间字段")
    descriptions: Dict[str, List[str]] = Field(description="描述字段")

class ERRelation(BaseModel):
    """实体关系"""
    from_table: str
    to_table: str
    from_column: str
    to_column: str
    relation_type: str  # one-to-one, one-to-many, many-to-many
    confidence: float = Field(ge=0, le=1)

class QueryScenario(BaseModel):
    """查询场景"""
    scenario_type: str
    complexity: str  # simple, medium, complex
    tables_involved: List[str]
    operations: List[str]  # SELECT, JOIN, GROUP BY, etc.
    filters: List[str]
    aggregations: List[str]

class GeneratedSQL(BaseModel):
    """生成的 SQL"""
    sql: str
    confidence: float = Field(ge=0, le=1)
    tables_used: List[str]
    explanation: str
    warnings: List[str] = []
    alternatives: List[str] = []
```

## 2. 轨迹记录器设计（参考 TRAEAgent）

```python
# utils/trajectory_recorder.py
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib

class TrajectoryRecorder:
    """轨迹记录器 - 记录完整的执行过程"""
    
    def __init__(self, trajectory_dir: str = "trajectories"):
        self.trajectory_dir = Path(trajectory_dir)
        self.trajectory_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成唯一文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_id = hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]
        self.trajectory_path = self.trajectory_dir / f"trajectory_{timestamp}_{random_id}.json"
        
        # 初始化轨迹数据
        self.trajectory_data = {
            "metadata": {
                "version": "1.0",
                "agent_type": "nl2sql",
                "start_time": datetime.now().isoformat(),
                "end_time": None,
                "duration": None
            },
            "task": {
                "query": "",
                "database": "",
                "model": ""
            },
            "execution": {
                "steps": [],
                "tool_calls": [],
                "llm_interactions": []
            },
            "result": {
                "success": False,
                "final_sql": None,
                "error": None,
                "token_usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0
                }
            }
        }
    
    def start_recording(self, task: str, model: str, database: str):
        """开始记录"""
        self.trajectory_data["task"] = {
            "query": task,
            "database": database,
            "model": model
        }
    
    def record_llm_interaction(self, messages: List[LLMMessage], response: LLMResponse):
        """记录 LLM 交互"""
        interaction = {
            "timestamp": datetime.now().isoformat(),
            "messages": [
                {"role": msg.role, "content": msg.content[:500]}  # 截断长内容
                for msg in messages[-3:]  # 只记录最近3条消息
            ],
            "response": {
                "content": response.content[:500] if response.content else None,
                "tool_calls": [
                    {"name": tc.name, "arguments": tc.arguments}
                    for tc in (response.tool_calls or [])
                ],
                "usage": response.usage
            }
        }
        
        self.trajectory_data["execution"]["llm_interactions"].append(interaction)
        
        # 更新 token 使用
        if response.usage:
            for key in ["prompt_tokens", "completion_tokens", "total_tokens"]:
                self.trajectory_data["result"]["token_usage"][key] += response.usage.get(key, 0)
    
    def record_agent_step(self, step: AgentStep):
        """记录智能体步骤"""
        step_data = {
            "step_number": step.step_number,
            "state": step.state.value,
            "timestamp": step.timestamp.isoformat(),
            "duration": None
        }
        
        # 记录思考内容
        if step.llm_response and step.state == AgentStepState.THINKING:
            step_data["thought"] = step.llm_response.content[:200]
        
        # 记录工具调用
        if step.tool_calls:
            step_data["tool_calls"] = [
                {"name": tc.name, "arguments": tc.arguments}
                for tc in step.tool_calls
            ]
        
        # 记录工具结果
        if step.tool_results:
            step_data["tool_results"] = [
                {
                    "tool": tr.tool_name,
                    "success": tr.success,
                    "summary": self._summarize_tool_result(tr)
                }
                for tr in step.tool_results
            ]
        
        # 记录反思
        if step.reflection:
            step_data["reflection"] = step.reflection
        
        self.trajectory_data["execution"]["steps"].append(step_data)
    
    def record_tool_call(self, tool_name: str, arguments: Dict[str, Any], 
                        result: ToolResult, duration: float):
        """记录工具调用详情"""
        tool_call = {
            "timestamp": datetime.now().isoformat(),
            "tool": tool_name,
            "arguments": arguments,
            "success": result.success,
            "duration": duration,
            "result_summary": self._summarize_tool_result(result)
        }
        
        if not result.success:
            tool_call["error"] = result.error
        
        self.trajectory_data["execution"]["tool_calls"].append(tool_call)
    
    def _summarize_tool_result(self, result: ToolResult) -> str:
        """总结工具结果"""
        if not result.success:
            return f"Error: {result.error}"
        
        if result.tool_name == "schema_extraction":
            data = result.data or {}
            return f"Extracted {len(data.get('tables', []))} tables"
        elif result.tool_name == "sql_generation":
            data = result.data or {}
            return f"Generated SQL with confidence {data.get('confidence', 0)}"
        else:
            return "Success"
    
    def finalize_recording(self, success: bool, final_sql: str = None, error: str = None):
        """完成记录"""
        end_time = datetime.now()
        start_time = datetime.fromisoformat(self.trajectory_data["metadata"]["start_time"])
        
        self.trajectory_data["metadata"]["end_time"] = end_time.isoformat()
        self.trajectory_data["metadata"]["duration"] = (end_time - start_time).total_seconds()
        
        self.trajectory_data["result"]["success"] = success
        self.trajectory_data["result"]["final_sql"] = final_sql
        self.trajectory_data["result"]["error"] = error
        
        # 保存到文件
        self.save()
    
    def save(self):
        """保存轨迹到文件"""
        with open(self.trajectory_path, 'w', encoding='utf-8') as f:
            json.dump(self.trajectory_data, f, ensure_ascii=False, indent=2)
    
    def get_summary(self) -> Dict[str, Any]:
        """获取执行摘要"""
        return {
            "task": self.trajectory_data["task"]["query"],
            "success": self.trajectory_data["result"]["success"],
            "steps_count": len(self.trajectory_data["execution"]["steps"]),
            "tools_called": len(self.trajectory_data["execution"]["tool_calls"]),
            "total_tokens": self.trajectory_data["result"]["token_usage"]["total_tokens"],
            "duration": self.trajectory_data["metadata"]["duration"]
        }
```

## 3. 提示词模板管理（Jinja2）

### 3.1 模板管理器

```python
# prompts/prompt_manager.py
from jinja2 import Environment, FileSystemLoader, Template, select_autoescape
from pathlib import Path
from typing import Dict, Any, Optional
import yaml
import json

class PromptManager:
    """Jinja2 提示词模板管理器"""
    
    def __init__(self, template_dir: str = None):
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"
        
        self.template_dir = Path(template_dir)
        
        # 初始化 Jinja2 环境
        self.env = Environment(
            loader=FileSystemLoader([
                str(self.template_dir),
                str(self.template_dir / "analysis"),
                str(self.template_dir / "generation"),
                str(self.template_dir / "system")
            ]),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # 添加自定义过滤器
        self.env.filters['json'] = json.dumps
        self.env.filters['yaml'] = yaml.dump
        
        # 加载配置
        self.config = self._load_config()
        self.examples = self._load_examples()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载提示词配置"""
        config_path = self.template_dir.parent / "config.yaml"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        return {}
    
    def _load_examples(self) -> Dict[str, List[Dict[str, Any]]]:
        """加载 few-shot 示例"""
        examples = {}
        examples_dir = self.template_dir.parent / "examples"
        
        if examples_dir.exists():
            for file in examples_dir.glob("*.yaml"):
                with open(file, 'r', encoding='utf-8') as f:
                    examples[file.stem] = yaml.safe_load(f)
        
        return examples
    
    def get_prompt(self, template_name: str, **kwargs) -> str:
        """获取渲染后的提示词"""
        # 添加 .j2 后缀
        if not template_name.endswith('.j2'):
            template_name += '.j2'
        
        template = self.env.get_template(template_name)
        
        # 合并上下文
        context = {
            "config": self.config,
            "examples": self.examples.get(template_name.replace('.j2', ''), []),
            **kwargs
        }
        
        return template.render(context)
    
    def get_system_prompt(self, agent_type: str = "nl2sql") -> str:
        """获取系统提示词"""
        return self.get_prompt(f"system/{agent_type}_system")
    
    def format_schema(self, schema: Dict[str, Any]) -> str:
        """格式化数据库 schema"""
        return self.get_prompt("formatters/schema_formatter", schema=schema)
    
    def format_examples(self, examples: List[Dict[str, Any]], max_examples: int = 3) -> str:
        """格式化示例"""
        return self.get_prompt(
            "formatters/examples_formatter",
            examples=examples[:max_examples]
        )
```

### 3.2 提示词模板示例

```jinja2
{# prompts/templates/system/nl2sql_system.j2 #}
你是一个专业的数据库专家，擅长将自然语言查询转换为准确的 SQL 语句。

## 你的能力
1. 深入理解数据库结构和业务逻辑
2. 准确识别查询意图
3. 生成高效、准确的 SQL 语句
4. 考虑边界情况和数据完整性

## 工作流程
1. 首先提取并分析数据库结构
2. 理解业务领域和数据关系
3. 分析用户查询意图
4. 生成并优化 SQL 语句

## 可用工具
你可以使用以下工具来完成任务：
- schema_extraction: 提取数据库结构
- initial_domain_analysis: 分析业务领域
- field_classification: 字段分类
- table_description: 生成表描述
- column_description: 生成列描述
- er_analysis: 实体关系分析
- scenario_generation: 场景识别
- sql_generation: SQL 生成
- sequential_thinking: 深度思考（用于复杂问题）
- task_done: 标记任务完成

## 注意事项
- 始终先了解数据库结构再生成 SQL
- 考虑查询性能和优化
- 处理可能的空值和异常情况
- 生成的 SQL 必须符合 MySQL 语法
```

```jinja2
{# prompts/templates/analysis/schema_extraction.j2 #}
## 任务
分析数据库 {{ database_name }} 的结构信息。

## 当前信息
数据库包含 {{ schema.tables | length }} 个表。

## 分析要求
1. **表的用途识别**
   - 每个表的业务含义
   - 表的数据类型（事实表/维度表/关联表）
   - 表的重要程度

2. **字段分析**
   - 关键字段识别
   - 字段的业务含义
   - 字段之间的关联

3. **关系分析**
   - 主外键关系
   - 隐式关系（通过命名规则）
   - 关系的业务含义

4. **数据特征**
   - 数据量级
   - 更新频率推测
   - 数据质量评估

{% if examples %}
## 参考示例
{% for example in examples[:2] %}
### 示例 {{ loop.index }}
输入：{{ example.input }}
输出：{{ example.output }}
{% endfor %}
{% endif %}

## 输出要求
请以结构化的方式输出分析结果，便于后续步骤使用。
```

## 4. 工具设计规范

### 4.1 工具基类

```python
# tools/base.py
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, Optional, List
from abc import abstractmethod
import time
import traceback

class ToolExecutionContext(BaseModel):
    """工具执行上下文"""
    trajectory_recorder: Optional[Any] = Field(default=None, exclude=True)
    database_connector: Optional[Any] = Field(default=None, exclude=True)
    prompt_manager: Optional[Any] = Field(default=None, exclude=True)
    shared_context: Dict[str, Any] = Field(default_factory=dict)

class BaseNL2SQLTool(BaseTool):
    """NL2SQL 工具基类"""
    
    # 执行上下文
    context: ToolExecutionContext = Field(default_factory=ToolExecutionContext)
    
    # 工具元数据
    tags: List[str] = []
    
    def _run(self, **kwargs) -> Dict[str, Any]:
        """执行工具（同步）"""
        start_time = time.time()
        
        try:
            # 验证输入
            if hasattr(self, 'args_schema'):
                self.args_schema(**kwargs)
            
            # 执行具体逻辑
            result = self.execute(**kwargs)
            
            # 构建成功结果
            tool_result = ToolResult(
                success=True,
                data=result,
                tool_name=self.name,
                execution_time=time.time() - start_time
            )
            
            # 记录执行
            if self.context.trajectory_recorder:
                self.context.trajectory_recorder.record_tool_call(
                    tool_name=self.name,
                    arguments=kwargs,
                    result=tool_result,
                    duration=tool_result.execution_time
                )
            
            return tool_result.dict()
            
        except Exception as e:
            # 构建错误结果
            tool_result = ToolResult(
                success=False,
                error=str(e),
                tool_name=self.name,
                execution_time=time.time() - start_time,
                data={"traceback": traceback.format_exc()}
            )
            
            # 记录错误
            if self.context.trajectory_recorder:
                self.context.trajectory_recorder.record_tool_call(
                    tool_name=self.name,
                    arguments=kwargs,
                    result=tool_result,
                    duration=tool_result.execution_time
                )
            
            return tool_result.dict()
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行具体逻辑"""
        pass
    
    def update_shared_context(self, key: str, value: Any):
        """更新共享上下文"""
        self.context.shared_context[key] = value
    
    def get_from_shared_context(self, key: str, default: Any = None) -> Any:
        """从共享上下文获取数据"""
        return self.context.shared_context.get(key, default)
```

### 4.2 具体工具实现示例

```python
# tools/initial_domain_analysis_tool.py
from typing import Dict, Any
from pydantic import BaseModel, Field
from tools.base import BaseNL2SQLTool
from models.schemas import DomainAnalysis

class InitialDomainAnalysisTool(BaseNL2SQLTool):
    """初始领域分析工具"""
    
    name = "initial_domain_analysis"
    description = "基于数据库结构分析业务领域，识别核心实体和业务规则"
    tags = ["analysis", "domain"]
    
    class InputSchema(BaseModel):
        schema_info: Dict[str, Any] = Field(description="数据库结构信息")
        user_query: str = Field(description="用户查询")
    
    args_schema = InputSchema
    
    def execute(self, schema_info: Dict[str, Any], user_query: str) -> Dict[str, Any]:
        """执行领域分析"""
        # 获取提示词
        prompt = self.context.prompt_manager.get_prompt(
            "analysis/domain_analysis",
            schema=schema_info,
            query=user_query
        )
        
        # 调用 LLM
        from utils.llm_client import get_llm
        llm = get_llm()
        response = llm.invoke(prompt)
        
        # 解析结果
        from utils.output_parser import parse_domain_analysis
        domain_analysis = parse_domain_analysis(response)
        
        # 更新共享上下文
        self.update_shared_context("domain_analysis", domain_analysis)
        
        return {
            "domain": domain_analysis.domain,
            "description": domain_analysis.description,
            "key_entities": domain_analysis.key_entities,
            "business_rules": domain_analysis.business_rules,
            "confidence": 0.85
        }

# tools/sql_generation_tool.py
class SQLGenerationTool(BaseNL2SQLTool):
    """SQL 生成工具"""
    
    name = "sql_generation"
    description = "基于分析结果生成 SQL 语句"
    tags = ["generation", "sql"]
    
    class InputSchema(BaseModel):
        user_query: str = Field(description="用户查询")
        schema_info: Dict[str, Any] = Field(description="数据库结构")
        domain_analysis: Optional[Dict[str, Any]] = Field(description="领域分析")
        field_classification: Optional[Dict[str, Any]] = Field(description="字段分类")
        scenario: Optional[Dict[str, Any]] = Field(description="查询场景")
    
    args_schema = InputSchema
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """生成 SQL"""
        # 构建完整上下文
        context = {
            "query": kwargs["user_query"],
            "schema": kwargs["schema_info"],
            "domain": kwargs.get("domain_analysis") or self.get_from_shared_context("domain_analysis"),
            "fields": kwargs.get("field_classification") or self.get_from_shared_context("field_classification"),
            "scenario": kwargs.get("scenario") or self.get_from_shared_context("scenario")
        }
        
        # 获取提示词
        prompt = self.context.prompt_manager.get_prompt(
            "generation/sql_generation",
            **context
        )
        
        # 生成 SQL
        from utils.llm_client import get_llm
        llm = get_llm()
        response = llm.invoke(prompt)
        
        # 解析 SQL
        from utils.sql_parser import parse_sql_response
        sql_result = parse_sql_response(response)
        
        # 验证 SQL
        validation = self._validate_sql(sql_result.sql, kwargs["schema_info"])
        
        return {
            "sql": sql_result.sql,
            "confidence": sql_result.confidence,
            "explanation": sql_result.explanation,
            "tables_used": sql_result.tables_used,
            "warnings": validation.get("warnings", []),
            "valid": validation.get("valid", True)
        }
    
    def _validate_sql(self, sql: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """验证 SQL 语法和逻辑"""
        warnings = []
        
        # 检查表是否存在
        import re
        table_pattern = r'FROM\s+(\w+)|JOIN\s+(\w+)'
        matches = re.findall(table_pattern, sql, re.IGNORECASE)
        
        available_tables = {t["name"] for t in schema.get("tables", [])}
        for match in matches:
            table = match[0] or match[1]
            if table and table not in available_tables:
                warnings.append(f"表 {table} 不存在于数据库中")
        
        return {
            "valid": len(warnings) == 0,
            "warnings": warnings
        }
```

## 5. LLM 客户端和输出解析

### 5.1 LLM 客户端

```python
# utils/llm_client.py
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from typing import List, Dict, Any
from config.settings import settings

_llm_instance = None

def get_llm():
    """获取 LLM 实例（单例）"""
    global _llm_instance
    
    if _llm_instance is None:
        _llm_instance = ChatOpenAI(
            model=settings.model_name,
            openai_api_key=settings.api_key,
            openai_api_base=settings.base_url,
            temperature=settings.temperature,
            max_tokens=2048
        )
    
    return _llm_instance

class LLMClient:
    """LLM 客户端封装"""
    
    def __init__(self, model_config: Dict[str, Any]):
        self.llm = ChatOpenAI(
            model=model_config.get("name", "gpt-4"),
            openai_api_key=model_config.get("api_key", ""),
            openai_api_base=model_config.get("base_url", ""),
            temperature=model_config.get("temperature", 0.1)
        )
        self.model = model_config.get("name", "gpt-4")
    
    def chat(self, messages: List[LLMMessage], tools: List[BaseNL2SQLTool] = None) -> LLMResponse:
        """发送聊天请求"""
        # 转换消息格式
        langchain_messages = []
        for msg in messages:
            if msg.role == "system":
                langchain_messages.append(SystemMessage(content=msg.content))
            elif msg.role == "user":
                langchain_messages.append(HumanMessage(content=msg.content))
        
        # 绑定工具
        if tools:
            llm_with_tools = self.llm.bind_tools(tools)
            response = llm_with_tools.invoke(langchain_messages)
        else:
            response = self.llm.invoke(langchain_messages)
        
        # 转换响应
        return LLMResponse(
            content=response.content,
            tool_calls=self._extract_tool_calls(response),
            usage=response.response_metadata.get("token_usage")
        )
    
    def _extract_tool_calls(self, response) -> List[ToolCall]:
        """提取工具调用"""
        tool_calls = []
        
        if hasattr(response, 'tool_calls'):
            for tc in response.tool_calls:
                tool_calls.append(ToolCall(
                    id=tc.get("id", ""),
                    name=tc.get("name", ""),
                    arguments=tc.get("args", {})
                ))
        
        return tool_calls
```

### 5.2 输出解析器

```python
# utils/output_parser.py
from typing import Dict, Any, Type, TypeVar
from pydantic import BaseModel
import json
import re
from models.schemas import *

T = TypeVar('T', bound=BaseModel)

def parse_json_response(text: str) -> Dict[str, Any]:
    """从文本中提取 JSON"""
    # 尝试直接解析
    try:
        return json.loads(text)
    except:
        pass
    
    # 查找 JSON 代码块
    json_pattern = r'```json\s*(.*?)\s*```'
    matches = re.findall(json_pattern, text, re.DOTALL)
    if matches:
        try:
            return json.loads(matches[0])
        except:
            pass
    
    # 查找大括号
    brace_pattern = r'\{[^{}]*\}'
    matches = re.findall(brace_pattern, text, re.DOTALL)
    for match in reversed(matches):  # 从后往前，通常最后的更完整
        try:
            return json.loads(match)
        except:
            continue
    
    return {}

def parse_model_response(text: str, model_class: Type[T]) -> T:
    """解析为 Pydantic 模型"""
    try:
        # 尝试提取 JSON
        data = parse_json_response(text)
        return model_class(**data)
    except:
        # 降级处理：从文本中提取信息
        return extract_from_text(text, model_class)

def parse_domain_analysis(text: str) -> DomainAnalysis:
    """解析领域分析结果"""
    return parse_model_response(text, DomainAnalysis)

def parse_sql_response(text: str) -> GeneratedSQL:
    """解析 SQL 生成结果"""
    # 提取 SQL
    sql = extract_sql_from_text(text)
    if not sql:
        raise ValueError("未找到有效的 SQL 语句")
    
    # 尝试结构化解析
    try:
        return parse_model_response(text, GeneratedSQL)
    except:
        # 降级：手动构建
        return GeneratedSQL(
            sql=sql,
            confidence=0.8,
            tables_used=extract_tables_from_sql(sql),
            explanation=extract_explanation_from_text(text),
            warnings=[]
        )

def extract_sql_from_text(text: str) -> str:
    """从文本中提取 SQL"""
    # SQL 代码块
    sql_pattern = r'```sql\s*(.*?)\s*```'
    matches = re.findall(sql_pattern, text, re.DOTALL | re.IGNORECASE)
    if matches:
        return matches[0].strip()
    
    # SELECT 语句
    select_pattern = r'(SELECT\s+.*?(?:;|$))'
    matches = re.findall(select_pattern, text, re.DOTALL | re.IGNORECASE)
    if matches:
        return matches[0].strip()
    
    return ""

def extract_tables_from_sql(sql: str) -> List[str]:
    """从 SQL 中提取表名"""
    tables = set()
    
    # FROM 和 JOIN 子句
    patterns = [
        r'FROM\s+`?(\w+)`?',
        r'JOIN\s+`?(\w+)`?'
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, sql, re.IGNORECASE)
        tables.update(matches)
    
    return list(tables)
```

## 6. 数据库连接器

```python
# utils/database_connector.py
import pymysql
from typing import Dict, Any, List, Optional
from contextlib import contextmanager

class DatabaseConnector:
    """MySQL 数据库连接器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._connection = None
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接上下文"""
        conn = pymysql.connect(
            host=self.config['host'],
            port=self.config.get('port', 3306),
            user=self.config['user'],
            password=self.config['password'],
            database=self.config['database'],
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        try:
            yield conn
        finally:
            conn.close()
    
    def get_tables(self) -> List[Dict[str, Any]]:
        """获取所有表信息"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                query = """
                    SELECT 
                        TABLE_NAME as name,
                        TABLE_COMMENT as comment,
                        TABLE_ROWS as row_count
                    FROM information_schema.TABLES
                    WHERE TABLE_SCHEMA = DATABASE()
                    ORDER BY TABLE_NAME
                """
                cursor.execute(query)
                return cursor.fetchall()
    
    def get_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """获取表的列信息"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                query = """
                    SELECT 
                        COLUMN_NAME as name,
                        DATA_TYPE as type,
                        IS_NULLABLE = 'YES' as nullable,
                        COLUMN_DEFAULT as default_value,
                        COLUMN_COMMENT as comment,
                        COLUMN_KEY = 'PRI' as is_primary,
                        COLUMN_KEY = 'MUL' as is_foreign
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE() 
                    AND TABLE_NAME = %s
                    ORDER BY ORDINAL_POSITION
                """
                cursor.execute(query, (table_name,))
                return cursor.fetchall()
    
    def test_connection(self) -> bool:
        """测试连接"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    return True
        except Exception:
            return False
```