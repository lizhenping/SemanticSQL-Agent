# Neo4j 快速查询参考 - 分离展示数据

## 🎯 解决显示混乱问题的核心查询

### 1. 只查看原始数据库表结构（testdb）

```cypher
// 查看testdb的表和列结构，不包含ER分析结果
MATCH (d:Database {name: "testdb"})-[:CONTAINS]->(t:Table)-[:HAS_COLUMN]->(c:Column)
RETURN t.name as 表名,
       t.comment as 表注释,
       collect({
           列名: c.name,
           类型: c.data_type,
           注释: coalesce(c.ai_business_desc, c.comment, ''),
           主键: c.is_primary_key,
           外键: c.is_foreign
       }) as 列信息
ORDER BY t.name
```

### 2. 只查看ER分析结果（testdb）

```cypher
// 查看testdb的ER分析结果，不包含原始表结构
MATCH (bd:BusinessDomain {database_name: "testdb"})-[:CONTAINS]->(er:ERRelation)-[:INVOLVES]->(be:BusinessEntity)
OPTIONAL MATCH (be)-[ha:HAS_ATTRIBUTE]->(c:Column)<-[:HAS_COLUMN]-(t:Table)
RETURN bd.name as 业务域,
       er.relation_name as ER关系,
       be.name as 业务实体,
       be.role as 实体角色,
       collect({
           属性列: c.name,
           来源表: t.name,
           属性类型: ha.attr_type
       }) as 实体属性
ORDER BY bd.created_at DESC, be.name
```

---

## 🔧 数据清理和管理

### 清理testdb的ER分析数据（保留表结构）

```cypher
// 只删除testdb的ER分析，保留原始表结构
MATCH (bd:BusinessDomain {database_name: "testdb"})
OPTIONAL MATCH (bd)-[:CONTAINS]->(er:ERRelation)-[:INVOLVES]->(be:BusinessEntity)
OPTIONAL MATCH (be)-[ha:HAS_ATTRIBUTE]->(c:Column)
DELETE ha, be, er, bd
```

### 查看数据分布情况

```cypher
// 快速查看testdb中有哪些类型的数据
CALL {
    MATCH (d:Database {name: "testdb"})
    RETURN "数据库结构" as 数据类型, count(d) as 数量
    UNION
    MATCH (d:Database {name: "testdb"})-[:CONTAINS]->(t:Table)
    RETURN "数据表" as 数据类型, count(t) as 数量
    UNION  
    MATCH (d:Database {name: "testdb"})-[:CONTAINS]->(t:Table)-[:HAS_COLUMN]->(c:Column)
    RETURN "数据列" as 数据类型, count(c) as 数量
    UNION
    MATCH (bd:BusinessDomain {database_name: "testdb"})
    RETURN "业务域" as 数据类型, count(bd) as 数量
    UNION
    MATCH (bd:BusinessDomain {database_name: "testdb"})-[:CONTAINS]->(er:ERRelation)  
    RETURN "ER关系" as 数据类型, count(er) as 数量
    UNION
    MATCH (bd:BusinessDomain {database_name: "testdb"})-[:CONTAINS]->(er:ERRelation)-[:INVOLVES]->(be:BusinessEntity)
    RETURN "业务实体" as 数据类型, count(be) as 数量
}
RETURN 数据类型, 数量
ORDER BY 数量 DESC
```

---

## 🎨 美化显示格式

### 表格式展示表结构

```cypher
// 以清晰的表格形式显示testdb结构
MATCH (d:Database {name: "testdb"})-[:CONTAINS]->(t:Table)-[:HAS_COLUMN]->(c:Column)
WITH t, 
     count(c) as 列数,
     collect(c.name) as 列名列表,
     sum(CASE WHEN c.is_primary_key THEN 1 ELSE 0 END) as 主键数,
     sum(CASE WHEN c.is_foreign THEN 1 ELSE 0 END) as 外键数
RETURN t.name as 表名,
       coalesce(t.comment, '无注释') as 表说明,
       列数,
       主键数,
       外键数,
       列名列表[0..5] as 前5列  // 只显示前5列避免过长
ORDER BY t.name
```

