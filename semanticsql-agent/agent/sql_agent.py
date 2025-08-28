"""SQL 智能体

基于 BaseAgent 实现的 SQL 查询智能体。
"""

import logging
from typing import List, Optional, Dict, Any

from langchain_community.utilities import SQLDatabase
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from config import SQLAgentConfig
from models import QueryResult, QueryExecutionResult
from tools import (
    SchemaExtractionTool,
    DomainAnalysisTool,
    FieldClassificationTool,
    ERAnalysisTool,
    SQLGenerationTool,
    SQLValidationTool,
    SQLExecutionTool,
    SequentialThinkingTool
)
from prompts.manager import PromptManager
from .base_agent import BaseAgent
from .agent_basics import AgentStep, AgentExecution, ToolResult

logger = logging.getLogger(__name__)


class SQLAgent(BaseAgent):
    """SQL 查询智能体"""
    
    def __init__(self, config: SQLAgentConfig):
        """初始化 SQL 智能体"""
        super().__init__(config)
        self.sql_config = config
        
        # 初始化数据库连接
        self.db = self._init_database()
        
        # 初始化提示管理器
        self.prompt_manager = PromptManager(template_dir=config.prompt_templates_dir)
        
        # 创建工具
        self._tools = self._create_tools()
        
        # SQL 上下文（简单字典）
        self._sql_context = {}
        
        # LangGraph ReAct agent（可选）
        self._react_agent = None
        if config.use_langgraph:
            self._react_agent = self._create_react_agent()
        
        logger.info(f"SQL 智能体初始化完成")
    
    def _init_database(self) -> SQLDatabase:
        """初始化数据库连接"""
        try:
            db = SQLDatabase.from_uri(
                self.sql_config.database.connection_string,
                include_tables=self.sql_config.database.include_tables,
                sample_rows_in_table_info=self.sql_config.database.sample_rows
            )
            logger.info(f"数据库连接成功: {self.sql_config.database.dialect}")
            return db
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise
    
    def _create_tools(self) -> List[Any]:
        """创建工具集"""
        tools = []
        
        # 工具映射
        tool_creators = {
            "extract_database_schema": lambda: SchemaExtractionTool(db=self.db),
            "analyze_business_domain": lambda: DomainAnalysisTool(db=self.db, llm=self._llm_client),
            "classify_table_fields": lambda: FieldClassificationTool(db=self.db, llm=self._llm_client),
            "analyze_entity_relationships": lambda: ERAnalysisTool(db=self.db, llm=self._llm_client),
            "generate_sql": lambda: SQLGenerationTool(
                db=self.db, llm=self._llm_client, prompt_manager=self.prompt_manager
            ),
            "validate_sql": lambda: SQLValidationTool(db=self.db),
            "execute_sql": lambda: SQLExecutionTool(db=self.db),
            "deep_thinking": lambda: SequentialThinkingTool(llm=self._llm_client)
        }
        
        # 根据配置创建工具
        for tool_name in self.sql_config.tools:
            if tool_name in tool_creators:
                try:
                    tool = tool_creators[tool_name]()
                    tools.append(tool)
                    logger.debug(f"创建工具: {tool_name}")
                except Exception as e:
                    logger.error(f"创建工具 {tool_name} 失败: {e}")
        
        return tools
    
    def _create_react_agent(self):
        """创建 LangGraph ReAct 智能体"""
        system_prompt = self._get_system_prompt()
        return create_react_agent(
            model=self._llm_client,
            tools=self._tools,
            state_modifier=system_prompt
        )
    
    def new_task(self, task: str, extra_args: Optional[Dict[str, Any]] = None) -> None:
        """创建新的查询任务"""
        self._task = task
        self._sql_context = {}  # 重置上下文
        
        # 准备初始消息
        system_prompt = self._get_system_prompt()
        self._initial_messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=task)
        ]
        
        logger.info(f"创建新任务: {task}")
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return self.prompt_manager.get_prompt(
            "system/sql_agent",
            dialect=self.sql_config.database.dialect,
            database_name=self.db.get_db_info().split()[0] if self.db else "unknown",
            tools=[tool.name for tool in self._tools]
        )
    
    def _is_task_completed(self, step: AgentStep, execution: AgentExecution) -> bool:
        """判断任务是否完成"""
        # 成功执行了 SQL
        if "execution_result" in self._sql_context:
            result = self._sql_context["execution_result"]
            if isinstance(result, QueryExecutionResult) and result.success:
                return True
        
        # 生成了 SQL 但用户只要求生成
        if "generated_sql" in self._sql_context and "生成" in self._task and "执行" not in self._task:
            return True
        
        return False
    
    def _extract_final_result(self, execution: AgentExecution) -> QueryResult:
        """提取最终结果"""
        return QueryResult(
            success=execution.success,
            question=self._task,
            sql=self._sql_context.get("generated_sql"),
            answer=self._build_answer(),
            execution_result=self._sql_context.get("execution_result"),
            steps=len(execution.steps)
        )
    
    def _build_answer(self) -> Optional[str]:
        """构建自然语言回答"""
        exec_result = self._sql_context.get("execution_result")
        if not exec_result:
            return None
        
        if isinstance(exec_result, QueryExecutionResult) and exec_result.success:
            return f"查询执行成功，返回 {exec_result.row_count} 条结果。"
        else:
            return f"查询执行失败: {getattr(exec_result, 'error', '未知错误')}"
    
    def reflect_on_results(self, tool_results: List[ToolResult]) -> Optional[str]:
        """SQL 特定的反思"""
        if not self.sql_config.enable_reflection:
            return None
        
        for result in tool_results:
            # SQL 验证或执行失败时反思
            if not result.success and result.name in ["validate_sql", "execute_sql"]:
                return f"{result.name} 失败: {result.error}"
        
        return None
    
    async def _execute_single_tool(self, tool_call) -> ToolResult:
        """执行工具并更新上下文"""
        result = await super()._execute_single_tool(tool_call)
        
        # 更新 SQL 上下文
        if result.success:
            context_mapping = {
                "extract_database_schema": ("schema_info", result.result),
                "analyze_business_domain": ("domain_analysis", result.result),
                "classify_table_fields": ("field_classifications", result.result),
                "analyze_entity_relationships": ("relationships", result.result),
                "generate_sql": ("generated_sql", result.result),
                "validate_sql": ("validation_result", result.result),
                "execute_sql": ("execution_result", result.result)
            }
            
            if tool_call.name in context_mapping:
                key, value = context_mapping[tool_call.name]
                self._sql_context[key] = value
        
        return result
    
    async def query(self, question: str, **kwargs) -> QueryResult:
        """执行查询的便捷方法"""
        # 使用 LangGraph ReAct agent
        if self._react_agent and self.sql_config.use_langgraph:
            return await self._query_with_react_agent(question, **kwargs)
        
        # 使用基础 agent
        self.new_task(question, extra_args=kwargs)
        execution = await self.execute_task()
        
        if execution.final_result and isinstance(execution.final_result, QueryResult):
            return execution.final_result
        else:
            return QueryResult(
                success=False,
                question=question,
                error=getattr(execution, 'error', "执行失败"),
                steps=len(execution.steps)
            )
    
    async def _query_with_react_agent(self, question: str, **kwargs) -> QueryResult:
        """使用 LangGraph ReAct agent 执行查询"""
        try:
            messages = [HumanMessage(content=question)]
            config = {"configurable": {"thread_id": kwargs.get("thread_id", "default")}}
            
            result = await self._react_agent.ainvoke(
                {"messages": messages},
                config=config
            )
            
            # 解析结果
            return self._parse_react_result(question, result)
            
        except Exception as e:
            logger.error(f"ReAct agent 执行失败: {e}")
            return QueryResult(
                success=False,
                question=question,
                error=str(e)
            )
    
    def _parse_react_result(self, question: str, result: Dict[str, Any]) -> QueryResult:
        """解析 ReAct agent 结果"""
        messages = result.get("messages", [])
        
        # 提取 SQL 和答案
        generated_sql = None
        final_answer = None
        
        for message in messages:
            content = getattr(message, 'content', '')
            if "```sql" in content:
                import re
                sql_match = re.search(r'```sql\n(.*?)\n```', content, re.DOTALL)
                if sql_match:
                    generated_sql = sql_match.group(1).strip()
            
            # 最后一条 AI 消息作为答案
            if hasattr(message, 'type') and message.type == 'ai':
                final_answer = content
        
        return QueryResult(
            success=True,
            question=question,
            sql=generated_sql,
            answer=final_answer,
            steps=len(messages)
        )