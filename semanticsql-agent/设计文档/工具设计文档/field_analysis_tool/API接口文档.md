# Field Analysis Tool API接口文档

## 工具基本信息

```python
class FieldAnalysisTool(BaseSemanticSQLTool):
    name: str = "field_analysis_tool"
    description: str = "基于数据库结构和样本数据，对字段进行语义分析和智能分类"
```

## 构造函数

### `__init__(memory_manager, database_manager, **kwargs)`

**功能**：初始化字段分析工具

**参数**：
- `memory_manager: Optional[Neo4jMemoryManager]` - Neo4j记忆管理器实例（必需）
- `database_manager: Optional[DatabaseManager]` - 数据库管理器实例（必需）
- `**kwargs` - 其他基类参数

**使用示例**：
```python
tool = FieldAnalysisTool(
    memory_manager=neo4j_manager,
    database_manager=db_manager
)
```

## 核心方法

### `_run(*args, **kwargs) -> str`

**功能**：执行字段分析的主入口方法

**参数**：
- `*args, **kwargs` - 输入参数（当前版本不使用）

**返回值**：
- `str` - 执行结果消息

**成功返回**：
```text
"✅ 字段语义分析完成

🔍 分析结果:
  • 分析字段总数: 25
  • 生成三元组: 75个
  • 关键字段: users.id, orders.order_id, products.product_id

📊 语义类型分布:
  • 标识符: 8个
  • 时间字段: 6个
  • 金额字段: 4个
  • 数量字段: 3个
  • 状态字段: 2个
  • 文本字段: 2个

🎯 分析统计:
  • 分析表数: 5
  • 高置信度匹配: 18个
  • LLM分类成功率: 85%
  
💾 字段语义知识已存储到Neo4j，可供后续工具使用"
```

**失败返回**：
```text
"❌ 字段分析失败: [错误详情]"
```

**执行流程**：
1. 检查依赖（需要schema_extraction_tool的结果）
2. 从Neo4j直接查询Column节点获取字段信息
3. 逐字段进行LLM分类（使用entropy_level字符串）
4. 解析LLM分类结果
5. 直接更新Neo4j Column节点的category/field_type/importance属性
6. 生成分类统计报告
7. 返回分析结果

**异常处理**：
- 捕获所有异常，返回错误消息而不抛出
- 记录详细错误日志
- 优雅降级处理

## 数据读取方法

### `_read_schema_from_neo4j() -> Dict[str, Any]`

**功能**：从Neo4j读取schema_extraction_tool存储的数据库结构

**返回值**：
```python
{
    "database_name": "testdb",
    "tables": [
        {
            "table_name": "users",
            "business_desc": "用户表",
            "columns": [
                {
                    "column_name": "id",
                    "data_type": "int",
                    "is_primary": True,
                    "is_nullable": False,
                    "entropy_level": "high",
                    "sample_values": [1, 2, 3, 4, 5]
                }
            ]
        }
    ]
}
```

**Cypher查询**：
```cypher
MATCH (db:Database)-[:CONTAINS]->(t:Table)-[:HAS_COLUMN]->(c:Column)
WHERE db.name = $database_name
RETURN db.name as database_name,
       collect(DISTINCT {
           table_name: t.name,
           business_desc: t.business_desc,
           columns: collect({
               column_name: c.name,
               data_type: c.data_type,
               is_primary: c.is_primary,
               is_nullable: c.is_nullable,
               entropy_level: c.entropy_level,
               sample_values: c.sample_values,
               business_desc: c.business_desc
           })
       }) as tables
```

### `_read_field_info_from_neo4j(database_name) -> List[Dict[str, Any]]`

**功能**：从Neo4j读取schema_extraction_tool已处理的字段信息

**参数**：
- `database_name: str` - 数据库名称

**返回值**：
```python
[
    {
        "field_name": "users.id",
        "table_name": "users",
        "column_name": "id",
        "data_type": "int",
        "is_primary": True,
        "is_nullable": False,
        "entropy_level": "high",        # schema_extraction_tool已计算
        "sample_values": [1, 2, 3, 4, 5],  # schema_extraction_tool已采集
        "business_desc": "用户ID"
    }
]
```

