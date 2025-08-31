#!/usr/bin/env python
"""
SemanticSQL Agent 主入口
专注MySQL支持的NL2SQL系统
"""

import sys
import logging
from pathlib import Path

from config.settings import Settings
from config.database import DatabaseConfig, DatabaseType
from agent.smart_sql_agent import SmartSQLAgent
from agent.data_generation_agent import DataGenerationAgent
from utils.database import DatabaseManager


def setup_logging(level: str = "INFO"):
    """设置日志"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def test_connection() -> bool:
    """测试数据库连接"""
    print("测试MySQL数据库连接...")
    
    # 使用默认MySQL配置
    db_config = DatabaseConfig()
    manager = DatabaseManager(db_config)
    
    if manager.initialize():
        print(f"✅ 数据库连接成功: {db_config.host}:{db_config.port}/{db_config.database}")
        
        # 获取数据库信息
        db_info = manager.get_database_info()
        print(f"📊 数据库信息: {db_info['tables_count']} 个表")
        if db_info.get('tables'):
            print(f"📋 表列表: {', '.join(db_info['tables'][:5])}")
        
        manager.close()
        return True
    else:
        print("❌ 数据库连接失败")
        return False


def run_query(question: str) -> None:
    """运行SQL查询"""
    print(f"\n🔍 处理问题: {question}")
    
    # 创建配置
    settings = Settings()
    db_config = DatabaseConfig()
    
    try:
        # 创建智能体
        agent = SmartSQLAgent(settings, db_config)
        
        # 执行查询
        result = agent.query(question)
        
        if result.success:
            print(f"✅ 查询成功")
            print(f"📝 生成的SQL: {result.sql}")
            print(f"📊 数据: {result.data}")
            print(f"⏱️  执行时间: {result.execution_time}s")
        else:
            print(f"❌ 查询失败: {result.error}")
            
    except Exception as e:
        print(f"❌ 系统错误: {e}")
    finally:
        if 'agent' in locals():
            agent.close()


def show_schema() -> None:
    """显示数据库结构"""
    print("\n📋 数据库结构信息...")
    
    db_config = DatabaseConfig()
    manager = DatabaseManager(db_config)
    
    if manager.initialize():
        tables = manager.get_tables()
        print(f"📊 共有 {len(tables)} 个表:")
        
        for table_name in tables[:10]:  # 只显示前10个表
            table_info = manager.get_table_info(table_name)
            columns = table_info.get('columns', [])
            print(f"  📋 {table_name} ({len(columns)} 列)")
            
            # 显示前几个列
            for col in columns[:5]:
                col_type = col.get('type', 'unknown')
                key_info = f" [PK]" if col.get('key') == 'PRI' else ""
                print(f"    - {col['name']} ({col_type}){key_info}")
            
            if len(columns) > 5:
                print(f"    ... 还有 {len(columns) - 5} 列")
        
        manager.close()
    else:
        print("❌ 无法连接数据库")


def interactive_mode():
    """交互模式"""
    print("\n🤖 进入交互模式 (输入 'quit' 退出)")
    print("支持的命令:")
    print("  - 任何自然语言问题")
    print("  - 'schema' - 显示数据库结构")
    print("  - 'test' - 测试数据库连接")
    print("  - 'quit' - 退出")
    
    settings = Settings()
    db_config = DatabaseConfig()
    agent = None
    
    try:
        agent = SmartSQLAgent(settings, db_config)
        
        while True:
            try:
                question = input("\n💬 请输入问题: ").strip()
                
                if question.lower() in ['quit', 'exit', 'q']:
                    break
                elif question.lower() == 'schema':
                    show_schema()
                elif question.lower() == 'test':
                    test_connection()
                elif question:
                    result = agent.query(question)
                    
                    if result.success:
                        print(f"✅ SQL: {result.sql}")
                        if result.data:
                            print(f"📊 结果: {result.data}")
                        print(f"⏱️  {result.execution_time:.2f}s")
                    else:
                        print(f"❌ 错误: {result.error}")
                        
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ 错误: {e}")
                
    finally:
        if agent:
            agent.close()
        print("👋 再见!")


def generate_training_data(count: int, output_file: str) -> None:
    """生成训练数据 - Agent自主执行"""
    print(f"\n🤖 开始生成 {count} 条NL2SQL训练数据...")
    print(f"📁 输出文件: {output_file}")
    
    # 创建配置
    settings = Settings()
    db_config = DatabaseConfig()
    
    try:
        # 创建完整数据生成智能体
        agent = DataGenerationAgent(settings, db_config)
        
        # Agent自主执行数据生成
        result = agent.generate_training_data(count, output_file)
        
        print(f"\n✅ 数据生成完成!")
        print(f"📊 生成样本数: {result['total_generated']}")
        print(f"📁 输出文件: {result['output_file']}")
        print(f"🔄 执行步骤: {result['execution_steps']}")
        print(f"🆔 任务ID: {result['task_id']}")
            
    except Exception as e:
        print(f"❌ 生成失败: {e}")
    finally:
        if 'agent' in locals():
            agent.close()


def main():
    """主函数"""
    setup_logging()
    
    if len(sys.argv) < 2:
        print("SemanticSQL Agent - MySQL专用NL2SQL系统")
        print("用法:")
        print("  python main.py test                    - 测试数据库连接")
        print("  python main.py schema                  - 显示数据库结构")
        print("  python main.py run <问题>              - 运行单个查询")
        print("  python main.py generate <数量> <输出>  - 生成训练数据")
        print("  python main.py interactive             - 交互模式")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "test":
        success = test_connection()
        sys.exit(0 if success else 1)
        
    elif command == "schema":
        show_schema()
        
    elif command == "run":
        if len(sys.argv) < 3:
            print("❌ 请提供要查询的问题")
            sys.exit(1)
        question = " ".join(sys.argv[2:])
        run_query(question)
        
    elif command == "generate":
        if len(sys.argv) < 4:
            print("❌ 用法: python main.py generate <数量> <输出文件>")
            print("   示例: python main.py generate 20 training_data.json")
            sys.exit(1)
        
        count = int(sys.argv[2])
        output_file = sys.argv[3]
        generate_training_data(count, output_file)
        
    elif command == "interactive":
        interactive_mode()
        
    else:
        print(f"❌ 未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()