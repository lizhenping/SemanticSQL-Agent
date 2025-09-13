"""
SQL生成工具 - Neo4j集成版本
基于Question节点的分析数据生成SQL查询并执行
"""

import re
import json
from typing import Dict, Any, Type, List, Optional
from pydantic import BaseModel, Field, model_validator
from enum import Enum
from datetime import datetime

from models.exceptions import ToolExecutionError, LLMException, raise_tool_error, raise_dependency_error
from prompts.manager import PromptManager
from utils.database import DatabaseManager
from utils.memory import Neo4jMemoryManager
from config.settings import get_settings
from config.factories import ComponentManager
from ..base_tool import BaseSemanticSQLTool


# ========== 工具内部数据模型 ==========

class SQLOperation(Enum):
    """SQL操作类型"""
    SELECT = "SELECT"
    JOIN = "JOIN"
    GROUP = "GROUP"
    SUBQUERY = "SUBQUERY"
    WINDOW = "WINDOW"
    CTE = "CTE"
    UNION = "UNION"


class SQLGenerationInput(BaseModel):
    """SQL生成输入参数 - Neo4j版本"""
    question_id: str = Field(default="", description="Question节点ID")
    database_name: str = Field(default="testdb", description="数据库名称")
    execute_sql: bool = Field(default=True, description="是否执行SQL")
    dialect: str = Field(default="mysql", description="SQL方言")
    
    @model_validator(mode='before')
    @classmethod
    def validate_input(cls, data):
        """处理字符串输入和不完整输入"""
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except:
                # 如果是单个字符串，尝试解析为question_id
                data = {"question_id": data}
        
        # 确保有默认值
        if isinstance(data, dict):
            if "database_name" not in data:
                data["database_name"] = "testdb"
            if "question_id" not in data:
                data["question_id"] = ""
                
        return data


