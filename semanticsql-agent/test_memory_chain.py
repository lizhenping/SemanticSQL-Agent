"""
测试Memory链是否正确工作
"""

import logging
from utils.memory import DatabaseAnalysisMemory

# 设置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_memory_chain():
    """测试memory链"""
    # 创建memory实例
    memory = DatabaseAnalysisMemory()
    
    # 模拟工具执行和保存结果
    print("=== 测试Memory链 ===")
    
    # 1. Schema extraction
    schema_data = {
        "database_name": "test_db",
        "tables": {
            "users": {
                "columns": {
                    "id": {"type": "int", "nullable": False},
                    "name": {"type": "varchar(50)", "nullable": False}
                },
                "primary_key": ["id"]
            }
        }
    }
    memory.save_context(
        inputs={"tool_name": "schema_extraction"},
        outputs=schema_data
    )
    print("✓ Schema extraction 保存成功")
    
    # 验证获取
    retrieved_schema = memory.get_analysis("schema_info")
    print(f"  获取schema_info: {bool(retrieved_schema)}")
    
    # 2. Domain analysis
    domain_data = {
        "domain_type": "电商",
        "domain_description": "电商平台数据库",
        "key_entities": ["用户", "订单", "商品"]
    }
    memory.save_context(
        inputs={"tool_name": "domain_analysis"},
        outputs=domain_data
    )
    print("✓ Domain analysis 保存成功")
    
    # 3. Field classification
    field_data = {
        "field_classifications": {
            "users": {
                "id": {"category": "identifier", "field_type": "主键", "importance": "high"},
                "name": {"category": "text", "field_type": "名称", "importance": "high"}
            }
        }
    }
    memory.save_context(
        inputs={"tool_name": "field_classification"},
        outputs=field_data
    )
    print("✓ Field classification 保存成功")
    
    # 4. Column meanings
    column_data = {
        "column_descriptions": {
            "users.id": "用户唯一标识符",
            "users.name": "用户姓名"
        }
    }
    memory.save_context(
        inputs={"tool_name": "column_meaning_analysis"},
        outputs=column_data
    )
    print("✓ Column meanings 保存成功")
    
    # 5. Table meanings
    table_data = {
        "table_descriptions": {
            "users": "存储系统用户基本信息"
        }
    }
    memory.save_context(
        inputs={"tool_name": "table_meaning_analysis"},
        outputs=table_data
    )
    print("✓ Table meanings 保存成功")
    
    # 6. ER analysis
    er_data = {
        "physical_relations": [],
        "logical_relations": [],
        "conceptual_relations": []
    }
    memory.save_context(
        inputs={"tool_name": "er_analysis"},
        outputs=er_data
    )
    print("✓ ER analysis 保存成功")
    
    # 验证完整性
    print("\n=== 验证Memory完整性 ===")
    has_complete = memory.has_complete_analysis()
    print(f"是否有完整分析: {has_complete}")
    
    # 获取摘要
    summary = memory.get_summary()
    print(f"Memory摘要: {summary}")
    
    # 验证所有键
    print("\n=== Memory中的所有键 ===")
    for key in ["schema_info", "domain_info", "field_classification", 
                "column_meanings", "table_meanings", "er_relations"]:
        data = memory.get_analysis(key)
        print(f"{key}: {'✓' if data else '✗'}")

if __name__ == "__main__":
    test_memory_chain()