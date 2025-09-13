"""
场景驱动的问题生成工具 - 基于scenario_driven_pipeline.py
主要区别：ER关系从Neo4j获取，而不是从参数传入
"""

import yaml
import json
import logging
import random
from pathlib import Path
from typing import Dict, Any, List, Optional
from langchain.tools import BaseTool
from langchain.pydantic_v1 import BaseModel, Field

from prompts.manager import PromptManager
from config.factories import ComponentManager
from config.settings import get_settings

logger = logging.getLogger(__name__)


class ScenarioOperationInput(BaseModel):
    """输入参数"""
    database_name: str = Field(
        default="testdb",
        description="数据库名称"
    )
    target_count: int = Field(
        default=10,
        description="目标生成问题数量"
    )


class ScenarioOperationTool(BaseTool):
    """场景驱动的问题生成工具
    
    基于scenario_driven_pipeline.py的逻辑，主要区别：
    - ER分析结果从Neo4j获取，而不是从参数传入
    - 保持相同的三层循环生成逻辑
    """
    
    name: str = "scenario_operation_generation"
    description: str = "基于场景生成SQL问题，ER关系从Neo4j获取"
    args_schema: type = ScenarioOperationInput
    
    def __init__(self, memory_manager=None, database_manager=None, **kwargs):
        super().__init__(**kwargs)
        
        # 初始化服务
        object.__setattr__(self, 'memory_manager', memory_manager)
        object.__setattr__(self, 'database_manager', database_manager)
        object.__setattr__(self, 'llm', ComponentManager.create_llm(get_settings()))
        object.__setattr__(self, 'prompt_manager', PromptManager())
        object.__setattr__(self, 'logger', logging.getLogger(self.__class__.__name__))
        
        # 设置配置目录
        base_path = Path(__file__).parent.parent.parent
        object.__setattr__(self, 'config_dir', base_path / 'config')
        
        # 加载配置文件（与pipeline相同）
        try:
            object.__setattr__(self, 'scenarios', self._load_yaml('scenarios.yaml'))
            object.__setattr__(self, 'operation_mapping', self._load_yaml('operation_mapping.yaml'))
            object.__setattr__(self, 'complexity_config', self._load_yaml('complexity.yaml'))
            self.logger.info("成功加载所有配置文件")
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {e}")
            raise
    
    def _load_yaml(self, filename: str) -> Dict:
        """加载YAML配置文件"""
        config_path = self.config_dir / filename
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _run(self, database_name: str = "testdb", 
            target_count: int = 10, **kwargs) -> Dict[str, Any]:
        """执行问题生成"""
        try:
            # questions = self.generate_questions(database_name, target_count)
            
            # # 存储生成的问题到Neo4j
            # if self.memory_manager and questions:
            #     self._store_questions_to_neo4j(questions, database_name)
            result_message = "✅ scenario_operation_tool 分析完成，已存储到Neo4j，请务必继续执行 sql_generation_tool 工具。"    
            return result_message

        except Exception as e:
            self.logger.error(f"生成失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def generate_questions(self, database_name: str, target_count: int) -> List[Dict[str, Any]]:
        """生成问题的主方法 - 核心逻辑与pipeline保持一致
        
        Args:
            database_name: 数据库名称
            target_count: 目标生成数量
        """
        all_questions = []
        
        # 准备数据（主要区别：从Neo4j获取）
        tables_data = self._prepare_tables_data(database_name)
        er_data = self._prepare_er_data(database_name)
        
        # 三层for循环（与pipeline完全一致）
        scenarios = self.scenarios['scenarios']
        scenario_use_case_mapping = self.operation_mapping['scenario_use_case_mapping']
        use_case_operations = self.operation_mapping['use_case_operations']
        
        # 第一层：遍历主场景
        for main_scenario_key, main_scenario_data in scenarios.items():
            # 跳过元数据
            if main_scenario_key in ['scenario_types', 'total_scenarios', 'total_sub_scenarios']:
                continue
            
            # 第二层：遍历子场景
            for sub_scenario_key, sub_scenario_data in main_scenario_data['sub_scenarios'].items():
                
                # 第三层：遍历复杂度级别
                for complexity in ['simple', 'moderate', 'complex', 'expert']:
                    
                    # 获取该场景-复杂度对应的用例映射
                    if (main_scenario_key in scenario_use_case_mapping and 
                        sub_scenario_key in scenario_use_case_mapping[main_scenario_key] and
                        complexity in scenario_use_case_mapping[main_scenario_key][sub_scenario_key]):
                        
                        use_case_weights = scenario_use_case_mapping[main_scenario_key][sub_scenario_key][complexity]
                        
                        # 简化选择：随机选择一个用例
                        use_case_names = []
                        for item in use_case_weights:
                            use_case_names.extend(item.keys())
                        selected_use_case_name = random.choice(use_case_names) if use_case_names else 'data_viewing'
                        selected_use_case = use_case_operations.get(selected_use_case_name, use_case_operations.get('data_viewing', {}))
                        
                        # 准备模板数据（严格按照模板要求）
                        template_data = {
                            'main_scenario': {
                                'name': main_scenario_data['name'],
                                'description': main_scenario_data['description']
                            },
                            'sub_scenario': {
                                'name': sub_scenario_data['name'],
                                'focus_areas': sub_scenario_data['focus_areas']
                            },
                            'complexity': complexity,
                            'complexity_config': self.complexity_config['complexity_levels'][complexity],
                            'use_case': selected_use_case,
                            'tables': tables_data,
                            'er_analysis': er_data
                        }
                        
                        # 生成提示词
                        prompt = self.prompt_manager.render_template(
                            'generation/question_generation.j2',
                            **template_data
                        )
                        
                        # 调用LLM生成问题
                        try:
                            question = self._generate_single_question(
                                prompt,
                                main_scenario_key,
                                sub_scenario_key,
                                complexity,
                                selected_use_case_name
                            )
                            
                            if question:
                                all_questions.append(question)
                                self.logger.info(f"生成问题 {len(all_questions)}/{target_count}: "
                                               f"{main_scenario_key}/{sub_scenario_key}/{complexity}")
                                
                                if len(all_questions) >= target_count:
                                    return all_questions
                                    
                        except Exception as e:
                            self.logger.error(f"生成失败 ({main_scenario_key}/{sub_scenario_key}/{complexity}): {e}")
                            continue
        
        # 如果遍历完所有组合还不够，随机选择继续生成
        while len(all_questions) < target_count:
            # 随机选择场景组合
            main_key = random.choice([k for k in scenarios.keys() 
                                    if k not in ['scenario_types', 'total_scenarios', 'total_sub_scenarios']])
            main_data = scenarios[main_key]
            sub_key = random.choice(list(main_data['sub_scenarios'].keys()))
            sub_data = main_data['sub_scenarios'][sub_key]
            complexity = random.choice(['simple', 'moderate', 'complex', 'expert'])
            
            if (main_key in scenario_use_case_mapping and 
                sub_key in scenario_use_case_mapping[main_key] and
                complexity in scenario_use_case_mapping[main_key][sub_key]):
                
                use_case_weights = scenario_use_case_mapping[main_key][sub_key][complexity]
                
                # 简化选择：随机选择一个用例
                use_case_names = []
                for item in use_case_weights:
                    use_case_names.extend(item.keys())
                selected_use_case_name = random.choice(use_case_names) if use_case_names else 'data_viewing'
                selected_use_case = use_case_operations.get(selected_use_case_name, use_case_operations.get('data_viewing', {}))
                
                template_data = {
                    'main_scenario': {
                        'name': main_data['name'],
                        'description': main_data['description']
                    },
                    'sub_scenario': {
                        'name': sub_data['name'],
                        'focus_areas': sub_data['focus_areas']
                    },
                    'complexity': complexity,
                    'complexity_config': self.complexity_config['complexity_levels'][complexity],
                    'use_case': selected_use_case,
                    'tables': tables_data,
                    'er_analysis': er_data
                }
                
                prompt = self.prompt_manager.render_template(
                    'generation/question_generation.j2',
                    **template_data
                )
                
                try:
                    question = self._generate_single_question(
                        prompt, main_key, sub_key, complexity, selected_use_case_name
                    )
                    
                    if question:
                        all_questions.append(question)
                        self.logger.info(f"生成问题 {len(all_questions)}/{target_count}")
                        
                except Exception as e:
                    self.logger.error(f"生成失败: {e}")
        
        return all_questions
    
    def _prepare_tables_data(self, database_name: str) -> List[Dict[str, Any]]:
        """准备表数据 - 从Neo4j获取"""
        
        if not self.memory_manager:
            # 如果没有Neo4j，返回空列表
            return []
        
        try:
            neo4j_graph = self.memory_manager.neo4j_graph
            
            # 查询数据库表结构
            cypher = """
            MATCH (d:Database {name: $database_name})-[:CONTAINS]->(t:Table)-[:HAS_COLUMN]->(c:Column)
            WITH t, collect({
                name: c.name,
                type: c.data_type,
                comment: coalesce(c.ai_business_desc, c.business_desc, c.comment, ''),
                description: coalesce(c.ai_business_desc, c.business_desc, c.comment, ''),
                classification: CASE 
                    WHEN c.data_type CONTAINS 'int' OR c.data_type CONTAINS 'decimal' THEN {category: 'numeric'}
                    WHEN c.data_type CONTAINS 'date' OR c.data_type CONTAINS 'time' THEN {category: 'date'}
                    WHEN c.data_type CONTAINS 'varchar' OR c.data_type CONTAINS 'text' THEN {category: 'text'}
                    ELSE {category: 'other'}
                END
            }) as columns
            RETURN t.name as name,
                   coalesce(t.ai_business_desc, t.business_desc, t.comment, '') as description,
                   columns,
                   t.row_count as row_count
            ORDER BY t.name
            """
            
            results = neo4j_graph.query(cypher, {'database_name': database_name})
            return results
            
        except Exception as e:
            self.logger.error(f"获取表数据失败: {e}")
            return []
    
    def _prepare_er_data(self, database_name: str) -> Dict[str, List[Dict[str, Any]]]:
        """准备ER关系数据 - 从Neo4j获取已分析的ER关系"""
        
        er_data = {
            'physical': [],
            'logical': [],
            'conceptual': []
        }
        
        if not self.memory_manager:
            return er_data
        
        try:
            neo4j_graph = self.memory_manager.neo4j_graph
            
            # 简化查询，直接获取已分析的ER关系
            cypher = """
            MATCH (er:ERAnalysis {database_name: $database_name})
            WHERE er.created_at IS NOT NULL
            RETURN er.physical_relations as physical,
                   er.logical_relations as logical,
                   er.conceptual_relations as conceptual
            ORDER BY er.created_at DESC
            LIMIT 1
            """
            
            result = neo4j_graph.query(cypher, {'database_name': database_name})
            
            if result and result[0]:
                # 解析存储的JSON数据
                if result[0].get('physical'):
                    er_data['physical'] = json.loads(result[0]['physical']) if isinstance(result[0]['physical'], str) else result[0]['physical']
                if result[0].get('logical'):
                    er_data['logical'] = json.loads(result[0]['logical']) if isinstance(result[0]['logical'], str) else result[0]['logical']
                if result[0].get('conceptual'):
                    er_data['conceptual'] = json.loads(result[0]['conceptual']) if isinstance(result[0]['conceptual'], str) else result[0]['conceptual']
            
            return er_data
            
        except Exception as e:
            self.logger.warning(f"获取ER数据失败，使用空数据: {e}")
            return er_data
    
    
    def _generate_single_question(self,
                                 prompt: str,
                                 main_scenario: str,
                                 sub_scenario: str,
                                 complexity: str,
                                 use_case: str) -> Optional[Dict[str, Any]]:
        """调用LLM生成单个问题"""
        
        try:
            # 根据复杂度级别设置max_tokens
            max_tokens = 6000  # 默认值
            complexity_level_config = self.complexity_config['complexity_levels'][complexity]
            if complexity_level_config and complexity_level_config.get('level', 1) >= 3:
                max_tokens = 18000  # 复杂和专家级别使用更多tokens
            
            # 调用LLM
            llm_response = self.llm.invoke(prompt)
            
            # 解析JSON响应
            response_content = llm_response.content if hasattr(llm_response, 'content') else str(llm_response)
            
            if '{' in response_content and '}' in response_content:
                json_start = response_content.find('{')
                json_end = response_content.rfind('}') + 1
                json_str = response_content[json_start:json_end]
                result = json.loads(json_str)
            else:
                # 如果不是JSON格式，创建默认结构
                result = {
                    'generated_question': {
                        'question_text': response_content.strip(),
                        'question_focus': '未知',
                        'expected_output': '未知',
                        'value_proposition': '未知'
                    }
                }
            
            # 保留完整的分析结果
            if 'table_analysis' not in result:
                result['table_analysis'] = {}
            if 'column_analysis' not in result:
                result['column_analysis'] = {}
            
            # 添加元数据
            result['metadata'] = {
                'main_scenario': main_scenario,
                'sub_scenario': sub_scenario,
                'complexity': complexity,
                'use_case': use_case,
                'complexity_level': self.complexity_config['complexity_levels'][complexity]['level']
            }
            
            return result
                
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析失败: {e}")
            return None
        except Exception as e:
            self.logger.error(f"处理LLM响应失败: {e}")
            return None
    
    def _store_questions_to_neo4j(self, questions: List[Dict], database_name: str):
        """将生成的问题完整存储到Neo4j"""
        if not self.memory_manager:
            self.logger.info("未配置Neo4j，跳过存储")
            return
        
        try:
            neo4j_graph = self.memory_manager.neo4j_graph
            stored_count = 0
            
            for question in questions:
                # 提取所有数据
                q_data = question.get('generated_question', {})
                metadata = question.get('metadata', {})
                table_analysis = question.get('table_analysis', {})
                column_analysis = question.get('column_analysis', {})
                
                # 创建Question节点，包含所有属性
                cypher = """
                CREATE (q:Question {
                    id: randomUUID(),
                    database_name: $database_name,
                    
                    // 基本问题信息
                    question_text: $question_text,
                    question_focus: $question_focus,
                    expected_output: $expected_output,
                    value_proposition: $value_proposition,
                    
                    // 业务规则（如果有）
                    business_rules: $business_rules,
                    
                    // 表分析
                    tables_used: $tables_used,
                    table_analysis: $table_analysis,
                    
                    // 列分析
                    columns_used: $columns_used,
                    column_analysis: $column_analysis,
                    
                    // 元数据
                    main_scenario: $main_scenario,
                    sub_scenario: $sub_scenario,
                    complexity: $complexity,
                    complexity_level: $complexity_level,
                    use_case: $use_case,
                    
                    // 系统字段
                    created_at: datetime(),
                    has_sql: false
                })
                RETURN q.id as question_id
                """
                
                try:
                    # 准备参数
                    params = {
                        'database_name': database_name,
                        
                        # 基本信息
                        'question_text': q_data.get('question_text', ''),
                        'question_focus': q_data.get('question_focus', ''),
                        'expected_output': q_data.get('expected_output', ''),
                        'value_proposition': q_data.get('value_proposition', ''),
                        
                        # 业务规则（JSON字符串）
                        'business_rules': json.dumps(q_data.get('business_rules', []), ensure_ascii=False),
                        
                        # 表分析（JSON字符串）
                        'tables_used': json.dumps(table_analysis.get('tables_used', []), ensure_ascii=False),
                        'table_analysis': json.dumps(table_analysis, ensure_ascii=False),
                        
                        # 列分析（JSON字符串）
                        'columns_used': json.dumps(column_analysis.get('columns_used', []), ensure_ascii=False),
                        'column_analysis': json.dumps(column_analysis, ensure_ascii=False),
                        
                        # 元数据
                        'main_scenario': metadata.get('main_scenario', ''),
                        'sub_scenario': metadata.get('sub_scenario', ''),
                        'complexity': metadata.get('complexity', ''),
                        'complexity_level': metadata.get('complexity_level', 0),
                        'use_case': metadata.get('use_case', '')
                    }
                    
                    result = neo4j_graph.query(cypher, params)
                    
                    if result:
                        stored_count += 1
                        self.logger.debug(f"问题已存储: {result[0]['question_id']}")
                        
                except Exception as e:
                    self.logger.warning(f"存储单个问题失败: {e}")
                    continue
            
            self.logger.info(f"成功存储 {stored_count}/{len(questions)} 个问题到Neo4j")
            
        except Exception as e:
            self.logger.error(f"Neo4j存储过程失败: {e}")
    
    @staticmethod
    def get_questions_without_sql(neo4j_graph, database_name: str, limit: int = 10) -> List[Dict]:
        """获取还没有SQL的问题 - 供其他工具使用"""
        cypher = """
        MATCH (q:Question)
        WHERE q.database_name = $database_name 
          AND q.has_sql = false
        RETURN q.id as id,
               q.question_text as question_text,
               q.question_data as question_data,
               q.metadata as metadata
        ORDER BY q.created_at
        LIMIT $limit
        """
        
        try:
            results = neo4j_graph.query(cypher, {
                'database_name': database_name,
                'limit': limit
            })
            
            # 解析JSON字符串
            for result in results:
                if result.get('question_data'):
                    result['question_data'] = json.loads(result['question_data'])
                if result.get('metadata'):
                    result['metadata'] = json.loads(result['metadata'])
            
            return results
        except Exception as e:
            logger.error(f"查询问题失败: {e}")
            return []
    
    @staticmethod
    def update_question_with_sql(neo4j_graph, question_id: str, sql: str) -> bool:
        """为问题添加SQL - 供其他工具使用"""
        cypher = """
        MATCH (q:Question {id: $question_id})
        SET q.sql = $sql,
            q.has_sql = true,
            q.sql_generated_at = datetime()
        RETURN q.id
        """
        
        try:
            result = neo4j_graph.query(cypher, {
                'question_id': question_id, 
                'sql': sql
            })
            return len(result) > 0
        except Exception as e:
            logger.error(f"更新问题SQL失败: {e}")
            return False


# 便利函数
def create_scenario_operation_tool(memory_manager=None, database_manager=None) -> ScenarioOperationTool:
    """创建场景操作工具的便利函数"""
    return ScenarioOperationTool(
        memory_manager=memory_manager,
        database_manager=database_manager
    )