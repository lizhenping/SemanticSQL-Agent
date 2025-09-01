"""
场景生成工具 - 基于预定义模板选择业务场景
基于 LangChain BaseTool
"""

import random
from typing import Dict, Any, Type, List, Optional
from datetime import datetime

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from models.schemas import QueryScenario, DifficultyLevel, SQLOperation
from models.exceptions import ToolExecutionError


class ScenarioToolInput(BaseModel):
    """场景工具输入"""
    iteration: int = Field(default=0, description="当前迭代次数")


class ScenarioTool(BaseTool):
    """基于预定义模板选择业务场景"""
    
    name: str = "scenario_tool"
    description: str = "从预定义的场景模板中选择一个适合当前数据库的业务场景"
    args_schema: Type[BaseModel] = ScenarioToolInput
    
    def __init__(self):
        super().__init__()
        # 使用object.__setattr__避开Pydantic验证
        object.__setattr__(self, 'scenario_templates', self._initialize_scenario_templates())
        object.__setattr__(self, 'difficulty_weights', {
            DifficultyLevel.EASY: 0.4,
            DifficultyLevel.MEDIUM: 0.4,
            DifficultyLevel.HARD: 0.15,
            DifficultyLevel.EXPERT: 0.05
        })
    
    def _run(self, iteration: int = 0, **kwargs) -> Dict[str, Any]:
        """选择一个场景"""
        try:
            
            # ScenarioTool基于预定义模板工作，不需要数据库分析结果
            # 它会返回通用的业务场景，供后续工具使用
            
            # 基于迭代次数选择不同的场景模板（避免重复）
            scenario_index = iteration % len(self.scenario_templates)
            selected_template = self.scenario_templates[scenario_index]
            
            # 创建场景实例（简化版本，不依赖具体表信息）
            scenario_id = f"scenario_{iteration}_{datetime.now().strftime('%H%M%S')}"
            
            return {
                "scenario_id": scenario_id,
                "category": selected_template["category"],
                "business_purpose": selected_template["business_purpose"],
                "complexity": selected_template["complexity"].value,
                "applicable_operations": [op.value for op in selected_template["suggested_operations"]],
                "description": selected_template["description"],
                "template_id": selected_template["id"]
            }
            
        except Exception as e:
            raise ToolExecutionError(
                tool_name=self.name,
                reason=f"场景选择失败: {str(e)}"
            )
    
    def _initialize_scenario_templates(self) -> List[Dict[str, Any]]:
        """初始化预定义的场景模板"""
        return [
            # 电商领域场景
            {
                "id": "ecom_sales_daily",
                "domain": "电商",
                "category": "销售分析",
                "business_purpose": "统计每日销售情况",
                "required_tables": ["order"],
                "optional_tables": ["product", "customer"],
                "complexity": DifficultyLevel.EASY,
                "suggested_operations": [SQLOperation.SELECT, SQLOperation.GROUP],
                "description": "统计指定日期范围内的销售额、订单数等基础指标"
            },
            {
                "id": "ecom_top_products",
                "domain": "电商",
                "category": "产品分析",
                "business_purpose": "查找热销商品",
                "required_tables": ["order", "product"],
                "optional_tables": ["category"],
                "complexity": DifficultyLevel.MEDIUM,
                "suggested_operations": [SQLOperation.SELECT, SQLOperation.JOIN, SQLOperation.GROUP],
                "description": "分析销量最高的商品，包含商品信息和销售数据"
            },
            {
                "id": "ecom_customer_value",
                "domain": "电商",
                "category": "客户分析",
                "business_purpose": "客户价值分析",
                "required_tables": ["order", "customer"],
                "optional_tables": ["payment"],
                "complexity": DifficultyLevel.HARD,
                "suggested_operations": [SQLOperation.SELECT, SQLOperation.JOIN, SQLOperation.GROUP, SQLOperation.WINDOW],
                "description": "计算客户生命周期价值，识别高价值客户"
            },
            
            # 金融领域场景
            {
                "id": "fin_account_balance",
                "domain": "金融",
                "category": "账户分析",
                "business_purpose": "账户余额查询",
                "required_tables": ["account"],
                "optional_tables": ["transaction"],
                "complexity": DifficultyLevel.EASY,
                "suggested_operations": [SQLOperation.SELECT],
                "description": "查询账户当前余额和基本信息"
            },
            {
                "id": "fin_transaction_summary",
                "domain": "金融",
                "category": "交易分析",
                "business_purpose": "交易汇总统计",
                "required_tables": ["transaction"],
                "optional_tables": ["account"],
                "complexity": DifficultyLevel.MEDIUM,
                "suggested_operations": [SQLOperation.SELECT, SQLOperation.GROUP],
                "description": "按时间、类型等维度统计交易数据"
            },
            
            # 通用场景
            {
                "id": "gen_data_overview",
                "domain": "通用",
                "category": "数据统计",
                "business_purpose": "数据概览",
                "required_tables": [],
                "optional_tables": [],
                "complexity": DifficultyLevel.EASY,
                "suggested_operations": [SQLOperation.SELECT],
                "description": "统计表的记录数、数据分布等基础信息"
            },
            {
                "id": "gen_date_analysis",
                "domain": "通用",
                "category": "时间分析",
                "business_purpose": "时间序列分析",
                "required_tables": [],
                "optional_tables": [],
                "complexity": DifficultyLevel.MEDIUM,
                "suggested_operations": [SQLOperation.SELECT, SQLOperation.GROUP],
                "description": "按时间维度分析数据变化趋势"
            },
            {
                "id": "gen_join_analysis",
                "domain": "通用",
                "category": "关联分析",
                "business_purpose": "多表关联查询",
                "required_tables": [],
                "optional_tables": [],
                "complexity": DifficultyLevel.MEDIUM,
                "suggested_operations": [SQLOperation.SELECT, SQLOperation.JOIN],
                "description": "通过关联多个表获取综合信息"
            },
            {
                "id": "gen_complex_analysis",
                "domain": "通用",
                "category": "复杂分析",
                "business_purpose": "高级数据分析",
                "required_tables": [],
                "optional_tables": [],
                "complexity": DifficultyLevel.EXPERT,
                "suggested_operations": [SQLOperation.SELECT, SQLOperation.JOIN, SQLOperation.SUBQUERY, SQLOperation.WINDOW],
                "description": "使用子查询、窗口函数等高级特性进行复杂分析"
            }
        ]
    
    def _filter_applicable_scenarios(
        self, 
        tables: List[str], 
        domain: str
    ) -> List[Dict[str, Any]]:
        """筛选适用的场景"""
        applicable = []
        table_names_lower = [t.lower() for t in tables]
        
        for template in self.scenario_templates:
            # 检查领域匹配
            if template["domain"] != "通用" and template["domain"] != domain:
                continue
            
            # 检查必需表
            required_tables = template.get("required_tables", [])
            if required_tables:
                # 检查是否包含所有必需表（模糊匹配）
                all_found = True
                for req_table in required_tables:
                    found = any(
                        req_table.lower() in table_name 
                        for table_name in table_names_lower
                    )
                    if not found:
                        all_found = False
                        break
                
                if not all_found:
                    continue
            
            applicable.append(template)
        
        return applicable
    
    def _create_scenario_from_template(
        self, 
        template: Dict[str, Any],
        tables: List[str],
        iteration: int
    ) -> QueryScenario:
        """从模板创建场景实例"""
        # 确定适用的表
        applicable_tables = []
        table_names_lower = [t.lower() for t in tables]
        
        # 添加必需表
        for req_table in template.get("required_tables", []):
            for i, table_name in enumerate(table_names_lower):
                if req_table.lower() in table_name:
                    applicable_tables.append(tables[i])
                    break
        
        # 添加一些可选表
        optional_tables = template.get("optional_tables", [])
        for opt_table in optional_tables[:2]:  # 最多添加2个可选表
            for i, table_name in enumerate(table_names_lower):
                if opt_table.lower() in table_name and tables[i] not in applicable_tables:
                    applicable_tables.append(tables[i])
                    break
        
        # 如果没有找到特定表，随机选择一些
        if not applicable_tables and tables:
            num_tables = min(3, len(tables))
            applicable_tables = random.sample(tables, num_tables)
        
        # 创建场景
        scenario = QueryScenario(
            category=template["category"],
            business_purpose=template["business_purpose"],
            complexity=template["complexity"],
            applicable_tables=applicable_tables,
            suggested_operations=template["suggested_operations"],
            description=f"{template['description']} (迭代 {iteration + 1})"
        )
        
        return scenario
    
    async def _arun(self, memory: Dict[str, Any], iteration: int = 0) -> Dict[str, Any]:
        """异步执行（当前实现为同步）"""
        return self._run(memory, iteration)