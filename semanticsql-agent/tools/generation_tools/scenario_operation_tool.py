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
            questions = self.generate_questions(database_name, target_count)
            return {
                'success': True,
                'questions': questions,
                'total_generated': len(questions),
                'database_name': database_name
            }
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
                        
                        # 根据权重选择用例
                        selected_use_case_name = self._weighted_choice(use_case_weights)
                        selected_use_case = use_case_operations[selected_use_case_name]
                        
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
                selected_use_case_name = self._weighted_choice(use_case_weights)
                selected_use_case = use_case_operations[selected_use_case_name]
                
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
        """准备ER关系数据 - 从Neo4j获取（使用新的BusinessDomain模型）"""
        
        er_data = {
            'physical': [],
            'logical': [],
            'conceptual': []
        }
        
        if not self.memory_manager:
            return er_data
        
        try:
            neo4j_graph = self.memory_manager.neo4j_graph
            
            # 查询新的ER模型
            cypher = """
            MATCH (bd:BusinessDomain {database_name: $database_name})-[:CONTAINS]->(er:ERRelation)-[:INVOLVES]->(be:BusinessEntity)
            OPTIONAL MATCH (be)-[ha:HAS_ATTRIBUTE]->(c:Column)<-[:HAS_COLUMN]-(t:Table)
            OPTIONAL MATCH (be1:BusinessEntity)-[rel]->(be2:BusinessEntity)
            WHERE (be1)-[:INVOLVES*0..1]-(:ERRelation)-[:CONTAINS*0..1]-(bd) 
            AND (be2)-[:INVOLVES*0..1]-(:ERRelation)-[:CONTAINS*0..1]-(bd)
            
            WITH collect(DISTINCT {
                entity: be.name,
                table: t.name,
                column: c.name
            }) as attributes,
            collect(DISTINCT {
                from_entity: be1.name,
                to_entity: be2.name,
                relation_type: type(rel)
            }) as relations
            
            RETURN attributes, relations
            LIMIT 1
            """
            
            result = neo4j_graph.query(cypher, {'database_name': database_name})
            
            if result:
                # 物理关系（列到实体的映射）
                for attr in result[0].get('attributes', []):
                    if attr['table'] and attr['column']:
                        er_data['physical'].append({
                            'from': f"{attr['table']}.{attr['column']}",
                            'to': attr['entity'] or 'Unknown'
                        })
                
                # 概念关系（实体间关系）
                for rel in result[0].get('relations', []):
                    if rel['from_entity'] and rel['to_entity']:
                        er_data['conceptual'].append({
                            'entity1': rel['from_entity'],
                            'entity2': rel['to_entity'],
                            'relationship': rel['relation_type']
                        })
            
            return er_data
            
        except Exception as e:
            self.logger.error(f"获取ER数据失败: {e}")
            return er_data
    
    def _weighted_choice(self, use_case_weights: List[Dict[str, float]]) -> str:
        """根据权重选择用例"""
        choices = []
        weights = []
        
        for item in use_case_weights:
            for choice, weight in item.items():
                choices.append(choice)
                weights.append(weight)
        
        return random.choices(choices, weights=weights, k=1)[0]
    
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


# 便利函数
def create_scenario_operation_tool(memory_manager=None, database_manager=None) -> ScenarioOperationTool:
    """创建场景操作工具的便利函数"""
    return ScenarioOperationTool(
        memory_manager=memory_manager,
        database_manager=database_manager
    )