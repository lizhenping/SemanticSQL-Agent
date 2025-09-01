# LangChain 集成指南

本指南详细说明 SemanticSQL Agent 如何集成和使用 LangChain 框架。

## 核心组件映射

### 1. Agent 系统

#### 使用 AgentExecutor

```python
from langchain.agents import create_react_agent, AgentExecutor
from langchain.chat_models import ChatOpenAI

class SQLAgent:
    def __init__(self, config):
        # 初始化 LLM
        self.llm = ChatOpenAI(
            openai_api_base=config.llm_base_url,
            model_name=config.llm_model,
            temperature=0.7
        )
        
        # 创建工具
        self.tools = self._create_tools()
        
        # 创建 Agent
        prompt = self._get_prompt_template()
        agent = create_react_agent(self.llm, self.tools, prompt)
        
        # 创建执行器
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,
            max_iterations=20,
            early_stopping_method="generate"
        )
```

### 2. 工具系统

#### 创建 LangChain 工具

```python
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

class SchemaExtractionTool(BaseTool):
    """数据库结构提取工具"""
    name = "extract_schema"
    description = "Extract database schema including tables, columns, and constraints"
    
    # 定义输入参数
    class InputSchema(BaseModel):
        database_name: str = Field(description="Database name to analyze")
    
    args_schema = InputSchema
    
    def _run(self, database_name: str) -> Dict[str, Any]:
        """同步执行"""
        # 连接数据库
        db_manager = DatabaseManager(self.db_config)
        
        # 提取结构
        tables = db_manager.get_tables()
        columns = db_manager.get_columns()
        constraints = db_manager.get_constraints()
        
        return {
            "database": database_name,
            "tables": tables,
            "columns": columns,
            "constraints": constraints
        }
    
    async def _arun(self, database_name: str) -> Dict[str, Any]:
        """异步执行（可选）"""
        raise NotImplementedError("Async not implemented")
```

### 3. 记忆管理

#### 自定义 Memory 类

```python
from langchain.memory import BaseMemory
from typing import List, Dict, Any

class DatabaseAnalysisMemory(BaseMemory):
    """专门管理数据库分析结果的记忆"""
    
    memory_key: str = "db_analysis"
    
    def __init__(self):
        super().__init__()
        self.analysis_results = {
            "schema_info": None,
            "domain_analysis": None,
            "field_classification": None,
            "column_meanings": None,
            "table_meanings": None,
            "er_analysis": None
        }
    
    @property
    def memory_variables(self) -> List[str]:
        """定义记忆变量"""
        return [self.memory_key]
    
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """加载记忆内容"""
        # 根据当前任务返回相关的分析结果
        return {
            self.memory_key: {
                "schema": self.analysis_results.get("schema_info"),
                "domain": self.analysis_results.get("domain_analysis"),
                "has_analysis": any(self.analysis_results.values())
            }
        }
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        """保存上下文"""
        # 识别工具输出并保存
        if "tool" in inputs and inputs["tool"] == "extract_schema":
            self.analysis_results["schema_info"] = outputs.get("data")
        elif "tool" in inputs and inputs["tool"] == "domain_analysis":
            self.analysis_results["domain_analysis"] = outputs.get("data")
        # ... 其他工具
    
    def clear(self) -> None:
        """清空记忆"""
        for key in self.analysis_results:
            self.analysis_results[key] = None
```

### 4. 提示词管理

#### 使用 PromptTemplate

```python
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate
from langchain.prompts import HumanMessagePromptTemplate, MessagesPlaceholder

# 系统提示词
system_prompt = SystemMessagePromptTemplate.from_template("""
You are a SQL expert agent specialized in generating high-quality NL2SQL training data.

Your workflow:
1. Database Analysis Phase (execute once, save to memory):
   - extract_schema: Get database structure
   - domain_analysis: Identify business domain
   - field_classification: Classify field semantics
   - column_meaning: Analyze column business meanings
   - table_meaning: Analyze table responsibilities
   - er_analysis: Analyze entity relationships

2. Data Generation Phase (iterate for each scenario):
   - scenario_generation: Generate scenarios (batch)
   - For each scenario:
     - operation_selection: Select SQL operations
     - question_generation: Generate natural language question
     - sql_generation: Generate SQL query
     - sql_validation: Validate SQL syntax
     - sql_execution: Execute and test SQL
     - sql_reflection: Reflect on quality

3. Reflection and Correction:
   - If quality issues found, use sequential_thinking to analyze
   - Re-execute only the problematic step
   - Continue with the flow

Current database: {database_name}
Analysis memory: {db_analysis}

Available tools: {tools}
""")

# 创建完整提示词
prompt = ChatPromptTemplate.from_messages([
    system_prompt,
    MessagesPlaceholder(variable_name="chat_history"),
    HumanMessagePromptTemplate.from_template("{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad")
])
```

### 5. 回调系统

#### 创建自定义回调

