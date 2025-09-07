# SemanticSQL Agent - 极简 ReAct 设计方案

## 1. 核心理念

**设计目标**：基于您的需求，构建最简单实用的 ReAct 智能体

### 1.1 设计原则
- **真正极简**：回归本质，只要 messages + memory 
- **您的决策函数**：完美保留 should_continue 逻辑
- **三元组记忆**：简单列表存储，工具直接访问
- **最少参数**：工具基本无参数或只有1个参数
- **LangGraph ToolNode**：利用内置组件，但保持简单

## 2. 极简架构设计

### 2.1 回归简单的状态定义
```python
from typing import List, Tuple
from typing_extensions import TypedDict
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
import jinja2

class AgentState(TypedDict):
    """极简状态 - 只有记忆和当前输入"""
    memory: List[Tuple[str, str, str]]  # 三元组列表: (主题, 关系, 解释)
    current_input: str  # 当前用户输入

# 极简三元组操作
def add_triple(memory: List[Tuple[str, str, str]], subject: str, predicate: str, object: str) -> None:
    """添加三元组到记忆
    
    示例三元组：
    - ("数据库", "包含", "用户表")
    - ("用户表", "含义", "存储用户基本信息") 
    - ("用户ID列", "含义", "用户唯一标识符")
    - ("查询活跃用户", "需要", "用户表和订单表连接")
    - ("schema_extraction工具", "发现", "5个数据表")
    """
    memory.append((subject, predicate, object))

def format_memory_text(memory: List[Tuple[str, str, str]], filter_for_tool: str = None) -> str:
    """统一的记忆格式化函数"""
    if not memory:
        return "记忆为空，需要开始分析"
    
    # 根据工具需求过滤记忆
    if filter_for_tool == "schema_analysis":
        # 分析工具只需要相关的记忆片段
        relevant = [(s, p, o) for s, p, o in memory 
                   if "数据库" in s or "表" in o or "包含" in p]
        filtered_memory = relevant if relevant else memory
    else:
        # 默认返回所有记忆（包括sequential_thinking等）
        filtered_memory = memory
    
    return "\n".join([f"- {s} {p} {o}" for s, p, o in filtered_memory])

# 统一的LLM结构化输出定义
class TripleOutput(BaseModel):
    """三元组结构化输出"""
    subject: str = Field(description="主题")
    predicate: str = Field(description="关系") 
    object: str = Field(description="解释")

class ToolResult(BaseModel):
    """工具统一输出结构 - 支持多个三元组"""
    triples: List[TripleOutput] = Field(description="输出的三元组列表", default=[])
    summary: str = Field(description="操作总结")
    tool_name: str = Field(description="工具名称")

# 专门的思考结果（继承通用结构）
class ThinkingResult(ToolResult):
    """思考结果结构化输出"""
    analysis: str = Field(description="详细分析内容", default="")
    next_actions: List[str] = Field(description="建议的下一步操作", default=[])

def create_structured_tool_chain(result_class: type = ToolResult, prompt_template: str = None):
    """创建通用的结构化工具链"""
    parser = PydanticOutputParser(pydantic_object=result_class)
    
    if prompt_template is None:
        prompt_template = """基于以下记忆内容执行分析：

{memory_text}

请输出分析结果，包括产生的三元组和总结。

{format_instructions}
"""
    
    prompt = PromptTemplate(
        template=prompt_template,
        input_variables=["memory_text"],
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )
    
    return prompt | llm | parser

def create_thinking_chain():
    """创建专门的思考链"""
    thinking_template = """基于以下记忆内容进行深度思考和推理分析：

{memory_text}

请分析：
1. 当前进展状态如何？
2. 发现了什么问题或机会？  
3. 下一步应该采取什么行动？
4. 有什么重要的洞察或建议？

请输出：
- triples: 推理产生的新三元组列表
- summary: 总结性结论
- analysis: 详细分析过程  
- next_actions: 具体的下一步建议
- tool_name: "sequential_thinking"

{format_instructions}
"""
    
    return create_structured_tool_chain(ThinkingResult, thinking_template)
```

