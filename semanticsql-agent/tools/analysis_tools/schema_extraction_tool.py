"""Schema Extraction Tool - 基于设计文档的Neo4j直接操作版本
专注于纯元数据提取和Neo4j图结构存储，符合extreme-simple设计理念
"""

from typing import Dict, Any, Optional, List, Union
import json
import logging
import statistics
from collections import Counter
from datetime import datetime

from pydantic import Field
from tools.base_tool import BaseSemanticSQLTool
from utils.database import DatabaseManager
from models.exceptions import raise_tool_error


class SchemaExtractionTool(BaseSemanticSQLTool):
    """Schema Extraction Tool - Neo4j直接操作版本
    
    核心职责：
    - 纯元数据提取：从MySQL数据库提取基础结构信息
    - Neo4j存储：将元数据以图结构存储到Neo4j
    - 阶段分离：专注当前阶段，为后续工具提供基础数据
    
    设计原则：
    - 极简操作：只处理数据库中实际存在的信息
    - 配置灵活：支持表过滤和comment使用配置
    - 无过度工程：不进行性能优化，直接简单操作
    - 直接存储：跳过三元组，直接操作Neo4j节点和关系
    """
    
    name: str = "schema_extraction_tool"
    description: str = "分析数据库结构，提取表和字段信息，直接存储到Neo4j图数据库"
    
    # 数据库管理器（可选注入）
    database_manager: Optional[DatabaseManager] = Field(default=None, exclude=True)
    
    def __init__(self, memory_manager: Optional['Neo4jMemoryManager'] = None, 
                 database_manager: Optional[DatabaseManager] = None, **kwargs):
        """
        初始化Schema提取工具
        
        Args:
            memory_manager: Neo4j记忆管理器实例
            database_manager: 可选的数据库管理器实例
        """
        super().__init__(memory_manager=memory_manager, **kwargs)
        # 使用object.__setattr__避免Pydantic验证问题
        object.__setattr__(self, 'database_manager', database_manager)
    
    def _run(self, *args, **kwargs) -> str:
        """
        执行Schema提取 - 基于设计文档的Neo4j直接操作
        
        Args:
            input_text: 包含数据库连接参数和配置的输入文本
            
        Returns:
            简洁的执行结果，指向下一个工具
        """
        # 提取输入文本

        
        # 自定义日志记录（避免基类中的三元组引用问题）
        self.logger.info(f"🔧 {self.name}: 开始执行 - 输入: ...")
        
        try:
            # 1. 解析输入参数和配置
        
            # # 2. 获取数据库管理器
            # db_manager = self._get_database_manager()
            
            # # 3. 从MySQL提取原始数据
            # raw_data = self._extract_mysql_metadata(db_manager)
            
            # # 4. 直接存储到Neo4j图结构
            # self._store_to_neo4j(raw_data)
            
            # # 5. 返回简洁成功消息
            result_message = "✅ schema_extraction_tool提取完成，已存储到Neo4j。请继续执行 domain_analysis_tool 工具。"
            
            # 自定义执行完成日志
            # table_count = len(raw_data.get('filtered_tables', []))
            self.logger.info(f"✅ {self.name}: 执行完成 - 成功处理 {table_count} 个表")
            return result_message
            
        except Exception as e:
            error_msg = f"Schema提取失败: {str(e)}"
            self.logger.error(f"❌ {self.name}: {error_msg}")
            return f"❌ {error_msg}"
    
    # ========== 核心业务逻辑 ==========
    
    def _get_database_manager(self) -> DatabaseManager:
        """获取数据库管理器"""
        # 优先使用注入的管理器
        if self.database_manager:
            return self.database_manager
        
        # 未提供数据库管理器时的错误处理
        raise_tool_error(
            self.name, 
            "未找到数据库连接信息，请通过构造函数注入DatabaseManager"
        )
    
    def _extract_mysql_metadata(self, db_manager: DatabaseManager) -> Dict[str, Any]:
        """从MySQL提取元数据 - 按设计文档规范"""
        try:
            connection_info = db_manager.get_connection_info()
            database_name = connection_info["database"]
            
            # 1. 获取数据库级别信息
            database_info = self._get_database_info(database_name)
            
            # 2. 获取所有表名并过滤
            all_tables = self._get_all_table_names(db_manager)
            filtered_tables = self._filter_tables(all_tables, ["aid_info"])
            
            # 3. 提取每个表的详细信息
            tables_data = []
            for table_name in filtered_tables:
                table_data = self._extract_table_metadata(db_manager, table_name)
                tables_data.append(table_data)
            
            self.logger.info(f"📊 成功提取数据库 {database_name}: {len(filtered_tables)} 个表 (过滤后)")
            
            return {
                "database_info": database_info,
                "filtered_tables": filtered_tables,
                "tables_data": tables_data,
                "connection_info": connection_info
            }
            
        except Exception as e:
            raise_tool_error(self.name, f"MySQL元数据提取失败: {str(e)}")
    
    def _get_database_info(self, database_name: str) -> Dict[str, Any]:
        """获取数据库级别信息
        
        MySQL不支持数据库级别的注释，business_desc字段保留在Neo4J中供后期填充
        """
        return {
            "name": database_name,
            "business_desc": ""  # 保留字段供后期在Neo4J中填充
        }
    
    def _get_all_table_names(self, db_manager: DatabaseManager) -> List[str]:
        """获取所有表名"""
        try:
            sql = f"SELECT TABLE_NAME as table_name FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = '{db_manager.database}'"
            result = db_manager.execute_sql_safe(sql)
            if result.get("success") and result.get("data"):
                return [row["table_name"] for row in result["data"]]
            return []
        except Exception as e:
            self.logger.error(f"获取表名列表失败: {e}")
            return []
    
    def _filter_tables(self, table_names: List[str], blacklist: List[str]) -> List[str]:
        """根据黑名单过滤表名"""
        if not blacklist:
            return table_names
        
        filtered = []
        for table_name in table_names:
            should_include = True
            for blacklist_pattern in blacklist:
                if blacklist_pattern in table_name:
                    should_include = False
                    break
            if should_include:
                filtered.append(table_name)
        
        filtered_count = len(table_names) - len(filtered)
        if filtered_count > 0:
            self.logger.info(f"🚫 过滤了 {filtered_count} 个表：{blacklist}")
        
        return filtered
    
    def _extract_table_metadata(self, db_manager: DatabaseManager, table_name: str) -> Dict[str, Any]:
        """提取单个表的元数据"""
        # 1. 获取表基本信息
        table_comment = ""
        use_db_comments = True
        if use_db_comments == True:
            try:
                sql = f"SELECT TABLE_COMMENT as table_comment FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = '{db_manager.database}' AND TABLE_NAME = '{table_name}'"
                result = db_manager.execute_sql_safe(sql)
                if result.get("success") and result.get("data"):
                    table_comment = result["data"][0].get("table_comment", "") or ""
            except Exception as e:
                self.logger.warning(f"获取表 {table_name} comment失败: {e}")
        
        # 2. 获取列信息
        columns_data = self._extract_columns_metadata(db_manager, table_name)
        
        return {
            "name": table_name,
            "row_count": None,  # 当前阶段为null，后续填充
            "business_desc": table_comment,
            "columns": columns_data
        }
    
    def _extract_columns_metadata(self, db_manager: DatabaseManager, table_name: str) -> List[Dict[str, Any]]:
        """提取列元数据 - 包含当前阶段所有字段"""
        # 获取基础列信息
        result = self._query_column_info(db_manager, table_name)
        if not (result.get("success") and result.get("data")):
            return []
        
        # 处理每一列
        columns_data = []
        for row in result["data"]:
            column_info = self._build_column_info(row, db_manager, table_name)
            columns_data.append(column_info)
            
        return columns_data
    
    def _query_column_info(self, db_manager: DatabaseManager, table_name: str) -> dict:
        """查询列的基础信息"""
        sql = f"""
        SELECT 
            COLUMN_NAME as column_name,
            DATA_TYPE as data_type,
            IS_NULLABLE as is_nullable,
            COLUMN_KEY as column_key,
            COLUMN_COMMENT as column_comment
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = '{db_manager.database}' 
          AND TABLE_NAME = '{table_name}'
        ORDER BY ORDINAL_POSITION
        """
        return db_manager.execute_sql_safe(sql)
    
    def _build_column_info(self, row: dict, db_manager: DatabaseManager, table_name: str) -> dict:
        """构建单个列的完整信息"""
        column_name = row["column_name"]
        
        # 基础字段
        column_info = self._create_base_column_info(row)
        
        # 增强信息
        column_info["is_foreign"] = self._check_foreign_key(db_manager, table_name, column_name)
        column_info["entropy_level"] = self._calculate_entropy_level(db_manager, table_name, column_name)
        column_info["sample_values"] = self._collect_sample_values(db_manager, table_name, column_name)
        
        return column_info
    
    def _create_base_column_info(self, row: dict) -> dict:
        """创建列的基础信息"""
        column_info = {
            "name": row["column_name"],
            "data_type": row["data_type"],
            "is_nullable": row["is_nullable"] == "YES",
            "is_primary": row["column_key"] == "PRI",
            "is_foreign": None,
            "category": None,
            "entropy_level": None,
            "sample_values": [],
            "business_desc": ""
        }
        
        # 处理业务描述
        use_db_comments = True
        if use_db_comments == True:
            column_info["business_desc"] = row.get("column_comment", "") or ""
            
        return column_info
    
    def _check_foreign_key(self, db_manager: DatabaseManager, table_name: str, column_name: str) -> Optional[bool]:
        """检查列是否为外键"""
        try:
            sql = f"""
            SELECT COUNT(*) as fk_count
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE 
            WHERE TABLE_SCHEMA = '{db_manager.database}' 
              AND TABLE_NAME = '{table_name}'
              AND COLUMN_NAME = '{column_name}'
              AND REFERENCED_TABLE_NAME IS NOT NULL
            """
            
            result = db_manager.execute_sql_safe(sql)
            if result.get("success") and result.get("data"):
                return result["data"][0]["fk_count"] > 0
            return None
            
        except Exception as e:
            self.logger.warning(f"检查外键失败 {table_name}.{column_name}: {e}")
            return None
    
    def _calculate_entropy_level(self, db_manager: DatabaseManager, table_name: str, column_name: str) -> Optional[str]:
        """计算列的熵值等级 - 采样500个数据计算熵，注意如果是空则设置为低"""
        try:
            # 先检查是否有数据
            count_sql = f"SELECT COUNT(*) as total_count FROM {table_name}"
            count_result = db_manager.execute_sql_safe(count_sql)
            if not (count_result.get("success") and count_result.get("data")):
                return "low"
            
            total_count = count_result["data"][0]["total_count"]
            if total_count == 0:
                return "low"
            
            # 采样500个数据
            sample_sql = f"SELECT {column_name} FROM {table_name} WHERE {column_name} IS NOT NULL LIMIT 500"
            sample_result = db_manager.execute_sql_safe(sample_sql)
            
            if not (sample_result.get("success") and sample_result.get("data")):
                return "low"
            
            # 计算唯一值比例
            values = [row[column_name] for row in sample_result["data"] if row[column_name] is not None]
            if not values:
                return "low"
            
            unique_values = len(set(values))
            total_values = len(values)
            unique_ratio = unique_values / total_values
            
            # 根据唯一值比例判断熵值等级
            if unique_ratio >= 0.8:
                return "high"
            elif unique_ratio >= 0.4:
                return "medium"
            else:
                return "low"
                
        except Exception as e:
            self.logger.warning(f"计算熵值失败 {table_name}.{column_name}: {e}")
            return "low"
    
    def _collect_sample_values(self, db_manager: DatabaseManager, table_name: str, column_name: str) -> List:
        """采集样本值 - 每列采集100个不重复值"""
        try:
            sql = f"SELECT DISTINCT {column_name} FROM {table_name} WHERE {column_name} IS NOT NULL LIMIT 100"
            result = db_manager.execute_sql_safe(sql)
            
            if result.get("success") and result.get("data"):
                return [row[column_name] for row in result["data"] if row[column_name] is not None]
            # 如果没有获取到内容，记录日志但不中断程序
            self.logger.warning(f"表 {table_name} 列 {column_name} 没有数据: {result.get('error', '查询结果为空')}") 
            return []
            
        except Exception as e:
            self.logger.warning(f"采集样本值失败 {table_name}.{column_name}: {e}")
            return []
    
    def _store_to_neo4j(self, raw_data: Dict[str, Any]) -> None:
        """直接存储到Neo4j图结构 - 按设计文档Neo4j结构"""
        # 简单验证: 需要Neo4j连接
        if not self.memory_manager or not getattr(self.memory_manager, 'neo4j_graph', None):
            raise Exception("Neo4j连接不可用，无法存储schema信息")
        
        try:
            neo4j_graph = self.memory_manager.neo4j_graph
            database_info = raw_data["database_info"]
            tables_data = raw_data["tables_data"]
            
            # 1. 创建Database节点
            self._create_database_node(neo4j_graph, database_info)
            
            # 2. 创建Table节点和关系
            for table_data in tables_data:
                self._create_table_node(neo4j_graph, database_info["name"], table_data)
                
                # 3. 创建Column节点和关系
                for column_data in table_data["columns"]:
                    self._create_column_node(neo4j_graph, table_data["name"], column_data)
            
            self.logger.info(f"💾 成功存储到Neo4j: 1个数据库, {len(tables_data)}个表, {sum(len(t['columns']) for t in tables_data)}个列")
            
        except Exception as e:
            self.logger.error(f"❌ Neo4j存储失败: {e}")
            raise
    
    def _create_database_node(self, neo4j_graph, database_info: Dict[str, Any]) -> None:
        """创建Database节点"""
        cypher = """
        MERGE (d:Database {name: $name})
        SET d.business_desc = $business_desc
        """
        
        neo4j_graph.query(cypher, {
            "name": database_info["name"],
            "business_desc": database_info["business_desc"]
        })
    
    def _create_table_node(self, neo4j_graph, database_name: str, table_data: Dict[str, Any]) -> None:
        """创建Table节点和CONTAINS关系"""
        cypher = """
        MATCH (d:Database {name: $database_name})
        MERGE (t:Table {name: $table_name})
        SET t.row_count = $row_count,
            t.business_desc = $business_desc
        MERGE (d)-[:CONTAINS]->(t)
        """
        
        neo4j_graph.query(cypher, {
            "database_name": database_name,
            "table_name": table_data["name"],
            "row_count": table_data["row_count"],
            "business_desc": table_data["business_desc"]
        })
    
    def _create_column_node(self, neo4j_graph, table_name: str, column_data: Dict[str, Any]) -> None:
        """创建Column节点和HAS_COLUMN关系"""
        cypher = """
        MATCH (t:Table {name: $table_name})
        MERGE (c:Column {name: $column_name})
        SET c.data_type = $data_type,
            c.is_nullable = $is_nullable,
            c.is_primary = $is_primary,
            c.is_foreign = $is_foreign,
            c.category = $category,
            c.entropy_level = $entropy_level,
            c.sample_values = $sample_values,
            c.business_desc = $business_desc
        MERGE (t)-[:HAS_COLUMN]->(c)
        """
        
        neo4j_graph.query(cypher, {
            "table_name": table_name,
            "column_name": column_data["name"],
            "data_type": column_data["data_type"],
            "is_nullable": column_data["is_nullable"],
            "is_primary": column_data["is_primary"],
            "is_foreign": column_data["is_foreign"],
            "category": column_data["category"],
            "entropy_level": column_data["entropy_level"],
            "sample_values": column_data["sample_values"],
            "business_desc": column_data["business_desc"]
        })


# ========== 便利函数 ==========
def create_schema_extraction_tool(
    memory_manager: Optional['Neo4jMemoryManager'] = None,
    database_manager: Optional['DatabaseManager'] = None
) -> SchemaExtractionTool:
    """创建Schema提取工具的便利函数
    
    Args:
        memory_manager: Neo4j记忆管理器
        database_manager: 数据库管理器
        
    Returns:
        配置好的Schema提取工具
    """
    return SchemaExtractionTool(
        memory_manager=memory_manager,
        database_manager=database_manager
    )
