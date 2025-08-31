# SchemaExtractionTool API 文档

## 概述
`SchemaExtractionTool` 是用于提取数据库完整结构信息的工具，包括表、列、索引、外键等元数据。

## 类定义
```python
class SchemaExtractionTool(BaseTool):
    """数据库结构提取工具"""
```

## 工具属性

- **名称**: `extract_schema`
- **类别**: `analysis`
- **描述**: 提取数据库的完整结构信息，包括表、列、索引、外键等

## 参数定义

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|-------|------|------|--------|------|
| include_views | boolean | 否 | False | 是否包含视图 |
| include_indexes | boolean | 否 | True | 是否包含索引信息 |
| sample_size | integer | 否 | 10 | 每个表的示例数据行数 |

## 方法

### `set_database_manager(db_manager)`
设置数据库管理器。

**参数：**
- `db_manager`: 数据库管理器实例

### `_execute(**kwargs) -> DatabaseSchema`
执行数据库结构提取。

**返回：**
- `DatabaseSchema`: 包含完整数据库结构信息的对象

**执行过程：**
1. 检查数据库连接
2. 获取所有表名
3. 遍历每个表提取详细信息
4. 提取列信息、主键、外键
5. 可选提取索引信息
6. 可选提取示例数据
7. 分析表关系

## 返回数据结构

```python
DatabaseSchema(
    database_name="database_name",
    tables={
        "table_name": TableInfo(
            name="table_name",
            columns=[
                ColumnInfo(
                    name="column_name",
                    data_type="varchar(255)",
                    nullable=True,
                    default=None,
                    is_primary=False,
                    is_foreign=False
                ),
                ...
            ],
            primary_key="id",
            foreign_keys=[
                ForeignKey(
                    column="user_id",
                    referenced_table="users",
                    referenced_column="id"
                ),
                ...
            ],
            indexes=["idx_created_at", ...],
            row_count=1000
        ),
        ...
    },
    relationships=[
        TableRelationship(
            from_table="orders",
            to_table="users",
            relationship_type="many-to-one",
            join_condition="orders.user_id = users.id"
        ),
        ...
    ],
    extracted_at=datetime.now()
)
```

## 使用示例

```python
# 创建工具实例
tool = SchemaExtractionTool(settings)
tool.set_database_manager(db_manager)

# 提取完整结构（包含索引）
result = tool.run(
    include_views=False,
    include_indexes=True,
    sample_size=5
)

if result["success"]:
    schema = result["data"]
    print(f"数据库: {schema.database_name}")
    print(f"表数量: {len(schema.tables)}")
    
    for table_name, table_info in schema.tables.items():
        print(f"\n表: {table_name}")
        print(f"  列数: {len(table_info.columns)}")
        print(f"  行数: {table_info.row_count}")
```

## 错误处理

- `SchemaExtractionError`: 结构提取失败
- `DatabaseConnectionError`: 数据库连接问题

## 注意事项

1. 需要先设置数据库管理器才能使用
2. 提取大型数据库结构可能耗时较长
3. 示例数据提取会增加执行时间
4. 某些数据库可能不支持所有元数据查询