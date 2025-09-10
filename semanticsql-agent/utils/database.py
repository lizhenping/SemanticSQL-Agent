"""
数据库连接管理 - SemanticSQL Agent基础设施
基于架构设计的标准数据库管理，支持MySQL + Neo4j
"""

import logging
from typing import Dict, Any, Optional, List, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from config.settings import Settings
from contextlib import contextmanager
import json

from sqlalchemy import create_engine, text, MetaData, inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel, Field

from models.exceptions import (
    DatabaseConnectionError, 
    SQLExecutionError,
    SchemaExtractionError
)


# 数据库信息模型 - 从 models/schemas.py 迁移到此处
class DatabaseInfo(BaseModel):
    """数据库信息模型"""
    
    name: str = Field(description="数据库名称")
    tables: List[str] = Field(default_factory=list, description="表名列表")
    schema_info: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="表结构信息")
    connection_params: Dict[str, Any] = Field(default_factory=dict, description="连接参数")


class DatabaseManager:
    """统一数据库管理器 - 支持MySQL/PostgreSQL数据库操作
    
    设计原则：
    - 安全第一：只允许SELECT查询，阻止危险操作
    - 结构化输出：返回标准化的数据结构
    - 错误处理：详细的错误分类和日志记录
    - 资源管理：自动连接池管理和资源清理
    - 统一配置：优先使用Settings统一配置
    """
    
    def __init__(self, settings: Optional['Settings'] = None):
        """
        初始化数据库管理器
        
        Args:
            settings: 统一配置对象（可选，默认使用全局配置）
        """
        self.logger = logging.getLogger(__name__)
        
        # 使用Settings配置
        if settings is None:
            from config.settings import get_settings
            settings = get_settings()
            
        self.db_type = settings.db_type.lower()
        self.host = settings.db_host
        self.port = settings.db_port
        self.database = settings.db_database
        self.username = settings.db_username
        self.password = settings.db_password
        self.connection_params = {
            "type": self.db_type,
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
            "password": self.password
        }
        
        self.engine = None
        self.session_factory = None
    
    def initialize(self) -> bool:
        """
        初始化数据库连接
        
        Returns:
            连接是否成功
        """
        try:
            # 构建连接字符串
            connection_string = self._build_connection_string()
            
            # 创建引擎
            self.engine = create_engine(
                connection_string,
                pool_size=5,
                max_overflow=10,
                pool_timeout=30,
                pool_recycle=3600,
                pool_pre_ping=True,
                echo=False  # 生产环境关闭SQL日志
            )
            
            # 测试连接
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            # 创建session工厂
            self.session_factory = sessionmaker(bind=self.engine)
            
            self.logger.info(f"✅ 数据库连接成功: {self.db_type}://{self.host}:{self.port}/{self.database}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 数据库连接失败: {e}")
            raise DatabaseConnectionError(self.db_type, {
                "host": self.host,
                "port": self.port,
                "database": self.database,
                "error": str(e)
            })
    
    def extract_database_schema(self) -> DatabaseInfo:
        """
        提取数据库结构信息
        
        Returns:
            数据库信息对象
        """
        if not self.engine:
            raise SchemaExtractionError(self.database, "数据库连接未初始化")
        
        try:
            inspector = inspect(self.engine)
            table_names = inspector.get_table_names()
            
            # 构建结构信息
            schema_info, total_columns = self._build_schema_info(inspector, table_names)
            
            # 创建数据库信息对象
            database_info = self._create_database_info(table_names, schema_info)
            
            self.logger.info(f"📊 提取数据库结构: {len(table_names)} 表, {total_columns} 列")
            return database_info
            
        except Exception as e:
            self.logger.error(f"❌ 数据库结构提取失败: {e}")
            raise SchemaExtractionError(self.database, str(e))
    
    def _build_schema_info(self, inspector, table_names: list) -> tuple:
        """构建数据库schema信息"""
        schema_info = {}
        total_columns = 0
        
        for table_name in table_names:
            table_info, column_count = self._extract_table_info(inspector, table_name)
            schema_info[table_name] = table_info
            total_columns += column_count
            
        return schema_info, total_columns
    
    def _extract_table_info(self, inspector, table_name: str) -> tuple:
        """提取单个表的信息"""
        columns = inspector.get_columns(table_name)
        column_info = [self._extract_column_info(column) for column in columns]
        
        return {
            "columns": column_info,
            "primary_keys": [c["name"] for c in column_info if c["primary_key"]],
            "column_count": len(column_info)
        }, len(column_info)
    
    def _extract_column_info(self, column: dict) -> dict:
        """提取列信息"""
        return {
            "name": column["name"],
            "type": self._safe_type_string(column["type"]),
            "nullable": column.get("nullable", True),
            "primary_key": column.get("primary_key", False),
            "default": self._safe_default_value(column.get("default"))
        }
    
    def _create_database_info(self, table_names: list, schema_info: dict) -> DatabaseInfo:
        """创建DatabaseInfo对象"""
        return DatabaseInfo(
            name=self.database,
            tables=list(table_names),
            schema_info=schema_info,
            connection_params={
                "host": self.host,
                "port": self.port,
                "database": self.database,
                "type": self.db_type
            }
        )
    
    def execute_sql_safe(self, sql: str, limit: int = 100) -> Dict[str, Any]:
        """
        安全执行SQL查询 - 仅允许SELECT语句
        
        Args:
            sql: SQL查询语句
            limit: 结果数量限制
            
        Returns:
            执行结果字典
        """
        # 清理和验证SQL
        sql_clean = self._prepare_sql(sql, limit)
        
        if not self._is_safe_sql(sql_clean):
            return self._create_error_response(sql_clean, "安全检查失败：只允许SELECT查询", "SecurityError")
        
        # 执行查询
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(sql_clean))
                return self._process_query_result(result, sql_clean)
                
        except SQLAlchemyError as e:
            self.logger.error(f"❌ SQL执行失败: {sql} - {e}")
            raise SQLExecutionError(sql, str(e), "SQLAlchemyError")
            
        except Exception as e:
            self.logger.error(f"❌ 查询执行异常: {sql} - {e}")
            raise SQLExecutionError(sql, str(e), type(e).__name__)
    
    def _prepare_sql(self, sql: str, limit: int) -> str:
        """准备SQL语句：清理并添加LIMIT"""
        sql_clean = sql.strip().rstrip(';')
        
        # 添加LIMIT限制
        if "LIMIT" not in sql_clean.upper():
            sql_clean = f"{sql_clean} LIMIT {limit}"
            
        return sql_clean
    
    def _create_error_response(self, sql: str, error_msg: str, error_type: str) -> Dict[str, Any]:
        """创建错误响应"""
        return {
            "success": False,
            "error": error_msg,
            "error_type": error_type,
            "sql": sql
        }
    
    def _process_query_result(self, result, sql_clean: str) -> Dict[str, Any]:
        """处理查询结果"""
        if not result.returns_rows:
            return {
                "success": True,
                "message": "查询执行成功，无返回数据",
                "sql": sql_clean
            }
        
        # 获取数据
        rows = result.fetchall()
        columns = list(result.keys())
        
        # 转换为字典列表
        data = [self._row_to_dict(row, columns) for row in rows]
        
        return {
            "success": True,
            "data": data,
            "row_count": len(data),
            "columns": columns,
            "sql": sql_clean
        }
    
    def _row_to_dict(self, row, columns: list) -> Dict[str, Any]:
        """将数据行转换为字典"""
        return {columns[i]: self._safe_value(row[i]) for i in range(len(columns))}
    
    def validate_sql_syntax(self, sql: str) -> Dict[str, Any]:
        """
        验证SQL语法 - 使用EXPLAIN进行语法检查
        
        Args:
            sql: SQL语句
            
        Returns:
            验证结果
        """
        try:
            sql_clean = sql.strip().rstrip(';')
            
            # 安全检查
            if not self._is_safe_sql(sql_clean):
                return {
                    "valid": False,
                    "error": "安全检查失败：只允许SELECT查询",
                    "error_type": "SecurityError"
                }
            
            # 语法检查
            explain_sql = f"EXPLAIN {sql_clean}"
            
            with self.engine.connect() as conn:
                conn.execute(text(explain_sql))
            
            return {
                "valid": True,
                "message": "SQL语法检查通过",
                "sql": sql_clean
            }
            
        except Exception as e:
            return {
                "valid": False,
                "error": f"SQL语法错误: {str(e)}",
                "error_type": "SyntaxError",
                "sql": sql_clean
            }
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """获取指定表的详细信息"""
        try:
            if not self.engine:
                raise SchemaExtractionError(table_name, "数据库连接未初始化")
            
            inspector = inspect(self.engine)
            
            # 检查表是否存在
            if table_name not in inspector.get_table_names():
                return {
                    "exists": False,
                    "error": f"表 {table_name} 不存在"
                }
            
            # 获取列信息
            columns = inspector.get_columns(table_name)
            column_info = []
            
            for column in columns:
                column_info.append({
                    "name": column["name"],
                    "type": self._safe_type_string(column["type"]),
                    "nullable": column.get("nullable", True),
                    "primary_key": column.get("primary_key", False),
                    "default": self._safe_default_value(column.get("default"))
                })
            
            # 获取索引信息
            indexes = inspector.get_indexes(table_name)
            
            # 获取外键信息
            foreign_keys = inspector.get_foreign_keys(table_name)
            
            return {
                "exists": True,
                "name": table_name,
                "columns": column_info,
                "column_count": len(column_info),
                "indexes": indexes,
                "foreign_keys": foreign_keys,
                "primary_keys": [c["name"] for c in column_info if c["primary_key"]]
            }
            
        except Exception as e:
            self.logger.error(f"❌ 获取表信息失败: {table_name} - {e}")
            return {
                "exists": False,
                "error": str(e)
            }
    
    def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            if not self.engine:
                return False
            
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
            
        except Exception as e:
            self.logger.warning(f"⚠️ 连接测试失败: {e}")
            return False
    
    def get_connection_info(self) -> Dict[str, Any]:
        """获取当前连接的基础信息"""
        return {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "type": self.db_type
        }
    
    def close(self) -> None:
        """关闭数据库连接"""
        if self.engine:
            self.engine.dispose()
            self.logger.info("🔒 数据库连接已关闭")
    
    # ========== 内部辅助方法 ==========
    def _build_connection_string(self) -> str:
        """构建数据库连接字符串"""
        if self.db_type == "mysql":
            return f"mysql+pymysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}?charset=utf8mb4"
        elif self.db_type == "postgresql":
            return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        elif self.db_type == "sqlite":
            return f"sqlite:///{self.database}"
        else:
            raise ValueError(f"不支持的数据库类型: {self.db_type}")
    
    def _is_safe_sql(self, sql: str) -> bool:
        """检查SQL是否安全"""
        sql_upper = sql.upper().strip()
        
        # 只允许SELECT语句
        if not sql_upper.startswith('SELECT'):
            return False
        
        # 检查危险关键词
        dangerous_keywords = [
            'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 
            'CREATE', 'TRUNCATE', 'REPLACE', 'MERGE', 'CALL',
            'EXEC', 'EXECUTE', 'LOAD_FILE', 'OUTFILE', 'DUMPFILE'
        ]
        
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                return False
        
        return True
    
    def _safe_type_string(self, column_type) -> str:
        """安全转换列类型为字符串"""
        try:
            type_str = str(column_type)
            
            # 处理ENUM类型
            if "enum(" in type_str.lower():
                import re
                enum_match = re.search(r"enum\((.*?)\)", type_str, re.IGNORECASE)
                if enum_match:
                    return f"ENUM({enum_match.group(1)})"
            
            # 清理特殊字符
            return type_str.replace('"', '').replace("'", "")
            
        except Exception:
            return "UNKNOWN"
    
    def _safe_default_value(self, default_value) -> Union[str, None]:
        """安全处理默认值"""
        if default_value is None:
            return None
        
        try:
            # 如果是可调用对象(如函数)，转换为字符串
            if hasattr(default_value, '__call__'):
                return str(default_value)
            
            return str(default_value)
        except Exception:
            return None
    
    def _safe_value(self, value) -> Any:
        """安全处理查询结果值"""
        try:
            # 处理日期时间类型
            if hasattr(value, 'isoformat'):
                return value.isoformat()
            
            # 处理Decimal类型
            if hasattr(value, '__float__'):
                return float(value)
            
            # 处理bytes类型
            if isinstance(value, bytes):
                try:
                    return value.decode('utf-8')
                except:
                    return str(value)
            
            return value
            
        except Exception:
            return str(value) if value is not None else None
    
    def _extract_foreign_keys(self, inspector, table_names: List[str]) -> List[Dict[str, Any]]:
        """提取外键关系"""
        relationships = []
        
        try:
            for table_name in table_names:
                foreign_keys = inspector.get_foreign_keys(table_name)
                
                for fk in foreign_keys:
                    relationships.append({
                        "source_table": table_name,
                        "source_columns": fk.get("constrained_columns", []),
                        "target_table": fk.get("referred_table"),
                        "target_columns": fk.get("referred_columns", []),
                        "constraint_name": fk.get("name")
                    })
                    
        except Exception as e:
            self.logger.warning(f"⚠️ 提取外键关系失败: {e}")
        
        return relationships


# ========== 便利函数 ==========
def create_database_manager(connection_params: Optional[Dict[str, Any]] = None, settings: Optional['Settings'] = None) -> DatabaseManager:
    """
    创建数据库管理器的便利函数 - 支持统一Settings配置
    
    Args:
        connection_params: 数据库连接参数 [DEPRECATED - 使用settings参数]
        settings: 统一配置对象 (推荐方式)
        
    Returns:
        初始化的数据库管理器
    """
    if settings is not None:
        manager = DatabaseManager(settings=settings)
    elif connection_params is not None:
        import warnings
        warnings.warn(
            "connection_params is deprecated. Use 'settings' parameter instead.",
            DeprecationWarning,
            stacklevel=2
        )
        manager = DatabaseManager(connection_params=connection_params)
    else:
        # 尝试使用默认配置
        from config.settings import get_settings
        default_settings = get_settings()
        manager = DatabaseManager(settings=default_settings)
    
    if not manager.initialize():
        db_type = getattr(manager, 'db_type', 'unknown')
        raise DatabaseConnectionError(
            db_type,
            {"host": getattr(manager, 'host', 'unknown'), "database": getattr(manager, 'database', 'unknown')}
        )
    
    return manager