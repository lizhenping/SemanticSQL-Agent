"""
ER关系分析工具 - 分析数据库表之间的实体关系
"""

from typing import Dict, Any, List, Optional, Set, Tuple
import networkx as nx

from tools.base_tool import BaseTool, ToolParameter
from models.schemas import TableRelationship


class ERAnalysisTool(BaseTool):
    """实体关系分析工具"""
    
    @property
    def name(self) -> str:
        return "er_analysis"
    
    @property
    def description(self) -> str:
        return "分析数据库表之间的实体关系，构建ER图"
    
    @property
    def category(self) -> str:
        return "analysis"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="schema_info",
                type="object",
                description="数据库结构信息",
                required=True
            ),
            ToolParameter(
                name="analyze_implicit",
                type="boolean",
                description="是否分析隐式关系",
                required=False,
                default=True
            ),
            ToolParameter(
                name="depth",
                type="integer",
                description="关系分析深度",
                required=False,
                default=2
            )
        ]
    
    def _execute(self, schema_info: Dict[str, Any], analyze_implicit: bool = True,
                 depth: int = 2) -> Dict[str, Any]:
        """
        执行ER关系分析
        
        Returns:
            关系分析结果
        """
        result = {
            "entities": {},
            "relationships": [],
            "relationship_graph": {},
            "entity_clusters": [],
            "statistics": {},
            "recommendations": []
        }
        
        # 识别实体
        result["entities"] = self._identify_entities(schema_info)
        
        # 提取显式关系（外键）
        explicit_relationships = self._extract_explicit_relationships(schema_info)
        result["relationships"].extend(explicit_relationships)
        
        # 分析隐式关系
        if analyze_implicit:
            implicit_relationships = self._analyze_implicit_relationships(
                schema_info, explicit_relationships
            )
            result["relationships"].extend(implicit_relationships)
        
        # 构建关系图
        result["relationship_graph"] = self._build_relationship_graph(
            result["relationships"], depth
        )
        
        # 识别实体簇
        result["entity_clusters"] = self._identify_entity_clusters(
            result["entities"], result["relationships"]
        )
        
        # 计算统计信息
        result["statistics"] = self._calculate_statistics(
            result["entities"], result["relationships"]
        )
        
        # 生成建议
        result["recommendations"] = self._generate_recommendations(
            result["entities"], result["relationships"], schema_info
        )
        
        return result
    
    def _identify_entities(self, schema_info: Dict[str, Any]) -> Dict[str, Dict]:
        """识别实体表"""
        entities = {}
        tables = schema_info.get("tables", {})
        
        for table_name, table_info in tables.items():
            entity = {
                "name": table_name,
                "type": self._classify_entity_type(table_name, table_info),
                "attributes": [],
                "key_attributes": [],
                "importance": self._calculate_entity_importance(table_info)
            }
            
            # 识别属性
            for column in table_info.get("columns", []):
                attr = {
                    "name": column.get("name"),
                    "type": column.get("data_type"),
                    "is_key": column.get("is_primary", False),
                    "is_foreign": column.get("is_foreign", False)
                }
                entity["attributes"].append(attr)
                
                if attr["is_key"]:
                    entity["key_attributes"].append(attr["name"])
            
            entities[table_name] = entity
        
        return entities
    
    def _classify_entity_type(self, table_name: str, table_info: Dict) -> str:
        """分类实体类型"""
        table_lower = table_name.lower()
        
        # 根据表名模式分类
        if any(word in table_lower for word in ["user", "customer", "member", "account"]):
            return "actor"
        elif any(word in table_lower for word in ["order", "transaction", "payment", "invoice"]):
            return "transaction"
        elif any(word in table_lower for word in ["product", "item", "goods", "service"]):
            return "resource"
        elif any(word in table_lower for word in ["category", "type", "status", "config"]):
            return "reference"
        elif any(word in table_lower for word in ["log", "history", "audit", "track"]):
            return "audit"
        elif "_" in table_name and any(word in table_lower for word in ["map", "rel", "link"]):
            return "association"
        else:
            return "entity"
    
    def _calculate_entity_importance(self, table_info: Dict) -> float:
        """计算实体重要性分数"""
        score = 0.0
        
        # 有主键的表更重要
        if any(col.get("is_primary") for col in table_info.get("columns", [])):
            score += 2.0
        
        # 被其他表引用的表更重要
        foreign_key_count = len(table_info.get("foreign_keys", []))
        score += foreign_key_count * 0.5
        
        # 字段越多可能越重要
        column_count = len(table_info.get("columns", []))
        score += min(column_count * 0.1, 2.0)
        
        # 有索引的表更重要
        if table_info.get("indexes"):
            score += 1.0
        
        return min(score, 10.0)
    
    def _extract_explicit_relationships(self, schema_info: Dict[str, Any]) -> List[Dict]:
        """提取显式关系（基于外键）"""
        relationships = []
        tables = schema_info.get("tables", {})
        
        for table_name, table_info in tables.items():
            for fk in table_info.get("foreign_keys", []):
                relationship = {
                    "from_entity": table_name,
                    "to_entity": fk.get("referenced_table"),
                    "type": "foreign_key",
                    "cardinality": self._determine_cardinality(table_name, fk, tables),
                    "attributes": {
                        "from_column": fk.get("column"),
                        "to_column": fk.get("referenced_column")
                    },
                    "confidence": 1.0  # 显式关系置信度为1
                }
                relationships.append(relationship)
        
        return relationships
    
    def _analyze_implicit_relationships(self, schema_info: Dict[str, Any],
                                       explicit_relationships: List[Dict]) -> List[Dict]:
        """分析隐式关系（基于命名模式和数据类型）"""
        implicit_relationships = []
        tables = schema_info.get("tables", {})
        
        # 已有的显式关系对
        explicit_pairs = set(
            (r["from_entity"], r["to_entity"]) 
            for r in explicit_relationships
        )
        
        # 分析每对表
        table_names = list(tables.keys())
        for i, table1 in enumerate(table_names):
            for table2 in table_names[i+1:]:
                # 跳过已有显式关系的表对
                if (table1, table2) in explicit_pairs or (table2, table1) in explicit_pairs:
                    continue
                
                # 检查命名模式
                relationship = self._check_naming_pattern_relationship(
                    table1, table2, tables[table1], tables[table2]
                )
                
                if relationship:
                    implicit_relationships.append(relationship)
        
        return implicit_relationships
    
    def _check_naming_pattern_relationship(self, table1: str, table2: str,
                                          table1_info: Dict, table2_info: Dict) -> Optional[Dict]:
        """检查基于命名模式的关系"""
        # 检查是否有相同的ID字段
        table1_columns = {col["name"] for col in table1_info.get("columns", [])}
        table2_columns = {col["name"] for col in table2_info.get("columns", [])}
        
        # 查找可能的关联字段
        potential_links = []
        
        # 模式1：table1_id 在 table2 中
        if f"{table1}_id" in table2_columns:
            potential_links.append({
                "from": table2,
                "to": table1,
                "column": f"{table1}_id",
                "pattern": "foreign_key_naming"
            })
        
        # 模式2：table2_id 在 table1 中
        if f"{table2}_id" in table1_columns:
            potential_links.append({
                "from": table1,
                "to": table2,
                "column": f"{table2}_id",
                "pattern": "foreign_key_naming"
            })
        
        # 模式3：关联表（如 user_role 关联 user 和 role）
        if "_" in table1 and table2 in table1:
            potential_links.append({
                "from": table1,
                "to": table2,
                "column": None,
                "pattern": "association_table"
            })
        
        if potential_links:
            link = potential_links[0]
            return {
                "from_entity": link["from"],
                "to_entity": link["to"],
                "type": "implicit",
                "cardinality": "one-to-many",  # 默认
                "attributes": {
                    "column": link["column"],
                    "pattern": link["pattern"]
                },
                "confidence": 0.7  # 隐式关系置信度较低
            }
        
        return None
    
    def _determine_cardinality(self, from_table: str, fk: Dict, tables: Dict) -> str:
        """判断关系的基数"""
        # 简化的基数判断逻辑
        # 如果外键也是主键，通常是一对一
        from_table_info = tables.get(from_table, {})
        fk_column = fk.get("column")
        
        for col in from_table_info.get("columns", []):
            if col.get("name") == fk_column and col.get("is_primary"):
                return "one-to-one"
        
        # 检查是否为多对多（通过关联表）
        if "_" in from_table:
            # 如果表名包含两个其他表名，可能是多对多关联表
            parts = from_table.split("_")
            if len(parts) >= 2 and all(p in tables for p in parts):
                return "many-to-many"
        
        # 默认一对多
        return "one-to-many"
    
    def _build_relationship_graph(self, relationships: List[Dict], depth: int) -> Dict:
        """构建关系图"""
        # 使用NetworkX构建图
        G = nx.DiGraph()
        
        # 添加边
        for rel in relationships:
            G.add_edge(
                rel["from_entity"],
                rel["to_entity"],
                type=rel["type"],
                cardinality=rel["cardinality"],
                confidence=rel.get("confidence", 1.0)
            )
        
        # 构建邻接表表示
        graph = {}
        for node in G.nodes():
            graph[node] = {
                "connections": list(G.neighbors(node)),
                "in_degree": G.in_degree(node),
                "out_degree": G.out_degree(node),
                "paths": self._find_paths_from_node(G, node, depth)
            }
        
        return graph
    
    def _find_paths_from_node(self, G: nx.DiGraph, start: str, max_depth: int) -> List[List[str]]:
        """从节点查找所有路径"""
        paths = []
        
        def dfs(node, path, depth):
            if depth >= max_depth:
                return
            
            for neighbor in G.neighbors(node):
                if neighbor not in path:  # 避免循环
                    new_path = path + [neighbor]
                    paths.append(new_path)
                    dfs(neighbor, new_path, depth + 1)
        
        dfs(start, [start], 0)
        return paths[:10]  # 限制返回的路径数量
    
    def _identify_entity_clusters(self, entities: Dict, relationships: List[Dict]) -> List[Dict]:
        """识别实体簇（紧密关联的实体组）"""
        # 使用NetworkX进行社区检测
        G = nx.Graph()
        
        # 添加节点和边
        for entity in entities:
            G.add_node(entity)
        
        for rel in relationships:
            G.add_edge(rel["from_entity"], rel["to_entity"])
        
        # 找连通分量
        clusters = []
        for component in nx.connected_components(G):
            cluster = {
                "entities": list(component),
                "size": len(component),
                "type": self._classify_cluster_type(component, entities),
                "core_entity": self._find_core_entity(component, entities, relationships)
            }
            clusters.append(cluster)
        
        return sorted(clusters, key=lambda x: x["size"], reverse=True)
    
    def _classify_cluster_type(self, component: Set[str], entities: Dict) -> str:
        """分类实体簇类型"""
        entity_types = [entities[e]["type"] for e in component if e in entities]
        
        if "transaction" in entity_types:
            return "transactional"
        elif "actor" in entity_types:
            return "user-centric"
        elif "resource" in entity_types:
            return "resource-centric"
        else:
            return "general"
    
    def _find_core_entity(self, component: Set[str], entities: Dict,
                          relationships: List[Dict]) -> str:
        """找到簇中的核心实体"""
        # 计算每个实体的连接数
        connection_counts = {e: 0 for e in component}
        
        for rel in relationships:
            if rel["from_entity"] in component:
                connection_counts[rel["from_entity"]] += 1
            if rel["to_entity"] in component:
                connection_counts[rel["to_entity"]] += 1
        
        # 返回连接最多的实体
        return max(connection_counts, key=connection_counts.get)
    
    def _calculate_statistics(self, entities: Dict, relationships: List[Dict]) -> Dict:
        """计算统计信息"""
        stats = {
            "total_entities": len(entities),
            "total_relationships": len(relationships),
            "entity_type_distribution": {},
            "relationship_type_distribution": {},
            "avg_connections_per_entity": 0,
            "max_connections": 0,
            "isolated_entities": []
        }
        
        # 实体类型分布
        for entity in entities.values():
            entity_type = entity["type"]
            stats["entity_type_distribution"][entity_type] = \
                stats["entity_type_distribution"].get(entity_type, 0) + 1
        
        # 关系类型分布
        for rel in relationships:
            rel_type = rel["type"]
            stats["relationship_type_distribution"][rel_type] = \
                stats["relationship_type_distribution"].get(rel_type, 0) + 1
        
        # 连接统计
        connection_counts = {e: 0 for e in entities}
        for rel in relationships:
            connection_counts[rel["from_entity"]] = connection_counts.get(rel["from_entity"], 0) + 1
            connection_counts[rel["to_entity"]] = connection_counts.get(rel["to_entity"], 0) + 1
        
        if connection_counts:
            stats["avg_connections_per_entity"] = sum(connection_counts.values()) / len(connection_counts)
            stats["max_connections"] = max(connection_counts.values())
            stats["isolated_entities"] = [e for e, c in connection_counts.items() if c == 0]
        
        return stats
    
    def _generate_recommendations(self, entities: Dict, relationships: List[Dict],
                                 schema_info: Dict) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        # 检查孤立实体
        connected_entities = set()
        for rel in relationships:
            connected_entities.add(rel["from_entity"])
            connected_entities.add(rel["to_entity"])
        
        isolated = set(entities.keys()) - connected_entities
        if isolated:
            recommendations.append(
                f"发现{len(isolated)}个孤立实体：{', '.join(list(isolated)[:3])}，建议检查是否缺少关系定义"
            )
        
        # 检查缺少外键的潜在关系
        implicit_count = sum(1 for r in relationships if r["type"] == "implicit")
        if implicit_count > 0:
            recommendations.append(
                f"发现{implicit_count}个潜在的隐式关系，建议添加外键约束"
            )
        
        # 检查多对多关系
        many_to_many = [r for r in relationships if r.get("cardinality") == "many-to-many"]
        if not many_to_many and len(entities) > 5:
            recommendations.append(
                "未发现多对多关系，如果业务需要，考虑添加关联表"
            )
        
        # 检查实体簇
        if len(entities) > 10:
            recommendations.append(
                "数据库包含较多实体，建议按业务模块进行分层设计"
            )
        
        return recommendations