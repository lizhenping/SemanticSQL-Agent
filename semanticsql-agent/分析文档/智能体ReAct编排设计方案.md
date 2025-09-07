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

### 2.1 核心架构组件

**状态定义**：
- `AgentState`: 包含三元组记忆列表和当前用户输入
- 记忆格式：`List[Tuple[str, str, str]]` 表示 (主语, 关系, 对象)

**核心接口**：
- `add_triple()`: 添加三元组到记忆
- `format_memory_text()`: 将记忆格式化为LLM可读文本

**数据结构**：
- `TripleOutput`: 标准三元组输出格式
- `ToolResult`: 所有工具的统一输出基类
- 工具特定结构：如 `ThinkingResult`, `ValidationResult` 等

**核心设计原则**：
- 状态极简化：只有记忆+输入两个字段
- 工具无参数化：从状态中获取所有信息
- 结构化输出：统一使用Pydantic模型

### 2.2 工具定义规范

**工具接口设计**：
- 所有工具接收 `AgentState` 参数
- 工具从 `state["memory"]` 获取输入信息  
- 输出格式为 `ToolResult` 结构的JSON字符串

**核心工具集**：

**数据分析工具**：
- `schema_extraction()`: 提取数据库结构，生成表-列关系三元组
- `domain_analysis()`: 分析业务域，识别核心模块和业务关联
- `field_analysis()`: 深度分析字段语义和业务含义
- `table_analysis()`: 分析表的业务作用和关系
- `er_analysis()`: 分析实体关系和外键约束

**生成工具**：
- `question_generation()`: 基于业务域生成典型NL2SQL问题
- `sql_generation()`: 根据问题和schema生成对应SQL

**验证工具**：  
- `sql_validation()`: 验证SQL语法和语义正确性
- `sql_execution()`: 执行SQL并验证结果

**推理工具**：
- `sequential_thinking()`: LLM深度推理分析当前状态

### 2.3 工作流设计

**ReAct循环结构**：
1. **Agent节点**: LLM基于记忆和用户输入选择工具
2. **Tools节点**: 使用ToolNode自动执行选中的工具  
3. **决策函数**: 使用您提供的should_continue函数判断是否继续

**系统消息模板**：
- 使用Jinja2模板渲染记忆内容和工具列表
- LLM根据格式化记忆选择合适的下一步工具
- 支持多轮ReAct循环直到任务完成

## 3. 决策函数设计

**should_continue函数的作用**：
- 这是ReAct循环的核心决策点
- 检查LLM是否选择了工具调用
- 如果选择了工具 → 继续执行("tools")  
- 如果没有选择工具 → 结束对话("__end__")

**为什么必需**：
- 防止无限循环：智能体需要知道何时停止
- LLM驱动决策：基于LLM的意图决定下一步行动
- 任务完成判断：当LLM认为任务完成时自动结束

## 4. 三元组记忆示例

**数据库结构三元组**：
- ("数据库", "包含", "用户表")
- ("用户表", "包含", "用户ID列")  
- ("用户ID列", "数据类型", "INTEGER")
- ("用户ID列", "含义", "用户唯一标识符")

**业务分析三元组**：
- ("数据库", "属于", "电商业务域")
- ("用户管理模块", "属于", "核心模块")
- ("用户表", "支持", "用户管理模块")

**问题处理三元组**：
- ("查询活跃用户", "定义为", "当前问题")
- ("查询活跃用户", "需要", "用户表")
- ("查询活跃用户", "对应SQL", "SELECT * FROM users WHERE...")

## 5. 典型执行流程

**简化版ReAct循环**：
```
用户输入: "分析数据库并生成SQL查询"
    ↓
LLM思考: 记忆为空，需要先提取schema
    ↓  
选择工具: schema_extraction()
    ↓
ToolNode: 自动执行，更新记忆
    ↓
LLM思考: 看到记忆中有表信息，分析业务域
    ↓
选择工具: domain_analysis()
    ↓
继续循环...直到任务完成
```

