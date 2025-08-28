"""SQL 智能体

基于 BaseAgent 实现的 SQL 查询智能体。
"""

import logging
from typing import List, Optional, Dict, Any

from langchain_community.utilities import SQLDatabase

from config import SQLAgentConfig
from models import QueryResult
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
from .agent_state import AgentStep, AgentExecution

logger = logging.getLogger(__name__)


class SQLAgent(BaseAgent):
    """SQL 查询智能体
    
    专门用于处理自然语言到 SQL 的转换和执行。
    """
    
    def __init__(self, config: SQLAgentConfig):
        """初始化 SQL 智能体
        
        Args:
            config: SQL 智能体配置
        """
        super().__init__(config)
        self.sql_config = config
        
        # 初始化数据库连接
        self.db = self._init_database()
        
        # 初始化提示管理器
        self.prompt_manager = PromptManager(template_dir=config.prompt_templates_dir)
        
        # 创建工具
        self.tools = self._create_tools()
        
        logger.info("SQL 智能体初始化完成")
    
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
        """创建工具集
        
        Returns:
            工具列表
        """
        tools = []
        tool_mapping = {
            "extract_database_schema": lambda: SchemaExtractionTool(db=self.db),
            "analyze_business_domain": lambda: DomainAnalysisTool(db=self.db, llm=self.llm),
            "classify_table_fields": lambda: FieldClassificationTool(db=self.db, llm=self.llm),
            "analyze_entity_relationships": lambda: ERAnalysisTool(db=self.db, llm=self.llm),
            "generate_sql": lambda: SQLGenerationTool(db=self.db, llm=self.llm, prompt_manager=self.prompt_manager),
            "validate_sql": lambda: SQLValidationTool(db=self.db),
            "execute_sql": lambda: SQLExecutionTool(db=self.db),
            "deep_thinking": lambda: SequentialThinkingTool(llm=self.llm)
        }
        
        # 根据配置创建工具
        for tool_name in self.sql_config.tools:
            if tool_name in tool_mapping:
                try:
                    tool = tool_mapping[tool_name]()
                    tools.append(tool)
                    logger.debug(f"创建工具: {tool_name}")
                except Exception as e:
                    logger.error(f"创建工具 {tool_name} 失败: {e}")
        
        logger.info(f"创建了 {len(tools)} 个工具")
        return tools
    
    def create_task(self, query: str, context: Optional[Dict[str, Any]] = None) -> None:
        """创建新的查询任务
        
        Args:
            query: 用户的自然语言查询
            context: 额外的上下文信息
        """
        self._task = query
        self._context.update(**(context or {}))
        self._messages = []
        
        logger.info(f"创建新任务: {query}")
        
        # 如果启用了自动分析，检查是否需要进行数据库分析
        if self.sql_config.auto_analyze:
            self._check_need_analysis(query)
    
    def _check_need_analysis(self, query: str) -> None:
        """检查是否需要进行数据库分析
        
        对于简单查询可以跳过分析阶段，直接生成 SQL。
        
        Args:
            query: 用户查询
        """
        # 简单的启发式规则
        simple_keywords = ["count", "sum", "average", "max", "min", "list", "show", "display"]
        complex_keywords = ["trend", "compare", "analyze", "relationship", "pattern", "correlation"]
        
        query_lower = query.lower()
        
        # 检查是否是简单查询
        is_simple = any(keyword in query_lower for keyword in simple_keywords)
        is_complex = any(keyword in query_lower for keyword in complex_keywords)
        
        # 更新上下文
        self._context.extra_info["need_analysis"] = is_complex or not is_simple
        self._context.extra_info["query_complexity"] = "complex" if is_complex else "simple"
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词
        
        Returns:
            系统提示词
        """
        # 从模板管理器获取系统提示词
        return self.prompt_manager.get_prompt(
            "system/sql_agent",
            dialect=self.sql_config.database.dialect,
            database_name=self.db.get_db_info().split()[0] if self.db else "unknown",
            tools=[tool.name for tool in self.tools]
        )
    
    def _is_task_completed(self, step: AgentStep, execution: AgentExecution) -> bool:
        """判断任务是否完成
        
        Args:
            step: 当前步骤
            execution: 执行记录
            
        Returns:
            是否完成
        """
        # 如果执行了 SQL 并获得结果，则任务完成
        if self._context.execution_result and self._context.execution_result.success:
            return True
        
        # 如果工具明确表示任务完成
        if step.action and step.action.tool == "task_done":
            return True
        
        # 如果生成了 SQL 但用户只要求生成不要求执行
        if self._context.generated_sql and "生成" in self._task and "执行" not in self._task:
            return True
        
        return False
    
    def _extract_final_result(self, execution: AgentExecution) -> QueryResult:
        """提取最终结果
        
        Args:
            execution: 执行记录
            
        Returns:
            查询结果
        """
        # 构建查询结果
        result = QueryResult(
            success=execution.state == AgentState.COMPLETED,
            question=self._task,
            sql=self._context.generated_sql,
            answer=self._build_answer(),
            execution_result=self._context.execution_result,
            error=execution.error,
            steps=execution.total_steps
        )
        
        return result
    
    def _build_answer(self) -> Optional[str]:
        """构建自然语言回答
        
        Returns:
            回答文本
        """
        if not self._context.execution_result:
            return None
        
        # 简单的回答生成
        exec_result = self._context.execution_result
        if exec_result.success:
            answer_parts = []
            
            # 添加查询描述
            answer_parts.append(f"查询执行成功，返回 {exec_result.row_count} 条结果。")
            
            # 如果结果较少，可以展示
            if exec_result.row_count > 0 and exec_result.row_count <= 10:
                answer_parts.append("\n结果如下：")
                # 格式化结果表格
                if exec_result.rows:
                    # 简单的表格格式化
                    headers = list(exec_result.rows[0].keys())
                    answer_parts.append(" | ".join(headers))
                    answer_parts.append("-" * (len(" | ".join(headers))))
                    for row in exec_result.rows[:10]:
                        answer_parts.append(" | ".join(str(row.get(h, "")) for h in headers))
            
            return "\n".join(answer_parts)
        else:
            return f"查询执行失败: {exec_result.error}"
    
    def reflect_on_result(self, result: Any) -> Optional[str]:
        """对结果进行反思
        
        如果启用了反思机制，在 SQL 生成或执行后进行反思。
        
        Args:
            result: 工具执行结果
            
        Returns:
            反思内容
        """
        if not self.sql_config.enable_reflection:
            return None
        
        # 对 SQL 验证失败的结果进行反思
        if hasattr(result, 'tool') and result.tool == "validate_sql":
            if not result.success:
                return f"SQL 验证失败，需要修正: {result.error}"
        
        # 对 SQL 执行错误进行反思
        if hasattr(result, 'tool') and result.tool == "execute_sql":
            if not result.success:
                return f"SQL 执行失败，可能需要调整查询: {result.error}"
        
        return None
    
    async def query(self, question: str, **kwargs) -> QueryResult:
        """执行查询的便捷方法
        
        Args:
            question: 用户问题
            **kwargs: 额外参数
            
        Returns:
            查询结果
        """
        # 创建任务
        self.create_task(question, kwargs)
        
        # 执行任务
        execution = await self.execute_task()
        
        # 返回结果
        if execution.final_result and isinstance(execution.final_result, QueryResult):
            return execution.final_result
        else:
            # 构建错误结果
            return QueryResult(
                success=False,
                question=question,
                error=execution.error or "执行失败",
                steps=execution.total_steps
            )