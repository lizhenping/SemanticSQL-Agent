# SemanticSQL-Agent 架构设计文档（基于 TRAEAgent 模式）

## 1. 项目概述

SemanticSQL-Agent 是一个基于智能体架构的自然语言到SQL转换系统，继承 TRAEAgent 的设计理念，使用 LangChain 的工具系统，并借鉴 nl2sql_pipeline 的格式化输出方式。

### 1.1 核心特性
- 基于 ReAct (Thought-Action-Observation) 模式
- LangChain 工具系统
- 结构化的轨迹记录（参考 TRAEAgent）
- Jinja2 提示词模板管理（参考 nl2sql_pipeline）
- 格式化的输入输出

### 1.2 技术栈
- **智能体框架**: 参考 TRAEAgent 设计
- **工具系统**: LangChain Tools
- **提示词**: Jinja2 模板
- **数据验证**: Pydantic
- **数据库**: MySQL (通过 pymysql)

## 2. 架构层次设计

```
semanticsql-agent/
│
├── config/
│   ├── __init__.py
│   ├── settings.py              # 全局配置
│   └── database.py              # 数据库配置
│
├── models/
│   ├── __init__.py
│   ├── agent_basics.py          # 智能体基础类型（参考 TRAEAgent）
│   ├── schemas.py               # 输入输出模式定义
│   └── database.py              # 数据库模型
│
├── tools/
│   ├── __init__.py
│   ├── base.py                  # LangChain Tool 基类
│   ├── schema_extraction_tool.py
│   ├── initial_domain_analysis_tool.py  
│   ├── field_classification_tool.py
│   ├── table_description_tool.py
│   ├── column_description_tool.py
│   ├── er_analysis_tool.py
│   ├── scenario_generation_tool.py
│   ├── sql_generation_tool.py
│   ├── sequential_thinking_tool.py
│   └── task_done_tool.py
│
├── prompts/
│   ├── __init__.py
│   ├── templates/               # Jinja2 模板目录
│   │   ├── analysis/
│   │   │   ├── schema_extraction.j2
│   │   │   ├── domain_analysis.j2
│   │   │   └── field_classification.j2
│   │   └── generation/
│   │       ├── sql_generation.j2
│   │       └── scenario_generation.j2
│   ├── examples/                # Few-shot 示例
│   └── prompt_manager.py        # Jinja2 模板管理器
│
├── agent/
│   ├── __init__.py
│   ├── agent_basics.py          # 基础类型定义
│   ├── base_agent.py            # 基础智能体（参考 TRAEAgent）
│   └── nl2sql_agent.py          # NL2SQL 智能体实现
│
├── utils/
│   ├── __init__.py
│   ├── database_connector.py    # 数据库连接管理
│   ├── llm_client.py           # LLM 客户端
│   ├── trajectory_recorder.py   # 轨迹记录（参考 TRAEAgent）
│   └── output_parser.py         # 输出解析器
│
└── cli.py                       # 命令行接口
```

## 3. 核心组件设计

### 3.1 智能体基础类型（参考 TRAEAgent）

```python
# models/agent_basics.py
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

class AgentState(Enum):
    """智能体状态"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"

class AgentStepState(Enum):
    """步骤状态 - TAO 模式"""
    THINKING = "thinking"
    CALLING_TOOL = "calling_tool"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    ERROR = "error"

@dataclass
class AgentStep:
    """执行步骤"""
    step_number: int
    state: AgentStepState
    llm_response: Optional['LLMResponse'] = None
    tool_calls: Optional[List['ToolCall']] = None
    tool_results: Optional[List['ToolResult']] = None
    reflection: Optional[str] = None
    error: Optional[str] = None

@dataclass
class AgentExecution:
    """执行记录"""
    task: str
    steps: List[AgentStep]
    agent_state: AgentState = AgentState.IDLE
    final_result: Optional[str] = None
    success: bool = False
    total_tokens: Optional[int] = None
    execution_time: Optional[float] = None
```

### 3.2 轨迹记录器（参考 TRAEAgent）

