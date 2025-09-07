# ReAct智能体系统级接口设计

基于LangGraph官方ReAct模式，结合SemanticSQL极简架构设计

## 1. 核心状态管理 (agent/state.py)

### 1.1 智能体状态定义
```python
from typing import List, Dict, Any, Optional, Sequence
from typing_extensions import TypedDict, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from tools.base_tool import SemanticTriple

class AgentState(TypedDict):
    """SemanticSQL智能体状态 - 基于LangGraph官方模式"""
    
    # LangGraph标准消息流
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # SemanticSQL特有状态
    memory: List[SemanticTriple]           # 语义三元组记忆
    current_input: str                     # 当前用户输入
    database_params: Optional[Dict[str, Any]]  # 数据库连接参数
    
    # 执行控制
    iteration_count: int                   # 当前迭代次数
    max_iterations: int                    # 最大迭代次数
    
class ExecutionResult(TypedDict):
    """执行结果包装"""
    success: bool
    message: str
    memory_count: int
    final_sql: Optional[str]
    error: Optional[str]
```

## 2. 核心决策函数 (agent/core_functions.py)

### 2.1 should_continue 决策函数
```python
from typing import Literal
from langchain_core.messages import ToolMessage

def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    """
    ReAct循环决策函数 - 基于LangGraph官方模式
    
    检查最后一条消息是否包含工具调用
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    # 检查是否达到最大迭代次数
    if state.get("iteration_count", 0) >= state.get("max_iterations", 10):
        return "__end__"
    
    # 检查LLM是否选择了工具调用
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    
    return "__end__"

def call_model(state: AgentState) -> Dict[str, Any]:
    """
    LLM调用节点 - 系统级实现
    
    基于当前记忆状态和消息历史，调用LLM选择下一步动作
    """
    from langchain_core.messages import SystemMessage, HumanMessage
    from tools.base_tool import BaseSemanticSQLTool
    
    # 格式化当前记忆状态
    memory_text = BaseSemanticSQLTool().format_memory_text(state["memory"])
    
    # 构建系统提示词
    system_prompt = f"""你是专业的 SemanticSQL 智能体，专门分析数据库并生成SQL查询。

当前分析状态 (已有{len(state["memory"])}条记忆):
{memory_text}

你的任务流程：
1. 如果记忆为空，首先使用 schema_extraction 分析数据库结构
2. 基于数据库结构，使用 domain_analysis 分析业务领域
3. 使用 field_analysis 分析字段语义含义  
4. 使用 table_analysis 分析表的业务含义
5. 使用 er_analysis 分析表间关系
6. 根据用户问题使用 question_generation 生成相关问题
7. 使用 sql_generation 生成SQL语句
8. 使用 sql_validation 验证SQL正确性
9. 如需要，使用 sequential_thinking 进行深度分析

用户输入: {state["current_input"]}

请根据当前记忆状态选择最合适的下一步工具。每次只选择一个工具执行。"""

    # 更新迭代计数
    new_iteration_count = state.get("iteration_count", 0) + 1
    
    # 构建消息（保持消息历史）
    messages = state["messages"] + [SystemMessage(content=system_prompt)]
    
    # 调用LLM（需要从外部传入，这里显示接口）
    # llm_with_tools = get_llm_client().bind_tools(get_available_tools())
    # response = llm_with_tools.invoke(messages)
    
    return {
        **state,
        "messages": messages,  # 消息会通过add_messages自动添加
        "iteration_count": new_iteration_count
    }
```

## 3. SemanticSQL专用智能体 (agent/sql_agent.py)

