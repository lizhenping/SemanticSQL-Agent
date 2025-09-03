# Think标签处理方案（LangChain 标准实现）

## 问题描述

Claude 等 LLM 在输出时可能包含 `<think>` 或 `<thinking>` 标签来表示内部思考过程。这些标签：
1. 不应该被传递给工具作为参数
2. 不应该被包含在最终输出中
3. 可能干扰 JSON 解析

## 解决方案（完全符合 LangChain 设计模式）

### 1. 自定义输出解析器
文件：`utils/thinking_parser.py`
- `ThinkingOutputParser`: 继承自 `BaseOutputParser`，专门处理 thinking 标签
- `ReActThinkingParser`: 专门用于 ReAct 模式，同时处理 thinking 和 action
- 符合 LangChain 的可插拔设计，可以与任何 LLM 和 Chain 组合使用

```python
# 使用方式
from utils.thinking_parser import ThinkingOutputParser

parser = ThinkingOutputParser()
chain = prompt | llm | parser

result = chain.invoke({"question": "你的问题"})
print(f"思考过程: {result['thinking']}")
print(f"最终答案: {result['answer']}")
```

### 2. Thinking Chain 实现
文件：`chains/thinking_chain.py`
- 提供了完整的 Chain 实现和 LCEL 实现
- 支持单步思考和多步思考链
- 完全符合 LangChain 的链式调用模式

### 3. 在回调和工具中集成
- `utils/callbacks.py`: 使用 `ThinkingOutputParser` 在回调层统一处理
- `tools/base_tool.py`: 使用 parser 清理工具输出
- 保持了 DRY 原则，核心逻辑只在 parser 中实现一次

### 4. 测试驱动开发
文件：`tests/test_thinking_parser.py`
- 完整的单元测试覆盖各种场景
- 易于验证和维护

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