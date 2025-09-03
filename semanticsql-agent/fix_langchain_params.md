# LangChain 参数传递问题修复方案

## 问题描述

LangChain 在调用工具时，有时会将整个 JSON 字符串作为第一个参数传递，而不是解析后的参数。这导致 Pydantic 验证失败。

错误示例：
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for ScenarioToolInput
iteration
  Input should be a valid integer, unable to parse string as an integer [type=int_parsing, input_value='{"database_name": "testdb", "iteration": 1}', input_type=str]
```

## 解决方案

1. **注释掉 `args_schema`**：避免 LangChain 的严格参数验证
2. **使用通用参数解析**：创建辅助函数处理各种参数传递方式
3. **更新 `_run` 方法**：使用 `tool_input: Any = None` 作为第一个参数

## 已修复的工具

### 生成工具
- ✅ ScenarioTool
- ✅ OperationSelectionTool  
- ✅ QuestionGenerationTool
- ✅ SQLGenerationTool

### 待修复的分析工具
- ⏳ SchemaExtractionTool
- ⏳ DomainAnalysisTool
- ⏳ FieldClassificationTool
- ⏳ ColumnMeaningTool
- ⏳ TableMeaningTool
- ⏳ ERAnalysisTool

## 修复模板

```python
# 1. 注释掉 args_schema
# args_schema: Type[BaseModel] = SomeInput

# 2. 更新 _run 方法签名
def _run(self, tool_input: Any = None, **kwargs) -> Dict[str, Any]:
    """工具描述"""
    try:
        # 使用辅助函数解析参数
        params = merge_tool_params(
            tool_input, 
            kwargs, 
            expected_params=["param1", "param2", ...]
        )
        
        # 获取参数
        param1 = params.get("param1", default_value)
        param2 = params.get("param2", default_value)
        
        # 业务逻辑...
```

## 测试建议

修复后需要测试：
1. 直接参数调用：`tool(param1=value1, param2=value2)`
2. JSON 字符串调用：`tool('{"param1": value1, "param2": value2}')`
3. 混合调用：第一个参数是 JSON，其他通过 kwargs