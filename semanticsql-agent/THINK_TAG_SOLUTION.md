# Think标签处理方案

## 问题描述

Claude 等 LLM 在输出时可能包含 `<think>` 标签来表示内部思考过程。这些标签：
1. 不应该被传递给工具作为参数
2. 不应该被包含在最终输出中
3. 可能干扰 JSON 解析

## 解决方案

### 1. 创建 LLM 输出解析器
文件：`utils/llm_output_parser.py`
- `parse_llm_output()`: 分离思考内容和实际响应
- `clean_tool_response()`: 递归清理工具响应中的 think 标签
- `extract_json_from_text()`: 从文本中安全提取 JSON

### 2. 在工具基类中自动清理
文件：`tools/base_tool.py`
- 重写 `run()` 方法，在工具执行后自动清理输出
- 确保所有工具输出都不包含 think 标签

### 3. 在回调处理器中过滤
文件：`utils/callbacks.py`
- 在 `on_llm_end()` 中过滤 LLM 输出
- 将思考内容记录到日志（debug级别）
- 只传递清理后的内容给后续处理

### 4. 更新系统提示词
文件：`prompts/templates/system/main.j2`
- 明确告诉 LLM 不要使用 `<think>` 标签
- 强调 Action Input 必须是有效的参数格式

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