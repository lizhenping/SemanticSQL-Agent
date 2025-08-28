"""优化后的 SQL 智能体（基于 trae_agent 设计）

使用工具注册表和模块化设计模式。
"""

import logging
from typing import List, Optional, Dict, Any, override

from ..utils.config import SQLAgentConfig
from ..utils.shared_types import QueryResult
from ..utils.llm_clients import LLMClient, LLMMessage
from ..tools import tools_registry, Tool
from .base_agent import BaseAgent
from .agent_basics import AgentExecution, AgentState, AgentStep

logger = logging.getLogger(__name__)

# 默认的 SQL Agent 工具集
SQLAgentToolNames = [
    "schema_extraction",
    "domain_analysis", 
    "field_classification",
    "er_analysis",
    "sql_generation",
    "sql_validation",
    "sql_execution",
    "sequential_thinking"
]


class SQLAgentV2(BaseAgent):
    """优化后的 SQL 查询智能体"""
    
    def __init__(self, config: SQLAgentConfig):
        """初始化 SQL 智能体
        
        Args:
            config: SQL 智能体配置
        """
        # 从配置中提取工具列表
        tool_names = config.tools if config.tools else SQLAgentToolNames
        
        # 使用工具注册表创建工具实例
        tools = self._create_tools_from_registry(tool_names, config)
        
        # 初始化基类
        super().__init__(
            llm_client=LLMClient(config.model),
            tools=tools,
            max_steps=config.max_steps,
            verbose=config.verbose
        )
        
        self._config = config
        self._sql_context: Dict[str, Any] = {}
        
        logger.info(f"SQL 智能体 V2 初始化完成，加载了 {len(tools)} 个工具")
    
    def _create_tools_from_registry(
        self, 
        tool_names: List[str], 
        config: SQLAgentConfig
    ) -> List[Tool]:
        """从工具注册表创建工具实例"""
        tools = []
        
        for tool_name in tool_names:
            if tool_name not in tools_registry:
                logger.warning(f"工具 {tool_name} 未在注册表中找到，跳过")
                continue
            
            try:
                # 获取工具类
                tool_class = tools_registry[tool_name]
                
                # 准备工具初始化参数
                tool_kwargs = {}
                
                # 某些工具需要数据库配置
                if tool_name in ["schema_extraction", "sql_execution", "sql_validation"]:
                    tool_kwargs["db_config"] = config.database
                
                # 某些工具需要 LLM 客户端
                if tool_name in ["domain_analysis", "field_classification", 
                               "er_analysis", "sql_generation", "sequential_thinking"]:
                    tool_kwargs["llm_client"] = LLMClient(config.model)
                
                # 创建工具实例
                tool = tool_class(**tool_kwargs)
                tools.append(tool)
                
                logger.debug(f"成功创建工具: {tool_name}")
                
            except Exception as e:
                logger.error(f"创建工具 {tool_name} 失败: {e}")
        
        return tools
    
    @override
    def _get_system_prompt(self, task: str) -> str:
        """获取系统提示词"""
        tool_descriptions = "\n".join([
            f"- {tool.name}: {tool.description}"
            for tool in self._tools.values()
        ])
        
        return f"""你是一个专业的 SQL 查询助手，负责将自然语言问题转换为 SQL 查询。

你的任务是：{task}

可用的工具：
{tool_descriptions}

工作流程：
1. 首先使用 schema_extraction 工具提取数据库结构
2. 使用 domain_analysis 工具分析业务领域
3. 如果需要，使用 field_classification 和 er_analysis 工具深入分析
4. 使用 sequential_thinking 工具进行深度思考
5. 使用 sql_generation 工具生成 SQL
6. 使用 sql_validation 工具验证 SQL
7. 如果用户需要，使用 sql_execution 工具执行 SQL

请始终：
- 仔细分析用户需求
- 生成准确、高效的 SQL
- 考虑数据库性能
- 提供清晰的解释
"""
    
    @override
    def _process_tool_results(
        self, 
        tool_results: List[Any],
        step: AgentStep
    ) -> None:
        """处理工具结果，更新 SQL 上下文"""
        super()._process_tool_results(tool_results, step)
        
        # 更新 SQL 特定上下文
        for tool_call, result in zip(step.tool_calls, tool_results):
            if result.success:
                context_mapping = {
                    "schema_extraction": ("schema_info", result.content),
                    "domain_analysis": ("domain_analysis", result.content),
                    "field_classification": ("field_classifications", result.content),
                    "er_analysis": ("relationships", result.content),
                    "sql_generation": ("generated_sql", result.content),
                    "sql_validation": ("validation_result", result.content),
                    "sql_execution": ("execution_result", result.content)
                }
                
                if tool_call.name in context_mapping:
                    key, value = context_mapping[tool_call.name]
                    self._sql_context[key] = value
                    logger.debug(f"更新 SQL 上下文: {key}")
    
    @override
    def _check_task_completion(
        self,
        step: AgentStep,
        execution: AgentExecution
    ) -> bool:
        """检查任务是否完成"""
        # 如果成功执行了 SQL
        if "execution_result" in self._sql_context:
            result = self._sql_context["execution_result"]
            if isinstance(result, dict) and result.get("success"):
                return True
        
        # 如果只需要生成 SQL（不执行）
        if "generated_sql" in self._sql_context:
            task_lower = execution.task.lower()
            if ("生成" in task_lower or "generate" in task_lower) and \
               ("执行" not in task_lower and "execute" not in task_lower):
                return True
        
        return False
    
    def _extract_final_result(self, execution: AgentExecution) -> QueryResult:
        """提取最终查询结果"""
        # 构建自然语言回答
        answer = self._build_answer()
        
        return QueryResult(
            success=execution.agent_state == AgentState.SUCCESS,
            question=execution.task,
            sql=self._sql_context.get("generated_sql"),
            answer=answer,
            execution_result=self._sql_context.get("execution_result"),
            steps=len(execution.steps)
        )
    
    def _build_answer(self) -> Optional[str]:
        """构建自然语言回答"""
        # 如果有执行结果
        exec_result = self._sql_context.get("execution_result")
        if exec_result:
            if isinstance(exec_result, dict) and exec_result.get("success"):
                row_count = exec_result.get("row_count", 0)
                return f"查询执行成功，返回 {row_count} 条结果。"
            else:
                error = exec_result.get("error", "未知错误") if isinstance(exec_result, dict) else "未知错误"
                return f"查询执行失败: {error}"
        
        # 如果只生成了 SQL
        if "generated_sql" in self._sql_context:
            return "SQL 查询已生成。"
        
        return None
    
    def query(self, question: str, **kwargs) -> QueryResult:
        """执行查询的便捷方法
        
        Args:
            question: 自然语言查询问题
            **kwargs: 额外参数
            
        Returns:
            QueryResult: 查询结果
        """
        # 执行任务
        execution = self.execute_task(question)
        
        # 提取并返回结果
        if execution.agent_state == AgentState.SUCCESS:
            return self._extract_final_result(execution)
        else:
            return QueryResult(
                success=False,
                question=question,
                error=execution.error or "查询执行失败",
                steps=len(execution.steps)
            )
    
    def reset(self) -> None:
        """重置智能体状态"""
        self._sql_context.clear()
        logger.debug("SQL 上下文已重置")