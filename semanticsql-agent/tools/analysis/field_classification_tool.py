"""
字段分类工具 - 对数据库字段进行智能分类
"""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime

from tools.base_tool import BaseTool, ToolParameter
from core.constants import FIELD_TYPES


class FieldClassificationTool(BaseTool):
    """字段智能分类工具"""
    
    @property
    def name(self) -> str:
        return "classify_fields"
    
    @property
    def description(self) -> str:
        return "对数据库表的字段进行智能分类，识别字段的业务含义"
    
    @property
    def category(self) -> str:
        return "analysis"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="table_info",
                type="object",
                description="表结构信息",
                required=True
            ),
            ToolParameter(
                name="sample_data",
                type="array",
                description="样本数据（可选）",
                required=False,
                default=[]
            ),
            ToolParameter(
                name="custom_patterns",
                type="object",
                description="自定义分类模式",
                required=False,
                default={}
            )
        ]
    
    def _execute(self, table_info: Dict[str, Any], sample_data: List[Dict] = None,
                 custom_patterns: Dict[str, List[str]] = None) -> Dict[str, Any]:
        """
        执行字段分类
        
        Returns:
            分类结果
        """
        classification_result = {
            "table_name": table_info.get("name", "unknown"),
            "field_classifications": {},
            "statistics": {},
            "recommendations": []
        }
        
        # 合并自定义模式
        patterns = self._merge_patterns(FIELD_TYPES, custom_patterns)
        
        # 对每个字段进行分类
        for column in table_info.get("columns", []):
            field_name = column.get("name", "")
            field_type = column.get("data_type", "")
            
            # 基于名称和类型分类
            classification = self._classify_field(
                field_name, field_type, patterns
            )
            
            # 如果有样本数据，进行数据分析
            if sample_data:
                data_analysis = self._analyze_field_data(
                    field_name, sample_data
                )
                classification["data_characteristics"] = data_analysis
            
            classification_result["field_classifications"][field_name] = classification
        
        # 统计分类结果
        classification_result["statistics"] = self._calculate_statistics(
            classification_result["field_classifications"]
        )
        
        # 生成建议
        classification_result["recommendations"] = self._generate_recommendations(
            classification_result["field_classifications"],
            table_info
        )
        
        return classification_result
    
    def _classify_field(self, field_name: str, field_type: str,
                        patterns: Dict[str, List[str]]) -> Dict[str, Any]:
        """分类单个字段"""
        field_lower = field_name.lower()
        type_lower = field_type.lower()
        
        classification = {
            "category": "unknown",
            "confidence": 0.0,
            "business_meaning": "",
            "data_type_group": self._get_data_type_group(type_lower),
            "characteristics": []
        }
        
        # 检查每个分类模式
        best_match = None
        best_score = 0
        
        for category, keywords in patterns.items():
            score = self._calculate_match_score(field_lower, keywords)
            if score > best_score:
                best_score = score
                best_match = category
        
        if best_match:
            classification["category"] = best_match
            classification["confidence"] = min(best_score * 100, 100)
            classification["business_meaning"] = self._get_business_meaning(
                best_match, field_name
            )
        
        # 识别特征
        classification["characteristics"] = self._identify_characteristics(
            field_name, field_type
        )
        
        return classification
    
    def _calculate_match_score(self, field_name: str, keywords: List[str]) -> float:
        """计算匹配分数"""
        score = 0.0
        
        for keyword in keywords:
            if keyword in field_name:
                # 完全匹配得分更高
                if field_name == keyword:
                    score += 1.0
                # 前缀匹配
                elif field_name.startswith(keyword):
                    score += 0.8
                # 后缀匹配
                elif field_name.endswith(keyword):
                    score += 0.7
                # 包含匹配
                else:
                    score += 0.5
        
        return score / len(keywords) if keywords else 0
    
    def _get_data_type_group(self, type_str: str) -> str:
        """获取数据类型分组"""
        if any(t in type_str for t in ['int', 'bigint', 'smallint', 'tinyint']):
            return "integer"
        elif any(t in type_str for t in ['decimal', 'float', 'double', 'numeric']):
            return "decimal"
        elif any(t in type_str for t in ['varchar', 'char', 'text', 'string']):
            return "string"
        elif any(t in type_str for t in ['date', 'time', 'timestamp', 'datetime']):
            return "datetime"
        elif any(t in type_str for t in ['bool', 'boolean', 'bit']):
            return "boolean"
        elif any(t in type_str for t in ['blob', 'binary', 'varbinary']):
            return "binary"
        elif any(t in type_str for t in ['json', 'jsonb']):
            return "json"
        else:
            return "other"
    
    def _get_business_meaning(self, category: str, field_name: str) -> str:
        """获取业务含义描述"""
        meanings = {
            "identifier": f"唯一标识符，用于识别记录",
            "timestamp": f"时间戳字段，记录时间信息",
            "numeric": f"数值字段，表示数量或金额",
            "category": f"分类字段，表示类型或状态",
            "description": f"描述性字段，包含文本信息"
        }
        return meanings.get(category, "业务含义待确定")
    
    def _identify_characteristics(self, field_name: str, field_type: str) -> List[str]:
        """识别字段特征"""
        characteristics = []
        field_lower = field_name.lower()
        
        # 主键特征
        if field_lower == "id" or field_lower.endswith("_id"):
            characteristics.append("likely_primary_key")
        
        # 外键特征
        if "_id" in field_lower and not field_lower.endswith("id"):
            characteristics.append("likely_foreign_key")
        
        # 必填字段特征
        if any(word in field_lower for word in ["name", "title", "code"]):
            characteristics.append("likely_required")
        
        # 索引候选
        if any(word in field_lower for word in ["code", "no", "date", "status"]):
            characteristics.append("index_candidate")
        
        # 敏感数据
        if any(word in field_lower for word in ["password", "pwd", "secret", "token"]):
            characteristics.append("sensitive_data")
        
        # 金额相关
        if any(word in field_lower for word in ["price", "amount", "cost", "fee"]):
            characteristics.append("monetary_value")
        
        return characteristics
    
    def _analyze_field_data(self, field_name: str, sample_data: List[Dict]) -> Dict[str, Any]:
        """分析字段的实际数据"""
        values = [row.get(field_name) for row in sample_data if field_name in row]
        
        if not values:
            return {}
        
        analysis = {
            "sample_size": len(values),
            "null_count": sum(1 for v in values if v is None),
            "unique_count": len(set(v for v in values if v is not None))
        }
        
        # 分析数据特征
        non_null_values = [v for v in values if v is not None]
        
        if non_null_values:
            # 数值分析
            if all(isinstance(v, (int, float)) for v in non_null_values):
                analysis["data_type"] = "numeric"
                analysis["min"] = min(non_null_values)
                analysis["max"] = max(non_null_values)
                analysis["avg"] = sum(non_null_values) / len(non_null_values)
            
            # 字符串分析
            elif all(isinstance(v, str) for v in non_null_values):
                analysis["data_type"] = "string"
                analysis["min_length"] = min(len(v) for v in non_null_values)
                analysis["max_length"] = max(len(v) for v in non_null_values)
                analysis["avg_length"] = sum(len(v) for v in non_null_values) / len(non_null_values)
                
                # 检查格式模式
                if self._is_email_pattern(non_null_values):
                    analysis["pattern"] = "email"
                elif self._is_phone_pattern(non_null_values):
                    analysis["pattern"] = "phone"
                elif self._is_url_pattern(non_null_values):
                    analysis["pattern"] = "url"
        
        return analysis
    
    def _is_email_pattern(self, values: List[str]) -> bool:
        """检查是否为邮箱格式"""
        email_pattern = re.compile(r'^[\w\.-]+@[\w\.-]+\.\w+$')
        return all(email_pattern.match(str(v)) for v in values[:10])
    
    def _is_phone_pattern(self, values: List[str]) -> bool:
        """检查是否为电话格式"""
        phone_pattern = re.compile(r'^[\d\-\+\(\)\s]+$')
        return all(phone_pattern.match(str(v)) for v in values[:10])
    
    def _is_url_pattern(self, values: List[str]) -> bool:
        """检查是否为URL格式"""
        url_pattern = re.compile(r'^https?://[\w\.-]+')
        return all(url_pattern.match(str(v)) for v in values[:10])
    
    def _calculate_statistics(self, classifications: Dict[str, Dict]) -> Dict[str, Any]:
        """计算分类统计"""
        stats = {
            "total_fields": len(classifications),
            "category_distribution": {},
            "confidence_avg": 0,
            "identified_keys": [],
            "sensitive_fields": []
        }
        
        confidences = []
        
        for field_name, classification in classifications.items():
            category = classification["category"]
            stats["category_distribution"][category] = \
                stats["category_distribution"].get(category, 0) + 1
            
            confidences.append(classification["confidence"])
            
            # 识别关键字段
            if "likely_primary_key" in classification.get("characteristics", []):
                stats["identified_keys"].append({"field": field_name, "type": "primary"})
            elif "likely_foreign_key" in classification.get("characteristics", []):
                stats["identified_keys"].append({"field": field_name, "type": "foreign"})
            
            # 识别敏感字段
            if "sensitive_data" in classification.get("characteristics", []):
                stats["sensitive_fields"].append(field_name)
        
        if confidences:
            stats["confidence_avg"] = sum(confidences) / len(confidences)
        
        return stats
    
    def _generate_recommendations(self, classifications: Dict[str, Dict],
                                 table_info: Dict[str, Any]) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        # 检查是否有主键
        has_primary_key = any(
            "likely_primary_key" in c.get("characteristics", [])
            for c in classifications.values()
        )
        
        if not has_primary_key:
            recommendations.append("建议为表添加主键字段")
        
        # 检查索引建议
        index_candidates = [
            field for field, c in classifications.items()
            if "index_candidate" in c.get("characteristics", [])
        ]
        
        if index_candidates:
            recommendations.append(
                f"建议为以下字段创建索引：{', '.join(index_candidates[:3])}"
            )
        
        # 检查敏感数据
        sensitive_fields = [
            field for field, c in classifications.items()
            if "sensitive_data" in c.get("characteristics", [])
        ]
        
        if sensitive_fields:
            recommendations.append(
                f"检测到敏感数据字段：{', '.join(sensitive_fields)}，建议加密存储"
            )
        
        # 检查分类置信度
        low_confidence_fields = [
            field for field, c in classifications.items()
            if c.get("confidence", 0) < 50
        ]
        
        if len(low_confidence_fields) > len(classifications) * 0.3:
            recommendations.append(
                "多个字段分类置信度较低，建议规范化字段命名"
            )
        
        return recommendations
    
    def _merge_patterns(self, default_patterns: Dict, custom_patterns: Dict) -> Dict:
        """合并默认和自定义模式"""
        if not custom_patterns:
            return default_patterns
        
        merged = default_patterns.copy()
        for category, patterns in custom_patterns.items():
            if category in merged:
                merged[category].extend(patterns)
            else:
                merged[category] = patterns
        
        return merged