"""业务领域分析工具

参考 nl2sql_pipeline 的 initial_domain_analysis_pipeline 实现，
使用智能体方式分析数据库的业务领域。
"""

from tools.base import BaseSemanticSQLTool
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import logging
import json

logger = logging.getLogger(__name__)


class DomainAnalysisInput(BaseModel):
    """输入模式"""
    schema_info: Dict[str, Any] = Field(
        description="数据库结构信息，通常来自 extract_database_schema 工具"
    )
    focus_tables: Optional[List[str]] = Field(
        default=None,
        description="需要重点分析的表，为空则分析所有表"
    )
    include_sample_data: bool = Field(
        default=True,
        description="是否包含样本数据以增强分析"
    )


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
        schema_info: Dict[str, Any],
        focus_tables: Optional[List[str]] = None,
        include_sample_data: bool = True
    ) -> Dict[str, Any]:
        """执行领域分析"""
        logger.info("开始业务领域分析")
        
        # 提取基本信息
        database_name = schema_info.get("database_name", "unknown")
        tables = schema_info.get("tables", [])
        
        if not tables:
            return {
                "success": False,
                "error": "未提供表信息，请先执行 extract_database_schema"
            }
        
        # 筛选要分析的表
        if focus_tables:
            tables = [t for t in tables if t["name"] in focus_tables]
            logger.info(f"聚焦分析 {len(tables)} 个表: {focus_tables}")
        
        # 准备分析数据
        analysis_data = self._prepare_analysis_data(tables, include_sample_data)
        
        # 使用 LLM 进行领域分析
        domain_analysis = self._analyze_with_llm(
            database_name,
            analysis_data,
            tables
        )
        
        # 生成领域知识
        domain_knowledge = self._generate_domain_knowledge(
            domain_analysis,
            tables,
            analysis_data
        )
        
        return {
            "success": True,
            "database_name": database_name,
            "domain_analysis": domain_analysis,
            "domain_knowledge": domain_knowledge,
            "analyzed_tables": len(tables),
            "summary": self._generate_summary(domain_knowledge)
        }
    
    def _prepare_analysis_data(
        self, 
        tables: List[Dict[str, Any]], 
        include_sample_data: bool
    ) -> Dict[str, Any]:
        """准备分析所需的数据"""
        analysis_data = {
            "table_summaries": {},
            "field_statistics": {},
            "sample_data": {}
        }
        
        for table in tables:
            table_name = table["name"]
            
            # 表摘要
            analysis_data["table_summaries"][table_name] = self._create_table_summary(table)
            
            # 字段统计
            analysis_data["field_statistics"][table_name] = self._analyze_table_fields(table)
            
            # 样本数据
            if include_sample_data and table.get("row_count", 0) > 0:
                sample = self._get_sample_data(table_name, limit=5)
                if sample:
                    analysis_data["sample_data"][table_name] = sample
        
        return analysis_data
    
    def _create_table_summary(self, table: Dict[str, Any]) -> str:
        """创建表摘要"""
        parts = []
        
        # 基本信息
        parts.append(f"表名: {table['name']}")
        
        if table.get("comment"):
            parts.append(f"注释: {table['comment']}")
        
        if "row_count" in table:
            parts.append(f"行数: {table['row_count']:,}")
        
        # 列信息
        columns = table.get("columns", [])
        parts.append(f"列数: {len(columns)}")
        
        # 主键
        primary_keys = table.get("primary_keys", [])
        if primary_keys:
            parts.append(f"主键: {', '.join(primary_keys)}")
        
        # 外键
        foreign_keys = table.get("foreign_keys", [])
        if foreign_keys:
            fk_summary = []
            for fk in foreign_keys[:3]:  # 最多显示3个
                fk_summary.append(f"{fk['column']} -> {fk['referenced_table']}.{fk['referenced_column']}")
            parts.append(f"外键: {'; '.join(fk_summary)}")
            if len(foreign_keys) > 3:
                parts.append(f"... 还有 {len(foreign_keys) - 3} 个外键")
        
        return "\n".join(parts)
    
    def _analyze_table_fields(self, table: Dict[str, Any]) -> Dict[str, Any]:
        """分析表的字段特征"""
        columns = table.get("columns", [])
        
        # 统计数据类型
        type_distribution = {}
        nullable_count = 0
        
        for col in columns:
            # 数据类型
            data_type = col.get("data_type", "").split('(')[0].upper()
            type_distribution[data_type] = type_distribution.get(data_type, 0) + 1
            
            # 可空性
            if col.get("is_nullable", True):
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
            col_name = col["name"].lower()
            
            # ID 字段
            if any(keyword in col_name for keyword in ["id", "_id", "code", "no"]):
                special_fields["id_fields"].append(col["name"])
            
            # 名称字段
            elif any(keyword in col_name for keyword in ["name", "title", "desc"]):
                special_fields["name_fields"].append(col["name"])
            
            # 时间字段
            elif any(keyword in col_name for keyword in ["time", "date", "created", "updated"]):
                special_fields["time_fields"].append(col["name"])
            
            # 状态字段
            elif any(keyword in col_name for keyword in ["status", "state", "flag", "type"]):
                special_fields["status_fields"].append(col["name"])
            
            # 金额字段
            elif any(keyword in col_name for keyword in ["amount", "price", "cost", "fee", "total"]):
                special_fields["amount_fields"].append(col["name"])
        
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
        tables: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """使用 LLM 进行领域分析"""
        # 构建提示词
        prompt = self._build_analysis_prompt(database_name, analysis_data, tables)
        
        # 调用 LLM
        try:
            response = self.llm.invoke(prompt)
            
            # 尝试解析 JSON 响应
            try:
                # 查找 JSON 块
                content = response.content
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group())
                else:
                    # 如果没有 JSON，进行文本解析
                    analysis = self._parse_text_response(content)
            except json.JSONDecodeError:
                analysis = self._parse_text_response(response.content)
            
            return analysis
            
        except Exception as e:
            logger.error(f"LLM 分析失败: {e}")
            return self._get_default_analysis()
    
    def _build_analysis_prompt(
        self, 
        database_name: str,
        analysis_data: Dict[str, Any],
        tables: List[Dict[str, Any]]
    ) -> str:
        """构建分析提示词"""
        # 准备表信息
        table_descriptions = []
        for table in tables[:10]:  # 限制表数量
            table_name = table["name"]
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
        
        # 构建提示词
        prompt = f"""分析数据库 '{database_name}' 的业务领域和含义。

## 数据库信息

包含 {len(tables)} 个表，以下是主要表的信息：

{chr(10).join(table_descriptions)}

## 分析要求

请分析并返回以下信息（JSON 格式）：

{{
    "domain": "业务领域类型（如：电商、金融、教育、医疗、ERP、CRM等）",
    "domain_description": "领域的详细描述",
    "core_entities": ["核心实体1", "核心实体2", ...],
    "entity_descriptions": {{
        "实体名": "实体描述",
        ...
    }},
    "business_processes": ["业务流程1", "业务流程2", ...],
    "business_rules": ["业务规则1", "业务规则2", ...],
    "terminology": {{
        "术语1": "解释",
        "术语2": "解释",
        ...
    }},
    "data_characteristics": {{
        "data_volume": "数据量特征（大/中/小）",
        "update_frequency": "更新频率（高/中/低）",
        "data_quality": "数据质量评估"
    }}
}}

请基于表结构和字段信息进行推断，给出专业的分析结果。"""
        
        return prompt
    
    def _parse_text_response(self, text: str) -> Dict[str, Any]:
        """解析文本响应"""
        result = self._get_default_analysis()
        
        # 尝试提取关键信息
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # 领域识别
            if "领域" in line and "：" in line:
                domain = line.split("：", 1)[-1].strip()
                result["domain"] = domain
            
            # 实体识别
            elif "实体" in line and "：" in line:
                entities = line.split("：", 1)[-1].strip()
                result["core_entities"] = [e.strip() for e in entities.split("、")]
            
            # 流程识别
            elif "流程" in line and "：" in line:
                processes = line.split("：", 1)[-1].strip()
                result["business_processes"] = [p.strip() for p in processes.split("、")]
        
        return result
    
    def _get_default_analysis(self) -> Dict[str, Any]:
        """获取默认分析结果"""
        return {
            "domain": "未知",
            "domain_description": "无法确定具体的业务领域",
            "core_entities": [],
            "entity_descriptions": {},
            "business_processes": [],
            "business_rules": [],
            "terminology": {},
            "data_characteristics": {
                "data_volume": "未知",
                "update_frequency": "未知",
                "data_quality": "未知"
            }
        }
    
    def _generate_domain_knowledge(
        self,
        domain_analysis: Dict[str, Any],
        tables: List[Dict[str, Any]],
        analysis_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """生成领域知识"""
        # 整合分析结果
        domain_knowledge = {
            "domain": domain_analysis.get("domain", "未知"),
            "description": domain_analysis.get("domain_description", ""),
            "core_concepts": {
                "entities": domain_analysis.get("core_entities", []),
                "entity_descriptions": domain_analysis.get("entity_descriptions", {}),
                "relationships": self._infer_relationships(tables),
                "processes": domain_analysis.get("business_processes", [])
            },
            "business_rules": domain_analysis.get("business_rules", []),
            "terminology": domain_analysis.get("terminology", {}),
            "data_profile": {
                "total_tables": len(tables),
                "total_rows": sum(t.get("row_count", 0) for t in tables),
                "characteristics": domain_analysis.get("data_characteristics", {})
            },
            "key_tables": self._identify_key_tables(tables, domain_analysis)
        }
        
        return domain_knowledge
    
    def _infer_relationships(self, tables: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """推断实体关系"""
        relationships = []
        
        # 基于外键推断
        for table in tables:
            for fk in table.get("foreign_keys", []):
                relationship = {
                    "from": table["name"],
                    "to": fk["referenced_table"],
                    "type": "references",
                    "via": fk["column"]
                }
                relationships.append(relationship)
        
        # 基于命名推断（如 user_order -> user + order）
        table_names = [t["name"] for t in tables]
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
        tables: List[Dict[str, Any]], 
        domain_analysis: Dict[str, Any]
    ) -> List[str]:
        """识别关键表"""
        key_tables = []
        core_entities = domain_analysis.get("core_entities", [])
        
        # 基于核心实体匹配
        for table in tables:
            table_name = table["name"].lower()
            
            # 检查是否匹配核心实体
            for entity in core_entities:
                if entity.lower() in table_name or table_name in entity.lower():
                    key_tables.append(table["name"])
                    break
            
            # 基于外键数量（被引用多的表通常是核心表）
            if not table["name"] in key_tables:
                # 计算被引用次数
                ref_count = sum(
                    1 for t in tables 
                    for fk in t.get("foreign_keys", [])
                    if fk["referenced_table"] == table["name"]
                )
                if ref_count >= 3:  # 被3个以上表引用
                    key_tables.append(table["name"])
        
        return list(set(key_tables))  # 去重
    
    def _generate_summary(self, domain_knowledge: Dict[str, Any]) -> str:
        """生成领域分析摘要"""
        parts = []
        
        # 领域
        parts.append(f"业务领域: {domain_knowledge['domain']}")
        
        # 描述
        if domain_knowledge.get("description"):
            parts.append(f"描述: {domain_knowledge['description']}")
        
        # 核心实体
        entities = domain_knowledge["core_concepts"]["entities"]
        if entities:
            parts.append(f"核心实体: {', '.join(entities[:5])}")
        
        # 关键表
        key_tables = domain_knowledge.get("key_tables", [])
        if key_tables:
            parts.append(f"关键表: {', '.join(key_tables[:5])}")
        
        # 数据规模
        data_profile = domain_knowledge["data_profile"]
        parts.append(f"数据规模: {data_profile['total_tables']} 表, {data_profile['total_rows']:,} 行")
        
        return "\n".join(parts)