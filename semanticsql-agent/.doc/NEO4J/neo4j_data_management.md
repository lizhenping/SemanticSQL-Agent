# Neo4j 数据管理操作指南

## 概述

SemanticSQL Agent 在 Neo4j 中存储两种不同类型的数据结构：
1. **数据库结构数据**：Database → Table → Column 的物理数据库结构
2. **ER分析数据**：BusinessDomain → ERRelation → BusinessEntity → Column 的业务概念模型

本文档提供分离查询、管理和清理这些不同数据类型的具体操作命令。

---

## 数据结构类型

### 1. 数据库结构数据（原始表列关系）
```
Database (数据库)
├── Table (表)
│   ├── Column (列)
│   └── Column (列)
└── Table (表)
    ├── Column (列)
    └── Column (列)
```

**节点标签**：`Database`, `Table`, `Column`  
**关系类型**：`CONTAINS` (Database→Table), `HAS_COLUMN` (Table→Column)

### 2. ER分析数据（业务概念模型）
```
BusinessDomain (业务域)
└── ERRelation (ER关系)
    ├── BusinessEntity (业务实体)
    │   ├── HAS_ATTRIBUTE → Column
    │   └── HAS_ATTRIBUTE → Column
    ├── BusinessEntity (业务实体)
    └── [实体间关系: ONE_TO_MANY, etc.]
```

**节点标签**：`BusinessDomain`, `ERRelation`, `BusinessEntity`  
**关系类型**：`CONTAINS` (BusinessDomain→ERRelation), `INVOLVES` (ERRelation→BusinessEntity), `HAS_ATTRIBUTE` (BusinessEntity→Column)

---

## 查询操作命令

### 🗃️ 查看数据库结构数据

#### 1. 查看所有数据库和表
```cypher
// 查看数据库概览
MATCH (d:Database)-[:CONTAINS]->(t:Table)
RETURN d.name as database_name, 
       collect(t.name) as tables,
       count(t) as table_count
ORDER BY database_name
```

#### 2. 查看指定数据库的详细表结构
```cypher
// 查看 testdb 的完整表结构
MATCH (d:Database {name: "testdb"})-[:CONTAINS]->(t:Table)-[:HAS_COLUMN]->(c:Column)
RETURN t.name as table_name,
       t.comment as table_comment,
       collect({
           name: c.name,
           type: c.data_type,
           comment: coalesce(c.ai_business_desc, c.business_desc, c.comment, ''),
           is_primary: c.is_primary_key,
           is_foreign: c.is_foreign
       }) as columns
ORDER BY table_name
```

#### 3. 查看表间关系（基于外键推断）
```cypher
// 查看可能的表间关系
MATCH (d:Database {name: "testdb"})-[:CONTAINS]->(t:Table)-[:HAS_COLUMN]->(c:Column)
WHERE c.is_foreign = true OR c.name ENDS WITH '_id'
RETURN t.name as table_name, 
       c.name as column_name,
       c.data_type as column_type,
       '可能的外键关系' as note
ORDER BY table_name, column_name
```

### 🏢 查看ER分析数据

#### 1. 查看所有业务域概览
```cypher
// 查看所有业务域和ER关系
MATCH (bd:BusinessDomain)-[:CONTAINS]->(er:ERRelation)
OPTIONAL MATCH (er)-[:INVOLVES]->(be:BusinessEntity)
RETURN bd.name as business_domain,
       bd.description as domain_desc,
       er.relation_name as er_relation,
       er.business_meaning as relation_meaning,
       count(be) as entity_count,
       bd.created_at as created_time
ORDER BY bd.created_at DESC
```

#### 2. 查看指定数据库的ER分析详情
```cypher
// 查看 testdb 相关的ER分析
MATCH (bd:BusinessDomain {database_name: "testdb"})-[:CONTAINS]->(er:ERRelation)-[:INVOLVES]->(be:BusinessEntity)
OPTIONAL MATCH (be)-[ha:HAS_ATTRIBUTE]->(c:Column)<-[:HAS_COLUMN]-(t:Table)
RETURN bd.name as business_domain,
       er.relation_name as er_relation,
       be.name as entity_name,
       be.description as entity_desc,
       be.role as entity_role,
       collect({
           column: c.name,
           table: t.name,
           attr_type: ha.attr_type,
           description: ha.description
       }) as attributes
ORDER BY bd.created_at DESC, be.name
```

