"""实体关系分析工具

参考 nl2sql_pipeline 的 er_analysis_pipeline 实现，
分析数据库中的实体关系。
"""

from tools.base import BaseSemanticSQLTool
from typing import Dict, Any, List, Optional, Set, Tuple
from models.analysis_models import (
    ERAnalysisInput,
    ERAnalysisOutput,
    Relationship,
    RelationshipGraph,
    RelationshipPattern,
    ERAnalysisReport,
    RelationshipType,
    RelationSource,
    SchemaExtractionOutput,
    DomainAnalysisOutput,
    FieldClassificationOutput,
    TableDetail
)
from utils.output_parsers import (
    create_structured_output_parser,
    get_pydantic_format_instruction
)
import logging
import json

logger = logging.getLogger(__name__)


class ERAnalysisTool(BaseSemanticSQLTool):
    """实体关系分析工具
    
    分析表之间的实体关系，包括：
    - 基于外键的显式关系
    - 基于命名规则的隐式关系
    - 基于数据分析的潜在关系
    - 关系类型推断（一对一、一对多、多对多）
    """
    
    name = "analyze_entity_relationships"
    description = (
        "分析数据库中的实体关系，识别表之间的关联。"
        "包括外键关系、命名约定关系和数据推断关系。"
        "输出关系图谱和关系类型（一对一、一对多、多对多）。"
    )
    args_schema = ERAnalysisInput
    
    def execute(
        self,
        schema_info: SchemaExtractionOutput,
        domain_knowledge: Optional[DomainAnalysisOutput] = None,
        field_classifications: Optional[FieldClassificationOutput] = None,
        analyze_implicit: bool = True
    ) -> ERAnalysisOutput:
        """执行实体关系分析"""
        logger.info("开始实体关系分析")
        
        tables = schema_info.tables
        if not tables:
            return ERAnalysisOutput(
                success=False,
                relationships={},
                relationship_graph=RelationshipGraph(
                    nodes=[],
                    edges=[],
                    node_degrees={},
                    core_nodes=[]
                ),
                patterns=RelationshipPattern(),
                report=ERAnalysisReport(
                    summary={},
                    key_findings=[],
                    recommendations=[]
                ),
                statistics={},
                error="未提供表信息"
            )
        
        # 分析各种类型的关系
        relationships = {
            "explicit": [],    # 显式关系（外键）
            "implicit": [],    # 隐式关系
            "inferred": []     # 推断关系
        }
        
        # 1. 提取显式外键关系
        explicit_relations = self._extract_explicit_relations(tables)
        relationships["explicit"] = explicit_relations
        logger.info(f"发现 {len(explicit_relations)} 个显式外键关系")
        
        # 2. 分析隐式关系
        if analyze_implicit:
            implicit_relations = self._analyze_implicit_relations(
                tables,
                explicit_relations,
                field_classifications
            )
            relationships["implicit"] = implicit_relations
            logger.info(f"发现 {len(implicit_relations)} 个隐式关系")
        
        # 3. 使用 LLM 推断更深层的关系
        if self.llm:
            inferred_relations = self._infer_relations_with_llm(
                tables,
                relationships,
                domain_knowledge
            )
            relationships["inferred"] = inferred_relations
            logger.info(f"推断出 {len(inferred_relations)} 个潜在关系")
        
        # 4. 生成关系图谱
        relationship_graph = self._build_relationship_graph(relationships)
        
        # 5. 识别关系模式
        patterns = self._identify_relationship_patterns(
            relationship_graph,
            tables
        )
        
        # 6. 生成分析报告
        analysis_report = self._generate_analysis_report(
            relationships,
            relationship_graph,
            patterns,
            tables
        )
        
        return ERAnalysisOutput(
            success=True,
            relationships=relationships,
            relationship_graph=relationship_graph,
            patterns=patterns,
            report=analysis_report,
            statistics=self._generate_statistics(relationships)
        )
    
    def _extract_explicit_relations(self, tables: List[TableDetail]) -> List[Relationship]:
        """提取显式外键关系"""
        relations = []
        
        for table in tables:
            for fk in table.foreign_keys:
                relation = Relationship(
                    from_table=table.name,
                    from_column=fk.column,
                    to_table=fk.referenced_table,
                    to_column=fk.referenced_column,
                    type=RelationSource.FOREIGN_KEY,
                    relationship_type=self._infer_relationship_type(
                        table.name,
                        fk.column,
                        fk.referenced_table,
                        fk.referenced_column,
                        tables
                    ),
                    constraint_name=fk.constraint_name
                )
                relations.append(relation)
        
        return relations
    
    def _infer_relationship_type(
        self,
        from_table: str,
        from_column: str,
        to_table: str,
        to_column: str,
        tables: List[TableDetail]
    ) -> RelationshipType:
        """推断关系类型（一对一、一对多、多对多）"""
        # 获取 from_table 的信息
        from_table_info = next((t for t in tables if t.name == from_table), None)
        if not from_table_info:
            return RelationshipType.UNKNOWN
        
        # 检查 from_column 是否是主键
        is_from_pk = from_column in from_table_info.primary_keys
        
        # 检查是否是连接表（多对多）
        if self._is_junction_table(from_table_info):
            return RelationshipType.MANY_TO_MANY
        
        # 如果外键同时是主键，通常是一对一
        if is_from_pk:
            return RelationshipType.ONE_TO_ONE
        
        # 默认是一对多
        return RelationshipType.ONE_TO_MANY
    
    def _is_junction_table(self, table_info: TableDetail) -> bool:
        """判断是否是连接表（用于多对多关系）"""
        # 连接表的特征：
        # 1. 表名包含下划线（如 user_role）
        # 2. 主键由多个外键组成
        # 3. 除了外键和少量元数据字段外，没有其他业务字段
        
        table_name = table_info.name
        
        # 检查表名
        if "_" not in table_name or table_name.count("_") != 1:
            return False
        
        # 检查外键数量
        if len(table_info.foreign_keys) < 2:
            return False
        
        # 检查主键
        if len(table_info.primary_keys) < 2:
            return False
        
        # 检查列数（连接表通常列数较少）
        non_meta_columns = [
            col for col in table_info.columns
            if not any(kw in col.name.lower() for kw in ["created", "updated", "id"])
        ]
        
        if len(non_meta_columns) > len(table_info.foreign_keys) + 2:
            return False
        
        return True
    
    def _analyze_implicit_relations(
        self,
        tables: List[Dict[str, Any]],
        explicit_relations: List[Dict[str, Any]],
        field_classifications: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """分析隐式关系"""
        implicit_relations = []
        
        # 已知的显式关系对
        explicit_pairs = set()
        for rel in explicit_relations:
            explicit_pairs.add((rel["from_table"], rel["to_table"]))
            explicit_pairs.add((rel["to_table"], rel["from_table"]))
        
        # 1. 基于命名约定的关系
        naming_relations = self._find_naming_convention_relations(
            tables,
            explicit_pairs
        )
        implicit_relations.extend(naming_relations)
        
        # 2. 基于共同字段的关系
        common_field_relations = self._find_common_field_relations(
            tables,
            explicit_pairs,
            field_classifications
        )
        implicit_relations.extend(common_field_relations)
        
        # 3. 基于数据分析的关系
        if len(tables) <= 20:  # 限制表数量，避免过多查询
            data_relations = self._analyze_data_relations(
                tables,
                explicit_pairs
            )
            implicit_relations.extend(data_relations)
        
        return implicit_relations
    
    def _find_naming_convention_relations(
        self,
        tables: List[Dict[str, Any]],
        explicit_pairs: Set[Tuple[str, str]]
    ) -> List[Dict[str, Any]]:
        """基于命名约定查找关系"""
        relations = []
        table_names = [t["name"] for t in tables]
        
        for table in tables:
            table_name = table["name"]
            
            # 查找表名中的其他表名引用
            for other_table in table_names:
                if other_table == table_name:
                    continue
                
                # 跳过已有显式关系
                if (table_name, other_table) in explicit_pairs:
                    continue
                
                # 模式1: table1_table2 (连接表)
                if "_" in table_name:
                    parts = table_name.split("_")
                    if len(parts) == 2 and all(p in table_names for p in parts):
                        if other_table in parts:
                            relations.append({
                                "from_table": table_name,
                                "to_table": other_table,
                                "type": "naming_convention",
                                "pattern": "junction_table",
                                "relationship_type": "many-to-many",
                                "confidence": 0.8
                            })
                
                # 模式2: 列名包含表名（如 user_id 引用 user 表）
                for col in table.get("columns", []):
                    col_name = col["name"].lower()
                    other_table_lower = other_table.lower()
                    
                    if (f"{other_table_lower}_id" == col_name or 
                        f"{other_table_lower}id" == col_name):
                        relations.append({
                            "from_table": table_name,
                            "from_column": col["name"],
                            "to_table": other_table,
                            "to_column": "id",  # 假设引用 id 列
                            "type": "naming_convention",
                            "pattern": "foreign_key_naming",
                            "relationship_type": "many-to-one",
                            "confidence": 0.7
                        })
        
        return relations
    
    def _find_common_field_relations(
        self,
        tables: List[Dict[str, Any]],
        explicit_pairs: Set[Tuple[str, str]],
        field_classifications: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """基于共同字段查找关系"""
        relations = []
        
        # 构建字段索引
        field_index = {}  # field_name -> [(table, column)]
        
        for table in tables:
            for col in table.get("columns", []):
                col_name = col["name"].lower()
                if col_name not in field_index:
                    field_index[col_name] = []
                field_index[col_name].append((table["name"], col["name"]))
        
        # 查找共同的标识符字段
        for field_name, occurrences in field_index.items():
            if len(occurrences) < 2:
                continue
            
            # 检查是否是标识符类型
            is_identifier = False
            if field_classifications:
                for table, col in occurrences:
                    field_key = f"{table}.{col}"
                    if field_key in field_classifications:
                        classification = field_classifications[field_key]
                        if classification.get("type") == "identifier":
                            is_identifier = True
                            break
            else:
                # 基于名称判断
                is_identifier = any(kw in field_name for kw in ["id", "code", "no"])
            
            if is_identifier:
                # 创建关系
                for i in range(len(occurrences)):
                    for j in range(i + 1, len(occurrences)):
                        table1, col1 = occurrences[i]
                        table2, col2 = occurrences[j]
                        
                        if (table1, table2) not in explicit_pairs:
                            relations.append({
                                "from_table": table1,
                                "from_column": col1,
                                "to_table": table2,
                                "to_column": col2,
                                "type": "common_field",
                                "field_name": field_name,
                                "relationship_type": "unknown",
                                "confidence": 0.5
                            })
        
        return relations
    
    def _analyze_data_relations(
        self,
        tables: List[Dict[str, Any]],
        explicit_pairs: Set[Tuple[str, str]]
    ) -> List[Dict[str, Any]]:
        """基于数据分析查找关系"""
        relations = []
        
        # 只分析小表之间的潜在关系
        small_tables = [t for t in tables if t.get("row_count", 0) < 10000]
        
        for i, table1 in enumerate(small_tables):
            for table2 in small_tables[i+1:]:
                if (table1["name"], table2["name"]) in explicit_pairs:
                    continue
                
                # 查找可能的关联字段
                potential_relations = self._find_data_correlations(
                    table1,
                    table2
                )
                
                relations.extend(potential_relations)
        
        return relations
    
    def _find_data_correlations(
        self,
        table1: Dict[str, Any],
        table2: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """查找两个表之间的数据关联"""
        relations = []
        
        # 获取标识符类型的列
        id_cols1 = [
            col for col in table1.get("columns", [])
            if any(kw in col["name"].lower() for kw in ["id", "code", "no"])
        ]
        
        id_cols2 = [
            col for col in table2.get("columns", [])
            if any(kw in col["name"].lower() for kw in ["id", "code", "no"])
        ]
        
        # 检查数据重叠
        for col1 in id_cols1:
            for col2 in id_cols2:
                overlap = self._check_data_overlap(
                    table1["name"],
                    col1["name"],
                    table2["name"],
                    col2["name"]
                )
                
                if overlap > 0.1:  # 至少10%的数据重叠
                    relations.append({
                        "from_table": table1["name"],
                        "from_column": col1["name"],
                        "to_table": table2["name"],
                        "to_column": col2["name"],
                        "type": "data_correlation",
                        "overlap_ratio": overlap,
                        "relationship_type": "unknown",
                        "confidence": min(overlap, 0.8)
                    })
        
        return relations
    
    def _check_data_overlap(
        self,
        table1: str,
        col1: str,
        table2: str,
        col2: str
    ) -> float:
        """检查两个列的数据重叠率"""
        try:
            # 获取两列的唯一值
            sql1 = f"SELECT DISTINCT `{col1}` FROM `{table1}` LIMIT 1000"
            sql2 = f"SELECT DISTINCT `{col2}` FROM `{table2}` LIMIT 1000"
            
            result1 = self.db.run(sql1)
            result2 = self.db.run(sql2)
            
            # 简单解析结果
            values1 = set()
            values2 = set()
            
            # 这里需要更好的结果解析
            # 暂时返回0，避免过多查询
            return 0.0
            
        except Exception as e:
            logger.debug(f"检查数据重叠失败: {e}")
            return 0.0
    
    def _infer_relations_with_llm(
        self,
        tables: List[Dict[str, Any]],
        existing_relations: Dict[str, List[Dict[str, Any]]],
        domain_knowledge: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """使用 LLM 推断更深层的关系"""
        # 准备上下文
        context = self._prepare_llm_context(tables, existing_relations, domain_knowledge)
        
        # 构建提示词
        prompt = self._build_inference_prompt(context)
        
        try:
            response = self.llm.invoke(prompt)
            inferred_relations = self._parse_llm_inference(response.content)
            return inferred_relations
        except Exception as e:
            logger.error(f"LLM 推断关系失败: {e}")
            return []
    
    def _prepare_llm_context(
        self,
        tables: List[Dict[str, Any]],
        existing_relations: Dict[str, List[Dict[str, Any]]],
        domain_knowledge: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """准备 LLM 上下文"""
        context = {
            "table_count": len(tables),
            "table_summaries": [],
            "existing_relations_count": sum(len(rels) for rels in existing_relations.values()),
            "domain": domain_knowledge.get("domain", "未知") if domain_knowledge else "未知"
        }
        
        # 表摘要
        for table in tables[:20]:  # 限制数量
            summary = {
                "name": table["name"],
                "columns": len(table.get("columns", [])),
                "primary_keys": table.get("primary_keys", []),
                "has_foreign_keys": len(table.get("foreign_keys", [])) > 0
            }
            context["table_summaries"].append(summary)
        
        return context
    
    def _build_inference_prompt(self, context: Dict[str, Any]) -> str:
        """构建推断提示词"""
        table_list = "\n".join(
            f"- {t['name']} ({t['columns']} 列)"
            for t in context["table_summaries"]
        )
        
        prompt = f"""基于以下数据库信息，推断可能存在但未通过外键定义的实体关系。

## 数据库信息
- 业务领域: {context['domain']}
- 表数量: {context['table_count']}
- 已知关系数: {context['existing_relations_count']}

## 主要表
{table_list}

## 任务
请推断可能存在的业务关系，特别是：
1. 业务流程中的隐含关系
2. 通过中间表的间接关系
3. 基于业务逻辑的关联

## 输出格式
返回 JSON 格式的推断关系列表：
[
    {{
        "from_table": "表1",
        "to_table": "表2",
        "relationship_type": "关系类型(one-to-one/one-to-many/many-to-many)",
        "description": "关系描述",
        "confidence": 0.7
    }},
    ...
]

只返回最可能的 5-10 个关系。"""
        
        return prompt
    
    def _parse_llm_inference(self, response: str) -> List[Dict[str, Any]]:
        """解析 LLM 推断结果"""
        inferred_relations = []
        
        try:
            # 查找 JSON 数组
            import re
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                relations = json.loads(json_match.group())
                
                for rel in relations:
                    if isinstance(rel, dict) and "from_table" in rel and "to_table" in rel:
                        inferred_relations.append({
                            "from_table": rel["from_table"],
                            "to_table": rel["to_table"],
                            "type": "llm_inferred",
                            "relationship_type": rel.get("relationship_type", "unknown"),
                            "description": rel.get("description", ""),
                            "confidence": rel.get("confidence", 0.5)
                        })
        except Exception as e:
            logger.error(f"解析 LLM 推断结果失败: {e}")
        
        return inferred_relations
    
    def _build_relationship_graph(
        self,
        relationships: Dict[str, List[Relationship]]
    ) -> RelationshipGraph:
        """构建关系图谱"""
        # 节点（表）
        nodes = set()
        edges = []
        
        # 处理所有关系
        for rel_type, relations in relationships.items():
            for rel in relations:
                from_table = rel.from_table
                to_table = rel.to_table
                
                nodes.add(from_table)
                if to_table:
                    nodes.add(to_table)
                    
                    edge = {
                        "from": from_table,
                        "to": to_table,
                        "type": rel_type,
                        "relationship_type": rel.relationship_type.value,
                        "label": self._create_edge_label(rel),
                        "confidence": rel.confidence
                    }
                    edges.append(edge)
        
        # 计算每个节点的连接度
        node_degrees = {node: 0 for node in nodes}
        for edge in edges:
            node_degrees[edge["from"]] += 1
            node_degrees[edge["to"]] += 1
        
        # 识别核心节点（连接度高的）
        core_nodes = [
            node for node, degree in node_degrees.items()
            if degree >= 3
        ]
        
        return RelationshipGraph(
            nodes=list(nodes),
            edges=edges,
            node_degrees=node_degrees,
            core_nodes=core_nodes
        )
    
    def _create_edge_label(self, relation: Relationship) -> str:
        """创建边的标签"""
        if relation.from_column and relation.to_column:
            return f"{relation.from_column} -> {relation.to_column}"
        elif hasattr(relation, "description") and relation.description:
            return relation.description
        else:
            return relation.relationship_type.value
    
    def _identify_relationship_patterns(
        self,
        graph: RelationshipGraph,
        tables: List[TableDetail]
    ) -> RelationshipPattern:
        """识别关系模式"""
        patterns = {
            "star_schema": None,
            "snowflake_schema": None,
            "junction_tables": [],
            "isolated_tables": [],
            "table_clusters": []
        }
        
        # 识别星型模式（一个中心表被多个维度表引用）
        for node in graph.core_nodes:
            incoming_edges = [
                e for e in graph.edges
                if e["to"] == node and e["relationship_type"] == "many-to-one"
            ]
            if len(incoming_edges) >= 3:
                patterns["star_schema"] = {
                    "fact_table": node,
                    "dimension_tables": [e["from"] for e in incoming_edges]
                }
                break
        
        # 识别连接表
        for table in tables:
            if self._is_junction_table(table):
                patterns["junction_tables"].append(table.name)
        
        # 识别孤立表
        connected_tables = set()
        for edge in graph.edges:
            connected_tables.add(edge["from"])
            connected_tables.add(edge["to"])
        
        patterns["isolated_tables"] = [
            t.name for t in tables
            if t.name not in connected_tables
        ]
        
        # 识别表簇（强连接的表组）
        patterns["table_clusters"] = self._find_table_clusters(graph)
        
        return RelationshipPattern(**patterns)
    
    def _find_table_clusters(self, graph: RelationshipGraph) -> List[Dict[str, Any]]:
        """查找表簇（强连接的表组）"""
        # 简单的连通分量算法
        adjacency = {}
        for node in graph.nodes:
            adjacency[node] = set()
        
        for edge in graph.edges:
            adjacency[edge["from"]].add(edge["to"])
            adjacency[edge["to"]].add(edge["from"])
        
        visited = set()
        clusters = []
        
        for node in graph.nodes:
            if node not in visited:
                cluster = []
                stack = [node]
                
                while stack:
                    current = stack.pop()
                    if current not in visited:
                        visited.add(current)
                        cluster.append(current)
                        stack.extend(adjacency[current] - visited)
                
                if len(cluster) > 1:
                    clusters.append({
                        "tables": cluster,
                        "size": len(cluster)
                    })
        
        return sorted(clusters, key=lambda x: x["size"], reverse=True)
    
    def _generate_analysis_report(
        self,
        relationships: Dict[str, List[Relationship]],
        graph: RelationshipGraph,
        patterns: RelationshipPattern,
        tables: List[TableDetail]
    ) -> ERAnalysisReport:
        """生成分析报告"""
        report = {
            "summary": {
                "total_tables": len(tables),
                "total_relationships": sum(len(rels) for rels in relationships.values()),
                "explicit_relationships": len(relationships["explicit"]),
                "implicit_relationships": len(relationships["implicit"]),
                "inferred_relationships": len(relationships["inferred"]),
                "isolated_tables": len(patterns["isolated_tables"]),
                "junction_tables": len(patterns["junction_tables"])
            },
            "key_findings": [],
            "recommendations": []
        }
        
        # 关键发现
        if patterns.star_schema:
            report["key_findings"].append(
                f"发现星型模式：{patterns.star_schema['fact_table']} 作为事实表"
            )
        
        if patterns.junction_tables:
            report["key_findings"].append(
                f"发现 {len(patterns.junction_tables)} 个多对多关系连接表"
            )
        
        if graph.core_nodes:
            report["key_findings"].append(
                f"核心实体表：{', '.join(graph.core_nodes[:5])}"
            )
        
        if patterns.isolated_tables:
            report["key_findings"].append(
                f"发现 {len(patterns.isolated_tables)} 个孤立表（无关联）"
            )
        
        # 建议
        if len(relationships["implicit"]) > len(relationships["explicit"]):
            report["recommendations"].append(
                "建议检查隐式关系，考虑添加外键约束以确保数据完整性"
            )
        
        if patterns.isolated_tables:
            report["recommendations"].append(
                f"建议检查孤立表 {patterns.isolated_tables[:3]} 的用途"
            )
        
        if len(tables) > 50 and not patterns.table_clusters:
            report["recommendations"].append(
                "数据库表较多但缺乏明显的模块化，建议考虑模式重构"
            )
        
        return ERAnalysisReport(**report)
    
    def _generate_statistics(self, relationships: Dict[str, List[Relationship]]) -> Dict[str, Any]:
        """生成统计信息"""
        stats = {
            "by_type": {},
            "by_relationship_type": {},
            "confidence_distribution": {
                "high": 0,    # >= 0.8
                "medium": 0,  # 0.5-0.8
                "low": 0      # < 0.5
            }
        }
        
        # 按类型统计
        for rel_type, relations in relationships.items():
            stats["by_type"][rel_type] = len(relations)
            
            # 按关系类型统计
            for rel in relations:
                rel_type_str = rel.relationship_type.value
                if rel_type_str not in stats["by_relationship_type"]:
                    stats["by_relationship_type"][rel_type_str] = 0
                stats["by_relationship_type"][rel_type_str] += 1
                
                # 置信度分布
                confidence = rel.confidence
                if confidence >= 0.8:
                    stats["confidence_distribution"]["high"] += 1
                elif confidence >= 0.5:
                    stats["confidence_distribution"]["medium"] += 1
                else:
                    stats["confidence_distribution"]["low"] += 1
        
        return stats