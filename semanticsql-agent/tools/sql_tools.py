"""
SQL相关工具实现 - 基于trae_agent风格
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from langchain_community.utilities import SQLDatabase

from .trae_base_tool import TraeBaseTool, ToolParameter
from ..config.database_models import DatabaseConfig


class SchemaExtractionTool(TraeBaseTool):
    """数据库Schema提取工具"""
    
    def __init__(self, database_config: DatabaseConfig):
        super().__init__(
            name="extract_schema",
            description="提取数据库的表结构、字段信息和关系"
        )
        self.database_config = database_config
        self.db = None
        self._init_database()
    
    def _init_database(self):
        """初始化数据库连接"""
        try:
            engine = create_engine(self.database_config.connection_string)
            self.db = SQLDatabase.from_uri(
                self.database_config.connection_string,
                include_tables=self.database_config.include_tables,
                exclude_tables=self.database_config.exclude_tables,
                sample_rows_in_table_info=self.database_config.sample_rows_in_table_info
            )
        except Exception as e:
            self.logger.error(f"数据库连接失败: {e}")
            raise
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="include_indexes",
                type="boolean",
                description="是否包含索引信息",
                required=False,
                default=False
            ),
            ToolParameter(
                name="include_constraints",
                type="boolean", 
                description="是否包含约束信息",
                required=False,
                default=True
            ),
            ToolParameter(
                name="table_name",
                type="string",
                description="指定表名（可选，不指定则提取所有表）",
                required=False
            )
        ]
    
    async def execute(self, include_indexes: bool = False, include_constraints: bool = True, table_name: str = None) -> Dict[str, Any]:
        """执行Schema提取"""
        try:
            if table_name:
                return await self._extract_single_table(table_name, include_indexes, include_constraints)
            else:
                return await self._extract_all_tables(include_indexes, include_constraints)
                
        except Exception as e:
            self.logger.error(f"Schema提取失败: {e}")
            return self.format_error(str(e))
    
    async def _extract_all_tables(self, include_indexes: bool, include_constraints: bool) -> Dict[str, Any]:
        """提取所有表信息"""
        try:
            tables = self.db.get_table_names()
            
            schema_info = {
                "database": self.database_config.database,
                "tables": {},
                "total_tables": len(tables)
            }
            
            for table in tables:
                table_info = await self._extract_table_info(table, include_indexes, include_constraints)
                schema_info["tables"][table] = table_info
            
            return self.format_result(schema_info)
            
        except Exception as e:
            raise e
    
    async def _extract_single_table(self, table_name: str, include_indexes: bool, include_constraints: bool) -> Dict[str, Any]:
        """提取单个表信息"""
        try:
            if table_name not in self.db.get_table_names():
                return self.format_error(f"表 {table_name} 不存在")
            
            table_info = await self._extract_table_info(table_name, include_indexes, include_constraints)
            return self.format_result(table_info)
            
        except Exception as e:
            raise e
    
    async def _extract_table_info(self, table_name: str, include_indexes: bool, include_constraints: bool) -> Dict[str, Any]:
        """提取表详细信息"""
        try:
            # 获取表信息
            table_info = self.db.get_table_info_no_throw([table_name])
            
            # 获取列信息
            columns = self.db._execute(
                text(f"DESCRIBE {table_name}")
            ).fetchall()
            
            # 构建列信息
            column_info = []
            for col in columns:
                column_info.append({
                    "name": col[0],
                    "type": col[1],
                    "nullable": col[2] == "YES",
                    "key": col[3],
                    "default": col[4],
                    "extra": col[5]
                })
            
            # 获取索引信息
            indexes = []
            if include_indexes:
                indexes = self.db._execute(
                    text(f"SHOW INDEX FROM {table_name}")
                ).fetchall()
            
            # 获取约束信息
            constraints = []
            if include_constraints:
                constraints = self.db._execute(
                    text(f"SELECT * FROM information_schema.TABLE_CONSTRAINTS WHERE table_name = '{table_name}'")
                ).fetchall()
            
            return {
                "name": table_name,
                "columns": column_info,
                "indexes": [dict(idx) for idx in indexes] if indexes else [],
                "constraints": [dict(constraint) for constraint in constraints] if constraints else [],
                "sample_data": self.db.run(f"SELECT * FROM {table_name} LIMIT 3")
            }
            
        except Exception as e:
            return {
                "name": table_name,
                "error": str(e),
                "columns": [],
                "indexes": [],
                "constraints": []
            }


class SQLGenerationTool(TraeBaseTool):
    """SQL生成工具"""
    
    def __init__(self, database_config: DatabaseConfig, schema_info: Dict[str, Any] = None):
        super().__init__(
            name="generate_sql",
            description="根据自然语言生成SQL查询"
        )
        self.database_config = database_config
        self.schema_info = schema_info
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="query",
                type="string",
                description="自然语言查询描述",
                required=True
            ),
            ToolParameter(
                name="context",
                type="object",
                description="额外的上下文信息",
                required=False
            ),
            ToolParameter(
                name="max_complexity",
                type="integer",
                description="最大查询复杂度",
                required=False,
                default=5
            )
        ]
    
    async def execute(self, query: str, context: Dict[str, Any] = None, max_complexity: int = 5) -> Dict[str, Any]:
        """生成SQL查询"""
        try:
            # 构建提示
            prompt = self._build_generation_prompt(query, context or {}, max_complexity)
            
            # 这里应该调用LLM生成SQL
            # 暂时返回模拟结果
            sql = self._mock_generate_sql(query, context or {})
            
            return self.format_result({
                "query": query,
                "sql": sql,
                "complexity": max_complexity,
                "generated_at": datetime.now().isoformat()
            })
            
        except Exception as e:
            return self.format_error(str(e))
    
    def _build_generation_prompt(self, query: str, context: Dict[str, Any], max_complexity: int) -> str:
        """构建SQL生成提示"""
        schema_context = json.dumps(self.schema_info or {}, indent=2, ensure_ascii=False)
        
        return f"""基于以下数据库Schema，将自然语言查询转换为SQL：

