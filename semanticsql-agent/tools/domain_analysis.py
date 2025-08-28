"""业务领域分析工具

参考 nl2sql_pipeline 的 initial_domain_analysis_pipeline 实现，
使用智能体方式分析数据库的业务领域。
"""

from typing import Dict, Any, List, Optional
import logging

from .base import BaseSemanticSQLTool
from utils.output_parsers import create_structured_output_parser

logger = logging.getLogger(__name__)


class DomainAnalysisTool(BaseSemanticSQLTool):
    """业务领域分析工具
    
    分析数据库的业务领域，识别核心概念、实体关系和业务规则。
    这是分析流程的第二步，基于架构信息进行深入的业务理解。
    """
    
    name = "analyze_business_domain"
    description = (
        "分析数据库的业务领域和特征。"
        "识别关键实体、业务规则、数据模式和领域知识。"
        "为后续的 SQL 生成提供业务上下文。"
    )
    
    def execute(
        self,
        schema_info: Dict[str, Any],
        focus_tables: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """分析业务领域"""
        logger.info("开始业务领域分析")
        
        # 准备分析数据
        analysis_data = self._prepare_analysis_data(schema_info, focus_tables)
        
        # 使用 LLM 进行领域分析
        domain_result = self._analyze_with_llm(analysis_data)
        
        # 补充推断
        domain_result["inferred_relationships"] = self._infer_relationships(
            schema_info, domain_result
        )
        
        # 生成摘要
        domain_result["summary"] = self._generate_summary(domain_result)
        
        logger.info(f"领域分析完成: {domain_result.get('domain', 'unknown')}")
        
        return domain_result
    
    def _prepare_analysis_data(
        self,
        schema_info: Dict[str, Any],
        focus_tables: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """准备分析数据"""
        tables = schema_info.get("tables", [])
        
        # 如果指定了焦点表，只分析这些表
        if focus_tables:
            tables = [t for t in tables if t["name"] in focus_tables]
        
        # 提取关键信息
        table_summaries = []
        for table in tables[:20]:  # 限制表数量
            summary = self._create_table_summary(table)
            table_summaries.append(summary)
        
        # 识别关键模式
        patterns = {
            "has_user_tables": any("user" in t["name"].lower() for t in tables),
            "has_order_tables": any("order" in t["name"].lower() for t in tables),
            "has_product_tables": any("product" in t["name"].lower() for t in tables),
            "has_transaction_tables": any(
                any(keyword in t["name"].lower() for keyword in ["transaction", "payment", "invoice"])
                for t in tables
            ),
            "has_log_tables": any("log" in t["name"].lower() for t in tables),
            "has_config_tables": any(
                any(keyword in t["name"].lower() for keyword in ["config", "setting", "parameter"])
                for t in tables
            )
        }
        
        return {
            "database_name": schema_info.get("database_name", "unknown"),
            "tables_count": len(tables),
            "table_summaries": table_summaries,
            "patterns": patterns,
            "sample_foreign_keys": self._extract_sample_foreign_keys(tables)
        }
    
    def _create_table_summary(self, table: Dict[str, Any]) -> Dict[str, Any]:
        """创建表摘要"""
        # 分析表字段特征
        field_types = self._analyze_table_fields(table)
        
        return {
            "name": table["name"],
            "row_count": table.get("row_count", 0),
            "columns_count": len(table.get("columns", [])),
            "has_primary_key": len(table.get("primary_keys", [])) > 0,
            "foreign_keys_count": len(table.get("foreign_keys", [])),
            "field_characteristics": field_types,
            "sample_columns": [
                {"name": col["name"], "type": col["data_type"]}
                for col in table.get("columns", [])[:5]
            ]
        }
    
    def _analyze_table_fields(self, table: Dict[str, Any]) -> Dict[str, int]:
        """分析表字段特征"""
        characteristics = {
            "id_fields": 0,
            "name_fields": 0,
            "date_fields": 0,
            "numeric_fields": 0,
            "text_fields": 0,
            "status_fields": 0
        }
        
        for column in table.get("columns", []):
            col_name = column["name"].lower()
            col_type = column["data_type"].lower()
            
            # ID 字段
            if "id" in col_name or col_name.endswith("_id"):
                characteristics["id_fields"] += 1
            
            # 名称字段
            if any(keyword in col_name for keyword in ["name", "title", "description"]):
                characteristics["name_fields"] += 1
            
            # 日期字段
            if any(keyword in col_type for keyword in ["date", "time", "timestamp"]):
                characteristics["date_fields"] += 1
            
            # 数值字段
            if any(keyword in col_type for keyword in ["int", "decimal", "float", "numeric"]):
                characteristics["numeric_fields"] += 1
            
            # 文本字段
            if any(keyword in col_type for keyword in ["char", "text", "string"]):
                characteristics["text_fields"] += 1
            
            # 状态字段
            if any(keyword in col_name for keyword in ["status", "state", "flag", "is_"]):
                characteristics["status_fields"] += 1
        
        return characteristics
    
    def _extract_sample_foreign_keys(self, tables: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """提取示例外键关系"""
        foreign_keys = []
        
        for table in tables[:10]:  # 限制数量
            for fk in table.get("foreign_keys", [])[:3]:  # 每个表最多3个
                foreign_keys.append({
                    "from": f"{table['name']}.{fk['column']}",
                    "to": f"{fk['referenced_table']}.{fk['referenced_column']}"
                })
        
        return foreign_keys[:10]  # 总共最多10个
    
    def _analyze_with_llm(self, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """使用 LLM 进行领域分析"""
        # 构建提示词
        prompt = self._build_analysis_prompt(analysis_data)
        
        # 调用 LLM
        response = self.llm.invoke(prompt)
        
        # 解析响应
        try:
            # 尝试使用结构化解析器
            parser = create_structured_output_parser(expected_keys=[
                "domain", "description", "key_entities", "business_rules", "data_characteristics"
            ])
            result = parser.parse(response.content)
        except:
            # 失败时使用简单解析
            result = self._parse_simple_response(response.content)
        
        return result
    
    def _build_analysis_prompt(self, data: Dict[str, Any]) -> str:
        """构建分析提示词"""
        prompt_parts = [
            "请分析以下数据库的业务领域和特征：\n",
            f"数据库名: {data['database_name']}",
            f"表数量: {data['tables_count']}",
            "\n表信息摘要："
        ]
        
        # 添加表摘要
        for summary in data["table_summaries"][:10]:
            prompt_parts.append(
                f"- {summary['name']}: "
                f"{summary['columns_count']}列, "
                f"{summary['row_count']}行, "
                f"特征: {summary['field_characteristics']}"
            )
        
        # 添加模式识别
        prompt_parts.append("\n识别的模式：")
        for pattern, exists in data["patterns"].items():
            if exists:
                prompt_parts.append(f"- {pattern}: 是")
        
        # 添加外键示例
        if data["sample_foreign_keys"]:
            prompt_parts.append("\n外键关系示例：")
            for fk in data["sample_foreign_keys"][:5]:
                prompt_parts.append(f"- {fk['from']} -> {fk['to']}")
        
        # 分析要求
        prompt_parts.extend([
            "\n请提供以下分析：",
            "1. domain: 业务领域（如：电商、金融、教育等）",
            "2. description: 领域描述（简要说明这是什么类型的系统）",
            "3. key_entities: 关键业务实体列表（如：用户、订单、产品等）",
            "4. business_rules: 识别出的业务规则列表",
            "5. data_characteristics: 数据特征描述",
            "\n请以 JSON 格式返回结果。"
        ])
        
        return "\n".join(prompt_parts)
    
    def _parse_simple_response(self, content: str) -> Dict[str, Any]:
        """简单解析响应"""
        # 默认结果
        result = {
            "domain": "unknown",
            "description": "",
            "key_entities": [],
            "business_rules": [],
            "data_characteristics": {}
        }
        
        # 尝试提取领域
        import re
        domain_match = re.search(r'领域[：:]\s*(\S+)', content)
        if domain_match:
            result["domain"] = domain_match.group(1)
        
        # 提取实体（查找中文或英文的列表项）
        entities = re.findall(r'[-•]\s*(\w+)', content)
        if entities:
            result["key_entities"] = list(set(entities[:10]))
        
        # 使用整个内容作为描述
        result["description"] = content[:200] + "..." if len(content) > 200 else content
        
        return result
    
    def _infer_relationships(
        self,
        schema_info: Dict[str, Any],
        domain_result: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """推断实体关系"""
        relationships = []
        tables = schema_info.get("tables", [])
        
        # 基于外键推断
        for table in tables:
            for fk in table.get("foreign_keys", []):
                relationships.append({
                    "from_entity": self._table_to_entity(table["name"]),
                    "to_entity": self._table_to_entity(fk["referenced_table"]),
                    "type": "references",
                    "via": f"{fk['column']}"
                })
        
        # 基于命名推断（如 user_order -> user 和 order 的关系）
        for table in tables:
            table_name = table["name"].lower()
            parts = table_name.split("_")
            
            if len(parts) == 2:
                # 可能是关联表
                entity1 = self._table_to_entity(parts[0])
                entity2 = self._table_to_entity(parts[1])
                
                if entity1 in domain_result.get("key_entities", []) and \
                   entity2 in domain_result.get("key_entities", []):
                    relationships.append({
                        "from_entity": entity1,
                        "to_entity": entity2,
                        "type": "many_to_many",
                        "via": table_name
                    })
        
        return relationships[:20]  # 限制数量
    
    def _table_to_entity(self, table_name: str) -> str:
        """将表名转换为实体名"""
        # 简单处理：移除复数 s，转换为单数
        entity = table_name.lower()
        if entity.endswith("ies"):
            entity = entity[:-3] + "y"
        elif entity.endswith("es"):
            entity = entity[:-2]
        elif entity.endswith("s"):
            entity = entity[:-1]
        
        return entity
    
    def _generate_summary(self, domain_result: Dict[str, Any]) -> str:
        """生成领域分析摘要"""
        parts = []
        
        # 领域
        domain = domain_result.get("domain", "unknown")
        parts.append(f"这是一个{domain}领域的数据库")
        
        # 描述
        if domain_result.get("description"):
            parts.append(domain_result["description"])
        
        # 关键实体
        entities = domain_result.get("key_entities", [])
        if entities:
            entities_str = "、".join(entities[:5])
            parts.append(f"主要包含{entities_str}等业务实体")
        
        # 业务规则
        rules = domain_result.get("business_rules", [])
        if rules:
            parts.append(f"识别出{len(rules)}条业务规则")
        
        return "。".join(parts) + "。"