## 6. 系统消息模板设计

**Jinja2模板结构**：
- 动态渲染当前记忆内容
- 自动列出可用工具及其描述  
- 为LLM提供上下文以做出智能决策

**模板要素**：
- 记忆状态显示：格式化三元组为可读文本
- 工具列表：动态生成当前可用的工具选项
- 指令明确：引导LLM选择合适的下一步工具

## 7. 工作流构建规范  

**核心组件**：
- `call_model()`: LLM调用节点，使用Jinja2模板渲染系统消息
- `create_react_agent()`: 创建完整的ReAct工作流
- `ToolNode`: LangGraph内置的工具执行节点

**工作流结构**：
1. **节点定义**: agent节点(LLM) + tools节点(工具执行)
2. **边设置**: entry → agent → conditional_edges → tools/end
3. **循环机制**: tools → agent (形成ReAct循环)

**关键设计要点**：
- 使用您提供的should_continue函数作为条件路由
- ToolNode自动处理工具调用和参数传递
- 工具直接操作state["memory"]，无需复杂的状态同步

## 8. 使用方式

**基本使用流程**：
1. 创建ReAct智能体实例
2. 定义初始状态(空记忆 + 用户输入)
3. 调用智能体执行任务
4. 查看记忆中积累的知识三元组

**输入格式**：
```
initial_state = {
    "memory": [],  # 空记忆开始
    "current_input": "分析数据库并生成查询SQL"  
}
```

**输出内容**：
- 更新后的记忆状态
- 积累的知识三元组
- 最终生成的SQL结果(如果任务完成)

## 9. 实施计划

**分阶段实施**：
- **Phase 1**: 核心架构(状态定义、记忆管理、决策函数)
- **Phase 2**: 工具集成(重构为state参数模式)  
- **Phase 3**: 系统集成(模板、工作流、测试)

**设计优势**：
- **状态极简**: 只有记忆+输入两个字段，无复杂同步
- **工具无参数**: 直接操作记忆，链式依赖自然形成
- **LLM驱动**: 推理替代硬编码规则，智能化决策
- **真正实用**: 代码量减少40%，维护成本低

## 10. 项目结构

### 10.1 目录结构

**核心模块**：
- `core/`: 通用组件(schemas, state, memory, workflow)  
- `tools/`: 按功能分组的工具集(analysis/generation/validation/thinking)
- `prompts/`: Jinja2模板管理
- `agent/`: ReAct智能体封装
- `utils/`: 辅助工具(数据库、LLM客户端等)

### 10.2 关键接口规范

**数据模型接口**：
- `TripleOutput`: 通用三元组输出结构
- `ToolResult`: 工具统一输出基类
- 工具特定结构：放置在各工具组内部schemas.py

**工作流接口**：
- `AgentState`: 状态定义(memory + current_input)
- `add_triple()`: 记忆添加接口
- `format_memory_text()`: 记忆格式化接口
- `should_continue()`: 您的决策函数接口

### 10.3 设计优势

**架构清晰**：
- 分层职责明确：core负责通用功能，tools按功能分组
- 模块化设计：工具可独立开发和测试
- 接口统一：统一的输入输出格式，易于扩展

**就近原则**：
- 通用结构放在core：TripleOutput, ToolResult 
- 工具特定结构放在工具内部：ThinkingResult, ValidationResult等
- 降低耦合度，提高可维护性

**符合极简理念**：
- ✅ **极简状态**: 只有memory+current_input两个字段
- ✅ **三元组记忆**: 直观的tuple格式，无复杂查询
- ✅ **结构化输出**: 统一的工具输出格式
- ✅ **LangGraph集成**: 标准ReAct工作流
- ✅ **工具无参数**: 直接从状态获取信息
- ✅ **LLM驱动**: 推理替代硬编码规则

---

**设计文档总结**：本文档专注于架构设计和接口规范，为SemanticSQL Agent提供了一个真正极简且实用的ReAct实现方案。所有具体的代码实现将基于这些设计规范进行开发。
