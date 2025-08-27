# SemanticSQL-Agent 架构设计文档（基于 LangChain ReAct Agent）

## 1. 项目概述

SemanticSQL-Agent 是一个基于 LangChain ReAct Agent 的自然语言到SQL转换系统，使用 LangChain 的预构建智能体简化实现，同时保持结构化的输出和完整的执行追踪。

### 1.1 核心特性
- 使用 LangChain 的 create_react_agent
- 结构化的工具设计和输出
- SQL 执行后的验证和反思
- Jinja2 提示词模板管理
- 完整的轨迹记录

### 1.2 技术栈
- **智能体框架**: LangChain ReAct Agent
- **工具系统**: LangChain Tools
- **提示词**: Jinja2 模板
- **数据验证**: Pydantic
- **数据库**: MySQL

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
│   ├── schemas.py               # 输入输出模式定义
│   └── database.py              # 数据库模型
│
├── tools/
│   ├── __init__.py
│   ├── base.py                  # 工具基类
│   ├── schema_tools.py          # Schema 相关工具
│   ├── analysis_tools.py        # 分析工具集
│   ├── generation_tools.py      # 生成工具集
│   └── validation_tools.py      # 验证工具集
│
├── prompts/
│   ├── __init__.py
│   ├── templates/               # Jinja2 模板
│   │   ├── tools/              # 工具描述模板
│   │   └── system/             # 系统提示词
│   └── manager.py               # 提示词管理器
│
├── agent/
│   ├── __init__.py
│   ├── nl2sql_agent.py          # 基于 create_react_agent 的智能体
│   ├── callbacks.py             # 回调处理器
│   └── memory.py                # 记忆管理
│
├── utils/
│   ├── __init__.py
│   ├── database.py              # 数据库连接
│   ├── trajectory.py            # 轨迹记录
│   ├── parser.py                # 输出解析
│   └── validator.py             # SQL 验证器
│
└── cli.py                       # 命令行接口
```

## 3. 核心组件设计

### 3.1 基于 LangChain ReAct Agent 的智能体

```python
# agent/nl2sql_agent.py
from langchain.agents import create_react_agent, AgentExecutor
from langchain.prompts import PromptTemplate
from langchain_core.callbacks import CallbackManagerForChainRun
from typing import List, Dict, Any, Optional
from models.schemas import QueryRequest, SQLResult

