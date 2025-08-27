"""业务领域分析工具

参考 nl2sql_pipeline 的 initial_domain_analysis_pipeline 实现，
使用智能体方式分析数据库的业务领域。
"""

from tools.base import BaseSemanticSQLTool
from typing import Dict, Any, List, Optional
from models.analysis_models import (
    DomainAnalysisInput,
    DomainAnalysisOutput,
    DomainKnowledge,
    DomainCharacteristics,
    SchemaExtractionOutput
)
from utils.output_parsers import (
    create_structured_output_parser,
    get_pydantic_format_instruction
)
import logging

logger = logging.getLogger(__name__)


class DomainAnalysisTool(BaseSemanticSQLTool):
    """业务领域分析工具
    
    分析数据库的业务领域，识别核心概念、实体关系和业务规则。
    这是分析流程的第二步，基于架构信息进行深入的业务理解。
    """
    
    name = "analyze_business_domain"
    description = (
        "分析数据库的业务领域，识别关键实体、业务规则和专业术语。"
        "需要先执行 extract_database_schema 获取结构信息。"
        "输出包括领域类型、核心实体、业务流程和术语解释。"
    )
    args_schema = DomainAnalysisInput
    
    def execute(
        self, 
        schema_info: SchemaExtractionOutput,
        focus_tables: Optional[List[str]] = None,
        include_sample_data: bool = True
    ) -> DomainAnalysisOutput:
        """执行领域分析"""
        logger.info("开始业务领域分析")
        
        # 提取基本信息
        database_name = schema_info.database_name
        tables = schema_info.tables
        
        if not tables:
            return DomainAnalysisOutput(
                success=False,
                database_name=database_name,
                domain_analysis=self._get_default_domain_knowledge(),
                domain_knowledge={},
                analyzed_tables=0,
                summary="",
                error="未提供表信息，请先执行 extract_database_schema"
            )
        
        # 筛选要分析的表
        if focus_tables:
            tables = [t for t in tables if t.name in focus_tables]
            logger.info(f"聚焦分析 {len(tables)} 个表: {focus_tables}")
        
        # 准备分析数据
        analysis_data = self._prepare_analysis_data(tables, include_sample_data)
        
        # 使用 LLM 进行领域分析
        domain_knowledge = self._analyze_with_llm(
            database_name,
            analysis_data,
            tables
        )
        
        # 生成领域知识详情
        domain_knowledge_dict = self._generate_domain_knowledge_dict(
            domain_knowledge,
            tables,
            analysis_data
        )
        
        return DomainAnalysisOutput(
            success=True,
            database_name=database_name,
            domain_analysis=domain_knowledge,
            domain_knowledge=domain_knowledge_dict,
            analyzed_tables=len(tables),
            summary=self._generate_summary(domain_knowledge)
        )
    
    def _prepare_analysis_data(
        self, 
        tables: List[TableDetail], 
        include_sample_data: bool
    ) -> Dict[str, Any]:
        """准备分析所需的数据"""
        analysis_data = {
            "table_summaries": {},
            "field_statistics": {},
            "sample_data": {}
        }
        
        for table in tables:
            table_name = table.name
            
            # 表摘要
            analysis_data["table_summaries"][table_name] = self._create_table_summary(table)
            
            # 字段统计
            analysis_data["field_statistics"][table_name] = self._analyze_table_fields(table)
            
            # 样本数据
            if include_sample_data and table.row_count and table.row_count > 0:
                sample = self._get_sample_data(table_name, limit=5)
                if sample:
                    analysis_data["sample_data"][table_name] = sample
        
        return analysis_data
    
    def _create_table_summary(self, table: TableDetail) -> str:
        """创建表摘要"""
        parts = []
        
        # 基本信息
        parts.append(f"表名: {table.name}")
        
        if table.comment:
            parts.append(f"注释: {table.comment}")
        
        if table.row_count is not None:
            parts.append(f"行数: {table.row_count:,}")
        
        # 列信息
        parts.append(f"列数: {len(table.columns)}")
        
        # 主键
        if table.primary_keys:
            parts.append(f"主键: {', '.join(table.primary_keys)}")
        
        # 外键
        if table.foreign_keys:
            fk_summary = []
            for fk in table.foreign_keys[:3]:  # 最多显示3个
                fk_summary.append(f"{fk.column} -> {fk.referenced_table}.{fk.referenced_column}")
            parts.append(f"外键: {'; '.join(fk_summary)}")
            if len(table.foreign_keys) > 3:
                parts.append(f"... 还有 {len(table.foreign_keys) - 3} 个外键")
        
        return "\n".join(parts)
    
    def _analyze_table_fields(self, table: TableDetail) -> Dict[str, Any]:
        """分析表的字段特征"""
        columns = table.columns
        
        # 统计数据类型
        type_distribution = {}
        nullable_count = 0
        
        for col in columns:
            # 数据类型
            data_type = col.data_type.split('(')[0].upper()
            type_distribution[data_type] = type_distribution.get(data_type, 0) + 1
            
            # 可空性
            if col.is_nullable:
                nullable_count += 1
        
        # 识别特殊字段
        special_fields = {
            "id_fields": [],
            "name_fields": [],
            "time_fields": [],
            "status_fields": [],
            "amount_fields": []
        }
        
        for col in columns:
            col_name = col.name.lower()
            
            # ID 字段
            if any(keyword in col_name for keyword in ["id", "_id", "code", "no"]):
                special_fields["id_fields"].append(col.name)
            
            # 名称字段
            elif any(keyword in col_name for keyword in ["name", "title", "desc"]):
                special_fields["name_fields"].append(col.name)
            
            # 时间字段
            elif any(keyword in col_name for keyword in ["time", "date", "created", "updated"]):
                special_fields["time_fields"].append(col.name)
            
            # 状态字段
            elif any(keyword in col_name for keyword in ["status", "state", "flag", "type"]):
                special_fields["status_fields"].append(col.name)
            
            # 金额字段
            elif any(keyword in col_name for keyword in ["amount", "price", "cost", "fee", "total"]):
                special_fields["amount_fields"].append(col.name)
        
        return {
            "total_columns": len(columns),
            "type_distribution": type_distribution,
            "nullable_ratio": nullable_count / len(columns) if columns else 0,
            "special_fields": special_fields
        }
    
    def _get_sample_data(self, table_name: str, limit: int = 5) -> Optional[List[Dict[str, Any]]]:
        """获取表的样本数据"""
        try:
            # 只获取前几列，避免数据过多
            sql = f"SELECT * FROM `{table_name}` LIMIT {limit}"
            result = self.db.run(sql)
            
            # 简单解析结果
            if result:
                lines = result.strip().split('\n')
                if len(lines) > 1:
                    # 第一行是列名
                    headers = [h.strip() for h in lines[0].split('|') if h.strip()]
                    
                    # 解析数据行
                    rows = []
                    for line in lines[2:]:  # 跳过标题和分隔线
                        if line.strip() and not line.startswith('-'):
                            values = [v.strip() for v in line.split('|') if v.strip()]
                            if len(values) == len(headers):
                                row = dict(zip(headers, values))
                                rows.append(row)
                    
                    return rows
        except Exception as e:
            logger.debug(f"获取表 {table_name} 样本数据失败: {e}")
        
        return None
    
    def _analyze_with_llm(
        self, 
        database_name: str,
        analysis_data: Dict[str, Any],
        tables: List[TableDetail]
    ) -> DomainKnowledge:
        """使用 LLM 进行领域分析"""
        # 创建输出解析器
        parser = create_structured_output_parser(DomainKnowledge)
        
        # 构建提示词（包含格式指令）
        prompt = self._build_analysis_prompt(database_name, analysis_data, tables, parser)
        
        # 调用 LLM
        try:
            response = self.llm.invoke(prompt)
            
            # 使用解析器解析响应
            domain_knowledge = parser.parse(response.content)
            
            return domain_knowledge
            
        except Exception as e:
            logger.error(f"LLM 分析失败: {e}")
            return self._get_default_domain_knowledge()
    
    def _build_analysis_prompt(
        self, 
        database_name: str,
        analysis_data: Dict[str, Any],
        tables: List[TableDetail],
        parser
    ) -> str:
        """构建分析提示词"""
        # 准备表信息
        table_descriptions = []
        for table in tables[:10]:  # 限制表数量
            table_name = table.name
            summary = analysis_data["table_summaries"].get(table_name, "")
            
            desc = f"### 表: {table_name}\n{summary}"
            
            # 添加特殊字段信息
            field_stats = analysis_data["field_statistics"].get(table_name, {})
            special_fields = field_stats.get("special_fields", {})
            
            if any(special_fields.values()):
                desc += "\n特殊字段:"
                for field_type, fields in special_fields.items():
                    if fields:
                        desc += f"\n- {field_type}: {', '.join(fields[:3])}"
            
            table_descriptions.append(desc)
        
        # 获取格式化指令
        format_instructions = get_pydantic_format_instruction(
            DomainKnowledge,
            "业务领域分析结果"
        )
        
        # 构建提示词
        prompt = f"""分析数据库 '{database_name}' 的业务领域和含义。

## 数据库信息

包含 {len(tables)} 个表，以下是主要表的信息：

{chr(10).join(table_descriptions)}

## 分析要求

请分析数据库的业务领域，识别核心实体、业务流程和专业术语。

{format_instructions}

请基于表结构和字段信息进行推断，给出专业的分析结果。"""
        
        return prompt
    

    
    def _get_default_domain_knowledge(self) -> DomainKnowledge:
        """获取默认领域知识"""
        return DomainKnowledge(
            domain="未知",
            domain_description="无法确定具体的业务领域",
            core_entities=[],
            entity_descriptions={},
            business_processes=[],
            business_rules=[],
            terminology={},
            data_characteristics=DomainCharacteristics(
                data_volume="未知",
                update_frequency="未知",
                data_quality="未知"
            )
        )
    
    def _generate_domain_knowledge_dict(
        self,
        domain_knowledge: DomainKnowledge,
        tables: List[TableDetail],
        analysis_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """生成领域知识字典"""
        # 整合分析结果
        domain_knowledge_dict = {
            "domain": domain_knowledge.domain,
            "description": domain_knowledge.domain_description,
            "core_concepts": {
                "entities": domain_knowledge.core_entities,
                "entity_descriptions": domain_knowledge.entity_descriptions,
                "relationships": self._infer_relationships(tables),
                "processes": domain_knowledge.business_processes
            },
            "business_rules": domain_knowledge.business_rules,
            "terminology": domain_knowledge.terminology,
            "data_profile": {
                "total_tables": len(tables),
                "total_rows": sum(t.row_count for t in tables if t.row_count),
                "characteristics": domain_knowledge.data_characteristics.dict()
            },
            "key_tables": self._identify_key_tables(tables, domain_knowledge)
        }
        
        return domain_knowledge_dict
    
    def _infer_relationships(self, tables: List[TableDetail]) -> List[Dict[str, str]]:
        """推断实体关系"""
        relationships = []
        
        # 基于外键推断
        for table in tables:
            for fk in table.foreign_keys:
                relationship = {
                    "from": table.name,
                    "to": fk.referenced_table,
                    "type": "references",
                    "via": fk.column
                }
                relationships.append(relationship)
        
        # 基于命名推断（如 user_order -> user + order）
        table_names = [t.name for t in tables]
        for table_name in table_names:
            if "_" in table_name:
                parts = table_name.split("_")
                if len(parts) == 2:
                    if parts[0] in table_names and parts[1] in table_names:
                        relationships.append({
                            "from": parts[0],
                            "to": parts[1],
                            "type": "many-to-many",
                            "via": table_name
                        })
        
        return relationships
    
    def _identify_key_tables(
        self, 
        tables: List[TableDetail], 
        domain_knowledge: DomainKnowledge
    ) -> List[str]:
        """识别关键表"""
        key_tables = []
        core_entities = domain_knowledge.core_entities
        
        # 基于核心实体匹配
        for table in tables:
            table_name = table.name.lower()
            
            # 检查是否匹配核心实体
            for entity in core_entities:
                if entity.lower() in table_name or table_name in entity.lower():
                    key_tables.append(table.name)
                    break
            
            # 基于外键数量（被引用多的表通常是核心表）
            if not table.name in key_tables:
                # 计算被引用次数
                ref_count = sum(
                    1 for t in tables 
                    for fk in t.foreign_keys
                    if fk.referenced_table == table.name
                )
                if ref_count >= 3:  # 被3个以上表引用
                    key_tables.append(table.name)
        
        return list(set(key_tables))  # 去重
    
    def _generate_summary(self, domain_knowledge: DomainKnowledge) -> str:
        """生成领域分析摘要"""
        parts = []
        
        # 领域
        parts.append(f"业务领域: {domain_knowledge.domain}")
        
        # 描述
        if domain_knowledge.domain_description:
            parts.append(f"描述: {domain_knowledge.domain_description}")
        
        # 核心实体
        if domain_knowledge.core_entities:
            parts.append(f"核心实体: {', '.join(domain_knowledge.core_entities[:5])}")
        
        # 业务流程
        if domain_knowledge.business_processes:
            parts.append(f"业务流程: {', '.join(domain_knowledge.business_processes[:3])}")
        
        # 数据特征
        chars = domain_knowledge.data_characteristics
        parts.append(f"数据特征: 数据量={chars.data_volume}, 更新频率={chars.update_frequency}")
        
        return "\n".join(parts)