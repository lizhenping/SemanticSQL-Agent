"""数据库管理（infra/database.py）

设计原则：
- YAGNI：删 Neo4j 支持（424 行死代码），只保留 MySQL + SQLite
- DRY：database_manager 不再每个工具各自初始化，通过依赖注入
- 可测试性：可注入 FakeDatabaseManager

迁移自 utils/database.py，核心逻辑保留，删除 Neo4j 相关注释和配置。
新增 SQLite 文件路径直连支持（论文数据集全部是 sqlite）。
"""

import logging
from typing import Any, Dict, Optional, Union, TYPE_CHECKING

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel, Field

from models.exceptions import (
    DatabaseConnectionError,
    SQLExecutionError,
    SchemaExtractionError,
)
from models.diagnosis import ErrorType

if TYPE_CHECKING:
    from config.settings import Settings


# ========== 数据模型 ==========

class DatabaseInfo(BaseModel):
    """数据库信息模型"""

    name: str = Field(description="数据库名称")
    tables: list[str] = Field(default_factory=list, description="表名列表")
    schema_info: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="表结构信息"
    )
    connection_params: Dict[str, Any] = Field(
        default_factory=dict, description="连接参数"
    )


# ========== Schema 提取器 ==========

class SchemaExtractor:
    """数据库模式提取器（迁自 utils/database.py）

    职责：
    - 从数据库中提取表和列的结构信息
    - 处理列类型、约束、默认值等元数据
    - 构建标准化的数据库信息对象
    """

    def __init__(self, engine, logger):
        self.engine = engine
        self.logger = logger

    def extract_schema(self, database_name: str) -> DatabaseInfo:
        """提取数据库结构信息"""
        try:
            inspector = inspect(self.engine)
            table_names = inspector.get_table_names()
            schema_info, total_columns = self._build_schema_info(inspector, table_names)
            database_info = self._create_database_info(
                database_name, table_names, schema_info
            )
            self.logger.info(
                f"📊 提取数据库结构: {len(table_names)} 表, {total_columns} 列"
            )
            return database_info
        except Exception as e:
            self.logger.error(f"❌ 数据库结构提取失败: {e}")
            raise SchemaExtractionError(database_name, str(e))

    def _build_schema_info(self, inspector, table_names: list) -> tuple:
        schema_info = {}
        total_columns = 0
        for table_name in table_names:
            table_info, column_count = self._extract_table_info(inspector, table_name)
            schema_info[table_name] = table_info
            total_columns += column_count
        return schema_info, total_columns

    def _extract_table_info(self, inspector, table_name: str) -> tuple:
        columns = inspector.get_columns(table_name)
        column_info = [self._extract_column_info(column) for column in columns]
        return {
            "columns": column_info,
            "primary_keys": [c["name"] for c in column_info if c["primary_key"]],
            "column_count": len(column_info),
        }, len(column_info)

    def _extract_column_info(self, column: dict) -> dict:
        return {
            "name": column["name"],
            "type": self._normalize_column_type(column["type"]),
            "nullable": column.get("nullable", True),
            "primary_key": column.get("primary_key", False),
            "default": self._normalize_default_value(column.get("default")),
        }

    def _create_database_info(
        self, database_name: str, table_names: list, schema_info: dict
    ) -> DatabaseInfo:
        return DatabaseInfo(
            name=database_name,
            tables=list(table_names),
            schema_info=schema_info,
            connection_params={},
        )

    def _normalize_column_type(self, column_type) -> str:
        try:
            type_str = str(column_type)
            if "enum(" in type_str.lower():
                import re
                enum_match = re.search(r"enum\((.*?)\)", type_str, re.IGNORECASE)
                if enum_match:
                    return f"ENUM({enum_match.group(1)})"
            return type_str.replace('"', "").replace("'", "")
        except Exception:
            return "UNKNOWN"

    def _normalize_default_value(self, default_value) -> Union[str, None]:
        if default_value is None:
            return None
        try:
            if hasattr(default_value, "__call__"):
                return str(default_value)
            return str(default_value)
        except Exception:
            return None


# ========== SQL 执行器 ==========

class SQLExecutor:
    """安全 SQL 执行器（迁自 utils/database.py）

    职责：
    - 安全执行 SELECT（仅允许查询）
    - 结果标准化
    """

    def __init__(self, engine, logger):
        self.engine = engine
        self.logger = logger

    def execute_safe(self, sql: str, limit: int = 100) -> Dict[str, Any]:
        """安全执行 SQL 查询 - 仅允许 SELECT"""
        sql_clean = self._prepare_sql(sql, limit)
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
        sql_clean = sql.strip().rstrip(";")
        if "LIMIT" not in sql_clean.upper():
            sql_clean = f"{sql_clean} LIMIT {limit}"
        return sql_clean

    def _process_query_result(self, result, sql_clean: str) -> Dict[str, Any]:
        if not result.returns_rows:
            return {"success": True, "message": "查询执行成功，无返回数据", "sql": sql_clean}
        rows = result.fetchall()
        columns = list(result.keys())
        data = [self._row_to_dict(row, columns) for row in rows]
        return {"success": True, "data": data, "row_count": len(data), "columns": columns, "sql": sql_clean}

    def _row_to_dict(self, row, columns: list) -> Dict[str, Any]:
        return {columns[i]: self._normalize_query_value(row[i]) for i in range(len(columns))}

    def _normalize_query_value(self, value) -> Any:
        try:
            if hasattr(value, "isoformat"):
                return value.isoformat()
            if hasattr(value, "__float__"):
                return float(value)
            if isinstance(value, bytes):
                try:
                    return value.decode("utf-8")
                except:
                    return str(value)
            return value
        except Exception:
            return str(value) if value is not None else None