**Cypher查询**：
```cypher
MATCH (db:Database {name: $database_name})-[:CONTAINS]->(t:Table)-[:HAS_COLUMN]->(c:Column)
RETURN t.name as table_name,
       c.name as column_name,
       c.data_type as data_type,
       c.is_primary as is_primary,
       c.is_nullable as is_nullable,
       c.entropy_level as entropy_level,
       c.sample_values as sample_values,
       c.business_desc as business_desc
```

## 数据分析方法

### `_classify_field_with_llm(field_info) -> Optional[Dict[str, Any]]`

**功能**：使用LLM对单个字段进行分类

**参数**：
- `field_info: Dict[str, Any]` - 单个字段信息

**返回值**：
```python
{
    "field_name": "users.id",
    "table_name": "users",
    "column_name": "id",
    "category": "identifier",
    "field_type": "主键标识符",
    "importance": "high",
    "confidence": 0.8,
    "data_type": "int",
    "entropy_level": "high"
}
```

**关键点**：
- 直接使用entropy_level字符串（"high"/"medium"/"low"）
- 无需数值转换，LLM直接理解语义化等级
- 逐字段处理，无批量逻辑

### `_classify_field_with_llm(field_info, context) -> Dict[str, Any]`

**功能**：使用LLM对字段进行智能分类

**参数**：
- `field_info: Dict[str, Any]` - 字段信息
- `context: Dict[str, Any]` - 上下文信息（表信息、领域知识等）

**返回值**：
```python
{
    "category": "identifier",           # 字段类别
    "semantic_type": "primary_key",     # 语义类型
    "business_meaning": "用户唯一标识符", # 业务含义
    "importance": "critical",           # 重要性级别
    "confidence": 0.95,                 # 分类置信度
    "reasoning": "字段名为id，数据类型为int..."  # LLM推理过程
}
```

**LLM提示词模板**（与field_classification_pipeline保持一致）：
```jinja2
请对以下数据库字段进行分类。

领域背景：{{ domain_type }}
业务描述：{{ domain_description }}

需要分类的字段：
{% for field in fields %}
字段：{{ field.field_name }}
数据类型：{{ field.data_type }}
样本值：{{ field.samples[:3] }}
熵值：{{ field.entropy | default(0) | round(3) }}
{% endfor %}

请为每个字段提供以下分类信息：
1. category: 字段类别，必须是以下之一：
   - identifier: 标识符（如ID、编号等）
   - measure: 度量值（可计算的数值）
   - dimension: 维度（分类、分组字段）
   - datetime: 日期时间
   - text: 文本
   - boolean: 布尔值
   - other: 其他

2. field_type: 更具体的字段类型描述（如：主键、外键、状态标志、金额等）

3. importance: 重要性（high/medium/low）

请严格按照以下JSON格式返回结果：
{
  {% for field in fields %}
  "{{ field.field_name }}": {
    "category": "上述类别之一",
    "field_type": "具体类型描述",
    "importance": "high/medium/low"
  }{% if not loop.last %},{% endif %}
  {% endfor %}
}
```

**字段分类类别**（与field_classification_pipeline保持一致）：
- `identifier`: 标识符（如ID、编号等）
- `measure`: 度量值（可计算的数值）
- `dimension`: 维度（分类、分组字段）
- `datetime`: 日期时间
- `text`: 文本
- `boolean`: 布尔值
- `other`: 其他

### `_match_field_patterns(field_name, data_type) -> Optional[Dict[str, Any]]`

**功能**：基于规则的字段模式匹配（辅助LLM分类）

**参数**：
- `field_name: str` - 字段名
- `data_type: str` - 数据类型

**返回值**：
```python
{
    "matched_pattern": "identifier_pattern",
    "semantic_type": "primary_key", 
    "confidence": 0.8,
    "reason": "字段名包含'id'且为整数类型"
}
```

