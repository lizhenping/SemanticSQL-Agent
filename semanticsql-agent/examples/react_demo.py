"""ReAct 模式 Tool Calling 演示"""

import logging
from typing import List, Dict, Any

from agent.agent_basics import AgentStep, AgentExecution
from agent.base_agent import BaseAgent
from utils.llm_clients import LLMClient
from tools.base import Tool, ToolParameter

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(message)s')


# 示例工具定义
class DatabaseInfoTool(Tool):
    """获取数据库信息的工具"""
    
    def __init__(self):
        super().__init__(
            name="get_database_info",
            description="获取数据库的基本信息，包括表列表和统计"
        )
        # 模拟的数据库信息
        self.db_info = {
            "tables": ["users", "orders", "products"],
            "stats": {
                "users": {"count": 1234, "columns": ["id", "name", "email", "created_at"]},
                "orders": {"count": 5678, "columns": ["id", "user_id", "total", "status"]},
                "products": {"count": 100, "columns": ["id", "name", "price", "stock"]}
            }
        }
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="table_name",
                type="string",
                description="特定表名（可选）",
                required=False
            )
        ]
    
    def execute(self, table_name: str = None) -> Dict[str, Any]:
        if table_name:
            if table_name in self.db_info["stats"]:
                return {
                    "table": table_name,
                    "info": self.db_info["stats"][table_name]
                }
            else:
                return {"error": f"表 {table_name} 不存在"}
        else:
            return self.db_info


class SQLGeneratorTool(Tool):
    """生成 SQL 的工具"""
    
    def __init__(self):
        super().__init__(
            name="generate_sql",
            description="根据需求生成 SQL 查询语句"
        )
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="requirement",
                type="string",
                description="查询需求描述",
                required=True
            ),
            ToolParameter(
                name="table_info",
                type="object",
                description="相关表的信息",
                required=False
            )
        ]
    
    def execute(self, requirement: str, table_info: Dict = None) -> Dict[str, Any]:
        # 简单的规则匹配生成 SQL
        requirement_lower = requirement.lower()
        
        if "用户" in requirement and "数量" in requirement:
            return {"sql": "SELECT COUNT(*) as user_count FROM users"}
        elif "订单" in requirement and "总额" in requirement:
            return {"sql": "SELECT SUM(total) as total_amount FROM orders"}
        elif "产品" in requirement and "库存" in requirement:
            return {"sql": "SELECT name, stock FROM products WHERE stock > 0"}
        else:
            return {"sql": f"-- 需求：{requirement}\n-- 请提供更具体的查询需求"}


class SQLExecutorTool(Tool):
    """执行 SQL 的工具"""
    
    def __init__(self):
        super().__init__(
            name="execute_sql",
            description="执行 SQL 查询并返回结果"
        )
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="sql",
                type="string",
                description="要执行的 SQL 语句",
                required=True
            )
        ]
    
    def execute(self, sql: str) -> Dict[str, Any]:
        # 模拟 SQL 执行
        sql_lower = sql.lower()
        
        if "count(*)" in sql_lower and "users" in sql_lower:
            return {"result": [{"user_count": 1234}], "row_count": 1}
        elif "sum(total)" in sql_lower and "orders" in sql_lower:
            return {"result": [{"total_amount": 123456.78}], "row_count": 1}
        elif "products" in sql_lower:
            return {
                "result": [
                    {"name": "产品A", "stock": 50},
                    {"name": "产品B", "stock": 30},
                    {"name": "产品C", "stock": 100}
                ],
                "row_count": 3
            }
        else:
            return {"error": "SQL 执行失败：模拟环境不支持此查询"}


# 演示智能体
class DemoAgent(BaseAgent):
    """演示用的 SQL 智能体"""
    
    def _get_system_prompt(self) -> str:
        return """你是一个 SQL 助手。通过以下步骤完成任务：
1. 使用 get_database_info 了解数据库结构
2. 使用 generate_sql 生成合适的 SQL
3. 使用 execute_sql 执行查询
4. 根据结果给出清晰的回答

每一步都要说明你的思考过程。"""
    
    def _is_task_completed(self, step: AgentStep, execution: AgentExecution) -> bool:
        # 如果最后一步没有工具调用，说明 LLM 认为任务完成
        return step.llm_response and not step.llm_response.tool_calls
    
    def _extract_final_result(self, execution: AgentExecution) -> str:
        # 获取最后一个有内容的 LLM 响应
        for step in reversed(execution.steps):
            if step.llm_response and step.llm_response.content:
                return step.llm_response.content
        return "任务完成，但没有明确的结果"


def main():
    """运行演示"""
    print("=== ReAct Tool Calling 演示 ===\n")
    
    # 创建 LLM 客户端
    llm_client = LLMClient(
        model="Qwen3-14B",
        base_url="http://192.168.200.216:9009/v1",
        temperature=0.1
    )
    
    # 创建工具
    tools = [
        DatabaseInfoTool(),
        SQLGeneratorTool(),
        SQLExecutorTool()
    ]
    
    # 创建智能体
    agent = DemoAgent(
        llm_client=llm_client,
        tools=tools,
        max_steps=5,
        verbose=True
    )
    
    # 测试查询
    queries = [
        "数据库中有多少个用户？",
        "所有订单的总金额是多少？",
        "显示有库存的产品列表"
    ]
    
    for query in queries:
        print(f"\n{'='*50}")
        print(f"查询: {query}")
        print('='*50)
        
        try:
            # 执行任务
            result = agent.execute_task(query)
            
            print(f"\n最终结果: {result.final_result}")
            print(f"执行步骤: {len(result.steps)}")
            print(f"执行时间: {result.execution_time:.2f}秒")
            
        except Exception as e:
            print(f"错误: {e}")


if __name__ == "__main__":
    main()