#### 3. 查看实体间关系
```cypher
// 查看业务实体间的关系
MATCH (bd:BusinessDomain {database_name: "testdb"})-[:CONTAINS]->(er:ERRelation)
MATCH (be1:BusinessEntity)-[rel]->(be2:BusinessEntity)
WHERE (be1)-[:INVOLVES*0..1]-(er) AND (be2)-[:INVOLVES*0..1]-(er)
RETURN be1.name as from_entity,
       be2.name as to_entity,
       type(rel) as relation_type,
       rel.business_meaning as meaning
```

---

## 数据管理操作

### 🧹 清理操作

#### 1. 清理指定数据库的ER分析数据
```cypher
// 删除 testdb 的所有ER分析数据
MATCH (bd:BusinessDomain {database_name: "testdb"})
OPTIONAL MATCH (bd)-[:CONTAINS]->(er:ERRelation)
OPTIONAL MATCH (er)-[:INVOLVES]->(be:BusinessEntity)
OPTIONAL MATCH (be)-[ha:HAS_ATTRIBUTE]->(c:Column)
DELETE ha, be, er, bd
```

#### 2. 清理所有ER分析数据（保留数据库结构）
```cypher
// 只删除ER分析相关数据，保留Database-Table-Column结构
MATCH (bd:BusinessDomain)
OPTIONAL MATCH (bd)-[:CONTAINS]->(er:ERRelation)
OPTIONAL MATCH (er)-[:INVOLVES]->(be:BusinessEntity)
OPTIONAL MATCH (be)-[ha:HAS_ATTRIBUTE]->(c:Column)
DELETE ha, be, er, bd
```

#### 3. 清理指定数据库的所有数据
```cypher
// 彻底删除testdb的所有数据（包括数据库结构和ER分析）
MATCH (d:Database {name: "testdb"})
OPTIONAL MATCH (d)-[:CONTAINS]->(t:Table)-[:HAS_COLUMN]->(c:Column)
OPTIONAL MATCH (bd:BusinessDomain {database_name: "testdb"})
OPTIONAL MATCH (bd)-[:CONTAINS]->(er:ERRelation)-[:INVOLVES]->(be:BusinessEntity)
OPTIONAL MATCH (be)-[ha:HAS_ATTRIBUTE]->(col:Column)
DELETE d, t, c, bd, er, be, ha
```

### 📊 统计操作

#### 1. 数据库结构统计
```cypher
// 统计数据库结构数据量
MATCH (d:Database)
OPTIONAL MATCH (d)-[:CONTAINS]->(t:Table)
OPTIONAL MATCH (t)-[:HAS_COLUMN]->(c:Column)
RETURN d.name as database,
       count(DISTINCT t) as tables,
       count(c) as columns
ORDER BY database
```

#### 2. ER分析数据统计
```cypher
// 统计ER分析数据量
MATCH (bd:BusinessDomain)
OPTIONAL MATCH (bd)-[:CONTAINS]->(er:ERRelation)
OPTIONAL MATCH (er)-[:INVOLVES]->(be:BusinessEntity)
OPTIONAL MATCH (be)-[ha:HAS_ATTRIBUTE]->(c:Column)
RETURN bd.database_name as database,
       bd.name as business_domain,
       count(DISTINCT er) as er_relations,
       count(DISTINCT be) as business_entities,
       count(ha) as attribute_mappings
ORDER BY bd.created_at DESC
```

---

## 数据分离查看

### 方案1：分别查询不同类型数据

#### 只看数据库结构（不含ER分析）
```cypher
// 纯数据库结构视图
MATCH (d:Database {name: "testdb"})-[:CONTAINS]->(t:Table)-[:HAS_COLUMN]->(c:Column)
RETURN '数据库结构' as data_type,
       t.name as table_name,
       collect(c.name) as columns
ORDER BY table_name
```

#### 展示 ER分析结果
```cypher
MATCH (bd:BusinessDomain {database_name: "testdb"})-[r1:CONTAINS]->(er:ERRelation)-[r2:INVOLVES]->(be:BusinessEntity)
RETURN bd, r1, er, r2, be
ORDER BY bd.created_at DESC, be.name 
```

#### 只看ER分析结果（不含原始结构）
```cypher
// 纯ER分析视图  
MATCH (bd:BusinessDomain {database_name: "testdb"})-[:CONTAINS]->(er:ERRelation)-[:INVOLVES]->(be:BusinessEntity)
RETURN 'ER分析结果' as data_type,
       bd.name as business_domain,
       er.relation_name as er_relation,
       be.name as business_entity,
       be.role as entity_role
ORDER BY bd.created_at DESC, be.name
```

