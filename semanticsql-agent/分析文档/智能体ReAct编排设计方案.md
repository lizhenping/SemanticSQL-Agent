# SemanticSQL Agent - LangGraph ReAct架构设计

## 1. 核心理念

**设计目标**：基于LangGraph的ReAct模式，构建智能的SQL生成和分析系统

### 1.1 设计原则
- **LangGraph ReAct架构**：基于状态机的ReAct循环实现，而非预设工作流
- **智能工具编排**：LLM通过思考-行动-观察循环自主选择工具
- **状态驱动**：基于AgentState和DatabaseAnalysisMemory的双重状态管理
- **思考增强**：SequentialThinkingTool作为普通工具，由LLM智能调用

## 2. LangGraph ReAct架构

### 2.1 核心组件设计
```python
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, add_messages

class AgentState(TypedDict):
    """智能体状态定义（基于LangGraph ReAct模式）"""
    # LangGraph标准消息状态
    messages: Annotated[list[BaseMessage], add_messages]
    
    # SemanticSQL特定状态
    memory: DatabaseAnalysisMemory          # 分析记忆系统
    current_task: str                       # 当前任务描述
    tools_used: list[str]                  # 已使用的工具列表
    analysis_complete: bool                # 分析是否完成
```

### 2.2 ReAct节点设计
```python
# 基于LangGraph的ReAct节点实现
def call_model(state: AgentState):
    """模型思考和决策节点"""
    messages = state["messages"]
    
    # 增强上下文：添加记忆摘要
    memory_summary = state["memory"].get_summary()
    completion_status = state["memory"].get_typed_context().get_completion_status()
    
    # 构建增强的系统消息
    system_message = create_system_message_with_memory(
        tools=tools,
        memory_summary=memory_summary,
        completion_status=completion_status
    )
    
    # LLM推理和工具选择
    response = llm_with_tools.invoke([system_message] + messages)
    return {"messages": [response]}

def call_tools(state: AgentState):
    """工具执行节点"""
    messages = state["messages"]
    last_message = messages[-1]
    
    # 执行工具调用
    tool_responses = []
    for tool_call in last_message.tool_calls:
        tool = tools_by_name[tool_call["name"]]
        
        # 设置工具的记忆引用
        tool.set_memory(state["memory"])
        
        # 执行工具
        result = tool.invoke(tool_call["args"])
        tool_responses.append(ToolMessage(
            content=result,
            tool_call_id=tool_call["id"]
        ))
        
        # 更新工具使用记录
        state["tools_used"].append(tool_call["name"])
    
    return {"messages": tool_responses}

def should_continue(state: AgentState):
    """决策路由函数"""
    messages = state["messages"]
    last_message = messages[-1]
    
    # 如果有工具调用，继续执行工具
    if last_message.tool_calls:
        return "tools"
    
    # 否则结束
    return "__end__"
```

### 2.3 图构建
```python
def create_react_agent():
    """创建LangGraph ReAct智能体"""
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", call_tools)
    
    # 设置入口点
    workflow.set_entry_point("agent")
    
    # 添加条件边
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "__end__": "__end__"}
    )
    
    # 工具执行后返回智能体
    workflow.add_edge("tools", "agent")
    
    return workflow.compile()
```

## 3. 智能体实现

