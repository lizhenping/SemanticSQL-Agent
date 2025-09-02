"""表映射器组件

选择适合特定场景的表。
"""

import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from ...models.database import DatabaseSchema
from ...models.generation import TableMapping
from ...models.analysis import DomainKnowledge

logger = logging.getLogger(__name__)


@dataclass
class TableSelection:
    """表选择结果"""
    primary_table: str
    related_tables: List[str]
    join_paths: List[Dict[str, Any]]
    rationale: str


class TableMapper:
    """表映射器
    
    根据场景、难度和问题类型选择合适的表。
    """
    
    def __init__(self):
        """初始化表映射器"""
        self.scenario_patterns = self._init_scenario_patterns()
        self.complexity_rules = self._init_complexity_rules()
    
    def map_tables(self,
                   schema: DatabaseSchema,
                   scenario: str,
                   difficulty: Any,
                   question_type: Any,
                   domain_knowledge: Optional[DomainKnowledge] = None) -> TableMapping:
        """映射表
        
        Args:
            schema: 数据库架构
            scenario: 场景名称
            difficulty: 难度级别
            question_type: 问题类型
            domain_knowledge: 领域知识
            
        Returns:
            表映射结果
        """
        logger.info(f"Mapping tables for scenario: {scenario}, difficulty: {difficulty.name}")
        
        # 获取候选表
        candidate_tables = self._get_candidate_tables(schema, scenario, domain_knowledge)
        
        # 根据难度选择表数量
        max_tables = self._get_max_tables(difficulty)
        
        # 根据问题类型过滤表
        filtered_tables = self._filter_by_question_type(
            candidate_tables, question_type, schema
        )
        
        # 选择主表
        primary_table = self._select_primary_table(
            filtered_tables, scenario, schema, domain_knowledge
        )
        
        # 选择相关表
        related_tables = self._select_related_tables(
            primary_table, filtered_tables, schema, max_tables - 1
        )
        
        # 查找连接路径
        join_paths = self._find_join_paths(
            primary_table, related_tables, schema
        )
        
        # 创建映射
        return TableMapping(
            scenario_id=scenario,
            complexity_level=difficulty.value if hasattr(difficulty, 'value') else 2,
            primary_table=primary_table,
            related_tables=related_tables,
            join_paths=join_paths,
            confidence=0.8
        )
    
    def _init_scenario_patterns(self) -> Dict[str, Dict[str, Any]]:
        """初始化场景模式"""
        return {
            'sales_analysis': {
                'keywords': ['order', 'sale', 'product', 'customer', 'revenue'],
                'required_types': ['transaction', 'master'],
                'preferred_relationships': ['customer_order', 'order_product']
            },
            'inventory_management': {
                'keywords': ['inventory', 'stock', 'product', 'warehouse', 'supplier'],
                'required_types': ['master', 'transaction', 'reference'],
                'preferred_relationships': ['product_inventory', 'supplier_product']
            },
            'customer_behavior': {
                'keywords': ['customer', 'behavior', 'activity', 'interaction', 'preference'],
                'required_types': ['master', 'transaction', 'history'],
                'preferred_relationships': ['customer_activity', 'customer_preference']
            }
        }
    
    def _init_complexity_rules(self) -> Dict[int, Dict[str, Any]]:
        """初始化复杂度规则"""
        return {
            1: {'max_tables': 1, 'allow_joins': False},
            2: {'max_tables': 2, 'allow_joins': True},
            3: {'max_tables': 3, 'allow_joins': True},
            4: {'max_tables': 5, 'allow_joins': True}
        }
    
    def _get_candidate_tables(self,
                            schema: DatabaseSchema,
                            scenario: str,
                            domain_knowledge: Optional[DomainKnowledge]) -> List[str]:
        """获取候选表"""
        candidates = []
        pattern = self.scenario_patterns.get(scenario, {})
        keywords = pattern.get('keywords', [])
        
        for table in schema.tables:
            table_lower = table.name.lower()
            
            # 基于关键词匹配
            if any(keyword in table_lower for keyword in keywords):
                candidates.append(table.name)
                continue
            
            # 基于领域知识
            if domain_knowledge and domain_knowledge.main_entities:
                if any(entity.lower() in table_lower 
                      for entity in domain_knowledge.main_entities):
                    candidates.append(table.name)
        
        # 如果候选太少，添加重要的表
        if len(candidates) < 3:
            for table in schema.tables:
                if self._is_important_table(table):
                    if table.name not in candidates:
                        candidates.append(table.name)
        
        return candidates
    
    def _get_max_tables(self, difficulty: Any) -> int:
        """获取最大表数量"""
        level = difficulty.value if hasattr(difficulty, 'value') else 2
        rule = self.complexity_rules.get(level, self.complexity_rules[2])
        return rule['max_tables']
    
    def _filter_by_question_type(self,
                                tables: List[str],
                                question_type: Any,
                                schema: DatabaseSchema) -> List[str]:
        """根据问题类型过滤表"""
        q_type = question_type.value if hasattr(question_type, 'value') else str(question_type)
        
        # 某些问题类型需要特定类型的表
        if q_type in ['aggregation', 'grouping']:
            # 需要事实表或交易表
            filtered = []
            for table_name in tables:
                table = next((t for t in schema.tables if t.name == table_name), None)
                if table and self._is_fact_or_transaction_table(table):
                    filtered.append(table_name)
            return filtered if filtered else tables
        
        elif q_type == 'joining':
            # 需要有关系的表
            filtered = []
            for table_name in tables:
                table = next((t for t in schema.tables if t.name == table_name), None)
                if table and (self._has_foreign_keys(table) or self._is_referenced(table, schema)):
                    filtered.append(table_name)
            return filtered if filtered else tables
        
        return tables
    
    def _select_primary_table(self,
                            candidates: List[str],
                            scenario: str,
                            schema: DatabaseSchema,
                            domain_knowledge: Optional[DomainKnowledge]) -> str:
        """选择主表"""
        if not candidates:
            # 返回第一个表作为后备
            return schema.tables[0].name if schema.tables else "unknown_table"
        
        # 计算每个候选表的得分
        scores = {}
        for table_name in candidates:
            table = next((t for t in schema.tables if t.name == table_name), None)
            if not table:
                continue
            
            score = 0
            
            # 场景相关性
            pattern = self.scenario_patterns.get(scenario, {})
            keywords = pattern.get('keywords', [])
            table_lower = table_name.lower()
            for keyword in keywords:
                if keyword in table_lower:
                    score += 10
            
            # 表的重要性
            if self._is_central_table(table, schema):
                score += 5
            
            # 数据量
            if hasattr(table, 'row_count') and table.row_count:
                if table.row_count > 1000:
                    score += 3
            
            scores[table_name] = score
        
        # 返回得分最高的表
        if scores:
            return max(scores, key=scores.get)
        
        return candidates[0]
    
    def _select_related_tables(self,
                             primary_table: str,
                             candidates: List[str],
                             schema: DatabaseSchema,
                             max_count: int) -> List[str]:
        """选择相关表"""
        if max_count <= 0:
            return []
        
        related = []
        
        # 查找直接相关的表
        primary = next((t for t in schema.tables if t.name == primary_table), None)
        if not primary:
            return []
        
        # 优先选择有直接关系的表
        for table in schema.tables:
            if table.name == primary_table or table.name not in candidates:
                continue
            
            # 检查是否有外键关系
            has_relation = False
            
            # 主表引用此表
            for fk in primary.foreign_keys:
                if fk.get('referenced_table') == table.name:
                    has_relation = True
                    break
            
            # 此表引用主表
            if not has_relation:
                for fk in table.foreign_keys:
                    if fk.get('referenced_table') == primary_table:
                        has_relation = True
                        break
            
            if has_relation:
                related.append(table.name)
                if len(related) >= max_count:
                    break
        
        # 如果还不够，添加其他候选表
        for table_name in candidates:
            if table_name != primary_table and table_name not in related:
                related.append(table_name)
                if len(related) >= max_count:
                    break
        
        return related
    
    def _find_join_paths(self,
                        primary_table: str,
                        related_tables: List[str],
                        schema: DatabaseSchema) -> List[Dict[str, Any]]:
        """查找连接路径"""
        join_paths = []
        
        for related_table in related_tables:
            path = self._find_join_path(primary_table, related_table, schema)
            if path:
                join_paths.append(path)
        
        return join_paths
    
    def _find_join_path(self,
                       table1: str,
                       table2: str,
                       schema: DatabaseSchema) -> Optional[Dict[str, Any]]:
        """查找两个表之间的连接路径"""
        t1 = next((t for t in schema.tables if t.name == table1), None)
        t2 = next((t for t in schema.tables if t.name == table2), None)
        
        if not t1 or not t2:
            return None
        
        # 直接外键关系
        for fk in t1.foreign_keys:
            if fk.get('referenced_table') == table2:
                return {
                    'from_table': table1,
                    'to_table': table2,
                    'join_type': 'inner',
                    'condition': f"{table1}.{fk.get('column')} = {table2}.{fk.get('referenced_column', 'id')}"
                }
        
        for fk in t2.foreign_keys:
            if fk.get('referenced_table') == table1:
                return {
                    'from_table': table1,
                    'to_table': table2,
                    'join_type': 'inner',
                    'condition': f"{table2}.{fk.get('column')} = {table1}.{fk.get('referenced_column', 'id')}"
                }
        
        # 没有直接关系，返回None
        return None
    
    # 辅助方法
    
    def _is_important_table(self, table: Any) -> bool:
        """判断是否为重要表"""
        # 有主键
        has_pk = any(col.is_primary_key for col in table.columns)
        
        # 被多个表引用
        # 有多个外键
        fk_count = sum(1 for col in table.columns if col.is_foreign_key)
        
        return has_pk and (fk_count >= 2 or len(table.columns) >= 5)
    
    def _is_fact_or_transaction_table(self, table: Any) -> bool:
        """判断是否为事实表或交易表"""
        table_lower = table.name.lower()
        
        # 名称模式
        transaction_patterns = ['order', 'sale', 'transaction', 'payment', 'invoice']
        if any(pattern in table_lower for pattern in transaction_patterns):
            return True
        
        # 结构特征
        has_amount = any('amount' in col.name.lower() or 'price' in col.name.lower() 
                        for col in table.columns)
        has_date = any('date' in col.name.lower() or 'time' in col.name.lower() 
                      for col in table.columns)
        has_fks = sum(1 for col in table.columns if col.is_foreign_key) >= 2
        
        return has_amount and has_date and has_fks
    
    def _has_foreign_keys(self, table: Any) -> bool:
        """检查表是否有外键"""
        return any(col.is_foreign_key for col in table.columns)
    
    def _is_referenced(self, table: Any, schema: DatabaseSchema) -> bool:
        """检查表是否被其他表引用"""
        for other_table in schema.tables:
            if other_table.name != table.name:
                for fk in other_table.foreign_keys:
                    if fk.get('referenced_table') == table.name:
                        return True
        return False
    
    def _is_central_table(self, table: Any, schema: DatabaseSchema) -> bool:
        """判断是否为中心表"""
        # 被多个表引用
        ref_count = 0
        for other_table in schema.tables:
            if other_table.name != table.name:
                # 通过外键列表检查是否引用了当前表
                for fk in other_table.foreign_keys:
                    if fk.get('referenced_table') == table.name:
                        ref_count += 1
                        break
        
        return ref_count >= 3