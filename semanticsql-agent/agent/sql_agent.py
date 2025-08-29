"""
SQL智能体实现 - 同步版本
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from agent.base_agent import SyncBaseAgent as BaseAgent, AgentExecution, AgentStep
from agent.sql_result import SQLQueryResult
from config.trae_config import TraeConfig
from tools.sql_tools import (
    SyncSchemaExtractionTool as SchemaExtractionTool,
    SyncSQLGenerationTool as SQLGenerationTool,
    SyncSQLValidationTool as SQLValidationTool,
    SyncSQLExecutionTool as SQLExecutionTool
)
from tools.analysis_tools import (
    SyncDomainAnalysisTool as DomainAnalysisTool,
    SyncFieldClassificationTool as FieldClassificationTool,
    SyncERAnalysisTool as ERAnalysisTool,
    SyncSequentialThinkingTool as SequentialThinkingTool
)
from utils.llm_clients.llm_client import LLMClient


class SQLAgent(BaseAgent):
    """SQL智能体 - 同步版本"""
    
    def __init__(self, config: TraeConfig):
        """初始化SQL智能体"""
        self.config = config
        self.llm_client = LLMClient(
            model=config.llm.model,
            base_url=config.llm.base_url,
            api_key=config.llm.api_key,
            temperature=config.llm.temperature,
            max_tokens=config.llm.max_tokens
        )
        
        # 创建同步工具
        tools = self._create_sync_tools(config)
        
        super().__init__(
            name="SQLAgent",
            llm_client=self.llm_client,
            tools=tools,
            max_steps=config.agent.max_steps,
            verbose=config.agent.verbose,
            enable_trajectory=config.trajectory.enabled
        )
        
        self.logger = logging.getLogger("agent.sql")
        self.context = {}
    
    def _create_sync_tools(self, config: TraeConfig) -> List:
        """创建同步工具"""
        tools = []
        
        # 根据配置创建启用的工具
        enabled_tools = config.agent.enabled_tools or [
            "extract_schema",
            "generate_sql",
            "validate_sql",
            "execute_sql",
            "analyze_domain",
            "classify_fields",
            "analyze_relationships",
            "sequential_thinking"
        ]
        
        tool_map = {
            "extract_schema": lambda: SchemaExtractionTool(config.database),
            "generate_sql": lambda: SQLGenerationTool(config.database),
            "validate_sql": lambda: SQLValidationTool(config.database),
            "execute_sql": lambda: SQLExecutionTool(config.database),
            "analyze_domain": lambda: DomainAnalysisTool(config.database),
            "classify_fields": lambda: FieldClassificationTool(config.database),
            "analyze_relationships": lambda: ERAnalysisTool(config.database),
            "sequential_thinking": lambda: SequentialThinkingTool()
        }
        
        for tool_name in enabled_tools:
            if tool_name in tool_map:
                try:
                    tool = tool_map[tool_name]()
                    tools.append(tool)
                except Exception as e:
                    self.logger.error(f"创建工具 {tool_name} 失败: {e}")
        
        return tools
    
    def _build_system_message(self) -> str:
        """构建系统消息"""
        tools_info = []
        for tool in self.tools.values():
            tools_info.append(f"- {tool.name}: {tool.description}")
        
        return f"""你是专业的SQL查询助手，具备以下工具：

{chr(10).join(tools_info)}

你的任务是将自然语言查询转换为SQL，并执行查询返回结果。

工作流程：
1. 首先分析数据库结构和业务域
2. 根据用户需求生成合适的SQL查询
3. 验证SQL语法和逻辑
4. 执行查询并返回结果
5. 提供自然语言解释

要求：
- 始终使用中文进行思考
- 确保SQL查询安全且高效
- 提供清晰的查询结果解释
- 处理各种数据库类型和结构

