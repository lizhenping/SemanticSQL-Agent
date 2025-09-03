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
from tools.analysis_tools.field_classification_tool import FieldClassificationTool
from tools.analysis_tools.column_meaning_tool import ColumnMeaningTool
from tools.analysis_tools.table_meaning_tool import TableMeaningTool
from tools.analysis_tools.er_analysis_tool import ERAnalysisTool

from tools.generation_tools.scenario_tool import ScenarioTool
from tools.generation_tools.operation_selection_tool import OperationSelectionTool
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
                FieldClassificationTool(llm=self.llm, db_manager=self.db_manager),
                ColumnMeaningTool(llm=self.llm),
                TableMeaningTool(llm=self.llm),
                ERAnalysisTool(llm=self.llm, db_manager=self.db_manager),
            ]
        )

        # 生成工具
        tools.extend(
            [
                ScenarioTool(),
                OperationSelectionTool(),
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

    def analyze_database(self, database_name: str) -> Dict[str, Any]:
        """执行数据库分析"""
        self.logger.info(f"Starting database analysis for: {database_name}")

        # 构建分析任务 - 让 Agent 自主决定执行流程
        analysis_task = self.prompt_manager.render_template(
            "analysis/database_analysis.j2",
            database_name=database_name
        )

        result = self.run(analysis_task)

        if result["success"]:
            # 获取分析结果
            memory_state = self.get_memory_state()
            return {
                "success": True,
                "analysis": memory_state.get("db_analysis", {}),
                "message": "数据库分析完成",
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "分析失败"),
                "message": "数据库分析失败",
            }

    def generate_training_data(
        self, count: int, output_file: str, database_name: Optional[str] = None
    ) -> TrainingDataResult:
        """生成训练数据"""
        self.logger.info(f"Starting training data generation: {count} examples")

        # 如果指定了数据库，先执行分析
        if database_name:
            analysis_result = self.analyze_database(database_name)
            if not analysis_result["success"]:
                raise AgentExecutionError(
                    step="database_analysis", reason=analysis_result["error"]
                )

        # 构建生成任务
        generation_task = self.prompt_manager.render_template(
            "generation/training_data_generation.j2",
            count=count
        )

        # 执行生成任务
        result = self.run(generation_task)

        if not result["success"]:
            raise AgentExecutionError(
                step="generation", reason=result.get("error", "生成失败")
            )

        # 处理生成结果
        try:
            # 从 Agent 输出中提取生成的数据
            output = result.get("result", {})
            generated_examples = self._extract_generated_examples(output)

            # 保存到文件
            self._save_training_data(generated_examples, output_file)

            # 创建结果对象
            training_result = TrainingDataResult(
                total=count,
                successful=len(generated_examples),
                failed=count - len(generated_examples),
                output_file=output_file,
                examples=generated_examples[:5],  # 只返回前5个示例
            )

            self.logger.info(
                f"Generation completed: {training_result.successful}/{count} successful"
            )

            return training_result

        except Exception as e:
            raise AgentExecutionError(
                step="post_processing",
                reason=f"Failed to process generation results: {str(e)}",
            )

    def _extract_generated_examples(self, agent_output: Any) -> List[Dict[str, Any]]:
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

                    if tool == "scenario_tool":
                        current_scenario = {
                            "id": tool_output.get("scenario_id", ""),
                            "category": tool_output.get("category", ""),
                            "business_purpose": tool_output.get("business_purpose", ""),
                            "difficulty": tool_output.get("complexity", "medium"),
                        }
                    elif tool == "operation_selection":
                        current_example["operations"] = tool_output.get(
                            "selected_operations", []
                        )
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
