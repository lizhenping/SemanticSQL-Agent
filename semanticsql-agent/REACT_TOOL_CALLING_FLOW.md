# ReAct 模式下的 Tool Calling 流程详解

## 🔄 ReAct (Reasoning + Acting) 模式

ReAct 模式是一种让 LLM 通过"思考-行动-观察"循环来解决问题的方法。

### 核心循环：
1. **Thought（思考）**: LLM 分析当前状态，决定下一步
2. **Action（行动）**: LLM 调用工具执行操作
3. **Observation（观察）**: 获取工具执行结果
4. 重复直到任务完成

## 📋 具体流程示例

假设用户问："数据库中有多少个用户？"

### Step 1: 初始消息
```python
messages = [
    LLMMessage(
        role="system", 
        content="你是一个 SQL 专家，通过调用工具来完成任务。"
    ),
    LLMMessage(
        role="user",
        content="数据库中有多少个用户？"
    )
]

# 可用工具
tools = [
    schema_extraction_tool.get_schema(),
    sql_generation_tool.get_schema(),
    sql_execution_tool.get_schema()
]
```

### Step 2: LLM 第一次响应（思考 + 决定调用工具）
```python
response = llm_client.chat(messages, tools=tools)

# LLM 响应包含 tool_calls
# response.content: "我需要先查看数据库结构来找到用户表..."
# response.tool_calls: [
#     ToolCall(
#         name="schema_extraction",
#         call_id="call_123",
#         arguments={"include_stats": True}
#     )
# ]
```

### Step 3: 执行工具调用
```python
for tool_call in response.tool_calls:
    if tool_call.name == "schema_extraction":
        # 执行工具
        result = schema_extraction_tool.execute(**tool_call.arguments)
        
        # 构建工具结果消息
        tool_message = LLMMessage(
            role="tool",
            tool_result=ToolResult(
                call_id=tool_call.call_id,
                name=tool_call.name,
                success=True,
                result=json.dumps(result)
            )
        )
        messages.append(tool_message)
```

### Step 4: LLM 处理工具结果（观察 + 再次思考）
```python
# 继续对话
response = llm_client.chat(messages, tools=tools)

# LLM 分析了数据库结构，决定生成 SQL
# response.tool_calls: [
#     ToolCall(
#         name="sql_generation",
#         call_id="call_456", 
#         arguments={
#             "query": "统计用户总数",
#             "schema_info": {...}  # 从上一步获得的信息
#         }
#     )
# ]
```

### Step 5: 执行 SQL 生成
```python
# 类似 Step 3，执行工具并添加结果到消息历史
```

### Step 6: LLM 决定执行 SQL
```python
# response.tool_calls: [
#     ToolCall(
#         name="sql_execution",
#         call_id="call_789",
#         arguments={
#             "sql": "SELECT COUNT(*) FROM users"
#         }
#     )
# ]
```

### Step 7: 最终回答
```python
# 执行 SQL 后，LLM 给出最终答案
response = llm_client.chat(messages, tools=tools)

# response.content: "根据查询结果，数据库中共有 1,234 个用户。"
# response.tool_calls: None  # 不再需要调用工具
```

## 🔧 关键实现细节

### 1. 消息历史的维护
```python
# LLMClient 内部维护完整的消息历史
self.message_history = [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "数据库中有多少个用户？"},
    {"role": "assistant", "content": None, "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "call_123", "content": "..."},
    {"role": "assistant", "content": None, "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "call_456", "content": "..."},
    # ... 继续累积
]
```

### 2. 工具调用的 API 格式
```json
// 发送给 Qwen 的请求
{
    "model": "Qwen3-14B",
    "messages": [...],
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "schema_extraction",
                "description": "提取数据库结构信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "include_stats": {
                            "type": "boolean",
                            "description": "是否包含统计信息"
                        }
                    }
                }
            }
        }
    ],
    "tool_choice": "auto"
}
```

### 3. Qwen 的响应格式
```json
// Qwen 返回的响应
{
    "choices": [{
        "message": {
            "role": "assistant",
            "content": null,  // 调用工具时可能为空
            "tool_calls": [{
                "id": "call_123",
                "type": "function",
                "function": {
                    "name": "schema_extraction",
                    "arguments": "{\"include_stats\": true}"
                }
            }]
        }
    }]
}
```

## 🎯 ReAct 的优势

1. **可解释性** - 每一步的思考和行动都是可见的
2. **可控性** - 可以限制工具调用次数，避免无限循环
3. **灵活性** - LLM 自主决定调用哪些工具
4. **准确性** - 通过工具获取真实数据，而不是猜测

## 💡 在 SemanticSQL-Agent 中的应用

```python
class SQLAgent:
    def execute_task(self, task: str) -> AgentExecution:
        messages = [self._build_system_message()]
        messages.append(LLMMessage(role="user", content=task))
        
        step_count = 0
        while step_count < self.max_steps:
            # 1. LLM 思考并决定行动
            response = self.llm.chat(messages, tools=self.available_tools)
            
            # 2. 检查是否完成
            if not response.tool_calls:
                # 任务完成
                break
            
            # 3. 执行工具调用
            for tool_call in response.tool_calls:
                result = self._execute_tool(tool_call)
                messages.append(self._create_tool_message(tool_call, result))
            
            step_count += 1
        
        return self._create_execution_result(messages)
```

## 🔍 调试提示

1. **查看完整消息历史** - 了解 LLM 的思考过程
2. **检查工具调用参数** - 确保 LLM 正确理解了工具用法
3. **监控循环次数** - 避免无限循环
4. **记录工具执行结果** - 便于问题排查

这就是 Tool Calling 在 ReAct 模式中的完整流程！