"""
同步版本的数据库连接管理器
"""

import logging
from typing import Dict, Any, Optional, List
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from config.trae_config import DatabaseConfig


class DatabaseManager:
    """同步版本的数据库管理器"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.engine = None
        self.session_factory = None
        self.logger = logging.getLogger(__name__)
        
        # 验证配置
        if not self.config.database:
            raise ValueError("数据库名称不能为空")
        
        self.logger.info(f"初始化数据库管理器: {config.type}://{config.host}:{config.port}/{config.database}")
    
    def initialize(self) -> bool:
        """初始化数据库连接"""
        try:
            connection_string = self._build_connection_string()
            self.engine = create_engine(
                connection_string,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_timeout=self.config.pool_timeout,
                pool_recycle=self.config.pool_recycle,
                echo=True
            )
            
            # 测试连接
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                
            self.session_factory = sessionmaker(bind=self.engine)
            self.logger.info("数据库连接成功")
            return True
            
        except Exception as e:
            self.logger.error(f"数据库连接失败: {e}")
            return False
    
    def _build_connection_string(self) -> str:
        """构建数据库连接字符串"""
        if self.config.type == "mysql":
            return f"mysql+pymysql://{self.config.username}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database}?charset={self.config.charset}"
        elif self.config.type == "postgresql":
            return f"postgresql://{self.config.username}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database}"
        elif self.config.type == "sqlite":
            return f"sqlite:///{self.config.database}.db"
        else:
            raise ValueError(f"不支持的数据库类型: {self.config.type}")
    
    def get_tables(self) -> List[str]:
        """获取所有表名"""
        try:
            with self.engine.connect() as conn:
                if self.config.type == "mysql":
                    result = conn.execute(text("SHOW TABLES"))
                    return [row[0] for row in result.fetchall()]
                elif self.config.type == "postgresql":
                    result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
                    return [row[0] for row in result.fetchall()]
                elif self.config.type == "sqlite":
                    result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
                    return [row[0] for row in result.fetchall()]
        except Exception as e:
            self.logger.error(f"获取表列表失败: {e}")
            return []
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """获取表信息"""
        try:
            with self.engine.connect() as conn:
                info = {"name": table_name, "columns": []}
                
                if self.config.type == "mysql":
                    # 获取列信息
                    result = conn.execute(text(f"DESCRIBE {table_name}"))
                    for row in result.fetchall():
                        info["columns"].append({
                            "name": row[0],
                            "type": str(row[1]),
                            "nullable": row[2] == "YES",
                            "key": row[3],
                            "default": row[4]
                        })
                elif self.config.type == "postgresql":
                    result = conn.execute(text(f"SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = '{table_name}'"))
                    for row in result.fetchall():
                        info["columns"].append({
                            "name": row[0],
                            "type": str(row[1]),
                            "nullable": row[2] == "YES"
                        })
                
                return info
                
        except Exception as e:
            self.logger.error(f"获取表信息失败: {e}")
            return {"name": table_name, "columns": []}
    
    def get_database_info(self) -> Dict[str, Any]:
        """获取数据库信息"""
        try:
            with self.engine.connect() as conn:
                tables = self.get_tables()
                
                # 获取数据库版本
                version = "unknown"
                try:
                    if self.config.type == "mysql":
                        result = conn.execute(text("SELECT VERSION()"))
                        version = result.scalar()
                    elif self.config.type == "postgresql":
                        result = conn.execute(text("SELECT version()"))
                        version = result.scalar().split()[1]
                except:
                    pass
                
                return {
                    "database": self.config.database,
                    "type": self.config.type,
                    "host": f"{self.config.host}:{self.config.port}",
                    "tables_count": len(tables),
                    "tables": tables,
                    "version": version
                }
                
        except Exception as e:
            self.logger.error(f"获取数据库信息失败: {e}")
            return {
                "database": self.config.database,
                "type": self.config.type,
                "error": str(e)
            }
    
    def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                return True
        except Exception:
            return False
    
    def execute_query(self, sql: str, params: Optional[Dict] = None, fetch: bool = True) -> Dict[str, Any]:
        """
        执行SQL查询
        
        Args:
            sql: SQL查询语句
            params: 查询参数
            fetch: 是否获取结果
            
        Returns:
            查询结果字典
        """
        try:
            with self.engine.connect() as conn:
                # 执行查询
                if params:
                    result = conn.execute(text(sql), params)
                else:
                    result = conn.execute(text(sql))
                
                if fetch and result.returns_rows:
                    # 获取结果
                    rows = result.fetchall()
                    columns = result.keys()
                    
                    # 转换为字典列表
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
                    # 对于非查询语句（INSERT, UPDATE, DELETE等）
                    return {
                        "success": True,
                        "affected_rows": result.rowcount if hasattr(result, 'rowcount') else 0,
                        "sql": sql
                    }
                    
        except SQLAlchemyError as e:
            self.logger.error(f"SQL执行失败: {sql}, 错误: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "SQLAlchemyError",
                "sql": sql
            }
        except Exception as e:
            self.logger.error(f"查询执行失败: {sql}, 错误: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "sql": sql
            }
    
    def execute_sql_safe(self, sql: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        安全执行SQL（只允许SELECT查询）
        
        Args:
            sql: SQL查询语句
            dry_run: 是否为试运行
            
        Returns:
            执行结果
        """
        # 清理SQL语句
        sql_clean = sql.strip().rstrip(';')
        sql_upper = sql_clean.upper()
        
        # 安全检查：只允许SELECT语句
        if not sql_upper.startswith('SELECT'):
            return {
                "success": False,
                "error": "为安全起见，只允许执行SELECT查询",
                "error_type": "SecurityError",
                "sql": sql
            }
        
        # 检查是否包含危险操作
        dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE']
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                return {
                    "success": False,
                    "error": f"SQL包含危险关键字: {keyword}",
                    "error_type": "SecurityError", 
                    "sql": sql
                }
        
        if dry_run:
            # 试运行：使用EXPLAIN检查SQL语法
            try:
                explain_sql = f"EXPLAIN {sql_clean}"
                result = self.execute_query(explain_sql, fetch=True)
                if result["success"]:
                    return {
                        "success": True,
                        "dry_run": True,
                        "sql": sql,
                        "message": "SQL语法检查通过"
                    }
                else:
                    return result
            except Exception as e:
                return {
                    "success": False,
                    "error": f"SQL语法检查失败: {e}",
                    "error_type": "SyntaxError",
                    "sql": sql
                }
        else:
            # 实际执行
            return self.execute_query(sql)
    
    def close(self):
        """关闭数据库连接"""
        if self.engine:
            self.engine.dispose()
            self.logger.info("数据库连接已关闭")