```python
from langchain.callbacks import BaseCallbackHandler
from datetime import datetime
import json

class TrajectoryCallback(BaseCallbackHandler):
    """记录执行轨迹的回调"""
    
    def __init__(self, trajectory_file: str = "trajectory.jsonl"):
        self.trajectory_file = trajectory_file
        self.current_step = {}
    
    def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs) -> None:
        """Chain 开始时"""
        self.current_step = {
            "type": "chain_start",
            "timestamp": datetime.now().isoformat(),
            "name": serialized.get("name", "unknown"),
            "inputs": inputs
        }
    
    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs) -> None:
        """工具开始时"""
        self.current_step = {
            "type": "tool_start",
            "timestamp": datetime.now().isoformat(),
            "tool": serialized.get("name"),
            "input": input_str
        }
    
    def on_tool_end(self, output: str, **kwargs) -> None:
        """工具结束时"""
        self.current_step["output"] = output
        self.current_step["end_time"] = datetime.now().isoformat()
        self._save_step()
    
    def on_tool_error(self, error: Union[Exception, KeyboardInterrupt], **kwargs) -> None:
        """工具错误时"""
        self.current_step["error"] = str(error)
        self.current_step["end_time"] = datetime.now().isoformat()
        self._save_step()
    
    def _save_step(self):
        """保存步骤到文件"""
        with open(self.trajectory_file, "a") as f:
            f.write(json.dumps(self.current_step) + "\n")
```

### 6. LLM 配置

#### 配置 ChatOpenAI

```python
from langchain.chat_models import ChatOpenAI
from langchain.cache import InMemoryCache
import langchain

# 启用缓存
langchain.llm_cache = InMemoryCache()

# 创建 LLM 实例
llm = ChatOpenAI(
    # Qwen 配置
    openai_api_base="http://localhost:9991/v1",
    openai_api_key="not-needed",  # Qwen 不需要 key
    model_name="Qwen",
    
    # 生成参数
    temperature=0.7,
    max_tokens=2000,
    top_p=0.95,
    
    # 超时和重试
    request_timeout=30,
    max_retries=3,
    
    # 流式输出（可选）
    streaming=False
)
```

## 高级用法

### 1. Chain 组合

```python
from langchain.chains import LLMChain, SequentialChain

# 创建多个 Chain
analysis_chain = LLMChain(
    llm=llm,
    prompt=analysis_prompt,
    output_key="analysis"
)

generation_chain = LLMChain(
    llm=llm,
    prompt=generation_prompt,
    output_key="sql"
)

# 组合成顺序链
overall_chain = SequentialChain(
    chains=[analysis_chain, generation_chain],
    input_variables=["question", "schema"],
    output_variables=["analysis", "sql"]
)

# 执行
result = overall_chain({"question": "查询订单", "schema": schema_info})
```

### 2. 向量存储集成

```python
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.memory import VectorStoreRetrieverMemory

# 创建向量存储
embeddings = OpenAIEmbeddings(openai_api_base=config.llm_base_url)
vectorstore = Chroma(
    collection_name="schema_info",
    embedding_function=embeddings
)

# 创建向量记忆
memory = VectorStoreRetrieverMemory(
    retriever=vectorstore.as_retriever(k=5),
    memory_key="relevant_schema"
)
```

### 3. 输出解析

```python
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel

class SQLOutput(BaseModel):
    sql: str
    confidence: float
    tables_used: List[str]

# 创建解析器
parser = PydanticOutputParser(pydantic_object=SQLOutput)

# 在提示词中包含格式说明
prompt = PromptTemplate(
    template="Generate SQL for: {question}\n{format_instructions}",
    input_variables=["question"],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)

# 解析输出
chain = LLMChain(llm=llm, prompt=prompt)
output = chain.run(question="查询订单")
parsed = parser.parse(output)
```

## 调试和监控

### 1. 启用详细日志

```python
import langchain
langchain.debug = True  # 启用调试模式
langchain.verbose = True  # 详细输出

# 或者使用环境变量
# export LANGCHAIN_DEBUG=true
```

### 2. 使用 LangSmith

```python
import os
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "your-api-key"
os.environ["LANGCHAIN_PROJECT"] = "semanticsql-agent"
```

### 3. 自定义度量

```python
from langchain.callbacks import get_openai_callback

# 监控 token 使用
with get_openai_callback() as cb:
    result = agent.run("生成 SQL")
    print(f"Total Tokens: {cb.total_tokens}")
    print(f"Total Cost: ${cb.total_cost}")
```

## 最佳实践

1. **工具命名**：使用清晰、描述性的工具名称
2. **错误处理**：在工具的 `_run` 方法中添加 try-catch
3. **输入验证**：使用 Pydantic 模型验证工具输入
4. **记忆管理**：定期清理不需要的记忆内容
5. **提示词优化**：使用 Few-shot 示例提高质量
6. **异步支持**：对于 I/O 密集型工具实现 `_arun`
7. **缓存策略**：合理使用 LLM 缓存减少调用

## 常见问题

### Q: 如何处理工具执行超时？

```python
from langchain.tools import Tool
import signal

class TimeoutTool(BaseTool):
    def _run(self, input: str) -> str:
        def timeout_handler(signum, frame):
            raise TimeoutError("Tool execution timeout")
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(30)  # 30秒超时
        try:
            # 执行工具逻辑
            result = self._execute(input)
        finally:
            signal.alarm(0)
        return result
```

### Q: 如何限制 Agent 迭代次数？

```python
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    max_iterations=10,  # 最大迭代次数
    max_execution_time=60,  # 最大执行时间（秒）
    early_stopping_method="force"  # 强制停止
)
```

### Q: 如何自定义工具选择策略？

```python
from langchain.agents import Tool

# 为工具设置优先级
high_priority_tool = Tool(
    name="high_priority",
    func=lambda x: x,
    description="High priority tool - use this first for analysis tasks"
)

# 在提示词中指导工具选择顺序
prompt = """
When analyzing database, ALWAYS follow this order:
1. First use 'extract_schema'
2. Then use 'domain_analysis'
3. Finally use other tools as needed
"""
```

---

更多 LangChain 相关信息，请参考 [LangChain 官方文档](https://docs.langchain.com/)。