```python
# utils/trajectory_recorder.py
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

class TrajectoryRecorder:
    """结构化的轨迹记录器"""
    
    def __init__(self, trajectory_path: str = None):
        if trajectory_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            trajectory_path = f"trajectories/nl2sql_{timestamp}.json"
            
        self.trajectory_path = Path(trajectory_path)
        self.trajectory_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.trajectory_data = {
            "task": "",
            "start_time": "",
            "end_time": "",
            "model": "",
            "database": "",
            "agent_steps": [],
            "tool_executions": [],
            "final_sql": None,
            "success": False,
            "execution_time": 0.0
        }
    
    def start_recording(self, task: str, model: str, database: str):
        """开始记录"""
        self.trajectory_data.update({
            "task": task,
            "start_time": datetime.now().isoformat(),
            "model": model,
            "database": database
        })
    
    def record_agent_step(self, step: AgentStep):
        """记录智能体步骤"""
        step_data = {
            "step_number": step.step_number,
            "state": step.state.value,
            "timestamp": datetime.now().isoformat()
        }
        
        if step.llm_response:
            step_data["llm_response"] = {
                "content": step.llm_response.content,
                "tool_calls": [tc.dict() for tc in step.llm_response.tool_calls or []]
            }
        
        if step.tool_results:
            step_data["tool_results"] = [
                {
                    "tool": tr.tool_name,
                    "success": tr.success,
                    "data": tr.data,
                    "error": tr.error
                }
                for tr in step.tool_results
            ]
        
        if step.reflection:
            step_data["reflection"] = step.reflection
            
        self.trajectory_data["agent_steps"].append(step_data)
    
    def record_tool_execution(self, tool_name: str, input_data: Dict, output_data: Dict, duration: float):
        """记录工具执行详情"""
        self.trajectory_data["tool_executions"].append({
            "tool": tool_name,
            "input": input_data,
            "output": output_data,
            "duration": duration,
            "timestamp": datetime.now().isoformat()
        })
    
    def finalize_recording(self, success: bool, final_sql: str = None):
        """完成记录"""
        self.trajectory_data.update({
            "end_time": datetime.now().isoformat(),
            "success": success,
            "final_sql": final_sql,
            "execution_time": self._calculate_execution_time()
        })
        
        # 保存到文件
        with open(self.trajectory_path, 'w', encoding='utf-8') as f:
            json.dump(self.trajectory_data, f, ensure_ascii=False, indent=2)
```

### 3.3 提示词管理器（Jinja2）

```python
# prompts/prompt_manager.py
from jinja2 import Environment, FileSystemLoader, Template
from pathlib import Path
from typing import Dict, Any
import yaml

class PromptManager:
    """Jinja2 提示词模板管理器"""
    
    def __init__(self, template_dir: str = None):
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"
        
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # 加载示例数据
        self.examples = self._load_examples()
    
    def _load_examples(self) -> Dict[str, Any]:
        """加载 few-shot 示例"""
        examples_path = Path(__file__).parent / "examples"
        examples = {}
        
        for file in examples_path.glob("*.yaml"):
            with open(file, 'r', encoding='utf-8') as f:
                examples[file.stem] = yaml.safe_load(f)
        
        return examples
    
    def get_prompt(self, template_name: str, **kwargs) -> str:
        """获取渲染后的提示词"""
        template = self.env.get_template(f"{template_name}.j2")
        
        # 添加通用上下文
        context = {
            "examples": self.examples.get(template_name, []),
            **kwargs
        }
        
        return template.render(context)
    
    def get_system_prompt(self, agent_type: str = "nl2sql") -> str:
        """获取系统提示词"""
        return self.get_prompt(f"system/{agent_type}_system")
```

### 3.4 工具基类设计

```python
# tools/base.py
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, Optional
from abc import abstractmethod
import time

class BaseNL2SQLTool(BaseTool):
    """NL2SQL 工具基类"""
    
    # 轨迹记录器
    trajectory_recorder: Optional['TrajectoryRecorder'] = Field(default=None, exclude=True)
    
    def _run(self, **kwargs) -> Dict[str, Any]:
        """执行工具并记录轨迹"""
        start_time = time.time()
        
        try:
            # 执行具体逻辑
            result = self.execute(**kwargs)
            
            # 记录成功执行
            if self.trajectory_recorder:
                self.trajectory_recorder.record_tool_execution(
                    tool_name=self.name,
                    input_data=kwargs,
                    output_data=result,
                    duration=time.time() - start_time
                )
            
            return {
                "success": True,
                "data": result,
                "tool_name": self.name
            }
            
        except Exception as e:
            # 记录失败
            if self.trajectory_recorder:
                self.trajectory_recorder.record_tool_execution(
                    tool_name=self.name,
                    input_data=kwargs,
                    output_data={"error": str(e)},
                    duration=time.time() - start_time
                )
            
            return {
                "success": False,
                "error": str(e),
                "tool_name": self.name
            }
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行具体逻辑"""
        pass
```