**模式库**：
```python
FIELD_PATTERNS = {
    "identifier": {
        "name_patterns": ["id", "_id", "uuid", "key", "_key", "code"],
        "type_patterns": ["int", "bigint", "varchar", "uuid"],
        "confidence": 0.9
    },
    "datetime": {
        "name_patterns": ["time", "date", "created", "updated", "at"],
        "type_patterns": ["datetime", "timestamp", "date"],
        "confidence": 0.85
    },
    "monetary": {
        "name_patterns": ["amount", "price", "cost", "fee", "money"],
        "type_patterns": ["decimal", "numeric", "float"],
        "confidence": 0.8
    }
}
```

## Neo4j存储方法

### `_store_field_analysis_to_neo4j(analysis_results) -> None`

**功能**：将字段分析结果存储到Neo4j

**参数**：
- `analysis_results: List[Dict[str, Any]]` - 字段分析结果列表

**存储结构**（更新Column节点属性）：
```cypher
# 更新Column节点，添加分类结果
MATCH (t:Table {name: $table_name})-[:HAS_COLUMN]->(c:Column {name: $column_name})
SET c.category = $category,
    c.field_type = $field_type,
    c.importance = $importance,
    c.classification_timestamp = datetime()

# 批量更新多个字段的分类结果
UNWIND $field_classifications as fc
MATCH (t:Table {name: fc.table_name})-[:HAS_COLUMN]->(c:Column {name: fc.column_name})
SET c.category = fc.category,
    c.field_type = fc.field_type,
    c.importance = fc.importance,
    c.classification_timestamp = datetime()
```

### `_create_analysis_summary_node(database_name, summary) -> None`

**功能**：创建分析摘要节点

**Cypher查询**：
```cypher
MATCH (db:Database {name: $database_name})
MERGE (summary:FieldAnalysisSummary {database_name: $database_name})
SET summary.total_fields = $total_fields,
    summary.analyzed_fields = $analyzed_fields,
    summary.classification_stats = $classification_stats,
    summary.entropy_distribution = $entropy_distribution,
    summary.analysis_timestamp = $timestamp,
    summary.llm_success_rate = $llm_success_rate
MERGE (db)-[:HAS_ANALYSIS_SUMMARY]->(summary)
```

## 批量处理方法

### `_process_fields_in_batches(field_list, batch_size=10) -> List[Dict[str, Any]]`

**功能**：批量处理字段以提高效率

**参数**：
- `field_list: List[Dict[str, Any]]` - 字段信息列表
- `batch_size: int` - 批处理大小

**返回值**：
- `List[Dict[str, Any]]` - 处理结果列表

**批处理策略**：
1. 按表分组处理，减少数据库连接开销
2. LLM调用批量化，提高API效率
3. Neo4j写入批量化，减少事务开销
4. 错误恢复机制，单个失败不影响整体

**示例代码**：
```python
def _process_fields_in_batches(self, field_list, batch_size=10):
    """批量处理字段"""
    results = []
    
    for i in range(0, len(field_list), batch_size):
        batch = field_list[i:i+batch_size]
        
        # 批量采集样本数据
        batch_samples = self._collect_batch_samples(batch)
        
        # 批量LLM分析
        batch_classifications = self._classify_batch_with_llm(batch, batch_samples)
        
        # 批量存储结果
        self._store_batch_results(batch_classifications)
        
        results.extend(batch_classifications)
        
        # 记录进度
        self.logger.info(f"已处理 {min(i+batch_size, len(field_list))}/{len(field_list)} 个字段")
    
    return results
```

## 配置参数

### `FIELD_ANALYSIS_CONFIG`

**分析配置**（简化版）：
```python
FIELD_ANALYSIS_CONFIG = {
    "max_retries": 3,                # LLM重试次数
    "sample_count": 3,               # 用于LLM分析的样本数量
    
    # 默认重要性映射（规则降级时使用）
    "default_importance": {
        "identifier": "high",
        "measure": "medium",
        "dimension": "medium",
        "datetime": "medium",
        "text": "low",
        "boolean": "low",
        "other": "low"
    }
}

# 注意：移除了batch_size和entropy_mapping
# entropy_level直接使用字符串，无需数值转换
```