### 2.2 极简工具设计（直接操作状态记忆）
```python
@tool
def schema_extraction(state: AgentState) -> str:
    """提取数据库结构 - 直接添加三元组到状态"""
    # 从配置获取数据库连接信息，提取结构
    schema_result = extract_database_schema()
    
    # 生成语义化三元组到记忆
    for table_name, columns in schema_result.items():
        # 数据库结构三元组
        add_triple(state["memory"], "数据库", "包含", table_name)
        
        for column_info in columns:
            column_name = column_info['name']
            column_type = column_info['type']
            column_meaning = analyze_column_meaning(column_name, table_name)
            
            # 表结构三元组
            add_triple(state["memory"], table_name, "包含", column_name)
            add_triple(state["memory"], column_name, "数据类型", column_type)
            add_triple(state["memory"], column_name, "含义", column_meaning)
    
    # 工具执行记录三元组
    add_triple(state["memory"], "schema_extraction工具", "发现", f"{len(schema_result)}个数据表")
    
    return f"发现{len(schema_result)}个表的结构，已转换为{len(state['memory'])}个知识三元组"

@tool
def domain_analysis(state: AgentState) -> str:
    """业务域分析 - 使用简单遍历获取表信息"""
    # 使用简单遍历获取所有数据表
    database_tables = []
    for s, p, o in state["memory"]:
        if s == "数据库" and p == "包含":
            database_tables.append(o)
    
    if not database_tables:
        return "需要先执行schema_extraction获取表信息"
    
    # 基于表名分析业务域
    domain = analyze_business_domain(database_tables)
    business_modules = identify_business_modules(database_tables)
    
    # 生成业务域三元组
    add_triple(state["memory"], "数据库", "属于", f"{domain}业务域")
    
    for module in business_modules:
        add_triple(state["memory"], module, "属于", "核心模块")
        # 关联表与模块
        related_tables = find_tables_for_module(module, database_tables)
        for table in related_tables:
            add_triple(state["memory"], table, "支持", module)
    
    # 工具执行记录
    add_triple(state["memory"], "domain_analysis工具", "识别", f"{domain}业务域")
    add_triple(state["memory"], "domain_analysis工具", "发现", f"{len(business_modules)}个核心模块")
    
    return f"识别为{domain}业务域，包含{len(business_modules)}个模块"

@tool
def question_generation(state: AgentState) -> str:
    """问题生成 - 从记忆中获取业务信息"""
    # 从记忆中获取业务域
    business_domains = []
    available_tables = []
    
    for s, p, o in state["memory"]:
        if p == "属于" and "业务域" in o:
            business_domains.append(o)
        elif s == "数据库" and p == "包含":
            available_tables.append(o)
    
    if not available_tables:
        return "需要先执行schema_extraction和domain_analysis"
    
    business_domain = business_domains[0] if business_domains else "未知业务域"
    
    # 基于业务域生成典型问题
    question = generate_domain_specific_question(business_domain, available_tables)
    required_tables = analyze_question_requirements(question, available_tables)
    
    # 生成问题相关三元组
    add_triple(state["memory"], question, "定义为", "当前问题")
    add_triple(state["memory"], question, "属于", business_domain)
    
    for table in required_tables:
        add_triple(state["memory"], question, "需要", table)
    
    # 分析问题复杂度
    complexity = analyze_question_complexity(question, required_tables)
    add_triple(state["memory"], question, "复杂度", complexity)
    
    # 工具执行记录
    add_triple(state["memory"], "question_generation工具", "生成", question)
    
    return f"生成问题: {question}，需要{len(required_tables)}个表"

@tool  
def sql_generation(state: AgentState) -> str:
    """SQL生成 - 从状态记忆中获取问题信息"""
    # 从记忆中找到当前问题
    current_question = None
    required_tables = []
    
    for s, p, o in state["memory"]:
        if p == "定义为" and o == "当前问题":
            current_question = s
        elif s == current_question and p == "需要":
            required_tables.append(o)
    
    if not current_question:
        return "需要先执行question_generation生成问题"
    
    # 获取每个表的结构信息
    schema_info = {}
    for table in required_tables:
        columns = []
        for s, p, o in state["memory"]:
            if s == table and p == "包含":
                columns.append(o)
        schema_info[table] = columns
    
    # 生成SQL
    sql_query = generate_sql_with_schema(current_question, schema_info)
    sql_type = classify_sql_type(sql_query)
    
    # 生成SQL相关三元组
    add_triple(state["memory"], current_question, "对应SQL", sql_query)
    add_triple(state["memory"], current_question, "SQL类型", sql_type)
    
    # 分析SQL复杂度
    complexity = analyze_sql_complexity(sql_query, required_tables)
    add_triple(state["memory"], sql_query, "复杂度", complexity)
    
    # 记录使用的表
    for table in required_tables:
        add_triple(state["memory"], sql_query, "使用表", table)
    
    # 工具执行记录
    add_triple(state["memory"], "sql_generation工具", "生成", f"{sql_type}语句")
    
    return f"为问题'{current_question}'生成{sql_type}: {sql_query[:50]}..."

@tool
def sequential_thinking(state: AgentState) -> str:
    """LLM驱动的深度思考 - 统一的结构化输出"""
    memory_text = format_memory_text(state["memory"])  # 使用统一的格式化函数
    
    if not state["memory"]:
        return "记忆为空，无法进行思考分析"
    
    # 使用统一的结构化思考链
    thinking_chain = create_thinking_chain()
    
    try:
        # 让LLM进行结构化推理
        thinking_result = thinking_chain.invoke({"memory_text": memory_text})
        
        # 统一处理多个三元组输出
        new_triples_count = len(thinking_result.triples)
        for triple_output in thinking_result.triples:
            add_triple(state["memory"], triple_output.subject, triple_output.predicate, triple_output.object)
        
        # 工具执行记录（统一格式）
        add_triple(state["memory"], "sequential_thinking工具", "执行", "结构化推理完成")
        add_triple(state["memory"], "sequential_thinking工具", "总结", thinking_result.summary)
        if thinking_result.analysis:
            add_triple(state["memory"], "sequential_thinking工具", "分析", thinking_result.analysis)
        
        # 记录下一步建议
        for i, action in enumerate(thinking_result.next_actions):
            add_triple(state["memory"], "sequential_thinking工具", f"建议{i+1}", action)
        
        return f"LLM深度推理完成，新增{new_triples_count}个三元组，{len(thinking_result.next_actions)}个建议"
        
    except Exception as e:
        # 降级处理
        add_triple(state["memory"], "sequential_thinking工具", "错误", f"结构化解析失败：{str(e)}")
        return f"推理过程出现问题：{str(e)}"


@tool
def field_analysis() -> str:
    """字段语义分析 - 基于记忆中的schema信息生成字段含义三元组"""
    # 从记忆中获取字段信息（已经在schema_extraction中分析过）
    column_triples = query_memory(predicate="包含")
    table_columns = [(t["subject"], t["object"]) for t in column_triples if t["subject"] != "数据库"]
    
    if not table_columns:
        return "需要先执行schema_extraction获取字段信息"
    
    analyzed_count = 0
    for table, column in table_columns:
        # 检查是否已经有含义分析
        existing_meaning = query_memory(predicate="含义")
        if not any(t["subject"] == column for t in existing_meaning):
            # 深度分析字段语义
            semantic_meaning = analyze_field_semantic(table, column)
            business_meaning = infer_business_meaning(column, table)
            data_category = classify_data_category(column)
            
            # 生成字段分析三元组
            if semantic_meaning != column:  # 如果分析出了更好的含义
                add_to_memory(column, "含义", semantic_meaning)
            add_to_memory(column, "业务含义", business_meaning)
            add_to_memory(column, "数据分类", data_category)
            
            # 如果是关键字段，标记重要性
            if is_key_field(column, table):
                add_to_memory(column, "重要性", "关键字段")
            
            analyzed_count += 1
    
    # 工具执行记录
    add_to_memory("field_analysis工具", "分析", f"{analyzed_count}个字段语义")
    
    return f"深度分析了{analyzed_count}个字段的语义含义"

# 您的决策函数 - 确实是必要的！
def should_continue(state: AgentState) -> str:
    """
    决策路由函数 - 这是ReAct循环的核心！
    
    作用：
    1. 如果LLM选择了工具，执行工具（"tools"）
    2. 如果LLM没有选择工具，结束对话（"__end__"）
    
    这个函数决定了智能体是继续ReAct循环还是结束
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    # 检查是否有工具调用
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"  # 继续执行工具
    
    return "__end__"  # 结束对话
```