### 3.1 SemanticSQL智能体实现
```python
from typing import Dict, Any, Optional, List
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

class SemanticSQLAgent:
    """SemanticSQL智能体 - 基于LangGraph系统级实现"""
    
    def __init__(self, 
                 llm_config: Dict[str, Any],
                 tools: List,
                 max_iterations: int = 10,
                 neo4j_config: Optional[Dict[str, Any]] = None):
        """
        初始化SemanticSQL智能体
        
        Args:
            llm_config: LLM配置 {"model": "gpt-4", "api_key": "xxx"}
            tools: 工具列表 [schema_extraction, domain_analysis, ...]
            max_iterations: 最大迭代次数
            neo4j_config: Neo4j配置（可选）
        """
        self.llm_config = llm_config
        self.tools = tools
        self.max_iterations = max_iterations
        self.neo4j_config = neo4j_config
        
        # 创建LLM客户端
        self.llm = ChatOpenAI(**llm_config)
        self.llm_with_tools = self.llm.bind_tools(tools)
        
        # 创建工作流
        self.workflow = self._create_workflow()
    
    def _create_workflow(self) -> StateGraph:
        """创建LangGraph工作流"""
        workflow = StateGraph(AgentState)
        
        # 添加节点
        workflow.add_node("agent", self._call_model)
        workflow.add_node("tools", ToolNode(self.tools))
        
        # 设置入口点
        workflow.set_entry_point("agent")
        
        # 添加条件边
        workflow.add_conditional_edges(
            "agent",
            self._should_continue,
            {
                "tools": "tools",
                "__end__": END,
            },
        )
        
        # 工具执行后返回agent
        workflow.add_edge("tools", "agent")
        
        return workflow.compile()
    
    def _should_continue(self, state: AgentState) -> str:
        """决策函数 - 检查是否继续执行工具"""
        messages = state["messages"]
        last_message = messages[-1]
        
        # 检查迭代次数限制
        if state.get("iteration_count", 0) >= state.get("max_iterations", self.max_iterations):
            return "__end__"
        
        # 检查是否有工具调用
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        
        return "__end__"
    
    def _call_model(self, state: AgentState) -> Dict[str, Any]:
        """LLM调用节点"""
        from tools.base_tool import BaseSemanticSQLTool
        
        # 格式化记忆状态
        memory_text = BaseSemanticSQLTool().format_memory_text(state["memory"])
        
        # 构建系统提示
        system_prompt = f"""你是专业的 SemanticSQL 智能体。

当前分析进度 (已存储{len(state["memory"])}条知识):
{memory_text if memory_text != "记忆为空，需要开始分析" else "尚未开始分析，请从数据库结构分析开始"}

分析流程：
1. schema_extraction - 提取数据库结构（必须首先执行）
2. domain_analysis - 分析业务领域
3. field_analysis - 分析字段语义  
4. table_analysis - 分析表业务含义
5. er_analysis - 分析表关系
6. question_generation - 生成业务问题
7. sql_generation - 生成SQL语句
8. sql_validation - 验证SQL

用户需求: {state["current_input"]}

请选择下一步最合适的工具。每次只选择一个工具。"""

        # 构建消息
        messages = state["messages"] + [HumanMessage(content=system_prompt)]
        
        # 调用LLM
        response = self.llm_with_tools.invoke(messages)
        
        # 更新状态
        return {
            **state,
            "messages": [response],  # add_messages会自动处理
            "iteration_count": state.get("iteration_count", 0) + 1
        }
    
    def analyze_database(self, 
                        database_params: Dict[str, Any],
                        user_question: str) -> ExecutionResult:
        """
        完整数据库分析流程
        
        Args:
            database_params: 数据库连接参数
            user_question: 用户问题
            
        Returns:
            ExecutionResult: 执行结果
        """
        try:
            # 创建初始状态
            initial_state: AgentState = {
                "messages": [HumanMessage(content=user_question)],
                "memory": [],
                "current_input": user_question,
                "database_params": database_params,
                "iteration_count": 0,
                "max_iterations": self.max_iterations
            }
            
            # 执行工作流
            final_state = self.workflow.invoke(initial_state)
            
            # 查找最终生成的SQL
            final_sql = None
            for triple in final_state["memory"]:
                if triple.predicate == "对应SQL" or triple.predicate == "生成SQL":
                    final_sql = triple.object
                    break
            
            return ExecutionResult(
                success=True,
                message=f"分析完成，共生成{len(final_state['memory'])}条知识",
                memory_count=len(final_state["memory"]),
                final_sql=final_sql,
                error=None
            )
            
        except Exception as e:
            return ExecutionResult(
                success=False,
                message="执行失败",
                memory_count=0,
                final_sql=None,
                error=str(e)
            )
    
    def stream_analysis(self, 
                       database_params: Dict[str, Any],
                       user_question: str):
        """
        流式执行分析过程，实时获取中间结果
        
        Args:
            database_params: 数据库连接参数
            user_question: 用户问题
            
        Yields:
            每个步骤的执行状态
        """
        initial_state: AgentState = {
            "messages": [HumanMessage(content=user_question)],
            "memory": [],
            "current_input": user_question,
            "database_params": database_params,
            "iteration_count": 0,
            "max_iterations": self.max_iterations
        }
        
        for step in self.workflow.stream(initial_state):
            yield step
```

## 4. 智能体工厂和使用示例 (agent/factory.py)

