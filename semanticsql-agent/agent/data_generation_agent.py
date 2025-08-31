"""
DataGenerationAgent - 智能体驱动的NL2SQL训练数据生成
基于ReAct模式，让Agent自主决策生成流程
"""

import json
import logging
from typing import Dict, Any, List, Optional

from .base_agent import BaseAgent
from config.settings import Settings
from config.database import DatabaseConfig
from utils.database import DatabaseManager
from models.schemas import GeneratedExample, TrainingExample

# 导入完整工具链
from tools.analysis_tools.schema_extraction_tool import SchemaExtractionTool
from tools.analysis_tools.domain_analysis_tool import DomainAnalysisTool
from tools.analysis_tools.field_classification_tool import FieldClassificationTool
from tools.analysis_tools.er_analysis_tool import ERAnalysisTool

from tools.generation_tools.scenario_tool import ScenarioTool
from tools.generation_tools.question_generation_tool import QuestionGenerationTool
from tools.generation_tools.sql_generation_tool import SQLGenerationTool
from tools.generation_tools.operation_selection_tool import OperationSelectionTool

from tools.validation_tools.sql_validation_tool import SQLValidationTool
from tools.validation_tools.sql_execution_tool import SQLExecutionTool

from tools.reflection_tools.sql_reflection_tool import SQLReflectionTool

from tools.thinking_tools.sequential_thinking_tool import SequentialThinkingTool


