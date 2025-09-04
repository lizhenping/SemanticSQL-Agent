"""
SQL Agent - SQL 生成智能体
支持批量训练数据生成
"""

from typing import List, Dict, Any, Optional
import json
import logging
from datetime import datetime

from langchain.tools import BaseTool
from langchain_core.memory import BaseMemory
from langchain.callbacks.base import BaseCallbackHandler

from agent.base_agent import BaseAgent
from config.settings import Settings
from config.database import DatabaseConfig
from utils.memory import DatabaseAnalysisMemory
from utils.database import DatabaseManager
from models.training import TrainingDataResult
from models.exceptions import AgentExecutionError
from prompts.manager import PromptManager

# 导入所有工具
from tools.analysis_tools.schema_extraction_tool import SchemaExtractionTool
from tools.analysis_tools.domain_analysis_tool import DomainAnalysisTool
from tools.analysis_tools.field_analysis_tool import FieldAnalysisTool
from tools.analysis_tools.column_analysis_tool import ColumnAnalysisTool
from tools.analysis_tools.table_analysis_tool import TableAnalysisTool
from tools.analysis_tools.er_analysis_tool import ERAnalysisTool

from tools.generation_tools.scenario_operation_tool import ScenarioOperationTool
from tools.generation_tools.question_generation_tool import QuestionGenerationTool
from tools.generation_tools.sql_generation_tool import SQLGenerationTool

from tools.validation_tools.sql_validation_tool import SQLValidationTool
from tools.validation_tools.sql_execution_tool import SQLExecutionTool

from tools.reflection_tools.sql_reflection_tool import SQLReflectionTool
from tools.thinking_tools.sequential_thinking_tool import SequentialThinkingTool


