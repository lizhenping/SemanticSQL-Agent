"""
DataGenerationAgent - NL2SQL 训练数据生成智能体
基于 LangChain 的 ReAct 模式实现
"""

from typing import List, Dict, Any, Optional
import json
import logging
from datetime import datetime

from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import BaseTool
from langchain_core.memory import BaseMemory
from langchain.callbacks.base import BaseCallbackHandler

from agent.base_agent import BaseAgent
from config.settings import Settings
from config.database import DatabaseConfig
from utils.memory import DatabaseAnalysisMemory
from utils.database import DatabaseManager
from models.schemas import TrainingDataResult, GeneratedExample
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


class DataGenerationAgent(BaseAgent):
    """NL2SQL 训练数据生成智能体
    
    基于 LangChain 的 ReAct 模式，实现自主决策的训练数据生成流程。
    核心特性：
    - 使用 LangChain AgentExecutor 管理执行流程
    - 自定义 DatabaseAnalysisMemory 存储分析结果
    - 所有工具继承自 langchain.tools.BaseTool
    - 反思-修正循环确保数据质量
    """
    
    def __init__(self, settings: Settings, db_config: DatabaseConfig, 
                 callbacks: Optional[List[BaseCallbackHandler]] = None):
        """初始化 DataGenerationAgent
        
        Args:
            settings: 系统配置
            db_config: 数据库配置
            callbacks: LangChain 回调处理器列表
        """
        # 初始化数据库管理器
        self.db_manager = DatabaseManager(db_config)
        if not self.db_manager.initialize():
            raise AgentExecutionError(
                step="initialization",
                reason="Failed to initialize database connection"
            )
        
        # 保存额外的回调
        self.extra_callbacks = callbacks or []
        
        # 调用父类初始化
        super().__init__(settings, db_config)
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("DataGenerationAgent initialized successfully")
    
    def _initialize_tools(self) -> List[BaseTool]:
        """初始化所有工具"""
        tools = []
        
        # 分析工具（按设计文档顺序）
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
        
        self.logger.info(f"Initialized {len(tools)} tools for DataGenerationAgent")
        return tools
    
    def _initialize_memory(self) -> BaseMemory:
        """初始化记忆系统"""
        return DatabaseAnalysisMemory()
    
    def analyze_database(self, database_name: str) -> Dict[str, Any]:
        """执行数据库分析阶段
        
        Args:
            database_name: 数据库名称
            
        Returns:
            分析结果
        """
        self.logger.info(f"Starting database analysis for: {database_name}")
        
        # 构建分析任务（引导性而非强制性）
        analysis_task = f"""
        请对数据库 {database_name} 进行全面分析，以便后续生成高质量的训练数据。
        
        ## 分析目标
        你需要深入理解这个数据库的结构、业务含义和数据关系。使用以下工具进行分析：
        
        1. **schema_extraction** - 首先获取数据库的基础结构
           - 参数: {{"database_name": "{database_name}"}}
           - 这将给你表、列、数据类型等基础信息
        
        2. **domain_analysis** - 理解这是什么业务领域
           - 需要基于数据库结构来判断业务类型
           - 将schema信息作为memory传入
        
        3. **field_classification** - 对字段进行语义分类
           - 识别ID字段、时间字段、金额字段等
           - 需要结合schema和domain的理解
        
        4. **column_meaning_analysis** - 分析每列的具体业务含义
           - 不仅要知道字段类型，还要理解业务用途
           - 基于前面的分析结果进行深入理解
        
        5. **table_meaning_analysis** - 理解每个表的业务职责
           - 识别核心业务表、辅助表、字典表等
           - 需要综合前面对列的理解
        
        6. **er_analysis** - 分析表之间的关系
           - 发现显式和隐式的关联
           - 理解数据流向和业务流程
        
        ## 执行建议
        - 这些分析工具相互依赖，后面的工具需要前面工具的结果
        - 通过memory参数传递累积的分析结果
        - 如果某个分析有疑问，可以使用 sequential_thinking 进行深度思考
        - 分析结果会自动保存，供后续数据生成使用
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
        """生成训练数据
        
        Args:
            count: 生成数据条数
            output_file: 输出文件路径
            database_name: 数据库名称（可选，如果未提供则使用已分析的数据库）
            
        Returns:
            TrainingDataResult: 生成结果统计
        """
        self.logger.info(f"Starting training data generation: {count} examples")
        
        # 检查是否需要执行数据库分析
        if database_name or not self.memory.has_complete_analysis():
            # 如果指定了数据库名或记忆中没有完整分析，执行分析
            target_db = database_name or self.db_manager.config.database
            analysis_result = self.analyze_database(target_db)
            if not analysis_result["success"]:
                raise AgentExecutionError(
                    step="database_analysis",
                    reason=analysis_result["error"]
                )
        
        # 构建生成任务（引导但不硬编码）
        generation_task = f"""
        **任务目标**：生成 {count} 个高质量的 NL2SQL 训练数据

        ## 第一阶段：数据库理解（如果还没有分析过）
        
        在生成训练数据之前，你需要全面理解数据库。使用以下分析工具：
        - **schema_extraction**: 获取数据库的完整结构信息（表、列、约束等）
        - **domain_analysis**: 理解这是什么业务领域的数据库
        - **column_meaning_analysis**: 分析每个列的业务含义和用途
        - **table_meaning_analysis**: 理解每个表的业务职责
        - **er_analysis**: 分析表之间的关系
        
        这些分析只需要做一次，结果会保存在记忆中供后续使用。

        ## 第二阶段：训练数据生成
        
        对于每个训练样本，你需要：
        
        1. **选择场景**：使用 scenario_tool 从预定义的业务场景中选择一个
           - 传入 iteration 参数（从0开始递增）来确保场景的多样性
        
        2. **确定操作**：使用 operation_selection 根据场景复杂度选择合适的SQL操作
           - 简单场景使用基础查询
           - 复杂场景可能需要JOIN、聚合或子查询
        
        3. **生成问题**：使用 question_generation 创建自然语言问题
           - 结合场景、操作和你对数据库的理解
           - 确保问题清晰、符合实际业务需求
        
        4. **生成SQL**：使用 sql_generation 生成对应的SQL查询
           - 基于问题和你的数据库知识
           - 确保SQL准确实现问题的意图
        
        5. **验证质量**：
           - 使用 sql_validation 检查SQL语法
           - 使用 sql_execution 实际执行SQL
           - 使用 sql_reflection 评估整体质量
        
        ## 第三阶段：反思与优化
        
        如果 sql_reflection 发现问题：
        - **需要深入分析时**：使用 sequential_thinking 分析问题根源
        - **问题不够清晰**：重新使用 question_generation
        - **SQL有误**：重新使用 sql_generation
        - **理解有偏差**：可能需要重新运行某个分析工具
        
        记住：
        - 每个样本都应该独立且高质量
        - 充分利用你对数据库的理解
        - 如果遇到复杂决策，使用 sequential_thinking 帮助分析
        - 生成 {count} 个样本后，以JSON数组格式输出所有结果

        ## 输出格式要求：
        最终输出必须是标准的JSON数组，每个元素包含：
        {{
          "question": "自然语言问题",
          "sql": "SQL查询语句",
          "scenario_info": {{
            "scenario_id": "场景ID",
            "category": "场景类别",
            "complexity": "复杂度"
          }},
          "validation_result": {{
            "syntax_valid": true/false,
            "execution_result": "结果描述"
          }}
        }}
        - 禁止在未完成所有步骤时给出 Final Answer

        ## 错误修正机制：
        如果任何步骤失败：
        1. 使用 sequential_thinking 分析问题
        2. 重新执行失败的步骤
        3. 继续后续步骤

        **现在开始执行！第一步：schema_extraction**
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
            # 从 Agent 最终输出中提取生成的数据
            generated_examples = self._extract_from_agent_output(result)
            
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
    
    def _extract_from_agent_output(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从Agent输出中提取训练样本"""
        examples = []
        
        try:
            # 从result中获取输出 - 修正字段名
            output = result.get("result", "")
            
            # 处理字符串输出（直接JSON格式）
            if isinstance(output, str):
                import json
                
                self.logger.debug(f"Processing string output: {output[:200]}...")
                
                # 尝试直接解析为JSON（Agent现在直接输出JSON格式）
                try:
                    parsed_output = json.loads(output)
                    self.logger.debug(f"Successfully parsed JSON output, type: {type(parsed_output)}")
                    
                    if isinstance(parsed_output, list):
                        # 处理直接的JSON数组
                        for item in parsed_output:
                            if isinstance(item, dict) and "question" in item and "sql" in item:
                                examples.append(item)
                                self.logger.debug(f"Successfully extracted training sample: {item.get('question', '')[:50]}...")
                    elif isinstance(parsed_output, dict):
                        # 处理包含training_samples的JSON对象
                        if "training_samples" in parsed_output:
                            for item in parsed_output["training_samples"]:
                                if isinstance(item, dict) and "question" in item and "sql" in item:
                                    examples.append(item)
                                    self.logger.debug(f"Successfully extracted training sample: {item.get('question', '')[:50]}...")
                        # 处理sample_1, sample_2等键值格式
                        elif any(key.startswith('sample_') for key in parsed_output.keys()):
                            for key, item in parsed_output.items():
                                if key.startswith('sample_') and isinstance(item, dict) and "question" in item and "sql" in item:
                                    examples.append(item)
                                    self.logger.debug(f"Successfully extracted training sample from {key}: {item.get('question', '')[:50]}...")
                        elif "question" in parsed_output and "sql" in parsed_output:
                            # 处理单个JSON对象
                            examples.append(parsed_output)
                            self.logger.debug(f"Successfully extracted training sample: {parsed_output.get('question', '')[:50]}...")
                            
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Failed to parse output as JSON: {e}")
                    # 尝试解析markdown格式
                    markdown_examples = self._extract_from_markdown(output)
                    if markdown_examples:
                        return markdown_examples
                    # 回退到轨迹提取
                    return self._extract_generated_examples()
                    
            # 处理字典输出
            elif isinstance(output, dict) and "question" in output and "sql" in output:
                examples.append(output)
                
            self.logger.info(f"Extracted {len(examples)} training examples from agent output")
            
        except Exception as e:
            self.logger.error(f"Failed to extract examples from agent output: {e}")
            # 回退到轨迹提取
            return self._extract_generated_examples()
            
        return examples
    
    def _extract_from_markdown(self, output: str) -> List[Dict[str, Any]]:
        """从markdown格式输出中提取训练样本"""
        examples = []
        import re
        
        try:
            # 匹配markdown格式的问题和SQL
            pattern = r'\*\*问题\*\*:\s*(.+?)\s*\*\*SQL\*\*:\s*(.+?)\s*\*\*场景信息\*\*:\s*(.+?)\s*\*\*验证结果\*\*:\s*(.+?)(?=\d+\.|$)'
            matches = re.findall(pattern, output, re.DOTALL)
            
            for match in matches:
                question = match[0].strip()
                sql = match[1].strip()
                scenario = match[2].strip()
                validation = match[3].strip()
                
                if question and sql:
                    example = {
                        "question": question,
                        "sql": sql,
                        "scenario_info": {"category": scenario, "complexity": "medium"},
                        "validation_result": {"syntax_valid": True, "execution_result": validation}
                    }
                    examples.append(example)
                    self.logger.debug(f"Successfully extracted training sample from markdown: {question[:50]}...")
            
            self.logger.info(f"Extracted {len(examples)} training examples from markdown format")
            return examples
            
        except Exception as e:
            self.logger.error(f"Failed to extract examples from markdown: {e}")
            return []
    
    def _extract_generated_examples(self) -> List[Dict[str, Any]]:
        """从 Agent 执行轨迹中提取生成的样例"""
        examples = []
        
        # 从执行轨迹中提取数据
        if hasattr(self.callback_handler, 'get_trajectories'):
            trajectories = self.callback_handler.get_trajectories()
            
            # 解析轨迹，提取问题-SQL对
            current_example = {}
            current_scenario = {}
            
            for trajectory in trajectories:
                if trajectory.get('type') == 'tool_end':
                    tool_name = trajectory.get('tool_name', '')
                    tool_output = trajectory.get('output', {})
                    
                    # 解析工具输出
                    if isinstance(tool_output, str):
                        try:
                            tool_output = json.loads(tool_output)
                        except:
                            continue
                    
                    if tool_name == 'scenario_tool':
                        current_scenario = {
                            'id': tool_output.get('scenario_id', ''),
                            'category': tool_output.get('category', ''),
                            'business_purpose': tool_output.get('business_purpose', ''),
                            'complexity': tool_output.get('complexity', 'medium')
                        }
                        current_example = {'scenario': current_scenario}
                        
                    elif tool_name == 'operation_selection':
                        current_example['operations'] = tool_output.get('selected_operations', [])
                        
                    elif tool_name == 'question_generation':
                        current_example['question'] = tool_output.get('question', '')
                        
                    elif tool_name == 'sql_generation':
                        current_example['sql'] = tool_output.get('sql', '')
                        current_example['tables'] = tool_output.get('tables_used', [])
                        
                    elif tool_name == 'sql_validation':
                        if 'validation' not in current_example:
                            current_example['validation'] = {}
                        current_example['validation']['syntax_valid'] = tool_output.get('valid', False)
                        
                    elif tool_name == 'sql_execution':
                        if 'validation' not in current_example:
                            current_example['validation'] = {}
                        current_example['validation']['execution_success'] = tool_output.get('success', False)
                        current_example['validation']['row_count'] = tool_output.get('row_count', 0)
                        if tool_output.get('data'):
                            current_example['validation']['result_sample'] = tool_output['data'][:3]
                            
                    elif tool_name == 'sql_reflection':
                        current_example['quality_score'] = tool_output.get('overall_score', 0.0)
                        
                        # 如果反思通过，保存样例
                        if (not tool_output.get('needs_revision', True) and 
                            'question' in current_example and 
                            'sql' in current_example and
                            current_example.get('question') and 
                            current_example.get('sql')):
                            
                            # 格式化样例
                            formatted_example = self._format_training_example(current_example)
                            examples.append(formatted_example)
                            self.logger.debug(f"Added training example: {formatted_example['id']}")
                            
                            # 重置当前样例
                            current_example = {}
        
        self.logger.info(f"Extracted {len(examples)} training examples from trajectories")
        return examples
    
    def _format_training_example(self, raw_example: Dict[str, Any]) -> Dict[str, Any]:
        """格式化训练样例以符合标准格式"""
        import uuid
        
        return {
            "id": f"q_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}",
            "scenario": raw_example.get("scenario", {}),
            "question": raw_example.get("question", ""),
            "sql": raw_example.get("sql", ""),
            "operations": raw_example.get("operations", []),
            "tables": raw_example.get("tables", []),
            "timestamp": datetime.now().isoformat(),
            "validation": raw_example.get("validation", {
                "syntax_valid": False,
                "execution_success": False,
                "row_count": 0
            }),
            "quality_score": raw_example.get("quality_score", 0.0)
        }
    
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
    
    def get_analysis_summary(self) -> Dict[str, Any]:
        """获取数据库分析摘要"""
        memory_state = self.get_memory_state()
        db_analysis = memory_state.get("db_analysis", {})
        
        summary = {
            "has_schema": bool(db_analysis.get("schema_info")),
            "has_domain": bool(db_analysis.get("domain_info")),
            "has_classification": bool(db_analysis.get("field_classification")),
            "has_column_meanings": bool(db_analysis.get("column_meanings")),
            "has_table_meanings": bool(db_analysis.get("table_meanings")),
            "has_er_analysis": bool(db_analysis.get("er_relations")),
            "total_tables": 0,
            "total_columns": 0
        }
        
        schema_info = db_analysis.get("schema_info", {})
        if schema_info:
            tables = schema_info.get("tables", {})
            summary["total_tables"] = len(tables)
            summary["total_columns"] = sum(
                len(table.get("columns", [])) 
                for table in tables.values()
            )
        
        return summary
    
    def validate_memory_state(self) -> Dict[str, Any]:
        """验证记忆状态是否完整"""
        summary = self.get_analysis_summary()
        
        required_analyses = [
            "has_schema", "has_domain", "has_classification",
            "has_column_meanings", "has_table_meanings", "has_er_analysis"
        ]
        
        missing_analyses = [
            analysis for analysis in required_analyses 
            if not summary.get(analysis, False)
        ]
        
        return {
            "is_complete": len(missing_analyses) == 0,
            "missing_analyses": missing_analyses,
            "summary": summary
        }
    
    def __del__(self):
        """清理资源"""
        if hasattr(self, 'db_manager') and self.db_manager:
            self.db_manager.close()