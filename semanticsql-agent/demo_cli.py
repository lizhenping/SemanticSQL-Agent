#!/usr/bin/env python3
"""
SemanticSQL Agent 演示CLI - 展示新架构完整功能
基于极简+自主+记忆驱动的架构实现
"""

import sys
import logging
import argparse
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from agent.sql_agent import create_semantic_sql_agent, SemanticSQLReActAgent
from utils.memory import Neo4jMemoryManager
from utils.database import DatabaseManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SemanticSQLCLI:
    """SemanticSQL CLI交互界面"""
    
    def __init__(self):
        """初始化CLI"""
        self.agent = None
        self.memory_manager = None
        
    def create_agent(self, llm_config=None, database_config=None):
        """创建Agent实例"""
        logger.info("🚀 初始化SemanticSQL Agent...")
        
        # 使用默认配置或用户配置
        default_llm_config = {
            "model": "gpt-4",
            "api_key": "your-api-key-here",
            "base_url": "https://api.openai.com/v1",
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        llm_config = llm_config or default_llm_config
        
        try:
            # 创建Agent
            self.agent = create_semantic_sql_agent(
                config_type="openai",
                llm_config=llm_config,
                database_config=database_config,
                max_iterations=10,
                verbose=True
            )
            
            logger.info(f"✅ Agent创建成功，包含工具: {self.agent.get_tool_names()}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Agent创建失败: {e}")
            return False
    
    def show_agent_info(self):
        """显示Agent信息"""
        if not self.agent:
            print("❌ Agent未初始化，请先创建Agent")
            return
        
        print("\n📊 SemanticSQL Agent 信息:")
        print(f"  • 工具数量: {len(self.agent.get_tool_names())}")
        print(f"  • 可用工具: {', '.join(self.agent.get_tool_names())}")
        
        # 显示记忆系统状态
        memory_stats = self.agent.get_memory_stats()
        print(f"  • 记忆系统: {memory_stats['status']}")
        
        if memory_stats['status'] != 'no_memory_manager':
            print(f"  • 存储三元组: {memory_stats.get('total_triples', 0)}个")
    
    def interactive_mode(self):
        """交互模式"""
        print("\n🎯 进入SemanticSQL Agent交互模式")
        print("输入SQL查询需求，Agent将自动分析并生成SQL")
        print("输入 'quit' 退出，'info' 显示Agent信息，'clear' 清空记忆")
        
        while True:
            try:
                user_input = input("\n🔤 请输入查询: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("👋 再见！")
                    break
                
                if user_input.lower() == 'info':
                    self.show_agent_info()
                    continue
                
                if user_input.lower() == 'clear':
                    if self.agent.clear_memory():
                        print("🧹 记忆已清空")
                    else:
                        print("⚠️ 记忆清空失败或无记忆管理器")
                    continue
                
                if not user_input:
                    print("⚠️ 请输入有效查询")
                    continue
                
                # 执行查询（演示模式，不依赖真实LLM）
                self.simulate_query_execution(user_input)
                
            except KeyboardInterrupt:
                print("\n👋 用户中断，退出")
                break
            except Exception as e:
                print(f"❌ 执行出错: {e}")
    
    def simulate_query_execution(self, query: str):
        """模拟查询执行（演示用）"""
        print(f"\n🔍 分析查询: {query}")
        print("📈 Agent执行流程（模拟）:")
        
        # 模拟ReAct工作流程
        steps = [
            ("Thought", "我需要分析数据库结构来理解用户查询"),
            ("Action", "schema_extraction"),
            ("Action Input", "分析数据库表结构"),
            ("Observation", "✅ 发现用户表、订单表、商品表等核心业务表"),
            ("Thought", "现在需要理解业务领域"),
            ("Action", "domain_analysis"), 
            ("Action Input", "分析业务领域特征"),
            ("Observation", "✅ 识别为电商业务域，包含用户管理、订单处理等功能"),
            ("Thought", "基于结构和领域分析，我可以生成SQL了"),
            ("Final Answer", f"基于'{query}'生成SQL查询：\n```sql\nSELECT * FROM users WHERE status = 'active';\n```")
        ]
        
        for i, (step_type, content) in enumerate(steps, 1):
            print(f"  {i}. {step_type}: {content}")
            
            # 模拟记忆存储
            if step_type == "Observation":
                print(f"     💾 知识已存储到记忆系统")
        
        print(f"\n✅ 查询处理完成！Agent使用了记忆驱动的工具协作模式")
    
    def demo_mode(self):
        """演示模式 - 展示核心功能"""
        print("\n🎭 SemanticSQL Agent 功能演示")
        
        # 演示1：Agent创建
        print("\n1️⃣ Agent创建演示:")
        self.show_agent_info()
        
        # 演示2：工具协作
        print("\n2️⃣ 工具协作演示:")
        print("   Agent包含6个分析工具，基于记忆系统协作:")
        for i, tool in enumerate(self.agent.get_tool_names(), 1):
            print(f"     {i}. {tool}: 负责{self.get_tool_description(tool)}")
        
        # 演示3：记忆系统
        print("\n3️⃣ 记忆系统演示:")
        memory_stats = self.agent.get_memory_stats()
        print(f"   记忆系统状态: {memory_stats['status']}")
        print("   • 工具间通过Neo4j三元组共享知识")
        print("   • 避免重复分析，提升执行效率")
        
        # 演示4：模拟查询
        print("\n4️⃣ 查询执行演示:")
        self.simulate_query_execution("查询所有活跃用户")
    
    def get_tool_description(self, tool_name: str) -> str:
        """获取工具描述"""
        descriptions = {
            "schema_extraction": "数据库结构提取",
            "domain_analysis": "业务领域识别", 
            "field_analysis": "字段语义分析",
            "column_analysis": "列业务含义生成",
            "table_analysis": "表实体类型分析",
            "er_analysis": "实体关系图谱构建"
        }
        return descriptions.get(tool_name, "未知功能")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="SemanticSQL Agent - 基于极简+自主+记忆驱动架构"
    )
    parser.add_argument("--mode", choices=["demo", "interactive"], default="demo",
                       help="运行模式：demo（演示）或 interactive（交互）")
    parser.add_argument("--verbose", action="store_true", 
                       help="详细日志输出")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 创建CLI实例
    cli = SemanticSQLCLI()
    
    # 创建Agent
    if not cli.create_agent():
        sys.exit(1)
    
    # 根据模式运行
    if args.mode == "demo":
        cli.demo_mode()
    elif args.mode == "interactive":
        cli.interactive_mode()
    
    print("\n🎉 SemanticSQL Agent演示完成！")


if __name__ == "__main__":
    main()