# ========== 数据库管理器 ==========

class DatabaseManager:
    """数据库连接管理器（MySQL + SQLite，删 Neo4j）

    核心职责：
    - 数据库连接的初始化和管理
    - 提供高层次 schema 提取和 SQL 执行接口
    - 资源清理

    用法：
        # 从 Settings 创建（MySQL）
        db = DatabaseManager.from_settings(settings)
        db.initialize()

        # 直接指定 SQLite 文件路径
        db = DatabaseManager.for_sqlite("path/to/db.sqlite")
    """

    def __init__(self, settings: Optional["Settings"] = None):
        self.logger = logging.getLogger(__name__)
        if settings is None:
            from config.settings import Settings
            settings = Settings()

        self.db_type = settings.db_type.lower()
        self.host = settings.db_host
        self.port = settings.db_port
        self.database = settings.db_database
        self.username = settings.db_username
        self.password = settings.db_password
        self.engine = None
        self.session_factory = None

    @classmethod
    def from_settings(cls, settings: Optional["Settings"] = None) -> "DatabaseManager":
        """工厂：从 Settings 创建"""
        return cls(settings)

    @classmethod
    def for_sqlite(cls, sqlite_path: str) -> "DatabaseManager":
        """工厂：直接指定 SQLite 文件路径（论文数据集全部是 sqlite）

        绕过 Settings，直接连接 sqlite 文件。
        """
        import types
        fake_settings = types.SimpleNamespace(
            db_type="sqlite",
            db_host="",
            db_port=0,
            db_database=sqlite_path,
            db_username="",
            db_password="",
        )
        return cls(fake_settings)

    def initialize(self) -> bool:
        """初始化数据库连接并测试连通性"""
        try:
            connection_string = self._build_connection_string()
            self.engine = create_engine(
                connection_string,
                pool_pre_ping=True,
                echo=False,
            )
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            self.session_factory = sessionmaker(bind=self.engine)
            self.logger.info(f"✅ 数据库连接成功: {self.db_type}://{self.database}")
            return True
        except Exception as e:
            self.logger.error(f"❌ 数据库连接失败: {e}")
            raise DatabaseConnectionError(
                self.db_type,
                {"host": self.host, "port": self.port, "database": self.database, "error": str(e)},
            )

    def extract_database_schema(self) -> DatabaseInfo:
        """提取数据库结构信息"""
        if not self.engine:
            raise SchemaExtractionError(self.database, "数据库连接未初始化")
        extractor = SchemaExtractor(self.engine, self.logger)
        database_info = extractor.extract_schema(self.database)
        database_info.connection_params = self._get_connection_params()
        return database_info

    def execute_sql_safe(self, sql: str, limit: int = 100) -> Dict[str, Any]:
        """安全执行 SQL 查询（仅 SELECT）"""
        if not self.engine:
            raise SQLExecutionError(sql, "数据库连接未初始化", "ConnectionError")
        executor = SQLExecutor(self.engine, self.logger)
        return executor.execute_safe(sql, limit)

    def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            if not self.engine:
                return False
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def close(self) -> None:
        """关闭数据库连接"""
        if self.engine:
            self.engine.dispose()
            self.logger.info("🔒 数据库连接已关闭")

    def _build_connection_string(self) -> str:
        """构建连接字符串（MySQL / SQLite，删 PostgreSQL/Neo4j）"""
        if self.db_type == "mysql":
            return f"mysql+pymysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}?charset=utf8mb4"
        elif self.db_type == "sqlite":
            return f"sqlite:///{self.database}"
        else:
            raise ValueError(f"不支持的数据库类型: {self.db_type}（仅支持 mysql/sqlite）")

    def _get_connection_params(self) -> Dict[str, Any]:
        return {"host": self.host, "port": self.port, "database": self.database, "type": self.db_type}


# ========== 错误分类函数（迁自 sql_execute._classify_error）==========

def classify_sql_error(error_msg: str) -> ErrorType:
    """把 DB 错误字符串映射到 ErrorType

    供 Phase 3 的 execution_check 使用。
    """
    error_msg_lower = error_msg.lower()
    if "unknown column" in error_msg_lower or ("column" in error_msg_lower and "not found" in error_msg_lower):
        return ErrorType.COLUMN_NOT_FOUND
    elif "table" in error_msg_lower and ("doesn't exist" in error_msg_lower or "not found" in error_msg_lower):
        return ErrorType.TABLE_NOT_FOUND
    elif "syntax error" in error_msg_lower or "sql syntax" in error_msg_lower:
        return ErrorType.SYNTAX_ERROR
    elif "data type" in error_msg_lower or "type mismatch" in error_msg_lower:
        return ErrorType.TYPE_ERROR
    elif "ambiguous" in error_msg_lower:
        return ErrorType.COLUMN_NOT_FOUND  # ambiguous column 归类为列问题
    elif "join" in error_msg_lower:
        return ErrorType.JOIN_INVALID
    else:
        return ErrorType.EXECUTION_FAILED


# ========== 便利函数 ==========

def create_database_manager(settings: Optional["Settings"] = None) -> Optional[DatabaseManager]:
    """创建数据库管理器的便利函数"""
    try:
        manager = DatabaseManager.from_settings(settings)
        if manager.initialize():
            return manager
        return None
    except Exception as e:
        logging.getLogger(__name__).error(f"数据库管理器创建失败: {e}")
        return None
