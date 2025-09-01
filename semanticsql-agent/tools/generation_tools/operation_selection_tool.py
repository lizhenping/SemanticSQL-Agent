"""
操作选择工具 - 根据场景选择合适的SQL操作
基于 LangChain BaseTool
"""

from typing import Dict, Any, Type, List
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from models.schemas import SQLOperation, DifficultyLevel
from models.exceptions import ToolExecutionError


class OperationSelectionInput(BaseModel):
    """操作选择输入"""
    scenario: Dict[str, Any] = Field(description="场景信息")
    memory: Dict[str, Any] = Field(description="包含数据库分析结果的记忆")


class OperationSelectionTool(BaseTool):
    """根据场景选择SQL操作"""
    
    name: str = "operation_selection"
    description: str = "根据场景复杂度和业务需求选择合适的SQL操作组合"
    # args_schema: Type[BaseModel] = OperationSelectionInput
    
    def _run(self, tool_input: str = "", **kwargs) -> Dict[str, Any]:
        """选择SQL操作"""
        try:
            # 解析JSON输入参数
            import json
            scenario = {}
            try:
                if tool_input:
                    input_data = json.loads(tool_input)
                    scenario = input_data.get('scenario', {})
                    if isinstance(scenario, str):
                        # 如果scenario是字符串，再次尝试解析
                        scenario = json.loads(scenario)
            except:
                scenario = {}
            
            complexity = scenario.get("complexity", "medium")
            category = scenario.get("category", "")
            suggested_operations = scenario.get("applicable_operations", [])
            
            # 如果场景已经有建议的操作，直接使用
            if suggested_operations:
                operations = suggested_operations
            else:
                # 基于复杂度选择操作
                operations = self._select_operations_by_complexity(complexity, category)
            
            # 生成操作描述
            operation_plan = self._generate_operation_plan(operations, scenario)
            
            return {
                "selected_operations": operations,
                "operation_count": len(operations),
                "complexity_level": complexity,
                "operation_plan": operation_plan,
                "estimated_difficulty": self._estimate_difficulty(operations)
            }
            
        except Exception as e:
            raise ToolExecutionError(
                tool_name=self.name,
                reason=f"操作选择失败: {str(e)}"
            )
    
    def _select_operations_by_complexity(
        self, 
        complexity: str, 
        category: str
    ) -> List[str]:
        """基于复杂度选择操作"""
        if complexity == "easy":
            # 简单查询
            return [SQLOperation.SELECT.value]
        
        elif complexity == "medium":
            # 中等复杂度
            if "分析" in category or "统计" in category:
                return [SQLOperation.SELECT.value, SQLOperation.GROUP.value]
            elif "关联" in category:
                return [SQLOperation.SELECT.value, SQLOperation.JOIN.value]
            else:
                return [SQLOperation.SELECT.value, SQLOperation.GROUP.value]
        
        elif complexity == "hard":
            # 复杂查询
            if "分析" in category:
                return [
                    SQLOperation.SELECT.value,
                    SQLOperation.JOIN.value,
                    SQLOperation.GROUP.value
                ]
            else:
                return [
                    SQLOperation.SELECT.value,
                    SQLOperation.JOIN.value,
                    SQLOperation.SUBQUERY.value
                ]
        
        else:  # expert
            # 专家级查询
            return [
                SQLOperation.SELECT.value,
                SQLOperation.JOIN.value,
                SQLOperation.GROUP.value,
                SQLOperation.WINDOW.value,
                SQLOperation.CTE.value
            ]
    
    def _generate_operation_plan(
        self, 
        operations: List[str], 
        scenario: Dict[str, Any]
    ) -> str:
        """生成操作计划描述"""
        plans = []
        
        if SQLOperation.SELECT.value in operations:
            plans.append("选择需要的字段")
        
        if SQLOperation.JOIN.value in operations:
            tables = scenario.get("applicable_tables", [])
            if len(tables) > 1:
                plans.append(f"关联表：{', '.join(tables[:3])}")
            else:
                plans.append("关联相关表")
        
        if SQLOperation.GROUP.value in operations:
            plans.append("按维度分组统计")
        
        if SQLOperation.WINDOW.value in operations:
            plans.append("使用窗口函数进行高级分析")
        
        if SQLOperation.SUBQUERY.value in operations:
            plans.append("使用子查询处理复杂逻辑")
        
        if SQLOperation.CTE.value in operations:
            plans.append("使用CTE组织复杂查询")
        
        if SQLOperation.UNION.value in operations:
            plans.append("合并多个查询结果")
        
        return " -> ".join(plans)
    
    def _estimate_difficulty(self, operations: List[str]) -> str:
        """估计查询难度"""
        score = 0
        
        # 基于操作计算难度分数
        operation_scores = {
            SQLOperation.SELECT.value: 1,
            SQLOperation.JOIN.value: 2,
            SQLOperation.GROUP.value: 2,
            SQLOperation.SUBQUERY.value: 3,
            SQLOperation.WINDOW.value: 4,
            SQLOperation.CTE.value: 3,
            SQLOperation.UNION.value: 2
        }
        
        for op in operations:
            score += operation_scores.get(op, 1)
        
        # 根据分数判断难度
        if score <= 2:
            return "简单"
        elif score <= 5:
            return "中等"
        elif score <= 8:
            return "困难"
        else:
            return "专家"
    
    async def _arun(
        self, 
        scenario: Dict[str, Any], 
        memory: Dict[str, Any]
    ) -> Dict[str, Any]:
        """异步执行（当前实现为同步）"""
        return self._run(scenario, memory)