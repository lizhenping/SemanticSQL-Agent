"""实体关系分析工具

参考 nl2sql_pipeline 的 er_analysis_pipeline 实现，
分析数据库中的实体关系。
"""

from typing import Dict, Any, List, Optional, Set, Tuple
import logging
from collections import defaultdict

from .base import BaseSemanticSQLTool

logger = logging.getLogger(__name__)


class ERAnalysisTool(BaseSemanticSQLTool):
    """实体关系分析工具
    
    分析数据库中表之间的关系，包括显式外键和隐式关联。
    这是分析流程的第四步，为复杂的多表查询提供关系理解。
    """
    
    name = "analyze_entity_relationships"
    description = (
        "分析数据库中表之间的实体关系。"
        "识别外键关系、命名约定关系、字段关联等。"
        "构建关系图谱，支持复杂的多表 JOIN 查询。"
    )
    
    def execute(
        self,
        schema_info: Dict[str, Any],
        domain_analysis: Optional[Dict[str, Any]] = None,
        field_classifications: Optional[Dict[str, Any]] = None,
        analyze_implicit: bool = True
    ) -> Dict[str, Any]:
        """执行实体关系分析"""
        logger.info("开始实体关系分析")
        
        tables = schema_info.get("tables", [])
        
        # 1. 提取显式关系（外键）
        explicit_relations = self._extract_explicit_relations(tables)
        
        # 2. 推断隐式关系（如果启用）
        implicit_relations = []
        if analyze_implicit:
            implicit_relations = self._infer_implicit_relations(
                tables, domain_analysis, field_classifications
            )
        
        # 3. 合并所有关系
        all_relations = explicit_relations + implicit_relations
        
        # 4. 构建关系图
        relationship_graph = self._build_relationship_graph(all_relations, tables)
        
        # 5. 识别关系模式
        patterns = self._identify_relationship_patterns(relationship_graph, tables)
        
        # 6. 生成分析报告
        report = self._generate_analysis_report(
            all_relations, relationship_graph, patterns, tables
        )
        
        logger.info(f"关系分析完成，发现 {len(all_relations)} 个关系")
        
        return report
    
    def _extract_explicit_relations(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """提取显式关系（基于外键）"""
        relations = []
        
        for table in tables:
            table_name = table["name"]
            
            for fk in table.get("foreign_keys", []):
                relation = {
                    "id": f"{table_name}.{fk['column']}->{fk['referenced_table']}.{fk['referenced_column']}",
                    "from_table": table_name,
                    "from_column": fk["column"],
                    "to_table": fk["referenced_table"],
                    "to_column": fk["referenced_column"],
                    "type": self._infer_relationship_type(table, fk),
                    "source": "foreign_key",
                    "constraint_name": fk.get("constraint_name", "")
                }
                relations.append(relation)
        
        return relations
    
    def _infer_relationship_type(
        self,
        table: Dict[str, Any],
        foreign_key: Dict[str, Any]
    ) -> str:
        """推断关系类型"""
        # 检查是否是复合主键的一部分
        primary_keys = table.get("primary_keys", [])
        fk_column = foreign_key["column"]
        
        if fk_column in primary_keys:
            # 外键是主键的一部分，可能是多对多关系的中间表
            if len(primary_keys) > 1:
                return "many-to-many"
            else:
                return "one-to-one"
        else:
            # 普通外键，通常是多对一
            return "many-to-one"
    
    def _infer_implicit_relations(
        self,
        tables: List[Dict[str, Any]],
        domain_analysis: Optional[Dict[str, Any]] = None,
        field_classifications: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """推断隐式关系"""
        relations = []
        
        # 1. 基于命名约定的关系
        naming_relations = self._find_naming_convention_relations(tables)
        relations.extend(naming_relations)
        
        # 2. 基于共同字段的关系
        if field_classifications:
            common_field_relations = self._find_common_field_relations(
                tables, field_classifications
            )
            relations.extend(common_field_relations)
        
        # 3. 基于领域知识的关系
        if domain_analysis:
            domain_relations = self._find_domain_based_relations(
                tables, domain_analysis
            )
            relations.extend(domain_relations)
        
        return relations
    
    def _find_naming_convention_relations(
        self,
        tables: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """基于命名约定查找关系"""
        relations = []
        table_names = {t["name"]: t for t in tables}
        
        for table in tables:
            table_name = table["name"]
            
            # 检查是否是连接表（如 user_role）
            if "_" in table_name:
                parts = table_name.split("_")
                if len(parts) == 2:
                    table1, table2 = parts
                    
                    # 检查对应的表是否存在
                    if self._find_similar_table(table1, table_names) and \
                       self._find_similar_table(table2, table_names):
                        # 这可能是多对多关系
                        relations.append({
                            "id": f"{table_name}-junction",
                            "from_table": table1,
                            "to_table": table2,
                            "via_table": table_name,
                            "type": "many-to-many",
                            "source": "naming_convention",
                            "confidence": 0.8
                        })
            
            # 检查列名中的表引用（如 user_id -> users 表）
            for column in table.get("columns", []):
                col_name = column["name"].lower()
                
                if col_name.endswith("_id") and not column.get("is_primary_key"):
                    # 可能是对其他表的引用
                    potential_table = col_name[:-3]  # 移除 _id
                    
                    # 查找匹配的表
                    target_table = self._find_similar_table(potential_table, table_names)
                    if target_table and target_table != table_name:
                        relations.append({
                            "id": f"{table_name}.{col_name}->{target_table}",
                            "from_table": table_name,
                            "from_column": col_name,
                            "to_table": target_table,
                            "to_column": "id",  # 假设目标是 id 列
                            "type": "many-to-one",
                            "source": "naming_convention",
                            "confidence": 0.7
                        })
        
        return relations
    
    def _find_similar_table(
        self,
        name: str,
        table_names: Dict[str, Dict[str, Any]]
    ) -> Optional[str]:
        """查找相似的表名"""
        name_lower = name.lower()
        
        # 精确匹配
        if name_lower in table_names:
            return name_lower
        
        # 复数形式
        if name_lower + "s" in table_names:
            return name_lower + "s"
        
        # 单数形式
        if name_lower.endswith("s") and name_lower[:-1] in table_names:
            return name_lower[:-1]
        
        # 特殊复数形式
        if name_lower.endswith("y"):
            plural = name_lower[:-1] + "ies"
            if plural in table_names:
                return plural
        
        return None
    
    def _find_common_field_relations(
        self,
        tables: List[Dict[str, Any]],
        field_classifications: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """基于共同字段查找关系"""
        relations = []
        
        # 查找具有相同名称和类型的字段
        field_index = defaultdict(list)
        
        for table in tables:
            table_name = table["name"]
            table_fields = field_classifications.get("classification_results", {}).get(table_name, {})
            
            for column in table.get("columns", []):
                col_name = column["name"]
                col_type = column["data_type"]
                
                # 跳过主键和已知的外键
                if column.get("is_primary_key") or column.get("is_foreign_key"):
                    continue
                
                # 索引字段
                field_key = f"{col_name}:{col_type}"
                field_index[field_key].append({
                    "table": table_name,
                    "column": col_name,
                    "classification": table_fields.get(col_name, {}).get("category", "unknown")
                })
        
        # 查找共同字段
        for field_key, occurrences in field_index.items():
            if len(occurrences) > 1:
                # 多个表有相同的字段
                for i in range(len(occurrences)):
                    for j in range(i + 1, len(occurrences)):
                        occ1, occ2 = occurrences[i], occurrences[j]
                        
                        # 如果都是标识符类型，可能存在关系
                        if "identifier" in occ1["classification"] or \
                           "identifier" in occ2["classification"]:
                            relations.append({
                                "id": f"{occ1['table']}.{occ1['column']}<->{occ2['table']}.{occ2['column']}",
                                "from_table": occ1["table"],
                                "from_column": occ1["column"],
                                "to_table": occ2["table"],
                                "to_column": occ2["column"],
                                "type": "potential",
                                "source": "common_field",
                                "confidence": 0.5
                            })
        
        return relations
    
    def _find_domain_based_relations(
        self,
        tables: List[Dict[str, Any]],
        domain_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """基于领域知识查找关系"""
        relations = []
        
        # 从领域分析中获取已推断的关系
        inferred_relations = domain_analysis.get("inferred_relationships", [])
        
        for rel in inferred_relations:
            # 转换为标准格式
            relations.append({
                "id": f"domain-{rel.get('from_entity', '')}-{rel.get('to_entity', '')}",
                "from_table": rel.get("from_entity", ""),
                "to_table": rel.get("to_entity", ""),
                "type": rel.get("type", "unknown"),
                "source": "domain_analysis",
                "via": rel.get("via", ""),
                "confidence": 0.6
            })
        
        return relations
    
    def _build_relationship_graph(
        self,
        relations: List[Dict[str, Any]],
        tables: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """构建关系图"""
        graph = {
            "nodes": {},
            "edges": [],
            "adjacency": defaultdict(set)
        }
        
        # 添加节点（表）
        for table in tables:
            table_name = table["name"]
            graph["nodes"][table_name] = {
                "name": table_name,
                "row_count": table.get("row_count", 0),
                "column_count": len(table.get("columns", [])),
                "has_primary_key": len(table.get("primary_keys", [])) > 0
            }
        
        # 添加边（关系）
        for relation in relations:
            from_table = relation.get("from_table", "")
            to_table = relation.get("to_table", "")
            
            if from_table and to_table:
                edge = {
                    "from": from_table,
                    "to": to_table,
                    "type": relation.get("type", "unknown"),
                    "label": self._create_edge_label(relation),
                    "source": relation.get("source", "unknown"),
                    "confidence": relation.get("confidence", 1.0)
                }
                graph["edges"].append(edge)
                
                # 更新邻接表
                graph["adjacency"][from_table].add(to_table)
                if relation.get("type") not in ["one-to-many", "many-to-one"]:
                    # 双向关系
                    graph["adjacency"][to_table].add(from_table)
        
        return graph
    
    def _create_edge_label(self, relation: Dict[str, Any]) -> str:
        """创建边的标签"""
        if relation.get("from_column") and relation.get("to_column"):
            return f"{relation['from_column']}->{relation['to_column']}"
        elif relation.get("via_table"):
            return f"via {relation['via_table']}"
        else:
            return relation.get("type", "related")
    
    def _identify_relationship_patterns(
        self,
        graph: Dict[str, Any],
        tables: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """识别关系模式"""
        patterns = {
            "hub_tables": [],      # 中心表（多个表与之关联）
            "junction_tables": [], # 连接表（多对多）
            "isolated_tables": [], # 孤立表（无关联）
            "chains": [],         # 关系链
            "clusters": []        # 表簇
        }
        
        adjacency = graph["adjacency"]
        
        # 识别中心表
        for table_name, connected in adjacency.items():
            if len(connected) >= 3:
                patterns["hub_tables"].append({
                    "table": table_name,
                    "connections": len(connected),
                    "connected_tables": list(connected)
                })
        
        # 识别连接表
        for table in tables:
            if self._is_junction_table(table):
                patterns["junction_tables"].append(table["name"])
        
        # 识别孤立表
        all_tables = set(t["name"] for t in tables)
        connected_tables = set(adjacency.keys()) | set().union(*adjacency.values())
        patterns["isolated_tables"] = list(all_tables - connected_tables)
        
        # 识别表簇
        patterns["clusters"] = self._find_table_clusters(adjacency)
        
        return patterns
    
    def _is_junction_table(self, table: Dict[str, Any]) -> bool:
        """判断是否是连接表"""
        # 连接表的特征：
        # 1. 主键由多个外键组成
        # 2. 表名包含下划线
        # 3. 列数较少
        
        primary_keys = table.get("primary_keys", [])
        foreign_keys = [fk["column"] for fk in table.get("foreign_keys", [])]
        
        # 检查主键是否都是外键
        if len(primary_keys) >= 2:
            pk_are_fk = all(pk in foreign_keys for pk in primary_keys)
            if pk_are_fk:
                return True
        
        # 检查表名和列数
        if "_" in table["name"] and len(table.get("columns", [])) <= 5:
            return True
        
        return False
    
    def _find_table_clusters(
        self,
        adjacency: Dict[str, Set[str]]
    ) -> List[List[str]]:
        """查找表簇（连通分量）"""
        visited = set()
        clusters = []
        
        def dfs(table: str, cluster: List[str]):
            if table in visited:
                return
            visited.add(table)
            cluster.append(table)
            
            for neighbor in adjacency.get(table, []):
                dfs(neighbor, cluster)
        
        for table in adjacency:
            if table not in visited:
                cluster = []
                dfs(table, cluster)
                if len(cluster) > 1:
                    clusters.append(sorted(cluster))
        
        return clusters
    
    def _generate_analysis_report(
        self,
        relations: List[Dict[str, Any]],
        graph: Dict[str, Any],
        patterns: Dict[str, Any],
        tables: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """生成分析报告"""
        # 关系统计
        stats = self._generate_statistics(relations, tables)
        
        # 构建报告
        report = {
            "total_relations": len(relations),
            "relationships": relations,
            "relationship_graph": {
                "nodes_count": len(graph["nodes"]),
                "edges_count": len(graph["edges"]),
                "nodes": list(graph["nodes"].values()),
                "edges": graph["edges"]
            },
            "patterns": patterns,
            "statistics": stats,
            "summary": self._generate_summary(relations, patterns, stats)
        }
        
        return report
    
    def _generate_statistics(
        self,
        relations: List[Dict[str, Any]],
        tables: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """生成统计信息"""
        stats = {
            "by_source": {},
            "by_type": {},
            "avg_relations_per_table": 0,
            "max_relations_table": None,
            "tables_with_relations": 0
        }
        
        # 按来源统计
        for rel in relations:
            source = rel.get("source", "unknown")
            stats["by_source"][source] = stats["by_source"].get(source, 0) + 1
        
        # 按类型统计
        for rel in relations:
            rel_type = rel.get("type", "unknown")
            stats["by_type"][rel_type] = stats["by_type"].get(rel_type, 0) + 1
        
        # 计算每个表的关系数
        table_relation_count = defaultdict(int)
        for rel in relations:
            if rel.get("from_table"):
                table_relation_count[rel["from_table"]] += 1
            if rel.get("to_table"):
                table_relation_count[rel["to_table"]] += 1
        
        # 统计
        if table_relation_count:
            stats["tables_with_relations"] = len(table_relation_count)
            stats["avg_relations_per_table"] = sum(table_relation_count.values()) / len(table_relation_count)
            max_table = max(table_relation_count.items(), key=lambda x: x[1])
            stats["max_relations_table"] = {
                "table": max_table[0],
                "count": max_table[1]
            }
        
        return stats
    
    def _generate_summary(
        self,
        relations: List[Dict[str, Any]],
        patterns: Dict[str, Any],
        stats: Dict[str, Any]
    ) -> str:
        """生成摘要"""
        parts = []
        
        # 关系总数
        parts.append(f"共识别出 {len(relations)} 个表间关系")
        
        # 关系来源
        by_source = stats.get("by_source", {})
        if by_source:
            source_str = "、".join([
                f"{source}({count}个)" 
                for source, count in by_source.items()
            ])
            parts.append(f"来源：{source_str}")
        
        # 关键模式
        if patterns.get("hub_tables"):
            hub_names = [h["table"] for h in patterns["hub_tables"][:3]]
            parts.append(f"中心表：{', '.join(hub_names)}")
        
        if patterns.get("junction_tables"):
            parts.append(f"发现 {len(patterns['junction_tables'])} 个多对多连接表")
        
        if patterns.get("isolated_tables"):
            parts.append(f"有 {len(patterns['isolated_tables'])} 个独立表无关联")
        
        # 表簇
        if patterns.get("clusters"):
            parts.append(f"表形成了 {len(patterns['clusters'])} 个关联组")
        
        return "。".join(parts) + "。"