"""字段信息格式化器

格式化数据库字段信息，包括字段分类、熵值等。
"""

from typing import List, Dict, Any, Optional
from .base import BaseFormatter
from ...models.database import ColumnInfo
from ...models.analysis import FieldClassification


class FieldFormatter(BaseFormatter):
    """字段信息格式化器
    
    将字段信息格式化为适合LLM理解的文本格式。
    """
    
    def format(self, data: Any, context: Optional[Dict[str, Any]] = None) -> str:
        """格式化字段信息
        
        Args:
            data: 字段名列表或字段信息字典
            context: 包含 columns, field_classifications 等信息
            
        Returns:
            格式化后的字段信息
        """
        if isinstance(data, list):
            return self.format_field_list(data, context)
        elif isinstance(data, dict):
            return self.format_field_dict(data, context)
        else:
            return str(data)
    
    def format_field_list(self, field_names: List[str], context: Optional[Dict[str, Any]] = None) -> str:
        """格式化字段列表"""
        if not context:
            return "Fields: " + ", ".join(field_names)
        
        lines = []
        lines.append(f"=== Fields ({len(field_names)}) ===")
        
        for field_name in field_names:
            # 解析表名和列名
            if '.' in field_name:
                table_name, column_name = field_name.split('.', 1)
            else:
                table_name = context.get('current_table', 'unknown')
                column_name = field_name
            
            # 获取列信息
            columns = context.get('columns', {}).get(table_name, [])
            column = next((c for c in columns if c.name == column_name), None)
            
            # 获取字段分类
            field_classifications = context.get('field_classifications', {})
            field_class = field_classifications.get(field_name)
            
            # 格式化输出
            line = f"\n- {field_name}"
            
            # 数据类型
            if column:
                line += f" ({column.data_type})"
            
            # 字段分类
            if field_class:
                line += f" [{field_class.field_type}]"
                if hasattr(field_class, 'entropy_level'):
                    line += f" [Entropy: {field_class.entropy_level}]"
            
            lines.append(line)
            
            # 字段描述
            if column and hasattr(column, 'description') and column.description:
                lines.append(f"  Description: {self._truncate(column.description, 80)}")
        
        return '\n'.join(lines)
    
    def format_field_dict(self, field_info: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> str:
        """格式化字段字典信息"""
        lines = []
        lines.append("=== Field Details ===")
        
        # 按类型分组
        by_type = {}
        for field_name, info in field_info.items():
            field_type = info.get('type', 'unknown')
            if field_type not in by_type:
                by_type[field_type] = []
            by_type[field_type].append((field_name, info))
        
        # 格式化每个类型组
        for field_type, fields in by_type.items():
            lines.append(f"\n{field_type.upper()} Fields ({len(fields)}):")
            
            for field_name, info in fields[:10]:  # 限制每组最多10个
                line = f"  - {field_name}"
                
                # 添加额外信息
                if 'data_type' in info:
                    line += f" ({info['data_type']})"
                if 'importance' in info:
                    line += f" [Importance: {info['importance']:.2f}]"
                if 'entropy_level' in info:
                    line += f" [Entropy: {info['entropy_level']}]"
                
                lines.append(line)
            
            if len(fields) > 10:
                lines.append(f"  ... and {len(fields) - 10} more")
        
        return '\n'.join(lines)
    
    def format_field_classification_summary(self, classifications: Dict[str, FieldClassification]) -> str:
        """格式化字段分类汇总"""
        lines = []
        lines.append("=== Field Classification Summary ===")
        
        # 统计各类型数量
        type_counts = {}
        entropy_counts = {'low': 0, 'medium': 0, 'high': 0}
        
        for field_key, fc in classifications.items():
            # 类型统计
            field_type = fc.field_type
            type_counts[field_type] = type_counts.get(field_type, 0) + 1
            
            # 熵值统计
            if hasattr(fc, 'entropy_level'):
                entropy_counts[fc.entropy_level] = entropy_counts.get(fc.entropy_level, 0) + 1
        
        # 输出统计
        lines.append(f"\nTotal Fields: {len(classifications)}")
        
        lines.append("\nBy Type:")
        for field_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(classifications)) * 100
            lines.append(f"  - {field_type}: {count} ({percentage:.1f}%)")
        
        lines.append("\nBy Entropy Level:")
        for level, count in entropy_counts.items():
            if count > 0:
                percentage = (count / len(classifications)) * 100
                lines.append(f"  - {level}: {count} ({percentage:.1f}%)")
        
        return '\n'.join(lines)
    
    def format_field_for_prompt(self, field_name: str, context: Optional[Dict[str, Any]] = None) -> str:
        """为提示词格式化单个字段"""
        if not context:
            return field_name
        
        # 解析表名和列名
        if '.' in field_name:
            table_name, column_name = field_name.split('.', 1)
        else:
            return field_name
        
        # 获取列信息
        columns = context.get('columns', {}).get(table_name, [])
        column = next((c for c in columns if c.name == column_name), None)
        
        if not column:
            return field_name
        
        # 构建描述
        parts = [field_name]
        
        # 数据类型
        parts.append(f"({column.data_type})")
        
        # 关键属性
        attrs = []
        if column.is_primary_key:
            attrs.append("PK")
        if column.is_foreign_key:
            attrs.append("FK")
        if not column.is_nullable:
            attrs.append("NOT NULL")
        
        if attrs:
            parts.append(f"[{', '.join(attrs)}]")
        
        # 字段分类
        field_classifications = context.get('field_classifications', {})
        if field_name in field_classifications:
            fc = field_classifications[field_name]
            parts.append(f"<{fc.field_type}>")
        
        return ' '.join(parts)