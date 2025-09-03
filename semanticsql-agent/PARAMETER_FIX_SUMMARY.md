# 参数匹配问题修复总结

## 问题根因

LangChain的参数传递错误是因为**提示词中定义的参数与工具的args_schema不匹配**。

## 示例：ScenarioTool

**提示词中的调用**：
```
Action: scenario_tool
Action Input: {"iteration": 0}
```

**原始args_schema定义**：
```python
class ScenarioToolInput(BaseModel):
    iteration: int = Field(default=0, description="当前迭代次数")
```

这是匹配的，所以ScenarioTool只需要简单的修复即可工作。

## 问题工具：其他生成工具

### OperationSelectionTool
**提示词调用**：`{"scenario_id": "...", "complexity": "..."}`  
**原始期望**：`{"scenario": {...}, "memory": {...}}`  
**修复**：更新Input定义，接受scenario_id和complexity

### QuestionGenerationTool  
**提示词调用**：`{"scenario_id": "...", "operations": [...]}`  
**原始期望**：`{"scenario": {...}, "operations": [...], "memory": {...}}`  
**修复**：更新Input定义，接受scenario_id

### SQLGenerationTool
**提示词调用**：`{"question": "...", "scenario": {...}}`  
**原始期望**：`{"question": "...", "memory": {...}, "operations": [...]}`  
**修复**：更新Input定义，scenario变为可选参数

## 解决方案

1. **保留args_schema**：这是LangChain的标准做法
2. **更新Input定义**：使其与提示词中的调用方式匹配
3. **使用Optional参数**：为向后兼容性提供灵活性
4. **简化_run方法**：直接接受定义的参数，不需要复杂的解析

## 修复后的模式

```python
class ToolInput(BaseModel):
    # 匹配提示词中的参数
    scenario_id: str = Field(default="", description="场景ID")
    # 提供向后兼容
    scenario: Optional[Dict[str, Any]] = Field(default=None, description="完整场景信息")
    
def _run(
    self,
    scenario_id: str = "",
    scenario: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Dict[str, Any]:
    # 直接使用参数，无需复杂解析
    pass
```

## 关键教训

1. **始终检查提示词与工具参数的匹配性**
2. **LangChain的args_schema是有用的**，它提供参数验证
3. **问题通常是参数不匹配**，而不是LangChain的bug
4. **保持简单**：让参数定义与实际使用一致