"""ER关系格式化器

格式化实体关系信息，包括物理、逻辑、概念三层。
"""

from typing import List, Dict, Any, Optional
from .base import BaseFormatter
from ...models.analysis import ERRelations, PhysicalRelation, LogicalRelation, ConceptualModel


class ERRelationFormatter(BaseFormatter):
    """ER关系格式化器
    
    将三层ER关系格式化为适合LLM理解的文本格式。
    """
    
    def format(self, data: Any, context: Optional[Dict[str, Any]] = None) -> str:
        """格式化ER关系信息
        
        Args:
            data: ERRelations对象或关系列表
            context: 额外的上下文信息
            
        Returns:
            格式化后的ER关系信息
        """
        if isinstance(data, ERRelations):
            return self.format_er_relations(data)
        elif isinstance(data, list):
            # 判断列表类型
            if data and isinstance(data[0], PhysicalRelation):
                return self.format_physical_relations(data)
            elif data and isinstance(data[0], LogicalRelation):
                return self.format_logical_relations(data)
        elif isinstance(data, ConceptualModel):
            return self.format_conceptual_model(data)
        else:
            return str(data)
    
    def format_er_relations(self, er_relations: ERRelations) -> str:
        """格式化完整的三层ER关系"""
        lines = []
        lines.append("=== Entity Relationship Analysis ===")
        
        # 物理层
        lines.append("\n## Physical Layer (Database Level)")
        lines.append(self.format_physical_relations(er_relations.physical_relations))
        
        # 逻辑层
        lines.append("\n## Logical Layer (Business Logic)")
        lines.append(self.format_logical_relations(er_relations.logical_relations))
        
        # 概念层
        lines.append("\n## Conceptual Layer (Domain Model)")
        lines.append(self.format_conceptual_model(er_relations.conceptual_model))
        
        return '\n'.join(lines)
    
    def format_physical_relations(self, relations: List[PhysicalRelation]) -> str:
        """格式化物理层关系"""
        if not relations:
            return "No physical relationships found."
        
        lines = []
        lines.append(f"Found {len(relations)} physical relationships:")
        
        # 按源表分组
        by_table = {}
        for rel in relations:
            if rel.from_table not in by_table:
                by_table[rel.from_table] = []
            by_table[rel.from_table].append(rel)
        
        # 格式化每个表的关系
        for table, rels in sorted(by_table.items()):
            lines.append(f"\n{table}:")
            for rel in rels[:5]:  # 限制每个表最多显示5个关系
                lines.append(f"  → {rel.to_table} ({rel.from_column} → {rel.to_column}) [{rel.relationship_type}]")
            
            if len(rels) > 5:
                lines.append(f"  ... and {len(rels) - 5} more relationships")
        
        return '\n'.join(lines)
    
    def format_logical_relations(self, relations: List[LogicalRelation]) -> str:
        """格式化逻辑层关系"""
        if not relations:
            return "No logical relationships found."
        
        lines = []
        lines.append(f"Found {len(relations)} logical relationships:")
        
        for rel in relations[:10]:  # 限制显示前10个
            line = f"\n- {rel.source_table} ↔ {rel.target_table}"
            line += f" [{rel.relationship_type}]"
            
            if rel.business_meaning:
                line += f"\n  Business Meaning: {self._truncate(rel.business_meaning, 80)}"
            
            if hasattr(rel, 'cardinality') and rel.cardinality:
                line += f"\n  Cardinality: {rel.cardinality}"
            
            if hasattr(rel, 'is_mandatory') and rel.is_mandatory:
                line += " (Mandatory)"
            
            lines.append(line)
        
        if len(relations) > 10:
            lines.append(f"\n... and {len(relations) - 10} more relationships")
        
        return '\n'.join(lines)
    
    def format_conceptual_model(self, model: ConceptualModel) -> str:
        """格式化概念层模型"""
        lines = []
        
        # 实体
        lines.append(f"Entities ({len(model.entities)}):")
        for entity in model.entities[:8]:  # 限制显示前8个
            line = f"\n- {entity.name}"
            if entity.business_meaning:
                line += f": {self._truncate(entity.business_meaning, 60)}"
            
            lines.append(line)
            
            # 关键属性
            if entity.key_attributes:
                lines.append(f"  Key Attributes: {', '.join(entity.key_attributes[:5])}")
            
            # 相关表
            if entity.related_tables:
                lines.append(f"  Tables: {', '.join(entity.related_tables[:3])}")
        
        if len(model.entities) > 8:
            lines.append(f"\n... and {len(model.entities) - 8} more entities")
        
        # 关系
        lines.append(f"\n\nRelationships ({len(model.relationships)}):")
        for rel in model.relationships[:8]:  # 限制显示前8个
            line = f"\n- {rel.source_table} ↔ {rel.target_table}"
            line += f" [{rel.relationship_type}]"
            
            if rel.business_meaning:
                line += f"\n  {self._truncate(rel.business_meaning, 80)}"
            
            lines.append(line)
        
        if len(model.relationships) > 8:
            lines.append(f"\n... and {len(model.relationships) - 8} more relationships")
        
        return '\n'.join(lines)
    
    def format_join_paths(self, relations: List[PhysicalRelation], tables: List[str]) -> str:
        """格式化表之间的连接路径"""
        lines = []
        lines.append("=== Available Join Paths ===")
        
        # 构建关系图
        graph = self._build_relationship_graph(relations)
        
        # 查找表之间的路径
        paths_found = 0
        for i, table1 in enumerate(tables):
            for table2 in tables[i+1:]:
                paths = self._find_paths(graph, table1, table2, max_depth=3)
                if paths:
                    paths_found += 1
                    lines.append(f"\n{table1} → {table2}:")
                    for path in paths[:2]:  # 每对表最多显示2条路径
                        lines.append(f"  - {' → '.join(path)}")
        
        if paths_found == 0:
            lines.append("\nNo direct join paths found between the selected tables.")
        
        return '\n'.join(lines)
    
    def _build_relationship_graph(self, relations: List[PhysicalRelation]) -> Dict[str, List[tuple]]:
        """构建关系图"""
        graph = {}
        for rel in relations:
            # 正向关系
            if rel.from_table not in graph:
                graph[rel.from_table] = []
            graph[rel.from_table].append((rel.to_table, rel.from_column, rel.to_column))
            
            # 反向关系
            if rel.to_table not in graph:
                graph[rel.to_table] = []
            graph[rel.to_table].append((rel.from_table, rel.to_column, rel.from_column))
        
        return graph
    
    def _find_paths(self, graph: Dict[str, List[tuple]], start: str, end: str, max_depth: int = 3) -> List[List[str]]:
        """查找两个表之间的路径"""
        if start == end:
            return [[start]]
        
        paths = []
        queue = [(start, [start])]
        visited = set()
        
        while queue and len(paths) < 3:  # 最多返回3条路径
            current, path = queue.pop(0)
            
            if len(path) > max_depth:
                continue
            
            if current in visited:
                continue
            visited.add(current)
            
            if current in graph:
                for next_table, from_col, to_col in graph[current]:
                    if next_table not in path:  # 避免循环
                        new_path = path + [f"{current}.{from_col}={next_table}.{to_col}", next_table]
                        if next_table == end:
                            paths.append(new_path)
                        else:
                            queue.append((next_table, new_path))
        
        return paths