### 3.1 基于现有BaseAgent的LangGraph扩展
```python
from agent.base_agent import BaseAgent
from langgraph.graph import StateGraph, add_messages
from langchain_core.messages import SystemMessage, HumanMessage

class SemanticSQLReActAgent(BaseAgent):
    """基于LangGraph ReAct的SemanticSQL智能体"""
    
    def __init__(self, settings: Settings, db_config: DatabaseConfig):
        super().__init__(settings, db_config)
        
        # 创建LangGraph ReAct智能体
        self.react_app = self._create_react_graph()
        
        # 工具映射表
        self.tools_by_name = {tool.name: tool for tool in self.tools}
    
    def _create_react_graph(self):
        """创建LangGraph ReAct图"""
        workflow = StateGraph(AgentState)
        
        # 添加节点
        workflow.add_node("agent", self._call_model)
        workflow.add_node("tools", self._call_tools)
        
        # 设置入口点
        workflow.set_entry_point("agent")
        
        # 添加条件边
        workflow.add_conditional_edges(
            "agent",
            self._should_continue,
            {"tools": "tools", "__end__": "__end__"}
        )
        
        # 工具执行后返回智能体
        workflow.add_edge("tools", "agent")
        
        return workflow.compile()
    
    def _call_model(self, state: AgentState):
        """模型思考和决策节点"""
        messages = state["messages"]
        
        # 构建增强的系统消息
        system_message = self._create_enhanced_system_message(state)
        
        # 如果没有系统消息，添加一个
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [system_message] + messages
        
        # 绑定工具到LLM
        llm_with_tools = self.llm.bind_tools(list(self.tools))
        
        # LLM推理和工具选择
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}
    
    def _call_tools(self, state: AgentState):
        """工具执行节点"""
        from langchain_core.messages import ToolMessage
        
        messages = state["messages"]
        last_message = messages[-1]
        
        tool_responses = []
        for tool_call in last_message.tool_calls:
            tool = self.tools_by_name[tool_call["name"]]
            
            # 设置工具的记忆引用（每次调用前更新）
            tool.set_memory(state["memory"])
            
            # 执行工具
            try:
                result = tool.invoke(tool_call["args"])
                tool_responses.append(ToolMessage(
                    content=str(result),
                    tool_call_id=tool_call["id"]
                ))
                
                # 更新工具使用记录
                state["tools_used"].append(tool_call["name"])
                
            except Exception as e:
                tool_responses.append(ToolMessage(
                    content=f"工具执行错误: {str(e)}",
                    tool_call_id=tool_call["id"]
                ))
        
        return {"messages": tool_responses}
    
    def _should_continue(self, state: AgentState):
        """决策路由函数"""
        messages = state["messages"]
        last_message = messages[-1]
        
        # 如果有工具调用，继续执行工具
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"
        
        # 否则结束
        return "__end__"
    
    def _create_enhanced_system_message(self, state: AgentState) -> SystemMessage:
        """创建增强的系统消息"""
        memory_summary = state["memory"].get_summary()
        completion_status = state["memory"].get_typed_context().get_completion_status()
        
        # 格式化完成状态
        status_lines = []
        for stage, completed in completion_status.items():
            icon = "✅" if completed else "⏳"
            status_lines.append(f"  {icon} {stage}")
        
        system_content = f"""你是一个专业的数据库分析和SQL生成智能体。

可用工具及其功能：
{self._get_tool_descriptions()}

当前分析状态：
{chr(10).join(status_lines)}

记忆摘要：
{memory_summary}

智能决策规则：
1. 根据当前状态和任务需求智能选择工具
2. 遇到复杂问题时主动使用sequential_thinking深度分析
3. 基于记忆中的信息做出上下文感知的决策
4. 确保结果质量，必要时重复执行工具或进行反思评估

你可以自由选择任何工具的调用顺序，目标是高质量完成用户任务。"""

        return SystemMessage(content=system_content)
    
    def _get_tool_descriptions(self) -> str:
        """获取工具描述"""
        descriptions = []
        for tool in self.tools:
            descriptions.append(f"- {tool.name}: {tool.description}")
        return "\n".join(descriptions)
```

### 3.2 执行接口
```python
def run(self, task: str, **kwargs) -> Dict[str, Any]:
    """执行任务的主接口（重写BaseAgent方法）"""
    
    # 初始化状态
    initial_state = {
        "messages": [HumanMessage(content=task)],
        "memory": self.memory,
        "current_task": task,
        "tools_used": [],
        "analysis_complete": False
    }
    
    try:
        # 使用LangGraph执行ReAct循环
        final_state = self.react_app.invoke(initial_state)
        
        # 提取最终结果
        messages = final_state["messages"]
        final_message = messages[-1]
        
        return {
            "success": True,
            "result": final_message.content,
            "tools_used": final_state["tools_used"],
            "total_messages": len(messages),
            "memory_summary": self.memory.get_summary()
        }
        
    except Exception as e:
        self.logger.error(f"ReAct execution failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "tools_used": initial_state.get("tools_used", []),
            "memory_summary": self.memory.get_summary()
        }
```

