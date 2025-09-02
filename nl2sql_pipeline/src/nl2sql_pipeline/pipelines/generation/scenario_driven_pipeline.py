"""场景驱动的问题生成管道 - 与提示词模板完全对齐"""

import yaml
import json
import logging
import random
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

class ScenarioDrivenGenerationPipeline:
    """场景驱动的问题生成管道"""
    
    def __init__(self, service_container: Any):
        self.services = service_container
        self.config_dir = Path(__file__).parent.parent.parent.parent.parent / 'config'
        self.template_dir = Path(__file__).parent.parent.parent / 'prompts/templates/generation'
        
        # 加载配置
        try:
            self.scenarios = self._load_yaml('scenarios.yaml')
            self.operation_mapping = self._load_yaml('operation_mapping.yaml')
            self.complexity_config = self._load_yaml('complexity.yaml')
            logger.info("成功加载所有配置文件")
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            raise
        
        # 初始化Jinja2
        try:
            self.jinja_env = Environment(loader=FileSystemLoader(str(self.template_dir)))
            self.template = self.jinja_env.get_template('question_generation.j2')
            logger.info("成功加载Jinja2模板")
        except Exception as e:
            logger.error(f"加载模板失败: {e}")
            raise
    
    def _load_yaml(self, filename: str) -> Dict:
        """加载YAML配置文件"""
        with open(self.config_dir / filename, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def generate_questions(self,
                          analysis_result: Dict[str, Any],
                          target_count: int = 100) -> List[Dict[str, Any]]:
        """生成问题的主方法
        
        Args:
            analysis_result: 分析结果，包含:
                - database_schema: 数据库schema对象
                - table_descriptions: 表描述字典
                - column_descriptions: 列描述字典  
                - field_classifications: 字段分类字典
                - er_analysis: ER分析结果
            target_count: 目标生成数量
        """
        all_questions = []
        
        # 准备通用数据
        tables_data = self._prepare_tables_data(analysis_result)
        er_data = self._prepare_er_data(analysis_result.get('er_analysis'))
        
        # 三层for循环
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
                        prompt = self.template.render(**template_data)
                        
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
                                logger.info(f"生成问题 {len(all_questions)}/{target_count}: "
                                          f"{main_scenario_key}/{sub_scenario_key}/{complexity}")
                                
                                if len(all_questions) >= target_count:
                                    return all_questions
                                    
                        except Exception as e:
                            logger.error(f"生成失败 ({main_scenario_key}/{sub_scenario_key}/{complexity}): {e}")
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
                
                prompt = self.template.render(**template_data)
                
                try:
                    question = self._generate_single_question(
                        prompt, main_key, sub_key, complexity, selected_use_case_name
                    )
                    
                    if question:
                        all_questions.append(question)
                        logger.info(f"生成问题 {len(all_questions)}/{target_count}")
                        
                except Exception as e:
                    logger.error(f"生成失败: {e}")
        
        return all_questions
    
    def _prepare_tables_data(self, analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """准备表数据，格式与模板要求一致"""
        tables = []
        database_schema = analysis_result.get('database_schema')
        table_descriptions = analysis_result.get('table_descriptions', {})
        column_descriptions = analysis_result.get('column_descriptions', {})
        field_classifications = analysis_result.get('field_classifications', {})
        
        if database_schema:
            for table in database_schema.tables:
                table_info = {
                    'name': table.name,
                    'description': table_descriptions.get(table.name, {}).get('business_description', ''),
                    'row_count': table_descriptions.get(table.name, {}).get('row_count'),
                    'columns': []
                }
                
                for column in table.columns:
                    field_key = f"{table.name}.{column.name}"
                    # 获取列描述，确保不为None
                    col_desc_obj = column_descriptions.get(field_key)
                    if col_desc_obj and hasattr(col_desc_obj, 'description'):
                        description = col_desc_obj.description or ''
                    elif col_desc_obj and hasattr(col_desc_obj, 'business_description'):
                        description = col_desc_obj.business_description or ''
                    else:
                        description = ''
                    
                    col_info = {
                        'name': column.name,
                        'type': column.data_type,
                        'comment': column.comment or '',  # 确保comment不为None
                        'description': description,
                        'classification': field_classifications.get(field_key)
                    }
                    table_info['columns'].append(col_info)
                
                tables.append(table_info)
        
        return tables
    
    def _prepare_er_data(self, er_analysis: Any) -> Dict[str, List[Dict[str, Any]]]:
        """准备ER关系数据，格式与模板要求一致"""
        er_data = {
            'physical': [],
            'logical': [],
            'conceptual': []
        }
        
        if er_analysis:
            # 物理关系
            if hasattr(er_analysis, 'physical_relations'):
                er_data['physical'] = [
                    {
                        'from': f"{rel.from_table}.{rel.from_column}",
                        'to': f"{rel.to_table}.{rel.to_column}"
                    }
                    for rel in er_analysis.physical_relations
                ]
            
            # 逻辑关系
            if hasattr(er_analysis, 'logical_relations'):
                er_data['logical'] = [
                    {
                        'tables': rel.tables,
                        'pattern': rel.pattern,
                        'confidence': rel.confidence
                    }
                    for rel in er_analysis.logical_relations
                ]
            
            # 概念关系
            if hasattr(er_analysis, 'conceptual_relations'):
                er_data['conceptual'] = [
                    {
                        'entity1': rel.entity1,
                        'entity2': rel.entity2,
                        'relationship': rel.relationship_type
                    }
                    for rel in er_analysis.conceptual_relations
                ]
        
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
            
            # 调用LLM的generate_json方法
            result = self.services.llm_service.generate_json(
                prompt,
                max_tokens=max_tokens,
                temperature=0.7  # 保持一定的创造性
            )
            
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
            logger.error(f"JSON解析失败: {e}")
            return None
        except Exception as e:
            logger.error(f"处理LLM响应失败: {e}")
            return None
    
