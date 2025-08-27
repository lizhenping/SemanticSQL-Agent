"""分析工作流示例

展示如何使用改造后的分析工具，按照 nl2sql_pipeline 的流程进行数据库分析。
"""

import yaml
from typing import Dict, Any
import json

from agent import SemanticSQLAgent


def print_section(title: str):
    """打印分节标题"""
    print(f"\n{'='*60}")
    print(f"{title}")
    print('='*60)


def run_analysis_workflow(agent: SemanticSQLAgent):
    """运行完整的分析工作流"""
    
    # 保存中间结果
    analysis_results = {}
    
    # 步骤1: 提取数据库结构
    print_section("步骤1: 提取数据库结构")
    
    schema_query = "使用 extract_database_schema 工具提取所有表的结构信息，包括行数和外键关系"
    result = agent.query(schema_query)
    
    if result.success:
        print(f"✓ 成功提取数据库结构")
        print(f"执行步骤: {result.steps}")
        
        # 从结果中提取 schema 信息
        # 注意：实际使用时需要解析 agent 返回的结果
        analysis_results["schema_info"] = {
            "success": True,
            "message": "Schema extraction completed"
        }
    else:
        print(f"✗ 提取失败: {result.error}")
        return
    
    # 步骤2: 分析业务领域
    print_section("步骤2: 分析业务领域")
    
    domain_query = """
    基于已提取的数据库结构，使用 analyze_business_domain 工具分析业务领域。
    请识别核心业务实体、业务流程和专业术语。
    """
    
    result = agent.query(domain_query)
    
    if result.success:
        print(f"✓ 成功分析业务领域")
        print(f"结果预览: {result.answer[:200]}...")
        analysis_results["domain_knowledge"] = {
            "success": True,
            "message": "Domain analysis completed"
        }
    else:
        print(f"✗ 分析失败: {result.error}")
    
    # 步骤3: 字段分类
    print_section("步骤3: 字段分类")
    
    classification_query = """
    使用 classify_table_fields 工具对主要表的字段进行分类。
    请识别维度、度量、标识符等字段类型，并计算熵值。
    重点分析前5个表。
    """
    
    result = agent.query(classification_query)
    
    if result.success:
        print(f"✓ 成功完成字段分类")
        print(f"SQL: {result.sql}" if result.sql else "")
        analysis_results["field_classifications"] = {
            "success": True,
            "message": "Field classification completed"
        }
    else:
        print(f"✗ 分类失败: {result.error}")
    
    # 步骤4: 实体关系分析
    print_section("步骤4: 实体关系分析")
    
    er_query = """
    使用 analyze_entity_relationships 工具分析表之间的关系。
    包括显式外键关系和基于命名约定的隐式关系。
    请生成关系图谱和关系类型分析。
    """
    
    result = agent.query(er_query)
    
    if result.success:
        print(f"✓ 成功分析实体关系")
        print(f"执行时间: {result.execution_result.get('execution_time', 'N/A')} 秒" if result.execution_result else "")
        analysis_results["er_analysis"] = {
            "success": True,
            "message": "ER analysis completed"
        }
    else:
        print(f"✗ 关系分析失败: {result.error}")
    
    # 总结
    print_section("分析流程总结")
    
    success_count = sum(1 for r in analysis_results.values() if r.get("success"))
    print(f"完成步骤: {success_count}/4")
    
    if success_count == 4:
        print("\n✅ 数据库分析流程全部完成！")
        print("\n基于分析结果，您现在可以：")
        print("1. 使用 generate_sql 工具生成符合业务逻辑的 SQL 查询")
        print("2. 利用字段分类信息优化聚合查询")
        print("3. 基于实体关系正确构建多表连接")
    else:
        print("\n⚠️ 部分分析步骤未完成，可能影响后续 SQL 生成质量")
    
    return analysis_results


def demonstrate_sql_generation(agent: SemanticSQLAgent):
    """演示基于分析结果的 SQL 生成"""
    print_section("演示：基于分析的 SQL 生成")
    
    # 示例查询
    queries = [
        "查询每个部门的员工数量和平均工资",
        "找出最近一个月内下单金额最高的10个客户",
        "统计每个产品类别的销售额和销售数量"
    ]
    
    for i, query in enumerate(queries, 1):
        print(f"\n示例 {i}: {query}")
        print("-" * 40)
        
        # 构建包含分析上下文的查询
        contextual_query = f"""
        基于之前的数据库分析结果，请生成 SQL 查询：{query}
        
        注意：
        1. 使用已识别的核心实体表
        2. 基于字段分类选择正确的聚合字段
        3. 利用实体关系信息构建准确的 JOIN 条件
        """
        
        result = agent.query(contextual_query)
        
        if result.success and result.sql:
            print(f"生成的 SQL:\n{result.sql}")
        else:
            print(f"生成失败: {result.error if not result.success else '未生成 SQL'}")


def main():
    """主函数"""
    # 加载配置
    try:
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print("错误: 未找到 config.yaml 文件")
        print("请先复制 config.yaml.example 并配置数据库连接信息")
        return
    
    # 创建智能体
    print("初始化 SemanticSQL Agent...")
    try:
        agent = SemanticSQLAgent(config)
    except Exception as e:
        print(f"初始化失败: {e}")
        return
    
    # 运行分析工作流
    print("\n开始数据库分析工作流...")
    print("这将按照 nl2sql_pipeline 的流程进行完整分析")
    
    analysis_results = run_analysis_workflow(agent)
    
    # 如果分析成功，演示 SQL 生成
    if all(r.get("success") for r in analysis_results.values()):
        input("\n按回车键继续演示 SQL 生成...")
        demonstrate_sql_generation(agent)
    
    print("\n演示完成！")


if __name__ == "__main__":
    main()