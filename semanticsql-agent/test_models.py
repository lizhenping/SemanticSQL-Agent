"""测试数据模型和解析器"""

import json
from models.analysis_models import (
    SchemaExtractionOutput,
    TableDetail,
    ColumnDetail,
    DomainKnowledge,
    DomainCharacteristics
)
from utils.output_parsers import (
    create_structured_output_parser,
    get_pydantic_format_instruction
)


def test_schema_models():
    """测试 Schema 相关模型"""
    print("=== 测试 Schema 模型 ===")
    
    # 创建列详情
    col1 = ColumnDetail(
        name="id",
        data_type="INT(11)",
        is_nullable=False,
        is_primary_key=True
    )
    
    col2 = ColumnDetail(
        name="name",
        data_type="VARCHAR(100)",
        is_nullable=True,
        comment="用户名称"
    )
    
    # 创建表详情
    table = TableDetail(
        name="users",
        comment="用户表",
        columns=[col1, col2],
        primary_keys=["id"],
        row_count=1000
    )
    
    # 创建输出模型
    output = SchemaExtractionOutput(
        database_name="test_db",
        tables_count=1,
        tables=[table],
        extraction_config={"include_row_count": True},
        summary={"total_tables": 1, "total_columns": 2}
    )
    
    # 转换为 JSON
    print(json.dumps(output.dict(), indent=2, ensure_ascii=False))
    print("✓ Schema 模型测试通过\n")


def test_domain_models():
    """测试领域分析模型"""
    print("=== 测试领域分析模型 ===")
    
    # 创建数据特征
    chars = DomainCharacteristics(
        data_volume="中",
        update_frequency="高",
        data_quality="良好"
    )
    
    # 创建领域知识
    knowledge = DomainKnowledge(
        domain="电商",
        domain_description="电子商务平台数据库",
        core_entities=["用户", "商品", "订单"],
        entity_descriptions={
            "用户": "平台注册用户",
            "商品": "销售的产品",
            "订单": "用户购买记录"
        },
        business_processes=["注册", "浏览", "下单", "支付"],
        business_rules=["用户必须先注册才能下单"],
        terminology={"SKU": "库存单位"},
        data_characteristics=chars
    )
    
    print(json.dumps(knowledge.dict(), indent=2, ensure_ascii=False))
    print("✓ 领域模型测试通过\n")


def test_output_parser():
    """测试输出解析器"""
    print("=== 测试输出解析器 ===")
    
    # 创建解析器
    parser = create_structured_output_parser(DomainKnowledge)
    
    # 获取格式指令
    instructions = get_pydantic_format_instruction(
        DomainKnowledge,
        "业务领域分析结果"
    )
    print("格式指令：")
    print(instructions)
    print()
    
    # 测试解析 JSON 响应
    json_response = """
    {
        "domain": "金融",
        "domain_description": "银行核心业务系统",
        "core_entities": ["账户", "客户", "交易"],
        "entity_descriptions": {
            "账户": "银行账户信息",
            "客户": "银行客户信息",
            "交易": "交易记录"
        },
        "business_processes": ["开户", "存款", "取款", "转账"],
        "business_rules": ["交易金额不能超过账户余额"],
        "terminology": {
            "ATM": "自动柜员机",
            "PIN": "个人识别码"
        },
        "data_characteristics": {
            "data_volume": "大",
            "update_frequency": "高",
            "data_quality": "优秀"
        }
    }
    """
    
    # 解析
    result = parser.parse(json_response)
    print("解析结果：")
    print(f"领域: {result.domain}")
    print(f"核心实体: {result.core_entities}")
    print("✓ 解析器测试通过\n")


def test_mixed_response():
    """测试混合文本响应的解析"""
    print("=== 测试混合响应解析 ===")
    
    parser = create_structured_output_parser(DomainKnowledge)
    
    # 模拟 LLM 的混合响应
    mixed_response = """
    根据数据库结构分析，这是一个教育管理系统的数据库。
    
    以下是详细的分析结果：
    
    ```json
    {
        "domain": "教育",
        "domain_description": "学校教务管理系统",
        "core_entities": ["学生", "教师", "课程", "成绩"],
        "entity_descriptions": {
            "学生": "在校学生信息",
            "教师": "授课教师信息",
            "课程": "开设的课程",
            "成绩": "学生课程成绩"
        },
        "business_processes": ["选课", "上课", "考试", "评分"],
        "business_rules": ["学生选课不能超过学分限制", "成绩必须在0-100之间"],
        "terminology": {
            "GPA": "平均成绩点",
            "学分": "课程的权重单位"
        },
        "data_characteristics": {
            "data_volume": "中",
            "update_frequency": "中",
            "data_quality": "良好"
        }
    }
    ```
    
    系统包含完整的教学管理功能。
    """
    
    # 解析
    result = parser.parse(mixed_response)
    print("从混合响应中解析的结果：")
    print(f"领域: {result.domain}")
    print(f"描述: {result.domain_description}")
    print(f"业务流程: {result.business_processes}")
    print("✓ 混合响应解析测试通过\n")


def main():
    """运行所有测试"""
    print("\n开始测试数据模型和解析器...\n")
    
    test_schema_models()
    test_domain_models()
    test_output_parser()
    test_mixed_response()
    
    print("所有测试通过！✨")


if __name__ == "__main__":
    main()