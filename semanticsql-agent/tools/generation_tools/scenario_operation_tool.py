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
    
    def _run(self, *args, **kwargs) -> str:
        """执行问题生成"""
        # 从kwargs中提取参数
        database_name = kwargs.get('database_name', 'testdb')
        target_count = kwargs.get('target_count', 10)
        
        self.logger.info(f"🔧 {self.name}: 开始场景问题生成，数据库: {database_name}")
        
        try:
            # 初始化必要的服务
            if not self.memory_manager:
                object.__setattr__(self, 'memory_manager', ComponentManager.create_memory_manager(get_settings()))
            
            # 生成问题
            questions = self.generate_questions(database_name, target_count)
            
            # 存储生成的问题到Neo4j
            if self.memory_manager and questions:
                self._store_questions_to_neo4j(questions, database_name)
            
            result_message = f"✅ scenario_operation_tool 分析完成，生成了 {len(questions)} 个问题，请务必继续执行 sql_generation_tool 工具。"    
            return result_message

        except Exception as e:
            error_msg = f"场景问题生成失败: {str(e)}"
            self.logger.error(f"❌ {self.name}: {error_msg}")
            return f"❌ {error_msg}"
    
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
        """准备表数据 - 增强版：包含完整的表-列映射"""
        
        if not self.memory_manager:
            # 如果没有Neo4j，返回空列表
            return []
        
        try:
            neo4j_graph = self.memory_manager.neo4j_graph
            
            # 查询数据库表结构 - 修复版：只使用实际存在的属性
            cypher = """
            MATCH (d:Database {name: $database_name})-[:CONTAINS]->(t:Table)-[:HAS_COLUMN]->(c:Column)
            WITH t, collect({
                name: c.name,
                type: c.data_type,
                comment: coalesce(c.ai_business_desc, c.business_desc, ''),
                description: coalesce(c.ai_business_desc, c.business_desc, ''),
                classification: CASE 
                    WHEN c.data_type CONTAINS 'int' OR c.data_type CONTAINS 'decimal' THEN {category: 'numeric'}
                    WHEN c.data_type CONTAINS 'date' OR c.data_type CONTAINS 'time' THEN {category: 'date'}
                    WHEN c.data_type CONTAINS 'varchar' OR c.data_type CONTAINS 'text' THEN {category: 'text'}
                    ELSE {category: 'other'}
                END
            }) as columns
            RETURN t.name as name,
                   coalesce(t.ai_business_desc, t.business_desc, '') as description,
                   columns
            ORDER BY t.name
            """
            
            results = neo4j_graph.query(cypher, {'database_name': database_name})
            
            # 构建表-列的严格映射（用于验证）
            object.__setattr__(self, 'table_column_mapping', {})
            
            # 为每个表添加完整的列引用格式
            for table_info in results:
                table_name = table_info['name']
                column_names = [col['name'] for col in table_info['columns']]
                self.table_column_mapping[table_name] = set(column_names)
                
                # 为每个列添加完整引用格式（用于模板）
                for col in table_info['columns']:
                    col['full_reference'] = f"{table_name}.{col['name']}"
            
            self.logger.info(f"构建了 {len(self.table_column_mapping)} 个表的列映射")
            
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
            
            # 修复版：使用实际存在的ER结构（ERRelation + BusinessEntity）
            cypher = """
            MATCH (bd:BusinessDomain)-[:CONTAINS]->(er:ERRelation)-[:INVOLVES]->(be:BusinessEntity)
            WHERE bd.database_name = $database_name OR bd.database_name IS NULL
            WITH er, COLLECT(DISTINCT be) as entities
            OPTIONAL MATCH (be1:BusinessEntity)-[rel]-(be2:BusinessEntity)
            WHERE be1 IN entities AND be2 IN entities AND type(rel) IN ['ONE_TO_ONE', 'ONE_TO_MANY']
            RETURN er.relation_name as relation_name,
                   er.business_meaning as business_meaning,
                   er.complexity_level as complexity_level,
                   COLLECT(DISTINCT {from: be1.name, to: be2.name, type: type(rel)}) as entity_relations
            """
            
            result = neo4j_graph.query(cypher, {'database_name': database_name})
            
            if result:
                # 处理实际的ER结构数据
                for row in result:
                    # 概念层关系（来自ERRelation的业务含义）
                    conceptual_relation = {
                        'relation_name': row.get('relation_name', ''),
                        'business_meaning': row.get('business_meaning', ''),
                        'complexity_level': row.get('complexity_level', 'medium')
                    }
                    er_data['conceptual'].append(conceptual_relation)
                    
                    # 逻辑层关系（BusinessEntity之间的关系）
                    entity_relations = row.get('entity_relations', [])
                    for rel in entity_relations:
                        if rel and rel.get('from') and rel.get('to'):
                            logical_relation = {
                                'from': rel['from'],
                                'to': rel['to'],
                                'relationship': rel['type']
                            }
                            er_data['logical'].append(logical_relation)
            
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
    
    def _validate_columns_strict(self, question: Dict[str, Any], database_name: str) -> Optional[Dict[str, Any]]:
        """严格验证问题中的列名，只验证不修复
        
        Args:
            question: 生成的问题数据
            database_name: 数据库名称
            
        Returns:
            验证通过返回原问题，验证失败返回None
        """
        if not self.memory_manager:
            return question
        
        try:
            # 确保已经构建了表-列映射
            if not hasattr(self, 'table_column_mapping'):
                self._prepare_tables_data(database_name)
            
            invalid_refs = []
            
            # 验证column_analysis中的列引用
            column_analysis = question.get('column_analysis', {})
            if column_analysis and 'columns_used' in column_analysis:
                for col_info in column_analysis['columns_used']:
                    col_ref = col_info.get('column_full_name', '')
                    if col_ref and not self._validate_table_column_combination(col_ref):
                        invalid_refs.append(col_ref)
            
            # 验证columns_used列表
            columns_used = question.get('columns_used', [])
            if isinstance(columns_used, list):
                for column_ref in columns_used:
                    if isinstance(column_ref, str) and not self._validate_table_column_combination(column_ref):
                        invalid_refs.append(column_ref)
            
            if invalid_refs:
                self.logger.error(f"问题验证失败，发现无效的表-列组合: {invalid_refs}")
                
                # 提供有用的调试信息
                for invalid_ref in invalid_refs:
                    if '.' in invalid_ref:
                        table, column = invalid_ref.split('.', 1)
                        # 查找包含此列的正确表
                        correct_tables = []
                        for table_name, columns in self.table_column_mapping.items():
                            if column in columns:
                                correct_tables.append(table_name)
                        
                        if correct_tables:
                            self.logger.info(f"提示：列 '{column}' 存在于表: {correct_tables}")
                        else:
                            self.logger.info(f"提示：列 '{column}' 在任何表中都不存在")
                
                return None  # 验证失败，返回None
            
            self.logger.info("表-列组合验证通过")
            return question
            
        except Exception as e:
            self.logger.error(f"表-列组合验证异常: {e}")
            return None
    
    def _validate_table_column_combination(self, column_ref: str) -> bool:
        """验证表-列组合是否正确（只验证不修复）
        
        Args:
            column_ref: 列引用，格式为 "表名.列名"
            
        Returns:
            组合是否有效
        """
        if not hasattr(self, 'table_column_mapping') or not self.table_column_mapping:
            self.logger.warning("表-列映射未初始化")
            return False
        
        if '.' not in column_ref:
            # 必须使用完整的 表名.列名 格式
            return False
        
        table, column = column_ref.split('.', 1)
        
        # 检查表是否存在
        if table not in self.table_column_mapping:
            return False
        
        # 检查列是否存在于指定表中
        return column in self.table_column_mapping[table]

    def _store_questions_to_neo4j(self, questions: List[Dict], database_name: str):
        """将生成的问题完整存储到Neo4j"""
        if not self.memory_manager:
            self.logger.info("未配置Neo4j，跳过存储")
            return
        
        try:
            neo4j_graph = self.memory_manager.neo4j_graph
            stored_count = 0
            
            for question in questions:
                # 严格验证列名（不修复）
                validated_question = self._validate_columns_strict(question, database_name)
                if validated_question is None:
                    # 验证失败，跳过这个问题
                    self.logger.warning("跳过验证失败的问题")
                    continue
                question = validated_question
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