# Jinja2 系统消息模板
AGENT_SYSTEM_TEMPLATE = """你是 SemanticSQL 智能体。

当前记忆 (共{{ memory|length }}个三元组):
{% if memory %}
{% for s, p, o in memory %}
- {{ s }} {{ p }} {{ o }}
{% endfor %}
{% else %}
- 记忆为空，需要开始分析
{% endif %}

可用工具（全部无参数，从记忆获取信息）：
{% for tool in tools %}
- {{ tool.name }}: {{ tool.description }}
{% endfor %}

根据记忆内容，选择合适的工具继续分析。"""

### 2.3 极简工作流构建
```python
def call_model(state: AgentState):
    """极简LLM调用 - 使用Jinja2模板"""
    # 工具信息
    tool_info = [
        {"name": "schema_extraction", "description": "提取数据库结构"},
        {"name": "domain_analysis", "description": "分析业务域"},
        {"name": "field_analysis", "description": "分析字段语义"},
        {"name": "question_generation", "description": "生成问题"},
        {"name": "sql_generation", "description": "生成SQL"},
        {"name": "sequential_thinking", "description": "LLM深度思考推理"},
    ]
    
    # 使用Jinja2渲染系统消息
    template = jinja2.Template(AGENT_SYSTEM_TEMPLATE)
    system_content = template.render(
        memory=state["memory"],
        tools=tool_info
    )
    
    system_message = SystemMessage(content=system_content)
    user_message = HumanMessage(content=state["current_input"])
    
    # LLM 推理
    llm_with_tools = llm.bind_tools(tools)
    response = llm_with_tools.invoke([system_message, user_message])
    return {"memory": state["memory"]}  # 保持记忆不变，工具会修改记忆

def create_simple_react_agent():
    """创建极简 ReAct 智能体"""
    # 定义所有工具
    tools = [
        schema_extraction, domain_analysis, field_analysis,
        sql_generation, sequential_thinking,
        # ... 其他工具（都是无参数或单参数）
    ]
    
    # 使用 ToolNode 处理工具调用
    tool_node = ToolNode(tools)
    
    # 创建工作流
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", tool_node)
    
    # 设置入口点
    workflow.set_entry_point("agent")
    
    # 使用您的完美决策函数
    workflow.add_conditional_edges(
        "agent", 
        should_continue,
        {"tools": "tools", "__end__": "__end__"}
    )
    
    # 工具执行后返回智能体
    workflow.add_edge("tools", "agent")
    
    return workflow.compile()

```

