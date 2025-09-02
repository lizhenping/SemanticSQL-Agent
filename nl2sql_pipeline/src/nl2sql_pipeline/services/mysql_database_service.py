"""MySQL数据库服务实现

基于PyMySQL的MySQL数据库服务具体实现。

注意：此文件已重构为模块化结构，详见 mysql/ 目录
"""

# 导入重构后的模块
from .mysql import (
    MySQLDatabaseService,
    MySQLConnectionManager,
    MySQLQueryExecutor,
    MySQLSchemaInspector,
    PaginatedResults
)

# 保持向后兼容，默认导出主服务类
__all__ = ['MySQLDatabaseService']