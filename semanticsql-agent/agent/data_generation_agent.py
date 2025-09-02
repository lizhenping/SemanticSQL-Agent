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
        
        # 构建分析任务（遵循设计文档的执行顺序）
        analysis_task = f"""
        请对数据库 {database_name} 执行完整的分析流程。按照以下顺序执行：
        
        **步骤1**: 使用 schema_extraction 提取数据库结构
        - 参数: {{"database_name": "{database_name}"}}
        
        **步骤2**: 使用 domain_analysis 分析业务领域  
        - 参数: {{"memory": {{"schema_info": <步骤1的结果>}}}}
        
        **步骤3**: 使用 field_classification 对字段进行语义分类
        - 参数: {{"memory": {{
            "schema_info": <步骤1的结果>,
            "domain_info": <步骤2的结果>
          }}}}
        
        **步骤4**: 使用 column_meaning_analysis 分析每个列的业务含义
        - 参数: {{"memory": {{
            "schema_info": <步骤1的结果>,
            "domain_info": <步骤2的结果>,
            "field_classification": <步骤3的结果>
          }}}}
        
        **步骤5**: 使用 table_meaning_analysis 分析每个表的业务职责
        - 参数: {{"memory": {{
            "schema_info": <步骤1的结果>,
            "domain_info": <步骤2的结果>,
            "field_classification": <步骤3的结果>,
            "column_meanings": <步骤4的结果>
          }}}}
        
        **步骤6**: 使用 er_analysis 分析表之间的实体关系
        - 参数: {{"memory": {{
            "schema_info": <步骤1的结果>,
            "domain_info": <步骤2的结果>,
            "field_classification": <步骤3的结果>,
            "column_meanings": <步骤4的结果>,
            "table_meanings": <步骤5的结果>
          }}}}
        
        **重要说明**：
        1. 每个工具会返回自己的分析结果
        2. 后续工具需要通过memory参数接收之前所有步骤的结果
        3. memory参数的键名必须与上述格式一致
        4. 系统会自动保存每个工具的结果到内存中，但你也需要手动构建memory参数
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
        
        # 构建生成任务（强制执行工具序列）
        generation_task = f"""
        **任务目标**：生成 {count} 个高质量的 NL2SQL 训练数据
        
        **严格执行要求**：
        - 你必须依次调用每个工具，不能跳过任何步骤
        - 不允许提前给出 Final Answer
        - 每个样本必须完成全部7个步骤才能继续下一个
        - 不允许自行构造或假设工具结果

        ## 开始之前，先执行数据库分析（仅执行一次）：
        
        **必须首先执行：**
        1. schema_extraction - 提取数据库结构
        2. domain_analysis - 分析业务领域  
        3. column_meaning_analysis - 分析列含义
        4. table_meaning_analysis - 分析表含义
        5. er_analysis - 分析实体关系

        ## 现在开始样本生成！必须一步一步执行：

        **第1个训练样本开始：**
        
        现在执行步骤1/7: 调用 scenario_tool
        - 参数: {{"iteration": 0}}
        - 等待工具执行完成后再继续
        
        (执行完步骤1后，继续步骤2...)
        现在执行步骤2/7: 调用 operation_selection  
        - 使用scenario_tool的输出结果
        - 等待工具执行完成后再继续
        
        (执行完步骤2后，继续步骤3...)
        现在执行步骤3/7: 调用 question_generation
        - 使用前面步骤的结果
        - 等待工具执行完成后再继续
        
        (执行完步骤3后，继续步骤4...)
        现在执行步骤4/7: 调用 sql_generation
        - 使用前面步骤的结果
        - 等待工具执行完成后再继续
        
        (执行完步骤4后，继续步骤5...)
        现在执行步骤5/7: 调用 sql_validation
        - 验证步骤4生成的SQL
        - 等待工具执行完成后再继续
        
        (执行完步骤5后，继续步骤6...)
        现在执行步骤6/7: 调用 sql_execution
        - 执行步骤4生成的SQL
        - 等待工具执行完成后再继续
        
        (执行完步骤6后，继续步骤7...)
        现在执行步骤7/7: 调用 sql_reflection
        - 反思整体质量
        - 完成第1个样本

        **第2个训练样本开始：**
        重复上述7个步骤，iteration参数改为1...
        
        **继续剩余样本直到完成{count}个样本**

        ## 最终输出要求：
        - 只有在完成所有 {count} 个样本的7个步骤后，才能输出 Final Answer
        - Final Answer 必须是纯JSON数组格式，不要添加任何其他文本
        - 精确的输出格式：
        [
          {{
            "question": "自然语言问题",
            "sql": "SQL查询语句",
            "scenario_info": {{
              "scenario_id": "场景ID",
              "category": "场景类别",
              "complexity": "复杂度"
            }},
            "validation_result": {{
              "syntax_valid": true,
              "execution_result": "执行结果描述"
            }}
          }}
        ]

        **禁止行为：**
        - 禁止跳过任何工具调用
        - 禁止提前给出结果
        - 禁止自行构造工具输出
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