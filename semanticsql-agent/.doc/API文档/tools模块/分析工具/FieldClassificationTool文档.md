# FieldClassificationTool API 文档

## 概述
`FieldClassificationTool` 是用于对数据库字段进行智能分类的工具。它能够识别字段的业务含义，帮助理解数据库结构和生成更准确的查询。

## 类定义
```python
class FieldClassificationTool(BaseTool):
    """字段智能分类工具"""
```

## 工具属性

- **名称**: `field_classification`
- **类别**: `analysis`
- **描述**: 对数据库表的字段进行智能分类，识别字段的业务含义

## 参数定义

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|-------|------|------|--------|------|
| table_info | object | 是 | - | 表结构信息 |
| sample_data | array | 否 | [] | 样本数据（可选） |
| custom_patterns | object | 否 | {} | 自定义分类模式 |

## 内置字段类型

```python
FIELD_TYPES = {
    "ID": ["id", "uuid", "key", "编号", "代码", "标识"],
    "TIMESTAMP": ["time", "date", "created", "updated", "timestamp", "时间", "日期"],
    "AMOUNT": ["amount", "price", "cost", "fee", "money", "金额", "价格", "费用"],
    "STATUS": ["status", "state", "flag", "type", "种类", "状态", "类型"],
    "DESCRIPTION": ["name", "title", "desc", "comment", "remark", "名称", "描述", "备注"]
}
```

## 执行方法

### `_execute(...) -> Dict[str, Any]`

**返回数据结构：**
```python
{
    "table_name": str,                    # 表名
    "field_classifications": {            # 字段分类结果
        "field_name": {
            "classification": str,        # 分类类型
            "confidence": float,          # 置信度 (0-1)
            "reasoning": str,             # 分类理由
            "characteristics": List[str]  # 字段特征
        },
        ...
    },
    "statistics": {                       # 统计信息
        "total_fields": int,
        "classified_fields": int,
        "classification_distribution": Dict[str, int]
    },
    "recommendations": List[str]          # 使用建议
}
```

## 内部分析方法

### `_classify_field(column: Dict, patterns: Dict, sample_values: List) -> Dict`
对单个字段进行分类。

**分类策略：**
1. 基于字段名的模式匹配
2. 基于数据类型的推断
3. 基于样本数据的分析
4. 综合评分决定最终分类

### `_analyze_by_name(field_name: str, patterns: Dict) -> Tuple[str, float]`
通过字段名分析分类。

**匹配规则：**
- 完全匹配：置信度 1.0
- 包含匹配：置信度 0.8
- 后缀匹配：置信度 0.6
- 相似匹配：置信度 0.4

### `_analyze_by_type(data_type: str) -> Tuple[str, float]`
通过数据类型分析分类。

**类型映射：**
- `int/bigint` + `_id` 后缀 → ID
- `datetime/timestamp` → TIMESTAMP
- `decimal/float` + 金额相关名称 → AMOUNT
- `varchar` + 小长度 → STATUS
- `text/varchar` + 大长度 → DESCRIPTION

### `_analyze_by_sample(sample_values: List) -> Tuple[str, float]`
通过样本数据分析分类。

**分析维度：**
- 值的格式模式
- 值的范围分布
- 值的唯一性
- 值的业务含义

## 使用示例

### 基本使用
```python
# 创建工具实例
tool = FieldClassificationTool(settings)

# 准备表信息
table_info = {
    "name": "orders",
    "columns": [
        {"name": "order_id", "type": "bigint", "is_primary": True},
        {"name": "user_id", "type": "bigint"},
        {"name": "total_amount", "type": "decimal(10,2)"},
        {"name": "order_status", "type": "varchar(20)"},
        {"name": "created_time", "type": "datetime"},
        {"name": "remark", "type": "text"}
    ]
}

# 执行分类
result = tool.run(table_info=table_info)

if result["success"]:
    classifications = result["data"]["field_classifications"]
    
    for field, info in classifications.items():
        print(f"{field}:")
        print(f"  分类: {info['classification']}")
        print(f"  置信度: {info['confidence']:.2f}")
        print(f"  理由: {info['reasoning']}")
```

