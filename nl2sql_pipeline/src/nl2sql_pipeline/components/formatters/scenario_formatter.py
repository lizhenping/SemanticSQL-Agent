"""场景格式化器

格式化业务场景信息，用于问题生成。
"""

from typing import List, Dict, Any, Optional
from .base import BaseFormatter


class ScenarioFormatter(BaseFormatter):
    """场景格式化器
    
    将业务场景信息格式化为适合LLM理解的文本格式。
    """
    
    def format(self, data: Any, context: Optional[Dict[str, Any]] = None) -> str:
        """格式化场景信息
        
        Args:
            data: 场景名称或场景信息字典
            context: 包含 scenarios, complexity_levels 等信息
            
        Returns:
            格式化后的场景信息
        """
        if isinstance(data, str):
            return self.format_single_scenario(data, context)
        elif isinstance(data, list):
            return self.format_scenario_list(data, context)
        elif isinstance(data, dict):
            return self.format_scenario_dict(data)
        else:
            return str(data)
    
    def format_single_scenario(self, scenario_name: str, context: Optional[Dict[str, Any]] = None) -> str:
        """格式化单个场景"""
        if not context:
            return f"Scenario: {scenario_name}"
        
        # 获取场景配置
        scenarios = context.get('scenarios', {})
        scenario_info = scenarios.get(scenario_name, {})
        
        lines = []
        lines.append(f"=== Scenario: {scenario_name} ===")
        
        # 场景描述
        if 'description' in scenario_info:
            lines.append(f"Description: {scenario_info['description']}")
        
        # 业务焦点
        if 'focus' in scenario_info:
            lines.append(f"Business Focus: {scenario_info['focus']}")
        
        # 关键操作
        if 'key_operations' in scenario_info:
            operations = scenario_info['key_operations']
            lines.append(f"Key Operations: {', '.join(operations)}")
        
        # 典型聚合
        if 'typical_aggregations' in scenario_info:
            aggregations = scenario_info['typical_aggregations']
            lines.append(f"Typical Aggregations: {', '.join(aggregations)}")
        
        # 子场景
        if 'sub_scenarios' in scenario_info:
            sub_scenarios = scenario_info['sub_scenarios']
            lines.append(f"Sub-scenarios: {', '.join(sub_scenarios)}")
        
        # 复杂度支持
        if 'complexity_support' in scenario_info:
            complexity = scenario_info['complexity_support']
            lines.append(f"Complexity Support: {complexity.get('min', 1)} - {complexity.get('max', 4)}")
        
        return '\n'.join(lines)
    
    def format_scenario_list(self, scenario_names: List[str], context: Optional[Dict[str, Any]] = None) -> str:
        """格式化场景列表"""
        lines = []
        lines.append(f"=== Available Scenarios ({len(scenario_names)}) ===")
        
        for scenario_name in scenario_names:
            lines.append(f"\n{scenario_name}:")
            
            if context:
                scenarios = context.get('scenarios', {})
                scenario_info = scenarios.get(scenario_name, {})
                
                if 'description' in scenario_info:
                    lines.append(f"  {self._truncate(scenario_info['description'], 80)}")
                
                if 'sub_scenarios' in scenario_info:
                    sub_count = len(scenario_info['sub_scenarios'])
                    lines.append(f"  {sub_count} sub-scenarios available")
        
        return '\n'.join(lines)
    
    def format_scenario_dict(self, scenario_info: Dict[str, Any]) -> str:
        """格式化场景详细信息"""
        lines = []
        
        # 标题
        scenario_name = scenario_info.get('name', 'Unknown Scenario')
        lines.append(f"=== {scenario_name} ===")
        
        # 基本信息
        for key in ['description', 'focus', 'business_context']:
            if key in scenario_info:
                lines.append(f"{key.replace('_', ' ').title()}: {scenario_info[key]}")
        
        # 操作和功能
        if 'operations' in scenario_info:
            lines.append("\nRequired Operations:")
            for op in scenario_info['operations']:
                lines.append(f"  - {op}")
        
        if 'sql_features' in scenario_info:
            lines.append("\nSQL Features:")
            for feature in scenario_info['sql_features']:
                lines.append(f"  - {feature}")
        
        # 示例问题
        if 'example_questions' in scenario_info:
            lines.append("\nExample Questions:")
            for i, question in enumerate(scenario_info['example_questions'][:3], 1):
                lines.append(f"  {i}. {question}")
        
        return '\n'.join(lines)
    
    def format_complexity_level(self, complexity: int, context: Optional[Dict[str, Any]] = None) -> str:
        """格式化复杂度级别"""
        lines = []
        lines.append(f"=== Complexity Level {complexity} ===")
        
        if context:
            complexity_info = context.get('complexity_levels', {}).get(str(complexity), {})
            
            if 'description' in complexity_info:
                lines.append(f"Description: {complexity_info['description']}")
            
            if 'sql_features' in complexity_info:
                features = complexity_info['sql_features']
                lines.append(f"SQL Features: {', '.join(features)}")
            
            if 'max_tables' in complexity_info:
                lines.append(f"Max Tables: {complexity_info['max_tables']}")
            
            if 'aggregation_allowed' in complexity_info:
                lines.append(f"Aggregation: {'Yes' if complexity_info['aggregation_allowed'] else 'No'}")
        else:
            # 默认描述
            complexity_desc = {
                1: "Simple queries with basic filtering",
                2: "Moderate complexity with joins",
                3: "Complex queries with multiple joins and aggregations",
                4: "Advanced queries with subqueries and window functions"
            }
            lines.append(f"Description: {complexity_desc.get(complexity, 'Unknown complexity')}")
        
        return '\n'.join(lines)
    
    def format_scenario_complexity_matrix(self, scenarios: List[str], complexities: List[int]) -> str:
        """格式化场景-复杂度矩阵"""
        lines = []
        lines.append("=== Scenario-Complexity Matrix ===")
        lines.append(f"Scenarios: {len(scenarios)}")
        lines.append(f"Complexity Levels: {len(complexities)}")
        lines.append(f"Total Combinations: {len(scenarios) * len(complexities)}")
        
        lines.append("\nMatrix:")
        lines.append("Scenario \\ Complexity" + "".join(f"\t{c}" for c in complexities))
        
        for scenario in scenarios:
            row = scenario[:20].ljust(20)  # 截断并对齐场景名
            for complexity in complexities:
                row += "\t✓"
            lines.append(row)
        
        return '\n'.join(lines)
    
    def format_generation_context(self, scenario: str, complexity: int, context: Dict[str, Any]) -> str:
        """格式化生成上下文"""
        lines = []
        lines.append(f"=== Generation Context ===")
        lines.append(f"Scenario: {scenario}")
        lines.append(f"Complexity: Level {complexity}")
        
        # 添加相关表信息
        if 'selected_tables' in context:
            tables = context['selected_tables']
            lines.append(f"\nSelected Tables ({len(tables)}):")
            for table in tables[:5]:
                lines.append(f"  - {table}")
        
        # 添加字段信息
        if 'selected_fields' in context:
            fields = context['selected_fields']
            lines.append(f"\nSelected Fields ({len(fields)}):")
            
            # 按类型分组
            by_type = {}
            for field in fields:
                field_type = field.get('type', 'unknown')
                if field_type not in by_type:
                    by_type[field_type] = []
                by_type[field_type].append(field.get('name', ''))
            
            for field_type, field_names in by_type.items():
                lines.append(f"  {field_type}: {', '.join(field_names[:3])}")
                if len(field_names) > 3:
                    lines.append(f"    ... and {len(field_names) - 3} more")
        
        # 添加生成要求
        if 'requirements' in context:
            lines.append("\nGeneration Requirements:")
            for req in context['requirements']:
                lines.append(f"  - {req}")
        
        return '\n'.join(lines)