### 3.5 具体工具实现示例

```python
# tools/schema_extraction_tool.py
from typing import Dict, Any
from tools.base import BaseNL2SQLTool
from pydantic import BaseModel, Field

class SchemaExtractionTool(BaseNL2SQLTool):
    """数据库结构提取工具"""
    
    name = "schema_extraction"
    description = "提取数据库的表结构信息，包括表、列、主键、外键等"
    
    class InputSchema(BaseModel):
        database_name: str = Field(description="数据库名称")
        include_stats: bool = Field(default=True, description="是否包含统计信息")
    
    args_schema = InputSchema
    
    # 数据库连接
    db_connector: Any = Field(exclude=True)
    
    def execute(self, database_name: str, include_stats: bool = True) -> Dict[str, Any]:
        """执行 schema 提取"""
        # 获取所有表
        tables = self.db_connector.get_tables()
        
        # 构建结构化的 schema 信息
        schema_info = {
            "database": database_name,
            "tables": []
        }
        
        for table in tables:
            table_info = {
                "name": table["name"],
                "comment": table.get("comment", ""),
                "columns": self.db_connector.get_columns(table["name"]),
                "primary_key": self.db_connector.get_primary_key(table["name"]),
                "foreign_keys": self.db_connector.get_foreign_keys(table["name"])
            }
            
            if include_stats:
                table_info["row_count"] = self.db_connector.get_table_row_count(
                    table["name"], database_name
                )
            
            schema_info["tables"].append(table_info)
        
        # 生成格式化的描述
        schema_info["formatted_schema"] = self._format_schema(schema_info["tables"])
        
        return schema_info
    
    def _format_schema(self, tables: list) -> str:
        """格式化 schema 为文本描述"""
        lines = [f"数据库包含 {len(tables)} 个表:\n"]
        
        for table in tables:
            lines.append(f"表: {table['name']}")
            if table.get('comment'):
                lines.append(f"  描述: {table['comment']}")
            lines.append(f"  列数: {len(table['columns'])}")
            if table.get('row_count', -1) >= 0:
                lines.append(f"  行数: {table['row_count']}")
            
            # 列信息
            lines.append("  列:")
            for col in table['columns'][:10]:  # 只显示前10列
                col_desc = f"    - {col['name']}: {col['type']}"
                if col.get('comment'):
                    col_desc += f" ({col['comment']})"
                lines.append(col_desc)
            
            if len(table['columns']) > 10:
                lines.append(f"    ... 还有 {len(table['columns']) - 10} 列")
            
            lines.append("")
        
        return "\n".join(lines)
```

## 4. 基础智能体实现（参考 TRAEAgent）

```python
# agent/base_agent.py
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import time

class BaseAgent(ABC):
    """基础智能体类 - 参考 TRAEAgent"""
    
    def __init__(self, config: 'AgentConfig'):
        self._llm_client = LLMClient(config.model)
        self._tools: List[BaseNL2SQLTool] = []
        self._trajectory_recorder = TrajectoryRecorder()
        self._max_steps = config.max_steps
        self._prompt_manager = PromptManager()
        
    def execute_task(self) -> AgentExecution:
        """执行任务 - TAO 循环"""
        start_time = time.time()
        execution = AgentExecution(task=self._task, steps=[])
        messages = self._initial_messages
        
        try:
            execution.agent_state = AgentState.RUNNING
            
            for step_number in range(1, self._max_steps + 1):
                step = AgentStep(step_number=step_number)
                
                # Thought 阶段
                step.state = AgentStepState.THINKING
                llm_response = self._llm_client.chat(messages, self._tools)
                step.llm_response = llm_response
                
                # 检查是否完成
                if self._is_task_completed(llm_response):
                    execution.agent_state = AgentState.COMPLETED
                    execution.final_result = llm_response.content
                    execution.success = True
                    break
                
                # Action 阶段
                if llm_response.tool_calls:
                    step.state = AgentStepState.CALLING_TOOL
                    tool_results = self._execute_tools(llm_response.tool_calls)
                    step.tool_results = tool_results
                    
                    # Observation 阶段
                    for result in tool_results:
                        messages.append(self._format_tool_result(result))
                    
                    # 简单反思
                    reflection = self.reflect_on_result(tool_results)
                    if reflection:
                        step.state = AgentStepState.REFLECTING
                        step.reflection = reflection
                        messages.append(LLMMessage(role="assistant", content=reflection))
                
                # 记录步骤
                self._trajectory_recorder.record_agent_step(step)
                execution.steps.append(step)
                
        except Exception as e:
            execution.agent_state = AgentState.ERROR
            execution.final_result = f"Error: {str(e)}"
            
        execution.execution_time = time.time() - start_time
        return execution
    
    def reflect_on_result(self, tool_results: List[ToolResult]) -> Optional[str]:
        """简单的反思机制"""
        failed_results = [r for r in tool_results if not r.success]
        if not failed_results:
            return None
            
        reflections = []
        for result in failed_results:
            reflections.append(
                f"工具 {result.tool_name} 执行失败: {result.error}。"
                "需要调整参数或尝试其他方法。"
            )
        
        return "\n".join(reflections)
```

