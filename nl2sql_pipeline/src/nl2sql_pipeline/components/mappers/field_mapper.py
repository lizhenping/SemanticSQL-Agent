"""字段映射器组件

选择适合特定问题类型的字段。
"""

import logging
from typing import List, Dict, Any, Optional

from ...models.database import DatabaseSchema
from ...models.generation import FieldMapping
from ...models.analysis import FieldClassification

logger = logging.getLogger(__name__)


class FieldMapper:
    """字段映射器
    
    根据问题类型和表选择合适的字段。
    """
    
    def __init__(self):
        """初始化字段映射器"""
        self.type_field_rules = self._init_type_field_rules()
    
    def map_fields(self,
                   tables: List[str],
                   schema: DatabaseSchema,
                   question_type: Any,
                   field_classifications: Optional[Dict[str, FieldClassification]] = None) -> FieldMapping:
        """映射字段
        
        Args:
            tables: 已选择的表列表
            schema: 数据库架构
            question_type: 问题类型
            field_classifications: 字段分类信息
            
        Returns:
            字段映射结果
        """
        logger.info(f"Mapping fields for {len(tables)} tables, type: {question_type.value}")
        
        selected_fields = []
        field_mappings = {}
        
        # 获取问题类型的字段规则
        field_rules = self.type_field_rules.get(
            question_type.value if hasattr(question_type, 'value') else str(question_type),
            self.type_field_rules['default']
        )
        
        # 为每个表选择字段
        for table_name in tables:
            table = next((t for t in schema.tables if t.name == table_name), None)
            if not table:
                continue
            
            # 选择字段
            table_fields = self._select_fields_for_table(
                table, field_rules, field_classifications
            )
            
            # 添加到结果
            for field in table_fields:
                field_key = f"{table_name}.{field['name']}"
                selected_fields.append(field_key)
                
                if table_name not in field_mappings:
                    field_mappings[table_name] = []
                field_mappings[table_name].append(field)
        
        # 查找连接字段
        join_fields = self._find_join_fields(tables, schema)
        
        # 创建映射
        return FieldMapping(
            sub_scenario="default",
            selected_fields=selected_fields,
            grouping_fields=[],
            filter_fields=[],
            output_fields=selected_fields
        )
    
    def _init_type_field_rules(self) -> Dict[str, Dict[str, Any]]:
        """初始化类型字段规则"""
        return {
            'basic_retrieval': {
                'prefer_types': ['dimension', 'identifier', 'attribute'],
                'avoid_types': ['measure'],
                'max_fields': 5,
                'include_keys': True
            },
            'aggregation': {
                'prefer_types': ['measure', 'metric'],
                'group_by_types': ['dimension', 'category'],
                'max_fields': 8,
                'include_keys': False
            },
            'filtering': {
                'prefer_types': ['dimension', 'category', 'datetime', 'status'],
                'avoid_types': ['description'],
                'max_fields': 6,
                'include_keys': True
            },
            'grouping': {
                'prefer_types': ['dimension', 'category'],
                'aggregate_types': ['measure', 'metric'],
                'max_fields': 10,
                'include_keys': False
            },
            'joining': {
                'prefer_types': ['identifier', 'foreign_key'],
                'include_types': ['dimension', 'measure'],
                'max_fields': 15,
                'include_keys': True
            },
            'calculation': {
                'prefer_types': ['measure', 'metric', 'amount'],
                'support_types': ['dimension'],
                'max_fields': 8,
                'include_keys': False
            },
            'comparison': {
                'prefer_types': ['measure', 'datetime', 'status'],
                'group_types': ['dimension'],
                'max_fields': 10,
                'include_keys': True
            },
            'default': {
                'prefer_types': ['dimension', 'measure'],
                'max_fields': 10,
                'include_keys': True
            }
        }
    
    def _select_fields_for_table(self,
                               table: Any,
                               field_rules: Dict[str, Any],
                               field_classifications: Optional[Dict[str, FieldClassification]]) -> List[Dict[str, Any]]:
        """为表选择字段"""
        selected = []
        
        # 获取字段分类信息
        field_info = {}
        for col in table.columns:
            field_key = f"{table.name}.{col.name}"
            classification = field_classifications.get(field_key) if field_classifications else None
            
            field_type = 'unknown'
            importance = 0.5
            
            if classification:
                field_type = classification.field_type
                importance = classification.importance or 0.5
            else:
                # 基于列属性推断
                field_type = self._infer_field_type(col)
                importance = self._calculate_importance(col)
            
            field_info[col.name] = {
                'name': col.name,
                'type': field_type,
                'importance': importance,
                'data_type': col.data_type,
                'is_key': col.is_primary_key or col.is_foreign_key,
                'is_nullable': col.is_nullable
            }
        
        # 根据规则选择字段
        # 1. 必须包含的键字段
        if field_rules.get('include_keys', True):
            for name, info in field_info.items():
                if info['is_key']:
                    selected.append(info)
        
        # 2. 优先类型的字段
        prefer_types = field_rules.get('prefer_types', [])
        for field_type in prefer_types:
            for name, info in field_info.items():
                if info['type'] == field_type and info not in selected:
                    selected.append(info)
                    if len(selected) >= field_rules.get('max_fields', 10):
                        return selected
        
        # 3. 按重要性补充
        remaining = sorted(
            [info for info in field_info.values() if info not in selected],
            key=lambda x: x['importance'],
            reverse=True
        )
        
        avoid_types = field_rules.get('avoid_types', [])
        for info in remaining:
            if info['type'] not in avoid_types:
                selected.append(info)
                if len(selected) >= field_rules.get('max_fields', 10):
                    break
        
        return selected
    
    def _find_join_fields(self,
                         tables: List[str],
                         schema: DatabaseSchema) -> List[Dict[str, str]]:
        """查找连接字段"""
        join_fields = []
        
        # 查找表之间的外键关系
        for i, table1_name in enumerate(tables):
            table1 = next((t for t in schema.tables if t.name == table1_name), None)
            if not table1:
                continue
            
            for j, table2_name in enumerate(tables):
                if i >= j:  # 避免重复
                    continue
                
                table2 = next((t for t in schema.tables if t.name == table2_name), None)
                if not table2:
                    continue
                
                # 检查table1到table2的外键
                for fk in table1.foreign_keys:
                    if fk.get('referenced_table') == table2_name:
                        join_fields.append({
                            'from_field': f"{table1_name}.{fk.get('column')}",
                            'to_field': f"{table2_name}.{fk.get('referenced_column', 'id')}",
                            'join_type': 'foreign_key'
                        })
                
                # 检查table2到table1的外键
                for fk in table2.foreign_keys:
                    if fk.get('referenced_table') == table1_name:
                        join_fields.append({
                            'from_field': f"{table2_name}.{fk.get('column')}",
                            'to_field': f"{table1_name}.{fk.get('referenced_column', 'id')}",
                            'join_type': 'foreign_key'
                        })
        
        return join_fields
    
    def _infer_field_type(self, column: Any) -> str:
        """推断字段类型"""
        col_lower = column.name.lower()
        data_type_lower = column.data_type.lower() if column.data_type else ''
        
        # 基于列名
        if column.is_primary_key:
            return 'identifier'
        elif column.is_foreign_key:
            return 'foreign_key'
        elif any(kw in col_lower for kw in ['amount', 'price', 'cost', 'total', 'sum']):
            return 'measure'
        elif any(kw in col_lower for kw in ['count', 'quantity', 'number']):
            return 'metric'
        elif any(kw in col_lower for kw in ['date', 'time', 'created', 'updated']):
            return 'datetime'
        elif any(kw in col_lower for kw in ['status', 'state', 'type', 'category']):
            return 'category'
        elif any(kw in col_lower for kw in ['name', 'title', 'code']):
            return 'dimension'
        elif any(kw in col_lower for kw in ['description', 'comment', 'note']):
            return 'description'
        
        # 基于数据类型
        elif any(t in data_type_lower for t in ['int', 'decimal', 'float', 'double', 'numeric']):
            return 'measure'
        elif any(t in data_type_lower for t in ['date', 'time']):
            return 'datetime'
        elif any(t in data_type_lower for t in ['text', 'clob']):
            return 'description'
        elif any(t in data_type_lower for t in ['char', 'varchar']):
            return 'dimension'
        
        return 'attribute'
    
    def _calculate_importance(self, column: Any) -> float:
        """计算字段重要性"""
        importance = 0.5
        
        # 键字段更重要
        if column.is_primary_key:
            importance = 0.9
        elif column.is_foreign_key:
            importance = 0.8
        
        # 非空字段更重要
        elif not column.is_nullable:
            importance = 0.7
        
        # 常见业务字段
        col_lower = column.name.lower()
        if any(kw in col_lower for kw in ['name', 'amount', 'date', 'status', 'type']):
            importance = max(importance, 0.7)
        
        return importance