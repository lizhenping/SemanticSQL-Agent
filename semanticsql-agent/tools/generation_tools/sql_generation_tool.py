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
    process_all: bool = Field(default=False, description="是否处理所有可用问题（批处理模式）")
    
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
    description: str = "基于Neo4j中的Question节点生成SQL查询。参数：question_id（Question节点ID，可选）、database_name（数据库名称）、process_all（是否批处理所有问题）。支持单问题处理和批处理模式。在使用前必须先运行scenario_operation_tool生成Question数据。"
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
        """简化版：获取所有问题，逐个生成SQL"""
        database_name = kwargs.get('database_name', 'testdb')
        execute_sql = kwargs.get('execute_sql', False)
        execute_sql = True
        self.logger.info(f"🔧 {self.name}: 开始处理所有Question节点")
        
        try:
            # 初始化组件
            if not self.memory_manager:
                object.__setattr__(self, 'memory_manager', ComponentManager.create_memory_manager(self.settings))
            if not self.database_manager:
                object.__setattr__(self, 'database_manager', ComponentManager.create_database_manager(self.settings))
            
            # 检查依赖
            self._check_dependencies()
            
            # 获取所有Question节点 - 简单直接
            cypher = "MATCH (q:Question) RETURN q.id as id, q.question_text as text ORDER BY q.created_at DESC"
            all_questions = self.memory_manager.neo4j_graph.query(cypher)
            
            if not all_questions:
                return "没有找到Question节点，请先运行scenario_operation_tool生成问题"
            
            self.logger.info(f"找到 {len(all_questions)} 个Question，开始逐个处理")
            
            # 逐个处理 - 简单的for循环
            results = []
            for i, question in enumerate(all_questions, 1):
                question_id = question['id']
                question_text = question['text']
                
                self.logger.info(f"处理 {i}/{len(all_questions)}: {question_id}")
                self.logger.info(f"问题: {question_text[:50]}...")
                
                try:
                    # 使用完整的处理逻辑（包含SQL执行）
                    result = self._process_single_question(question_id, database_name, execute_sql, 'mysql')
                    results.append(result)
                    self.logger.info(f"✅ 问题 {question_id} 处理成功")
                    
                except Exception as e:
                    self.logger.warning(f"❌ 问题 {question_id} 处理失败: {e}")
                    continue
            
            return json.dumps({
                'total': len(all_questions),
                'processed': len(results),
                'results': results
            }, ensure_ascii=False)
            
        except Exception as e:
            error_msg = f"SQL生成失败: {str(e)}"
            self.logger.error(f"❌ {self.name}: {error_msg}")
            return f"❌ {error_msg}"

    def _generate_sql_for_question(self, question_id: str, database_name: str, execute_sql: bool = False) -> str:
        """为单个问题生成SQL - 极简版"""
        try:
            # 获取问题数据
            question_data = self._fetch_question_from_neo4j(question_id, database_name)
            
            # 获取schema和外键信息
            schema_info = self._fetch_schema_from_neo4j(database_name)
            foreign_keys = self._fetch_foreign_keys_from_neo4j(database_name)
            
            # 验证schema信息
            if not schema_info or not schema_info.get('tables'):
                raise ValueError(f"无法获取数据库 {database_name} 的schema信息")
            
            # 构建context字典用于_build_enhanced_context
            context_dict = {
                'schema_info': schema_info,
                'foreign_keys': foreign_keys,
                'er_relations': {'physical': foreign_keys}  # 兼容性
            }
            
            # 构建增强的context字符串
            enhanced_context = self._build_enhanced_context(question_data, context_dict)
            
            # 正确传递模板变量
            prompt = self.prompt_manager.render_template(
                'tools/sql_generation.j2',
                question=question_data.get('question_text', ''),
                context=enhanced_context,
                dialect='mysql',
                question_focus=question_data.get('question_focus', ''),
                expected_output=question_data.get('expected_output', ''),
                business_rules=question_data.get('business_rules', []),
                join_relationships=foreign_keys
            )
            
            # 调用LLM生成SQL
            response = self.llm.invoke(prompt)
            sql = self._extract_sql_from_response(response.content)
            
            # 存储结果
            self._store_sql_result_to_neo4j(question_id, sql, None, 'mysql')
            
            return sql
            
        except Exception as e:
            self.logger.error(f"为问题 {question_id} 生成SQL失败: {e}")
            raise

    # ========== Neo4j数据获取方法 ==========
    def _check_dependencies(self) -> None:
        """检查Neo4j连接和基本依赖"""
        if not self.memory_manager or not getattr(self.memory_manager, 'neo4j_graph', None):
            raise_dependency_error(
                self.name,
                "Neo4j连接不可用，无法获取Question和schema信息"
            )
    
    def _fetch_question_from_neo4j(self, question_id: str, database_name: str) -> Dict[str, Any]:
        """从Neo4j获取Question节点的完整数据 - 修复版：添加Question节点存在性检查"""
        # 首先检查Question节点是否存在
        check_cypher = "MATCH (q:Question) RETURN count(q) as count"
        check_result = self.memory_manager.neo4j_graph.query(check_cypher)
        if not check_result or check_result[0]['count'] == 0:
            raise_tool_error(self.name, "未找到任何Question节点，请先执行scenario_operation_tool生成问题")
        
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
            'question_data': question_data
        }
        
        # 验证schema信息
        if not context['schema_info'] or not context['schema_info'].get('tables'):
            raise_tool_error(self.name, f"无法获取数据库 {database_name} 的schema信息")
        
        return context
    
    def _fetch_schema_from_neo4j(self, database_name: str) -> Dict[str, Any]:
        """获取数据库schema信息 - 修复版：使用实际存在的属性名"""
        cypher = """
        MATCH (d:Database {name: $database_name})-[:CONTAINS]->(t:Table)-[:HAS_COLUMN]->(c:Column)
        RETURN t.name as table_name,
               COALESCE(t.business_desc, t.ai_business_desc, '') as table_comment,
               collect({
                   name: c.name,
                   type: c.data_type,
                   comment: COALESCE(c.business_desc, c.ai_business_desc, ''),
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
        """获取ER关系信息 - 修复版：使用实际的ER结构（ERRelation + BusinessEntity）"""
        er_data = {'physical': [], 'logical': [], 'conceptual': []}
        
        try:
            # 查询BusinessEntity之间的关系（逻辑层）
            entity_cypher = """
            MATCH (be1:BusinessEntity)-[r]-(be2:BusinessEntity)
            WHERE type(r) IN ['ONE_TO_ONE', 'ONE_TO_MANY']
            RETURN be1.name as from_entity, 
                   type(r) as rel_type, 
                   be2.name as to_entity
            """
            
            entity_result = self.memory_manager.neo4j_graph.query(entity_cypher)
            
            # 将BusinessEntity关系转换为逻辑层关系
            for row in entity_result:
                if row['from_entity'] and row['to_entity']:
                    relation = {
                        'from': row['from_entity'],
                        'to': row['to_entity'],
                        'relationship': row['rel_type']
                    }
                    er_data['logical'].append(relation)
            
            # 查询ERRelation的概念层关系
            concept_cypher = """
            MATCH (bd:BusinessDomain)-[:CONTAINS]->(er:ERRelation)-[:INVOLVES]->(be:BusinessEntity)
            WHERE bd.database_name = $database_name OR bd.database_name IS NULL
            RETURN er.relation_name as relation_name,
                   er.business_meaning as business_meaning,
                   er.complexity_level as complexity_level,
                   COLLECT(be.name) as involved_entities
            """
            
            concept_result = self.memory_manager.neo4j_graph.query(concept_cypher, {'database_name': database_name})
            
            # 将ERRelation转换为概念层关系
            for row in concept_result:
                if row['relation_name']:
                    conceptual_relation = {
                        'relation_name': row['relation_name'],
                        'business_meaning': row['business_meaning'],
                        'complexity_level': row['complexity_level'],
                        'involved_entities': row['involved_entities']
                    }
                    er_data['conceptual'].append(conceptual_relation)
        
        except Exception as e:
            self.logger.warning(f"获取ER关系数据失败: {e}")
        
        return er_data
    
    def _fetch_foreign_keys_from_neo4j(self, database_name: str) -> List[Dict[str, Any]]:
        """获取外键关系 - 修复版：基于实际的is_foreign标记和共同列，不限制列名模式"""
        # 基于外键标记和共同列名推断表关系
        cypher = """
        MATCH (d:Database {name: $database_name})-[:CONTAINS]->(t1:Table)-[:HAS_COLUMN]->(c1:Column)
        MATCH (d)-[:CONTAINS]->(t2:Table)-[:HAS_COLUMN]->(c2:Column)
        WHERE t1.name < t2.name 
              AND c1.name = c2.name
              AND (c1.is_foreign = true OR c1.is_primary = true 
                   OR c2.is_foreign = true OR c2.is_primary = true)
        RETURN DISTINCT t1.name as from_table,
                        c1.name as column_name,
                        t2.name as to_table,
                        c1.is_foreign as c1_is_fk,
                        c1.is_primary as c1_is_pk,
                        c2.is_foreign as c2_is_fk,
                        c2.is_primary as c2_is_pk
        ORDER BY from_table, to_table, column_name
        LIMIT 20
        """
        
        try:
            result = self.memory_manager.neo4j_graph.query(cypher, {'database_name': database_name})
            
            foreign_keys = []
            for row in result:
                # 构建JOIN关系信息
                from_table = row['from_table']
                to_table = row['to_table']
                column = row['column_name']
                
                foreign_keys.append({
                    'from_table': from_table,
                    'to_table': to_table,
                    'column_name': column,
                    'from': f"{from_table}.{column}",
                    'to': f"{to_table}.{column}",
                    'relationship_type': self._classify_relationship_type(row)
                })
            
            if foreign_keys:
                self.logger.info(f"找到 {len(foreign_keys)} 个表关系")
            else:
                self.logger.warning("没有找到外键关系")
            
            return foreign_keys
        except Exception as e:
            self.logger.warning(f"外键关系查询失败: {e}")
            return []
    
    def _classify_relationship_type(self, row: Dict) -> str:
        """分类关系类型"""
        c1_fk, c1_pk = row['c1_is_fk'], row['c1_is_pk']
        c2_fk, c2_pk = row['c2_is_fk'], row['c2_is_pk']
        
        if (c1_fk and c2_pk) or (c1_pk and c2_fk):
            return "foreign_key"
        elif c1_pk and c2_pk:
            return "shared_primary"
        else:
            return "common_column"
    
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
        """获取领域分析结果 - 修复版：DomainAnalysis不存在，使用BusinessDomain和Database信息"""
        # DomainAnalysis节点不存在，尝试从BusinessDomain和Database获取信息
        cypher = """
        MATCH (d:Database {name: $database_name})
        OPTIONAL MATCH (bd:BusinessDomain)
        RETURN d.business_desc as domain_desc,
               bd.name as domain_name,
               COLLECT(DISTINCT bd.name) as business_domains
        LIMIT 1
        """
        
        try:
            result = self.memory_manager.neo4j_graph.query(cypher, {'database_name': database_name})
            
            domain_analysis = {}
            if result and result[0]:
                row = result[0]
                domain_analysis = {
                    'domain_type': row.get('domain_name', ''),
                    'business_characteristics': row.get('domain_desc', ''),
                    'key_entities': ''
                }
            else:
                domain_analysis = {}
            
            return domain_analysis
        except Exception as e:
            self.logger.error(f"领域分析查询失败: {e}")
            raise Exception(f"无法获取领域分析数据: {e}")
    
    def _fetch_field_classifications_from_neo4j(self, database_name: str) -> Dict[str, Any]:
        """获取字段分类结果 - 修复版：使用实际存在的属性"""
        cypher = """
        MATCH (d:Database {name: $database_name})-[:CONTAINS]->(t:Table)-[:HAS_COLUMN]->(c:Column)
        WHERE c.category IS NOT NULL
        RETURN t.name + '.' + c.name as column_name,
               COALESCE(c.category, '') as field_type,
               COALESCE(c.category_desc, c.category, '') as classification,
               c.category as category
        """
        
        try:
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
            
            if not field_classifications:
                self.logger.info("没有找到字段分类数据（field_type属性不存在）")
            
            return field_classifications
        except Exception as e:
            self.logger.warning(f"字段分类查询失败: {e}")
            return {}
    
    def _fetch_table_meanings_from_neo4j(self, database_name: str) -> Dict[str, Any]:
        """获取表业务含义 - 使用实际存在的属性名"""
        cypher = """
        MATCH (d:Database {name: $database_name})-[:CONTAINS]->(t:Table)
        WHERE COALESCE(t.ai_business_desc, t.business_desc, '') <> ''
        RETURN t.name as table_name,
               COALESCE(t.ai_business_desc, t.business_desc, '') as business_meaning
        """
        
        result = self.memory_manager.neo4j_graph.query(cypher, {'database_name': database_name})
        
        table_meanings = {}
        for row in result:
            table_name = row.get('table_name', '')
            if table_name:
                table_meanings[table_name] = {
                    'business_meaning': row.get('business_meaning', '')
                }
        
        return table_meanings
    

    def _process_single_question(self, question_id: str, database_name: str, execute_sql: bool, dialect: str) -> Dict[str, Any]:
        """处理单个问题的核心逻辑（从_run方法提取）
        
        Args:
            question_id: 问题ID
            database_name: 数据库名称
            execute_sql: 是否执行SQL
            dialect: SQL方言
            
        Returns:
            单个问题的处理结果
        """
        # 1. 从Neo4j获取Question分析数据
        question_data = self._fetch_question_from_neo4j(question_id, database_name)
        
        # 2. 获取完整的分析上下文
        context = self._gather_neo4j_context(database_name, question_data)
        
        # 3. 生成SQL
        sql = self._generate_sql_with_context(question_data, context, dialect)
        
        # 4. 执行SQL（如果需要）
        execution_result = None
        if execute_sql and self.database_manager:
            execution_result = self._execute_sql_safely(sql, database_name)
        
        # 5. 存储结果到Neo4j
        self._store_sql_result_to_neo4j(question_id, sql, execution_result, dialect)
        
        # 6. 构建结果
        return {
            "question_id": question_id,
            "question_text": question_data.get('question_text', ''),
            "sql": sql,
            "dialect": dialect,
            "executed": execute_sql,
            "execution_success": execution_result is not None if execute_sql else None,
            "result_count": len(execution_result) if execution_result else None
        }

    # ========== SQL生成方法 ==========
    def _validate_question_columns(self, question_data: Dict[str, Any], schema_info: Dict[str, Any]) -> None:
        """严格验证问题中引用的列名（只验证不修复）
        
        Args:
            question_data: 问题数据
            schema_info: 数据库schema信息
            
        Raises:
            ValueError: 如果发现无效的表-列组合
        """
        if not schema_info or not schema_info.get('tables'):
            self.logger.warning("缺少schema信息，跳过列名验证")
            return
        
        # 构建有效的表-列组合集合
        valid_combinations = set()
        table_columns = {}
        for table_name, table_info in schema_info['tables'].items():
            columns = [col['name'] for col in table_info.get('columns', [])]
            table_columns[table_name] = set(columns)
            # 构建所有有效的表.列组合
            for col_name in columns:
                valid_combinations.add(f"{table_name}.{col_name}")
        
        # 收集所有的列引用
        all_column_refs = []
        
        # 从columns_used收集
        columns_used = question_data.get('columns_used', [])
        if isinstance(columns_used, list):
            for col_ref in columns_used:
                if isinstance(col_ref, str):
                    all_column_refs.append(col_ref)
        
        # 从column_analysis收集
        column_analysis = question_data.get('column_analysis', {})
        if column_analysis and 'columns_used' in column_analysis:
            for col_info in column_analysis['columns_used']:
                col_ref = col_info.get('column_full_name', '')
                if col_ref:
                    all_column_refs.append(col_ref)
        
        # 验证所有列引用
        invalid_refs = []
        for col_ref in all_column_refs:
            if col_ref not in valid_combinations:
                invalid_refs.append(col_ref)
        
        if invalid_refs:
            error_msg = f"发现无效的表-列组合: {invalid_refs}"
            self.logger.error(error_msg)
            
            # 提供有用的调试信息
            for invalid_ref in invalid_refs:
                if '.' in invalid_ref:
                    table, column = invalid_ref.split('.', 1)
                    # 查找包含此列的正确表
                    correct_tables = []
                    for table_name, columns in table_columns.items():
                        if column in columns:
                            correct_tables.append(table_name)
                    
                    if correct_tables:
                        valid_refs = [f"{t}.{column}" for t in correct_tables]
                        self.logger.info(f"提示：列 '{column}' 的正确引用应该是: {valid_refs}")
                    else:
                        self.logger.info(f"提示：列 '{column}' 在任何表中都不存在")
                else:
                    self.logger.info(f"提示：'{invalid_ref}' 应该使用完整格式 '表名.列名'")
            
            # 抛出异常，不继续处理
            raise ValueError(error_msg)
        
        self.logger.debug("问题列名验证通过")

    def _generate_sql_with_context(
        self,
        question_data: Dict[str, Any],
        context: Dict[str, Any],
        dialect: str
    ) -> str:
        """基于完整上下文生成SQL"""
        # 预验证问题中的列名
        self._validate_question_columns(question_data, context.get('schema_info', {}))
        
        # 构建增强的上下文信息
        enhanced_context = self._build_enhanced_context(question_data, context)
        
        # 添加：根据问题类型添加SQL模式推荐
        sql_patterns = self._get_recommended_sql_patterns(question_data)
        if sql_patterns:
            enhanced_context += f"\n\n{sql_patterns}"
        
        # 获取JOIN关系信息
        join_relationships = context.get('foreign_keys', [])
        
        prompt = self.prompt_manager.render_template(
            "tools/sql_generation.j2",
            question=question_data['question_text'],
            context=enhanced_context,
            dialect=dialect,
            question_focus=question_data.get('question_focus', ''),
            expected_output=question_data.get('expected_output', ''),
            business_rules=question_data.get('business_rules', []),
            join_relationships=join_relationships
        )
        
        # 调用LLM
        response = self.llm.invoke(prompt)
        sql = self._extract_sql_from_response(response.content)
        
        # 验证SQL基本结构
        validated_sql, validation_errors = self._validate_sql_basics(sql, context['schema_info'], dialect)
        if not validated_sql:
            self.logger.warning(f"SQL验证失败: {validation_errors}")
            # 记录验证失败，但仍尝试执行（允许一些边缘情况）
            
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
    
    def _validate_sql_basics(self, sql: str, schema: Dict[str, Any], dialect: str) -> tuple[bool, str]:
        """轻量级SQL验证 - 只检查最常见的错误"""
        errors = []
        sql_upper = sql.upper()
        
        # 1. 检查禁用的PostgreSQL函数
        pg_functions = ['DATE_TRUNC', 'ARRAY_AGG', 'STRING_AGG']
        for func in pg_functions:
            if func in sql_upper:
                if func == 'DATE_TRUNC':
                    errors.append(f"使用了PostgreSQL的{func}，请使用MySQL的QUARTER()或DATE_FORMAT()")
                else:
                    errors.append(f"使用了PostgreSQL的{func}，请使用MySQL对应函数")
        
        # 2. 检查Oracle函数
        oracle_functions = ['ROWNUM', 'LISTAGG']
        for func in oracle_functions:
            if func in sql_upper:
                errors.append(f"使用了Oracle的{func}，MySQL中不支持")
        
        # 3. 检查SQL Server函数
        sqlserver_functions = ['DATEPART', 'STUFF']
        for func in sqlserver_functions:
            if func in sql_upper:
                errors.append(f"使用了SQL Server的{func}，MySQL中不支持")
        
        # 4. 提取并验证JOIN中的列（使用正则表达式）
        import re
        # 匹配 ON table.column = table.column 模式
        join_pattern = r'ON\s+(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)'
        for match in re.finditer(join_pattern, sql, re.IGNORECASE):
            t1, c1, t2, c2 = match.groups()
            # 验证列是否存在
            if schema and 'tables' in schema:
                if t1 in schema['tables']:
                    cols = [c['name'] for c in schema['tables'][t1]['columns']]
                    if c1 not in cols:
                        errors.append(f"列 {t1}.{c1} 不存在于表 {t1} 中")
                if t2 in schema['tables']:
                    cols = [c['name'] for c in schema['tables'][t2]['columns']]
                    if c2 not in cols:
                        errors.append(f"列 {t2}.{c2} 不存在于表 {t2} 中")
        
        # 5. 检查MySQL变量语法
        if re.search(r'@\w+\s*:=', sql):
            errors.append("使用了MySQL变量赋值语法，请使用窗口函数")
        
        return len(errors) == 0, '\n'.join(errors)
    
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
            # Note: DatabaseManager is already connected to the correct database
            # via its initialization, no need to switch
            
            # Execute SQL using the correct method
            result = self.database_manager.execute_sql_safe(sql, limit=100)
            
            if result.get("success"):
                data = result.get("data", [])
                self.logger.info(f"SQL执行成功，返回 {len(data)} 条记录")
                return data
            else:
                error_msg = result.get("error", "Unknown error")
                self.logger.error(f"SQL执行失败: {error_msg}")
                return None
                
        except Exception as e:
            self.logger.error(f"SQL执行失败: {e}")
            return None
    
    
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
        """从LLM响应中提取SQL - 增强版：处理多种Markdown格式"""
        # 1. 尝试匹配 ```sql ... ``` 格式
        sql_match = re.search(r'```sql\s*(.*?)\s*```', response_content, re.DOTALL | re.IGNORECASE)
        if sql_match:
            return sql_match.group(1).strip()
        
        # 2. 尝试匹配 ``` ... ``` 格式（无sql标识）
        sql_match = re.search(r'```\s*(.*?)\s*```', response_content, re.DOTALL)
        if sql_match:
            content = sql_match.group(1).strip()
            # 检查是否看起来像SQL
            if any(keyword in content.upper() for keyword in ['SELECT', 'WITH', 'INSERT', 'UPDATE', 'DELETE']):
                return content
        
        # 3. 如果没有代码块，直接使用内容
        return response_content.strip()
    
    def _get_recommended_sql_patterns(self, question_data: Dict[str, Any]) -> str:
        """根据问题类型获取推荐的SQL模式"""
        patterns = []
        
        # 检查问题文本中的关键词
        question_text = question_data.get('question_text', '').lower()
        
        # 检查是否需要排名
        if any(keyword in question_text for keyword in ['排名', '前n', 'top', '第几', '最高', '最低', '第一', '第二']):
            patterns.append("- 排名分析: 使用 ROW_NUMBER() OVER (ORDER BY ...) 进行排名，不要使用@变量")
            patterns.append("  示例: ROW_NUMBER() OVER (ORDER BY amount DESC) AS rank")
        
        # 检查是否需要分组排名
        if any(keyword in question_text for keyword in ['每个', '各', '按', '分组', '各类', '各种']):
            patterns.append("- 分组排名: 使用 PARTITION BY 进行分组排名")
            patterns.append("  示例: RANK() OVER (PARTITION BY category ORDER BY value DESC)")
        
        # 检查是否需要累计
        if any(keyword in question_text for keyword in ['累计', '累积', '总和', '汇总']):
            patterns.append("- 累积计算: 使用窗口函数进行累积计算")
            patterns.append("  示例: SUM(amount) OVER (ORDER BY date ROWS UNBOUNDED PRECEDING)")
        
        # 检查是否需要比例
        if any(keyword in question_text for keyword in ['占比', '比例', '百分比', '份额']):
            patterns.append("- 比例计算: 使用窗口函数计算占比")
            patterns.append("  示例: amount / SUM(amount) OVER (PARTITION BY category) * 100")
        
        # 检查是否需要移动平均
        if any(keyword in question_text for keyword in ['移动', '滑动', '近n', '最近']):
            patterns.append("- 移动聚合: 使用 ROWS BETWEEN 子句")
            patterns.append("  示例: AVG(value) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)")
        
        if patterns:
            return f"推荐的SQL模式:\n" + '\n'.join(patterns)
        else:
            return ""
    
    def _postprocess_sql(self, sql: str, dialect: str) -> str:
        """后处理SQL语句 - 增强版：彻底清理Markdown标记"""
        # 1. 移除各种Markdown代码块标记
        sql = re.sub(r'```sql\s*', '', sql, flags=re.IGNORECASE)  # 开始标记
        sql = re.sub(r'```\s*', '', sql)  # 结束标记
        # 注意：不要简单删除所有反引号，因为字段名需要反引号
        
        # 2. 移除可能的其他标记
        # 更精确地清理末尾：只清理明显的错误字符，保留必要的分号
        sql = re.sub(r';\s*```\s*\]?\s*$', ';', sql)  # 清理 "; ```]" 这样的模式
        sql = re.sub(r';\s*```\s*$', ';', sql)  # 清理 "; ```" 这样的模式
        sql = re.sub(r'\s*\]$', '', sql)  # 清理末尾的方括号
        
        # 3. 移除多余空白
        sql = re.sub(r'\s+', ' ', sql).strip()
        
        # 4. 确保以分号结尾
        if not sql.endswith(';'):
            sql += ';'
        
        # 5. MySQL特定处理
        if dialect == "mysql":
            # 保持字段名的反引号（MySQL标准）
            # 不做额外的引号转换，LLM生成的应该已经是正确的格式
            pass
            
            # 检测并警告MySQL变量使用
            if '@' in sql and ':=' in sql:
                self.logger.warning("⚠️ 检测到MySQL变量语法！建议使用窗口函数替代")
                self.logger.warning(f"问题SQL: {sql[:100]}...")
                
                # 提供修改建议
                if '@row_num' in sql.lower():
                    self.logger.warning("💡 建议: 使用 ROW_NUMBER() OVER (ORDER BY ...) 替代 @row_num")
        
        return sql
    
    def _fix_mysql_quotes(self, sql: str) -> str:
        """修复MySQL字段名的引号"""
        # 简单的字段名引号修复：将双引号替换为反引号
        # 但要避免替换字符串内的双引号
        
        # 这是一个简化版本，更复杂的情况需要SQL解析器
        # 只替换明显是字段名的双引号
        sql = re.sub(r'"([a-zA-Z_]\w*)"', r'`\1`', sql)
        
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