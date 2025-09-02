# 工具调用示例 - 数据库分析流程

本文档演示了智能体之间正确的工具调用格式。

## 步骤1: schema_extraction

**调用格式**：
```json
{
  "tool": "schema_extraction",
  "arguments": {
    "database_name": "testdb"
  }
}
```

**返回结果**：
```json
{
  "database_name": "testdb",
  "tables": {
    "users": {
      "columns": [...],
      "primary_keys": [...],
      "foreign_keys": [...]
    }
  },
  "table_count": 5
}
```

## 步骤2: domain_analysis

**调用格式**：
```json
{
  "tool": "domain_analysis",
  "arguments": {
    "memory": {
      "schema_info": {
        "database_name": "testdb",
        "tables": {...},
        "table_count": 5
      }
    }
  }
}
```

**返回结果**：
```json
{
  "primary_domain": "电商",
  "sub_domains": ["用户管理", "订单管理"],
  "business_entities": {...},
  "business_processes": [...],
  "domain_confidence": 0.85
}
```

## 步骤3: field_classification

**调用格式**：
```json
{
  "tool": "field_classification", 
  "arguments": {
    "memory": {
      "schema_info": {<步骤1的结果>},
      "domain_info": {<步骤2的结果>}
    }
  }
}
```

**返回结果**：
```json
{
  "field_classifications": {...},
  "classification_summary": {...},
  "insights": [...],
  "total_fields": 45
}
```

## 步骤4: column_meaning_analysis

**调用格式**：
```json
{
  "tool": "column_meaning_analysis",
  "arguments": {
    "memory": {
      "schema_info": {<步骤1的结果>},
      "domain_info": {<步骤2的结果>},
      "field_classification": {<步骤3的结果>}
    }
  }
}
```

**返回结果**：
```json
{
  "column_meanings": {...},
  "business_terms": {...},
  "data_patterns": {...},
  "analysis_summary": {...}
}
```

## 步骤5: table_meaning_analysis

**调用格式**：
```json
{
  "tool": "table_meaning_analysis",
  "arguments": {
    "memory": {
      "schema_info": {<步骤1的结果>},
      "domain_info": {<步骤2的结果>},
      "field_classification": {<步骤3的结果>},
      "column_meanings": {<步骤4的结果>}
    }
  }
}
```

**返回结果**：
```json
{
  "table_purposes": {...},
  "table_relationships": {...},
  "business_entities": {...},
  "entity_hierarchy": {...}
}
```

## 步骤6: er_analysis

**调用格式**：
```json
{
  "tool": "er_analysis",
  "arguments": {
    "memory": {
      "schema_info": {<步骤1的结果>},
      "domain_info": {<步骤2的结果>},
      "field_classification": {<步骤3的结果>},
      "column_meanings": {<步骤4的结果>},
      "table_meanings": {<步骤5的结果>}
    }
  }
}
```

**返回结果**：
```json
{
  "relationships": {...},
  "explicit_count": 8,
  "implicit_count": 3,
  "total_relations": 11,
  "relationship_patterns": {...},
  "insights": [...]
}
```

## 重要说明

1. **数据累积**：每个步骤都需要包含之前所有步骤的结果
2. **键名一致性**：memory中的键名必须与callbacks中的映射一致：
   - schema_extraction → schema_info
   - domain_analysis → domain_info
   - field_classification → field_classification
   - column_meaning_analysis → column_meanings
   - table_meaning_analysis → table_meanings
   - er_analysis → er_relations

3. **自动保存**：系统的callback会自动将每个工具的结果保存到内存中
4. **输入验证**：所有工具都继承自BaseAnalysisTool，可以处理JSON字符串或字典输入