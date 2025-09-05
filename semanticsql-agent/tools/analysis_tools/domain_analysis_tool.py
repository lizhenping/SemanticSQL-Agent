"""
领域分析工具 - 优化版本
简化设计，移除过度异常处理，按就近原则组织代码
"""

from typing import Dict, Any, Type, List
import json
from pydantic import BaseModel, Field

from models.exceptions import ToolExecutionError
from prompts.manager import PromptManager
from ..base_tool import BaseSemanticSQLTool


# ========== 工具内部数据模型（就近原则）==========
class DomainAnalysisInput(BaseModel):
    """领域分析输入参数"""
    use_llm: bool = Field(default=False, description="是否使用LLM增强分析")


class DomainKeywords(BaseModel):
    """领域关键词配置"""
    domain_name: str
    table_keywords: List[str]
    column_keywords: List[str]
    confidence_weight: float = 1.0


class DomainMatchResult(BaseModel):
    """领域匹配结果"""
    domain_name: str
    matched_tables: List[str]
    matched_columns: List[str]
    match_score: float
    confidence: float


class DomainAnalysisResult(BaseModel):
    """领域分析结果"""
    primary_domain: str
    secondary_domains: List[str]
    business_concepts: List[str]
    confidence_score: float
    domain_description: str
    key_entities: List[str]


