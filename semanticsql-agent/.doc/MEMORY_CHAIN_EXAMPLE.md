# Memory Chain 示例

本文档展示SemanticSQL Agent中的记忆链如何工作，确保每个工具都能访问前面步骤的结果。

## 执行流程和记忆传递

### 1. Schema Extraction (第一步)
```python
# 工具：SchemaExtractionTool
# 输入：database_name
# 输出保存到：memory["schema_info"]

结果示例：
{
    "database_name": "ecommerce_db",
    "tables": {
        "users": {
            "columns": {
                "id": {"type": "int", "nullable": false},
                "name": {"type": "varchar(100)", "nullable": false},
                "email": {"type": "varchar(200)", "nullable": false}
            },
            "primary_key": ["id"],
            "row_count": 10000
        },
        "orders": {
            "columns": {
                "id": {"type": "int", "nullable": false},
                "user_id": {"type": "int", "nullable": false},
                "total_amount": {"type": "decimal(10,2)", "nullable": false}
            },
            "primary_key": ["id"]
        }
    }
}
```

### 2. Domain Analysis (使用schema_info)
```python
# 工具：DomainAnalysisTool
# 输入：自动从memory获取schema_info
# 输出保存到：memory["domain_info"]

# 工具内部使用schema_info：
- 格式化数据库DDL
- 收集字段统计（类型分布、模式统计）
- 基于表结构识别业务领域

结果示例：
{
    "domain_type": "电商",
    "domain_description": "电商平台核心业务数据库",
    "key_entities": ["用户", "订单", "商品"],
    "business_rules": ["用户可以创建多个订单", "每个订单关联一个用户"]
}
```

### 3. Field Classification (使用schema_info + domain_info)
```python
# 工具：FieldClassificationTool
# 输入：自动从memory获取schema_info和domain_info
# 输出保存到：memory["field_classification"]

# 工具内部使用记忆：
- 使用schema_info获取所有字段信息
- 使用domain_info理解业务背景，更准确分类

结果示例：
{
    "field_classifications": {
        "users": {
            "id": {"category": "identifier", "field_type": "主键", "importance": "high"},
            "name": {"category": "text", "field_type": "姓名", "importance": "high"},
            "email": {"category": "text", "field_type": "联系方式", "importance": "high"}
        },
        "orders": {
            "id": {"category": "identifier", "field_type": "主键", "importance": "high"},
            "user_id": {"category": "identifier", "field_type": "外键", "importance": "high"},
            "total_amount": {"category": "measure", "field_type": "金额", "importance": "high"}
        }
    }
}
```

### 4. Column Meaning (使用所有前面的记忆)
```python
# 工具：ColumnMeaningTool
# 输入：自动从memory获取schema_info, domain_info, field_classification
# 输出保存到：memory["column_meanings"]

# 工具内部使用记忆：
- 使用schema_info获取表结构和样本数据
- 使用domain_info理解业务上下文
- 使用field_classification理解字段类型和重要性
- 综合以上信息生成准确的业务描述

结果示例：
{
    "column_descriptions": {
        "users.id": "用户唯一标识符，系统自动生成",
        "users.name": "用户真实姓名，用于订单配送",
        "users.email": "用户邮箱地址，用于登录和接收通知",
        "orders.id": "订单唯一编号",
        "orders.user_id": "下单用户ID，关联到users表",
        "orders.total_amount": "订单总金额，包含商品价格和运费"
    }
}
```

### 5. Table Meaning (使用所有前面的记忆)
```python
# 工具：TableMeaningTool
# 输入：自动从memory获取schema_info, domain_info, column_meanings
# 输出保存到：memory["table_meanings"]

# 工具内部使用记忆：
- 使用schema_info了解表结构
- 使用domain_info理解业务领域
- 使用column_meanings理解表中各列的业务含义
- 综合分析表的整体业务职责

结果示例：
{
    "table_descriptions": {
        "users": "存储平台注册用户的基本信息，是系统的核心主数据",
        "orders": "记录用户的订单信息，包含订单金额等交易数据"
    }
}
```

### 6. ER Analysis (使用所有记忆)
```python
# 工具：ERAnalysisTool
# 输入：自动从memory获取所有前面的分析结果
# 输出保存到：memory["er_relations"]

# 工具内部使用记忆：
- 使用schema_info分析物理外键
- 使用column_meanings和table_meanings理解业务含义
- 基于业务理解推断逻辑关系和概念关系

结果示例：
{
    "physical_relations": [
        {
            "from_table": "orders",
            "from_column": "user_id",
            "to_table": "users",
            "to_column": "id",
            "relationship_type": "foreign_key"
        }
    ],
    "logical_relations": [
        {
            "from": "orders.user_id",
            "to": "users.id",
            "type": "many-to-one",
            "reason": "每个订单属于一个用户，用户可以有多个订单"
        }
    ],
    "conceptual_relations": [
        {
            "entity1": "用户",
            "entity2": "订单",
            "relationship": "用户创建订单",
            "type": "contains",
            "business_rule": "用户是订单的创建者和所有者"
        }
    ]
}
```

## Memory Chain的优势

1. **避免重复分析**：每个步骤的结果都保存在memory中，后续步骤直接使用
2. **累积理解**：每个工具都基于前面的分析结果，理解越来越深入
3. **上下文一致**：所有工具共享同一个memory，确保分析的一致性
4. **智能决策**：LLM可以基于完整的上下文做出更准确的判断

## 在Agent中的使用

```python
# Agent会自动管理memory
agent = SQLAgent(settings, db_config)

# 执行数据库分析时，Agent会：
# 1. 创建DatabaseAnalysisMemory实例
# 2. 将memory传递给每个工具
# 3. 按顺序执行工具，每个工具自动使用前面的结果

result = agent.analyze_database("ecommerce_db")
# 此时memory中已包含完整的分析结果链
```