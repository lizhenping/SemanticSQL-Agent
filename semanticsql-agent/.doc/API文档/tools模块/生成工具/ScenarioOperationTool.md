# ScenarioOperationTool API 文档

场景-操作组合生成工具，系统的核心生成工具，合并了原来的场景选择和操作选择功能。

## 类定义

```python
from langchain.tools import BaseTool
from typing import Dict, Any, List
from semanticsql_agent.tools.generation_tools import ScenarioOperationTool

class ScenarioOperationTool(BaseTool):
    """
    场景-操作组合生成工具（核心工具）
    
    内部封装三层for循环，生成所有场景-操作组合，为每个组合生成专用提示词。
    
    Attributes:
        name: "scenario_operation_generation"
        description: "生成所有场景-操作组合，内部处理三层for循环遍历"
    """
```

## 功能概述

ScenarioOperationTool 是整个训练数据生成流程的核心工具，负责：

1. **内部三层遍历**：主场景 × 子场景 × 复杂度级别
2. **组合生成**：生成所有可能的场景-操作组合（通常48个）
3. **提示词生成**：为每个组合创建专门的问题生成指导
4. **操作映射**：根据复杂度自动选择合适的SQL操作组合

## 输入参数

### ScenarioOperationInput

```python
class ScenarioOperationInput(BaseModel):
    mode: str = Field(
        default="get_all_combinations",
        description="生成模式：get_all_combinations 或 get_single_combination"
    )
    iteration: int = Field(
        default=0,
        description="迭代次数（仅在 get_single_combination 模式下使用）"
    )
```

### 支持的模式

- **get_all_combinations**: 返回所有场景组合（默认）
- **get_single_combination**: 返回指定索引的单个组合

## 输出格式

### get_all_combinations 模式

```python
{
    "success": true,
    "total_combinations": 48,
    "combinations": [
        {
            "combination_id": "sales_analysis_simple",
            "index": 0,
            "scenario": {
                "main_key": "sales_analysis",
                "main_name": "销售分析",
                "main_description": "销售数据分析和统计",
                "sub_key": "sales_statistics", 
                "sub_name": "销售统计",
                "focus_areas": ["销售额", "订单量", "客户数"],
                "complexity": "simple"
            },
            "operations": ["SELECT", "WHERE"],
            "generated_prompt": "基于销售分析场景的销售统计任务，生成simple级别的问题。\n\n## 场景描述\n销售数据分析和统计\n\n## 任务焦点\n销售额, 订单量, 客户数\n\n## SQL操作要求\n必须使用以下操作: SELECT, WHERE\n\n## 复杂度要求\n基础查询\n\n请生成一个符合上述要求的自然语言问题。",
            "complexity_config": {
                "level": 1,
                "description": "基础查询"
            }
        },
        // ... 更多47个组合
    ],
    "generation_strategy": "三层遍历：主场景×子场景×复杂度"
}
```

### get_single_combination 模式

```python
{
    "success": true,
    "combination": {
        "combination_id": "inventory_management_moderate",
        "scenario": {...},
        "operations": ["SELECT", "GROUP BY", "HAVING"],
        "generated_prompt": "..."
    },
    "total_available": 48,
    "selected_index": 15
}
```

## 内部配置

### 主场景类别

```yaml
# scenarios.yaml
sales_analysis:
  name: "销售分析"
  description: "销售数据分析和统计"
  sub_scenarios:
    sales_statistics:
      name: "销售统计"
      focus_areas: ["销售额", "订单量", "客户数"]
    sales_trends:
      name: "销售趋势"
      focus_areas: ["时间趋势", "增长率", "季节性"]

inventory_management:
  name: "库存管理"
  description: "库存状态和补货分析"
  sub_scenarios:
    inventory_status:
      name: "库存状态"
      focus_areas: ["库存量", "库存预警", "周转率"]
```

### 操作映射

```yaml
# operation_mapping.yaml
simple: ["SELECT", "WHERE"]
moderate: ["SELECT", "GROUP BY", "HAVING"]
complex: ["SELECT", "JOIN", "SUBQUERY"]
expert: ["SELECT", "WINDOW_FUNCTION", "CTE"]
```

### 复杂度配置

```yaml
# complexity.yaml
simple:
  level: 1
  description: "基础查询"
moderate:
  level: 2
  description: "聚合分析"
complex:
  level: 3
  description: "多表关联"
expert:
  level: 4
  description: "高级特性"
```

## 使用示例

### Agent 调用方式

```python
# 获取所有组合
Action: scenario_operation_generation
Action Input: {"mode": "get_all_combinations"}

# 获取单个组合
Action: scenario_operation_generation
Action Input: {"mode": "get_single_combination", "iteration": 12}
```

### 编程调用方式

```python
from tools import ScenarioOperationTool

# 创建工具实例
tool = ScenarioOperationTool()

# 获取所有组合
result = tool._run(mode="get_all_combinations")
print(f"生成了 {result['total_combinations']} 个场景组合")

# 获取特定组合
single_result = tool._run(mode="get_single_combination", iteration=5)
print(f"选中组合: {single_result['combination']['combination_id']}")
```

## 三层遍历逻辑

工具内部实现了三层for循环：

```python
for main_key, main_data in scenarios.items():           # 主场景层
    for sub_key, sub_data in sub_scenarios.items():     # 子场景层
        for complexity in ['simple', 'moderate', 'complex', 'expert']:  # 复杂度层
            # 生成组合
            combination = {
                "combination_id": f"{main_key}_{sub_key}_{complexity}",
                "scenario": {...},
                "operations": [...],
                "generated_prompt": "..."
            }
```

## 错误处理

工具包含完善的错误处理机制：

```python
# 配置文件加载失败时使用默认配置
# 无效模式时返回错误信息
# 索引超出范围时自动取模处理
```

## 性能特点

- **延迟加载**: 配置文件仅在首次访问时加载
- **缓存复用**: 组合生成结果可被复用
- **内存高效**: 使用属性和方法避免不必要的存储

## 集成要点

1. **Agent自主调用**: Agent完全自主决策调用时机和参数
2. **记忆集成**: 生成结果自动保存到Agent记忆系统
3. **工具链协作**: 为后续的QuestionGenerationTool提供输入

---

相关文档：
- [QuestionGenerationTool](./QuestionGenerationTool.md) - 问题生成工具
- [SQLGenerationTool](./SQLGenerationTool.md) - SQL生成工具