class DomainAnalysisTool(BaseSemanticSQLTool):
    """领域分析工具 - 优化版本
    
    职责：
    - 基于数据库结构识别业务领域
    - 分析表名和字段名的业务语义
    - 计算领域匹配置信度
    
    设计原则：
    - 单一职责：专注领域识别
    - 方法拆分：每个方法<30行
    - 类型安全：使用Pydantic模型
    - 简化异常：让异常自然传播
    """
    
    name: str = "domain_analysis"
    description: str = "分析数据库的业务领域，识别主要业务场景和数据特征"
    args_schema: Type[BaseModel] = DomainAnalysisInput

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, 'prompt_manager', PromptManager())
        object.__setattr__(self, '_domain_keywords', self._initialize_domain_keywords())

    def _run(self, use_llm: bool = False, **kwargs) -> str:
        """执行领域分析 - 主流程"""
        # 获取数据库结构信息
        schema_info = self._get_schema_info()
        
        # 分析业务领域
        domain_matches = self._match_domains_from_schema(schema_info)
        
        # 生成分析结果
        result = self._build_analysis_result(domain_matches, schema_info)
        
        # 保存并返回
        self.save_to_memory("domain_analysis", result)
        return json.dumps(result, ensure_ascii=False)
    
    # ========== 核心分析逻辑 ==========
    def _get_schema_info(self) -> Dict[str, Any]:
        """获取数据库结构信息"""
        schema_info = self.get_from_memory("schema_extraction")
        if not schema_info:
            raise ToolExecutionError(
                tool_name=self.name,
                reason="无法获取数据库结构信息，需要先运行schema_extraction工具"
            )
        return schema_info
    
    def _initialize_domain_keywords(self) -> List[DomainKeywords]:
        """初始化领域关键词配置"""
        return [
            DomainKeywords(
                domain_name="电商",
                table_keywords=["order", "product", "customer", "payment", "cart", "shop"],
                column_keywords=["price", "amount", "quantity", "sku", "order_id"]
            ),
            DomainKeywords(
                domain_name="财务",
                table_keywords=["account", "transaction", "payment", "invoice", "billing"],
                column_keywords=["amount", "balance", "cost", "fee", "tax"]
            ),
            DomainKeywords(
                domain_name="人事",
                table_keywords=["employee", "department", "salary", "attendance", "user"],
                column_keywords=["salary", "position", "department", "hire_date"]
            ),
            DomainKeywords(
                domain_name="库存",
                table_keywords=["inventory", "stock", "warehouse", "supplier", "goods"],
                column_keywords=["stock", "quantity", "supplier", "warehouse"]
            ),
            DomainKeywords(
                domain_name="内容管理",
                table_keywords=["article", "post", "content", "media", "news"],
                column_keywords=["title", "content", "author", "publish_date"]
            )
        ]
    
    def _match_domains_from_schema(self, schema_info: Dict[str, Any]) -> List[DomainMatchResult]:
        """从数据库结构匹配业务领域"""
        tables = schema_info.get("tables", {})
        domain_matches = []
        
        for domain_config in self._domain_keywords:
            match_result = self._match_single_domain(domain_config, tables)
            if match_result.match_score > 0:
                domain_matches.append(match_result)
        
        # 按匹配得分排序
        return sorted(domain_matches, key=lambda x: x.match_score, reverse=True)
    
    def _match_single_domain(self, domain_config: DomainKeywords, tables: Dict[str, Any]) -> DomainMatchResult:
        """匹配单个领域"""
        matched_tables = []
        matched_columns = []
        table_score = 0
        column_score = 0
        
        for table_name, table_info in tables.items():
            # 匹配表名
            if self._match_table_name(table_name, domain_config.table_keywords):
                matched_tables.append(table_name)
                table_score += 1
            
            # 匹配列名
            columns = table_info.get("columns", [])
            for column in columns:
                column_name = column.get("name", "")
                if self._match_column_name(column_name, domain_config.column_keywords):
                    matched_columns.append(f"{table_name}.{column_name}")
                    column_score += 0.5
        
        match_score = (table_score * 2 + column_score) * domain_config.confidence_weight
        confidence = min(0.95, match_score / max(1, len(tables)) * 0.8)
        
        return DomainMatchResult(
            domain_name=domain_config.domain_name,
            matched_tables=matched_tables,
            matched_columns=matched_columns,
            match_score=match_score,
            confidence=confidence
        )
    
    def _match_table_name(self, table_name: str, keywords: List[str]) -> bool:
        """匹配表名关键词"""
        table_lower = table_name.lower()
        return any(keyword in table_lower for keyword in keywords)
    
    def _match_column_name(self, column_name: str, keywords: List[str]) -> bool:
        """匹配列名关键词"""
        column_lower = column_name.lower()
        return any(keyword in column_lower for keyword in keywords)
    
    def _build_analysis_result(self, domain_matches: List[DomainMatchResult], schema_info: Dict[str, Any]) -> Dict[str, Any]:
        """构建分析结果"""
        if not domain_matches:
            return self._build_default_result(schema_info)
        
        # 选择主要领域和次要领域
        primary_match = domain_matches[0]
        secondary_domains = [match.domain_name for match in domain_matches[1:3] if match.confidence > 0.2]
        
        # 提取业务概念
        business_concepts = self._extract_business_concepts(domain_matches, schema_info)
        
        # 构建结果
        return {
            "primary_domain": primary_match.domain_name,
            "secondary_domains": secondary_domains,
            "business_concepts": business_concepts,
            "confidence_score": primary_match.confidence,
            "domain_description": f"基于数据库结构分析，该系统主要属于{primary_match.domain_name}领域",
            "key_entities": list(schema_info.get("tables", {}).keys())[:8],
            "match_details": {
                "matched_tables": primary_match.matched_tables,
                "matched_columns": primary_match.matched_columns[:10],
                "match_score": primary_match.match_score
            },
            "analysis_summary": f"识别出{len(domain_matches)}个可能的业务领域，主领域为{primary_match.domain_name}"
        }
    
    def _build_default_result(self, schema_info: Dict[str, Any]) -> Dict[str, Any]:
        """构建默认结果（未匹配到特定领域时）"""
        tables = list(schema_info.get("tables", {}).keys())
        return {
            "primary_domain": "通用业务",
            "secondary_domains": [],
            "business_concepts": tables[:5],
            "confidence_score": 0.1,
            "domain_description": "未能识别出明确的业务领域，可能为通用型数据库",
            "key_entities": tables[:8],
            "match_details": {
                "matched_tables": [],
                "matched_columns": [],
                "match_score": 0.0
            },
            "analysis_summary": f"分析了{len(tables)}个表，未识别出特定业务领域"
        }
    
    def _extract_business_concepts(self, domain_matches: List[DomainMatchResult], schema_info: Dict[str, Any]) -> List[str]:
        """提取业务概念"""
        concepts = set()
        
        # 从匹配的表名提取概念
        for match in domain_matches[:2]:
            concepts.update(match.matched_tables)
        
        # 从表名中提取其他概念词
        for table_name in schema_info.get("tables", {}).keys():
            # 简单的概念提取：去掉常见前后缀
            clean_name = table_name.lower().replace("_", " ").replace("t_", "").replace("tbl_", "")
            if len(clean_name) > 2 and clean_name not in ["id", "key", "info", "data"]:
                concepts.add(clean_name)
        
        return list(concepts)[:10]
    
    async def _arun(self, use_llm: bool = False, **kwargs) -> str:
        """异步执行（当前实现为同步）"""
        return self._run(use_llm, **kwargs)