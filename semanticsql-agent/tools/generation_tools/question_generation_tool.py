"""
问题生成工具 - 生成自然语言查询问题
"""

import random
from typing import Dict, Any, List, Optional
from openai import OpenAI

from tools.base_tool import BaseTool, ToolParameter
from models.schemas import QueryScenario, SQLOperation
from models.exceptions import LLMError
from config.settings import Settings


class QuestionGenerationTool(BaseTool):
    """基于场景生成自然语言问题"""
    
    def __init__(self, settings: Settings):
        super().__init__(settings)
        # 初始化LLM客户端
        self.llm_client = OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key
        )
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature
    
    @property
    def name(self) -> str:
        return "generate_question"
    
    @property
    def description(self) -> str:
        return "根据场景和操作生成自然语言查询问题"
    
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
                name="operations",
                type="array",
                description="SQL操作类型",
                required=True
            ),
            ToolParameter(
                name="schema_info",
                type="object",
                description="数据库结构信息",
                required=True
            ),
            ToolParameter(
                name="style",
                type="string",
                description="问题风格",
                required=False,
                enum=["formal", "casual", "technical"],
                default="formal"
            ),
            ToolParameter(
                name="use_llm",
                type="boolean",
                description="是否使用LLM生成",
                required=False,
                default=True
            )
        ]
    
    def _execute(self, scenario: Dict[str, Any], operations: List[str],
                 schema_info: Dict[str, Any], style: str = "formal",
                 use_llm: bool = True) -> Dict[str, Any]:
        """
        生成自然语言问题
        
        Returns:
            包含问题和元数据的字典
        """
        if use_llm and self.llm_client:
            # 使用LLM生成
            question = self._generate_with_llm(scenario, operations, schema_info, style)
        else:
            # 使用模板生成
            question = self._generate_with_template(scenario, operations, schema_info, style)
        
        # 生成问题变体
        variations = self._generate_variations(question, style)
        
        return {
            "question": question,
            "variations": variations,
            "style": style,
            "keywords": self._extract_keywords(question, scenario),
            "intent": self._identify_intent(operations)
        }
    
    def _generate_with_llm(self, scenario: Dict[str, Any], operations: List[str],
                          schema_info: Dict[str, Any], style: str) -> str:
        """使用LLM生成问题"""
        try:
            # 构建提示词
            prompt = self._build_llm_prompt(scenario, operations, schema_info, style)
            
            # 调用LLM
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个数据分析师，擅长将业务需求转换为自然语言查询问题。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=200
            )
            
            question = response.choices[0].message.content.strip()
            return question
            
        except Exception as e:
            self.logger.warning(f"LLM generation failed: {e}, falling back to template")
            return self._generate_with_template(scenario, operations, schema_info, style)
    
    def _generate_with_template(self, scenario: Dict[str, Any], operations: List[str],
                               schema_info: Dict[str, Any], style: str) -> str:
        """使用模板生成问题"""
        templates = self._get_question_templates(operations, style)
        template = random.choice(templates)
        
        # 填充模板
        question = self._fill_template(template, scenario, schema_info)
        
        return question
    
    def _build_llm_prompt(self, scenario: Dict[str, Any], operations: List[str],
                         schema_info: Dict[str, Any], style: str) -> str:
        """构建LLM提示词"""
        tables = scenario.get("applicable_tables", [])
        business_purpose = scenario.get("business_purpose", "数据查询")
        
        prompt = f"""基于以下信息生成一个自然语言查询问题：

业务场景：{business_purpose}
涉及的表：{', '.join(tables)}
SQL操作：{', '.join(operations)}
难度级别：{scenario.get('complexity', 'medium')}
问题风格：{style}

表结构信息：
"""
        
        # 添加相关表的结构信息
        for table in tables:
            if table in schema_info.get("tables", {}):
                table_info = schema_info["tables"][table]
                columns = [col["name"] for col in table_info.get("columns", [])]
                prompt += f"\n{table}表字段：{', '.join(columns[:10])}"
        
        prompt += f"""

请生成一个{self._get_style_description(style)}的自然语言问题，要求：
1. 符合业务场景
2. 体现所需的SQL操作
3. 表述清晰自然
4. 不要直接提及表名和字段名

生成的问题："""
        
        return prompt
    
    def _get_question_templates(self, operations: List[str], style: str) -> List[str]:
        """获取问题模板"""
        templates = []
        
        # 根据操作类型选择模板
        if "SELECT" in operations:
            if style == "formal":
                templates.extend([
                    "请查询{entity}的{attribute}信息",
                    "获取所有{condition}的{entity}数据",
                    "显示{time_range}内的{entity}记录"
                ])
            elif style == "casual":
                templates.extend([
                    "帮我看看{entity}的{attribute}",
                    "查一下{condition}的{entity}",
                    "找出{time_range}的{entity}"
                ])
            else:  # technical
                templates.extend([
                    "检索{entity}表中{condition}的记录",
                    "提取{entity}的{attribute}字段",
                    "查询满足{condition}条件的{entity}数据"
                ])
        
        if "JOIN" in operations:
            if style == "formal":
                templates.extend([
                    "请显示{entity1}及其对应的{entity2}信息",
                    "查询{entity1}关联的{entity2}数据",
                    "获取{entity1}和{entity2}的关联信息"
                ])
            else:
                templates.extend([
                    "把{entity1}和{entity2}的信息一起显示",
                    "查看{entity1}对应的{entity2}",
                    "关联查询{entity1}和{entity2}"
                ])
        
        if "GROUP" in operations:
            if style == "formal":
                templates.extend([
                    "请统计各{group_by}的{metric}",
                    "按{group_by}分组计算{metric}",
                    "汇总每个{group_by}的{metric}数据"
                ])
            else:
                templates.extend([
                    "统计一下各{group_by}的{metric}",
                    "按{group_by}算一下{metric}",
                    "看看每个{group_by}的{metric}是多少"
                ])
        
        # 默认模板
        if not templates:
            templates = ["查询{entity}的相关信息"]
        
        return templates
    
    def _fill_template(self, template: str, scenario: Dict[str, Any],
                      schema_info: Dict[str, Any]) -> str:
        """填充模板变量"""
        tables = scenario.get("applicable_tables", [])
        
        # 准备填充值
        replacements = {
            "{entity}": self._get_entity_name(tables[0] if tables else "数据"),
            "{entity1}": self._get_entity_name(tables[0] if tables else "数据"),
            "{entity2}": self._get_entity_name(tables[1] if len(tables) > 1 else "相关数据"),
            "{attribute}": self._get_random_attribute(schema_info, tables),
            "{condition}": self._get_random_condition(),
            "{time_range}": self._get_random_time_range(),
            "{group_by}": self._get_groupby_field(),
            "{metric}": self._get_random_metric()
        }
        
        # 替换模板中的变量
        question = template
        for key, value in replacements.items():
            question = question.replace(key, value)
        
        return question
    
    def _get_entity_name(self, table_name: str) -> str:
        """获取实体名称"""
        entity_map = {
            "user": "用户",
            "customer": "客户",
            "order": "订单",
            "product": "产品",
            "employee": "员工",
            "sale": "销售",
            "inventory": "库存"
        }
        
        table_lower = table_name.lower()
        for key, value in entity_map.items():
            if key in table_lower:
                return value
        
        return table_name
    
    def _get_random_attribute(self, schema_info: Dict[str, Any], tables: List[str]) -> str:
        """获取随机属性"""
        attributes = ["基本", "详细", "完整", "主要", "关键"]
        return random.choice(attributes)
    
    def _get_random_condition(self) -> str:
        """获取随机条件"""
        conditions = [
            "状态为有效",
            "金额大于1000",
            "最近更新",
            "本月新增",
            "优先级较高"
        ]
        return random.choice(conditions)
    
    def _get_random_time_range(self) -> str:
        """获取随机时间范围"""
        ranges = ["本月", "本季度", "今年", "最近7天", "上个月"]
        return random.choice(ranges)
    
    def _get_groupby_field(self) -> str:
        """获取分组字段"""
        fields = ["类别", "部门", "地区", "月份", "产品类型"]
        return random.choice(fields)
    
    def _get_random_metric(self) -> str:
        """获取随机指标"""
        metrics = ["总金额", "数量", "平均值", "最大值", "记录数"]
        return random.choice(metrics)
    
    def _generate_variations(self, question: str, style: str) -> List[str]:
        """生成问题变体"""
        variations = []
        
        # 简单的变体生成
        if style == "formal":
            variations.append(question.replace("请", "麻烦"))
            variations.append(question.replace("查询", "检索"))
        elif style == "casual":
            variations.append(question.replace("帮我", "给我"))
            variations.append(question.replace("看看", "查查"))
        
        return variations[:2]  # 返回最多2个变体
    
    def _extract_keywords(self, question: str, scenario: Dict[str, Any]) -> List[str]:
        """提取关键词"""
        keywords = []
        
        # 从场景中提取
        keywords.append(scenario.get("category", ""))
        
        # 从问题中提取常见关键词
        common_keywords = ["查询", "统计", "分析", "获取", "显示", "计算"]
        for keyword in common_keywords:
            if keyword in question:
                keywords.append(keyword)
        
        return list(set(filter(None, keywords)))
    
    def _identify_intent(self, operations: List[str]) -> str:
        """识别查询意图"""
        if "GROUP" in operations:
            return "aggregation"
        elif "JOIN" in operations:
            return "relationship"
        elif "SUBQUERY" in operations:
            return "nested"
        else:
            return "simple_query"
    
    def _get_style_description(self, style: str) -> str:
        """获取风格描述"""
        descriptions = {
            "formal": "正式、专业",
            "casual": "口语化、自然",
            "technical": "技术性、精确"
        }
        return descriptions.get(style, "标准")