class SQLAgent(BaseAgent):
    """SQL 生成智能体 - 支持批量训练数据生成"""

    def __init__(
        self,
        settings: Settings,
        db_config: DatabaseConfig,
        callbacks: Optional[List[BaseCallbackHandler]] = None,
    ):
        """初始化 SQL Agent

        Args:
            settings: 系统配置
            db_config: 数据库配置
            callbacks: LangChain 回调处理器列表
        """
        # 初始化数据库管理器
        self.db_manager = DatabaseManager(db_config)
        if not self.db_manager.initialize():
            raise AgentExecutionError(
                step="initialization", reason="Failed to initialize database connection"
            )

        # 保存额外的回调
        self.extra_callbacks = callbacks or []

        # 调用父类初始化
        super().__init__(settings, db_config)

        self.logger = logging.getLogger(__name__)
        self.prompt_manager = PromptManager()

    def _initialize_tools(self) -> List[BaseTool]:
        """初始化所有工具"""
        tools = []

        # 分析工具
        tools.extend(
            [
                SchemaExtractionTool(db_manager=self.db_manager),
                DomainAnalysisTool(llm=self.llm),
                FieldAnalysisTool(llm=self.llm, db_manager=self.db_manager),
                ColumnAnalysisTool(llm=self.llm),
                TableAnalysisTool(llm=self.llm),
                ERAnalysisTool(llm=self.llm, db_manager=self.db_manager),
            ]
        )

        # 生成工具
        tools.extend(
            [
                ScenarioOperationTool(),  # 合并的场景-操作工具
                QuestionGenerationTool(llm=self.llm),
                SQLGenerationTool(llm=self.llm, db_manager=self.db_manager),
            ]
        )

        # 验证工具
        tools.extend(
            [
                SQLValidationTool(db_manager=self.db_manager),
                SQLExecutionTool(db_manager=self.db_manager),
            ]
        )

        # 反思工具
        tools.extend(
            [SQLReflectionTool(llm=self.llm), SequentialThinkingTool(llm=self.llm)]
        )

        self.logger.info(f"Initialized {len(tools)} tools")
        return tools

    def _initialize_memory(self) -> BaseMemory:
        """初始化记忆系统"""
        return DatabaseAnalysisMemory()


    def generate_training_data(self, output_file: str = "training_data.jsonl") -> List[Dict[str, Any]]:
        """生成训练数据（完全由Agent自主驱动）"""
        self.logger.info("Starting training data generation (Agent自主模式)")

        # 极简的任务输入
        task = "请生成高质量的NL2SQL训练数据集，覆盖所有场景组合"

        # 完全交给Agent自主决策
        result = self.run(task)

        if not result["success"]:
            raise AgentExecutionError(
                step="generation", reason=result.get("error", "生成失败")
            )

        # 处理生成结果
        try:
            # 从Agent输出中提取所有生成的样本
            output = result.get("result", {})
            generated_examples = self._extract_all_samples(output)

            # 保存到文件
            self._save_training_data(generated_examples, output_file)

            self.logger.info(f"Generation completed: {len(generated_examples)} samples generated")
            return generated_examples

        except Exception as e:
            raise AgentExecutionError(
                step="post_processing",
                reason=f"Failed to process generation results: {str(e)}",
            )

    def _extract_all_samples(self, agent_output: Any) -> List[Dict[str, Any]]:
        """从 Agent 输出中提取生成的样例"""
        examples = []

        # 从执行轨迹中提取数据
        if hasattr(self.callback_handler, "get_trajectories"):
            trajectories = self.callback_handler.get_trajectories()

            # 解析轨迹，提取问题-SQL对
            current_example = {}
            current_scenario = {}

            for trajectory in trajectories:
                if trajectory["type"] == "action":
                    tool = trajectory["tool"]
                    tool_output = trajectory.get("output", {})

                    if tool == "scenario_operation_generation":
                        # 新的合并工具处理
                        if "combinations" in tool_output:
                            # 处理get_all_combinations模式的输出
                            current_example["all_combinations"] = tool_output.get("combinations", [])
                            current_example["total_combinations"] = tool_output.get("total_combinations", 0)
                        elif "combination" in tool_output:
                            # 处理get_single_combination模式的输出
                            combo = tool_output.get("combination", {})
                            current_scenario = {
                                "id": combo.get("combination_id", ""),
                                "category": combo.get("scenario", {}).get("main_name", ""),
                                "business_purpose": combo.get("scenario", {}).get("main_description", ""),
                                "difficulty": combo.get("scenario", {}).get("complexity", "medium"),
                            }
                            current_example["operations"] = combo.get("operations", [])
                    elif tool == "question_generation":
                        current_example["question"] = tool_output.get("question", "")
                        current_example["scenario"] = current_scenario
                    elif tool == "sql_generation":
                        current_example["sql"] = tool_output.get("sql", "")
                        current_example["tables"] = tool_output.get("tables_used", [])
                    elif tool == "sql_validation":
                        if "validation" not in current_example:
                            current_example["validation"] = {}
                        current_example["validation"]["syntax_valid"] = tool_output.get(
                            "valid", False
                        )
                    elif tool == "sql_execution":
                        if "validation" not in current_example:
                            current_example["validation"] = {}
                        current_example["validation"]["execution_success"] = (
                            tool_output.get("success", False)
                        )
                        current_example["validation"]["row_count"] = tool_output.get(
                            "row_count", 0
                        )
                        if tool_output.get("data"):
                            current_example["validation"]["result_sample"] = (
                                tool_output["data"][:3]
                            )
                    elif tool == "sql_reflection":
                        current_example["quality_score"] = tool_output.get(
                            "overall_score", 0.0
                        )

                        # 如果反思通过，保存样例
                        if (
                            not tool_output.get("needs_revision", True)
                            and "question" in current_example
                            and "sql" in current_example
                        ):
                            # 格式化样例
                            formatted_example = self._format_training_example(
                                current_example
                            )
                            examples.append(formatted_example)
                            # 重置当前样例
                            current_example = {}

        return examples

    def _format_training_example(self, raw_example: Dict[str, Any]) -> Dict[str, Any]:
        """格式化训练样例以符合API规范"""
        import uuid

        return {
            "id": f"q_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}",
            "scenario": raw_example.get("scenario", {}),
            "question": raw_example.get("question", ""),
            "sql": raw_example.get("sql", ""),
            "operations": raw_example.get("operations", []),
            "tables": raw_example.get("tables", []),
            "timestamp": datetime.now().isoformat(),
            "validation": raw_example.get(
                "validation",
                {"syntax_valid": False, "execution_success": False, "row_count": 0},
            ),
            "quality_score": raw_example.get("quality_score", 0.0),
        }

    def _save_training_data(self, examples: List[Dict[str, Any]], output_file: str):
        """保存训练数据到文件"""
        with open(output_file, "w", encoding="utf-8") as f:
            if output_file.endswith(".jsonl"):
                # JSONL 格式
                for example in examples:
                    f.write(json.dumps(example, ensure_ascii=False) + "\n")
            else:
                # JSON 格式
                json.dump(examples, f, ensure_ascii=False, indent=2)

        self.logger.info(f"Saved {len(examples)} examples to {output_file}")

    def __del__(self):
        """清理资源"""
        if hasattr(self, "db_manager") and self.db_manager:
            self.db_manager.close()
