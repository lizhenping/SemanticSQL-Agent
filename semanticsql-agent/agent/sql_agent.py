"""SQL 智能体

基于 BaseAgent 实现的 SQL 查询智能体，参考 TRAEAgent 的设计。
"""

import logging
from typing import List, Optional, Dict, Any

from langchain_community.utilities import SQLDatabase
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

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
from .agent_basics import (
    AgentStep, AgentExecution, AgentState, AgentStepState,
    ToolResult, LLMUsage
)

logger = logging.getLogger(__name__)


class SQLAgent(BaseAgent):
    """SQL 查询智能体
    
    专门用于处理自然语言到 SQL 的转换和执行。
    参考 TRAEAgent 的设计，实现了：
    - 智能的工具选择和执行
    - SQL 验证后的反思机制
    - 详细的执行轨迹记录
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
        self._tools = self._create_tools()
        
        # SQL 生成和执行相关的上下文
        self._sql_context = {
            "schema_info": None,
            "domain_analysis": None,
            "field_classifications": None,
            "relationships": None,
            "generated_sql": None,
            "validation_result": None,
            "execution_result": None
        }
        
        logger.info(f"SQL 智能体初始化完成，连接到数据库: {config.database.database}")
    
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
        
        # 工具映射
        tool_mapping = {
            "extract_database_schema": lambda: SchemaExtractionTool(
                db=self.db,
                name="extract_database_schema",
                description="提取数据库 schema 信息，包括表结构、字段、索引等"
            ),
            "analyze_business_domain": lambda: DomainAnalysisTool(
                db=self.db,
                llm=self._llm_client,
                name="analyze_business_domain",
                description="分析数据库的业务领域和数据特征"
            ),
            "classify_table_fields": lambda: FieldClassificationTool(
                db=self.db,
                llm=self._llm_client,
                name="classify_table_fields",
                description="对表字段进行分类，识别维度、度量、时间字段等"
            ),
            "analyze_entity_relationships": lambda: ERAnalysisTool(
                db=self.db,
                llm=self._llm_client,
                name="analyze_entity_relationships",
                description="分析表之间的实体关系"
            ),
            "generate_sql": lambda: SQLGenerationTool(
                db=self.db,
                llm=self._llm_client,
                prompt_manager=self.prompt_manager,
                name="generate_sql",
                description="根据自然语言查询生成 SQL"
            ),
            "validate_sql": lambda: SQLValidationTool(
                db=self.db,
                name="validate_sql",
                description="验证生成的 SQL 语法和语义"
            ),
            "execute_sql": lambda: SQLExecutionTool(
                db=self.db,
                name="execute_sql",
                description="执行 SQL 并返回结果"
            ),
            "deep_thinking": lambda: SequentialThinkingTool(
                llm=self._llm_client,
                name="deep_thinking",
                description="对复杂问题进行深度思考和推理"
            )
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
    
    def new_task(
        self,
        task: str,
        extra_args: Optional[Dict[str, Any]] = None,
        tool_names: Optional[List[str]] = None
    ) -> None:
        """创建新的查询任务
        
        Args:
            task: 用户的自然语言查询
            extra_args: 额外的参数
            tool_names: 指定使用的工具名称（可选）
        """
        self._task = task
        
        # 重置 SQL 上下文
        self._sql_context = {
            "schema_info": None,
            "domain_analysis": None,
            "field_classifications": None,
            "relationships": None,
            "generated_sql": None,
            "validation_result": None,
            "execution_result": None
        }
        
        # 如果指定了工具，过滤工具列表
        if tool_names:
            self._active_tools = [t for t in self._tools if t.name in tool_names]
        else:
            self._active_tools = self._tools
        
        # 准备初始消息
        system_prompt = self._get_system_prompt()
        self._initial_messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=task)
        ]
        
        # 检查是否需要数据库分析
        if self.sql_config.auto_analyze:
            self._check_need_analysis(task)
        
        logger.info(f"创建新任务: {task}")
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return self.prompt_manager.get_prompt(
            "system/sql_agent",
            dialect=self.sql_config.database.dialect,
            database_name=self.db.get_db_info().split()[0] if self.db else "unknown",
            tools=[tool.name for tool in self._tools],
            max_steps=self._max_steps
        )
    
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
        
        # 如果是简单查询，可能不需要所有分析工具
        if is_simple and not is_complex:
            # 可以跳过一些分析工具
            skip_tools = ["analyze_entity_relationships", "classify_table_fields"]
            self._active_tools = [t for t in self._tools if t.name not in skip_tools]
            logger.info("检测到简单查询，跳过部分分析工具")
    
    def _is_task_completed(self, step: AgentStep, execution: AgentExecution) -> bool:
        """判断任务是否完成
        
        Args:
            step: 当前步骤
            execution: 执行记录
            
        Returns:
            是否完成
        """
        # 如果成功执行了 SQL 并获得结果
        if self._sql_context["execution_result"]:
            result = self._sql_context["execution_result"]
            if isinstance(result, QueryExecutionResult) and result.success:
                return True
        
        # 如果工具明确表示任务完成
        if step.tool_calls:
            for tool_call in step.tool_calls:
                if tool_call.name == "task_done":
                    return True
        
        # 如果生成了 SQL 但用户只要求生成不要求执行
        if self._sql_context["generated_sql"] and "生成" in self._task and "执行" not in self._task:
            return True
        
        # 如果出现错误
        if step.state == AgentStepState.ERROR:
            return True
        
        return False
    
    def _extract_final_result(self, step: AgentStep, execution: AgentExecution) -> QueryResult:
        """提取最终结果
        
        Args:
            step: 最后的步骤
            execution: 执行记录
            
        Returns:
            查询结果
        """
        # 构建查询结果
        result = QueryResult(
            success=execution.success,
            question=self._task,
            sql=self._sql_context["generated_sql"],
            answer=self._build_answer(),
            execution_result=self._sql_context["execution_result"],
            error=execution.error,
            steps=execution.total_steps
        )
        
        # 添加 token 使用统计
        if execution.total_tokens:
            result.token_usage = {
                "input_tokens": execution.total_tokens.input_tokens,
                "output_tokens": execution.total_tokens.output_tokens,
                "total_tokens": execution.total_tokens.total_tokens
            }
        
        return result
    
    def _build_answer(self) -> Optional[str]:
        """构建自然语言回答
        
        Returns:
            回答文本
        """
        if not self._sql_context["execution_result"]:
            return None
        
        exec_result = self._sql_context["execution_result"]
        if isinstance(exec_result, QueryExecutionResult) and exec_result.success:
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
            return f"查询执行失败: {exec_result.error if hasattr(exec_result, 'error') else '未知错误'}"
    
    def _should_reflect(self, tool_results: List[ToolResult]) -> bool:
        """判断是否需要反思
        
        Args:
            tool_results: 工具执行结果
            
        Returns:
            是否需要反思
        """
        if not self.sql_config.enable_reflection:
            return False
        
        # SQL 验证失败需要反思
        for result in tool_results:
            if result.name == "validate_sql" and not result.success:
                return True
            # SQL 执行失败也需要反思
            if result.name == "execute_sql" and not result.success:
                return True
        
        return False
    
    async def _reflect_on_results(
        self,
        tool_results: List[ToolResult],
        messages: List[BaseMessage]
    ) -> Optional[str]:
        """对结果进行反思
        
        专门针对 SQL 生成和执行的反思。
        
        Args:
            tool_results: 工具执行结果
            messages: 消息历史
            
        Returns:
            反思内容
        """
        reflections = []
        
        for result in tool_results:
            if not result.success:
                if result.name == "validate_sql":
                    reflections.append(f"SQL 验证失败: {result.error}。需要修正 SQL 语法或逻辑。")
                elif result.name == "execute_sql":
                    reflections.append(f"SQL 执行失败: {result.error}。可能需要检查表名、字段名或数据类型。")
                elif result.name == "generate_sql":
                    reflections.append(f"SQL 生成失败: {result.error}。需要更好地理解查询需求。")
        
        if reflections:
            return " ".join(reflections)
        
        return None
    
    async def _execute_single_tool(self, tool_call) -> ToolResult:
        """执行单个工具调用（重写以更新上下文）
        
        Args:
            tool_call: 工具调用
            
        Returns:
            工具执行结果
        """
        # 调用父类方法
        result = await super()._execute_single_tool(tool_call)
        
        # 更新 SQL 上下文
        if result.success:
            if tool_call.name == "extract_database_schema":
                self._sql_context["schema_info"] = result.result
            elif tool_call.name == "analyze_business_domain":
                self._sql_context["domain_analysis"] = result.result
            elif tool_call.name == "classify_table_fields":
                self._sql_context["field_classifications"] = result.result
            elif tool_call.name == "analyze_entity_relationships":
                self._sql_context["relationships"] = result.result
            elif tool_call.name == "generate_sql":
                self._sql_context["generated_sql"] = result.result
            elif tool_call.name == "validate_sql":
                self._sql_context["validation_result"] = result.result
            elif tool_call.name == "execute_sql":
                self._sql_context["execution_result"] = result.result
        
        return result
    
    async def query(self, question: str, **kwargs) -> QueryResult:
        """执行查询的便捷方法
        
        Args:
            question: 用户问题
            **kwargs: 额外参数
            
        Returns:
            查询结果
        """
        # 创建任务
        self.new_task(question, extra_args=kwargs)
        
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