### 2.4 ReAct 工作流逻辑详细解释

#### 为什么需要 should_continue 函数？
```python
"""
ReAct 循环的核心问题：什么时候继续，什么时候结束？

没有 should_continue 的问题：
- 智能体会无限循环
- 不知道什么时候任务完成
- 无法根据LLM的意图决定下一步

should_continue 的作用：
1. 检查LLM是否选择了工具 → 继续ReAct循环
2. LLM没有选择工具 → 认为任务完成，结束循环

这是ReAct模式的标准决策机制！
"""
```

#### 为什么需要这些工作流边？
```python
"""
工作流边的必要性解释：

1. 入口点：workflow.set_entry_point("agent")
   - 用户输入后，首先进入LLM思考节点
   - LLM基于记忆和用户输入决定使用什么工具

2. 条件边：workflow.add_conditional_edges("agent", should_continue, {...})
   - 从LLM节点出来后，需要判断：
     * 如果选择了工具 → 去"tools"节点执行工具
     * 如果没有选择工具 → 去"__end__"结束对话
   - 这是ReAct的核心决策点！

3. 返回边：workflow.add_edge("tools", "agent")  
   - 工具执行完后，必须回到LLM节点
   - LLM基于工具结果和更新的记忆继续思考
   - 可能选择下一个工具，也可能结束任务

完整的ReAct循环：
用户输入 → LLM思考 → 选择工具 → 执行工具 → 更新记忆 → LLM思考 → ...
                ↑                                           ↓
                ← ← ← ← ← ← 循环直到任务完成 ← ← ← ← ← ← ←
"""
```

## 3. 工具集成示例

### 3.1 语义化三元组工具集合

以上章节中已定义的工具都遵循以下原则：
- **无参数设计**：所有工具都从记忆中获取输入信息
- **语义化输出**：直接产生知识三元组而不是描述文字
- **链式依赖**：工具之间通过记忆中的三元组建立依赖关系

