"""字段分类工具

参考 nl2sql_pipeline 的 field_classification_pipeline 实现，
对数据库字段进行智能分类。
"""

from typing import Dict, Any, List, Optional
import logging
import re

from .base import BaseSemanticSQLTool

logger = logging.getLogger(__name__)


class FieldClassificationTool(BaseSemanticSQLTool):
    """字段分类工具
    
    对数据库中的字段进行分类，识别维度、度量、时间戳等类型。
    这是分析流程的第三步，为 SQL 生成提供字段级别的理解。
    """
    
    name = "classify_table_fields"
    description = (
        "对数据库表的字段进行智能分类。"
        "识别维度字段、度量字段、时间字段、标识符等。"
        "帮助生成更准确的聚合查询和分析型 SQL。"
    )
    
    def execute(
        self,
        schema_info: Dict[str, Any],
        domain_analysis: Optional[Dict[str, Any]] = None,
        tables_to_classify: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """执行字段分类"""
        logger.info("开始字段分类")
        
        tables = schema_info.get("tables", [])
        
        # 如果指定了表，只分类这些表
        if tables_to_classify:
            tables = [t for t in tables if t["name"] in tables_to_classify]
        
        # 分类结果
        classification_results = {}
        table_reports = []
        
        # 对每个表进行分类
        for table in tables:
            table_name = table["name"]
            logger.debug(f"分类表 {table_name} 的字段")
            
            # 分类字段
            field_classifications = self._classify_table_fields(table, domain_analysis)
            
            # 生成表级报告
            report = self._generate_table_report(table_name, field_classifications)
            table_reports.append(report)
            
            # 保存分类结果
            classification_results[table_name] = field_classifications
        
        # 生成总体统计
        overall_stats = self._generate_overall_statistics(classification_results)
        
        # 构建输出
        output = {
            "tables_classified": len(table_reports),
            "classification_results": classification_results,
            "table_reports": table_reports,
            "overall_statistics": overall_stats,
            "summary": self._generate_summary(overall_stats, domain_analysis)
        }
        
        logger.info(f"字段分类完成，共分类 {len(table_reports)} 个表")
        
        return output
    
    def _classify_table_fields(
        self,
        table: Dict[str, Any],
        domain_analysis: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """对单个表的字段进行分类"""
        classifications = {}
        
        for column in table.get("columns", []):
            col_name = column["name"]
            col_type = column["data_type"]
            
            # 基础分类
            base_category = self._classify_by_rules(column, table)
            
            # 如果有领域分析，使用 LLM 进行更精确的分类
            if domain_analysis and base_category in ["dimension", "measure"]:
                refined_category = self._refine_with_llm(
                    column, table, domain_analysis, base_category
                )
                category = refined_category
            else:
                category = base_category
            
            # 收集字段统计信息
            field_stats = self._collect_field_statistics(column, table)
            
            classifications[col_name] = {
                "category": category,
                "data_type": col_type,
                "is_nullable": column.get("is_nullable", True),
                "is_primary_key": column.get("is_primary_key", False),
                "is_foreign_key": column.get("is_foreign_key", False),
                "statistics": field_stats,
                "confidence": self._calculate_confidence(column, category)
            }
        
        return classifications
    
    def _classify_by_rules(self, column: Dict[str, Any], table: Dict[str, Any]) -> str:
        """基于规则的字段分类"""
        col_name = column["name"].lower()
        col_type = column["data_type"].lower()
        
        # 1. 标识符（ID）
        if column.get("is_primary_key") or col_name.endswith("_id") or col_name == "id":
            return "identifier"
        
        # 2. 外键标识符
        if column.get("is_foreign_key"):
            return "foreign_identifier"
        
        # 3. 时间戳
        if any(keyword in col_type for keyword in ["date", "time", "timestamp"]):
            return "timestamp"
        
        if any(keyword in col_name for keyword in ["_date", "_time", "created", "updated", "modified"]):
            return "timestamp"
        
        # 4. 状态/标志
        if any(keyword in col_name for keyword in ["status", "state", "flag", "is_", "has_"]):
            return "status"
        
        # 5. 描述性文本
        if any(keyword in col_type for keyword in ["text", "blob", "clob"]):
            return "description"
        
        if any(keyword in col_name for keyword in ["description", "comment", "note", "remark"]):
            return "description"
        
        # 6. 度量（数值类型且名称暗示可计算）
        if any(keyword in col_type for keyword in ["int", "decimal", "float", "numeric", "double"]):
            measure_keywords = [
                "amount", "price", "cost", "total", "sum", "count", "quantity",
                "balance", "score", "rate", "ratio", "percent", "avg", "max", "min"
            ]
            if any(keyword in col_name for keyword in measure_keywords):
                return "measure"
        
        # 7. 维度（默认字符串类型）
        if any(keyword in col_type for keyword in ["char", "varchar", "string"]):
            return "dimension"
        
        # 8. 默认：基于数据类型
        if any(keyword in col_type for keyword in ["int", "decimal", "float", "numeric"]):
            return "measure"
        else:
            return "dimension"
    
    def _refine_with_llm(
        self,
        column: Dict[str, Any],
        table: Dict[str, Any],
        domain_analysis: Dict[str, Any],
        base_category: str
    ) -> str:
        """使用 LLM 精细化分类"""
        # 构建提示
        prompt = f"""
在 {domain_analysis.get('domain', 'unknown')} 领域的数据库中，
表 {table['name']} 的字段 {column['name']} (类型: {column['data_type']})
初步分类为 {base_category}。

请确认这个分类是否准确，可选类别：
- dimension: 维度字段（用于分组、筛选）
- measure: 度量字段（可计算、聚合）
- identifier: 标识符
- timestamp: 时间戳
- status: 状态标志
- description: 描述文本

只返回最合适的类别名称。
"""
        
        try:
            response = self.llm.invoke(prompt)
            category = response.content.strip().lower()
            
            # 验证返回的类别
            valid_categories = ["dimension", "measure", "identifier", "timestamp", "status", "description"]
            if category in valid_categories:
                return category
        except:
            pass
        
        # 失败时返回基础分类
        return base_category
    
    def _collect_field_statistics(
        self,
        column: Dict[str, Any],
        table: Dict[str, Any]
    ) -> Dict[str, Any]:
        """收集字段统计信息"""
        stats = {
            "distinct_count": None,
            "null_count": None,
            "min_value": None,
            "max_value": None,
            "avg_length": None
        }
        
        # 这里可以通过查询数据库获取实际统计信息
        # 为了简化，这里只返回基础信息
        
        return stats
    
    def _calculate_confidence(self, column: Dict[str, Any], category: str) -> float:
        """计算分类置信度"""
        confidence = 0.5  # 基础置信度
        
        col_name = column["name"].lower()
        
        # 根据命名规则增加置信度
        if category == "identifier" and ("_id" in col_name or column.get("is_primary_key")):
            confidence = 0.95
        elif category == "timestamp" and any(kw in col_name for kw in ["date", "time"]):
            confidence = 0.9
        elif category == "measure" and any(kw in col_name for kw in ["amount", "total", "count"]):
            confidence = 0.85
        elif category == "dimension" and any(kw in col_name for kw in ["name", "type", "category"]):
            confidence = 0.85
        elif category == "status" and any(kw in col_name for kw in ["status", "flag", "is_"]):
            confidence = 0.9
        
        return confidence
    
    def _generate_table_report(
        self,
        table_name: str,
        classifications: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """生成表级分类报告"""
        # 统计各类别数量
        category_counts = {}
        high_confidence_fields = []
        low_confidence_fields = []
        
        for field_name, field_info in classifications.items():
            category = field_info["category"]
            confidence = field_info["confidence"]
            
            # 统计类别
            category_counts[category] = category_counts.get(category, 0) + 1
            
            # 收集高/低置信度字段
            if confidence >= 0.8:
                high_confidence_fields.append(field_name)
            elif confidence < 0.6:
                low_confidence_fields.append(field_name)
        
        # 识别关键字段
        key_fields = {
            "primary_keys": [
                f for f, info in classifications.items()
                if info.get("is_primary_key")
            ],
            "foreign_keys": [
                f for f, info in classifications.items()
                if info.get("is_foreign_key")
            ],
            "measures": [
                f for f, info in classifications.items()
                if info["category"] == "measure"
            ][:5],  # 最多5个
            "dimensions": [
                f for f, info in classifications.items()
                if info["category"] == "dimension"
            ][:5],  # 最多5个
            "timestamps": [
                f for f, info in classifications.items()
                if info["category"] == "timestamp"
            ]
        }
        
        return {
            "table_name": table_name,
            "total_fields": len(classifications),
            "category_distribution": category_counts,
            "key_fields": key_fields,
            "high_confidence_count": len(high_confidence_fields),
            "low_confidence_fields": low_confidence_fields[:5]  # 最多显示5个
        }
    
    def _generate_overall_statistics(
        self,
        all_classifications: Dict[str, Dict[str, Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """生成总体统计"""
        total_fields = 0
        category_totals = {}
        all_measures = []
        all_dimensions = []
        all_timestamps = []
        
        for table_name, classifications in all_classifications.items():
            total_fields += len(classifications)
            
            for field_name, field_info in classifications.items():
                category = field_info["category"]
                category_totals[category] = category_totals.get(category, 0) + 1
                
                # 收集特定类型的字段
                full_field_name = f"{table_name}.{field_name}"
                if category == "measure":
                    all_measures.append(full_field_name)
                elif category == "dimension":
                    all_dimensions.append(full_field_name)
                elif category == "timestamp":
                    all_timestamps.append(full_field_name)
        
        return {
            "total_fields_classified": total_fields,
            "category_distribution": category_totals,
            "top_measures": all_measures[:10],
            "top_dimensions": all_dimensions[:10],
            "all_timestamps": all_timestamps,
            "measure_ratio": category_totals.get("measure", 0) / total_fields if total_fields > 0 else 0,
            "dimension_ratio": category_totals.get("dimension", 0) / total_fields if total_fields > 0 else 0
        }
    
    def _generate_summary(
        self,
        stats: Dict[str, Any],
        domain_analysis: Optional[Dict[str, Any]] = None
    ) -> str:
        """生成分类摘要"""
        parts = []
        
        # 总体统计
        total_fields = stats["total_fields_classified"]
        parts.append(f"共分类了 {total_fields} 个字段")
        
        # 类别分布
        category_dist = stats["category_distribution"]
        main_categories = sorted(category_dist.items(), key=lambda x: x[1], reverse=True)[:3]
        if main_categories:
            cat_str = "、".join([f"{cat}({count}个)" for cat, count in main_categories])
            parts.append(f"主要类别：{cat_str}")
        
        # 分析特征
        measure_ratio = stats["measure_ratio"]
        if measure_ratio > 0.3:
            parts.append("数据库包含大量可计算的度量字段，适合进行数据分析")
        elif measure_ratio < 0.1:
            parts.append("数据库以维度数据为主，可能是配置或参考数据")
        
        # 时间字段
        timestamps = stats["all_timestamps"]
        if len(timestamps) > 5:
            parts.append(f"包含 {len(timestamps)} 个时间相关字段，支持时间序列分析")
        
        return "。".join(parts) + "。"