### 带样本数据的分类
```python
# 提供样本数据以提高分类准确性
sample_data = [
    {
        "order_id": 10001,
        "user_id": 1234,
        "total_amount": 299.99,
        "order_status": "completed",
        "created_time": "2024-01-01 10:00:00",
        "remark": "加急配送"
    },
    # 更多样本...
]

result = tool.run(
    table_info=table_info,
    sample_data=sample_data
)
```

### 自定义分类模式
```python
# 添加业务特定的分类模式
custom_patterns = {
    "PHONE": ["phone", "mobile", "tel", "电话", "手机"],
    "EMAIL": ["email", "mail", "邮箱"],
    "ADDRESS": ["address", "addr", "地址", "location"]
}

result = tool.run(
    table_info=table_info,
    custom_patterns=custom_patterns
)
```

## 输出示例

```json
{
    "table_name": "orders",
    "field_classifications": {
        "order_id": {
            "classification": "ID",
            "confidence": 0.95,
            "reasoning": "字段名包含'id'且为主键",
            "characteristics": ["主键", "自增", "唯一标识"]
        },
        "user_id": {
            "classification": "ID",
            "confidence": 0.90,
            "reasoning": "字段名以'_id'结尾，类型为bigint",
            "characteristics": ["外键", "关联用户表"]
        },
        "total_amount": {
            "classification": "AMOUNT",
            "confidence": 0.95,
            "reasoning": "字段名包含'amount'，类型为decimal",
            "characteristics": ["金额字段", "两位小数", "非负数"]
        },
        "order_status": {
            "classification": "STATUS",
            "confidence": 0.90,
            "reasoning": "字段名包含'status'，类型为varchar(20)",
            "characteristics": ["状态枚举", "有限值集合"]
        },
        "created_time": {
            "classification": "TIMESTAMP",
            "confidence": 1.0,
            "reasoning": "字段名包含'time'，类型为datetime",
            "characteristics": ["创建时间", "不可更新"]
        },
        "remark": {
            "classification": "DESCRIPTION",
            "confidence": 0.85,
            "reasoning": "字段名为'remark'，类型为text",
            "characteristics": ["备注信息", "可选字段", "长文本"]
        }
    },
    "statistics": {
        "total_fields": 6,
        "classified_fields": 6,
        "classification_distribution": {
            "ID": 2,
            "TIMESTAMP": 1,
            "AMOUNT": 1,
            "STATUS": 1,
            "DESCRIPTION": 1
        }
    },
    "recommendations": [
        "建议为 user_id 创建外键约束",
        "order_status 建议使用枚举类型或创建状态表",
        "total_amount 建议添加CHECK约束确保非负",
        "created_time 建议添加默认值 CURRENT_TIMESTAMP"
    ]
}
```

## 分类类型详解

### ID（标识符）
- 主键字段
- 外键引用
- UUID/GUID
- 业务编号

### TIMESTAMP（时间戳）
- 创建时间
- 更新时间
- 日期字段
- 时间区间

### AMOUNT（金额）
- 价格
- 费用
- 余额
- 数值计算字段

### STATUS（状态）
- 枚举状态
- 标志位
- 类型标识
- 分类字段

### DESCRIPTION（描述）
- 名称
- 标题
- 备注
- 详细说明

## 最佳实践

1. **提供样本数据**
   - 至少提供 5-10 条样本
   - 包含各种典型值
   - 有助于提高分类准确性

2. **使用自定义模式**
   - 添加业务特定的字段类型
   - 使用行业术语
   - 支持多语言关键词

3. **结合其他分析**
   - 配合 ER 分析使用
   - 参考领域分析结果
   - 综合多维度信息

4. **关注低置信度分类**
   - 置信度 < 0.6 需要人工确认
   - 可能需要更多样本数据
   - 考虑添加自定义规则

## 扩展功能

### 支持的额外分类
通过自定义模式可以支持：
- 地理位置（经纬度、地址）
- 联系方式（电话、邮箱）
- 文件路径（URL、路径）
- 加密字段（密码、令牌）
- 业务特定（SKU、订单号等）

## 注意事项

1. 分类结果基于启发式规则，可能需要人工验证
2. 样本数据质量直接影响分类准确性
3. 自定义模式优先级高于内置模式
4. 某些字段可能匹配多个分类，选择置信度最高的