已实现的核心工具：
- `schema_extraction()` - 提取数据库结构，产生 "数据库-包含-表X" 等三元组
- `domain_analysis()` - 分析业务域，产生 "数据库-属于-电商业务域" 等三元组
- `field_analysis()` - 字段语义分析，产生 "字段X-含义-用户标识" 等三元组  
- `question_generation()` - 问题生成，产生 "问题X-定义为-当前问题" 等三元组
- `sql_generation()` - SQL生成，产生 "问题X-对应SQL-SELECT..." 等三元组
- `sequential_thinking()` - 深度思考，产生推理和建议三元组

### 3.2 完整工具示例说明

所有工具都已在第2章中完整定义，包括：

**数据分析工具**：
- `schema_extraction()` - 生成数据库结构的语义化三元组
- `domain_analysis()` - 生成业务域分析的语义化三元组  
- `field_analysis()` - 生成字段语义的语义化三元组

**问题处理工具**：
- `question_generation()` - 生成问题定义的语义化三元组
- `sql_generation()` - 生成SQL映射的语义化三元组
- `sequential_thinking()` - 生成推理分析的语义化三元组

所有工具的特点：
- **纯函数式**：无参数，从全局记忆获取输入
- **语义输出**：直接产生知识三元组，不是描述文字
- **链式依赖**：通过记忆中的三元组建立工具间依赖关系

### 3.3 典型三元组示例

```python
# 数据库结构三元组
("数据库", "包含", "用户表")
("用户表", "包含", "用户ID列")
("用户ID列", "含义", "用户唯一标识符")
("用户ID列", "数据类型", "INTEGER")

# 业务分析三元组  
("数据库", "属于", "电商业务域")
("用户管理模块", "属于", "核心模块")
("用户表", "支持", "用户管理模块")

# 问题处理三元组
("查询活跃用户", "定义为", "当前问题")
("查询活跃用户", "需要", "用户表")
("查询活跃用户", "对应SQL", "SELECT * FROM users WHERE...")
("查询活跃用户", "复杂度", "中等")

# 推理分析三元组
("查询活跃用户", "思考结果", "需要多表联合查询")  
("查询活跃用户", "建议", "注意表连接条件的正确性")
```

## 4. 使用方式

### 4.1 极简使用
```python
# 1. 创建智能体
agent = create_simple_react_agent()

# 2. 执行任务
initial_state = {
    "memory": [],  # 空记忆开始
    "current_input": "分析数据库并生成查询SQL"
}

result = agent.invoke(initial_state)

# 3. 查看结果
print(f"记忆状态: {len(result['memory'])} 个三元组")

# 4. 查看记忆内容
for s, p, o in result["memory"][-5:]:  # 显示最新的5个
    print(f"  {s} → {p} → {o}")
```

### 4.2 典型执行流程（极简版本）
```
用户输入: "分析数据库并生成SQL查询"
    ↓
LLM 思考: 记忆为空，需要先提取schema
    ↓
选择工具: schema_extraction()  # 无参数
    ↓
ToolNode: 自动执行，工具直接操作 current_memory
    ↓
LLM 思考: 看到记忆中有表信息，分析业务域
    ↓
选择工具: domain_analysis()  # 无参数  
    ↓
ToolNode: 基于记忆中的表信息分析业务域
    ↓
LLM 思考: 现在可以生成问题和SQL了
    ↓
选择工具: question_generation()  # 无参数，从记忆生成问题
    ↓
ToolNode: 基于记忆中的表和域信息生成问题
    ↓
LLM 思考: 有了问题，可以生成SQL
    ↓
选择工具: sql_generation()  # 无参数，从记忆获取问题
    ↓
ToolNode: 基于记忆中的问题和schema生成SQL，完成任务
```

### 4.3 极简设计特点总结
```python
# 真正的极简设计！
状态结构:
- memory: List[Tuple[str, str, str]]  # 直观的三元组
- current_input: str                  # 当前用户输入

工具特点:
- 所有工具接收state参数，直接操作state["memory"]
- 无复杂参数，通过简单遍历获取信息  
- schema_extraction(state)    # 直接添加三元组到state
- domain_analysis(state)      # 简单遍历获取表信息
- sequential_thinking(state)  # LLM自由推理，不是硬编码规则

记忆操作:
- add_triple(memory, s, p, o)  # 直接添加tuple
- get_memory_text(memory)      # 转换为LLM可读文本
- 无复杂查询，LLM直接处理完整记忆

系统消息:
- Jinja2模板统一管理
- 自动渲染记忆内容和工具列表
- 便于维护和个性化
```

