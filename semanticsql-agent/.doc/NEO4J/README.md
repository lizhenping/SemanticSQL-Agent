# Neo4j 数据查询和管理指南

## 🎯 快速解决"显示混乱"问题

你的Neo4j数据库中现在有两种类型的数据：
1. **原始数据库结构**：Database → Table → Column 
2. **ER分析结果**：BusinessDomain → ERRelation → BusinessEntity → Column

---

## 🚀 立即可用的解决方案

### 方案1：只看testdb的原始表结构

在Neo4j Browser中执行：

```cypher
MATCH (d:Database {name: "testdb"})-[:CONTAINS]->(t:Table)-[:HAS_COLUMN]->(c:Column)
RETURN t.name as 表名,
       collect(c.name) as 列名
ORDER BY t.name
```

### 方案2：只看testdb的ER分析结果

```cypher
MATCH (bd:BusinessDomain {database_name: "testdb"})-[:CONTAINS]->(er:ERRelation)-[:INVOLVES]->(be:BusinessEntity)
RETURN bd.name as 业务域,
       er.relation_name as ER关系,
       be.name as 业务实体
ORDER BY bd.created_at DESC
```

### 方案3：查看数据分布（了解有什么数据）

```cypher
CALL {
    MATCH (d:Database {name: "testdb"})-[:CONTAINS]->(t:Table)
    RETURN "原始表结构" as 类型, count(t) as 数量
    UNION
    MATCH (bd:BusinessDomain {database_name: "testdb"})-[:CONTAINS]->(er:ERRelation)
    RETURN "ER分析结果" as 类型, count(er) as 数量
}
RETURN 类型, 数量
```

---

## 🧹 数据清理（如果需要）

### 只清理ER分析，保留原始表结构
```cypher
MATCH (bd:BusinessDomain {database_name: "testdb"})
DETACH DELETE bd
```

### 查看清理效果
```cypher
MATCH (n)
WHERE labels(n)[0] IN ["Database", "Table", "Column", "BusinessDomain", "ERRelation", "BusinessEntity"]
RETURN labels(n)[0] as 节点类型, count(n) as 数量
ORDER BY 数量 DESC
```

---

## 📚 详细文档

1. **neo4j_data_management.md** - 完整的操作指南和命令参考
2. **quick_reference_queries.md** - 常用查询的快速参考

---

## 🔗 Neo4j Browser 访问

通常可以通过以下方式访问Neo4j Browser：
- 本地安装：`http://localhost:7474`
- 或查看你的Neo4j配置中的连接信息

在Browser中直接粘贴上述查询语句即可执行。

---

## ⚡ 最常用的3个命令

```cypher
// 1. 看表结构
MATCH (d:Database {name: "testdb"})-[:CONTAINS]->(t:Table)
RETURN t.name, t.comment
ORDER BY t.name

// 2. 看ER分析  
MATCH (bd:BusinessDomain {database_name: "testdb"})
RETURN bd.name, bd.description, bd.created_at
ORDER BY bd.created_at DESC

// 3. 清理ER分析
MATCH (bd:BusinessDomain {database_name: "testdb"})
DETACH DELETE bd
```

现在你可以清晰地分开查看不同类型的数据了！