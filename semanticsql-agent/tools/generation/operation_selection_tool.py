"""
操作选择工具 - 为场景选择合适的SQL操作
"""

import random
from typing import Dict, Any, List

from tools.base_tool import BaseTool, ToolParameter
from core.models import QueryScenario, SQLOperation, DifficultyLevel


class OperationSelectionTool(BaseTool):
    """为查询场景选择SQL操作类型"""
    
    @property
    def name(self) -> str:
        return "select_operations"
    
    @property
    def description(self) -> str:
        return "根据场景和难度选择合适的SQL操作组合"
    
    @property
    def category(self) -> str:
        return "generation"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="scenario",
                type="object",
                description="查询场景",
                required=True
            ),
            ToolParameter(
                name="schema_info",
                type="object", 
                description="数据库结构信息",
                required=True
            ),
            ToolParameter(
                name="force_operations",
                type="array",
                description="强制包含的操作类型",
                required=False,
                default=[]
            )
        ]
    
    def _execute(self, scenario: Dict[str, Any], schema_info: Dict[str, Any],
                 force_operations: List[str] = None) -> Dict[str, Any]:
        """
        选择SQL操作
        
        Returns:
            包含操作类型和理由的字典
        """
        difficulty = DifficultyLevel[scenario.get("complexity", "MEDIUM").upper()]
        tables = scenario.get("applicable_tables", [])
        
        # 根据难度确定操作组合
        operations = self._select_operations_by_difficulty(
            difficulty,
            len(tables),
            schema_info,
            force_operations
        )
        
        # 生成操作说明
        operation_details = self._generate_operation_details(
            operations,
            scenario,
            schema_info
        )
        
        return {
            "operations": [op.value for op in operations],
            "operation_details": operation_details,
            "estimated_complexity": self._estimate_complexity(operations),
            "rationale": self._generate_rationale(operations, scenario)
        }
    
    def _select_operations_by_difficulty(self, difficulty: DifficultyLevel,
                                        table_count: int,
                                        schema_info: Dict[str, Any],
                                        force_operations: List[str] = None) -> List[SQLOperation]:
        """根据难度选择操作"""
        operations = []
        
        # 处理强制操作
        if force_operations:
            operations = [SQLOperation[op.upper()] for op in force_operations]
        
        # 根据难度添加操作
        if difficulty == DifficultyLevel.EASY:
            # 简单查询：基础SELECT，可能带WHERE
            if SQLOperation.SELECT not in operations:
                operations.append(SQLOperation.SELECT)
                
        elif difficulty == DifficultyLevel.MEDIUM:
            # 中等查询：JOIN或GROUP BY
            if SQLOperation.SELECT not in operations:
                operations.append(SQLOperation.SELECT)
            
            if table_count > 1 and SQLOperation.JOIN not in operations:
                operations.append(SQLOperation.JOIN)
            elif table_count == 1 and SQLOperation.GROUP not in operations:
                # 单表聚合
                operations.append(SQLOperation.GROUP)
                
        else:  # HARD
            # 复杂查询：多种操作组合
            if SQLOperation.SELECT not in operations:
                operations.append(SQLOperation.SELECT)
            
            # 随机添加高级操作
            advanced_ops = [
                SQLOperation.SUBQUERY,
                SQLOperation.WINDOW,
                SQLOperation.CTE,
                SQLOperation.UNION
            ]
            
            # 根据表数量决定操作
            if table_count > 2:
                if SQLOperation.JOIN not in operations:
                    operations.append(SQLOperation.JOIN)
                # 可能添加子查询
                if random.random() > 0.5 and SQLOperation.SUBQUERY not in operations:
                    operations.append(SQLOperation.SUBQUERY)
            
            # 添加一个高级操作
            available_advanced = [op for op in advanced_ops if op not in operations]
            if available_advanced and random.random() > 0.3:
                operations.append(random.choice(available_advanced))
        
        return operations
    
    def _generate_operation_details(self, operations: List[SQLOperation],
                                   scenario: Dict[str, Any],
                                   schema_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成操作详情"""
        details = []
        tables = scenario.get("applicable_tables", [])
        
        for op in operations:
            detail = {
                "operation": op.value,
                "description": self._get_operation_description(op),
                "usage": self._get_operation_usage(op, tables, schema_info)
            }
            details.append(detail)
        
        return details
    
    def _get_operation_description(self, operation: SQLOperation) -> str:
        """获取操作描述"""
        descriptions = {
            SQLOperation.SELECT: "基础查询操作，选择需要的列和记录",
            SQLOperation.JOIN: "表关联操作，连接多个表的数据",
            SQLOperation.GROUP: "分组聚合操作，对数据进行统计分析",
            SQLOperation.SUBQUERY: "子查询操作，在查询中嵌套另一个查询",
            SQLOperation.WINDOW: "窗口函数操作，进行排名、累计等高级分析",
            SQLOperation.CTE: "公共表表达式，创建临时命名结果集",
            SQLOperation.UNION: "联合查询操作，合并多个查询结果"
        }
        return descriptions.get(operation, "未知操作")
    
    def _get_operation_usage(self, operation: SQLOperation,
                            tables: List[str],
                            schema_info: Dict[str, Any]) -> str:
        """获取操作使用说明"""
        if operation == SQLOperation.SELECT:
            return f"从{', '.join(tables)}中选择数据"
        elif operation == SQLOperation.JOIN:
            if len(tables) > 1:
                return f"关联{tables[0]}和{tables[1]}"
            return "关联相关表"
        elif operation == SQLOperation.GROUP:
            return f"对{tables[0] if tables else '表'}进行分组统计"
        elif operation == SQLOperation.SUBQUERY:
            return "使用子查询进行嵌套查询"
        elif operation == SQLOperation.WINDOW:
            return "使用窗口函数进行高级分析"
        elif operation == SQLOperation.CTE:
            return "使用WITH子句创建临时结果集"
        elif operation == SQLOperation.UNION:
            return "合并多个查询结果"
        else:
            return "执行查询操作"
    
    def _estimate_complexity(self, operations: List[SQLOperation]) -> str:
        """估算查询复杂度"""
        complexity_score = 0
        
        # 各操作的复杂度分数
        scores = {
            SQLOperation.SELECT: 1,
            SQLOperation.JOIN: 2,
            SQLOperation.GROUP: 2,
            SQLOperation.SUBQUERY: 3,
            SQLOperation.WINDOW: 4,
            SQLOperation.CTE: 3,
            SQLOperation.UNION: 2
        }
        
        for op in operations:
            complexity_score += scores.get(op, 1)
        
        # 根据总分判断复杂度
        if complexity_score <= 2:
            return "简单"
        elif complexity_score <= 5:
            return "中等"
        else:
            return "复杂"
    
    def _generate_rationale(self, operations: List[SQLOperation],
                           scenario: Dict[str, Any]) -> str:
        """生成操作选择理由"""
        rationale_parts = []
        
        business_purpose = scenario.get("business_purpose", "数据查询")
        rationale_parts.append(f"基于业务需求'{business_purpose}'")
        
        if SQLOperation.JOIN in operations:
            rationale_parts.append("需要关联多表数据")
        
        if SQLOperation.GROUP in operations:
            rationale_parts.append("需要进行数据聚合统计")
        
        if SQLOperation.SUBQUERY in operations:
            rationale_parts.append("使用子查询实现复杂逻辑")
        
        if SQLOperation.WINDOW in operations:
            rationale_parts.append("使用窗口函数进行高级分析")
        
        return "，".join(rationale_parts)