class NL2SQLAgent:
    """基于 LangChain ReAct Agent 的 NL2SQL 智能体"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.llm = self._create_llm()
        self.tools = self._create_tools()
        self.memory = self._create_memory()
        
        # 创建 ReAct Agent
        self.agent = self._create_agent()
        
        # 创建执行器
        self.executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,
            max_iterations=config.get("max_iterations", 15),
            handle_parsing_errors=True,
            callbacks=[TrajectoryCallback(), ValidationCallback()]
        )
    
    def _create_llm(self):
        """创建 LLM 实例"""
        from langchain_openai import ChatOpenAI
        
        return ChatOpenAI(
            model=self.config["model_name"],
            openai_api_key=self.config["api_key"],
            openai_api_base=self.config["base_url"],
            temperature=self.config.get("temperature", 0.1)
        )
    
    def _create_tools(self) -> List:
        """创建工具集"""
        from tools import (
            SchemaExtractionTool,
            DomainAnalysisTool,
            FieldClassificationTool,
            SQLGenerationTool,
            SQLValidationTool,
            SQLExecutionTool
        )
        
        # 数据库连接
        db_connector = DatabaseConnector(self.config["database"])
        
        # 共享上下文
        shared_context = {}
        
        tools = [
            SchemaExtractionTool(db_connector=db_connector, shared_context=shared_context),
            DomainAnalysisTool(shared_context=shared_context),
            FieldClassificationTool(db_connector=db_connector, shared_context=shared_context),
            SQLGenerationTool(shared_context=shared_context),
            SQLValidationTool(db_connector=db_connector, shared_context=shared_context),
            SQLExecutionTool(db_connector=db_connector, shared_context=shared_context)
        ]
        
        return tools
    
    def _create_memory(self):
        """创建记忆系统"""
        from langchain.memory import ConversationSummaryBufferMemory
        
        return ConversationSummaryBufferMemory(
            llm=self.llm,
            max_token_limit=2000,
            memory_key="chat_history"
        )
    
    def _create_agent(self):
        """创建 ReAct Agent"""
        # 获取系统提示词
        from prompts.manager import PromptManager
        prompt_manager = PromptManager()
        
        # 构建 ReAct 提示词
        react_prompt = PromptTemplate.from_template(
            prompt_manager.get_system_prompt("nl2sql_react")
        )
        
        # 创建 agent
        return create_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=react_prompt
        )
    
    def generate_sql(self, query: str) -> SQLResult:
        """生成 SQL"""
        try:
            # 执行智能体
            result = self.executor.invoke({
                "input": query,
                "chat_history": self.memory.chat_memory.messages
            })
            
            # 从结果中提取 SQL
            sql_result = self._extract_sql_result(result)
            
            # 执行后验证（反思机制）
            if sql_result.sql:
                validation_result = self._post_generation_validation(
                    query, sql_result.sql
                )
                sql_result.validation_status = validation_result
            
            return sql_result
            
        except Exception as e:
            return SQLResult(
                sql="",
                error=str(e),
                success=False
            )
    
    def _post_generation_validation(self, query: str, sql: str) -> Dict[str, Any]:
        """SQL 生成后的验证和反思"""
        validation = {
            "syntax_valid": True,
            "semantically_correct": True,
            "performance_acceptable": True,
            "suggestions": []
        }
        
        # 1. 语法验证
        syntax_check = self.tools[4].run({"sql": sql})  # SQLValidationTool
        if not syntax_check["valid"]:
            validation["syntax_valid"] = False
            validation["suggestions"].append("SQL 语法错误需要修正")
        
        # 2. 语义验证 - 检查是否真正回答了用户问题
        semantic_check = self._check_semantic_correctness(query, sql)
        if not semantic_check["correct"]:
            validation["semantically_correct"] = False
            validation["suggestions"].extend(semantic_check["issues"])
        
        # 3. 性能检查
        perf_check = self._check_performance(sql)
        if not perf_check["acceptable"]:
            validation["performance_acceptable"] = False
            validation["suggestions"].extend(perf_check["suggestions"])
        
        return validation
```

### 3.2 工具设计（支持验证和反思）

```python
# tools/generation_tools.py
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

class SQLGenerationTool(BaseTool):
    """SQL 生成工具"""
    
    name = "generate_sql"
    description = "基于分析结果生成 SQL 语句，会自动进行初步验证"
    
    class InputSchema(BaseModel):
        query: str = Field(description="用户的自然语言查询")
        context: Optional[Dict[str, Any]] = Field(description="分析上下文")
    
    args_schema = InputSchema
    shared_context: Dict[str, Any] = Field(default_factory=dict)
    
    def _run(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """生成 SQL"""
        # 获取上下文
        full_context = {
            **self.shared_context,
            **(context or {})
        }
        
        # 生成 SQL
        sql = self._generate_sql(query, full_context)
        
        # 初步验证
        validation = self._validate_generated_sql(sql, full_context)
        
        # 如果有问题，尝试修正
        if not validation["valid"]:
            sql = self._fix_sql_issues(sql, validation["issues"])
        
        # 更新共享上下文
        self.shared_context["generated_sql"] = sql
        self.shared_context["sql_metadata"] = {
            "tables": self._extract_tables(sql),
            "operations": self._extract_operations(sql)
        }
        
        return f"生成的 SQL:\n```sql\n{sql}\n```\n\n说明: {self._explain_sql(sql)}"

class SQLValidationTool(BaseTool):
    """SQL 验证工具"""
    
    name = "validate_sql"
    description = "验证 SQL 语法和逻辑的正确性"
    
    class InputSchema(BaseModel):
        sql: str = Field(description="要验证的 SQL")
        check_execution: bool = Field(default=False, description="是否试执行")
    
    args_schema = InputSchema
    db_connector: Any = Field(exclude=True)
    
    def _run(self, sql: str, check_execution: bool = False) -> str:
        """验证 SQL"""
        results = {
            "syntax": self._check_syntax(sql),
            "logic": self._check_logic(sql),
            "security": self._check_security(sql)
        }
        
        if check_execution:
            results["execution"] = self._try_execute(sql)
        
        # 生成报告
        if all(r["valid"] for r in results.values()):
            return "SQL 验证通过，可以安全执行"
        else:
            issues = []
            for check, result in results.items():
                if not result.get("valid", True):
                    issues.extend(result.get("issues", []))
            
            return f"SQL 存在以下问题:\n" + "\n".join(f"- {issue}" for issue in issues)

class SQLExecutionTool(BaseTool):
    """SQL 执行工具（用于测试）"""
    
    name = "execute_sql_test"
    description = "在测试模式下执行 SQL，返回前几行结果用于验证"
    
    class InputSchema(BaseModel):
        sql: str = Field(description="要执行的 SQL")
        limit: int = Field(default=5, description="返回行数限制")
    
    args_schema = InputSchema
    db_connector: Any = Field(exclude=True)
    
    def _run(self, sql: str, limit: int = 5) -> str:
        """测试执行 SQL"""
        try:
            # 添加 LIMIT 子句
            test_sql = self._add_limit(sql, limit)
            
            # 执行查询
            results = self.db_connector.execute_query(test_sql)
            
            # 格式化结果
            if results:
                return self._format_results(results, sql)
            else:
                return "查询执行成功但没有返回结果"
                
        except Exception as e:
            return f"执行失败: {str(e)}"
```

### 3.3 回调处理器（记录执行过程）

```python
# agent/callbacks.py
from langchain.callbacks.base import BaseCallbackHandler
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

class TrajectoryCallback(BaseCallbackHandler):
    """轨迹记录回调"""
    
    def __init__(self):
        self.trajectory = {
            "start_time": datetime.now().isoformat(),
            "steps": [],
            "tool_calls": [],
            "thoughts": []
        }
    
    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs):
        """LLM 开始思考"""
        self.trajectory["thoughts"].append({
            "timestamp": datetime.now().isoformat(),
            "prompt_preview": prompts[0][:200] if prompts else ""
        })
    
    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs):
        """工具开始执行"""
        self.trajectory["tool_calls"].append({
            "timestamp": datetime.now().isoformat(),
            "tool": serialized.get("name", "unknown"),
            "input": input_str,
            "status": "started"
        })
    
    def on_tool_end(self, output: str, **kwargs):
        """工具执行结束"""
        if self.trajectory["tool_calls"]:
            self.trajectory["tool_calls"][-1].update({
                "output": output[:500],  # 截断长输出
                "status": "completed",
                "end_time": datetime.now().isoformat()
            })
    
    def on_agent_action(self, action: Any, **kwargs):
        """智能体执行动作"""
        self.trajectory["steps"].append({
            "timestamp": datetime.now().isoformat(),
            "action": str(action.tool),
            "input": str(action.tool_input),
            "log": action.log
        })
    
    def save_trajectory(self, filepath: str):
        """保存轨迹"""
        self.trajectory["end_time"] = datetime.now().isoformat()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.trajectory, f, ensure_ascii=False, indent=2)

class ValidationCallback(BaseCallbackHandler):
    """验证回调 - 在 SQL 生成后自动验证"""
    
    def on_tool_end(self, output: str, **kwargs):
        """工具执行结束时检查"""
        # 如果是 SQL 生成工具的输出
        if "生成的 SQL:" in output and "```sql" in output:
            # 提取 SQL
            import re
            sql_match = re.search(r'```sql\n(.*?)\n```', output, re.DOTALL)
            if sql_match:
                sql = sql_match.group(1)
                
                # 触发验证
                print(f"\n[验证] 正在验证生成的 SQL...")
                # 这里可以调用验证工具或发送验证信号
```

### 3.4 提示词模板（ReAct 格式）

```jinja2
{# prompts/templates/system/nl2sql_react.j2 #}
你是一个专业的数据库专家，使用 ReAct 模式将自然语言转换为 SQL。

## 可用工具

你可以使用以下工具：
{% for tool in tools %}
- {{ tool.name }}: {{ tool.description }}
{% endfor %}

## 工作流程

1. 分析数据库结构 (extract_database_schema)
2. 理解业务领域 (analyze_domain)  
3. 分类字段类型 (classify_fields)
4. 生成 SQL (generate_sql)
5. 验证 SQL (validate_sql)
6. 测试执行 (execute_sql_test) - 可选

## 重要提示

- 生成 SQL 后必须进行验证
- 如果验证失败，分析原因并重新生成
- 考虑查询性能和安全性
- 生成的 SQL 必须准确回答用户问题

## 输出格式

最终输出应包含：
1. 生成的 SQL
2. SQL 的解释
3. 使用的表和字段
4. 任何注意事项

现在，请分析并回答用户的查询。