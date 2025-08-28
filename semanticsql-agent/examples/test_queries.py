#!/usr/bin/env python3
"""测试查询示例脚本"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.sql_agent_v2 import SQLAgentV2
from utils.config import Config

def main():
    """运行测试查询"""
    # 加载配置
    config = Config.from_yaml("examples/config.yaml")
    sql_config = config.to_sql_agent_config()
    
    # 创建智能体
    agent = SQLAgentV2(sql_config)
    
    # 测试查询列表
    test_queries = [
        "查询所有表的结构",
        "统计每个表的记录数",
        "找出最近7天创建的订单",
        "计算每个产品类别的总销售额",
        "查询销售额最高的前10个客户"
    ]
    
    # 执行查询
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'='*60}")
        print(f"测试 {i}: {query}")
        print('='*60)
        
        try:
            # 执行查询
            result = agent.query(query)
            
            # 显示结果
            print(f"成功: {result.success}")
            if result.sql:
                print(f"\nSQL:\n{result.sql}")
            if result.answer:
                print(f"\n回答: {result.answer}")
            print(f"\n步数: {result.steps}")
            
        except Exception as e:
            print(f"错误: {e}")
        
        # 重置智能体
        agent.reset()
        
        # 暂停一下，避免请求过快
        import time
        time.sleep(1)


if __name__ == "__main__":
    main()