数据库信息：
- 类型: {self.config.database.type}
- 数据库: {self.config.database.database}
- 主机: {self.config.database.host}:{self.config.database.port}"""
    
    def _is_task_complete(self, step: AgentStep, execution: AgentExecution) -> bool:
        """判断任务是否完成"""
        # 检查是否生成了SQL并执行成功
        for tool_result in step.tool_results:
            if tool_result.name == "execute_sql" and tool_result.success:
                return True
            elif tool_result.name == "generate_sql" and tool_result.success:
                # 如果只要求生成SQL，不执行
                if "生成" in execution.task and "执行" not in execution.task:
                    return True
        
        return False
    
    def _extract_final_result(self, execution: AgentExecution) -> SQLQueryResult:
        """提取最终结果"""
        sql = None
        data = None
        row_count = 0
        error = None
        
        # 从工具结果中提取信息
        for step in execution.steps:
            for tool_result in step.tool_results:
                if tool_result.name == "generate_sql" and tool_result.success:
                    sql = tool_result.output.get("sql")
                elif tool_result.name == "execute_sql" and tool_result.success:
                    data = tool_result.output.get("data", [])
                    row_count = tool_result.output.get("row_count", 0)
                elif not tool_result.success:
                    error = tool_result.error
        
        # 构建答案
        answer = self._build_answer(sql, data, row_count, error)
        
        return SQLQueryResult(
            success=execution.state.value == "completed",
            question=execution.task,
            sql=sql,
            answer=answer,
            data=data,
            row_count=row_count,
            execution_time=execution.execution_time,
            error=error,
            steps=len(execution.steps)
        )
    
    def _build_answer(self, sql: str, data: List[Dict[str, Any]], row_count: int, error: str) -> Optional[str]:
        """构建自然语言答案"""
        if error:
            return f"查询执行失败: {error}"
        
        if not sql:
            return "无法生成合适的SQL查询"
        
        if not data:
            return f"查询执行成功，但没有返回数据"
        
        # 根据数据构建答案
        if len(data) == 1:
            # 单条结果
            result = data[0]
            if len(result) == 1:
                # 单列结果
                value = list(result.values())[0]
                return f"查询结果为: {value}"
            else:
                # 多列结果
                return f"查询结果为: {json.dumps(result, ensure_ascii=False)}"
        else:
            # 多条结果
            return f"查询成功，共返回 {row_count} 条结果"
    
    def query(self, question: str, context: Optional[Dict[str, Any]] = None) -> SQLQueryResult:
        """执行查询的便捷方法"""
        execution = self.execute_task(question, context or {})
        return self._extract_final_result(execution)
    
    def query_with_sql(self, question: str, sql: str, context: Optional[Dict[str, Any]] = None) -> SQLQueryResult:
        """执行已知SQL的查询"""
        # 验证SQL
        validation_result = self.tools["validate_sql"].execute(sql=sql)
        if not validation_result["success"]:
            return SQLQueryResult(
                success=False,
                question=question,
                sql=sql,
                error=validation_result["error"]
            )
        
        # 执行SQL
        execution_result = self.tools["execute_sql"].execute(sql=sql)
        if not execution_result["success"]:
            return SQLQueryResult(
                success=False,
                question=question,
                sql=sql,
                error=execution_result["error"]
            )
        
        # 构建结果
        return SQLQueryResult(
            success=True,
            question=question,
            sql=sql,
            data=execution_result["data"]["data"],
            row_count=execution_result["data"]["row_count"],
            execution_time=execution_result["data"]["execution_time"]
        )
    
    def explain_schema(self, table_name: Optional[str] = None) -> Dict[str, Any]:
        """解释数据库Schema"""
        if table_name:
            result = self.tools["extract_schema"].execute(table_name=table_name)
        else:
            result = self.tools["extract_schema"].execute()
        
        return result
    
    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {
            "database": {
                "type": self.config.database.type,
                "host": self.config.database.host,
                "database": self.config.database.database
            },
            "llm": {
                "model": self.config.llm.model,
                "base_url": self.config.llm.base_url
            },
            "agent": {
                "max_steps": self.config.agent.max_steps,
                "verbose": self.config.agent.verbose
            }
        }