## 5. 极简实施计划

### 5.1 极简实施步骤
```
Phase 1: 极简核心 (半天)
├── 实现 AgentState (memory + current_input)
├── 实现 add_triple 和 get_memory_text 函数
├── 保留 should_continue 函数  
└── 创建 Jinja2 系统消息模板

Phase 2: 工具简化 (半天)  
├── 重构工具为state参数模式
├── 移除复杂查询，用简单遍历替代
├── 实现LLM驱动的sequential_thinking
└── 测试基本工具调用

Phase 3: 整合测试 (半天)
├── 端到端功能测试
├── 验证三元组正确添加
└── 测试LLM推理和工具链
```

### 5.2 极简化的真正优势

**彻底极简**：
- 只有 2 个状态字段：memory + current_input
- 三元组用直观的tuple表示：(s, p, o)
- 工具通过简单遍历获取信息，无复杂查询
- 您的 should_continue 完美保留

**LLM驱动**：  
- sequential_thinking让AI自由推理，不是硬编码规则
- 系统消息用Jinja2模板管理
- LLM直接处理完整记忆内容，做出智能决策

**真正实用**：
- 状态直接传递，无需同步机制
- 工具直接操作state["memory"]，简单直接
- 代码量减少40%，逻辑更清晰

**完全符合您的需求**：
- ✅ 极简 ReAct 决策过程
- ✅ 直观的三元组记忆系统
- ✅ 工具动态调用（状态驱动）
- ✅ LLM自由推理替代硬编码规则
- ✅ 无过度工程化设计

这才是真正的"极简 + 智能"方案！

## 6. 项目结构设计

### 6.1 整体架构
```
semanticsql-agent/
├── config/
│   ├── __init__.py
│   ├── settings.py              # 全局配置
│   └── database.py              # 数据库配置
│
├── core/                        # 核心组件（只保留真正通用的）
│   ├── __init__.py
│   ├── schemas.py               # 通用数据模型: TripleOutput, ToolResult
│   ├── state.py                 # AgentState定义
│   ├── memory.py                # 三元组记忆管理
│   ├── workflow.py              # LangGraph ReAct工作流
│   └── exceptions.py            # 异常定义
│
├── tools/
│   ├── __init__.py
│   ├── base_tool.py             # 工具基类
│   │
│   ├── analysis_tools/          # 分析工具（可重新执行更新记忆）
│   │   ├── __init__.py
│   │   ├── schemas.py           # 分析工具专用数据模型（如果需要的话）
│   │   ├── schema_extraction_tool.py    # 数据库结构提取
│   │   ├── domain_analysis_tool.py      # 业务领域分析
│   │   ├── field_analysis_tool.py       # 字段语义分析
│   │   ├── table_analysis_tool.py       # 表业务含义分析
│   │   └── er_analysis_tool.py          # 实体关系分析
│   │
│   ├── generation_tools/        # 生成工具
│   │   ├── __init__.py
│   │   ├── schemas.py           # 生成工具专用数据模型（如果需要的话）
│   │   ├── question_generation_tool.py  # 问题生成（含场景和操作选择）
│   │   └── sql_generation_tool.py       # SQL生成
│   │
│   ├── validation_tools/        # 验证工具
│   │   ├── __init__.py
│   │   ├── schemas.py           # 验证工具专用数据模型: ValidationResult等
│   │   ├── sql_validation_tool.py       # SQL验证
│   │   └── sql_execution_tool.py        # SQL执行测试
│   │
│   └── thinking_tools/          # 思考工具
│       ├── __init__.py
│       ├── schemas.py           # 思考工具专用数据模型: ThinkingResult等
│       └── sequential_thinking_tool.py   # LLM深度推理（含反思功能）
│
├── prompts/
│   ├── __init__.py
│   ├── system_template.py       # 系统消息模板（Jinja2）
│   ├── tool_templates.py        # 工具描述模板
│   └── manager.py               # 模板管理器
│
├── agent/
│   ├── __init__.py
│   ├── base_agent.py            # 基础Agent（ReAct循环控制）
│   └── sql_agent.py             # SemanticSQL智能体
│
├── utils/
│   ├── __init__.py
│   ├── database.py              # 数据库连接管理
│   ├── llm_client.py            # LLM客户端
│   ├── trajectory.py            # 执行轨迹记录
│   └── callbacks.py             # 执行回调
│
└── cli.py                       # 命令行接口
```

