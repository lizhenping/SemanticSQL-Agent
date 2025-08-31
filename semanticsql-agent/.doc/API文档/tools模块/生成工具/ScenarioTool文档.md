# ScenarioTool API 文档

## 概述
`ScenarioTool` 是基于数据库结构生成业务场景的工具。它能够根据数据库模式和业务领域信息，自动生成多样化的查询场景，用于训练数据生成或测试。

## 类定义
```python
class ScenarioTool(BaseTool):
    """基于规则的业务场景生成工具"""
```

## 工具属性

- **名称**: `scenario_generation`
- **类别**: `generation`
- **描述**: 基于数据库结构和业务领域生成查询场景

## 参数定义

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|-------|------|------|--------|------|
| schema_info | object | 是 | - | 数据库结构信息 |
| domain_info | object | 否 | {} | 业务领域信息 |
| count | integer | 否 | 10 | 生成场景数量 |
| difficulty | string | 否 | "mixed" | 难度级别 (easy/medium/hard/mixed) |

## 内置配置

### 场景类别
```python
scenario_categories = [
    "销售分析", "客户分析", "产品分析", "库存管理", 
    "财务报表", "员工管理", "系统监控", "数据统计"
]
```

### 难度分布
```python
difficulty_distribution = {
    "easy": 0.4,    # 40% 简单场景
    "medium": 0.4,  # 40% 中等场景
    "hard": 0.2     # 20% 困难场景
}
```

## 执行方法

### `_execute(...) -> List[QueryScenario]`

**返回数据结构：**
```python
[
    QueryScenario(
        id="scenario_001",
        category="销售分析",
        business_purpose="分析月度销售趋势",
        complexity=DifficultyLevel.MEDIUM,
        applicable_tables=["orders", "order_items", "products"],
        required_operations=[SQLOperation.SELECT, SQLOperation.GROUP],
        description="生成月度销售报表，包含总额和增长率"
    ),
    ...
]
```

## 内部方法

### `_generate_scenario(tables: List[str], category: str, difficulty: DifficultyLevel) -> QueryScenario`
生成单个场景。

**生成策略：**
1. 根据表结构选择相关表
2. 基于难度确定操作复杂度
3. 生成业务目的描述
4. 确定所需的 SQL 操作

### `_select_tables_for_scenario(all_tables: List[str], category: str, difficulty: DifficultyLevel) -> List[str]`
为场景选择相关表。

**选择规则：**
- 简单：1-2 个表
- 中等：2-3 个表
- 困难：3-5 个表

### `_determine_operations(difficulty: DifficultyLevel, table_count: int) -> List[SQLOperation]`
确定所需的 SQL 操作。

**操作映射：**
- 简单：SELECT, WHERE
- 中等：+ GROUP, ORDER, JOIN
- 困难：+ SUBQUERY, WINDOW, CTE

### `_generate_business_purpose(category: str, operations: List[str]) -> str`
生成业务目的描述。

## 场景类别详解

### 销售分析
- 销售趋势分析
- 产品销售排名
- 客户购买行为
- 收入预测

### 客户分析
- 客户细分
- 客户价值评估
- 流失预测
- 行为分析

### 产品分析
- 产品性能评估
- 库存周转
- 产品关联分析
- 定价策略

### 库存管理
- 库存水平监控
- 补货建议
- 库存成本分析
- 仓库优化

## 使用示例

### 基本使用
```python
# 创建工具实例
tool = ScenarioTool(settings)

# 准备数据库结构
schema_info = {
    "tables": {
        "orders": {...},
        "customers": {...},
        "products": {...}
    }
}

# 生成场景
scenarios = tool.run(
    schema_info=schema_info,
    count=10,
    difficulty="mixed"
)

if scenarios["success"]:
    for scenario in scenarios["data"]:
        print(f"场景: {scenario.category} - {scenario.business_purpose}")
        print(f"难度: {scenario.complexity.value}")
        print(f"涉及表: {', '.join(scenario.applicable_tables)}")
        print(f"操作: {', '.join([op.value for op in scenario.required_operations])}")
        print("-" * 50)
```