### 3.3 LLM智能决策机制
```python
def create_intelligent_react_prompt() -> str:
    """创建让LLM智能决策的ReAct提示词"""
    
    return """你是一个专业的数据库分析和SQL生成智能体。你需要智能地选择工具并决定执行顺序。

智能决策规则：
1. **自主判断**：你可以根据当前情况自由选择任何工具
2. **思考增强**：当遇到复杂问题、结果不理想时，主动使用sequential_thinking
3. **上下文感知**：基于记忆中的信息做出明智的工具选择
4. **质量驱动**：优先保证结果质量，必要时重复执行工具

工具使用策略：
- schema_extraction: 首次分析数据库时必用
- domain_analysis: 理解业务域，基于schema结果
- field_analysis/column_analysis/table_analysis: 深度理解数据语义
- er_analysis: 分析表间关系
- scenario_operation_tool: 生成业务场景
- question_generation: 生成自然语言问题
- sql_generation: 核心功能，生成SQL
- sql_validation/sql_execution: 验证和执行
- sql_reflection: 质量评估
- sequential_thinking: 遇到问题时的深度思考工具

记忆感知：
当前记忆状态: {memory_summary}
完成度: {completion_status}

自主决策示例：
- 如果schema信息不完整 → 使用sequential_thinking分析原因
- 如果SQL生成失败 → 先thinking再重新生成
- 如果结果质量不高 → 主动调用reflection评估

你的目标是高质量完成任务，请智能地选择工具顺序。
"""

### 3.4 智能工具调度
```python
class IntelligentToolScheduler:
    """智能工具调度器 - 让LLM自主决策"""
    
    def __init__(self, memory: DatabaseAnalysisMemory):
        self.memory = memory
    
    def get_tool_recommendations(self) -> str:
        """基于当前状态推荐工具"""
        context = self.memory.get_typed_context()
        completion = context.get_completion_status()
        
        recommendations = []
        
        # 基于完成状态智能推荐
        if not completion["schema_info"]:
            recommendations.append("🔧 schema_extraction: 首先需要提取数据库结构")
        
        elif not completion["domain_info"]:
            recommendations.append("🏢 domain_analysis: 基于schema分析业务域")
            
        elif context.schema_info and context.schema_info.total_tables > 5:
            if not completion["er_relations"]:
                recommendations.append("🔗 er_analysis: 表较多，建议分析表间关系")
        
        if context.current_sql and not self._is_sql_validated():
            recommendations.append("✅ sql_validation: SQL需要验证")
            
        # 质量检查推荐
        if self._needs_quality_improvement():
            recommendations.append("🤔 sequential_thinking: 当前结果需要深度分析")
        
        return "\n".join(recommendations) if recommendations else "🎯 所有基础分析已完成，可以开始生成任务"
    
    def _is_sql_validated(self) -> bool:
        """检查SQL是否已验证"""
        return "sql_validation" in self.memory.memories
    
    def _needs_quality_improvement(self) -> bool:
        """判断是否需要质量改进"""
        # 基于启发式规则判断
        if self.memory.context.domain_info:
            return self.memory.context.domain_info.confidence_score < 0.7
        return False
```

## 4. ReAct执行流程

### 4.1 LLM主导的智能执行
```
用户任务输入
     ↓
LLM分析任务 (Thought)
     ↓
智能选择工具 (Action)
     ↓
工具执行并返回结果 (Observation)
     ↓
LLM评估结果质量 (Thought)
     ↓
决定：继续/思考增强/完成 (Action/Thinking)
     ↓
重复直到任务完成
```

### 4.2 典型执行序列示例
```
Thought: 用户要求分析数据库并生成SQL，我需要先了解数据库结构
Action: schema_extraction
Action Input: {"host": "localhost", "database": "sales", "username": "root", "password": "pass"}
Observation: 成功提取到5个表的结构信息...

Thought: 数据库结构已获取，现在需要理解业务领域
Action: domain_analysis  
Action Input: {}
Observation: 识别为电商领域，置信度0.85...

Thought: 置信度较高，现在可以分析字段语义
Action: field_analysis
Action Input: {}
Observation: 完成字段分类，识别出用户、订单、商品等核心实体...

Thought: 现在可以根据用户具体需求生成SQL
Action: sql_generation
Action Input: {"question": "查询近30天销售额最高的10个用户"}
Observation: 生成SQL查询语句...

Thought: SQL已生成，需要验证正确性
Action: sql_validation
Action Input: {"sql": "SELECT..."}
Observation: SQL语法正确，逻辑合理...

Thought: 任务完成，提供最终结果
Final Answer: 已成功分析数据库并生成所需SQL查询...
```

### 4.3 智能增强场景
```
# 场景1: 遇到问题时自动思考
Thought: schema_extraction返回的表信息似乎不完整，需要深入分析
Action: sequential_thinking
Action Input: {"problem_description": "数据库schema提取结果不完整，只获取到2个表但预期应该更多"}
Observation: 分析建议检查数据库连接权限和schema配置...