## 5. 主智能体实现

```python
# agent/nl2sql_agent.py
from typing import List, Dict, Any
from agent.base_agent import BaseAgent
from tools import *

class NL2SQLAgent(BaseAgent):
    """NL2SQL 智能体"""
    
    def __init__(self, config: 'AgentConfig'):
        super().__init__(config)
        
        # 初始化数据库连接
        from utils.database_connector import DatabaseConnector
        self.db_connector = DatabaseConnector(config.database)
        
        # 初始化工具
        self._initialize_tools()
        
    def _initialize_tools(self):
        """初始化所有工具"""
        self._tools = [
            SchemaExtractionTool(db_connector=self.db_connector, trajectory_recorder=self._trajectory_recorder),
            InitialDomainAnalysisTool(trajectory_recorder=self._trajectory_recorder),
            FieldClassificationTool(db_connector=self.db_connector, trajectory_recorder=self._trajectory_recorder),
            TableDescriptionTool(trajectory_recorder=self._trajectory_recorder),
            ColumnDescriptionTool(trajectory_recorder=self._trajectory_recorder),
            ERAnalysisTool(trajectory_recorder=self._trajectory_recorder),
            ScenarioGenerationTool(trajectory_recorder=self._trajectory_recorder),
            SQLGenerationTool(trajectory_recorder=self._trajectory_recorder),
            SequentialThinkingTool(trajectory_recorder=self._trajectory_recorder),
            TaskDoneTool()
        ]
    
    def new_task(self, query: str, database: str):
        """创建新任务"""
        self._task = query
        
        # 使用 Jinja2 模板生成系统提示词
        system_prompt = self._prompt_manager.get_system_prompt("nl2sql")
        
        self._initial_messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(
                role="user", 
                content=f"数据库: {database}\n查询需求: {query}"
            )
        ]
        
        # 开始记录
        self._trajectory_recorder.start_recording(
            task=query,
            model=self._llm_client.model,
            database=database
        )
    
    def execute_task(self) -> AgentExecution:
        """执行任务并完成记录"""
        execution = super().execute_task()
        
        # 完成轨迹记录
        if execution.success:
            # 从最后的响应中提取 SQL
            final_sql = self._extract_sql_from_response(execution.final_result)
            self._trajectory_recorder.finalize_recording(
                success=True,
                final_sql=final_sql
            )
        else:
            self._trajectory_recorder.finalize_recording(
                success=False
            )
        
        return execution
```

## 6. 配置示例

```yaml
# config.yaml
model:
  name: "Qwen3-14B"
  api_key: "not-needed"
  base_url: "http://192.168.200.216:9009/v1"
  temperature: 0.1

database:
  host: "192.168.200.216"
  port: 13306
  user: "testuser"
  password: "testpass"
  database: "testdb"

agent:
  max_steps: 15
```

## 7. 提示词模板示例

```jinja2
{# prompts/templates/analysis/schema_extraction.j2 #}
## 任务
提取并分析数据库 {{ database_name }} 的结构信息。

## 要求
1. 识别所有表及其用途
2. 分析表之间的关系
3. 标注关键字段
4. 评估数据规模

## 输出格式
请以结构化的方式输出分析结果，包括：
- 表的业务含义
- 主要字段说明
- 表间关系描述
- 数据量级评估

{% if examples %}
## 参考示例
{% for example in examples %}
输入: {{ example.input }}
输出: {{ example.output }}
{% endfor %}
{% endif %}
```

这个新设计：
1. **保持了 TRAEAgent 的智能体模式**，而不是工作流
2. **使用结构化的轨迹记录**，便于分析和反思
3. **采用 Jinja2 模板管理**提示词（参考 nl2sql_pipeline）
4. **工具设计更加详细**，每个工具都是独立的 LangChain Tool
5. **移除了 LangGraph**，使用传统的智能体执行模式