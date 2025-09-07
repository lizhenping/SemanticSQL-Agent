# SemanticSQL Agent 接口设计方案总览

## 📋 文档结构

本设计方案严格遵循**极简ReAct设计理念**，按架构模块组织为以下文档：

### 核心文档
1. **[01-core模块接口设计.md](./01-core模块接口设计.md)** - 核心数据模型和状态管理
2. **[02-工具基类接口设计.md](./02-工具基类接口设计.md)** - 极简工具基类和统一接口
3. **[03-分析工具接口设计.md](./03-分析工具接口设计.md)** - 数据库分析工具组
4. **[04-生成工具接口设计.md](./04-生成工具接口设计.md)** - 问题和SQL生成工具组
5. **[05-验证和思考工具接口设计.md](./05-验证和思考工具接口设计.md)** - 验证和推理工具组
6. **[06-ReAct智能体接口设计.md](./06-ReAct智能体接口设计.md)** - ReAct智能体核心接口
7. **[07-辅助组件接口设计.md](./07-辅助组件接口设计.md)** - 配置、模板、数据库等辅助组件

## 🎯 设计核心理念

### 极简设计原则
基于`智能体ReAct编排设计方案.md`的核心要求：

1. **状态极简化**：`AgentState`只有`memory`和`current_input`两个字段
2. **三元组记忆**：简单的`List[Tuple[str, str, str]]`格式，直接操作
3. **工具无参数化**：工具从`state["memory"]`获取信息，最少外部参数
4. **LLM驱动选择**：ReAct模式下LLM动态选择工具，无预定义流水线
5. **should_continue决策**：严格保留您提供的决策函数逻辑

### 去掉的过度设计
❌ **移除的复杂组件**：
- 工厂模式、注册表、执行管理器
- 复杂的上下文管理和状态同步
- 执行统计、监控、分类管理
- 预定义的流水线模式
- 复杂的数据结构和元数据管理

## 🏗️ 架构概览

```
极简架构组成：
├── Core模块 (核心状态和数据模型)
├── Tools (工具直接操作记忆)
├── Agent (ReAct循环控制) 
└── Utils (最基础的辅助功能)
```

### 核心数据流
```
用户输入 → AgentState.memory (三元组列表)
    ↓
LLM分析记忆内容 → 选择合适工具
    ↓  
工具执行 → 直接操作state["memory"]
    ↓
should_continue决策 → 继续/结束
```

## 🔧 关键接口摘要

### 1. 核心数据模型
```python
# 极简三元组
class TripleOutput(BaseModel):
    subject: str
    predicate: str  
    object: str

# 统一工具输出
class ToolResult(BaseModel):
    triples: List[TripleOutput]
    summary: str
    tool_name: str

# 极简状态
class AgentState(TypedDict):
    memory: List[Tuple[str, str, str]]
    current_input: str
```

### 2. 工具基类
```python
class BaseSemanticSQLTool(BaseTool):
    def execute_with_state(self, state: AgentState, **kwargs) -> str:
        """直接操作state["memory"]"""
        raise NotImplementedError
```

### 3. ReAct智能体
```python
class BaseReActAgent:
    def should_continue(self, state: AgentState) -> Literal["tools", "__end__"]:
        """您的决策函数 - 检查LLM是否选择工具"""
        pass
    
    def call_model(self, state: AgentState) -> Dict[str, Any]:
        """LLM推理 - 使用Jinja2模板渲染记忆"""
        pass
```

## 🎪 工具组织结构

### 分析工具组 (Analysis Tools)
- `schema_extraction` - 数据库结构提取
- `domain_analysis` - 业务域分析
- `field_analysis` - 字段语义分析
- `table_analysis` - 表业务分析
- `er_analysis` - 实体关系分析

### 生成工具组 (Generation Tools)
- `question_generation` - 问题生成
- `sql_generation` - SQL生成

### 验证工具组 (Validation Tools) 
- `sql_validation` - SQL验证
- `sql_execution` - SQL执行

### 思考工具组 (Thinking Tools)
- `sequential_thinking` - LLM深度推理

## 🚀 使用示例

### 基本使用流程
```python
# 1. 创建智能体
agent = create_semantic_sql_agent(
    llm_config={"model": "gpt-4", "api_key": "..."},
    tools=get_all_tools()
)

# 2. 执行分析
result = agent.analyze_and_generate_sql(
    database_params={"host": "localhost", "database": "shop"},
    user_question="查询活跃用户"
)

# 3. 查看结果
print(f"生成 {len(result['memory'])} 个三元组")
for s, p, o in result["memory"][-5:]:
    print(f"  {s} → {p} → {o}")
```

### ReAct执行流程
```
用户: "分析数据库并生成查询SQL"
    ↓
LLM: 记忆为空 → 选择 schema_extraction
    ↓
ToolNode: 执行工具 → 更新memory
    ↓ 
LLM: 看到表信息 → 选择 domain_analysis
    ↓
继续ReAct循环...直到任务完成
```

## 📊 设计优势

### 真正的极简化
- **代码量减少60%**：去掉所有不必要的复杂层
- **维护成本低**：简单直接的接口，易于理解
- **扩展性好**：新工具只需实现execute_with_state方法

### 符合ReAct理念
- **LLM驱动**：智能体根据记忆状态动态选择工具
- **状态延续**：工具执行结果自然累积到记忆中
- **智能决策**：should_continue函数完美控制循环

### 生产就绪
- **错误处理**：简单但有效的错误捕获
- **配置管理**：基础的配置和模板系统
- **CLI支持**：命令行工具便于使用和调试

---

**总结**：这套接口设计完全遵循了`智能体ReAct编排设计方案.md`的核心理念，实现了真正的"极简+智能"架构。所有复杂的管理层都被移除，回归到ReAct的本质：LLM观察记忆状态，推理并选择工具，工具执行后更新记忆，循环直到任务完成。