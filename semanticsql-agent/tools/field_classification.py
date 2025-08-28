"""字段分类工具

参考 nl2sql_pipeline 的 field_classification_pipeline 实现，
对数据库字段进行分类和特征分析。
"""

from tools.base import BaseSemanticSQLTool
from typing import Dict, Any, List, Optional
from models.analysis_models import (
    FieldClassificationInput,
    FieldClassificationOutput,
    FieldClassification,
    FieldStatistics,
    TableFieldReport,
    FieldCategory,
    SchemaExtractionOutput,
    DomainAnalysisOutput
)
from utils.output_parsers import (
    create_structured_output_parser,
    get_pydantic_format_instruction
)
from collections import Counter
import math
import logging
import json

logger = logging.getLogger(__name__)


class FieldClassificationTool(BaseSemanticSQLTool):
    """字段分类工具
    
    对表的字段进行分类，识别维度、度量、标识符、时间戳等类型。
    包括熵值计算，帮助理解字段的数据分布特征。
    """
    
    name = "classify_table_fields"
    description = (
        "对数据库字段进行分类，识别维度、度量、标识符等类型，并计算熵值。"
        "需要先执行 extract_database_schema 获取结构信息。"
        "可选使用 analyze_business_domain 的结果增强分类准确性。"
    )
    args_schema = FieldClassificationInput
    
    def execute(
        self,
        schema_info: Dict[str, Any],
        domain_knowledge: Optional[Dict[str, Any]] = None,
        sample_size: int = 100,
        focus_tables: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """执行字段分类"""
        logger.info("开始字段分类分析")
        
        tables = schema_info.get("tables", [])
        if not tables:
            return {
                "success": False,
                "error": "未提供表信息"
            }
        
        # 筛选要分析的表
        if focus_tables:
            tables = [t for t in tables if t["name"] in focus_tables]
        
        # 收集和分析所有字段
        all_field_infos = []
        for table in tables:
            field_infos = self._collect_table_fields(table, sample_size)
            all_field_infos.extend(field_infos)
        
        logger.info(f"收集了 {len(all_field_infos)} 个字段的信息")
        
        # 使用 LLM 进行分类
        classifications = self._classify_fields_with_llm(
            all_field_infos,
            domain_knowledge
        )
        
        # 生成分类报告
        classification_report = self._generate_classification_report(
            classifications,
            all_field_infos
        )
        
        return {
            "success": True,
            "total_fields": len(all_field_infos),
            "classifications": classifications,
            "report": classification_report,
            "statistics": self._generate_statistics(classifications)
        }
    
    def _collect_table_fields(
        self, 
        table: Dict[str, Any], 
        sample_size: int
    ) -> List[Dict[str, Any]]:
        """收集表的字段信息"""
        logger.info(f"收集表 {table['name']} 的字段信息")
        
        field_infos = []
        columns = table.get("columns", [])
        
        if not columns:
            return field_infos
        
        # 获取样本数据
        column_names = [f"`{col['name']}`" for col in columns]
        sql = f"SELECT {', '.join(column_names)} FROM `{table['name']}` LIMIT {sample_size}"
        
        try:
            result = self.db.run(sql)
            rows = self._parse_query_result(result, [col['name'] for col in columns])
        except Exception as e:
            logger.error(f"获取表 {table['name']} 数据失败: {e}")
            rows = []
        
        # 分析每个字段
        for col in columns:
            col_name = col["name"]
            
            # 收集该列的所有值
            values = []
            if rows:
                for row in rows:
                    value = row.get(col_name)
                    if value is not None and value != 'NULL':
                        values.append(value)
            
            # 计算字段特征
            field_info = {
                "table_name": table["name"],
                "column_name": col_name,
                "field_name": f"{table['name']}.{col_name}",
                "data_type": col["data_type"],
                "is_nullable": col.get("is_nullable", True),
                "is_primary_key": col.get("is_primary_key", False),
                "is_foreign_key": col.get("is_foreign_key", False),
                "comment": col.get("comment"),
                "sample_count": len(values),
                "null_count": sample_size - len(values) if rows else 0,
                "samples": values[:10],  # 保留前10个样本
                "entropy": self._calculate_entropy(values),
                "unique_count": len(set(values)),
                "statistics": self._calculate_statistics(values, col["data_type"])
            }
            
            field_infos.append(field_info)
            
            logger.debug(
                f"  - {field_info['field_name']}: "
                f"熵值={field_info['entropy']:.3f}, "
                f"唯一值={field_info['unique_count']}, "
                f"非空样本={field_info['sample_count']}"
            )
        
        return field_infos
    
    def _parse_query_result(
        self, 
        result: str, 
        column_names: List[str]
    ) -> List[Dict[str, Any]]:
        """解析查询结果"""
        rows = []
        
        if not result:
            return rows
        
        lines = result.strip().split('\n')
        if len(lines) <= 2:  # 没有数据行
            return rows
        
        # 跳过标题和分隔线
        for line in lines[2:]:
            if line.strip() and not line.startswith('-'):
                values = [v.strip() for v in line.split('|')]
                if len(values) >= len(column_names):
                    # 创建行字典（考虑可能有多余的空值）
                    row = {}
                    for i, col_name in enumerate(column_names):
                        if i < len(values):
                            value = values[i].strip()
                            row[col_name] = value if value else None
                        else:
                            row[col_name] = None
                    rows.append(row)
        
        return rows
    
    def _calculate_entropy(self, values: List[Any]) -> float:
        """计算熵值"""
        if not values:
            return 0.0
        
        # 计算值的频率
        counter = Counter(values)
        total = len(values)
        
        # 计算熵
        entropy = 0.0
        for count in counter.values():
            if count > 0:
                probability = count / total
                entropy -= probability * math.log2(probability)
        
        return entropy
    
    def _calculate_statistics(
        self, 
        values: List[Any], 
        data_type: str
    ) -> Dict[str, Any]:
        """计算字段统计信息"""
        stats = {
            "value_distribution": {},
            "numeric_stats": None,
            "length_stats": None
        }
        
        if not values:
            return stats
        
        # 值分布（对于低基数字段）
        unique_values = set(values)
        if len(unique_values) <= 20:
            counter = Counter(values)
            stats["value_distribution"] = dict(counter.most_common(10))
        
        # 数值统计
        if self._is_numeric_type(data_type):
            numeric_values = []
            for v in values:
                try:
                    numeric_values.append(float(v))
                except (ValueError, TypeError):
                    pass
            
            if numeric_values:
                stats["numeric_stats"] = {
                    "min": min(numeric_values),
                    "max": max(numeric_values),
                    "avg": sum(numeric_values) / len(numeric_values),
                    "distinct_count": len(set(numeric_values))
                }
        
        # 长度统计（对于字符串）
        elif self._is_string_type(data_type):
            lengths = [len(str(v)) for v in values]
            stats["length_stats"] = {
                "min_length": min(lengths),
                "max_length": max(lengths),
                "avg_length": sum(lengths) / len(lengths)
            }
        
        return stats
    
    def _is_numeric_type(self, data_type: str) -> bool:
        """判断是否为数值类型"""
        numeric_types = [
            'INT', 'BIGINT', 'SMALLINT', 'TINYINT',
            'DECIMAL', 'NUMERIC', 'FLOAT', 'DOUBLE', 'REAL'
        ]
        return any(t in data_type.upper() for t in numeric_types)
    
    def _is_string_type(self, data_type: str) -> bool:
        """判断是否为字符串类型"""
        string_types = ['VARCHAR', 'CHAR', 'TEXT', 'STRING']
        return any(t in data_type.upper() for t in string_types)
    
    def _classify_fields_with_llm(
        self,
        field_infos: List[Dict[str, Any]],
        domain_knowledge: Optional[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """使用 LLM 对字段进行分类"""
        classifications = {}
        
        # 按表分组处理
        table_fields = {}
        for field_info in field_infos:
            table_name = field_info["table_name"]
            if table_name not in table_fields:
                table_fields[table_name] = []
            table_fields[table_name].append(field_info)
        
        # 批量处理每个表的字段
        for table_name, fields in table_fields.items():
            logger.info(f"使用 LLM 分类表 {table_name} 的 {len(fields)} 个字段")
            
            # 构建提示词
            prompt = self._build_classification_prompt(
                table_name,
                fields,
                domain_knowledge
            )
            
            # 调用 LLM
            try:
                response = self.llm.invoke(prompt)
                table_classifications = self._parse_llm_response(
                    response.content,
                    fields
                )
                
                # 合并结果
                for field_name, classification in table_classifications.items():
                    classifications[field_name] = classification
                    
            except Exception as e:
                logger.error(f"LLM 分类表 {table_name} 失败: {e}")
                # 使用基于规则的分类作为降级方案
                for field in fields:
                    classifications[field["field_name"]] = self._rule_based_classification(field)
        
        return classifications
    
    def _build_classification_prompt(
        self,
        table_name: str,
        fields: List[Dict[str, Any]],
        domain_knowledge: Optional[Dict[str, Any]]
    ) -> str:
        """构建分类提示词"""
        # 准备字段信息
        field_descriptions = []
        for field in fields:
            desc_parts = [
                f"字段名: {field['column_name']}",
                f"数据类型: {field['data_type']}",
                f"熵值: {field['entropy']:.2f}",
                f"唯一值数: {field['unique_count']}",
                f"空值率: {field['null_count'] / (field['sample_count'] + field['null_count']):.1%}" if field['sample_count'] + field['null_count'] > 0 else "空值率: N/A"
            ]
            
            if field.get("comment"):
                desc_parts.append(f"注释: {field['comment']}")
            
            if field.get("samples"):
                samples = field["samples"][:5]
                desc_parts.append(f"样本值: {samples}")
            
            if field["is_primary_key"]:
                desc_parts.append("主键")
            if field["is_foreign_key"]:
                desc_parts.append("外键")
            
            field_descriptions.append("\n".join(desc_parts))
        
        # 领域上下文
        domain_context = ""
        if domain_knowledge:
            domain = domain_knowledge.get("domain", "未知")
            domain_context = f"\n业务领域: {domain}\n"
            
            # 如果表是核心实体
            core_entities = domain_knowledge.get("core_concepts", {}).get("entities", [])
            if any(entity.lower() in table_name.lower() for entity in core_entities):
                domain_context += f"注意：{table_name} 是核心业务实体表\n"
        
        prompt = f"""分析表 {table_name} 的字段并进行分类。
{domain_context}
## 字段信息

{chr(10).join(f'### 字段 {i+1}\n{desc}' for i, desc in enumerate(field_descriptions))}

## 分类标准

1. **{FieldType.IDENTIFIER}（标识符）**
   - 主键、外键、唯一标识
   - ID、编号、代码类字段
   - 熵值通常很高（接近唯一）

2. **{FieldType.DIMENSION}（维度）**
   - 用于分组、筛选的分类字段
   - 状态、类型、类别等枚举值
   - 熵值通常较低（有限的取值）

3. **{FieldType.MEASURE}（度量）**
   - 可以进行数学运算的数值
   - 金额、数量、分数等
   - 通常是数值类型

4. **{FieldType.TIMESTAMP}（时间戳）**
   - 日期、时间相关字段
   - 创建时间、更新时间等

5. **{FieldType.DESCRIPTION}（描述）**
   - 文本描述、备注、评论
   - 通常是较长的文本字段
   - 熵值通常很高

## 输出要求

请返回 JSON 格式的分类结果：
{{
    "表名.字段名": {{
        "category": "分类（使用上述5个类别之一）",
        "confidence": 0.9,  // 置信度 0-1
        "reason": "分类理由"
    }},
    ...
}}"""
        
        return prompt
    
    def _parse_llm_response(
        self,
        response: str,
        fields: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """解析 LLM 响应"""
        classifications = {}
        
        try:
            # 尝试解析 JSON
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                
                # 处理结果
                for field_name, classification in result.items():
                    if isinstance(classification, dict):
                        # 验证分类类别
                        category = classification.get("category", FieldType.DIMENSION)
                        if category not in [ft.value for ft in FieldType]:
                            category = FieldType.DIMENSION
                        
                        classifications[field_name] = {
                            "type": category,
                            "confidence": classification.get("confidence", 0.8),
                            "reason": classification.get("reason", "")
                        }
        except Exception as e:
            logger.error(f"解析 LLM 分类响应失败: {e}")
        
        # 确保所有字段都有分类
        for field in fields:
            if field["field_name"] not in classifications:
                classifications[field["field_name"]] = self._rule_based_classification(field)
        
        return classifications
    
    def _rule_based_classification(self, field_info: Dict[str, Any]) -> Dict[str, Any]:
        """基于规则的字段分类（降级方案）"""
        field_name = field_info["column_name"].lower()
        data_type = field_info["data_type"].upper()
        
        # 标识符
        if field_info["is_primary_key"] or any(kw in field_name for kw in ["_id", "id", "code", "no"]):
            return {
                "type": FieldType.IDENTIFIER,
                "confidence": 0.9,
                "reason": "主键或包含ID关键词"
            }
        
        # 时间戳
        if any(kw in field_name for kw in ["time", "date", "created", "updated"]) or "DATE" in data_type or "TIME" in data_type:
            return {
                "type": FieldType.TIMESTAMP,
                "confidence": 0.9,
                "reason": "时间相关字段"
            }
        
        # 度量
        if self._is_numeric_type(data_type) and not any(kw in field_name for kw in ["id", "type", "status", "flag"]):
            return {
                "type": FieldType.MEASURE,
                "confidence": 0.8,
                "reason": "数值类型且非分类字段"
            }
        
        # 描述
        if "TEXT" in data_type or any(kw in field_name for kw in ["desc", "remark", "comment", "note"]):
            return {
                "type": FieldType.DESCRIPTION,
                "confidence": 0.8,
                "reason": "文本类型或包含描述关键词"
            }
        
        # 默认为维度
        return {
            "type": FieldType.DIMENSION,
            "confidence": 0.7,
            "reason": "默认分类"
        }
    
    def _generate_classification_report(
        self,
        classifications: Dict[str, Dict[str, Any]],
        field_infos: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """生成分类报告"""
        # 按表组织
        table_reports = {}
        
        for field_info in field_infos:
            table_name = field_info["table_name"]
            field_name = field_info["field_name"]
            
            if table_name not in table_reports:
                table_reports[table_name] = {
                    "fields": [],
                    "summary": {
                        "total": 0,
                        "by_type": {}
                    }
                }
            
            classification = classifications.get(field_name, {})
            
            field_report = {
                "name": field_info["column_name"],
                "type": classification.get("type", FieldType.DIMENSION),
                "confidence": classification.get("confidence", 0),
                "data_type": field_info["data_type"],
                "entropy": field_info["entropy"],
                "unique_ratio": field_info["unique_count"] / field_info["sample_count"] if field_info["sample_count"] > 0 else 0,
                "null_ratio": field_info["null_count"] / (field_info["sample_count"] + field_info["null_count"]) if field_info["sample_count"] + field_info["null_count"] > 0 else 0,
                "reason": classification.get("reason", "")
            }
            
            table_reports[table_name]["fields"].append(field_report)
            table_reports[table_name]["summary"]["total"] += 1
            
            # 统计类型
            field_type = field_report["type"]
            if field_type not in table_reports[table_name]["summary"]["by_type"]:
                table_reports[table_name]["summary"]["by_type"][field_type] = 0
            table_reports[table_name]["summary"]["by_type"][field_type] += 1
        
        return table_reports
    
    def _generate_statistics(self, classifications: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """生成统计信息"""
        stats = {
            "total_fields": len(classifications),
            "by_type": {},
            "average_confidence": 0,
            "low_confidence_fields": []
        }
        
        total_confidence = 0
        
        for field_name, classification in classifications.items():
            # 类型统计
            field_type = classification.get("type", FieldType.DIMENSION)
            if field_type not in stats["by_type"]:
                stats["by_type"][field_type] = 0
            stats["by_type"][field_type] += 1
            
            # 置信度统计
            confidence = classification.get("confidence", 0)
            total_confidence += confidence
            
            # 低置信度字段
            if confidence < 0.7:
                stats["low_confidence_fields"].append({
                    "field": field_name,
                    "type": field_type,
                    "confidence": confidence
                })
        
        # 平均置信度
        if classifications:
            stats["average_confidence"] = total_confidence / len(classifications)
        
        return stats