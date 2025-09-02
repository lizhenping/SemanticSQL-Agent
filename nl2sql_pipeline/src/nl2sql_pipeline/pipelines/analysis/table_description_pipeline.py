"""表描述生成管道（极简版）

本管道负责为数据库中的每个表生成业务描述。
主要依赖LLM生成表注释，保持简单直接。
"""

import logging
from typing import Dict, Any, List, Optional

from ..base import Pipeline, PipelineStep
from ...models.database import DatabaseSchema, TableInfo
from ...models.analysis import (
    DomainKnowledge,
    ColumnDescription,
    TableDescription
)
from ...models.pipeline_contexts import TableDescriptionContext

from ...services import ServiceContainer

logger = logging.getLogger(__name__)

# ========== 常量定义 ==========
SYSTEM_TABLES = {'information_schema', 'mysql', 'performance_schema', 'sys'}
DEFAULT_BATCH_SIZE = 5


# ========== 管道步骤 ==========

class GenerateTableDescriptionsStep(PipelineStep[TableDescriptionContext]):
    """生成表描述步骤 - 使用LLM生成表注释"""
    
    def __init__(self, batch_size: int = DEFAULT_BATCH_SIZE):
        super().__init__("生成表描述")
        self.batch_size = batch_size
    
    def execute(self, context: TableDescriptionContext) -> TableDescriptionContext:
        """执行表描述生成"""
        logger.info("开始生成表描述")
        
        # 过滤系统表 (黑名单检查已注释，处理完整数据库)
        user_tables = []
        for table in context.database_schema.tables:
            if table.name.lower() in SYSTEM_TABLES:
                continue
            # # 黑名单检查已删除，aid_info表已在数据库获取源头过滤
            user_tables.append(table)
        
        # 批量处理
        for i in range(0, len(user_tables), self.batch_size):
            batch = user_tables[i:i + self.batch_size]
            self._process_batch(batch, context)
        
        logger.info(f"生成了 {len(context.table_descriptions)} 个表描述")
        return context
    
    def _process_batch(self, batch: List[TableInfo], context: TableDescriptionContext):
        """处理一批表"""
        for table in batch:
            try:
                description = self._generate_single_table_description(table, context)
                
                context.table_descriptions[table.name] = TableDescription(
                    table_name=table.name,
                    description=description,
                    business_type='data_table',  # 简化，不推断类型
                    key_columns=[col.name for col in table.columns if col.is_primary_key],
                    row_count=None,  # 简化，不获取行数
                    confidence=0.9
                )
                
            except Exception as e:
                logger.error(f"生成表 {table.name} 描述失败: {e}")
                # 使用默认描述
                context.table_descriptions[table.name] = TableDescription(
                    table_name=table.name,
                    description=f"{table.name}表",
                    business_type='data_table',
                    key_columns=[],
                    row_count=None,
                    confidence=0.5
                )
    
    def _generate_single_table_description(self, table: TableInfo, context: TableDescriptionContext) -> str:
        """生成单个表的描述"""
        # 构建表结构DDL（包含列注释）
        table_ddl_with_comments = self._build_table_ddl_with_comments(table, context)
        
        # 准备提示词参数
        prompt_params = {
            'table_name': table.name,
            'database_domain': context.domain_knowledge.description,
            'table_schema_with_comments_ddl': table_ddl_with_comments
        }
        
        # 生成提示词
        prompt = context.prompt_service.render(
            'analysis/06_table_description.j2',
            **prompt_params
        )
        
        # 调用LLM
        response = context.llm_service.generate(prompt)
        
        # 清理响应
        description = response.strip()
        
        # 基本验证
        if not description or len(description) < 5:
            description = f"{table.name}表"
        elif len(description) > 100:  # 限制长度
            description = description[:97] + "..."
        
        return description
    
    def _build_table_ddl_with_comments(self, table: TableInfo, context: TableDescriptionContext) -> str:
        """构建包含列注释的表DDL"""
        lines = [f"CREATE TABLE `{table.name}` ("]
        
        column_defs = []
        for col in table.columns:
            # 基本列定义
            col_def = f"  `{col.name}` {col.data_type}"
            
            # 约束
            if not col.is_nullable:
                col_def += " NOT NULL"
            if col.is_primary_key:
                col_def += " PRIMARY KEY"
            if col.default_value:
                col_def += f" DEFAULT {col.default_value}"
            
            # 添加列注释（从列描述中获取）
            field_key = f"{table.name}.{col.name}"
            if field_key in context.column_descriptions:
                col_desc = context.column_descriptions[field_key]
                col_def += f" COMMENT '{col_desc.description}'"
            elif col.comment:
                col_def += f" COMMENT '{col.comment}'"
            
            column_defs.append(col_def)
        
        lines.extend([f"{cd}," if i < len(column_defs) - 1 else cd 
                     for i, cd in enumerate(column_defs)])
        
        lines.append(");")
        
        return "\n".join(lines)


# ========== 主管道类 ==========

class TableDescriptionPipeline(Pipeline[TableDescriptionContext]):
    """表描述生成管道（极简版）
    
    只包含一个步骤：使用LLM生成表描述
    """
    
    def __init__(self, services: ServiceContainer):
        """初始化管道"""
        super().__init__("表描述生成")
        self.services = services
        
        # 只添加一个步骤
        self.add_step(GenerateTableDescriptionsStep())
    
    def execute(self,
                database_schema: DatabaseSchema,
                database_name: str,
                domain_knowledge: DomainKnowledge,
                column_descriptions: Dict[str, ColumnDescription]) -> Dict[str, Any]:
        """执行表描述生成管道
        
        参数:
            database_schema: 数据库架构
            database_name: 数据库名称
            domain_knowledge: 领域知识
            column_descriptions: 列描述字典
            
        返回:
            包含表描述的结果字典
        """
        # 创建上下文
        context = TableDescriptionContext(
            database_schema=database_schema,
            database_name=database_name,
            domain_knowledge=domain_knowledge,
            column_descriptions=column_descriptions,
            database_service=self.services.database_service,
            llm_service=self.services.llm_service,
            prompt_service=self.services.prompt_service
        )
        
        # 运行管道
        result = self.run(context)
        
        # 返回结果
        return {
            "table_descriptions": result.table_descriptions
        }