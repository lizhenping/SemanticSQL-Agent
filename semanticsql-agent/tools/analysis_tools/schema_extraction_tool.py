"""
数据库结构提取工具 - 极简架构重构版本
基于新的BaseSemanticSQLTool，实现完全自主的结构提取
"""

from typing import Dict, Any, Optional, List
import json
import logging

from pydantic import Field
from tools.base_tool import BaseSemanticSQLTool
from utils.database import DatabaseManager, create_database_manager
from models.schemas import PredicateType, EntityType
from models.exceptions import raise_tool_error, raise_dependency_error


class SchemaExtractionTool(BaseSemanticSQLTool):
    """数据库结构提取工具 - 极简重构版本
    
    职责：
    - 提取数据库完整结构信息（表、字段、类型、约束）
    - 生成表-字段关系三元组
    - 为后续工具提供结构化的数据库知识
    
    设计原则：
    - 极简实现：所有逻辑在_run()中完成
    - 自主决策：自动决定提取策略和存储时机
    - 三元组输出：结构化知识表示
    """
    
    name: str = "schema_extraction"
    description: str = "提取数据库结构信息，生成表字段关系三元组，为后续分析提供基础"
    
    # 数据库管理器（可选注入）
    database_manager: Optional[DatabaseManager] = Field(default=None, exclude=True)
    
    def __init__(self, database_manager: Optional[DatabaseManager] = None, **kwargs):
        """
        初始化结构提取工具
        
        Args:
            database_manager: 可选的数据库管理器
        """
        super().__init__(**kwargs)
        # 使用object.__setattr__避免Pydantic验证问题
        object.__setattr__(self, 'database_manager', database_manager)
    
    def _run(self, *args, **kwargs) -> str:
        """
        执行数据库结构提取 - 完全自主实现
        
        Args:
            input_text: 输入文本，期望包含数据库连接信息或提取指令
            
        Returns:
            自定义格式的执行结果字符串
        """
        # 提取输入文本
        input_text = args[0] if args else kwargs.get('input', '')
        
        # 1. 清空上次执行的三元组
        self._clear_generated_triples()
        self._log_execution_start(input_text)
        
        try:
            # 2. 解析输入参数 - 直接在_run中处理
            extraction_params = self._parse_input_inline(input_text)
            
            # 3. 获取或创建数据库管理器
            db_manager = self._get_database_manager(extraction_params)
            
            # 4. 提取数据库结构信息
            schema_info = self._extract_database_schema(db_manager)
            
            # 5. 生成结构化三元组
            self._generate_schema_triples(schema_info)
            
            # 6. 持久化三元组到记忆系统
            self._persist_triples()
            
            # 7. 构建执行结果
            result_message = self._build_result_message(schema_info)
            
            self._log_execution_end(f"提取了 {len(schema_info['tables'])} 个表")
            return result_message
            
        except Exception as e:
            error_msg = f"结构提取失败: {str(e)}"
            self.logger.error(f"❌ {self.name}: {error_msg}")
            return f"❌ {error_msg}"
    
    # ========== 核心业务逻辑 ==========
    def _parse_input_inline(self, input_text: str) -> Dict[str, Any]:
        """解析输入参数 - 内联版本，避免与LangChain BaseTool冲突"""
        try:
            # 如果输入已经是字典，直接返回
            if isinstance(input_text, dict):
                return input_text
                
            # 如果是字符串，尝试解析JSON格式的输入
            text = str(input_text)
            if text.strip().startswith('{'):
                return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # 默认提取参数
        return {
            "include_sample_data": True,
            "max_sample_rows": 3,
            "include_foreign_keys": True
        }
    
    def _get_database_manager(self, params: Dict[str, Any]) -> DatabaseManager:
        """获取数据库管理器"""
        # 优先使用注入的管理器
        if self.database_manager:
            return self.database_manager
        
        # 从输入参数创建
        if "database_params" in params:
            return create_database_manager(params["database_params"])
        
        # 最后尝试从记忆中获取连接信息
        raise_tool_error(
            self.name, 
            "未找到数据库连接信息，请提供database_params或注入DatabaseManager"
        )
    
    def _extract_database_schema(self, db_manager: DatabaseManager) -> Dict[str, Any]:
        """提取数据库结构信息"""
        try:
            # 获取数据库基本信息
            connection_info = db_manager.get_connection_info()
            database_name = connection_info["database"]
            
            # 提取详细结构信息
            schema_info = db_manager.extract_database_schema()
            
            self.logger.info(f"📊 成功提取数据库 {database_name} 的结构信息")
            return {
                "database_name": database_name,
                "tables": schema_info.schema_info,
                "table_names": schema_info.tables,
                "connection_info": connection_info
            }
            
        except Exception as e:
            raise_tool_error(
                self.name,
                f"数据库结构提取失败: {str(e)}"
            )
    
    def _generate_schema_triples(self, schema_info: Dict[str, Any]) -> None:
        """生成结构化三元组"""
        database_name = schema_info["database_name"]
        tables_info = schema_info["tables"]
        
        # 1. 生成数据库-表关系三元组
        for table_name in schema_info["table_names"]:
            self.add_analysis_triple(
                subject=database_name,
                predicate=PredicateType.HAS_TABLE.value,
                object=table_name,
                subject_type=EntityType.DATABASE.value,
                object_type=EntityType.TABLE.value,
                confidence=1.0
            )
        
        # 2. 生成表-字段关系三元组
        for table_name, table_info in tables_info.items():
            columns = table_info.get("columns", [])
            
            for column in columns:
                column_name = column["name"]
                
                # 表-字段关系
                self.add_analysis_triple(
                    subject=table_name,
                    predicate=PredicateType.HAS_COLUMN.value,
                    object=column_name,
                    subject_type=EntityType.TABLE.value,
                    object_type=EntityType.COLUMN.value,
                    confidence=1.0
                )
                
                # 字段类型信息
                column_type = column.get("type", "UNKNOWN")
                self.add_analysis_triple(
                    subject=column_name,
                    predicate="has_type",
                    object=column_type,
                    subject_type=EntityType.COLUMN.value,
                    object_type="DataType",
                    confidence=1.0
                )
                
                # 主键信息
                if column_name in table_info.get("primary_keys", []):
                    self.add_analysis_triple(
                        subject=column_name,
                        predicate="is_primary_key",
                        object="true",
                        subject_type=EntityType.COLUMN.value,
                        object_type="Boolean",
                        confidence=1.0
                    )
        
        # 3. 生成外键关系三元组
        for table_name, table_info in tables_info.items():
            for fk in table_info.get("foreign_keys", []):
                source_columns = fk.get("constrained_columns", [])
                target_table = fk.get("referred_table", "")
                target_columns = fk.get("referred_columns", [])
                
                if source_columns and target_table and target_columns:
                    # 简化处理：使用第一个外键字段
                    source_col = source_columns[0]
                    target_col = target_columns[0]
                    
                    self.add_analysis_triple(
                        subject=f"{table_name}.{source_col}",
                        predicate=PredicateType.REFERENCES.value,
                        object=f"{target_table}.{target_col}",
                        subject_type="ForeignKey",
                        object_type="PrimaryKey",
                        confidence=0.95
                    )
        
        self.logger.info(f"📝 生成了 {len(self._generated_triples)} 个结构三元组")
    
    def _build_result_message(self, schema_info: Dict[str, Any]) -> str:
        """构建执行结果消息"""
        database_name = schema_info["database_name"]
        table_count = len(schema_info["table_names"])
        total_columns = sum(
            len(table_info.get("columns", [])) 
            for table_info in schema_info["tables"].values()
        )
        triple_count = len(self._generated_triples)
        
        # 生成表概览
        table_overview = []
        for table_name, table_info in schema_info["tables"].items():
            column_count = len(table_info.get("columns", []))
            pk_count = len(table_info.get("primary_keys", []))
            fk_count = len(table_info.get("foreign_keys", []))
            
            table_overview.append(
                f"  • {table_name}: {column_count}列, {pk_count}主键, {fk_count}外键"
            )
        
        result = f"""✅ 数据库结构提取完成

📊 数据库概览:
  • 数据库: {database_name}
  • 表数量: {table_count}
  • 总字段数: {total_columns}
  • 生成三元组: {triple_count}

📋 表结构详情:
{chr(10).join(table_overview)}

💾 结构知识已存储到记忆系统，可供后续工具使用"""
        
        return result


# ========== 便利函数 ==========
def create_schema_extraction_tool(
    memory_manager: Optional['Neo4jMemoryManager'] = None,
    database_manager: Optional['DatabaseManager'] = None,
    database_params: Optional[Dict[str, Any]] = None
) -> SchemaExtractionTool:
    """创建结构提取工具的便利函数
    
    Args:
        memory_manager: Neo4j记忆管理器
        database_manager: 数据库管理器
        database_params: 数据库连接参数（向后兼容）
        
    Returns:
        配置好的结构提取工具
    """
    # 处理向后兼容的database_params
    if database_params and not database_manager:
        database_manager = create_database_manager(database_params)
    
    return SchemaExtractionTool(
        memory_manager=memory_manager,
        database_manager=database_manager
    )