class SQLGenerationTool(BaseSemanticSQLTool):
    """SQL生成工具 - Neo4j集成版本
    
    职责：
    - 从Neo4j获取Question节点的分析数据
    - 获取数据库schema和ER关系
    - 基于完整上下文生成SQL查询
    - 执行SQL并将结果存储到Neo4j
    
    设计原则：
    - Neo4j优先：直接从Question节点获取分析结果
    - 完整上下文：利用table_analysis和column_analysis
    - 简单执行：SQL执行后直接存储结果
    - 依赖检查：验证Question和schema数据存在
    """
    
    name: str = "sql_generation_tool" 
    description: str = "基于Neo4j中的Question节点生成SQL查询。需要参数：question_id（Question节点的ID）和database_name（数据库名称）。在使用前必须先运行scenario_operation_tool生成Question数据。"
    args_schema: Type[BaseModel] = SQLGenerationInput
    
    def __init__(self, memory_manager: Optional[Neo4jMemoryManager] = None, 
                 database_manager: Optional[DatabaseManager] = None, **kwargs):
        """初始化SQL生成工具
        
        Args:
            memory_manager: Neo4j记忆管理器
            database_manager: 数据库管理器
            **kwargs: 其他参数
        """
        super().__init__(memory_manager=memory_manager, **kwargs)
        
        # 初始化组件
        settings = get_settings()
        object.__setattr__(self, 'settings', settings)
        object.__setattr__(self, 'memory_manager', memory_manager)
        object.__setattr__(self, 'database_manager', database_manager)
        object.__setattr__(self, 'llm', ComponentManager.create_llm(settings))
        object.__setattr__(self, 'prompt_manager', PromptManager())

    def _run(self, *args, **kwargs) -> str:
        """生成SQL查询 - 主流程"""
        # 从kwargs中提取参数
        question_id = kwargs.get('question_id', '')
        database_name = kwargs.get('database_name', 'testdb')
        execute_sql = kwargs.get('execute_sql', True)
        dialect = kwargs.get('dialect', 'mysql')
        
        self.logger.info(f"🔧 {self.name}: 开始处理Question {question_id}")
        
        try:
            # 验证输入参数
            if not question_id or question_id.strip() == "":
                # 尝试查找可用的Question
                available_questions = self._find_available_questions(database_name)
                if available_questions:
                    question_id = available_questions[0]['id']
                    self.logger.info(f"自动选择Question: {question_id}")
                else:
                    return "❌ SQL生成失败: 需要提供有效的question_id，且Neo4j中没有找到可用的Question。请先运行scenario_operation_tool生成问题。"
            
            # 初始化组件
            if not self.memory_manager:
                self.memory_manager = ComponentManager.create_memory_manager(self.settings)
            if not self.database_manager:
                self.database_manager = ComponentManager.create_database_manager(self.settings)
            
            # 1. 检查依赖
            self._check_dependencies()
            
            # 2. 从Neo4j获取Question分析数据
            question_data = self._fetch_question_from_neo4j(question_id, database_name)
            
            # 3. 获取完整的分析上下文
            context = self._gather_neo4j_context(database_name, question_data)
            
            # 4. 生成SQL
            sql = self._generate_sql_with_context(question_data, context, dialect)
            
            # 5. 执行SQL（如果需要）
            execution_result = None
            if execute_sql and self.database_manager:
                execution_result = self._execute_sql_safely(sql, database_name)
            
            # 6. 存储结果到Neo4j
            self._store_sql_result_to_neo4j(question_id, sql, execution_result, dialect)
            
            # 7. 返回结果
            result = {
                "question_id": question_id,
                "sql": sql,
                "dialect": dialect,
                "executed": execute_sql,
                "execution_success": execution_result is not None if execute_sql else None,
                "result_count": len(execution_result) if execution_result else None
            }
            
            self.logger.info(f"✅ {self.name}: SQL生成完成 - {question_id}")
            return json.dumps(result, ensure_ascii=False)
            
        except Exception as e:
            error_msg = f"SQL生成失败: {str(e)}"
            self.logger.error(f"❌ {self.name}: {error_msg}")
            return f"❌ {error_msg}"

    # ========== Neo4j数据获取方法 ==========
    def _check_dependencies(self) -> None:
        """检查Neo4j连接和基本依赖"""
        if not self.memory_manager or not getattr(self.memory_manager, 'neo4j_graph', None):
            raise_dependency_error(
                self.name,
                "Neo4j连接不可用，无法获取Question和schema信息"
            )
    
    def _find_available_questions(self, database_name: str) -> List[Dict[str, Any]]:
        """查找可用的Question节点"""
        if not self.memory_manager:
            return []
        
        try:
            cypher = """
            MATCH (q:Question)
            WHERE (q.database_name = $database_name OR q.database_name = '' OR q.database_name IS NULL) 
                  AND (q.has_sql = false OR q.has_sql IS NULL)
            RETURN q.id as id, q.question_text as question_text
            ORDER BY q.created_at DESC
            LIMIT 5
            """
            
            result = self.memory_manager.neo4j_graph.query(cypher, {'database_name': database_name})
            return result if result else []
            
        except Exception as e:
            self.logger.warning(f"查找可用Question失败: {e}")
            return []
    
    def _fetch_question_from_neo4j(self, question_id: str, database_name: str) -> Dict[str, Any]:
        """从Neo4j获取Question节点的完整数据"""
        cypher = """
        MATCH (q:Question)
        WHERE q.id = $question_id 
              AND (q.database_name = $database_name OR q.database_name = '' OR q.database_name IS NULL)
        RETURN q.question_text as question_text,
               q.question_focus as question_focus,
               q.expected_output as expected_output,
               q.value_proposition as value_proposition,
               q.business_rules as business_rules,
               q.table_analysis as table_analysis,
               q.column_analysis as column_analysis,
               q.tables_used as tables_used,
               q.columns_used as columns_used,
               q.main_scenario as main_scenario,
               q.sub_scenario as sub_scenario,
               q.use_case as use_case,
               q.complexity as complexity,
               q.complexity_level as complexity_level
        """
        
        result = self.memory_manager.neo4j_graph.query(cypher, {
            'question_id': question_id,
            'database_name': database_name
        })
        
        if not result:
            raise_tool_error(self.name, f"未找到Question节点: {question_id}")
        
        question_raw = result[0]
        
        # 解析基本字段
        question_data = {
            'question_text': question_raw.get('question_text', ''),
            'question_focus': question_raw.get('question_focus', ''),
            'expected_output': question_raw.get('expected_output', ''),
            'value_proposition': question_raw.get('value_proposition', ''),
            'main_scenario': question_raw.get('main_scenario', ''),
            'sub_scenario': question_raw.get('sub_scenario', ''),
            'use_case': question_raw.get('use_case', ''),
            'complexity': question_raw.get('complexity', '简单'),
            'complexity_level': question_raw.get('complexity_level', 1)
        }
        
        # 解析JSON字符串字段
        try:
            question_data['business_rules'] = json.loads(question_raw.get('business_rules', '[]')) if question_raw.get('business_rules') else []
            question_data['table_analysis'] = json.loads(question_raw.get('table_analysis', '{}')) if question_raw.get('table_analysis') else {}
            question_data['column_analysis'] = json.loads(question_raw.get('column_analysis', '{}')) if question_raw.get('column_analysis') else {}
            question_data['tables_used'] = json.loads(question_raw.get('tables_used', '[]')) if question_raw.get('tables_used') else []
            question_data['columns_used'] = json.loads(question_raw.get('columns_used', '[]')) if question_raw.get('columns_used') else []
        except json.JSONDecodeError as e:
            self.logger.warning(f"JSON解析警告: {e}")
            question_data['business_rules'] = []
            question_data['table_analysis'] = {}
            question_data['column_analysis'] = {}
            question_data['tables_used'] = []
            question_data['columns_used'] = []
        
        return question_data
    
    def _gather_neo4j_context(self, database_name: str, question_data: Dict[str, Any]) -> Dict[str, Any]:
        """从Neo4j收集完整的分析上下文"""
        context = {
            'schema_info': self._fetch_schema_from_neo4j(database_name),
            'er_relations': self._fetch_er_relations_from_neo4j(database_name),
            'foreign_keys': self._fetch_foreign_keys_from_neo4j(database_name),
            'column_meanings': self._fetch_column_meanings_from_neo4j(database_name),
            'domain_analysis': self._fetch_domain_analysis_from_neo4j(database_name),
            'field_classifications': self._fetch_field_classifications_from_neo4j(database_name),
            'table_meanings': self._fetch_table_meanings_from_neo4j(database_name),
            'business_entities': self._fetch_business_entities_from_neo4j(database_name),
            'question_data': question_data
        }
        
        # 验证schema信息
        if not context['schema_info'] or not context['schema_info'].get('tables'):
            raise_tool_error(self.name, f"无法获取数据库 {database_name} 的schema信息")
        
        return context
    
    def _fetch_schema_from_neo4j(self, database_name: str) -> Dict[str, Any]:
        """获取数据库schema信息"""
        cypher = """
        MATCH (d:Database {name: $database_name})-[:CONTAINS]->(t:Table)-[:HAS_COLUMN]->(c:Column)
        RETURN t.name as table_name,
               t.comment as table_comment,
               collect({
                   name: c.name,
                   type: c.data_type,
                   comment: c.comment,
                   is_primary: c.is_primary,
                   is_foreign: c.is_foreign,
                   is_nullable: c.is_nullable
               }) as columns
        ORDER BY t.name
        """
        
        result = self.memory_manager.neo4j_graph.query(cypher, {'database_name': database_name})
        
        schema_info = {'tables': {}}
        for row in result:
            table_name = row['table_name']
            schema_info['tables'][table_name] = {
                'name': table_name,
                'comment': row.get('table_comment', ''),
                'columns': row['columns']
            }
        
        return schema_info
    
    def _fetch_er_relations_from_neo4j(self, database_name: str) -> Dict[str, Any]:
        """获取ER关系信息"""
        cypher = """
        MATCH (er:ERAnalysis {database_name: $database_name})
        RETURN er.physical_relations as physical,
               er.logical_relations as logical,
               er.conceptual_relations as conceptual
        ORDER BY er.created_at DESC
        LIMIT 1
        """
        
        result = self.memory_manager.neo4j_graph.query(cypher, {'database_name': database_name})
        
        er_data = {'physical': [], 'logical': [], 'conceptual': []}
        if result and result[0]:
            row = result[0]
            try:
                if row.get('physical'):
                    er_data['physical'] = json.loads(row['physical']) if isinstance(row['physical'], str) else row['physical']
                if row.get('logical'):
                    er_data['logical'] = json.loads(row['logical']) if isinstance(row['logical'], str) else row['logical']
                if row.get('conceptual'):
                    er_data['conceptual'] = json.loads(row['conceptual']) if isinstance(row['conceptual'], str) else row['conceptual']
            except json.JSONDecodeError:
                self.logger.warning("ER关系JSON解析失败")
        
        return er_data
    
    def _fetch_foreign_keys_from_neo4j(self, database_name: str) -> List[Dict[str, Any]]:
        """获取外键关系"""
        cypher = """
        MATCH (d:Database {name: $database_name})-[:CONTAINS]->(t1:Table)-[:HAS_COLUMN]->(c1:Column)-[:REFERENCES]->(c2:Column)<-[:HAS_COLUMN]-(t2:Table)
        RETURN t1.name + '.' + c1.name as from_column,
               t2.name + '.' + c2.name as to_column,
               t1.name as from_table,
               t2.name as to_table
        """
        
        result = self.memory_manager.neo4j_graph.query(cypher, {'database_name': database_name})
        
        foreign_keys = []
        for row in result:
            foreign_keys.append({
                'from': row['from_column'],
                'to': row['to_column'],
                'from_table': row['from_table'],
                'to_table': row['to_table']
            })
        
        return foreign_keys
    
    def _fetch_column_meanings_from_neo4j(self, database_name: str) -> Dict[str, Any]:
        """获取列的业务含义"""
        cypher = """
        MATCH (d:Database {name: $database_name})-[:CONTAINS]->(t:Table)-[:HAS_COLUMN]->(c:Column)
        WHERE c.business_meaning IS NOT NULL
        RETURN t.name + '.' + c.name as column_name,
               c.business_meaning as meaning,
               c.category as category
        """
        
        result = self.memory_manager.neo4j_graph.query(cypher, {'database_name': database_name})
        
        column_meanings = {}
        for row in result:
            column_meanings[row['column_name']] = {
                'business_meaning': row.get('meaning', ''),
                'category': row.get('category', '')
            }
        
        return column_meanings

    def _fetch_domain_analysis_from_neo4j(self, database_name: str) -> Dict[str, Any]:
        """获取领域分析结果"""
        cypher = """
        MATCH (d:DomainAnalysis {database_name: $database_name})
        RETURN d.domain_type as domain_type,
               d.business_characteristics as business_characteristics,
               d.key_entities as key_entities,
               d.created_at as created_at
        ORDER BY d.created_at DESC
        LIMIT 1
        """
        
        result = self.memory_manager.neo4j_graph.query(cypher, {'database_name': database_name})
        
        domain_analysis = {}
        if result and result[0]:
            row = result[0]
            domain_analysis = {
                'domain_type': row.get('domain_type', ''),
                'business_characteristics': row.get('business_characteristics', ''),
                'key_entities': row.get('key_entities', '')
            }
        
        return domain_analysis
    
    def _fetch_field_classifications_from_neo4j(self, database_name: str) -> Dict[str, Any]:
        """获取字段分类结果"""
        cypher = """
        MATCH (d:Database {name: $database_name})-[:CONTAINS]->(t:Table)-[:HAS_COLUMN]->(c:Column)
        WHERE c.field_type IS NOT NULL
        RETURN t.name + '.' + c.name as column_name,
               c.field_type as field_type,
               c.classification as classification,
               c.category as category
        """
        
        result = self.memory_manager.neo4j_graph.query(cypher, {'database_name': database_name})
        
        field_classifications = {}
        for row in result:
            column_name = row.get('column_name', '')
            if column_name:
                field_classifications[column_name] = {
                    'field_type': row.get('field_type', ''),
                    'classification': row.get('classification', ''),
                    'category': row.get('category', '')
                }
        
        return field_classifications
    
    def _fetch_table_meanings_from_neo4j(self, database_name: str) -> Dict[str, Any]:
        """获取表业务含义"""
        cypher = """
        MATCH (d:Database {name: $database_name})-[:CONTAINS]->(t:Table)
        WHERE t.business_meaning IS NOT NULL
        RETURN t.name as table_name,
               t.business_meaning as business_meaning,
               t.usage_pattern as usage_pattern,
               t.purpose as purpose
        """
        
        result = self.memory_manager.neo4j_graph.query(cypher, {'database_name': database_name})
        
        table_meanings = {}
        for row in result:
            table_name = row.get('table_name', '')
            if table_name:
                table_meanings[table_name] = {
                    'business_meaning': row.get('business_meaning', ''),
                    'usage_pattern': row.get('usage_pattern', ''),
                    'purpose': row.get('purpose', '')
                }
        
        return table_meanings
    
    def _fetch_business_entities_from_neo4j(self, database_name: str) -> Dict[str, Any]:
        """获取业务实体信息"""
        cypher = """
        MATCH (be:BusinessEntity)-[:MAPS_TO]->(t:Table)<-[:CONTAINS]-(d:Database {name: $database_name})
        RETURN be.name as entity_name,
               be.type as entity_type,
               be.description as entity_description,
               t.name as table_name
        """
        
        result = self.memory_manager.neo4j_graph.query(cypher, {'database_name': database_name})
        
        business_entities = {}
        for row in result:
            entity_name = row.get('entity_name', '')
            if entity_name:
                business_entities[entity_name] = {
                    'entity_type': row.get('entity_type', ''),
                    'entity_description': row.get('entity_description', ''),
                    'table_name': row.get('table_name', '')
                }
        
        return business_entities

    # ========== SQL生成方法 ==========
    def _generate_sql_with_context(
        self,
        question_data: Dict[str, Any],
        context: Dict[str, Any],
        dialect: str
    ) -> str:
        """基于完整上下文生成SQL"""
        # 构建增强的提示词
        enhanced_context = self._build_enhanced_context(question_data, context)
        
        prompt = self.prompt_manager.render_template(
            "tools/sql_generation.j2",
            question=question_data['question_text'],
            context=enhanced_context,
            dialect=dialect,
            question_focus=question_data.get('question_focus', ''),
            expected_output=question_data.get('expected_output', ''),
            business_rules=question_data.get('business_rules', [])
        )
        
        # 调用LLM
        response = self.llm.invoke(prompt)
        sql = self._extract_sql_from_response(response.content)
        
        return self._postprocess_sql(sql, dialect)
    
    def _build_enhanced_context(self, question_data: Dict[str, Any], context: Dict[str, Any]) -> str:
        """构建增强的上下文信息"""
        context_parts = []
        
        # 1. Question的表分析
        table_analysis = question_data.get('table_analysis', {})
        if table_analysis and table_analysis.get('tables_used'):
            context_parts.append("表使用分析：")
            for table_info in table_analysis['tables_used']:
                table_name = table_info.get('table_name', '')
                selection_reason = table_info.get('selection_reason', '')
                context_parts.append(f"  - {table_name}: {selection_reason}")
                
                # 添加操作详情
                operations = table_info.get('operations', [])
                for op in operations:
                    op_type = op.get('operation_type', '')
                    op_detail = op.get('operation_detail', '')
                    purpose = op.get('purpose', '')
                    context_parts.append(f"    * {op_type}: {op_detail} ({purpose})")
        
        # 2. Question的列分析
        column_analysis = question_data.get('column_analysis', {})
        if column_analysis and column_analysis.get('columns_used'):
            context_parts.append("\n列使用分析：")
            for column_info in column_analysis['columns_used']:
                column_name = column_info.get('column_full_name', '')
                selection_reason = column_info.get('selection_reason', '')
                context_parts.append(f"  - {column_name}: {selection_reason}")
                
                # 添加操作详情
                operations = column_info.get('operations', [])
                for op in operations:
                    op_type = op.get('operation_type', '')
                    op_detail = op.get('operation_detail', '')
                    purpose = op.get('purpose', '')
                    context_parts.append(f"    * {op_type}: {op_detail} ({purpose})")
        
        # 3. 数据库Schema
        schema_info = context.get('schema_info', {})
        if schema_info.get('tables'):
            context_parts.append("\n数据库结构：")
            # 仅显示在Question中分析的表
            relevant_tables = self._extract_relevant_tables(question_data)
            for table_name in relevant_tables:
                if table_name in schema_info['tables']:
                    table_info = schema_info['tables'][table_name]
                    context_parts.append(f"\n表: {table_name}")
                    if table_info.get('comment'):
                        context_parts.append(f"  说明: {table_info['comment']}")
                    
                    context_parts.append("  列:")
                    for col in table_info.get('columns', [])[:15]:
                        col_desc = f"    - {col.get('name')} ({col.get('type')})"
                        if col.get('comment'):
                            col_desc += f" -- {col['comment']}"
                        context_parts.append(col_desc)
        
        # 4. ER关系
        er_relations = context.get('er_relations', {})
        if er_relations.get('physical'):
            context_parts.append("\n外键关系:")
            for rel in er_relations['physical'][:10]:
                if isinstance(rel, dict):
                    from_table = rel.get('from', '')
                    to_table = rel.get('to', '')
                    context_parts.append(f"  - {from_table} → {to_table}")
        
        # 5. 列业务含义
        column_meanings = context.get('column_meanings', {})
        if column_meanings:
            context_parts.append("\n列业务含义:")
            for col_name, meaning_info in list(column_meanings.items())[:10]:
                business_meaning = meaning_info.get('business_meaning', '')
                if business_meaning:
                    context_parts.append(f"  - {col_name}: {business_meaning}")
        
        # 6. 领域分析
        domain_analysis = context.get('domain_analysis', {})
        if domain_analysis.get('domain_type'):
            context_parts.append("\n领域分析:")
            context_parts.append(f"  领域类型: {domain_analysis.get('domain_type', '')}")
            if domain_analysis.get('business_characteristics'):
                context_parts.append(f"  业务特征: {domain_analysis.get('business_characteristics', '')}")
            if domain_analysis.get('key_entities'):
                context_parts.append(f"  关键实体: {domain_analysis.get('key_entities', '')}")
        
        # 7. 字段分类
        field_classifications = context.get('field_classifications', {})
        if field_classifications:
            context_parts.append("\n字段分类:")
            for col_name, classification_info in list(field_classifications.items())[:10]:
                field_type = classification_info.get('field_type', '')
                classification = classification_info.get('classification', '')
                if field_type:
                    context_parts.append(f"  - {col_name}: {field_type} ({classification})")
        
        # 8. 表业务含义
        table_meanings = context.get('table_meanings', {})
        if table_meanings:
            context_parts.append("\n表业务含义:")
            for table_name, meaning_info in table_meanings.items():
                business_meaning = meaning_info.get('business_meaning', '')
                purpose = meaning_info.get('purpose', '')
                if business_meaning:
                    context_parts.append(f"  - {table_name}: {business_meaning}")
                    if purpose:
                        context_parts.append(f"    用途: {purpose}")
        
        # 9. 业务实体
        business_entities = context.get('business_entities', {})
        if business_entities:
            context_parts.append("\n业务实体:")
            for entity_name, entity_info in business_entities.items():
                entity_type = entity_info.get('entity_type', '')
                table_name = entity_info.get('table_name', '')
                entity_description = entity_info.get('entity_description', '')
                context_parts.append(f"  - {entity_name} ({entity_type}): 映射到表 {table_name}")
                if entity_description:
                    context_parts.append(f"    描述: {entity_description}")
        
        # 10. Question的直接字段信息（使用独立字段）
        if question_data.get('tables_used'):
            context_parts.append("\n问题涉及的表:")
            for table in question_data['tables_used']:
                context_parts.append(f"  - {table}")
        
        if question_data.get('columns_used'):
            context_parts.append("\n问题涉及的列:")
            for column in question_data['columns_used']:
                context_parts.append(f"  - {column}")
        
        return "\n".join(context_parts)
    
    def _extract_relevant_tables(self, question_data: Dict[str, Any]) -> List[str]:
        """从Question分析中提取相关表名"""
        tables = set()
        
        # 从表分析中获取
        table_analysis = question_data.get('table_analysis', {})
        if table_analysis.get('tables_used'):
            for table_info in table_analysis['tables_used']:
                table_name = table_info.get('table_name')
                if table_name:
                    tables.add(table_name)
        
        # 从列分析中获取
        column_analysis = question_data.get('column_analysis', {})
        if column_analysis.get('columns_used'):
            for column_info in column_analysis['columns_used']:
                column_full_name = column_info.get('column_full_name', '')
                if '.' in column_full_name:
                    table_name = column_full_name.split('.')[0]
                    tables.add(table_name)
        
        return list(tables)

    # ========== SQL执行和存储方法 ==========
    def _execute_sql_safely(self, sql: str, database_name: str) -> Optional[List[Dict[str, Any]]]:
        """安全执行SQL查询"""
        if not self.database_manager:
            self.logger.warning("数据库管理器未配置，跳过SQL执行")
            return None
        
        try:
            # 切换到指定数据库
            self.database_manager.switch_database(database_name)
            
            # 执行SQL（限制结果数量）
            limited_sql = self._add_limit_to_sql(sql)
            result = self.database_manager.execute_query(limited_sql)
            
            self.logger.info(f"SQL执行成功，返回 {len(result)} 条记录")
            return result
            
        except Exception as e:
            self.logger.error(f"SQL执行失败: {e}")
            return None
    
    def _add_limit_to_sql(self, sql: str) -> str:
        """为SQL添加LIMIT子句（如果没有）"""
        sql_lower = sql.lower().strip()
        
        # 如果已经有LIMIT，直接返回
        if 'limit' in sql_lower:
            return sql
        
        # 移除末尾分号
        sql = sql.rstrip(';')
        
        # 添加LIMIT
        return f"{sql} LIMIT 100;"
    
    def _store_sql_result_to_neo4j(self, question_id: str, sql: str, execution_result: Optional[List[Dict]], dialect: str) -> None:
        """将SQL和执行结果存储到Neo4j"""
        try:
            # 更新Question节点
            update_question_cypher = """
            MATCH (q:Question {id: $question_id})
            SET q.has_sql = true,
                q.sql_updated_at = datetime()
            """
            
            self.memory_manager.neo4j_graph.query(update_question_cypher, {'question_id': question_id})
            
            # 创建SQLResult节点
            create_result_cypher = """
            MATCH (q:Question {id: $question_id})
            CREATE (r:SQLResult {
                id: randomUUID(),
                sql: $sql,
                dialect: $dialect,
                executed: $executed,
                execution_success: $execution_success,
                result_count: $result_count,
                result_preview: $result_preview,
                created_at: datetime()
            })
            CREATE (q)-[:HAS_SQL_RESULT]->(r)
            RETURN r.id as result_id
            """
            
            # 准备参数
            executed = execution_result is not None
            execution_success = executed
            result_count = len(execution_result) if execution_result else 0
            result_preview = json.dumps(execution_result[:5], ensure_ascii=False) if execution_result else None
            
            params = {
                'question_id': question_id,
                'sql': sql,
                'dialect': dialect,
                'executed': executed,
                'execution_success': execution_success,
                'result_count': result_count,
                'result_preview': result_preview
            }
            
            result = self.memory_manager.neo4j_graph.query(create_result_cypher, params)
            
            if result:
                self.logger.info(f"SQL结果已存储: {result[0]['result_id']}")
            
        except Exception as e:
            self.logger.error(f"存储SQL结果失败: {e}")

    # ========== 辅助方法 ==========
    def _extract_sql_from_response(self, response_content: str) -> str:
        """从LLM响应中提取SQL"""
        sql_match = re.search(r'```sql\s*(.*?)\s*```', response_content, re.DOTALL | re.IGNORECASE)
        if sql_match:
            return sql_match.group(1).strip()
        return response_content.strip()
    
    def _postprocess_sql(self, sql: str, dialect: str) -> str:
        """后处理SQL语句"""
        # 移除多余空白
        sql = re.sub(r'\s+', ' ', sql).strip()
        
        # 确保以分号结尾
        if not sql.endswith(';'):
            sql += ';'
        
        # MySQL特定处理
        if dialect == "mysql":
            sql = sql.replace('"', '`')
        
        return sql



# ========== 工具工厂函数 ==========
def create_sql_generation_tool(memory_manager: Optional[Neo4jMemoryManager] = None,
                              database_manager: Optional[DatabaseManager] = None) -> SQLGenerationTool:
    """创建SQL生成工具实例
    
    Args:
        memory_manager: Neo4j记忆管理器
        database_manager: 数据库管理器
        
    Returns:
        配置好的SQL生成工具实例
    """
    settings = get_settings()
    
    # 创建组件（如果未提供）
    if memory_manager is None:
        memory_manager = ComponentManager.create_memory_manager(settings)
    
    if database_manager is None:
        database_manager = ComponentManager.create_database_manager(settings)
    
    return SQLGenerationTool(
        memory_manager=memory_manager,
        database_manager=database_manager
    )