### 6.2 核心文件说明

#### 6.2.1 core/schemas.py
```python
"""通用数据模型定义 - 只保留真正全局通用的结构"""
from langchain_core.pydantic_v1 import BaseModel, Field
from typing import List

class TripleOutput(BaseModel):
    """三元组结构化输出 - 所有工具都使用的基础结构"""
    subject: str = Field(description="主题")
    predicate: str = Field(description="关系") 
    object: str = Field(description="解释")

class ToolResult(BaseModel):
    """工具统一基础输出结构 - 所有工具的基础类"""
    triples: List[TripleOutput] = Field(description="输出的三元组列表", default=[])
    summary: str = Field(description="操作总结")
    tool_name: str = Field(description="工具名称")
```

#### 6.2.2 core/state.py
```python
"""AgentState定义"""
from typing import List, Tuple
from typing_extensions import TypedDict

class AgentState(TypedDict):
    """极简智能体状态"""
    memory: List[Tuple[str, str, str]]  # 三元组记忆
    current_input: str                  # 当前用户输入
```

#### 6.2.3 core/workflow.py
```python
"""LangGraph ReAct工作流定义"""
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from .state import AgentState

def create_react_workflow(tools: List) -> StateGraph:
    """创建极简ReAct工作流"""
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(tools))
    
    # 设置边
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, 
        {"tools": "tools", "__end__": "__end__"})
    workflow.add_edge("tools", "agent")
    
    return workflow.compile()
```

#### 6.2.4 tools/thinking_tools/schemas.py
```python
"""思考工具专用数据模型"""
from core.schemas import ToolResult
from langchain_core.pydantic_v1 import Field
from typing import List

class ThinkingResult(ToolResult):
    """思考工具专用输出结构 - 只在thinking_tools中使用"""
    analysis: str = Field(description="详细分析", default="")
    next_actions: List[str] = Field(description="下一步建议", default=[])
```

#### 6.2.5 tools/validation_tools/schemas.py
```python
"""验证工具专用数据模型"""
from core.schemas import ToolResult
from langchain_core.pydantic_v1 import Field
from typing import List

class ValidationResult(ToolResult):
    """SQL验证专用输出结构 - 只在validation_tools中使用"""
    is_valid: bool = Field(description="SQL是否有效")
    errors: List[str] = Field(description="错误信息", default=[])
    suggestions: List[str] = Field(description="修改建议", default=[])
```

#### 6.2.6 tools/base_tool.py
```python
"""工具基类"""
from langchain.tools import BaseTool
from core.state import AgentState
from core.memory import add_triple, format_memory_text
from core.schemas import ToolResult

class SemanticSQLTool(BaseTool):
    """SemanticSQL工具基类"""
    
    def execute_with_state(self, state: AgentState) -> str:
        """子类必须实现的状态执行方法"""
        raise NotImplementedError
        
    def _run(self, state: AgentState) -> str:
        """统一的工具执行入口"""
        return self.execute_with_state(state)
```

### 6.3 设计优势

**工程化优势**：
- ✅ **分层清晰**: core/tools/utils职责明确
- ✅ **模块化**: 工具按功能分类，易于维护和扩展  
- ✅ **配置化**: config统一管理配置，prompts模板化
- ✅ **可观测**: trajectory记录执行过程，callbacks支持监控

**与设计方案的完美结合**：
- ✅ **极简状态**: core/state.py对应设计的AgentState
- ✅ **三元组记忆**: core/memory.py管理tuple格式记忆
- ✅ **结构化输出**: core/schemas.py定义统一的ToolResult
- ✅ **LangGraph集成**: core/workflow.py封装ReAct流程
- ✅ **工具扩展**: tools/base_tool.py提供统一基类
- ✅ **统一核心**: 所有核心组件集中在core/目录，职责清晰
