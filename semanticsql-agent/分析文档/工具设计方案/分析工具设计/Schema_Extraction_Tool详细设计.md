# Schema Extraction Tool 简化设计方案

## 1. 工具职责

**核心职责**: 从数据库中提取NL2SQL需要的基本结构信息：表、列、数据类型、注释

## 2. 输入设计

### 2.1 输入参数（简化版）
```python
def _run(
    self, 
    host: str,
    database: str, 
    username: str,
    password: str,
    port: int = 3306,
    **kwargs
) -> TripleCollection:
```

### 2.2 参数说明
- **host**: 数据库服务器地址
- **database**: 数据库名称
- **username**: 用户名
- **password**: 密码
- **port**: 端口号（默认3306）

## 3. 输出设计 - 三层基本三元组

### 3.1 数据库层 - 包含哪些表
```python
("database", "has_table", "users")
("database", "has_table", "orders")
("database", "has_table", "products")
("database", "has_table", "order_items")
```

### 3.2 表层 - 表注释和包含哪些列
```python
# 表注释（如果有）
("table:users", "table_comment", "用户信息表")
("table:orders", "table_comment", "订单信息表")
("table:products", "table_comment", "商品信息表")

# 表包含的列
("table:users", "has_column", "id")
("table:users", "has_column", "username")
("table:users", "has_column", "email")
("table:users", "has_column", "created_at")

("table:orders", "has_column", "id") 
("table:orders", "has_column", "user_id")
("table:orders", "has_column", "total_amount")
("table:orders", "has_column", "status")
("table:orders", "has_column", "created_at")
```

### 3.3 列层 - 数据类型和列注释
```python
# 用户表的列
("column:users.id", "data_type", "int")
("column:users.id", "column_comment", "用户唯一标识")

("column:users.username", "data_type", "varchar")
("column:users.username", "column_comment", "用户名")

("column:users.email", "data_type", "varchar") 
("column:users.email", "column_comment", "邮箱地址")

("column:users.created_at", "data_type", "datetime")
("column:users.created_at", "column_comment", "创建时间")

# 订单表的列
("column:orders.id", "data_type", "int")
("column:orders.id", "column_comment", "订单ID")

("column:orders.user_id", "data_type", "int")
("column:orders.user_id", "column_comment", "用户ID")

("column:orders.total_amount", "data_type", "decimal")
("column:orders.total_amount", "column_comment", "订单总金额")

("column:orders.status", "data_type", "varchar")
("column:orders.status", "column_comment", "订单状态")
```

## 4. 数据类型标准化

### 4.1 统一数据类型映射
```python
# 将复杂的数据库类型映射为标准类型
TYPE_MAPPING = {
    # 整数类型
    "int": "int",
    "integer": "int", 
    "bigint": "int",
    "smallint": "int",
    "tinyint": "int",
    
    # 字符串类型
    "varchar": "varchar",
    "char": "varchar",
    "text": "text",
    "longtext": "text",
    
    # 数值类型
    "decimal": "decimal",
    "float": "decimal",
    "double": "decimal",
    
    # 时间类型
    "datetime": "datetime",
    "timestamp": "datetime", 
    "date": "date",
    "time": "time",
    
    # 布尔类型
    "boolean": "boolean",
    "bool": "boolean"
}
```

## 5. 实现策略

### 5.1 核心查询逻辑
```python
def _extract_database_schema(self, config: Dict) -> TripleCollection:
    """提取数据库schema的简化逻辑"""
    result_triples = TripleCollection()
    
    with self._get_database_connection(config) as conn:
        # 1. 获取所有表
        tables = self._get_table_list(conn, config['database'])
        
        for table_name in tables:
            # 添加数据库包含表的三元组
            result_triples.add_triple("database", "has_table", table_name)
            
            # 2. 获取表注释
            table_comment = self._get_table_comment(conn, table_name)
            if table_comment:
                result_triples.add_triple(f"table:{table_name}", "table_comment", table_comment)
            
            # 3. 获取列信息
            columns = self._get_column_info(conn, table_name)
            
            for column in columns:
                # 表包含列
                result_triples.add_triple(f"table:{table_name}", "has_column", column['name'])
                
                # 列的数据类型（标准化）
                standard_type = self._standardize_data_type(column['type'])
                result_triples.add_triple(
                    f"column:{table_name}.{column['name']}", 
                    "data_type", 
                    standard_type
                )
                
                # 列注释（如果有）
                if column.get('comment'):
                    result_triples.add_triple(
                        f"column:{table_name}.{column['name']}", 
                        "column_comment", 
                        column['comment']
                    )
    
    return result_triples
```

### 5.2 简化的SQL查询
```python
# 获取表列表
GET_TABLES_QUERY = """
SELECT TABLE_NAME, TABLE_COMMENT 
FROM information_schema.TABLES 
WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'
"""

# 获取列信息  
GET_COLUMNS_QUERY = """
SELECT 
    COLUMN_NAME as name,
    DATA_TYPE as type, 
    COLUMN_COMMENT as comment
FROM information_schema.COLUMNS 
WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
ORDER BY ORDINAL_POSITION
"""
```

## 6. 调用示例

### 6.1 基本调用
```python
# 简单的参数传递
schema_result = agent.execute_tool("schema_extraction",
    host="localhost",
    database="ecommerce", 
    username="root",
    password="password123"
)

# 查看提取结果
for triple in schema_result:
    print(f"{triple.subject} --{triple.predicate}--> {triple.object}")
```

### 6.2 结果统计
```python
# 统计基本信息
tables = []
columns = {}

for triple in schema_result:
    if triple.predicate == "has_table":
        tables.append(triple.object)
    elif triple.predicate == "has_column":
        table_name = triple.subject.replace("table:", "")
        if table_name not in columns:
            columns[table_name] = []
        columns[table_name].append(triple.object)

print(f"数据库包含 {len(tables)} 个表")
for table, cols in columns.items():
    print(f"  表 {table}: {len(cols)} 个列")
```

## 7. 设计优势

### 7.1 极简专注
- 只包含NL2SQL真正需要的信息
- 去除了所有不必要的复杂性
- 专注于核心的表-列-类型结构

### 7.2 易于理解
- 清晰的三层关系：数据库→表→列
- 自然的语义表达
- 标准化的数据类型

### 7.3 高效实现
- 只需要2个简单的SQL查询
- 无复杂的关系分析
- 处理速度快，资源消耗少

### 7.4 满足需求
- 包含SQL生成需要的所有基础信息
- 表和列的注释帮助理解业务含义
- 为后续分析工具提供充足的上下文

这个简化版本去除了70%+的复杂性，同时保留了NL2SQL系统需要的所有核心信息。