#### 只看ER分析结果（包含表列结构）
```cypher
MATCH (bd:BusinessDomain {database_name: "testdb"})-[r1:CONTAINS]->(er:ERRelation)-[r2:INVOLVES]->(be:BusinessEntity)-[r3:HAS_ATTRIBUTE]->(c:Column)<-[r4:HAS_COLUMN]-(t:Table)
RETURN bd, r1, er, r2, be, r3, c, r4, t
ORDER BY be.name, t.name, c.name
```

### 方案2：使用标签过滤

#### 查看所有节点类型
```cypher
// 查看数据库中所有节点类型
CALL db.labels() YIELD label
RETURN label
ORDER BY label
```

#### 按标签分类展示数据
```cypher
// 分类展示节点数量
MATCH (n)
WHERE n.database_name = "testdb" OR EXISTS((n)<-[:CONTAINS*..3]-(:Database {name: "testdb"}))
RETURN labels(n) as node_types, count(n) as count
ORDER BY count DESC
```

---

## 实用查询脚本

### 🔍 快速诊断

#### 检查数据一致性
```cypher
// 检查是否有孤立的列（没有对应表的列）
MATCH (c:Column)
WHERE NOT EXISTS((c)<-[:HAS_COLUMN]-(:Table))
RETURN count(c) as orphaned_columns
```

#### 检查ER分析覆盖率
```cypher
// 检查哪些表还没有ER分析覆盖
MATCH (d:Database {name: "testdb"})-[:CONTAINS]->(t:Table)
OPTIONAL MATCH (bd:BusinessDomain {database_name: "testdb"})-[:CONTAINS]->(er:ERRelation)-[:INVOLVES]->(be:BusinessEntity)-[:HAS_ATTRIBUTE]->(c:Column)<-[:HAS_COLUMN]-(t)
RETURN t.name as table_name,
       CASE WHEN be IS NULL THEN '未分析' ELSE '已分析' END as er_status
ORDER BY er_status, table_name
```

### 🎯 特定查询

#### 查找特定实体的所有属性
```cypher
// 查找Customer实体的所有属性
MATCH (be:BusinessEntity {name: "Customer"})-[ha:HAS_ATTRIBUTE]->(c:Column)<-[:HAS_COLUMN]-(t:Table)
RETURN be.name as entity,
       t.name as table_name,
       c.name as column_name,
       ha.attr_type as attribute_type,
       ha.description as description
```

#### 查找跨表的业务实体
```cypher
// 查找属性分布在多个表中的业务实体
MATCH (be:BusinessEntity)-[:HAS_ATTRIBUTE]->(c:Column)<-[:HAS_COLUMN]-(t:Table)
WITH be, collect(DISTINCT t.name) as tables
WHERE size(tables) > 1
RETURN be.name as entity_name,
       be.description as entity_desc,
       tables as spanning_tables,
       size(tables) as table_count
ORDER BY table_count DESC
```

---

## 维护建议

### 定期清理
1. 定期清理过期的ER分析数据
2. 保持数据库结构数据为单一真实来源
3. 避免重复的ER分析结果

### 数据隔离
1. ER分析数据使用独立的节点标签
2. 通过`database_name`属性关联而非直接图关系
3. 定期检查数据一致性

### 性能优化
1. 在常用查询字段上创建索引：
```cypher
CREATE INDEX ON :Database(name)
CREATE INDEX ON :BusinessDomain(database_name)  
CREATE INDEX ON :BusinessDomain(analysis_id)
```

---

## 常用命令速查

| 功能 | 命令 |
|------|------|
| 查看testdb表结构 | `MATCH (d:Database {name: "testdb"})-[:CONTAINS]->(t:Table) RETURN t.name, t.comment` |
| 查看testdb的ER分析 | `MATCH (bd:BusinessDomain {database_name: "testdb"}) RETURN bd.name, bd.description` |
| 清理testdb的ER分析 | `MATCH (bd:BusinessDomain {database_name: "testdb"}) DETACH DELETE bd` |
| 统计数据量 | `MATCH (n) RETURN labels(n), count(n)` |

使用这些命令可以清晰地分离和管理不同类型的数据，避免显示混乱的问题。


显示问题

MATCH (q:Question) 
WHERE q.database_name = "" 
  AND q.has_sql = false 
RETURN q 
ORDER BY q.created_at 
LIMIT 10