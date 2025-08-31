"""
场景生成工具 - 基于数据库结构生成业务场景
"""

import random
from typing import Dict, Any, List
from datetime import datetime

from tools.base_tool import BaseTool, ToolParameter
from models.schemas import QueryScenario, DifficultyLevel, SQLOperation
from config.settings import Settings


class ScenarioTool(BaseTool):
    """基于规则的业务场景生成工具"""
    
    def __init__(self, settings: Settings):
        super().__init__(settings)
        # 定义场景类别和难度分布
        self.scenario_categories = [
            "销售分析", "客户分析", "产品分析", "库存管理", 
            "财务报表", "员工管理", "系统监控", "数据统计"
        ]
        self.difficulty_distribution = {
            "easy": 0.4,
            "medium": 0.4, 
            "hard": 0.2
        }
    
    @property
    def name(self) -> str:
        return "generate_scenario"
    
    @property
    def description(self) -> str:
        return "基于数据库结构和业务领域生成查询场景"
    
    @property
    def category(self) -> str:
        return "generation"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="schema_info",
                type="object",
                description="数据库结构信息",
                required=True
            ),
            ToolParameter(
                name="domain_info",
                type="object",
                description="业务领域信息",
                required=False,
                default={}
            ),
            ToolParameter(
                name="count",
                type="integer",
                description="生成场景数量",
                required=False,
                default=10
            ),
            ToolParameter(
                name="difficulty",
                type="string",
                description="指定难度级别",
                required=False,
                enum=["easy", "medium", "hard", "mixed"]
            )
        ]
    
    def _execute(self, schema_info: Dict[str, Any], domain_info: Dict[str, Any] = None, 
                 count: int = 10, difficulty: str = "mixed") -> List[QueryScenario]:
        """
        生成查询场景
        
        Args:
            schema_info: 数据库结构信息
            domain_info: 业务领域信息
            count: 生成数量
            difficulty: 难度级别
            
        Returns:
            场景列表
        """
        scenarios = []
        tables = schema_info.get("tables", {})
        
        if not tables:
            raise ValueError("No tables found in schema info")
        
        # 根据表结构生成场景模板
        scenario_templates = self._create_scenario_templates(tables, domain_info)
        
        # 根据难度分布生成场景
        for i in range(count):
            # 确定难度
            if difficulty == "mixed":
                scenario_difficulty = self._select_difficulty()
            else:
                scenario_difficulty = DifficultyLevel[difficulty.upper()]
            
            # 选择合适的模板
            template = self._select_template(scenario_templates, scenario_difficulty)
            
            # 生成场景
            scenario = self._generate_scenario_from_template(
                template, 
                tables,
                scenario_difficulty
            )
            scenarios.append(scenario)
        
        return scenarios
    
    def _create_scenario_templates(self, tables: Dict[str, Any], 
                                  domain_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """创建场景模板"""
        templates = []
        table_names = list(tables.keys())
        
        # 基础查询模板
        for table in table_names:
            templates.append({
                "type": "basic_select",
                "category": self._infer_category(table),
                "tables": [table],
                "operations": [SQLOperation.SELECT],
                "business_purpose": f"查询{self._get_table_alias(table)}基本信息"
            })
        
        # 关联查询模板
        relationships = self._find_relationships(tables)
        for rel in relationships:
            templates.append({
                "type": "join_query",
                "category": self._infer_category(rel["from_table"]),
                "tables": [rel["from_table"], rel["to_table"]],
                "operations": [SQLOperation.JOIN],
                "business_purpose": f"关联查询{self._get_table_alias(rel['from_table'])}和{self._get_table_alias(rel['to_table'])}"
            })
        
        # 聚合查询模板
        for table in table_names:
            if self._has_numeric_columns(tables[table]):
                templates.append({
                    "type": "aggregation",
                    "category": self._infer_category(table),
                    "tables": [table],
                    "operations": [SQLOperation.GROUP],
                    "business_purpose": f"统计分析{self._get_table_alias(table)}数据"
                })
        
        # 复杂查询模板
        if len(table_names) >= 2:
            templates.append({
                "type": "complex_query",
                "category": "综合分析",
                "tables": random.sample(table_names, min(3, len(table_names))),
                "operations": [SQLOperation.SUBQUERY, SQLOperation.JOIN],
                "business_purpose": "多表综合分析"
            })
        
        return templates
    
    def _select_difficulty(self) -> DifficultyLevel:
        """根据分布选择难度"""
        rand = random.random()
        cumulative = 0
        
        for level, prob in self.difficulty_distribution.items():
            cumulative += prob
            if rand <= cumulative:
                return DifficultyLevel[level.upper()]
        
        return DifficultyLevel.MEDIUM
    
    def _select_template(self, templates: List[Dict[str, Any]], 
                        difficulty: DifficultyLevel) -> Dict[str, Any]:
        """根据难度选择模板"""
        # 根据难度过滤模板
        if difficulty == DifficultyLevel.EASY:
            filtered = [t for t in templates if t["type"] == "basic_select"]
        elif difficulty == DifficultyLevel.MEDIUM:
            filtered = [t for t in templates if t["type"] in ["join_query", "aggregation"]]
        else:  # HARD
            filtered = [t for t in templates if t["type"] == "complex_query"]
        
        if not filtered:
            filtered = templates
        
        return random.choice(filtered)
    
    def _generate_scenario_from_template(self, template: Dict[str, Any],
                                        tables: Dict[str, Any],
                                        difficulty: DifficultyLevel) -> QueryScenario:
        """从模板生成具体场景"""
        scenario = QueryScenario(
            category=template["category"],
            business_purpose=template["business_purpose"],
            complexity=difficulty,
            applicable_tables=template["tables"],
            required_operations=template["operations"]
        )
        
        # 添加更详细的描述
        scenario.description = self._generate_scenario_description(
            template, 
            tables,
            difficulty
        )
        
        return scenario
    
    def _generate_scenario_description(self, template: Dict[str, Any],
                                      tables: Dict[str, Any],
                                      difficulty: DifficultyLevel) -> str:
        """生成场景描述"""
        desc_parts = []
        
        # 基础描述
        desc_parts.append(f"业务场景：{template['business_purpose']}")
        desc_parts.append(f"涉及表：{', '.join(template['tables'])}")
        desc_parts.append(f"难度级别：{difficulty.value}")
        
        # 根据类型添加特定描述
        if template["type"] == "basic_select":
            desc_parts.append("查询类型：基础单表查询，包含条件筛选")
        elif template["type"] == "join_query":
            desc_parts.append("查询类型：多表关联查询，需要JOIN操作")
        elif template["type"] == "aggregation":
            desc_parts.append("查询类型：聚合统计查询，使用GROUP BY和聚合函数")
        elif template["type"] == "complex_query":
            desc_parts.append("查询类型：复杂查询，可能包含子查询、多表关联等")
        
        return " | ".join(desc_parts)
    
    def _infer_category(self, table_name: str) -> str:
        """推断业务类别"""
        table_lower = table_name.lower()
        
        # 根据表名推断类别
        category_keywords = {
            "销售分析": ["order", "sale", "revenue"],
            "客户分析": ["customer", "client", "user", "member"],
            "产品分析": ["product", "item", "goods", "sku"],
            "库存管理": ["inventory", "stock", "warehouse"],
            "财务报表": ["payment", "invoice", "transaction", "finance"],
            "员工管理": ["employee", "staff", "hr", "department"]
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in table_lower for keyword in keywords):
                return category
        
        # 默认类别
        return random.choice(self.scenario_categories)
    
    def _get_table_alias(self, table_name: str) -> str:
        """获取表的中文别名"""
        aliases = {
            "user": "用户",
            "customer": "客户",
            "order": "订单",
            "product": "产品",
            "employee": "员工",
            "department": "部门",
            "payment": "支付",
            "inventory": "库存"
        }
        
        table_lower = table_name.lower()
        for key, alias in aliases.items():
            if key in table_lower:
                return alias
        
        return table_name
    
    def _find_relationships(self, tables: Dict[str, Any]) -> List[Dict[str, Any]]:
        """查找表之间的关系"""
        relationships = []
        
        for table_name, table_info in tables.items():
            # 查找外键关系
            for column in table_info.get("columns", []):
                if column.get("is_foreign_key"):
                    relationships.append({
                        "from_table": table_name,
                        "to_table": column.get("referenced_table", "unknown"),
                        "join_column": column["name"]
                    })
        
        return relationships
    
    def _has_numeric_columns(self, table_info: Dict[str, Any]) -> bool:
        """检查表是否有数值列"""
        numeric_types = ["int", "decimal", "float", "double", "numeric", "number"]
        
        for column in table_info.get("columns", []):
            col_type = column.get("data_type", "").lower()
            if any(num_type in col_type for num_type in numeric_types):
                return True
        
        return False