# ERAnalysisTool API 文档

## 概述
`ERAnalysisTool` 是用于分析数据库表之间实体关系的工具。它能够识别显式和隐式的表关系，构建实体关系图，并提供关系分析建议。

## 类定义
```python
class ERAnalysisTool(BaseTool):
    """实体关系分析工具"""
```

## 工具属性

- **名称**: `analyze_er`
- **类别**: `analysis`
- **描述**: 分析数据库表之间的实体关系，构建ER图

## 参数定义

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|-------|------|------|--------|------|
| schema_info | object | 是 | - | 数据库结构信息 |
| analyze_implicit | boolean | 否 | True | 是否分析隐式关系 |
| depth | integer | 否 | 2 | 关系分析深度 |

## 执行方法

### `_execute(...) -> Dict[str, Any]`

**返回数据结构：**
```python
{
    "entities": Dict[str, Dict],        # 实体信息
    "relationships": List[Dict],        # 关系列表
    "relationship_graph": Dict,         # 关系图
    "entity_clusters": List[List[str]], # 实体聚类
    "statistics": Dict,                 # 统计信息
    "recommendations": List[str]        # 分析建议
}
```

## 内部分析方法

### `_identify_entities(schema_info: Dict) -> Dict[str, Dict]`
识别数据库中的实体。

**实体分类：**
- **主实体（Master）**：独立存在的核心业务对象
- **事务实体（Transactional）**：记录业务活动
- **查找实体（Lookup）**：提供参考数据
- **关联实体（Junction）**：多对多关系表

### `_extract_explicit_relationships(schema_info: Dict) -> List[Dict]`
提取基于外键的显式关系。

**关系类型：**
- `one-to-one`：一对一关系
- `one-to-many`：一对多关系
- `many-to-many`：多对多关系

### `_analyze_implicit_relationships(schema_info: Dict, explicit_rels: List) -> List[Dict]`
分析基于命名约定和数据模式的隐式关系。

**识别规则：**
- 字段名称相似性（如 user_id, customer_id）
- 数据类型匹配
- 命名模式（如 xxx_id 格式）

### `_build_relationship_graph(entities: Dict, relationships: List) -> Dict`
构建关系图结构。

**图结构：**
```python
{
    "table_name": {
        "parents": ["parent_table1", ...],
        "children": ["child_table1", ...],
        "related": ["related_table1", ...]
    }
}
```

### `_find_entity_clusters(graph: nx.Graph) -> List[List[str]]`
使用图算法查找实体聚类。

**聚类方法：**
- 连通分量分析
- 社区检测
- 密度聚类

## 使用示例

### 基本使用
```python
# 创建工具实例
tool = ERAnalysisTool(settings)

# 准备数据库结构
schema_info = {
    "tables": {
        "users": {
            "columns": [...],
            "foreign_keys": []
        },
        "orders": {
            "columns": [...],
            "foreign_keys": [
                {
                    "column": "user_id",
                    "referenced_table": "users",
                    "referenced_column": "id"
                }
            ]
        },
        "order_items": {
            "columns": [...],
            "foreign_keys": [
                {
                    "column": "order_id",
                    "referenced_table": "orders",
                    "referenced_column": "id"
                }
            ]
        }
    }
}

# 执行分析
result = tool.run(
    schema_info=schema_info,
    analyze_implicit=True,
    depth=3
)

if result["success"]:
    data = result["data"]
    
    # 查看实体分类
    print("实体分类:")
    for entity, info in data["entities"].items():
        print(f"- {entity}: {info['type']} ({info['importance']})")
    
    # 查看关系
    print("\n表关系:")
    for rel in data["relationships"]:
        print(f"- {rel['from_table']} -> {rel['to_table']} ({rel['type']})")
    
    # 查看聚类
    print("\n实体聚类:")
    for i, cluster in enumerate(data["entity_clusters"]):
        print(f"聚类 {i+1}: {', '.join(cluster)}")
```

### 高级分析
```python
# 只分析显式关系
result = tool.run(
    schema_info=schema_info,
    analyze_implicit=False  # 禁用隐式关系分析
)

# 深度关系分析
result = tool.run(
    schema_info=schema_info,
    depth=5  # 分析5层深度的关系
)
```

## 输出示例

```json
{
    "entities": {
        "users": {
            "type": "master",
            "importance": "high",
            "attributes": ["id", "name", "email", "created_at"],
            "role": "核心用户实体"
        },
        "orders": {
            "type": "transactional",
            "importance": "high",
            "attributes": ["id", "user_id", "total", "status"],
            "role": "订单事务"
        },
        "products": {
            "type": "master",
            "importance": "high",
            "attributes": ["id", "name", "price", "category"],
            "role": "产品主数据"
        }
    },
    "relationships": [
        {
            "from_table": "orders",
            "to_table": "users",
            "type": "many-to-one",
            "via": "user_id",
            "strength": "strong",
            "confidence": 1.0
        },
        {
            "from_table": "order_items",
            "to_table": "orders",
            "type": "many-to-one",
            "via": "order_id",
            "strength": "strong",
            "confidence": 1.0
        }
    ],
    "relationship_graph": {
        "users": {
            "parents": [],
            "children": ["orders", "user_addresses"],
            "related": ["user_roles"]
        },
        "orders": {
            "parents": ["users"],
            "children": ["order_items", "payments"],
            "related": []
        }
    },
    "entity_clusters": [
        ["users", "orders", "order_items", "payments"],
        ["products", "categories", "inventory"],
        ["employees", "departments", "salaries"]
    ],
    "statistics": {
        "total_entities": 15,
        "master_entities": 5,
        "transactional_entities": 6,
        "relationships_count": 18,
        "avg_relationships_per_table": 2.4,
        "max_relationship_depth": 4
    },
    "recommendations": [
        "建议为 orders.user_id 创建索引以优化连接查询",
        "发现孤立实体 'logs'，考虑是否需要关联",
        "users 表是核心实体，建议优化其查询性能",
        "检测到可能的循环依赖：orders -> shipments -> orders"
    ]
}
```

## 分析维度

### 1. 实体重要性评估
- **高重要性**：被多个表引用的主实体
- **中重要性**：参与业务流程的事务表
- **低重要性**：辅助查找表

### 2. 关系强度分析
- **强关系**：通过外键约束的关系
- **中等关系**：通过命名约定的隐式关系
- **弱关系**：可能的间接关系

### 3. 聚类算法
- 基于连通性的聚类
- 基于业务领域的聚类
- 基于数据流向的聚类

## 最佳实践

1. **提供完整的外键信息**
   - 确保外键定义准确
   - 包含所有约束信息

2. **使用有意义的表名和字段名**
   - 遵循命名约定
   - 使用描述性名称

3. **适当设置分析深度**
   - 简单数据库：深度 2-3
   - 复杂数据库：深度 4-5
   - 避免过深导致性能问题

4. **关注分析建议**
   - 索引优化建议
   - 关系异常提醒
   - 性能改进建议

## 注意事项

1. 大型数据库可能需要较长分析时间
2. 隐式关系分析基于启发式，可能有误判
3. 循环依赖检测可能影响性能
4. 建议结合人工审核确认关系