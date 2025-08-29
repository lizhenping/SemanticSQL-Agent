"""
SmartSQLAgent - 基于ReAct模式的智能数据库分析Agent
完全重写为真正的智能体架构
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from .base_agent import BaseAgent, AgentExecution
from tools.agent_tools import (
    DatabaseConnectionTool,
    SchemaAnalysisTool, 
    QueryGenerationTool,
    QueryExecutionTool,
    DataAnalysisTool,
    ReasoningTool,
    DomainAnalysisTool
)
from config.trae_config import TraeConfig
from models.sql_result import SQLQueryResult


class SmartSQLAgent(BaseAgent):
    """智能SQL分析Agent - 使用ReAct模式进行数据库分析"""
    
    def __init__(self, config: TraeConfig):
        """初始化智能SQL Agent"""
        super().__init__(config)
        self.logger = logging.getLogger("SmartSQLAgent")
        
        # 存储当前分析上下文
        self.current_database_info = None
        self.current_schema_info = None
        self.analysis_results = {}
        
    def _initialize_tools(self):
        """初始化智能体工具"""
        # 注册所有可用的工具
        self.register_tool(
            "connect_database",
            DatabaseConnectionTool(self.config),
            "连接数据库并获取基本信息"
        )
        
        self.register_tool(
            "analyze_schema", 
            SchemaAnalysisTool(self.config),
            "分析数据库表结构和字段信息"
        )
        
        self.register_tool(
            "generate_sql",
            QueryGenerationTool(self.config, self.llm_client),
            "根据自然语言问题生成SQL查询"
        )
        
        self.register_tool(
            "execute_sql",
            QueryExecutionTool(self.config),
            "执行SQL查询并返回结果"
        )
        
        self.register_tool(
            "analyze_data",
            DataAnalysisTool(self.config, self.llm_client),
            "分析查询结果数据并提供洞察"
        )
        
        self.register_tool(
            "reasoning",
            ReasoningTool(self.config, self.llm_client),
            "进行推理思考，规划下一步行动"
        )
        
        self.register_tool(
            "analyze_domain",
            DomainAnalysisTool(self.config, self.llm_client),
            "分析数据库的业务领域和应用场景"
        )
    
    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        tools_desc = "\n".join([
            f"- {name}: {desc}" 
            for name, desc in self.tool_descriptions.items()
        ])
        
        return f"""# 智能数据库分析Agent

你是一个专业的数据库分析专家，能够：
1. 连接和分析各种数据库系统
2. 理解自然语言查询并生成SQL
3. 执行查询并分析结果
4. 提供业务洞察和建议

## 可用工具
{tools_desc}

## 工作流程
请遵循ReAct (Reasoning + Acting) 模式：

1. **Observation**: 观察当前状态和用户需求
2. **Thought**: 思考需要采取什么行动
3. **Action**: 选择并执行合适的工具
4. **Observation**: 观察工具执行结果
5. 重复直到任务完成

## 响应格式
请严格按照以下格式响应：

```
Thought: 我需要[你的思考过程]
Action: [工具名称]
Action Input: {{"参数名": "参数值"}}
```

**重要**: Action后面只能是确切的工具名称！

## 可用工具名称（严格使用）
- connect_database  
- analyze_schema
- generate_sql
- execute_sql
- analyze_data
- reasoning  
- analyze_domain

## 注意事项
- 始终先连接数据库获取基本信息
- 根据实际情况灵活选择分析策略
- 在执行SQL前先分析相关表结构
- 为用户提供清晰的分析结果和建议
- 如果遇到错误，尝试其他方法或工具
- Action必须是上述工具名称之一，不能是中文描述或句子