### 层次结构展示ER分析

```cypher
// 以层次结构显示ER分析结果
MATCH (bd:BusinessDomain {database_name: "testdb"})
OPTIONAL MATCH (bd)-[:CONTAINS]->(er:ERRelation)  
OPTIONAL MATCH (er)-[:INVOLVES]->(be:BusinessEntity)
RETURN bd.name as 业务域,
       bd.description as 域描述,
       collect({
           ER关系: er.relation_name,
           关系说明: er.business_meaning,
           实体列表: [(er)-[:INVOLVES]->(entity) | entity.name],
           实体数量: size([(er)-[:INVOLVES]->(entity) | entity])
       }) as ER关系详情
```

---

## 🚀 一键式查询脚本

### 脚本1：完整展示testdb原始结构

```cypher
// === TESTDB 原始数据库结构 ===
MATCH (d:Database {name: "testdb"})
WITH d
MATCH (d)-[:CONTAINS]->(t:Table)
OPTIONAL MATCH (t)-[:HAS_COLUMN]->(c:Column)
RETURN '=== ' + d.name + ' 数据库结构 ===' as 标题,
       collect({
           表名: t.name,
           表注释: coalesce(t.comment, ''),
           列信息: [(t)-[:HAS_COLUMN]->(col) | {
               列名: col.name,
               类型: col.data_type,
               注释: coalesce(col.ai_business_desc, col.comment, ''),
               主键: coalesce(col.is_primary_key, false),
               外键: coalesce(col.is_foreign, false)
           }]
       }) as 表结构
```

### 脚本2：完整展示testdb的ER分析

```cypher
// === TESTDB ER分析结果 ===  
MATCH (bd:BusinessDomain {database_name: "testdb"})
OPTIONAL MATCH (bd)-[:CONTAINS]->(er:ERRelation)
RETURN '=== ' + bd.name + ' ER分析结果 ===' as 标题,
       bd.description as 业务域描述,
       collect({
           ER关系名: er.relation_name,
           业务含义: er.business_meaning,
           复杂度: er.complexity_level,
           置信度: er.confidence,
           实体详情: [(er)-[:INVOLVES]->(be:BusinessEntity) | {
               实体名: be.name,
               实体说明: be.description,
               实体角色: be.role,
               属性数量: size([(be)-[:HAS_ATTRIBUTE]->() | 1]),
               属性详情: [(be)-[ha:HAS_ATTRIBUTE]->(c:Column)<-[:HAS_COLUMN]-(t:Table) | 
                   t.name + '.' + c.name + ' (' + ha.attr_type + ')']
           }],
           实体关系: [(er)-[:INVOLVES]->(be1:BusinessEntity) | 
               [(be1)-[rel]->(be2:BusinessEntity) WHERE (be2)-[:INVOLVES*0..1]-(er) | 
                   be1.name + ' --[' + type(rel) + ']--> ' + be2.name]]
       }) as ER分析详情
```

---

## 📋 常用清理命令

```cypher
// 1. 只保留表结构，清除所有ER分析
MATCH (bd:BusinessDomain {database_name: "testdb"})
DETACH DELETE bd

// 2. 只保留最新的ER分析（删除旧的）
MATCH (bd:BusinessDomain {database_name: "testdb"})
WITH bd ORDER BY bd.created_at DESC SKIP 1
DETACH DELETE bd

// 3. 查看清理后的状态
MATCH (n)
WHERE n.database_name = "testdb" OR 
      EXISTS((n)<-[:CONTAINS*..3]-(:Database {name: "testdb"}))
RETURN labels(n) as 节点类型, count(n) as 数量
```

---

## 💡 使用建议

1. **分别查询**: 使用上面的脚本1和脚本2分别查看不同类型的数据
2. **定期清理**: 如果ER分析结果过多，定期清理旧的分析结果
3. **数据验证**: 使用统计查询确认数据完整性
4. **性能优化**: 对于大数据量，添加`LIMIT`子句限制返回结果

这样你就可以清晰地分开查看testdb的原始表结构和ER分析结果，避免显示混乱的问题。