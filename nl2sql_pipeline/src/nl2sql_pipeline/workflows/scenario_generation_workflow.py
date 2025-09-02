"""场景驱动的问题生成工作流"""

import logging
import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

from ..models.states import AnalysisResult
from ..pipelines.generation import ScenarioDrivenGenerationPipeline
from ..services import ServiceContainer

logger = logging.getLogger(__name__)


class ScenarioGenerationWorkflow:
    """场景驱动的生成工作流
    
    直接使用三层for循环生成问题，无需复杂的状态管理
    """
    
    def __init__(self, services: ServiceContainer):
        """初始化工作流
        
        Args:
            services: 服务容器
        """
        self.services = services
        self.pipeline = ScenarioDrivenGenerationPipeline(services)
    
    def run(self, 
            analysis_result: AnalysisResult,
            target_count: int = 1000) -> Dict[str, Any]:
        """运行生成工作流
        
        Args:
            analysis_result: 分析结果
            target_count: 目标生成数量
            
        Returns:
            包含生成结果的字典
        """
        logger.info(f"开始场景驱动的问题生成，目标数量: {target_count}")
        
        try:
            # 转换分析结果为字典格式
            analysis_dict = self._convert_analysis_result(analysis_result)
            
            # 调用管道生成问题
            questions = self.pipeline.generate_questions(
                analysis_result=analysis_dict,
                target_count=target_count
            )
            
            logger.info(f"成功生成 {len(questions)} 个问题")
            
            # 统计信息
            stats = self._calculate_statistics(questions)
            
            return {
                'success': True,
                'questions': questions,
                'count': len(questions),
                'statistics': stats
            }
            
        except Exception as e:
            logger.error(f"生成过程失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'questions': [],
                'count': 0
            }
    
    def _convert_analysis_result(self, analysis_result: AnalysisResult) -> Dict[str, Any]:
        """将分析结果对象转换为字典格式"""
        # 转换table_descriptions和column_descriptions为字典格式
        table_descriptions = {}
        for table_desc in analysis_result.table_descriptions:
            table_descriptions[table_desc.table_name] = {
                'business_description': table_desc.description,  # 使用正确的属性名
                'row_count': table_desc.row_count,
                'business_type': table_desc.business_type,
                'key_columns': table_desc.key_columns
            }
        
        column_descriptions = {}
        for col_desc in analysis_result.column_descriptions:
            field_key = f"{col_desc.table_name}.{col_desc.column_name}"
            column_descriptions[field_key] = {
                'business_description': col_desc.description,  # 使用正确的属性名
                'confidence': col_desc.confidence,
                'source': col_desc.source
            }
        
        return {
            'database_schema': analysis_result.database_schema,
            'domain_knowledge': analysis_result.domain_knowledge,
            'table_descriptions': table_descriptions,
            'column_descriptions': column_descriptions,
            'field_classifications': analysis_result.field_classifications,
            'er_analysis': analysis_result.er_relationships  # 修正属性名
        }
    
    def _calculate_statistics(self, questions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算统计信息"""
        stats = {
            'by_scenario': {},
            'by_complexity': {},
            'by_use_case': {},
            'by_scenario_complexity': {}
        }
        
        for q in questions:
            meta = q.get('metadata', {})
            
            # 按场景统计
            main_scenario = meta.get('main_scenario', 'unknown')
            sub_scenario = meta.get('sub_scenario', 'unknown')
            scenario_key = f"{main_scenario}/{sub_scenario}"
            stats['by_scenario'][scenario_key] = stats['by_scenario'].get(scenario_key, 0) + 1
            
            # 按复杂度统计
            complexity = meta.get('complexity', 'unknown')
            stats['by_complexity'][complexity] = stats['by_complexity'].get(complexity, 0) + 1
            
            # 按用例统计
            use_case = meta.get('use_case', 'unknown')
            stats['by_use_case'][use_case] = stats['by_use_case'].get(use_case, 0) + 1
            
            # 按场景-复杂度组合统计
            combo_key = f"{scenario_key}_{complexity}"
            stats['by_scenario_complexity'][combo_key] = stats['by_scenario_complexity'].get(combo_key, 0) + 1
        
        return stats
    
    def save_results(self, 
                    questions: List[Dict[str, Any]], 
                    output_dir: str = "output") -> str:
        """保存生成结果到文件
        
        Args:
            questions: 生成的问题列表
            output_dir: 输出目录
            
        Returns:
            保存的文件路径
        """
        # 创建输出目录
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"generated_questions_{timestamp}.json"
        filepath = output_path / filename
        
        # 准备输出数据
        output_data = {
            'generation_time': datetime.now().isoformat(),
            'total_count': len(questions),
            'questions': questions,
            'statistics': self._calculate_statistics(questions)
        }
        
        # 保存到文件
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"结果已保存到: {filepath}")
        return str(filepath)
    
    def load_results(self, filepath: str) -> Dict[str, Any]:
        """从文件加载生成结果
        
        Args:
            filepath: 结果文件路径
            
        Returns:
            加载的结果数据
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)