开始分析吧！"""

    def smart_analyze(self, user_request: str = "请分析这个数据库系统") -> Dict[str, Any]:
        """智能分析入口 - 保持兼容性"""
        execution = self.new_task(user_request)
        
        # 转换为兼容的结果格式
        result = {
            "success": execution.success,
            "task": execution.task,
            "steps_taken": execution.total_steps,
            "execution_time": execution.execution_time,
            "final_result": execution.final_result,
            "error": execution.error,
            "detailed_steps": [
                {
                    "type": step.step_type.value,
                    "content": step.content,
                    "tool": step.tool_name,
                    "timestamp": step.timestamp.isoformat()
                }
                for step in execution.steps
            ]
        }
        
        return result
    
    def query(self, question: str) -> SQLQueryResult:
        """简单查询功能 - 兼容性方法"""
        try:
            # 使用智能体执行查询任务
            execution = self.new_task(f"回答这个问题: {question}")
            
            if execution.success and execution.final_result:
                # 从执行结果中提取SQL查询信息
                sql = None
                data = []
                row_count = 0
                
                # 查找SQL执行步骤
                for step in execution.steps:
                    if step.tool_name == "execute_sql" and step.tool_output:
                        if step.tool_output.get("success"):
                            sql = step.tool_output.get("sql")
                            data = step.tool_output.get("results", [])
                            row_count = step.tool_output.get("row_count", 0)
                            break
                
                return SQLQueryResult(
                    success=True,
                    question=question,
                    sql=sql,
                    answer=str(execution.final_result),
                    data=data,
                    row_count=row_count,
                    execution_time=execution.execution_time,
                    steps=execution.total_steps
                )
            else:
                return SQLQueryResult(
                    success=False,
                    question=question,
                    error=execution.error or "任务执行失败",
                    steps=execution.total_steps
                )
                
        except Exception as e:
            self.logger.error(f"查询执行失败: {e}")
            return SQLQueryResult(
                success=False,
                question=question,
                error=str(e)
            )
    
    def _generate_final_result(self) -> Dict[str, Any]:
        """生成最终分析结果"""
        if not self.current_execution:
            return {"error": "没有执行记录"}
        
        # 收集所有工具的输出
        results = {
            "task_completed": True,
            "analysis_summary": {},
            "key_findings": [],
            "recommendations": []
        }
        
        # 从执行步骤中提取关键信息
        for step in self.current_execution.steps:
            if step.tool_output and step.tool_output.get("success"):
                
                if step.tool_name == "connect_database":
                    results["database_connection"] = step.tool_output.get("database_info")
                    
                elif step.tool_name == "analyze_schema":
                    results["schema_analysis"] = step.tool_output
                    
                elif step.tool_name == "analyze_domain":
                    results["domain_analysis"] = step.tool_output.get("domain_analysis")
                    
                elif step.tool_name == "execute_sql":
                    if "query_results" not in results:
                        results["query_results"] = []
                    results["query_results"].append({
                        "sql": step.tool_output.get("sql"),
                        "row_count": step.tool_output.get("row_count"),
                        "data_sample": step.tool_output.get("results", [])[:3]  # 只保留前3行作为样本
                    })
                    
                elif step.tool_name == "analyze_data":
                    if "data_insights" not in results:
                        results["data_insights"] = []
                    results["data_insights"].append(step.tool_output)
        
        # 生成总结
        if self.current_database_info:
            results["analysis_summary"] = {
                "database_name": self.current_database_info.get("database"),
                "total_tables": self.current_database_info.get("tables_count"),
                "database_type": self.current_database_info.get("type"),
                "analysis_completed": True
            }
        
        # 添加建议
        if results.get("domain_analysis"):
            results["recommendations"].append("建议基于识别的业务领域制定相应的数据管理策略")
            
        if results.get("query_results"):
            results["recommendations"].append("建议定期审查查询性能并优化慢查询")
        
        return results
    
    def _reflect_on_progress(self) -> Optional[str]:
        """反思当前进度"""
        if not self.current_execution or len(self.current_execution.steps) < 2:
            return None
        
        # 检查是否已连接数据库
        has_db_connection = any(
            step.tool_name == "connect_database" and 
            step.tool_output and step.tool_output.get("success")
            for step in self.current_execution.steps
        )
        
        # 检查是否已进行架构分析
        has_schema_analysis = any(
            step.tool_name == "analyze_schema"
            for step in self.current_execution.steps
        )
        
        if has_db_connection and not has_schema_analysis:
            return "我已成功连接数据库，接下来应该分析数据库架构以了解表结构"
            
        elif has_schema_analysis:
            # 检查是否有用户的具体查询需求
            user_task = self.current_execution.task.lower()
            if any(keyword in user_task for keyword in ["查询", "统计", "计算", "多少", "什么"]):
                return "我已了解数据库结构，现在应该专注于回答用户的具体问题"
            else:
                return "我已分析了数据库架构，可能需要进行业务领域分析或生成示例查询"
        
        return "让我评估当前进度，确保朝着正确方向前进"


# 为了保持向后兼容性，保留原有的SmartAnalysisResult类
class SmartAnalysisResult:
    """智能分析结果 - 兼容性类"""
    
    def __init__(self, execution: AgentExecution):
        self.success = execution.success
        self.execution_time = execution.execution_time
        self.error = execution.error
        self.final_result = execution.final_result
        self.steps_taken = execution.total_steps
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "execution_time": self.execution_time,
            "error": self.error,
            "final_result": self.final_result,
            "steps_taken": self.steps_taken
        }