"""智能体执行器

提供使用 LangChain 的 create_react_agent 的执行器实现。
"""

import logging
from typing import Dict, Any, List, Optional

from langchain.agents import AgentExecutor
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

from .sql_agent import SQLAgent
from models import QueryResult

logger = logging.getLogger(__name__)


class SQLAgentExecutor:
    """SQL 智能体执行器
    
    使用 LangChain 的 create_react_agent 来执行查询。
    """
    
    def __init__(self, agent: SQLAgent):
        """初始化执行器
        
        Args:
            agent: SQL 智能体实例
        """
        self.agent = agent
        self.react_executor = self._create_react_executor()
    
    def _create_react_executor(self):
        """创建 ReAct 执行器"""
        # 创建 ReAct 智能体
        react_agent = create_react_agent(
            model=self.agent.llm,
            tools=self.agent.tools,
            state_modifier=self.agent._get_system_prompt()
        )
        
        return react_agent
    
    async def execute(self, query: str, **kwargs) -> QueryResult:
        """执行查询
        
        Args:
            query: 用户查询
            **kwargs: 额外参数
            
        Returns:
            查询结果
        """
        try:
            # 创建消息
            messages = [HumanMessage(content=query)]
            
            # 配置
            config = {
                "configurable": {
                    "thread_id": kwargs.get("thread_id", "default")
                }
            }
            
            # 执行
            result = await self.react_executor.ainvoke(
                {"messages": messages},
                config=config
            )
            
            # 解析结果
            return self._parse_result(query, result)
            
        except Exception as e:
            logger.error(f"执行查询失败: {e}")
            return QueryResult(
                success=False,
                question=query,
                error=str(e)
            )
    
    def _parse_result(self, query: str, result: Dict[str, Any]) -> QueryResult:
        """解析执行结果
        
        Args:
            query: 原始查询
            result: 执行结果
            
        Returns:
            查询结果
        """
        # 从结果中提取信息
        messages = result.get("messages", [])
        
        # 查找 SQL 和执行结果
        generated_sql = None
        execution_result = None
        final_answer = None
        
        for message in messages:
            content = message.content if hasattr(message, 'content') else str(message)
            
            # 提取 SQL
            if "```sql" in content:
                import re
                sql_match = re.search(r'```sql\n(.*?)\n```', content, re.DOTALL)
                if sql_match:
                    generated_sql = sql_match.group(1).strip()
            
            # 提取答案
            if "答案" in content or "结果" in content:
                final_answer = content
        
        # 构建结果
        return QueryResult(
            success=True,
            question=query,
            sql=generated_sql,
            answer=final_answer,
            steps=len(messages)
        )
    
    def execute_sync(self, query: str, **kwargs) -> QueryResult:
        """同步执行查询
        
        Args:
            query: 用户查询
            **kwargs: 额外参数
            
        Returns:
            查询结果
        """
        import asyncio
        
        # 在新的事件循环中运行
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果已有事件循环在运行，创建任务
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.execute(query, **kwargs))
                    return future.result()
            else:
                # 直接运行
                return loop.run_until_complete(self.execute(query, **kwargs))
        except RuntimeError:
            # 没有事件循环，创建新的
            return asyncio.run(self.execute(query, **kwargs))