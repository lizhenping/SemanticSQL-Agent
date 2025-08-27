"""实体关系分析工具"""

from tools.base import BaseSemanticSQLTool
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class ERAnalysisInput(BaseModel):
    """输入模式"""
    schema_info: Dict[str, Any] = Field(
        description="数据库结构信息"
    )
    focus_tables: Optional[List[str]] = Field(
        default=None,
        description="需要重点分析关系的表"
    )


class ERAnalysisTool(BaseSemanticSQLTool):
    """实体关系分析工具"""
    
    name = "analyze_entity_relationships"
    description = (
        "分析表之间的实体关系，识别主外键关系、关联字段等。"
        "帮助理解数据模型，生成正确的 JOIN 查询。"
    )
    args_schema = ERAnalysisInput
    
    def execute(
        self,
        schema_info: Dict[str, Any],
        focus_tables: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """执行实体关系分析"""
        tables = schema_info.get("tables", {})
        
        # 分析外键关系
        foreign_keys = self._extract_foreign_keys(tables)
        
        # 分析潜在关系
        potential_relations = self._analyze_potential_relations(
            tables, 
            focus_tables
        )
        
        # 生成关系图
        relationship_map = self._build_relationship_map(
            foreign_keys,
            potential_relations
        )
        
        # 使用 LLM 增强分析
        enhanced_analysis = self._enhance_with_llm(
            schema_info,
            relationship_map,
            focus_tables
        )
        
        return {
            "foreign_keys": foreign_keys,
            "potential_relations": potential_relations,
            "relationship_map": relationship_map,
            "analysis": enhanced_analysis,
            "summary": self._generate_summary(relationship_map)
        }
    
    def _extract_foreign_keys(self, tables: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从表结构中提取外键关系"""
        foreign_keys = []
        
        for table_name, table_info in tables.items():
            structure = table_info.get("structure", "")
            if not structure:
                continue
            
            # 简单的外键模式匹配
            lines = structure.split('\n')
            for line in lines:
                line = line.strip()
                if 'FOREIGN KEY' in line.upper():
                    # 尝试解析外键信息
                    fk_info = self._parse_foreign_key(line, table_name)
                    if fk_info:
                        foreign_keys.append(fk_info)
        
        return foreign_keys
    
    def _parse_foreign_key(self, line: str, table_name: str) -> Optional[Dict[str, Any]]:
        """解析外键定义"""
        import re
        
        # 匹配 FOREIGN KEY (`column`) REFERENCES `table` (`column`)
        pattern = r'FOREIGN\s+KEY\s*\(`?(\w+)`?\)\s*REFERENCES\s*`?(\w+)`?\s*\(`?(\w+)`?\)'
        match = re.search(pattern, line, re.IGNORECASE)
        
        if match:
            return {
                "from_table": table_name,
                "from_column": match.group(1),
                "to_table": match.group(2),
                "to_column": match.group(3),
                "type": "foreign_key"
            }
        
        return None
    
    def _analyze_potential_relations(
        self,
        tables: Dict[str, Any],
        focus_tables: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """分析潜在的关系（基于命名约定）"""
        potential_relations = []
        
        # 获取所有表的列信息
        table_columns = {}
        for table_name, table_info in tables.items():
            if focus_tables and table_name not in focus_tables:
                continue
            columns = [col["name"] for col in table_info.get("columns", [])]
            table_columns[table_name] = columns
        
        # 查找潜在关系
        for table1, columns1 in table_columns.items():
            for table2, columns2 in table_columns.items():
                if table1 >= table2:  # 避免重复
                    continue
                
                # 查找相同名称的列
                common_columns = set(columns1) & set(columns2)
                for col in common_columns:
                    if self._is_potential_join_column(col):
                        potential_relations.append({
                            "from_table": table1,
                            "to_table": table2,
                            "column": col,
                            "type": "potential",
                            "confidence": self._calculate_confidence(col)
                        })
                
                # 查找表名_id 模式
                for col in columns1:
                    if col.lower() == f"{table2.lower()}_id" or col.lower() == f"{table2.lower()}id":
                        potential_relations.append({
                            "from_table": table1,
                            "from_column": col,
                            "to_table": table2,
                            "to_column": "id",
                            "type": "naming_convention",
                            "confidence": 0.8
                        })
        
        return potential_relations
    
    def _is_potential_join_column(self, column_name: str) -> bool:
        """判断是否可能是关联列"""
        column_lower = column_name.lower()
        
        # 常见的关联列模式
        patterns = ["id", "code", "no", "key", "user", "customer", "order", "product"]
        
        return any(pattern in column_lower for pattern in patterns)
    
    def _calculate_confidence(self, column_name: str) -> float:
        """计算关系置信度"""
        column_lower = column_name.lower()
        
        if column_lower in ["id", "user_id", "customer_id", "order_id"]:
            return 0.9
        elif "_id" in column_lower:
            return 0.8
        elif any(pattern in column_lower for pattern in ["code", "no"]):
            return 0.6
        else:
            return 0.4
    
    def _build_relationship_map(
        self,
        foreign_keys: List[Dict[str, Any]],
        potential_relations: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """构建关系映射"""
        relationship_map = {}
        
        # 添加外键关系
        for fk in foreign_keys:
            key = f"{fk['from_table']}->{fk['to_table']}"
            if key not in relationship_map:
                relationship_map[key] = []
            relationship_map[key].append(fk)
        
        # 添加潜在关系（按置信度排序）
        sorted_relations = sorted(
            potential_relations,
            key=lambda x: x.get("confidence", 0),
            reverse=True
        )
        
        for rel in sorted_relations[:10]:  # 只保留置信度最高的10个
            key = f"{rel['from_table']}->{rel['to_table']}"
            if key not in relationship_map:
                relationship_map[key] = []
            relationship_map[key].append(rel)
        
        return relationship_map
    
    def _enhance_with_llm(
        self,
        schema_info: Dict[str, Any],
        relationship_map: Dict[str, List[Dict[str, Any]]],
        focus_tables: Optional[List[str]] = None
    ) -> str:
        """使用 LLM 增强关系分析"""
        # 构建提示词
        prompt = f"""基于以下数据库结构和已识别的关系，请分析数据模型：

数据库包含 {schema_info.get('tables_count', 0)} 个表。

已识别的关系：
{self._format_relationships(relationship_map)}

请分析：
1. 核心实体及其关系类型（一对一、一对多、多对多）
2. 主要的业务流程涉及的表
3. 数据模型的设计模式（如星型、雪花型等）
4. 关键的关联查询场景

请用简洁的语言描述。"""
        
        if focus_tables:
            prompt += f"\n\n重点关注这些表：{', '.join(focus_tables)}"
        
        response = self.llm.invoke(prompt)
        return response.content
    
    def _format_relationships(self, relationship_map: Dict[str, List[Dict[str, Any]]]) -> str:
        """格式化关系信息"""
        lines = []
        
        for key, relations in relationship_map.items():
            for rel in relations:
                if rel["type"] == "foreign_key":
                    lines.append(
                        f"- {rel['from_table']}.{rel['from_column']} -> "
                        f"{rel['to_table']}.{rel['to_column']} (外键)"
                    )
                elif rel["type"] == "potential":
                    lines.append(
                        f"- {rel['from_table']} <-> {rel['to_table']} "
                        f"通过 {rel['column']} (潜在关系，置信度: {rel['confidence']:.1f})"
                    )
        
        return "\n".join(lines) if lines else "未发现明确的关系"
    
    def _generate_summary(self, relationship_map: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """生成关系摘要"""
        summary = {
            "total_relationships": len(relationship_map),
            "foreign_keys_count": 0,
            "potential_relations_count": 0,
            "most_connected_tables": []
        }
        
        # 统计表的连接数
        table_connections = {}
        
        for key, relations in relationship_map.items():
            tables = key.split("->")
            for table in tables:
                table_connections[table] = table_connections.get(table, 0) + 1
            
            for rel in relations:
                if rel["type"] == "foreign_key":
                    summary["foreign_keys_count"] += 1
                else:
                    summary["potential_relations_count"] += 1
        
        # 找出连接最多的表
        if table_connections:
            sorted_tables = sorted(
                table_connections.items(),
                key=lambda x: x[1],
                reverse=True
            )
            summary["most_connected_tables"] = [
                {"table": table, "connections": count}
                for table, count in sorted_tables[:5]
            ]
        
        return summary