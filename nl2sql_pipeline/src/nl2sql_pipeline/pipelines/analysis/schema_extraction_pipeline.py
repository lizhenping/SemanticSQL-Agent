"""数据库架构提取管道 - 分析流程步骤1

本管道负责从数据库中提取完整的架构信息，包括：
- 表及其元数据（注释、行数等）
- 列及其属性（数据类型、是否可空、默认值等）
- 主键和外键约束
- 索引信息

这是整个分析流程的第一步，为后续的领域分析、字段分类等步骤提供基础数据。
"""

from typing import Dict, Any, TYPE_CHECKING
import logging
from dataclasses import dataclass

from ..base import Pipeline, PipelineStep
from ...models.database import DatabaseSchema, TableInfo, ColumnInfo
from ...services import ServiceContainer

if TYPE_CHECKING:
    from ...services import DatabaseService

logger = logging.getLogger(__name__)


# ========== 导入上下文模型 ==========

from ...models.pipeline_contexts import SchemaExtractionContext


# ========== 管道步骤定义 ==========

class ConnectDatabaseStep(PipelineStep):
    """连接数据库步骤
    
    建立数据库连接并验证连接是否成功。
    这是架构提取的第一步，确保后续步骤可以正常访问数据库。
    """
    
    def __init__(self, services: ServiceContainer):
        """初始化步骤
        
        参数:
            services: 服务容器
        """
        super().__init__("连接数据库")
        self.db_service = services.database_service
    
    def execute(self, context: SchemaExtractionContext) -> SchemaExtractionContext:
        """执行数据库连接
        
        参数:
            context: 包含数据库配置的上下文
            
        返回:
            包含数据库服务的上下文
            
        异常:
            DatabaseConnectionException: 连接失败时抛出
        """
        logger.info(f"正在连接数据库: {context.database_config.get('database', 'unknown')}")
        
        # 建立连接
        self.db_service.connect(**context.database_config)
        
        # 将数据库服务存储在上下文中，供后续步骤使用
        context.database_service = self.db_service
        
        logger.info("数据库连接成功")
        return context


class ExtractTablesStep(PipelineStep):
    """提取表信息步骤
    
    从数据库中获取所有表的基本信息，包括表名、注释、行数等。
    不包括列信息，列信息在下一步中获取。
    """
    
    def __init__(self):
        """初始化步骤"""
        super().__init__("提取表信息")
    
    def execute(self, context: SchemaExtractionContext) -> SchemaExtractionContext:
        """执行表信息提取
        
        参数:
            context: 架构提取上下文
            
        返回:
            包含原始表信息的上下文
        """
        logger.info("开始提取表信息")
        
        # 获取所有表名
        table_names = context.database_service.get_tables()
        
        # 构建表信息字典列表
        tables = [self._create_table_info(table_name, context.database_service) for table_name in table_names]
        
        # 保存原始信息
        context.raw_schema_info = {'tables': tables}
        logger.info(f"成功提取 {len(tables)} 个表的信息")
        
        return context
    
    def _create_table_info(self, table_name: str, database_service: 'DatabaseService') -> Dict[str, Any]:
        """创建单个表的信息字典
        
        参数:
            table_name: 表名
            database_service: 数据库服务
            
        返回:
            表信息字典
        """
        return {
            'name': table_name,
            'comment': database_service.get_table_comment(table_name) or '',
            'columns': [],  # 将在下一步填充
            'primary_key': None,  # 将在下一步填充
            'foreign_keys': []  # 将在下一步填充
        }


class ExtractColumnsStep(PipelineStep):
    """提取列信息步骤
    
    为每个表提取详细的列信息，包括：
    - 列名和数据类型
    - 是否可空、是否有默认值
    - 主键和外键标识
    - 列注释
    """
    
    def __init__(self):
        """初始化步骤"""
        super().__init__("提取列信息")
    
    def execute(self, context: SchemaExtractionContext) -> SchemaExtractionContext:
        """执行列信息提取
        
        参数:
            context: 包含表信息的上下文
            
        返回:
            包含完整表和列信息的上下文
        """
        logger.info("开始提取列信息")
        
        tables = context.raw_schema_info['tables']
        
        for table in tables:
            table_name = table['name']
            
            # 获取列信息
            columns = context.database_service.get_columns(table_name)
            table['columns'] = columns
            
            # 获取主键信息
            pk = context.database_service.get_primary_key(table_name)
            table['primary_key'] = pk
            
            # 获取外键信息
            fks = context.database_service.get_foreign_keys(table_name)
            table['foreign_keys'] = fks
            
            logger.debug(f"表 {table_name}: {len(columns)} 列, "
                        f"主键: {pk if pk else '无'}, "
                        f"外键: {len(fks)} 个")
        
        logger.info("列信息提取完成")
        return context


class BuildSchemaModelStep(PipelineStep):
    """构建架构模型步骤
    
    将原始的字典格式数据转换为Pydantic模型。
    这一步确保数据的类型安全和验证。
    """
    
    def __init__(self):
        """初始化步骤"""
        super().__init__("构建架构模型")
    
    def execute(self, context: SchemaExtractionContext) -> SchemaExtractionContext:
        """构建Pydantic模型
        
        参数:
            context: 包含原始架构信息的上下文
            
        返回:
            包含DatabaseSchema模型的上下文
        """
        logger.info("开始构建架构模型")
        
        tables = []
        for table_info in context.raw_schema_info['tables']:
            # 构建列模型 - table_info['columns']已经是ColumnInfo对象列表
            columns = table_info['columns']
            
            # 构建表模型
            table = TableInfo(
                name=table_info['name'],
                columns=columns,
                primary_key=table_info.get('primary_key'),
                foreign_keys=table_info.get('foreign_keys', []),
                indexes=table_info.get('indexes', []),
                comment=table_info.get('comment'),
                row_count=table_info.get('row_count')
            )
            tables.append(table)
        
        # 构建数据库架构模型
        context.database_schema = DatabaseSchema(
            database_name=context.database_config['database'],
            tables=tables
        )
        
        logger.info(f"架构模型构建完成: {len(tables)} 个表, "
                   f"共 {context.database_schema.total_columns} 个列")
        return context


# ========== 管道主类 ==========

class SchemaExtractionPipeline(Pipeline):
    """数据库架构提取管道
    
    这是分析流程的第一个管道，负责从数据库中提取完整的架构信息。
    包含4个步骤：连接数据库 -> 提取表 -> 提取列 -> 构建模型
    """
    
    def __init__(self, services: ServiceContainer):
        """初始化管道
        
        参数:
            services: 服务容器
        """
        super().__init__("架构提取")
        
        # 按顺序添加步骤
        self.add_step(ConnectDatabaseStep(services))
        self.add_step(ExtractTablesStep())
        self.add_step(ExtractColumnsStep())
        self.add_step(BuildSchemaModelStep())
    
    def execute(self, database_config: Dict[str, Any]) -> Dict[str, Any]:
        """执行架构提取管道
        
        参数:
            database_config: 数据库连接配置，包含host、port、database、user、password等
            
        返回:
            包含提取结果的字典：
            - database_schema: DatabaseSchema模型实例
            - table_count: 表数量
            - total_columns: 总列数
        """
        # 创建初始上下文
        context = SchemaExtractionContext(database_config=database_config)
        
        # 运行管道
        result = self.run(context)
        
        # 返回结果
        return {
            'database_schema': result.database_schema,
            'table_count': result.database_schema.table_count,
            'total_columns': result.database_schema.total_columns
        }