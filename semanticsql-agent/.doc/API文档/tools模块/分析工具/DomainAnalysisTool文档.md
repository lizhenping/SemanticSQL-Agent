# DomainAnalysisTool API 文档

## 概述
`DomainAnalysisTool` 是用于分析数据库业务领域的工具，能够识别数据库的主要业务场景、实体和流程。

## 类定义
```python
class DomainAnalysisTool(BaseTool):
    """业务领域分析工具"""
```

## 工具属性

- **名称**: `analyze_domain`
- **类别**: `analysis`
- **描述**: 分析数据库的业务领域，识别主要业务场景

## 参数定义

| 参数名 | 类型 | 必需 | 默认值 | 描述 |
|-------|------|------|--------|------|
| schema_info | object | 是 | - | 数据库结构信息 |
| sample_data | object | 否 | {} | 各表的样本数据 |

## 执行方法

### `_execute(schema_info: Dict[str, Any], sample_data: Dict[str, List] = None) -> Dict[str, Any]`

**返回数据结构：**
```python
{
    "primary_domain": str,              # 主要业务领域
    "sub_domains": List[str],           # 次要业务领域
    "business_entities": Dict[str, Dict],  # 业务实体映射
    "business_processes": List[str],    # 识别的业务流程
    "data_characteristics": Dict,       # 数据特征分析
    "domain_confidence": float,         # 领域识别置信度
    "recommendations": List[str]        # 使用建议
}
```

## 内部分析方法

### `_analyze_domain_patterns(tables: Dict) -> Dict[str, float]`
分析表名和结构模式，识别可能的业务领域。

**支持的领域类型：**
- 电商/零售（ecommerce）
- 金融/财务（finance）
- 人力资源（hr）
- 客户关系管理（crm）
- 库存管理（inventory）
- 医疗健康（healthcare）
- 教育培训（education）
- 物流运输（logistics）

### `_identify_business_entities(tables: Dict) -> Dict[str, Dict]`
识别核心业务实体。

**返回示例：**
```python
{
    "customer": {
        "tables": ["users", "customers", "accounts"],
        "type": "master",
        "importance": "high"
    },
    "order": {
        "tables": ["orders", "order_items"],
        "type": "transactional",
        "importance": "high"
    }
}
```

### `_identify_business_processes(tables: Dict, entities: Dict) -> List[str]`
基于表关系识别业务流程。

**识别的流程类型：**
- 订单处理流程
- 支付流程
- 库存管理流程
- 客户服务流程
- 审批流程

### `_analyze_data_characteristics(tables: Dict, sample_data: Dict) -> Dict`
分析数据特征。

**分析维度：**
- 数据量级
- 更新频率
- 数据完整性
- 时间跨度
- 地理分布

## 使用示例

```python
# 创建工具实例
tool = DomainAnalysisTool(settings)

# 准备输入数据
schema_info = {
    "tables": {
        "users": {...},
        "orders": {...},
        "products": {...},
        "inventory": {...}
    }
}

sample_data = {
    "users": [{"id": 1, "name": "张三", ...}],
    "orders": [{"id": 1001, "user_id": 1, ...}]
}

# 执行分析
result = tool.run(
    schema_info=schema_info,
    sample_data=sample_data
)

if result["success"]:
    analysis = result["data"]
    print(f"主要业务领域: {analysis['primary_domain']}")
    print(f"置信度: {analysis['domain_confidence']:.2%}")
    print(f"识别的业务实体: {list(analysis['business_entities'].keys())}")
    print(f"业务流程: {analysis['business_processes']}")
    
    # 查看建议
    for rec in analysis['recommendations']:
        print(f"- {rec}")
```

## 领域识别规则

### 电商领域特征
- 表名包含：product, order, cart, payment
- 存在用户-订单-产品关系
- 包含价格、库存等字段

### 金融领域特征
- 表名包含：account, transaction, balance
- 存在借贷关系
- 包含金额、日期等字段

### 人力资源领域特征
- 表名包含：employee, department, salary
- 存在组织结构关系
- 包含职位、薪资等字段

## 输出示例

```json
{
    "primary_domain": "ecommerce",
    "sub_domains": ["crm", "inventory"],
    "business_entities": {
        "customer": {
            "tables": ["users", "user_profiles"],
            "type": "master",
            "importance": "high"
        },
        "product": {
            "tables": ["products", "product_categories"],
            "type": "master",
            "importance": "high"
        },
        "order": {
            "tables": ["orders", "order_items"],
            "type": "transactional",
            "importance": "high"
        }
    },
    "business_processes": [
        "订单处理流程",
        "库存管理流程",
        "客户服务流程"
    ],
    "data_characteristics": {
        "total_records": 1500000,
        "update_frequency": "high",
        "data_quality": "good",
        "time_span": "3 years"
    },
    "domain_confidence": 0.85,
    "recommendations": [
        "建议关注订单转化率分析",
        "可以进行客户细分分析",
        "适合做销售预测模型"
    ]
}
```

## 注意事项

1. 领域识别基于启发式规则，可能不完全准确
2. 样本数据有助于提高分析准确性
3. 复杂业务可能涵盖多个领域
4. 建议结合人工确认领域分析结果