# 场景2: 质量不满意时主动评估  
Thought: 生成的SQL可能不够优化，让我评估一下
Action: sql_reflection  
Action Input: {"original_question": "查询用户购买行为", "reflection_depth": "deep"}
Observation: SQL质量评分0.75，建议优化JOIN条件...
```

## 5. 使用方式

### 5.1 LangGraph ReAct标准调用
```python
from config.settings import Settings
from utils.database_config import DatabaseConfig

# 1. 初始化（基于现有架构 + LangGraph扩展）
settings = Settings()
db_config = DatabaseConfig(
    host="localhost",
    database="sales_db", 
    username="root",
    password="password"
)

# 2. 创建LangGraph ReAct智能体
agent = SemanticSQLReActAgent(settings, db_config)

# 3. 执行任务（LangGraph管理ReAct循环）
result = agent.run("分析销售数据库并生成用户购买行为的SQL查询")

# 4. 查看结果
print("任务执行:", "成功" if result["success"] else "失败")
print("使用的工具:", result["tools_used"])
print("消息数量:", result["total_messages"])
print("记忆状态:", result["memory_summary"])
```

### 5.2 观察LangGraph ReAct循环
```python
# LangGraph的ReAct循环是这样的：
# 1. agent节点: LLM分析情况并选择工具
# 2. tools节点: 执行选中的工具
# 3. 回到agent节点: LLM评估结果并决定下一步
# 4. 重复直到任务完成

agent = SemanticSQLReActAgent(settings, db_config)

# 执行复杂任务
result = agent.run("全面分析电商数据库，生成用户行为分析SQL，并执行验证")

# LangGraph会自动管理状态流转，例如：
# Messages: [HumanMessage, AIMessage with tool_calls, ToolMessage, AIMessage, ...]
# State: {messages: [...], tools_used: [...], memory: DatabaseAnalysisMemory}

print("ReAct循环完成:")
print(f"- 工具调用序列: {result['tools_used']}")
print(f"- 消息链长度: {result['total_messages']}")
```

### 5.3 状态和记忆监控
```python
# LangGraph状态可以在执行过程中被监控
from langgraph.graph import StateGraph

agent = SemanticSQLReActAgent(settings, db_config)

# 添加状态监控回调
def monitor_state_changes(state):
    """监控LangGraph状态变化"""
    print(f"📊 工具使用: {state.get('tools_used', [])}")
    
    memory = state.get('memory')
    if memory:
        context = memory.get_typed_context()
        completion = context.get_completion_status()
        
        completed_count = sum(1 for done in completion.values() if done)
        print(f"📈 分析进度: {completed_count}/{len(completion)}")
        
        if context.domain_info:
            print(f"🏢 识别域: {context.domain_info.primary_domain}")

# 使用回调执行
result = agent.run("分析数据库并生成复杂查询")
```

### 5.4 流式执行和实时反馈
```python
# LangGraph支持流式执行，可以实时观察ReAct过程
agent = SemanticSQLReActAgent(settings, db_config)

initial_state = {
    "messages": [HumanMessage(content="分析销售数据库并生成Top10用户SQL")],
    "memory": agent.memory,
    "current_task": "分析任务",
    "tools_used": [],
    "analysis_complete": False
}

# 流式执行，实时观察每个节点的状态变化
for step in agent.react_app.stream(initial_state):
    node_name = list(step.keys())[0]
    node_output = step[node_name]
    
    print(f"\n🔄 执行节点: {node_name}")
    
    if node_name == "agent":
        # LLM思考和工具选择
        last_message = node_output["messages"][-1]
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            for tool_call in last_message.tool_calls:
                print(f"  🛠️ 选择工具: {tool_call['name']}")
                print(f"  📝 参数: {tool_call['args']}")
        else:
            print(f"  💭 LLM回应: {last_message.content[:100]}...")
    
    elif node_name == "tools":
        # 工具执行结果
        tool_messages = [msg for msg in node_output["messages"] if isinstance(msg, ToolMessage)]
        for tool_msg in tool_messages:
            print(f"  ✅ 工具结果: {tool_msg.content[:100]}...")

