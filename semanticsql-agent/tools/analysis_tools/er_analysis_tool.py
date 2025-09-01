"""
ER关系分析工具 - 分析数据库表之间的实体关系
基于 LangChain BaseTool
"""

from typing import Dict, Any, Type, List, Set, Tuple, Optional
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import networkx as nx

from models.schemas import TableRelationship
from models.exceptions import ToolExecutionError


class ERAnalysisInput(BaseModel):
    """ER分析输入"""
    memory: Dict[str, Any] = Field(description="包含数据库分析结果的记忆")
    analyze_implicit: bool = Field(default=True, description="是否分析隐式关系")
    depth: int = Field(default=2, description="关系分析深度")


class ERAnalysisTool(BaseTool):
    """实体关系分析工具"""
    
    name: str = "er_analysis"
    description: str = "分析数据库表之间的实体关系，识别外键关系和隐式关联"
    args_schema: Type[BaseModel] = ERAnalysisInput
    
    def _run(self, tool_input: str = "", **kwargs) -> Dict[str, Any]:
        """执行ER关系分析"""
        try:
            # 解析输入参数
            import json
            memory = {}
            schema_info = {}
            field_classification = {}
            
            if tool_input:
                try:
                    parsed_input = json.loads(tool_input)
                    # 尝试多种输入格式
                    if "database_schema" in parsed_input:
                        schema_info = parsed_input["database_schema"]
                    elif "schema" in parsed_input:
                        schema_info = parsed_input["schema"]
                    elif "memory" in parsed_input:
                        memory = parsed_input["memory"]
                        db_analysis = memory.get("db_analysis", {})
                        schema_info = db_analysis.get("schema_info", {})
                        field_classification = db_analysis.get("field_classification", {})
                    elif "db_analysis" in parsed_input:
                        db_analysis = parsed_input["db_analysis"]
                        schema_info = db_analysis.get("schema_info", {})
                        field_classification = db_analysis.get("field_classification", {})
                    else:
                        memory = parsed_input
                        db_analysis = memory.get("db_analysis", {})
                        schema_info = db_analysis.get("schema_info", {})
                        field_classification = db_analysis.get("field_classification", {})
                except json.JSONDecodeError:
                    schema_info = {}
            
            if not schema_info:
                raise ToolExecutionError(
                    tool_name=self.name,
                    reason="未找到数据库结构信息，请先执行schema_extraction"
                )
            
            tables = schema_info.get("tables", {})
            
            # 分析关系
            relationships = {}
            all_relations = []
            
            # 1. 分析显式外键关系
            explicit_relations = self._analyze_explicit_relations(tables)
            all_relations.extend(explicit_relations)
            
            # 2. 分析隐式关系（如果启用）
            implicit_relations = []
            if analyze_implicit:
                implicit_relations = self._analyze_implicit_relations(
                    tables, field_classification
                )
                all_relations.extend(implicit_relations)
            
            # 3. 构建关系图
            relation_graph = self._build_relation_graph(all_relations)
            
            # 4. 分析关系模式
            patterns = self._analyze_relationship_patterns(
                relation_graph, tables, all_relations
            )
            
            # 5. 生成关系洞察
            insights = self._generate_relationship_insights(
                all_relations, patterns, tables
            )
            
            # 整理结果
            for relation in all_relations:
                from_table = relation["from_table"]
                if from_table not in relationships:
                    relationships[from_table] = []
                relationships[from_table].append(relation)
            
            return {
                "relationships": relationships,
                "explicit_count": len(explicit_relations),
                "implicit_count": len(implicit_relations),
                "total_relations": len(all_relations),
                "relationship_patterns": patterns,
                "insights": insights,
                "relation_graph": self._graph_to_dict(relation_graph)
            }
            
        except Exception as e:
            raise ToolExecutionError(
                tool_name=self.name,
                reason=f"ER关系分析失败: {str(e)}"
            )
    
    def _analyze_explicit_relations(self, tables: Dict[str, Any]) -> List[Dict[str, Any]]:
        """分析显式外键关系"""
        relations = []
        
        for table_name, table_info in tables.items():
            foreign_keys = table_info.get("foreign_keys", [])
            
            for fk in foreign_keys:
                relation = {
                    "from_table": table_name,
                    "to_table": fk.get("referred_table", ""),
                    "type": "foreign_key",
                    "foreign_key": fk.get("constrained_columns", []),
                    "referenced_columns": fk.get("referred_columns", []),
                    "constraint_name": fk.get("name", ""),
                    "relationship_type": "many-to-one",
                    "is_explicit": True,
                    "confidence": 1.0
                }
                relations.append(relation)
        
        return relations
    
    def _analyze_implicit_relations(
        self, 
        tables: Dict[str, Any],
        field_classification: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """分析隐式关系（基于命名约定）"""
        relations = []
        
        # 获取所有表名
        table_names = list(tables.keys())
        table_names_lower = [t.lower() for t in table_names]
        
        for table_name, table_info in tables.items():
            columns = table_info.get("columns", [])
            
            for column in columns:
                column_name = column["name"]
                column_name_lower = column_name.lower()
                
                # 检查是否是潜在的外键
                if column_name_lower.endswith("_id") and column_name_lower != "id":
                    # 提取可能的表名
                    potential_table = column_name_lower[:-3]  # 去掉_id
                    
                    # 查找匹配的表
                    matched_table = None
                    
                    # 精确匹配
                    if potential_table in table_names_lower:
                        idx = table_names_lower.index(potential_table)
                        matched_table = table_names[idx]
                    # 复数形式匹配
                    elif potential_table + "s" in table_names_lower:
                        idx = table_names_lower.index(potential_table + "s")
                        matched_table = table_names[idx]
                    # 单数形式匹配
                    elif potential_table.endswith("s") and potential_table[:-1] in table_names_lower:
                        idx = table_names_lower.index(potential_table[:-1])
                        matched_table = table_names[idx]
                    
                    if matched_table and matched_table != table_name:
                        # 检查是否已存在显式关系
                        existing = any(
                            rel for rel in relations
                            if rel["from_table"] == table_name 
                            and rel["to_table"] == matched_table
                            and column_name in rel.get("foreign_key", [])
                        )
                        
                        if not existing:
                            relation = {
                                "from_table": table_name,
                                "to_table": matched_table,
                                "type": "implicit_foreign_key",
                                "foreign_key": [column_name],
                                "referenced_columns": ["id"],
                                "relationship_type": "many-to-one",
                                "is_explicit": False,
                                "confidence": 0.8,
                                "reason": "命名约定推断"
                            }
                            relations.append(relation)
        
        # 分析多对多关系表
        for table_name in tables:
            table_name_lower = table_name.lower()
            
            # 检查是否是关联表（包含多个表名）
            if table_name.count("_") >= 1:
                parts = table_name_lower.split("_")
                
                # 查找可能的关联表
                matched_tables = []
                for part in parts:
                    if part in table_names_lower:
                        idx = table_names_lower.index(part)
                        matched_tables.append(table_names[idx])
                    elif part + "s" in table_names_lower:
                        idx = table_names_lower.index(part + "s")
                        matched_tables.append(table_names[idx])
                
                # 如果找到两个表，可能是多对多关系
                if len(matched_tables) == 2:
                    relation = {
                        "from_table": matched_tables[0],
                        "to_table": matched_tables[1],
                        "type": "many_to_many",
                        "junction_table": table_name,
                        "relationship_type": "many-to-many",
                        "is_explicit": False,
                        "confidence": 0.7,
                        "reason": "关联表命名推断"
                    }
                    relations.append(relation)
        
        return relations
    
    def _build_relation_graph(self, relations: List[Dict[str, Any]]) -> nx.DiGraph:
        """构建关系图"""
        graph = nx.DiGraph()
        
        for relation in relations:
            from_table = relation["from_table"]
            to_table = relation["to_table"]
            
            # 添加节点
            graph.add_node(from_table, type="table")
            graph.add_node(to_table, type="table")
            
            # 添加边
            edge_data = {
                "type": relation["type"],
                "relationship_type": relation["relationship_type"],
                "confidence": relation.get("confidence", 1.0)
            }
            
            if relation.get("foreign_key"):
                edge_data["foreign_key"] = relation["foreign_key"]
            
            graph.add_edge(from_table, to_table, **edge_data)
        
        return graph
    
    def _analyze_relationship_patterns(
        self, 
        graph: nx.DiGraph,
        tables: Dict[str, Any],
        relations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """分析关系模式"""
        patterns = {
            "hub_tables": [],
            "isolated_tables": [],
            "relationship_chains": [],
            "circular_dependencies": [],
            "table_connectivity": {}
        }
        
        # 找出孤立的表
        all_tables = set(tables.keys())
        connected_tables = set(graph.nodes())
        patterns["isolated_tables"] = list(all_tables - connected_tables)
        
        # 分析每个表的连接度
        for table in connected_tables:
            in_degree = graph.in_degree(table)
            out_degree = graph.out_degree(table)
            total_degree = in_degree + out_degree
            
            patterns["table_connectivity"][table] = {
                "in_degree": in_degree,
                "out_degree": out_degree,
                "total_degree": total_degree
            }
            
            # 识别中心表（高连接度）
            if total_degree >= 5:
                patterns["hub_tables"].append({
                    "table": table,
                    "connections": total_degree,
                    "role": "central_entity"
                })
        
        # 查找循环依赖
        try:
            cycles = list(nx.simple_cycles(graph))
            patterns["circular_dependencies"] = [
                {"tables": cycle, "length": len(cycle)}
                for cycle in cycles
            ]
        except:
            pass
        
        # 查找关系链
        for source in connected_tables:
            for target in connected_tables:
                if source != target:
                    try:
                        paths = list(nx.all_simple_paths(
                            graph, source, target, cutoff=3
                        ))
                        for path in paths:
                            if len(path) > 2:  # 至少经过一个中间表
                                patterns["relationship_chains"].append({
                                    "path": path,
                                    "length": len(path) - 1
                                })
                    except:
                        pass
        
        return patterns
    
    def _generate_relationship_insights(
        self, 
        relations: List[Dict[str, Any]],
        patterns: Dict[str, Any],
        tables: Dict[str, Any]
    ) -> List[str]:
        """生成关系洞察"""
        insights = []
        
        # 基本统计
        total_relations = len(relations)
        explicit_count = sum(1 for r in relations if r.get("is_explicit", True))
        implicit_count = total_relations - explicit_count
        
        insights.append(f"共发现{total_relations}个表关系，其中显式外键{explicit_count}个")
        
        if implicit_count > 0:
            insights.append(f"通过命名约定推断出{implicit_count}个隐式关系")
        
        # 孤立表分析
        isolated = patterns.get("isolated_tables", [])
        if isolated:
            insights.append(f"发现{len(isolated)}个孤立表，可能是配置表或日志表")
        
        # 中心表分析
        hub_tables = patterns.get("hub_tables", [])
        if hub_tables:
            top_hubs = sorted(hub_tables, key=lambda x: x["connections"], reverse=True)[:3]
            hub_names = [h["table"] for h in top_hubs]
            insights.append(f"核心实体表：{', '.join(hub_names)}")
        
        # 关系类型分析
        many_to_many = sum(1 for r in relations if r["relationship_type"] == "many-to-many")
        if many_to_many > 0:
            insights.append(f"发现{many_to_many}个多对多关系")
        
        # 循环依赖
        cycles = patterns.get("circular_dependencies", [])
        if cycles:
            insights.append(f"警告：发现{len(cycles)}个循环依赖，可能影响数据完整性")
        
        # 连接度分析
        connectivity = patterns.get("table_connectivity", {})
        if connectivity:
            avg_degree = sum(t["total_degree"] for t in connectivity.values()) / len(connectivity)
            if avg_degree < 2:
                insights.append("数据库关系较为简单，适合基础查询")
            elif avg_degree > 4:
                insights.append("数据库关系复杂，适合多表关联查询")
        
        return insights
    
    def _graph_to_dict(self, graph: nx.DiGraph) -> Dict[str, Any]:
        """将图转换为字典格式"""
        return {
            "nodes": list(graph.nodes()),
            "edges": [
                {
                    "from": u,
                    "to": v,
                    "data": data
                }
                for u, v, data in graph.edges(data=True)
            ],
            "node_count": graph.number_of_nodes(),
            "edge_count": graph.number_of_edges()
        }
    
    async def _arun(
        self,
        memory: Dict[str, Any],
        analyze_implicit: bool = True,
        depth: int = 2
    ) -> Dict[str, Any]:
        """异步执行（当前实现为同步）"""
        return self._run(memory, analyze_implicit, depth)