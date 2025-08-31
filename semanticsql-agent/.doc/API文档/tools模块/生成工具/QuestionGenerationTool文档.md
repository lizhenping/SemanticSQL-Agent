# QuestionGenerationTool API 文档

## 概述
`QuestionGenerationTool` 是用于生成自然语言查询问题的工具。它可以根据给定的场景、SQL 操作类型和数据库结构，生成多样化的自然语言问题。

## 类定义
```python
class QuestionGenerationTool(BaseTool):
    """基于场景生成自然语言问题"""
```

## 工具属性

- **名称**: `generate_question`
- **类别**: `generation`
- **描述**: 根据场景和操作生成自然语言查询问题

## 参数定义

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|-------|------|------|--------|------|
| scenario | object | 是 | - | 查询场景 |
| operations | array | 是 | - | SQL操作类型列表 |
| schema_info | object | 是 | - | 数据库结构信息 |
| style | string | 否 | "formal" | 问题风格 (formal/casual/technical) |
| use_llm | boolean | 否 | True | 是否使用LLM生成 |

## 执行方法

### `_execute(...) -> Dict[str, Any]`

**返回数据结构：**
```python
{
    "questions": List[str],              # 生成的问题列表
    "metadata": {                        # 元数据
        "scenario_id": str,              # 场景ID
        "difficulty": str,               # 难度级别
        "operations_used": List[str],    # 使用的操作
        "tables_involved": List[str],    # 涉及的表
        "generation_method": str         # 生成方法
    }
}
```

## 内部方法

### `_generate_with_llm(scenario: Dict, operations: List, schema_context: str, style: str) -> List[str]`
使用 LLM 生成问题。

**提示词策略：**
- 包含场景描述
- 指定操作要求
- 提供数据库上下文
- 设定风格约束

### `_generate_with_templates(scenario: Dict, operations: List, schema_info: Dict, style: str) -> List[str]`
使用模板生成问题（备选方案）。

**模板类型：**
- 基础查询模板
- 聚合查询模板
- 连接查询模板
- 复杂查询模板

### `_get_question_templates(operations: List[str], style: str) -> List[str]`
获取问题模板。

**模板示例：**
```python
# Formal 风格
"请查询{time_range}内{entity}的{metric}"
"显示所有{condition}的{entity}列表"

# Casual 风格
"我想看看{time_range}的{entity}{metric}"
"能帮我找出{condition}的{entity}吗"

# Technical 风格
"获取{table}表中{condition}的记录"
"执行{operation}操作统计{metric}"
```

## 问题风格

### Formal（正式）
- 使用规范的商务语言
- 结构完整清晰
- 适合报表和分析

### Casual（随意）
- 使用日常对话语言
- 更加自然亲切
- 适合交互式查询

### Technical（技术）
- 使用数据库术语
- 更接近 SQL 表达
- 适合技术人员

## 使用示例

### 基本使用
```python
# 创建工具实例
tool = QuestionGenerationTool(settings)

# 定义场景
scenario = {
    "id": "sales_analysis",
    "category": "销售分析",
    "business_purpose": "分析销售趋势",
    "complexity": "medium",
    "applicable_tables": ["orders", "order_items", "products"]
}

# 指定操作
operations = ["SELECT", "GROUP", "JOIN"]

# 生成问题
result = tool.run(
    scenario=scenario,
    operations=operations,
    schema_info=schema_info,
    style="formal"
)

if result["success"]:
    questions = result["data"]["questions"]
    for i, question in enumerate(questions, 1):
        print(f"{i}. {question}")
```

