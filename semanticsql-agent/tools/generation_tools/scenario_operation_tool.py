"""
场景-操作组合生成工具
合并了原来的scenario_tool和operation_selection_tool
内部封装三层for循环，生成所有场景-操作组合
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from langchain.tools import BaseTool
from langchain.pydantic_v1 import BaseModel, Field

logger = logging.getLogger(__name__)


class ScenarioOperationInput(BaseModel):
    """ScenarioOperationTool的输入参数"""
    mode: str = Field(
        default="get_all_combinations",
        description="生成模式：get_all_combinations（获取所有组合）或 get_single_combination（获取单个组合）"
    )
    iteration: int = Field(
        default=0,
        description="迭代次数（仅在get_single_combination模式下使用）"
    )


class ScenarioOperationTool(BaseTool):
    """场景-操作组合生成工具（核心工具）"""
    
    name = "scenario_operation_generation"
    description = "生成所有场景-操作组合，内部处理三层for循环遍历，为每个组合生成专用提示词"
    args_schema = ScenarioOperationInput
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        
        # 配置文件路径
        self.config_dir = Path(__file__).parent.parent.parent / 'config'
        
        # 加载配置
        try:
            self.scenarios = self._load_yaml('scenarios.yaml')
            self.operation_mapping = self._load_yaml('operation_mapping.yaml')
            self.complexity_config = self._load_yaml('complexity.yaml')
            self.logger.info("成功加载场景和操作配置文件")
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {e}")
            # 使用默认配置
            self._init_default_configs()
    
    def _load_yaml(self, filename: str) -> Dict:
        """加载YAML配置文件"""
        try:
            config_path = self.config_dir / filename
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
            else:
                self.logger.warning(f"配置文件不存在: {config_path}")
                return {}
        except Exception as e:
            self.logger.error(f"加载配置文件失败 {filename}: {e}")
            return {}
    
    def _init_default_configs(self):
        """初始化默认配置"""
        self.scenarios = {
            "sales_analysis": {
                "name": "销售分析",
                "description": "销售数据分析和统计",
                "sub_scenarios": {
                    "sales_statistics": {
                        "name": "销售统计",
                        "focus_areas": ["销售额", "订单量", "客户数"]
                    },
                    "sales_trends": {
                        "name": "销售趋势",
                        "focus_areas": ["时间趋势", "增长率", "季节性"]
                    }
                }
            },
            "inventory_management": {
                "name": "库存管理",
                "description": "库存状态和补货分析",
                "sub_scenarios": {
                    "inventory_status": {
                        "name": "库存状态",
                        "focus_areas": ["库存量", "库存预警", "周转率"]
                    }
                }
            }
        }
        
        self.operation_mapping = {
            "simple": ["SELECT", "WHERE"],
            "moderate": ["SELECT", "GROUP BY", "HAVING"],
            "complex": ["SELECT", "JOIN", "SUBQUERY"],
            "expert": ["SELECT", "WINDOW_FUNCTION", "CTE"]
        }
        
        self.complexity_config = {
            "simple": {"level": 1, "description": "基础查询"},
            "moderate": {"level": 2, "description": "聚合分析"},
            "complex": {"level": 3, "description": "多表关联"},
            "expert": {"level": 4, "description": "高级特性"}
        }
    
    def _run(self, mode: str = "get_all_combinations", iteration: int = 0, **kwargs) -> Dict[str, Any]:
        """执行场景-操作组合生成
        
        Args:
            mode: 生成模式
            iteration: 迭代次数（仅单个模式使用）
            
        Returns:
            场景-操作组合结果
        """
        try:
            if mode == "get_all_combinations":
                return self._generate_all_combinations()
            elif mode == "get_single_combination":
                return self._generate_single_combination(iteration)
            else:
                return {
                    "success": False,
                    "error": f"不支持的模式: {mode}",
                    "supported_modes": ["get_all_combinations", "get_single_combination"]
                }
                
        except Exception as e:
            self.logger.error(f"场景-操作生成失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _generate_all_combinations(self) -> Dict[str, Any]:
        """生成所有场景-操作组合（内部三层for循环）"""
        
        all_combinations = []
        combination_index = 0
        
        # 三层for循环（参考pipeline设计）
        for main_key, main_data in self.scenarios.items():
            if main_key in ['scenario_types', 'total_scenarios', 'total_sub_scenarios']:
                continue
                
            for sub_key, sub_data in main_data.get('sub_scenarios', {}).items():
                for complexity in ['simple', 'moderate', 'complex', 'expert']:
                    
                    # 获取操作组合
                    operations = self._get_operations_for_complexity(complexity)
                    
                    if operations:
                        # 生成专门的提示词模板
                        generated_prompt = self._generate_prompt_for_combination(
                            main_data, sub_data, complexity, operations
                        )
                        
                        combination = {
                            "combination_id": f"{main_key}_{sub_key}_{complexity}",
                            "index": combination_index,
                            "scenario": {
                                "main_key": main_key,
                                "main_name": main_data['name'],
                                "main_description": main_data['description'],
                                "sub_key": sub_key,
                                "sub_name": sub_data['name'],
                                "focus_areas": sub_data.get('focus_areas', []),
                                "complexity": complexity
                            },
                            "operations": operations,
                            "generated_prompt": generated_prompt,
                            "complexity_config": self.complexity_config.get(complexity, {})
                        }
                        
                        all_combinations.append(combination)
                        combination_index += 1
        
        result = {
            "success": True,
            "total_combinations": len(all_combinations),
            "combinations": all_combinations,
            "generation_strategy": "三层遍历：主场景×子场景×复杂度"
        }
        
        self.logger.info(f"生成了 {len(all_combinations)} 个场景-操作组合")
        return result
    
    def _generate_single_combination(self, iteration: int) -> Dict[str, Any]:
        """生成单个场景-操作组合（基于iteration选择）"""
        
        # 先生成所有组合
        all_result = self._generate_all_combinations()
        
        if not all_result["success"]:
            return all_result
        
        all_combinations = all_result["combinations"]
        
        if not all_combinations:
            return {
                "success": False,
                "error": "没有可用的场景组合"
            }
        
        # 基于iteration选择一个组合
        selected_index = iteration % len(all_combinations)
        selected_combination = all_combinations[selected_index]
        
        return {
            "success": True,
            "combination": selected_combination,
            "total_available": len(all_combinations),
            "selected_index": selected_index
        }
    
    def _get_operations_for_complexity(self, complexity: str) -> List[str]:
        """根据复杂度获取SQL操作组合"""
        return self.operation_mapping.get(complexity, ["SELECT", "WHERE"])
    
    def _generate_prompt_for_combination(self, main_data: Dict, sub_data: Dict, 
                                       complexity: str, operations: List[str]) -> str:
        """为特定组合生成专门的问题生成提示词"""
        
        complexity_desc = self.complexity_config.get(complexity, {}).get('description', complexity)
        
        prompt_template = f"""
基于{main_data['name']}场景的{sub_data['name']}任务，生成{complexity}级别的问题。

## 场景描述
{main_data['description']}

## 任务焦点
{', '.join(sub_data.get('focus_areas', []))}

## SQL操作要求
必须使用以下操作: {', '.join(operations)}

## 复杂度要求
{complexity_desc}

请生成一个符合上述要求的自然语言问题。
"""
        return prompt_template.strip()
    
    async def _arun(self, mode: str = "get_all_combinations", iteration: int = 0, **kwargs) -> Dict[str, Any]:
        """异步执行（可选实现）"""
        return self._run(mode=mode, iteration=iteration, **kwargs)