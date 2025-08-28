"""简单使用示例 - 使用 OpenAI SDK"""

from openai import OpenAI

# 1. 直接使用 OpenAI SDK
client = OpenAI(
    api_key="not-needed",
    base_url="http://192.168.200.216:9009/v1"
)

# 2. 定义工具
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "获取指定位置的当前天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "城市名，例如：北京、上海"
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "温度单位"
                    }
                },
                "required": ["location"]
            }
        }
    }
]

# 3. 发送带工具的请求
response = client.chat.completions.create(
    model="Qwen3-14B",
    messages=[
        {"role": "system", "content": "你是一个有用的助手。"},
        {"role": "user", "content": "北京的天气怎么样？"}
    ],
    tools=tools,
    tool_choice="auto"
)

# 4. 处理响应
message = response.choices[0].message

if message.tool_calls:
    # LLM 决定调用工具
    for tool_call in message.tool_calls:
        print(f"工具调用: {tool_call.function.name}")
        print(f"参数: {tool_call.function.arguments}")
        
        # 模拟执行工具
        if tool_call.function.name == "get_current_weather":
            # 实际应该调用真实的天气 API
            weather_result = {
                "temperature": 25,
                "condition": "晴",
                "humidity": 60
            }
            
            # 5. 将结果发回给 LLM
            response = client.chat.completions.create(
                model="Qwen3-14B",
                messages=[
                    {"role": "system", "content": "你是一个有用的助手。"},
                    {"role": "user", "content": "北京的天气怎么样？"},
                    {"role": "assistant", "content": None, "tool_calls": message.tool_calls},
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.function.name,
                        "content": str(weather_result)
                    }
                ]
            )
            
            # 6. 获取最终回答
            final_answer = response.choices[0].message.content
            print(f"\n最终回答: {final_answer}")
else:
    # 直接回答，没有工具调用
    print(f"回答: {message.content}")