数据库Schema：
{schema_context}

自然语言查询：{query}

请生成合适的SQL查询，复杂度不超过{max_complexity}。

要求：
1. 使用正确的表名和列名
2. 考虑数据类型约束
3. 添加必要的JOIN条件
4. 使用适当的聚合函数
5. 确保查询性能合理

只返回SQL查询，不要添加解释。"""
    
    def _mock_generate_sql(self, query: str, context: Dict[str, Any]) -> str:
        """模拟SQL生成（实际应调用LLM）"""
        # 根据查询内容返回不同的SQL
        query_lower = query.lower()
        
        if "用户" in query_lower and "数量" in query_lower:
            return "SELECT COUNT(*) as user_count FROM users"
        elif "订单" in query_lower and "总额" in query_lower:
            return "SELECT SUM(total_amount) as total_orders FROM orders"
        elif "产品" in query_lower and "销量" in query_lower:
            return "SELECT product_name, SUM(quantity) as total_sold FROM order_items oi JOIN products p ON oi.product_id = p.id GROUP BY product_name ORDER BY total_sold DESC LIMIT 10"
        else:
            return f"-- 基于查询: {query}\nSELECT * FROM information LIMIT 10"


class SQLValidationTool(TraeBaseTool):
    """SQL验证工具"""
    
    def __init__(self, database_config: DatabaseConfig):
        super().__init__(
            name="validate_sql",
            description="验证SQL查询的语法和逻辑"
        )
        self.database_config = database_config
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="sql",
                type="string",
                description="需要验证的SQL查询",
                required=True
            ),
            ToolParameter(
                name="check_tables",
                type="boolean",
                description="检查表和列是否存在",
                required=False,
                default=True
            ),
            ToolParameter(
                name="check_permissions",
                type="boolean",
                description="检查查询权限",
                required=False,
                default=False
            )
        ]
    
    async def execute(self, sql: str, check_tables: bool = True, check_permissions: bool = False) -> Dict[str, Any]:
        """执行SQL验证"""
        try:
            # 创建临时的只读连接
            engine = create_engine(self.database_config.connection_string)
            
            validation_result = {
                "sql": sql,
                "is_valid": False,
                "errors": [],
                "warnings": [],
                "estimated_cost": "unknown"
            }
            
            # 语法检查
            try:
                with engine.connect() as conn:
                    # EXPLAIN查询来检查语法和获取执行计划
                    explain_sql = f"EXPLAIN {sql}"
                    result = conn.execute(text(explain_sql))
                    validation_result["is_valid"] = True
                    
                    # 获取执行计划信息
                    plan_info = result.fetchall()
                    validation_result["execution_plan"] = [dict(row) for row in plan_info]
                    
            except SQLAlchemyError as e:
                validation_result["errors"].append(str(e))
                validation_result["is_valid"] = False
            
            # 表和列检查
            if check_tables and validation_result["is_valid"]:
                # 这里可以添加更详细的表和列验证
                validation_result["warnings"].append("表和列验证功能待实现")
            
            return self.format_result(validation_result)
            
        except Exception as e:
            return self.format_error(str(e))


class SQLExecutionTool(TraeBaseTool):
    """SQL执行工具"""
    
    def __init__(self, database_config: DatabaseConfig):
        super().__init__(
            name="execute_sql",
            description="执行SQL查询并返回结果"
        )
        self.database_config = database_config
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="sql",
                type="string",
                description="要执行的SQL查询",
                required=True
            ),
            ToolParameter(
                name="max_rows",
                type="integer",
                description="最大返回行数",
                required=False,
                default=1000
            ),
            ToolParameter(
                name="include_metadata",
                type="boolean",
                description="是否包含元数据",
                required=False,
                default=True
            )
        ]
    
    async def execute(self, sql: str, max_rows: int = 1000, include_metadata: bool = True) -> Dict[str, Any]:
        """执行SQL查询"""
        try:
            engine = create_engine(self.database_config.connection_string)
            
            # 安全检查：只允许SELECT查询
            sql_upper = sql.strip().upper()
            if not sql_upper.startswith("SELECT"):
                return self.format_error("只允许执行SELECT查询")
            
            # 添加LIMIT限制
            if "LIMIT" not in sql_upper:
                sql = f"{sql} LIMIT {max_rows}"
            
            with engine.connect() as conn:
                result = conn.execute(text(sql))
                
                # 获取结果
                rows = result.fetchall()
                columns = list(result.keys())
                
                # 格式化结果
                data = []
                for row in rows:
                    data.append(dict(zip(columns, row)))
                
                execution_result = {
                    "sql": sql,
                    "row_count": len(data),
                    "columns": columns,
                    "data": data,
                    "execution_time": 0.0,  # 实际应计算执行时间
                    "truncated": len(data) >= max_rows
                }
                
                if include_metadata:
                    execution_result.update({
                        "database": self.database_config.database,
                        "timestamp": datetime.now().isoformat()
                    })
                
                return self.format_result(execution_result)
                
        except Exception as e:
            return self.format_error(str(e))