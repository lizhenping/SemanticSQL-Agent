"""
SQL Agent - SQL 生成智能体
支持批量训练数据生成
"""

from typing import List, Dict, Any, Optional
import json
import logging
from datetime import datetime

from langchain.tools import BaseTool
from langchain.memory import BaseMemory

from agent.base_agent import BaseAgent
from config.settings import Settings
from config.database import DatabaseConfig
from utils.memory import DatabaseAnalysisMemory
from utils.database import DatabaseManager
from models.schemas import TrainingDataResult
from models.exceptions import AgentExecutionError

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
    
    def __init__(self, settings: Settings, db_config: DatabaseConfig):
        """初始化 SQL Agent"""
        # 初始化数据库管理器
        self.db_manager = DatabaseManager(db_config)
        if not self.db_manager.initialize():
            raise AgentExecutionError(
                step="initialization",
                reason="Failed to initialize database connection"
            )
        
        # 调用父类初始化
        super().__init__(settings, db_config)
        
        self.logger = logging.getLogger(__name__)
    
    def _initialize_tools(self) -> List[BaseTool]:
        """初始化所有工具"""
        tools = []
        
        # 分析工具
        tools.extend([
            SchemaExtractionTool(db_manager=self.db_manager),
            DomainAnalysisTool(),
            FieldClassificationTool(),
            ColumnMeaningTool(),
            TableMeaningTool(),
            ERAnalysisTool()
        ])
        
        # 生成工具
        tools.extend([
            ScenarioTool(),
            OperationSelectionTool(),
            QuestionGenerationTool(llm=self.llm),
            SQLGenerationTool(llm=self.llm, db_manager=self.db_manager)
        ])
        
        # 验证工具
        tools.extend([
            SQLValidationTool(db_manager=self.db_manager),
            SQLExecutionTool(db_manager=self.db_manager)
        ])
        
        # 反思工具
        tools.extend([
            SQLReflectionTool(llm=self.llm),
            SequentialThinkingTool(llm=self.llm)
        ])
        
        self.logger.info(f"Initialized {len(tools)} tools")
        return tools
    
    def _initialize_memory(self) -> BaseMemory:
        """初始化记忆系统"""
        return DatabaseAnalysisMemory()
    
    def analyze_database(self, database_name: str) -> Dict[str, Any]:
        """执行数据库分析"""
        self.logger.info(f"Starting database analysis for: {database_name}")
        
        # 构建分析任务
        analysis_task = f"""
        请对数据库 {database_name} 执行完整的分析：
        1. 使用 schema_extraction 提取数据库结构
        2. 使用 domain_analysis 分析业务领域
        3. 使用 field_classification 对字段进行分类
        4. 使用 column_meaning_analysis 分析列的业务含义
        5. 使用 table_meaning_analysis 分析表的业务含义
        6. 使用 er_analysis 分析实体关系
        
        请按顺序执行这些分析，并将结果保存到记忆中。
        """
        
        result = self.run(analysis_task)
        
        if result["success"]:
            # 获取分析结果
            memory_state = self.get_memory_state()
            return {
                "success": True,
                "analysis": memory_state.get("db_analysis", {}),
                "message": "数据库分析完成"
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "分析失败"),
                "message": "数据库分析失败"
            }
    
    def generate_training_data(
        self, 
        count: int, 
        output_file: str,
        database_name: Optional[str] = None
    ) -> TrainingDataResult:
        """生成训练数据"""
        self.logger.info(f"Starting training data generation: {count} examples")
        
        # 如果指定了数据库，先执行分析
        if database_name:
            analysis_result = self.analyze_database(database_name)
            if not analysis_result["success"]:
                raise AgentExecutionError(
                    step="database_analysis",
                    reason=analysis_result["error"]
                )
        
        # 构建生成任务
        generation_task = f"""
        请生成 {count} 个高质量的 SQL 训练数据：
        
        1. 对于每个训练样本，执行以下步骤：
           - 使用 scenario_tool 选择一个场景
           - 使用 operation_selection 根据场景选择合适的 SQL 操作
           - 使用 question_generation 生成自然语言问题
           - 使用 sql_generation 生成对应的 SQL 查询
           - 使用 sql_validation 验证 SQL 语法
           - 使用 sql_execution 执行 SQL 测试
           - 使用 sql_reflection 反思生成质量
        
        2. 如果反思发现问题：
           - 分析问题来源（problem_source）
           - 根据建议（recommended_action）调用相应工具修正
           - 重新执行有问题的步骤
        
        3. 每生成一个成功的样本，保存到结果列表中
        
        请确保生成的问题和 SQL 具有多样性，覆盖不同的场景和操作类型。
        """
        
        # 执行生成任务
        result = self.run(generation_task)
        
        if not result["success"]:
            raise AgentExecutionError(
                step="generation",
                reason=result.get("error", "生成失败")
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
                examples=generated_examples[:5]  # 只返回前5个示例
            )
            
            self.logger.info(
                f"Generation completed: {training_result.successful}/{count} successful"
            )
            
            return training_result
            
        except Exception as e:
            raise AgentExecutionError(
                step="post_processing",
                reason=f"Failed to process generation results: {str(e)}"
            )
    
    def _extract_generated_examples(self, agent_output: Any) -> List[Dict[str, Any]]:
        """从 Agent 输出中提取生成的样例"""
        # 这里需要根据实际的 Agent 输出格式来解析
        # 目前返回空列表，实际实现需要解析 agent_output
        examples = []
        
        # TODO: 实现实际的解析逻辑
        # 可能需要从执行轨迹中提取生成的问题和SQL对
        
        return examples
    
    def _save_training_data(self, examples: List[Dict[str, Any]], output_file: str):
        """保存训练数据到文件"""
        with open(output_file, 'w', encoding='utf-8') as f:
            if output_file.endswith('.jsonl'):
                # JSONL 格式
                for example in examples:
                    f.write(json.dumps(example, ensure_ascii=False) + '\n')
            else:
                # JSON 格式
                json.dump(examples, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"Saved {len(examples)} examples to {output_file}")
    
    def __del__(self):
        """清理资源"""
        if hasattr(self, 'db_manager') and self.db_manager:
            self.db_manager.close()