### 指定难度生成
```python
# 只生成简单场景
easy_scenarios = tool.run(
    schema_info=schema_info,
    count=20,
    difficulty="easy"
)

# 只生成困难场景
hard_scenarios = tool.run(
    schema_info=schema_info,
    count=5,
    difficulty="hard"
)
```

### 带领域信息的生成
```python
# 提供领域信息以生成更准确的场景
domain_info = {
    "primary_domain": "ecommerce",
    "business_entities": {
        "customer": ["users", "user_profiles"],
        "order": ["orders", "order_items"],
        "product": ["products", "categories"]
    }
}

scenarios = tool.run(
    schema_info=schema_info,
    domain_info=domain_info,
    count=15
)
```

## 生成示例

### 简单场景
```json
{
    "id": "scenario_001",
    "category": "产品分析",
    "business_purpose": "查看所有在售产品列表",
    "complexity": "easy",
    "applicable_tables": ["products"],
    "required_operations": ["SELECT"],
    "description": "获取当前所有状态为'在售'的产品信息"
}
```

### 中等场景
```json
{
    "id": "scenario_002",
    "category": "销售分析",
    "business_purpose": "分析各产品类别的月度销售额",
    "complexity": "medium",
    "applicable_tables": ["orders", "order_items", "products"],
    "required_operations": ["SELECT", "JOIN", "GROUP"],
    "description": "统计每个产品类别在过去各月的销售总额和订单数量"
}
```

### 困难场景
```json
{
    "id": "scenario_003",
    "category": "客户分析",
    "business_purpose": "识别高价值客户群体并分析其购买模式",
    "complexity": "hard",
    "applicable_tables": ["customers", "orders", "order_items", "products", "categories"],
    "required_operations": ["SELECT", "JOIN", "GROUP", "WINDOW", "SUBQUERY"],
    "description": "找出累计消费TOP 20%的客户，分析他们的购买频率、偏好类别和平均订单价值"
}
```

## 场景质量控制

### 多样性保证
- 类别轮换机制
- 表组合去重
- 操作组合变化

### 合理性检查
- 表关系验证
- 操作适用性
- 业务逻辑校验

### 平衡性控制
- 难度分布均衡
- 类别覆盖完整
- 操作类型多样

## 扩展定制

### 自定义场景类别
```python
# 添加行业特定场景
custom_categories = {
    "医疗": ["患者分析", "诊疗统计", "药品管理"],
    "教育": ["学生成绩", "课程分析", "教师评估"],
    "物流": ["运输分析", "路线优化", "成本核算"]
}
```

### 自定义难度规则
```python
# 调整难度参数
custom_difficulty = {
    "easy": {
        "max_tables": 2,
        "max_operations": 2,
        "allow_aggregation": False
    },
    "expert": {
        "min_tables": 4,
        "min_operations": 5,
        "require_advanced": True
    }
}
```

## 与其他工具配合

### 工作流示例
```python
# 1. 生成场景
scenarios = scenario_tool.run(schema_info=schema_info)

# 2. 为每个场景生成问题
for scenario in scenarios["data"]:
    questions = question_tool.run(
        scenario=scenario,
        operations=scenario.required_operations
    )
    
# 3. 生成对应的 SQL
for question in questions["data"]["questions"]:
    sql = sql_tool.run(
        question=question,
        schema_info=schema_info
    )
```

## 最佳实践

1. **合理设置数量**
   - 开发测试：10-20 个
   - 训练数据：100-1000 个
   - 避免一次生成过多

2. **难度平衡**
   - 使用 "mixed" 获得平衡分布
   - 根据用户水平调整比例
   - 逐步增加难度

3. **领域对齐**
   - 提供准确的领域信息
   - 确保场景符合业务实际
   - 定期更新场景模板

4. **质量验证**
   - 人工抽查生成质量
   - 确保场景可执行
   - 收集用户反馈改进

## 注意事项

1. 场景生成基于规则和模板，可能需要人工调整
2. 复杂数据库可能生成过于复杂的场景
3. 建议结合实际业务需求筛选场景
4. 生成的场景仅供参考，需要验证可行性