## 错误处理

### 错误级别分类

**致命错误（返回失败）**：
- Neo4j连接不可用
- 数据库管理器缺失
- schema_extraction_tool依赖未满足

**业务错误（记录警告，继续处理）**：
- 单个字段样本采集失败
- LLM分类调用失败
- 部分字段存储失败

**优雅降级**：
- LLM不可用时使用规则分类
- 样本采集失败时使用已有样本值
- 分类失败时标记为"other"

### 错误恢复机制

```python
def _analyze_field_with_fallback(self, field_info):
    """带降级的字段分析"""
    try:
        # 尝试完整分析
        return self._analyze_field_complete(field_info)
    except LLMError:
        # 降级到规则分析
        self.logger.warning(f"LLM分析失败，降级到规则分析: {field_info['field_name']}")
        return self._analyze_field_with_rules(field_info)
    except Exception as e:
        # 最后降级到默认分类
        self.logger.error(f"字段分析完全失败: {field_info['field_name']}, {e}")
        return self._create_default_classification(field_info)
```

## 性能指标

### 时间复杂度
- **字段数量**: O(n) 其中n为字段总数
- **样本采集**: O(k) 其中k为采样数量（500）
- **LLM分类**: O(n/b) 其中b为批处理大小（10）

### 内存使用
- **样本数据**: O(n*k) 存储所有字段样本
- **分析结果**: O(n) 存储分析结果
- **批处理缓存**: O(b*k) 批处理时的临时存储

### 性能优化建议
- 对于大型数据库（>1000字段），增加批处理大小
- 使用异步处理提高LLM调用效率
- 实现结果缓存避免重复分析

## 便利函数

### `create_field_analysis_tool(memory_manager, database_manager) -> FieldAnalysisTool`

**功能**：创建字段分析工具的便利函数

**参数**：
- `memory_manager: Optional[Neo4jMemoryManager]` - Neo4j记忆管理器
- `database_manager: Optional[DatabaseManager]` - 数据库管理器

**返回值**：
- `FieldAnalysisTool` - 配置好的工具实例

**使用示例**：
```python
from tools.analysis_tools.field_analysis_tool import create_field_analysis_tool

tool = create_field_analysis_tool(
    memory_manager=neo4j_manager,
    database_manager=db_manager
)

# 执行分析
result = tool._run()
```

## 日志接口

### 日志级别和格式
```python
# 开始执行
self.logger.info(f"🔧 {self.name}: 开始字段分析")

# 依赖检查
self.logger.info(f"✅ 依赖检查通过: schema_extraction_tool")

# 数据读取
self.logger.info(f"📖 从Neo4j读取到 {total_fields} 个字段")

# 批处理进度
self.logger.info(f"📊 批处理进度: {current_batch}/{total_batches}")

# LLM分析
self.logger.info(f"🤖 LLM分析完成: 成功率 {success_rate:.1%}")

# 结果存储
self.logger.info(f"💾 分析结果已存储到Neo4j: {stored_count} 个字段")

# 执行完成
self.logger.info(f"✅ {self.name}: 字段分析完成 - 分析了 {total_fields} 个字段")

# 警告信息
self.logger.warning(f"⚠️ 字段样本采集失败: {table_name}.{column_name}")

# 错误信息
self.logger.error(f"❌ {self.name}: 字段分析失败: {error_message}")
```

## 集成测试接口

### 测试用例设计

**基础功能测试**：
- 依赖检查测试
- 数据读取测试
- 样本采集测试
- 分类算法测试
- 结果存储测试

**错误处理测试**：
- LLM服务不可用测试
- 数据库连接异常测试
- 部分数据缺失测试

**性能测试**：
- 大量字段处理测试
- 内存使用监控测试
- 批处理效率测试