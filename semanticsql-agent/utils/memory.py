"""
Neo4j三元组记忆管理 - SemanticSQL Agent核心记忆系统
基于架构设计的完全重构版本，实现工具间智能协作
"""

from typing import List, Dict, Any, Optional, Union
import logging
from datetime import datetime
import uuid

try:
    # 优先使用新的langchain-neo4j包
    from langchain_neo4j import Neo4jGraph
    NEO4J_AVAILABLE = True
    LANGCHAIN_NEO4J_NEW = True
except ImportError:
    try:
        # 备用旧的langchain_community包
        from langchain_community.graphs import Neo4jGraph
        NEO4J_AVAILABLE = True
        LANGCHAIN_NEO4J_NEW = False
    except ImportError:
        NEO4J_AVAILABLE = False
        LANGCHAIN_NEO4J_NEW = False
        Neo4jGraph = None

try:
    from langchain_community.graphs.graph_document import GraphDocument, Node, Relationship
except ImportError:
    Node = None
    Relationship = None
    GraphDocument = None

from models.schemas import SemanticTriple, TripleCollection, PredicateType
from models.exceptions import (
    MemoryConnectionError, 
    TripleStorageError, 
    MemoryQueryError
)


class Neo4jMemoryManager:
    """Neo4j三元组记忆管理器 - 工具间智能协作的核心
    
    设计原则：
    - 记忆分片：每个工具管理自己的记忆片段(source_tool)
    - 依赖查询：工具通过source_tool查询其他工具的记忆
    - 结构化存储：三元组形式存储，支持图查询和推理
    - 完全自主：工具自主决定存储时机和查询策略
    
    核心功能：
    1. store_triples() - 存储工具生成的三元组
    2. query_by_source_tool() - 按工具查询记忆片段
    3. get_related_triples() - 获取实体相关三元组
    """
    
    def __init__(self, 
                 neo4j_uri: str = "bolt://localhost:7687",
                 neo4j_user: str = "neo4j", 
                 neo4j_password: str = "",
                 use_fallback: bool = True):
        """
        初始化Neo4j记忆管理器
        
        Args:
            neo4j_uri: Neo4j连接URI
            neo4j_user: 用户名
            neo4j_password: 密码
            use_fallback: 是否在连接失败时使用内存后备存储
        """
        self.logger = logging.getLogger(__name__)
        self.use_fallback = use_fallback
        self.neo4j_graph = None
        self.fallback_storage = {}  # 内存后备存储
        
        # 尝试连接Neo4j - 使用LangChain Neo4jGraph (需要APOC)
        if NEO4J_AVAILABLE and neo4j_password:
            try:
                self.neo4j_graph = Neo4jGraph(
                    url=neo4j_uri,
                    username=neo4j_user,
                    password=neo4j_password
                )
                # 测试连接
                self.neo4j_graph.query("MATCH (n) RETURN count(n) LIMIT 1")
                self.logger.info("✅ Neo4j连接成功")
            except Exception as e:
                self.logger.warning(f"⚠️ Neo4j连接失败: {e}")
                if not use_fallback:
                    raise MemoryConnectionError("Neo4j", {
                        "uri": neo4j_uri,
                        "user": neo4j_user,
                        "error": str(e)
                    })
                self.logger.info("📦 使用内存后备存储")
    
    def store_triples(self, 
                     triples: Union[List[SemanticTriple], TripleCollection], 
                     source_tool: str) -> bool:
        """
        存储三元组到记忆系统
        
        Args:
            triples: 三元组列表或集合
            source_tool: 来源工具名称
            
        Returns:
            存储是否成功
        """
        try:
            # 统一处理输入格式
            if isinstance(triples, TripleCollection):
                triple_list = triples.triples
                source_tool = triples.source_tool or source_tool
            else:
                triple_list = triples
            
            if not triple_list:
                self.logger.warning(f"⚠️ 工具 {source_tool} 没有三元组需要存储")
                return True
            
            # 设置source_tool
            for triple in triple_list:
                if not triple.source_tool:
                    triple.source_tool = source_tool
            
            # 尝试存储到Neo4j
            if self.neo4j_graph:
                success = self._store_to_neo4j(triple_list, source_tool)
            else:
                success = self._store_to_fallback(triple_list, source_tool)
            
            if success:
                self.logger.info(f"💾 成功存储 {len(triple_list)} 个三元组 (来源: {source_tool})")
            
            return success
            
        except Exception as e:
            self.logger.error(f"❌ 存储三元组失败: {e}")
            raise TripleStorageError("存储", str(e), {"source_tool": source_tool})
    
    def query_by_source_tool(self, source_tool: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        按工具来源查询记忆片段 - 核心依赖查询方法
        
        Args:
            source_tool: 来源工具名称
            limit: 返回数量限制
            
        Returns:
            三元组字典列表
        """
        try:
            if self.neo4j_graph:
                results = self._query_neo4j_by_source(source_tool, limit)
            else:
                results = self._query_fallback_by_source(source_tool, limit)
            
            self.logger.debug(f"🔍 查询 {source_tool} 记忆: {len(results)} 条")
            return results
            
        except Exception as e:
            self.logger.error(f"❌ 查询记忆失败: {e}")
            raise MemoryQueryError("source_tool", str(e), {"source_tool": source_tool})
    
    def get_related_triples(self, 
                           entity: str, 
                           relation_types: Optional[List[str]] = None,
                           limit: int = 30) -> List[Dict[str, Any]]:
        """
        获取实体相关的三元组
        
        Args:
            entity: 实体名称
            relation_types: 关系类型过滤
            limit: 返回数量限制
            
        Returns:
            相关三元组列表
        """
        try:
            if self.neo4j_graph:
                results = self._query_neo4j_related(entity, relation_types, limit)
            else:
                results = self._query_fallback_related(entity, relation_types, limit)
            
            self.logger.debug(f"🔍 查询 {entity} 相关记忆: {len(results)} 条")
            return results
            
        except Exception as e:
            self.logger.error(f"❌ 查询相关记忆失败: {e}")
            raise MemoryQueryError("相关实体", str(e), {"entity": entity})
    
    def get_all_memory_by_tools(self, tool_names: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """
        批量获取多个工具的记忆
        
        Args:
            tool_names: 工具名称列表
            
        Returns:
            按工具分组的记忆字典
        """
        memory_dict = {}
        for tool_name in tool_names:
            memory_dict[tool_name] = self.query_by_source_tool(tool_name)
        return memory_dict
    
    def clear_tool_memory(self, source_tool: str) -> bool:
        """
        清空指定工具的记忆
        
        Args:
            source_tool: 工具名称
            
        Returns:
            清空是否成功
        """
        try:
            if self.neo4j_graph:
                success = self._clear_neo4j_memory(source_tool)
            else:
                success = self._clear_fallback_memory(source_tool)
            
            if success:
                self.logger.info(f"🗑️ 清空工具 {source_tool} 的记忆")
            
            return success
            
        except Exception as e:
            self.logger.error(f"❌ 清空记忆失败: {e}")
            raise TripleStorageError("清空", str(e), {"source_tool": source_tool})
    
    def get_memory_statistics(self) -> Dict[str, Any]:
        """获取记忆统计信息"""
        try:
            if self.neo4j_graph:
                return self._get_neo4j_statistics()
            else:
                return self._get_fallback_statistics()
        except Exception as e:
            self.logger.warning(f"⚠️ 获取记忆统计失败: {e}")
            return {"error": str(e)}
    
    # ========== Neo4j存储实现 ==========
    def _store_to_neo4j(self, triples: List[SemanticTriple], source_tool: str) -> bool:
        """存储到Neo4j"""
        try:
            # 转换为GraphDocument
            graph_doc = self._convert_to_graph_document(triples, source_tool)
            
            # 添加到Neo4j
            self.neo4j_graph.add_graph_documents([graph_doc])
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Neo4j存储失败: {e}")
            # 尝试后备存储
            if self.use_fallback:
                return self._store_to_fallback(triples, source_tool)
            return False
    
    def _query_neo4j_by_source(self, source_tool: str, limit: int) -> List[Dict[str, Any]]:
        """从Neo4j按工具查询"""
        cypher_query = """
        MATCH (s)-[r]->(o)
        WHERE r.source_tool = $source_tool
        RETURN s.name as subject, type(r) as predicate, o.name as object,
               r.confidence as confidence, r.source_tool as source_tool,
               s.type as subject_type, o.type as object_type
        ORDER BY id(r) DESC
        LIMIT $limit
        """
        
        results = self.neo4j_graph.query(
            cypher_query, 
            {"source_tool": source_tool, "limit": limit}
        )
        return results
    
    def _query_neo4j_related(self, entity: str, relation_types: Optional[List[str]], limit: int) -> List[Dict[str, Any]]:
        """从Neo4j查询相关实体"""
        if relation_types:
            relation_filter = "AND type(r) IN $relation_types"
            params = {"entity": entity, "relation_types": relation_types, "limit": limit}
        else:
            relation_filter = ""
            params = {"entity": entity, "limit": limit}
        
        cypher_query = f"""
        MATCH (s)-[r]->(o)
        WHERE s.name = $entity OR o.name = $entity {relation_filter}
        RETURN s.name as subject, type(r) as predicate, o.name as object,
               r.confidence as confidence, r.source_tool as source_tool
        ORDER BY r.confidence DESC
        LIMIT $limit
        """
        
        results = self.neo4j_graph.query(cypher_query, params)
        return results
    
    def _clear_neo4j_memory(self, source_tool: str) -> bool:
        """清空Neo4j中指定工具的记忆"""
        cypher_query = """
        MATCH ()-[r]->() 
        WHERE r.source_tool = $source_tool
        DELETE r
        """
        
        self.neo4j_graph.query(cypher_query, {"source_tool": source_tool})
        return True
    
    def _get_neo4j_statistics(self) -> Dict[str, Any]:
        """获取Neo4j统计信息"""
        stats_query = """
        MATCH ()-[r]->()
        RETURN r.source_tool as tool, count(r) as count
        ORDER BY count DESC
        """
        
        results = self.neo4j_graph.query(stats_query)
        
        total_query = "MATCH ()-[r]->() RETURN count(r) as total"
        total_result = self.neo4j_graph.query(total_query)
        
        return {
            "storage_type": "Neo4j",
            "total_triples": total_result[0]["total"] if total_result else 0,
            "by_tool": {r["tool"]: r["count"] for r in results}
        }
    
    # ========== 内存后备存储实现 ==========
    def _store_to_fallback(self, triples: List[SemanticTriple], source_tool: str) -> bool:
        """存储到内存后备"""
        if source_tool not in self.fallback_storage:
            self.fallback_storage[source_tool] = []
        
        for triple in triples:
            self.fallback_storage[source_tool].append({
                "subject": triple.subject,
                "predicate": triple.predicate,
                "object": triple.object,
                "subject_type": triple.subject_type,
                "object_type": triple.object_type,
                "confidence": triple.confidence,
                "source_tool": triple.source_tool,
                "timestamp": triple.timestamp,
                "session_id": triple.session_id
            })
        
        return True
    
    def _query_fallback_by_source(self, source_tool: str, limit: int) -> List[Dict[str, Any]]:
        """从内存后备按工具查询"""
        tool_data = self.fallback_storage.get(source_tool, [])
        return tool_data[:limit]
    
    def _query_fallback_related(self, entity: str, relation_types: Optional[List[str]], limit: int) -> List[Dict[str, Any]]:
        """从内存后备查询相关实体"""
        related_triples = []
        
        for tool_data in self.fallback_storage.values():
            for triple_dict in tool_data:
                # 检查主体或客体是否匹配
                if triple_dict["subject"] == entity or triple_dict["object"] == entity:
                    # 检查关系类型过滤
                    if not relation_types or triple_dict["predicate"] in relation_types:
                        related_triples.append(triple_dict)
        
        # 按置信度排序
        related_triples.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        return related_triples[:limit]
    
    def _clear_fallback_memory(self, source_tool: str) -> bool:
        """清空内存后备中指定工具的记忆"""
        if source_tool in self.fallback_storage:
            del self.fallback_storage[source_tool]
        return True
    
    def _get_fallback_statistics(self) -> Dict[str, Any]:
        """获取内存后备统计信息"""
        by_tool = {tool: len(triples) for tool, triples in self.fallback_storage.items()}
        total = sum(by_tool.values())
        
        return {
            "storage_type": "Memory Fallback",
            "total_triples": total,
            "by_tool": by_tool
        }
    
    # ========== 辅助方法 ==========
    def _convert_to_graph_document(self, triples: List[SemanticTriple], source_tool: str) -> GraphDocument:
        """将三元组转换为GraphDocument"""
        if not NEO4J_AVAILABLE:
            raise RuntimeError("Neo4j不可用，无法转换为GraphDocument")
        
        nodes = []
        relationships = []
        node_set = set()
        
        for triple in triples:
            # 创建主体节点
            if triple.subject not in node_set:
                subject_node = Node(
                    id=triple.subject,
                    type=triple.subject_type,
                    properties={"name": triple.subject, "type": triple.subject_type}
                )
                nodes.append(subject_node)
                node_set.add(triple.subject)
            
            # 创建客体节点
            if triple.object not in node_set:
                object_node = Node(
                    id=triple.object,
                    type=triple.object_type,
                    properties={"name": triple.object, "type": triple.object_type}
                )
                nodes.append(object_node)
                node_set.add(triple.object)
            
            # 创建关系
            relationship = Relationship(
                source=Node(id=triple.subject, type=triple.subject_type),
                target=Node(id=triple.object, type=triple.object_type),
                type=triple.predicate.upper().replace(" ", "_"),
                properties={
                    "confidence": triple.confidence,
                    "source_tool": triple.source_tool,
                    "timestamp": triple.timestamp,
                    "session_id": triple.session_id
                }
            )
            relationships.append(relationship)
        
        return GraphDocument(
            nodes=nodes,
            relationships=relationships,
            source=f"SemanticSQL-Agent-{source_tool}"
        )
    
    def is_available(self) -> bool:
        """检查记忆系统是否可用"""
        return self.neo4j_graph is not None or self.use_fallback
    
    def get_connection_info(self) -> Dict[str, Any]:
        """获取连接信息"""
        return {
            "neo4j_available": self.neo4j_graph is not None,
            "fallback_enabled": self.use_fallback,
            "storage_type": "Neo4j" if self.neo4j_graph else "Memory"
        }


# ========== 便利函数 ==========
def create_memory_manager(neo4j_uri: Optional[str] = None,
                         neo4j_user: Optional[str] = None,
                         neo4j_password: Optional[str] = None) -> Neo4jMemoryManager:
    """
    创建记忆管理器的便利函数
    
    Args:
        neo4j_uri: Neo4j连接URI
        neo4j_user: 用户名
        neo4j_password: 密码
        
    Returns:
        配置好的记忆管理器
    """
    return Neo4jMemoryManager(
        neo4j_uri=neo4j_uri or "bolt://localhost:7687",
        neo4j_user=neo4j_user or "neo4j",
        neo4j_password=neo4j_password or "",
        use_fallback=True
    )


def format_memory_text(memory_triples: List[Dict[str, Any]], limit: int = 10) -> str:
    """
    格式化记忆三元组为文本描述
    
    Args:
        memory_triples: 记忆三元组列表
        limit: 显示数量限制
        
    Returns:
        格式化的记忆文本
    """
    if not memory_triples:
        return "记忆为空"
    
    text_lines = []
    for triple in memory_triples[:limit]:
        subject = triple.get("subject", "")
        predicate = triple.get("predicate", "")
        object_val = triple.get("object", "")
        source = triple.get("source_tool", "unknown")
        
        text_lines.append(f"• {subject} {predicate} {object_val} [{source}]")
    
    if len(memory_triples) > limit:
        text_lines.append(f"... 还有 {len(memory_triples) - limit} 条记忆")
    
    return "\n".join(text_lines)