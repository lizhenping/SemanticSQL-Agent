"""
SQL Agent - SQL 生成智能体
优化版本：单一职责，类型安全，无状态设计
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json
import logging
import uuid
from datetime import datetime

from langchain.tools import BaseTool
from langchain_core.memory import BaseMemory
from langchain.callbacks.base import BaseCallbackHandler

from agent.base_agent import BaseAgent
from config.settings import Settings
from utils.database_config import DatabaseConfig
from utils.memory import DatabaseAnalysisMemory
from utils.database import DatabaseManager
from models.training import TrainingDataResult
from models.exceptions import AgentExecutionError
from prompts.manager import PromptManager

# 工具导入（按类别分组）
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


# ========== 类型安全的数据容器 ==========
@dataclass
class TrainingExample:
    """训练样例数据结构"""
    id: str
    scenario: Dict[str, Any]
    question: str
    sql: str
    operations: List[str]
    tables: List[str]
    timestamp: str
    validation: Dict[str, Any]
    quality_score: float


@dataclass
class ServiceContainer:
    """类型安全的服务容器"""
    database_manager: DatabaseManager
    prompt_manager: PromptManager
    settings: Settings


class SQLAgent(BaseAgent):
    """SQL 生成智能体 - 专注于 SQL 生成和工具协调
    
    职责：
    - 管理和协调各种分析和生成工具
    - 执行 SQL 生成工作流
    - 提供统一的工具访问接口
    
    设计原则：
    - 单一职责：只负责工具协调和 SQL 生成
    - 无状态设计：通过参数传递数据而非存储状态
    - 类型安全：使用强类型容器而非字典
    """

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
        # 初始化服务容器
        self.services = self._create_service_container(settings, db_config)
        
        # 保存额外回调
        self.extra_callbacks = callbacks or []
        
        # 调用父类初始化
        super().__init__(settings, db_config)
        
        # 创建训练数据生成器（委托模式）
        self.training_generator = TrainingDataGenerator(self)
        
        self.logger = logging.getLogger(__name__)
    
    def _create_service_container(self, settings: Settings, db_config: DatabaseConfig) -> ServiceContainer:
        """创建类型安全的服务容器"""
        db_manager = DatabaseManager(db_config)
        if not db_manager.initialize():
            raise AgentExecutionError(
                step="initialization", 
                reason="Failed to initialize database connection"
            )
        
        return ServiceContainer(
            database_manager=db_manager,
            prompt_manager=PromptManager(),
            settings=settings
        )

    # ========== 工具管理（按功能分组）==========
    def _initialize_tools(self) -> List[BaseTool]:
        """初始化所有工具 - 使用服务容器统一管理依赖"""
        analysis_tools = self._create_analysis_tools()
        generation_tools = self._create_generation_tools()
        validation_tools = self._create_validation_tools()
        reflection_tools = self._create_reflection_tools()
        
        all_tools = analysis_tools + generation_tools + validation_tools + reflection_tools
        self.logger.info(f"Initialized {len(all_tools)} tools")
        return all_tools
    
    def _create_analysis_tools(self) -> List[BaseTool]:
        """创建分析工具集"""
        return [
            SchemaExtractionTool(db_manager=self.services.database_manager),
            DomainAnalysisTool(llm=self.llm),
            FieldAnalysisTool(llm=self.llm, db_manager=self.services.database_manager),
            ColumnAnalysisTool(llm=self.llm),
            TableAnalysisTool(llm=self.llm),
            ERAnalysisTool(llm=self.llm, db_manager=self.services.database_manager),
        ]
    
    def _create_generation_tools(self) -> List[BaseTool]:
        """创建生成工具集"""
        return [
            ScenarioOperationTool(),
            QuestionGenerationTool(llm=self.llm),
            SQLGenerationTool(llm=self.llm, db_manager=self.services.database_manager),
        ]
    
    def _create_validation_tools(self) -> List[BaseTool]:
        """创建验证工具集"""
        return [
            SQLValidationTool(db_manager=self.services.database_manager),
            SQLExecutionTool(db_manager=self.services.database_manager),
        ]
    
    def _create_reflection_tools(self) -> List[BaseTool]:
        """创建反思工具集"""
        return [
            SQLReflectionTool(llm=self.llm),
            SequentialThinkingTool(llm=self.llm)
        ]

    def _initialize_memory(self) -> BaseMemory:
        """初始化记忆系统"""
        return DatabaseAnalysisMemory()
    
    # ========== 训练数据生成接口 ==========
    def generate_training_data(self, output_file: str = "training_data.jsonl") -> List[Dict[str, Any]]:
        """生成训练数据 - 委托给专门的生成器
        
        Args:
            output_file: 输出文件路径
            
        Returns:
            生成的训练样例列表
        """
        return self.training_generator.generate_training_data(output_file)
    
    # ========== 资源清理 ==========
    def __del__(self):
        """清理资源"""
        if hasattr(self, "services") and self.services and self.services.database_manager:
            self.services.database_manager.close()


class TrainingDataGenerator:
    """训练数据生成器 - 专门负责训练数据的生成和处理
    
    职责：
    - 从 Agent 执行结果中提取训练样例
    - 格式化和验证训练数据
    - 保存训练数据到文件
    
    设计原则：
    - 单一职责：只处理训练数据相关逻辑
    - 类型安全：使用强类型数据结构
    - 方法拆分：每个方法不超过30行
    """
    
    def __init__(self, agent: SQLAgent):
        """初始化训练数据生成器
        
        Args:
            agent: SQL Agent 实例
        """
        self.agent = agent
        self.logger = logging.getLogger(__name__ + '.TrainingDataGenerator')
    
    def generate_training_data(self, output_file: str = "training_data.jsonl") -> List[Dict[str, Any]]:
        """生成训练数据主流程
        
        Args:
            output_file: 输出文件路径
            
        Returns:
            生成的训练样例列表
        """
        self.logger.info("Starting training data generation (Agent自主模式)")
        
        # 执行生成任务
        agent_result = self._execute_generation_task()
        
        # 提取和处理样例
        examples = self._process_generation_result(agent_result)
        
        # 保存到文件
        self._save_training_data(examples, output_file)
        
        self.logger.info(f"Generation completed: {len(examples)} samples generated")
        return examples
    
    def _execute_generation_task(self) -> Dict[str, Any]:
        """执行Agent生成任务"""
        task = "请生成高质量的NL2SQL训练数据集，覆盖所有场景组合"
        result = self.agent.run(task)
        
        if not result["success"]:
            raise AgentExecutionError(
                step="generation", 
                reason=result.get("error", "生成失败")
            )
        
        return result
    
    def _process_generation_result(self, agent_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """处理Agent生成结果"""
        output = agent_result.get("result", {})
        return self._extract_all_samples(output)

    # ========== 样例提取和处理（按流程顺序拆分）==========
    def _extract_all_samples(self, agent_output: Any) -> List[Dict[str, Any]]:
        """从 Agent 输出中提取生成的样例 - 主协调方法"""
        if not hasattr(self.agent.callback_handler, "get_trajectories"):
            return []
        
        trajectories = self.agent.callback_handler.get_trajectories()
        return self._parse_trajectories(trajectories)
    
    def _parse_trajectories(self, trajectories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """解析执行轨迹，提取训练样例"""
        examples = []
        current_example = {}
        current_scenario = {}
        
        for trajectory in trajectories:
            if trajectory["type"] == "action":
                tool_name = trajectory["tool"]
                tool_output = trajectory.get("output", {})
                
                # 更新当前样例和场景
                self._process_tool_output(
                    tool_name, tool_output, current_example, current_scenario
                )
                
                # 检查是否完成一个样例
                if self._is_example_complete(tool_name, tool_output, current_example):
                    formatted_example = self._format_training_example(current_example)
                    examples.append(formatted_example)
                    current_example = {}  # 重置
        
        return examples
    
    def _process_tool_output(
        self, 
        tool_name: str, 
        tool_output: Dict[str, Any], 
        current_example: Dict[str, Any], 
        current_scenario: Dict[str, Any]
    ) -> None:
        """处理单个工具的输出"""
        if tool_name == "scenario_operation_generation":
            self._process_scenario_output(tool_output, current_example, current_scenario)
        elif tool_name == "question_generation":
            self._process_question_output(tool_output, current_example, current_scenario)
        elif tool_name == "sql_generation":
            self._process_sql_output(tool_output, current_example)
        elif tool_name == "sql_validation":
            self._process_validation_output(tool_output, current_example)
        elif tool_name == "sql_execution":
            self._process_execution_output(tool_output, current_example)
        elif tool_name == "sql_reflection":
            self._process_reflection_output(tool_output, current_example)
    
    def _process_scenario_output(
        self, 
        tool_output: Dict[str, Any], 
        current_example: Dict[str, Any], 
        current_scenario: Dict[str, Any]
    ) -> None:
        """处理场景生成工具输出"""
        if "combinations" in tool_output:
            # 处理get_all_combinations模式
            current_example["all_combinations"] = tool_output.get("combinations", [])
            current_example["total_combinations"] = tool_output.get("total_combinations", 0)
        elif "combination" in tool_output:
            # 处理get_single_combination模式
            combo = tool_output.get("combination", {})
            scenario_info = combo.get("scenario", {})
            current_scenario.update({
                "id": combo.get("combination_id", ""),
                "category": scenario_info.get("main_name", ""),
                "business_purpose": scenario_info.get("main_description", ""),
                "difficulty": scenario_info.get("complexity", "medium"),
            })
            current_example["operations"] = combo.get("operations", [])
    
    def _process_question_output(
        self, 
        tool_output: Dict[str, Any], 
        current_example: Dict[str, Any], 
        current_scenario: Dict[str, Any]
    ) -> None:
        """处理问题生成工具输出"""
        current_example["question"] = tool_output.get("question", "")
        current_example["scenario"] = current_scenario.copy()
    
    def _process_sql_output(self, tool_output: Dict[str, Any], current_example: Dict[str, Any]) -> None:
        """处理SQL生成工具输出"""
        current_example["sql"] = tool_output.get("sql", "")
        current_example["tables"] = tool_output.get("tables_used", [])
    
    def _process_validation_output(self, tool_output: Dict[str, Any], current_example: Dict[str, Any]) -> None:
        """处理SQL验证工具输出"""
        if "validation" not in current_example:
            current_example["validation"] = {}
        current_example["validation"]["syntax_valid"] = tool_output.get("valid", False)
    
    def _process_execution_output(self, tool_output: Dict[str, Any], current_example: Dict[str, Any]) -> None:
        """处理SQL执行工具输出"""
        if "validation" not in current_example:
            current_example["validation"] = {}
        
        validation = current_example["validation"]
        validation["execution_success"] = tool_output.get("success", False)
        validation["row_count"] = tool_output.get("row_count", 0)
        
        if tool_output.get("data"):
            validation["result_sample"] = tool_output["data"][:3]
    
    def _process_reflection_output(self, tool_output: Dict[str, Any], current_example: Dict[str, Any]) -> None:
        """处理SQL反思工具输出"""
        current_example["quality_score"] = tool_output.get("overall_score", 0.0)
    
    def _is_example_complete(
        self, 
        tool_name: str, 
        tool_output: Dict[str, Any], 
        current_example: Dict[str, Any]
    ) -> bool:
        """检查当前样例是否完整"""
        # 反思工具输出后，检查是否应该保存样例
        if tool_name == "sql_reflection":
            needs_revision = tool_output.get("needs_revision", True)
            has_question = "question" in current_example
            has_sql = "sql" in current_example
            return not needs_revision and has_question and has_sql
        
        return False

    # ========== 数据格式化和保存 ==========
    def _format_training_example(self, raw_example: Dict[str, Any]) -> Dict[str, Any]:
        """格式化训练样例为标准格式"""
        return {
            "id": self._generate_example_id(),
            "scenario": raw_example.get("scenario", {}),
            "question": raw_example.get("question", ""),
            "sql": raw_example.get("sql", ""),
            "operations": raw_example.get("operations", []),
            "tables": raw_example.get("tables", []),
            "timestamp": datetime.now().isoformat(),
            "validation": self._get_default_validation(raw_example),
            "quality_score": raw_example.get("quality_score", 0.0),
        }
    
    def _generate_example_id(self) -> str:
        """生成唯一的样例ID"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        unique_suffix = uuid.uuid4().hex[:8]
        return f"q_{timestamp}_{unique_suffix}"
    
    def _get_default_validation(self, raw_example: Dict[str, Any]) -> Dict[str, Any]:
        """获取默认验证结果"""
        default = {
            "syntax_valid": False, 
            "execution_success": False, 
            "row_count": 0
        }
        return raw_example.get("validation", default)

    def _save_training_data(self, examples: List[Dict[str, Any]], output_file: str) -> None:
        """保存训练数据到文件
        
        Args:
            examples: 训练样例列表
            output_file: 输出文件路径
        """
        with open(output_file, "w", encoding="utf-8") as f:
            if output_file.endswith(".jsonl"):
                self._save_as_jsonl(f, examples)
            else:
                self._save_as_json(f, examples)
        
        self.logger.info(f"Saved {len(examples)} examples to {output_file}")
    
    def _save_as_jsonl(self, file_handle, examples: List[Dict[str, Any]]) -> None:
        """保存为JSONL格式"""
        for example in examples:
            file_handle.write(json.dumps(example, ensure_ascii=False) + "\n")
    
    def _save_as_json(self, file_handle, examples: List[Dict[str, Any]]) -> None:
        """保存为JSON格式"""
        json.dump(examples, file_handle, ensure_ascii=False, indent=2)