class DataGenerationAgent(BaseAgent):
    """
    完整的训练数据生成Agent
    
    核心特点：
    1. 提示词驱动：通过精心设计的提示词引导Agent步骤
    2. 自主决策：Agent根据情况自主决定工具调用顺序
    3. 反思循环：执行后反思，发现问题时自主回退修正
    4. 记忆机制：数据库分析结果贯穿整个过程
    5. 完整工具链：分析、生成、验证、反思、思考工具
    """
    
    def __init__(self, settings: Settings, db_config: DatabaseConfig):
        """Initialize DataGeneration Agent"""
        # Initialize database manager BEFORE calling super().__init__
        self.db_manager = DatabaseManager(db_config)
        if not self.db_manager.initialize():
            raise Exception("Failed to initialize database connection")
        
        # Track generated data
        self.training_examples = []
        
        # Initialize memory storage for analysis results
        self.memory = {
            "schema_info": None,  # Database schema information
            "domain_analysis": None,  # Domain analysis results
            "field_classification": None,  # Field classification results
            "er_analysis": None,  # Entity relationship analysis
            "current_scenario": None,  # Current generation scenario
        }
        
        # Call parent initialization
        super().__init__(settings, db_config)
    
    def _initialize_tools(self):
        """初始化完整工具链 - 所有分析、生成、验证、反思、思考工具"""
        
        # === 分析工具 ===
        schema_tool = SchemaExtractionTool(self.settings)
        schema_tool.set_database_manager(self.db_manager)
        self.register_tool("extract_schema", schema_tool, 
                          "提取完整数据库结构，包括表、列、索引、约束信息")
        
        domain_tool = DomainAnalysisTool(self.settings)
        self.register_tool("domain_analysis", domain_tool,
                          "基于表名和字段名分析业务领域特征")
        
        field_tool = FieldClassificationTool(self.settings)
        self.register_tool("field_classification", field_tool,
                          "对数据库字段进行语义分类，识别字段含义和类型")
        
        er_tool = ERAnalysisTool(self.settings)
        self.register_tool("er_analysis", er_tool,
                          "分析表之间的实体关系，识别主外键和隐式关联")
        
        # === 生成工具 ===
        scenario_tool = ScenarioTool(self.settings)
        self.register_tool("scenario_generation", scenario_tool,
                          "基于领域分析结果生成业务查询场景")
        
        operation_tool = OperationSelectionTool(self.settings)
        self.register_tool("operation_selection", operation_tool,
                          "选择SQL操作类型和复杂度级别")
        
        question_tool = QuestionGenerationTool(self.settings)
        self.register_tool("question_generation", question_tool,
                          "基于场景生成自然语言问题")
        
        sql_gen_tool = SQLGenerationTool(self.settings)
        self.register_tool("sql_generation", sql_gen_tool,
                          "根据问题和数据库结构生成SQL查询")
        
        # === 验证工具 ===
        validation_tool = SQLValidationTool(self.settings)
        self.register_tool("sql_validation", validation_tool,
                          "验证SQL语法和逻辑正确性")
        
        execution_tool = SQLExecutionTool(self.db_manager)
        self.register_tool("sql_execution", execution_tool,
                          "执行SQL查询并获取结果，验证可行性")
        
        # === 反思工具 ===
        reflection_tool = SQLReflectionTool(self.settings)
        self.register_tool("sql_reflection", reflection_tool,
                          "根据SQL执行结果进行反思分析，评估质量并提出改进建议")
        
        # === 思考工具 ===
        thinking_tool = SequentialThinkingTool(self.settings)
        self.register_tool("sequential_thinking", thinking_tool,
                          "在复杂情况下进行深度思考和分析")
    
    def get_system_prompt(self) -> str:
        """
        使用完整的系统提示词模板
        """
        from jinja2 import Template
        
        # 读取模板文件
        template_path = "/root/autodl-tmp/nl2sql/NL2SQL/trae-agent/semanticsql-agent/prompts/templates/system/agent_system.j2"
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            template = Template(template_content)
            return template.render(
                tools=self.tool_descriptions,
                database_name=self.db_config.database,
                table_count="未知(需要extract_schema分析)",
                current_task="NL2SQL训练数据生成"
            )
        except Exception as e:
            self.logger.error(f"加载系统提示词模板失败: {e}")
            # 降级到简化版本
            tools_desc = "\n".join([
                f"- **{name}**: {desc}" 
                for name, desc in self.tool_descriptions.items()
            ])
            
            return f"""你是NL2SQL训练数据生成专家。

可用工具：
{tools_desc}

执行原则：
1. 先完整分析数据库并记忆结果
2. 基于分析结果生成问题和SQL
3. 执行SQL验证并反思
4. 发现问题时回退修正

数据库: {self.db_config.database}

开始执行！"""
    
    def _execute_action(self, action: str, action_input: Optional[Dict]) -> Any:
        """Override to handle memory storage and injection"""
        
        # Inject memory into action_input for tools that need it
        if action == "domain_analysis" and self.memory["schema_info"]:
            if action_input is None:
                action_input = {}
            action_input["schema_info"] = self.memory["schema_info"]
        
        elif action == "field_classification" and self.memory["schema_info"]:
            if action_input is None:
                action_input = {}
            # FieldClassificationTool expects 'table_info' for a single table
            # If no specific table is specified, use the first table as example
            schema_data = self.memory["schema_info"]
            if isinstance(schema_data, dict) and "tables" in schema_data:
                tables = schema_data["tables"]
                if tables:
                    # Use first table if no specific table specified
                    table_name = list(tables.keys())[0]
                    action_input["table_info"] = tables[table_name]
            else:
                # Fallback: pass schema_info as table_info
                action_input["table_info"] = schema_data
        
        elif action == "er_analysis" and self.memory["schema_info"]:
            if action_input is None:
                action_input = {}
            action_input["schema_info"] = self.memory["schema_info"]
        
        elif action == "sequential_thinking":
            if action_input is None:
                action_input = {}
            # Inject all available memory as context
            if "context" not in action_input:
                action_input["context"] = {
                    "schema": self.memory["schema_info"],
                    "domain": self.memory["domain_analysis"],
                    "fields": self.memory["field_classification"],
                    "relationships": self.memory["er_analysis"]
                }
        
        # Execute the action
        result = super()._execute_action(action, action_input)
        
        # Store results in memory
        if action == "extract_schema" and result.get("success"):
            self.memory["schema_info"] = result.get("data")
            self.logger.info("Schema information stored in memory")
        
        elif action == "domain_analysis" and result.get("success"):
            self.memory["domain_analysis"] = result.get("data")
            self.logger.info("Domain analysis stored in memory")
        
        elif action == "field_classification" and result.get("success"):
            self.memory["field_classification"] = result.get("data")
            self.logger.info("Field classification stored in memory")
        
        elif action == "er_analysis" and result.get("success"):
            self.memory["er_analysis"] = result.get("data")
            self.logger.info("ER analysis stored in memory")
        
        return result
    
    def generate_training_data(self, count: int, output_file: str) -> Dict[str, Any]:
        """
        生成训练数据 - 完全由Agent自主执行
        无硬编码步骤，所有决策由Agent基于提示词做出
        """
        task = f"生成{count}条高质量NL2SQL训练数据。数据库：{self.db_config.database}。要求：1)先完整分析数据库并记忆；2)生成SQL后必须执行验证；3)执行后必须反思，发现问题时回退修正；4)复杂情况调用思考工具。输出文件：{output_file}"
        
        # Agent自主执行 - 进入ReAct循环
        execution = self.new_task(task)
        
        # 提取生成的训练数据
        training_data = self._extract_training_data_from_execution(execution)
        
        # 保存结果
        if training_data:
            self._save_training_data(training_data, output_file)
        else:
            # 创建空文件
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump([], f)
        
        return {
            'total_generated': len(training_data),
            'output_file': output_file,
            'execution_steps': len(execution.steps),
            'task_id': execution.task_id
        }
    
    def _extract_training_data_from_execution(self, execution) -> List[Dict[str, Any]]:
        """从Agent执行轨迹中提取训练数据"""
        training_data = []
        
        for step in execution.steps:
            # 从成功的sql_generation工具调用中提取数据
            if (step.tool_name == "sql_generation" and 
                step.tool_input and 
                step.tool_output and 
                isinstance(step.tool_output, dict) and 
                step.tool_output.get('success')):
                
                try:
                    # 从工具输入获取问题
                    question = step.tool_input.get('question', '')
                    
                    # 从工具输出获取SQL
                    sql_data = step.tool_output.get('data', {})
                    sql = sql_data.get('sql', '') if isinstance(sql_data, dict) else str(sql_data)
                    
                    if question and sql:
                        training_data.append({
                            'question': question,
                            'sql': sql,
                            'database_id': self.db_config.database
                        })
                        self.logger.info(f"提取到训练数据: {question} -> {sql[:50]}...")
                        
                except Exception as e:
                    self.logger.warning(f"提取训练数据失败: {e}")
                    continue
        
        return training_data
    
    def _save_training_data(self, data: List[Dict[str, Any]], output_file: str):
        """保存训练数据"""
        import os
        os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"训练数据已保存到: {output_file}")
    
    def close(self):
        """关闭连接"""
        if hasattr(self, 'db_manager') and self.db_manager:
            self.db_manager.close()