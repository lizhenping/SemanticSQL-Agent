"""MySQL数据库服务模块

模块化的MySQL服务实现，包含：
- connectors: 连接管理组件
  - connection_manager: 连接生命周期管理
- executors: 查询执行组件
  - query_executor: SQL查询执行和结果处理
- inspectors: 架构检查组件
  - schema_inspector: 元数据获取和分析
- service: 主服务类，整合所有组件
"""

from .service import MySQLDatabaseService
from .connectors.connection_manager import MySQLConnectionManager
from .executors.query_executor import MySQLQueryExecutor, PaginatedResults
from .inspectors.schema_inspector import MySQLSchemaInspector

__all__ = [
    # 主服务类
    'MySQLDatabaseService',
    
    # 组件类（可单独使用）
    'MySQLConnectionManager',
    'MySQLQueryExecutor',
    'MySQLSchemaInspector',
    'PaginatedResults',
]