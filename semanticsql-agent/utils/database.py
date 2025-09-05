"""
Simplified database connection management
Based on the design specification - combines connection_manager functionality
"""

import logging
from typing import Dict, Any, Optional, List
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from utils.database_config import DatabaseConfig


class DatabaseManager:
    """Simplified database manager"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.engine = None
        self.session_factory = None
        self.logger = logging.getLogger(__name__)
        
        # Validate configuration
        self.config.validate_connection_params()
        
        self.logger.info(f"Initializing database manager: {config.type}://{config.host}:{config.port}/{config.database}")
    
    def initialize(self) -> bool:
        """Initialize database connection"""
        try:
            connection_string = self.config.to_connection_string()
            self.engine = create_engine(
                connection_string,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_timeout=self.config.pool_timeout,
                pool_recycle=self.config.pool_recycle,
                pool_pre_ping=self.config.pool_pre_ping,
                echo=self.config.echo
            )
            
            # Test connection
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                
            self.session_factory = sessionmaker(bind=self.engine)
            self.logger.info("Database connection successful")
            return True
            
        except Exception as e:
            self.logger.error(f"Database connection failed: {e}")
            return False
    
    def get_tables(self) -> List[str]:
        """Get all table names"""
        try:
            with self.engine.connect() as conn:
                if self.config.type.value == "mysql":
                    result = conn.execute(text("SHOW TABLES"))
                    return [row[0] for row in result.fetchall()]
                elif self.config.type.value == "postgresql":
                    result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
                    return [row[0] for row in result.fetchall()]
                elif self.config.type.value == "sqlite":
                    result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
                    return [row[0] for row in result.fetchall()]
        except Exception as e:
            self.logger.error(f"Failed to get table list: {e}")
            return []
    
    def _safe_type_string(self, column_type) -> str:
        """安全地转换列类型为字符串，处理特殊字符"""
        try:
            type_str = str(column_type)
            # 清理可能导致JSON解析问题的字符
            if "enum(" in type_str.lower():
                # 提取enum值并简化格式
                import re
                enum_match = re.search(r"enum\((.*?)\)", type_str, re.IGNORECASE)
                if enum_match:
                    enum_values = enum_match.group(1)
                    # 解析enum值列表，移除引号并用逗号分隔
                    values_list = []
                    for val in enum_values.split(','):
                        clean_val = val.strip().strip("'\"")
                        if clean_val:
                            values_list.append(clean_val)
                    return f"ENUM({','.join(values_list)})"
            
            # 移除其他可能的问题字符
            return type_str.replace('"', '').replace("'", "")
        except:
            return "UNKNOWN"

    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get table information"""
        try:
            with self.engine.connect() as conn:
                info = {"name": table_name, "columns": []}
                
                if self.config.type.value == "mysql":
                    result = conn.execute(text(f"DESCRIBE {table_name}"))
                    for row in result.fetchall():
                        info["columns"].append({
                            "name": row[0],
                            "type": self._safe_type_string(row[1]),
                            "nullable": row[2] == "YES",
                            "key": row[3],
                            "default": row[4]
                        })
                elif self.config.type.value == "postgresql":
                    result = conn.execute(text(f"SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = '{table_name}'"))
                    for row in result.fetchall():
                        info["columns"].append({
                            "name": row[0],
                            "type": str(row[1]),
                            "nullable": row[2] == "YES"
                        })
                
                return info
                
        except Exception as e:
            self.logger.error(f"Failed to get table info: {e}")
            return {"name": table_name, "columns": []}
    
    def get_database_info(self) -> Dict[str, Any]:
        """Get database information"""
        try:
            with self.engine.connect() as conn:
                tables = self.get_tables()
                
                # Get database version
                version = "unknown"
                try:
                    if self.config.type.value == "mysql":
                        result = conn.execute(text("SELECT VERSION()"))
                        version = result.scalar()
                    elif self.config.type.value == "postgresql":
                        result = conn.execute(text("SELECT version()"))
                        version = result.scalar().split()[1]
                except:
                    pass
                
                return {
                    "database": self.config.database,
                    "type": self.config.type.value,
                    "host": f"{self.config.host}:{self.config.port}",
                    "tables_count": len(tables),
                    "tables": tables,
                    "version": version
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get database info: {e}")
            return {
                "database": self.config.database,
                "type": self.config.type.value,
                "error": str(e)
            }
    
    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                return True
        except Exception:
            return False
    
    def execute_sql_safe(self, sql: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Safely execute SQL (SELECT only)
        
        Args:
            sql: SQL query string
            dry_run: Whether to perform a dry run
            
        Returns:
            Execution result
        """
        # Clean SQL statement
        sql_clean = sql.strip().rstrip(';')
        sql_upper = sql_clean.upper()
        
        # Security check: only allow SELECT statements
        if not sql_upper.startswith('SELECT'):
            return {
                "success": False,
                "error": "For security reasons, only SELECT queries are allowed",
                "error_type": "SecurityError",
                "sql": sql
            }
        
        # Check for dangerous operations
        dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE']
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                return {
                    "success": False,
                    "error": f"SQL contains dangerous keyword: {keyword}",
                    "error_type": "SecurityError", 
                    "sql": sql
                }
        
        if dry_run:
            # Dry run: use EXPLAIN to check SQL syntax
            try:
                explain_sql = f"EXPLAIN {sql_clean}"
                with self.engine.connect() as conn:
                    conn.execute(text(explain_sql))
                return {
                    "success": True,
                    "dry_run": True,
                    "sql": sql,
                    "message": "SQL syntax check passed"
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"SQL syntax check failed: {e}",
                    "error_type": "SyntaxError",
                    "sql": sql
                }
        else:
            # Actual execution
            return self._execute_query(sql)
    
    def _execute_query(self, sql: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute SQL query"""
        try:
            with self.engine.connect() as conn:
                # Execute query
                if params:
                    result = conn.execute(text(sql), params)
                else:
                    result = conn.execute(text(sql))
                
                if result.returns_rows:
                    # Get results
                    rows = result.fetchall()
                    columns = result.keys()
                    
                    # Convert to dictionary list
                    data = []
                    for row in rows:
                        row_dict = {}
                        for i, column in enumerate(columns):
                            row_dict[column] = row[i]
                        data.append(row_dict)
                    
                    return {
                        "success": True,
                        "data": data,
                        "row_count": len(data),
                        "columns": list(columns),
                        "sql": sql
                    }
                else:
                    # For non-query statements (INSERT, UPDATE, DELETE, etc.)
                    return {
                        "success": True,
                        "affected_rows": result.rowcount if hasattr(result, 'rowcount') else 0,
                        "sql": sql
                    }
                    
        except SQLAlchemyError as e:
            self.logger.error(f"SQL execution failed: {sql}, error: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "SQLAlchemyError",
                "sql": sql
            }
        except Exception as e:
            self.logger.error(f"Query execution failed: {sql}, error: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "sql": sql
            }
    
    def close(self):
        """Close database connection"""
        if self.engine:
            self.engine.dispose()
            self.logger.info("Database connection closed")