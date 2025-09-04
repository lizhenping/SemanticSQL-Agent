# Think标签处理和思考工具实现（LangChain 标准）

## 1. Think 标签处理

### 问题描述
Claude 等 LLM 在输出时可能包含 `<think>` 或 `<thinking>` 标签来表示内部思考过程。这些标签：
1. 不应该被传递给工具作为参数
2. 不应该被包含在最终输出中
3. 可能干扰 JSON 解析

### 解决方案
文件：`utils/thinking_parser.py`
- `ThinkingOutputParser`: 继承自 `BaseOutputParser`，专门处理 thinking 标签
- 在 `utils/callbacks.py` 和 `tools/base_tool.py` 中集成使用
- 支持 `<think>` 和 `<thinking>` 标签（大小写不敏感）

## 2. Sequential Thinking Tool（LangChain 标准实现）

### 重构说明
文件：`tools/thinking_tools/sequential_thinking_tool.py`

从自定义实现重构为使用 LangChain 标准组件：

#### 使用的 LangChain 组件
1. **ChatPromptTemplate** - 结构化的提示词模板
2. **PydanticOutputParser** - 结构化输出解析
3. **RunnableSequence** - LCEL 链式调用
4. **LLMChain** - 后备方案的简单链

#### 核心特性
```python
# 定义结构化输出
class ThinkingStrategy(BaseModel):
    analysis: str
    root_cause: str
    next_action: str
    reasoning: str
    confidence: float

# 使用 LCEL 构建思考链
thinking_chain = prompt | llm | parser
```

#### 优势
1. **标准化** - 使用 LangChain 的标准组件
2. **可维护** - 符合 LangChain 生态的最佳实践
3. **灵活性** - 支持同步和异步执行
4. **错误处理** - 内置后备分析机制

## 使用示例

```python
# 原始LLM输出
output = """
<think>
我需要分析这个数据库的结构...
</think>

Thought: 我需要提取数据库结构
Action: schema_extraction
Action Input: {"database": "testdb"}
"""

# 清理后
cleaned = """
Thought: 我需要提取数据库结构
Action: schema_extraction
Action Input: {"database": "testdb"}
"""
```

## 效果

1. **工具调用更稳定** - 不会因为 think 标签导致参数解析失败
2. **输出更清晰** - 用户看到的是干净的输出
3. **调试更方便** - 思考内容保存在日志中，便于调试

## 注意事项

- 这个方案对所有 LLM 都有效，不仅限于 Claude
- 思考内容会被记录到 debug 日志，不会丢失
- 不影响正常的 Thought/Action/Observation 流程