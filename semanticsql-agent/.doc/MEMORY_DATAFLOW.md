# Memory数据流详解

本文档详细说明SemanticSQL Agent中每个分析工具如何使用前面步骤的记忆数据。

## 1. Schema Extraction Tool
**输入**: 
- `database_name`: 数据库名称

**输出到memory["schema_info"]**:
```json
{
    "database_name": "db_name",
    "tables": {
        "table_name": {
            "columns": {
                "col_name": {
                    "type": "varchar(50)",
                    "nullable": true,
                    "is_primary": false,
                    "comment": "列注释"
                }
            },
            "primary_key": ["id"],
            "foreign_keys": [...],
            "indexes": [...],
            "row_count": 1000,
            "comment": "表注释"
        }
    },
    "total_tables": 10,
    "total_columns": 50
}
```

## 2. Domain Analysis Tool
**从memory获取**:
- `schema_info`: 完整的数据库结构信息

**使用方式**:
1. 从schema_info生成DDL语句
2. 统计字段类型分布和模式（时间字段、ID字段、金额字段等）
3. 将DDL和统计信息传入LLM进行领域分析

**LLM输入包含**:
- `database_ddl`: 格式化的DDL语句
- `type_distribution`: 字段类型统计
- `field_patterns`: 字段模式统计（时间、ID、金额等）
- `pattern_examples`: 每种模式的示例字段

**输出到memory["domain_info"]**:
```json
{
    "domain_type": "电商",
    "domain_description": "电商平台核心业务数据库...",
    "key_entities": ["用户", "商品", "订单", "支付"],
    "business_characteristics": [
        "包含完整的用户购买流程",
        "支持多种支付方式"
    ],
    "business_rules": [
        "每个订单必须关联用户",
        "订单金额必须大于0"
    ]
}
```

## 3. Field Classification Tool
**从memory获取**:
- `schema_info`: 获取所有字段信息
- `domain_info`: 理解业务背景，辅助分类

**使用方式**:
1. 遍历所有表的所有字段
2. 如果有db_manager，计算字段熵值
3. 批量调用LLM进行分类

**LLM输入包含**:
- `fields`: 字段列表（包含字段名、类型、样本数据、熵值）
- `domain_type`: 业务领域类型
- `domain_description`: 业务领域描述

**输出到memory["field_classification"]**:
```json
{
    "field_classifications": {
        "users": {
            "id": {
                "category": "identifier",
                "field_type": "主键",
                "importance": "high"
            },
            "created_at": {
                "category": "temporal",
                "field_type": "创建时间",
                "importance": "medium"
            }
        }
    }
}
```

## 4. Column Meaning Tool
**从memory获取**:
- `schema_info`: 表结构和DDL
- `domain_info`: 业务背景
- `field_classification`: 字段分类信息

**使用方式**:
1. 按表批量处理列
2. 为每个列准备包含分类信息的数据
3. 调用LLM生成业务描述

**LLM输入包含**:
- `table_ddl`: 表的DDL
- `columns`: 列信息列表，每个包含：
  - `name`: 列名
  - `examples`: 样本数据
  - `classification`: 来自field_classification的分类信息
- `domain_type`: 业务领域
- `domain_description`: 业务描述
- `key_entities`: 关键实体
- `business_characteristics`: 业务特征

**输出到memory["column_meanings"]**:
```json
{
    "column_descriptions": {
        "users.id": "用户唯一标识符，系统自动生成的主键",
        "users.email": "用户邮箱地址，用于登录和接收通知",
        "orders.total_amount": "订单总金额，包含商品价格、税费和运费"
    }
}
```

## 5. Table Meaning Tool
**从memory获取**:
- `schema_info`: 表结构信息
- `domain_info`: 业务背景
- `column_meanings`: 所有列的业务描述

**使用方式**:
1. 为每个表收集其所有列的描述
2. 结合领域信息理解表的整体职责
3. 批量调用LLM生成表描述

**LLM输入包含**:
- `tables`: 表信息列表，每个包含：
  - `name`: 表名
  - `columns`: 列信息（包含列描述）
  - `row_count`: 行数
  - `comment`: 表注释
- `domain_type`: 业务领域
- `domain_description`: 业务描述

**输出到memory["table_meanings"]**:
```json
{
    "table_descriptions": {
        "users": "存储平台注册用户的基本信息和认证数据，是系统的核心主数据",
        "orders": "记录用户的订单信息，包含订单状态、金额、时间等交易核心数据",
        "order_items": "订单明细表，记录每个订单包含的商品项、数量和价格"
    }
}
```

## 6. ER Analysis Tool
**从memory获取**:
- `schema_info`: 物理外键信息
- `column_meanings`: 列的业务含义
- `table_meanings`: 表的业务职责

**使用方式**:
1. 分析物理外键关系
2. 基于列名和业务含义推断逻辑关系
3. 基于表职责推断概念关系

**LLM输入包含**:
- **逻辑关系分析**:
  - `formatted_schema`: 包含列描述和表描述的schema
  - `foreign_keys`: 物理外键信息
- **概念关系分析**:
  - `formatted_schema`: 完整的业务化schema
  - `physical_relations`: 物理关系
  - `logical_relations`: 逻辑关系

**输出到memory["er_relations"]**:
```json
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
            "from": "order_items.product_id",
            "to": "products.id",
            "type": "many-to-one",
            "reason": "订单项引用商品信息"
        }
    ],
    "conceptual_relations": [
        {
            "entity1": "用户",
            "entity2": "订单",
            "relationship": "用户创建订单",
            "type": "one-to-many",
            "business_rule": "一个用户可以创建多个订单"
        }
    ]
}
```

## 关键设计原则

1. **累积理解**: 每个工具都基于前面所有工具的分析结果
2. **上下文传递**: LLM调用时包含所有相关的前置分析
3. **结构化输出**: 所有工具返回结构化的字典，方便后续使用
4. **业务语义**: 从技术信息逐步提升到业务语义理解

## Memory使用最佳实践

1. **获取数据时使用专门方法**:
   ```python
   schema_info = self.get_schema_info()
   domain_info = self.get_domain_info()
   ```

2. **保存数据时指定工具名**:
   ```python
   self.save_to_memory("tool_name", result_dict)
   ```

3. **LLM调用时传递完整上下文**:
   ```python
   prompt_data = {
       'current_step_data': ...,
       'previous_analysis': {
           'domain': domain_info,
           'classifications': field_classification,
           ...
       }
   }
   ```