### 4.1 智能体工厂函数
```python
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from tools.base_tool import BaseSemanticSQLTool

def create_semantic_sql_agent(
    llm_config: Dict[str, Any],
    database_tools: Optional[List] = None,
    max_iterations: int = 10,
    neo4j_config: Optional[Dict[str, Any]] = None
) -> SemanticSQLAgent:
    """
    创建SemanticSQL智能体工厂函数
    
    Args:
        llm_config: LLM配置 {"model": "gpt-4", "api_key": "xxx"}
        database_tools: 数据库工具列表（可选，使用默认）
        max_iterations: 最大迭代次数
        neo4j_config: Neo4j配置（可选）
        
    Returns:
        配置好的SemanticSQL智能体实例
    """
    
    # 如果没有提供工具，创建默认工具集
    if database_tools is None:
        database_tools = create_default_tools(neo4j_config)
    
    # 创建智能体实例
    agent = SemanticSQLAgent(
        llm_config=llm_config,
        tools=database_tools,
        max_iterations=max_iterations,
        neo4j_config=neo4j_config
    )
    
    return agent

def create_default_tools(neo4j_config: Optional[Dict[str, Any]] = None) -> List:
    """创建默认工具集合"""
    
    # 根据需要创建Neo4j实例
    neo4j_graph = None
    if neo4j_config:
        from langchain_neo4j import Neo4jGraph
        neo4j_graph = Neo4jGraph(**neo4j_config)
    
    # 创建工具实例（简化示例）
    @tool
    def schema_extraction(state: AgentState) -> str:
        """数据库结构提取工具"""
        tool_instance = BaseSemanticSQLTool(neo4j_graph)
        tool_instance.name = "schema_extraction"
        
        # 从state中获取数据库参数并分析
        db_params = state.get("database_params", {})
        
        # 这里是简化的实现，实际应该连接数据库分析
        tool_instance.add_knowledge_triple(
            state,
            subject="数据库",
            predicate="分析状态",
            object="结构提取完成",
            subject_type="Database",
            object_type="Status"
        )
        
        return tool_instance.create_result(
            summary="数据库结构提取完成",
            triples=tool_instance.query_by_source(state["memory"], "schema_extraction")
        )
    
    @tool
    def sql_generation(state: AgentState) -> str:
        """SQL生成工具"""
        tool_instance = BaseSemanticSQLTool(neo4j_graph)
        tool_instance.name = "sql_generation"
        
        # 基于记忆生成SQL
        tool_instance.add_knowledge_triple(
            state,
            subject=state["current_input"],
            predicate="对应SQL",
            object="SELECT * FROM users WHERE active = 1",
            subject_type="Question",
            object_type="SQL"
        )
        
        return tool_instance.create_result(
            summary="SQL语句生成完成",
            triples=tool_instance.query_by_source(state["memory"], "sql_generation")
        )
    
    # 可以继续添加更多工具...
    tools = [
        schema_extraction,
        sql_generation,
        # domain_analysis,
        # field_analysis,
        # table_analysis,
        # er_analysis,
        # question_generation,
        # sql_validation,
        # sequential_thinking
    ]
    
    return tools
```

## 5. 使用示例

### 5.1 基本使用示例
```python
# 创建智能体
agent = create_semantic_sql_agent(
    llm_config={
        "model": "gpt-4",
        "api_key": "your-openai-api-key",
        "temperature": 0.7
    },
    max_iterations=10
)

# 数据库连接参数
database_params = {
    "host": "localhost",
    "port": 3306,
    "database": "ecommerce", 
    "username": "root",
    "password": "password"
}

# 执行分析
result = agent.analyze_database(
    database_params=database_params,
    user_question="查询最近30天活跃用户的订单统计"
)

# 查看结果
if result.success:
    print(f"✅ 分析成功！生成了 {result.memory_count} 条知识")
    if result.final_sql:
        print(f"🔍 最终SQL: {result.final_sql}")
else:
    print(f"❌ 分析失败: {result.error}")
```

### 5.2 流式执行示例
```python
# 流式执行，实时查看每个步骤
print("🚀 开始分析数据库...")

for step in agent.stream_analysis(database_params, "查询用户订单信息"):
    if "agent" in step:
        print(f"🤖 智能体思考中...")
    elif "tools" in step:
        tool_name = step["tools"]["messages"][-1].name if "messages" in step["tools"] else "unknown"
        print(f"🔧 执行工具: {tool_name}")

print("✅ 分析完成！")
```

### 5.3 带Neo4j持久化的使用
```python
# 创建带Neo4j持久化的智能体
neo4j_config = {
    "url": "bolt://localhost:7687",
    "username": "neo4j",
    "password": "neo4j_password"
}

agent_with_neo4j = create_semantic_sql_agent(
    llm_config={"model": "gpt-4", "api_key": "your-key"},
    neo4j_config=neo4j_config
)

# 执行分析（知识会自动同步到Neo4j）
result = agent_with_neo4j.analyze_database(
    database_params=database_params,
    user_question="分析用户行为模式"
)

print(f"知识已同步到Neo4j图数据库: {result.memory_count}个三元组")
```

---

**极简设计特点**：
1. **纯ReAct模式**：LLM根据记忆状态动态选择工具，无预定义流水线
2. **状态驱动**：所有决策基于AgentState，特别是memory内容
3. **Jinja2模板**：灵活的系统提示词管理
4. **should_continue核心**：严格按照原设计的决策函数逻辑
5. **工具无参数**：工具从state获取信息，符合极简理念