### 不同风格的生成
```python
# 正式风格
formal_result = tool.run(
    scenario=scenario,
    operations=["SELECT", "GROUP"],
    schema_info=schema_info,
    style="formal"
)
# 输出: "请查询2024年第一季度各产品类别的销售总额"

# 随意风格
casual_result = tool.run(
    scenario=scenario,
    operations=["SELECT", "GROUP"],
    schema_info=schema_info,
    style="casual"
)
# 输出: "我想看看今年一季度每个产品类别卖了多少钱"

# 技术风格
technical_result = tool.run(
    scenario=scenario,
    operations=["SELECT", "GROUP"],
    schema_info=schema_info,
    style="technical"
)
# 输出: "从orders表按product_category分组统计Q1的sum(amount)"
```

### 复杂场景生成
```python
# 复杂查询场景
complex_scenario = {
    "category": "客户分析",
    "business_purpose": "识别高价值客户",
    "complexity": "hard",
    "applicable_tables": ["customers", "orders", "payments"]
}

# 包含高级操作
advanced_operations = ["SELECT", "JOIN", "GROUP", "HAVING", "WINDOW"]

result = tool.run(
    scenario=complex_scenario,
    operations=advanced_operations,
    schema_info=schema_info
)
```

## 生成示例

### 输入场景
```json
{
    "category": "库存管理",
    "business_purpose": "监控库存水平",
    "applicable_tables": ["inventory", "products", "warehouses"]
}
```

### 生成的问题
```json
{
    "questions": [
        "请查询当前库存量低于安全库存的产品清单",
        "显示各仓库中每个产品类别的库存总值",
        "查找最近30天内库存变动超过50%的产品",
        "列出需要补货的产品及其建议采购量",
        "分析各仓库的库存周转率并按从高到低排序"
    ],
    "metadata": {
        "scenario_id": "inv_001",
        "difficulty": "medium",
        "operations_used": ["SELECT", "JOIN", "GROUP", "HAVING"],
        "tables_involved": ["inventory", "products", "warehouses"],
        "generation_method": "llm"
    }
}
```

## 操作类型映射

### 基础操作
- `SELECT` → "查询"、"显示"、"列出"
- `WHERE` → "筛选"、"过滤"、"满足条件"

### 聚合操作
- `GROUP` → "按...分组"、"各个"、"每个"
- `COUNT` → "数量"、"个数"、"统计"
- `SUM` → "总和"、"合计"、"总额"
- `AVG` → "平均"、"均值"

### 高级操作
- `JOIN` → "关联"、"结合"、"包含"
- `SUBQUERY` → "其中"、"存在"、"符合"
- `WINDOW` → "排名"、"累计"、"移动平均"

## 质量控制

### 多样性保证
- 使用不同的句式结构
- 变换查询角度
- 混合不同复杂度

### 合理性检查
- 确保问题符合业务逻辑
- 验证表和字段的相关性
- 检查操作的适用性

### 完整性要求
- 问题包含明确的查询目标
- 指定必要的条件和范围
- 提供足够的上下文信息

## 最佳实践

1. **场景设计**
   - 提供清晰的业务目的
   - 指定相关的数据表
   - 设置合适的复杂度

2. **操作选择**
   - 根据查询需求选择操作
   - 考虑操作的组合效果
   - 平衡查询复杂度

3. **风格一致性**
   - 同一批次使用相同风格
   - 考虑目标用户群体
   - 保持术语的一致性

4. **质量把控**
   - 生成后进行人工审核
   - 确保问题的可执行性
   - 验证业务合理性

## 扩展功能

### 自定义模板
```python
# 添加行业特定模板
custom_templates = {
    "电商": [
        "查看{time}的GMV和订单转化率",
        "分析{category}的复购率趋势"
    ],
    "金融": [
        "统计{period}的交易金额和手续费",
        "识别{risk_level}的异常交易"
    ]
}
```

### 多语言支持
- 支持中英文混合
- 可扩展其他语言
- 保持语义一致性

## 注意事项

1. LLM 生成可能有随机性，建议多次生成选择最佳
2. 模板生成速度快但灵活性有限
3. 复杂场景建议使用 LLM 生成
4. 注意避免生成无法执行的问题