print("\n🎯 ReAct循环完成!")
```

### 5.5 自定义ReAct行为
```python
# 可以通过修改系统消息来调整LLM的ReAct行为
class CustomSemanticSQLAgent(SemanticSQLReActAgent):
    
    def _create_enhanced_system_message(self, state: AgentState) -> SystemMessage:
        """自定义系统消息，让LLM更积极使用思考工具"""
        memory_summary = state["memory"].get_summary()
        completion_status = state["memory"].get_typed_context().get_completion_status()
        
        system_content = f"""你是一个追求完美的数据库分析专家。

核心原则：
1. 对每个结果都要精益求精，主动质疑和验证
2. 遇到任何复杂或不确定的情况，必须使用sequential_thinking深度分析
3. 每完成一个重要工具调用后，考虑是否需要sql_reflection评估质量
4. 确保最终输出达到生产级别标准

可用工具：
{self._get_tool_descriptions()}

当前状态: {memory_summary}
完成情况: {completion_status}

请以最严格的标准完成任务，不要害怕多次使用工具来确保质量。"""
        
        return SystemMessage(content=system_content)

# 使用自定义智能体
custom_agent = CustomSemanticSQLAgent(settings, db_config)
result = custom_agent.run("生成高质量的用户留存分析SQL")
```

## 6. 方案优势

### 6.1 LangGraph ReAct的优势
- **状态机优雅性**：LangGraph提供清晰的状态管理和节点流转控制
- **ReAct标准实现**：完全符合ReAct模式，支持复杂的思考-行动-观察循环
- **流式执行支持**：天然支持流式执行，可实时观察智能体决策过程
- **调试友好性**：每个节点的状态变化都可追踪和监控

### 6.2 与现有架构的完美结合
- **BaseAgent继承**：完全复用现有BaseAgent的所有功能
- **工具无缝集成**：13个工具无需任何修改即可在LangGraph中使用
- **记忆系统保持**：DatabaseAnalysisMemory完整保留，状态双重管理
- **向后兼容**：保持现有所有接口和功能不变

### 6.3 智能决策能力
- **上下文感知**：系统消息实时包含记忆状态和完成情况
- **自主工具选择**：LLM根据当前状态智能选择最合适的工具
- **质量驱动**：支持工具重复执行和思考增强
- **任务自适应**：不同任务自动形成不同的工具调用序列

### 6.4 开发和运维友好
- **渐进式升级**：可与现有系统共存，逐步迁移
- **标准化架构**：基于LangChain生态，文档完善，社区支持好
- **监控和调试**：丰富的状态监控和流式执行能力
- **扩展性强**：新增工具或修改逻辑都很简单

## 7. 实施计划

### 7.1 实施步骤（LangGraph版本）
```
Phase 1: LangGraph ReAct基础实现 (1周)
├── 实现AgentState和基础图结构
├── 重写BaseAgent，集成LangGraph ReAct
├── 测试基本的ReAct循环功能
└── 验证工具调用和状态管理

Phase 2: 记忆和状态增强 (1周)  
├── 完善系统消息的记忆状态集成
├── 优化工具执行和状态更新逻辑
├── 添加流式执行和监控能力
└── 测试复杂任务的多轮ReAct

Phase 3: 智能决策优化 (1周)
├── 优化LLM的工具选择prompt
├── 增强SequentialThinkingTool的集成
├── 添加质量评估和重试机制
└── 性能调优和错误处理完善

Phase 4: 测试和部署 (1周)
├── 端到端功能测试
├── 与现有系统的对比测试  
├── 性能基准和压力测试
└── 文档完善和生产部署
```

### 7.2 技术优势对比

| 特性 | 传统AgentExecutor | LangGraph ReAct |
|------|-------------------|-----------------|
| 状态管理 | 内置记忆系统 | 显式状态机 + 记忆系统 |
| 执行控制 | 黑盒循环控制 | 透明的节点流转控制 |
| 调试能力 | 标准日志 | 节点级状态监控 + 流式执行 |
| 扩展性 | 修改prompt | 修改节点逻辑或添加新节点 |
| 复杂任务 | 依赖LLM控制 | 状态机 + LLM双重控制 |
| 错误处理 | 基础重试 | 节点级错误处理和状态恢复 |

### 7.3 核心价值
- **架构现代化**：从传统Agent升级到状态机架构，技术更先进
- **可观测性**：每个决策步骤都可观测，便于调试和优化
- **可控性增强**：在保持LLM智能决策的同时，增加系统级控制能力
- **生产就绪**：LangGraph的成熟度和稳定性更适合生产环境

这个基于LangGraph的ReAct方案既保持了LLM智能决策的灵活性，又提供了状态机的可控性和可观测性，是现有架构的完美升级路径。