# Schema Extraction Tool 设计文档

## 1. 工具定位与职责

### 1.1 核心职责
- **纯元数据提取**：从MySQL数据库提取基础结构信息
- **Neo4j存储**：将元数据以图结构存储到Neo4j
- **阶段分离**：专注当前阶段，为后续工具提供基础数据

### 1.2 设计原则
- **极简操作**：只处理数据库中实际存在的信息
- **配置灵活**：支持表过滤和comment使用配置
- **无过度工程**：不进行性能优化，直接简单操作

## 2. Neo4j图结构设计

### 2.1 核心节点类型（3种）

#### Database节点
```cypher
CREATE (d:Database {
    name: "数据库名称",
    business_desc: "业务描述"  // 根据配置使用comment或后续填充
})
```

#### Table节点  
```cypher
CREATE (t:Table {
    name: "表名",
    row_count: null,           // 🔖 后续阶段填充
    business_desc: "业务描述"   // 根据配置使用comment或后续填充
})
```

#### Column节点
```cypher
CREATE (c:Column {
    name: "列名",              // ✅ 当前阶段：从MySQL获取
    data_type: "数据类型",      // ✅ 当前阶段：从MySQL获取
    is_nullable: true,         // ✅ 当前阶段：从MySQL获取
    is_primary: false,         // ✅ 当前阶段：从MySQL获取
    is_foreign: null,          // 🔖 后续阶段填充
    category: null,            // 🔖 后续阶段填充 (identifier/measure/dimension/datetime)
    entropy_level: null,       // 🔖 后续阶段填充 (low/medium/high)
    sample_values: [],         // 🔖 后续阶段填充 (采样数据)
    business_desc: "业务描述"   // 根据配置使用comment或后续填充
})
```

### 2.2 核心关系类型（2种）

#### CONTAINS关系
```cypher
(Database)-[:CONTAINS]->(Table)
```

#### HAS_COLUMN关系
```cypher
(Table)-[:HAS_COLUMN]->(Column)
```

## 3. 配置参数设计

### 3.1 工具配置接口
```python
{
    "table_blacklist": [        // 表黑名单
        "temp_",                // 过滤表名包含"temp_"的表
        "log_",                 // 过滤表名包含"log_"的表  
        "backup_",              // 过滤表名包含"backup_"的表
        "sys_",                 // 可自定义其他过滤规则
    ],
    "use_db_comments": true     // 是否使用数据库comment作为business_desc
}
```

### 3.2 配置说明
- **table_blacklist**: 支持前缀匹配过滤，包含指定字符串的表将被跳过
- **use_db_comments**: 
  - `true`: 使用数据库、表、列的comment作为business_desc
  - `false`: business_desc字段留空，标记为后续阶段填充

## 4. MySQL数据提取规范

### 4.1 当前阶段直接获取的字段

#### 数据库级别
```sql
SELECT 
    SCHEMA_NAME as database_name,
    SCHEMA_COMMENT as database_comment    -- 可选用作business_desc
FROM INFORMATION_SCHEMA.SCHEMATA 
WHERE SCHEMA_NAME = '目标数据库名'
```

#### 表级别
```sql
SELECT 
    TABLE_NAME as table_name,
    TABLE_COMMENT as table_comment        -- 可选用作business_desc
FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_SCHEMA = '目标数据库名'
```

#### 列级别
```sql
SELECT 
    COLUMN_NAME as column_name,           -- ✅ 直接获取
    DATA_TYPE as data_type,               -- ✅ 直接获取
    IS_NULLABLE as is_nullable,           -- ✅ 直接获取
    COLUMN_KEY as column_key,             -- ✅ 用于判断is_primary
    COLUMN_COMMENT as column_comment      -- 可选用作business_desc
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_SCHEMA = '目标数据库名' 
  AND TABLE_NAME = '目标表名'
```

### 4.2 字段映射逻辑
- `is_primary`: 从`COLUMN_KEY = 'PRI'`判断
- `is_nullable`: 从`IS_NULLABLE = 'YES'`判断
- `business_desc`: 根据`use_db_comments`配置决定是否使用comment

## 5. 后续阶段填充字段标记

### 5.1 🔖 标记：后续阶段填充的字段

#### Database节点
- `business_desc`（当use_db_comments=false时）

#### Table节点  
- `row_count`: 需要执行`SELECT COUNT(*) FROM table_name`统计
- `business_desc`（当use_db_comments=false时）

#### Column节点
- `is_foreign`: 需要分析外键关系
- `category`: 需要AI推理字段类型分类
- `entropy_level`: 需要数据分析计算多样性
- `sample_values`: 需要执行`SELECT DISTINCT column_name LIMIT 100`采样
- `business_desc`（当use_db_comments=false时）

### 5.2 填充时机
- **domain_analysis阶段**: 填充business_desc（如果启用LLM推理）
- **data_analysis阶段**: 填充row_count、sample_values、entropy_level
- **er_analysis阶段**: 填充is_foreign和关系信息
- **field_analysis阶段**: 填充category分类

## 6. Neo4j查询接口

### 6.1 获取完整元数据结构
```cypher
MATCH (db:Database)-[:CONTAINS]->(t:Table)-[:HAS_COLUMN]->(c:Column)
WHERE db.name = $database_name
RETURN db.name as database_name,
       collect(DISTINCT {
           table_name: t.name,
           business_desc: t.business_desc,
           row_count: t.row_count,
           columns: collect({
               name: c.name,
               data_type: c.data_type,
               is_nullable: c.is_nullable,
               is_primary: c.is_primary,
               is_foreign: c.is_foreign,
               business_desc: c.business_desc
           })
       }) as tables
```

### 6.2 查找主键列
```cypher
MATCH (t:Table)-[:HAS_COLUMN]->(c:Column)
WHERE c.is_primary = true
RETURN t.name as table_name, c.name as primary_key
```

### 6.3 获取表基础信息
```cypher
MATCH (db:Database)-[:CONTAINS]->(t:Table)
WHERE db.name = $database_name
RETURN t.name as table_name, 
       t.business_desc as description,
       t.row_count as row_count
```

## 7. 工具返回格式

### 7.1 成功返回
```
✅ 数据库结构提取完成，已存储到Neo4j。请继续执行domain_analysis工具。
```

### 7.2 配置示例返回
```
✅ 数据库结构提取完成：
- 数据库: testdb
- 提取表数: 8个（过滤了3个黑名单表）
- 提取列数: 156个
- 使用数据库comment: 是
已存储到Neo4j，请继续执行domain_analysis工具。
```

## 8. 实现要点

### 8.1 核心特点
1. **无LLM推理**: 当前阶段不进行任何AI分析
2. **无性能优化**: 简单直接的操作，无批量处理
3. **配置驱动**: 通过配置控制行为，不写死逻辑
4. **阶段清晰**: 明确区分当前阶段和后续阶段的职责

### 8.2 错误处理
- 数据库连接失败: 返回连接错误信息
- 表黑名单过滤: 记录过滤的表数量
- Neo4j存储失败: 返回存储错误信息

### 8.3 扩展性考虑
- 配置参数可扩展: 后续可添加更多过滤规则
- 字段预留: 为后续阶段预留必要字段
- 关系扩展: 当前关系结构支持后续ER关系的建立

---

**总结**: 本工具专注于纯元数据的提取和存储，为整个SemanticSQL工具链提供干净、结构化的基础数据。通过配置灵活性和阶段清晰划分，确保每个阶段的职责单一且明确。