"""
ER关系分析工具 - 三元组图谱版本
基于LLM生成概念ER关系三元组，存储为独立的图谱结构
"""

from typing import Dict, Any, List, Optional
import json
import logging
import time

from tools.base_tool import BaseSemanticSQLTool
from models.exceptions import raise_tool_error
from prompts.manager import PromptManager
from config.factories import ComponentManager
from config.settings import get_settings


class ERAnalysisTool(BaseSemanticSQLTool):
    """ER关系分析工具 - 三元组图谱版本
    
    职责：
    - 基于数据库结构和业务语义分析概念ER关系
    - 生成三元组形式的ER关系图谱
    - 使用独立的ERAnalysis容器存储，与原有数据隔离
    - 支持一次性获取完整ER关系分析结果
    
    设计原则：
    - 简洁架构：只分析概念层ER关系，不区分物理/逻辑层
    - 三元组表示：所有关系都用(源表.源列, 关系语义, 目标表.目标列)表示
    - 容器存储：ERAnalysis + ERTriplet节点，便于一次性查询
    - 数据隔离：完全独立于原有Database/Table/Column结构
    """
    
    name: str = "er_analysis"
    description: str = "分析数据库表间的概念ER关系，生成三元组图谱"
    
    def __init__(self, memory_manager=None, database_manager=None, **kwargs):
        """初始化ER分析工具"""
        super().__init__(memory_manager=memory_manager, **kwargs)
        # 使用object.__setattr__避免Pydantic验证问题
        object.__setattr__(self, 'settings', get_settings())
        object.__setattr__(self, 'memory_manager', memory_manager)
        object.__setattr__(self, 'database_manager', database_manager)
        object.__setattr__(self, 'llm', ComponentManager.create_llm(get_settings()))
        object.__setattr__(self, 'prompt_manager', PromptManager())
    
    def _run(self, *args, **kwargs) -> str:
        """执行工具分析"""
        # 提取输入文本
        input_text = args[0] if args else kwargs.get('input', '')
        self._log_execution_start(input_text)
        
        try:
            # 初始化必要的服务
            if not self.memory_manager:
                self.memory_manager = ComponentManager.create_memory_manager(self.settings)
            
            # 获取数据库元数据信息
            neo4j_graph = self.memory_manager.neo4j_graph
            database_context = self._gather_database_context_from_neo4j(neo4j_graph)
            
            # 执行概念ER关系分析
            er_analysis = self._perform_er_analysis(database_context)
            
            # 存储到独立的ER图谱结构
            analysis_id = self._store_er_analysis_with_container(neo4j_graph, er_analysis, database_context)
            
            # 构建执行结果
            result_message = self._build_result_message(er_analysis, analysis_id)
            
            # 统计实体和关系数量
               # 6. 构建返回消息
            result_message = "✅ er_analysis_tool 分析完成，已存储到Neo4j，请务必继续执行 scenario_operation_tool 工具。"
            self._log_execution_end(f"完成了 er_analysis_tool 工具分析")
            return result_message
            
        except Exception as e:
            error_msg = f"ER关系分析失败: {str(e)}"
            self.logger.error(f"❌ {self.name}: {error_msg}")
            return f"❌ {error_msg}"
    
    # ========== 核心业务逻辑 ==========
    def _gather_database_context_from_neo4j(self, neo4j_graph) -> Dict[str, Any]:
        """从 Neo4j 获取数据库上下文信息"""
        # 读取数据库和表基本信息，以及列的完整分析信息（使用 COALESCE 处理可能不存在的属性）
        cypher = """
        MATCH (d:Database)-[:CONTAINS]->(t:Table)-[:HAS_COLUMN]->(c:Column)
        RETURN d.name as database_name,
               COALESCE(d.business_desc, d.ai_business_desc, '') as database_desc,
               t.name as table_name,
               COALESCE(t.ai_business_desc, t.business_desc, '') as table_desc,
               collect({
                   name: c.name,
                   data_type: COALESCE(c.data_type, 'unknown'),
                   is_primary_key: COALESCE(c.is_primary_key, false),
                   is_foreign: COALESCE(c.is_foreign, false),
                   comment: COALESCE(c.ai_business_desc, c.business_desc, c.comment, ''),
                   sample_values: COALESCE(c.sample_values, [])
               }) as columns
        ORDER BY t.name
        """
        
        try:
            results = neo4j_graph.query(cypher)
            
            database_name = "unknown"
            database_desc = ""
            tables_info = {}
            
            for record in results:
                database_name = record.get('database_name', 'unknown')
                database_desc = record.get('database_desc', '')
                table_name = record['table_name']
                table_desc = record.get('table_desc', '')
                columns = record['columns']
                
                # 为模板准备正确的数据结构
                processed_columns = []
                for column in columns:
                    processed_columns.append({
                        'name': column.get('name', ''),
                        'data_type': column.get('data_type', 'unknown'),
                        'comment': column.get('comment', ''),  # 模板期望的字段名
                        'is_primary_key': column.get('is_primary_key', False),
                        'is_foreign': column.get('is_foreign', False),
                        'sample_values': column.get('sample_values', [])
                    })
                
                tables_info[table_name] = {
                    'name': table_name,
                    'comment': table_desc or '',  # 模板期望的字段名
                    'description': table_desc or '',  # 保持向后兼容
                    'columns': processed_columns
                }
            
            return {
                'database_name': database_name,
                'database_desc': database_desc or '',
                'tables': tables_info
            }
            
        except Exception as e:
            self.logger.error(f"从 Neo4j 获取数据库信息失败: {e}")
            raise_tool_error(self.name, f"获取数据库信息失败: {e}")
    
    def _perform_er_analysis(self, database_context: Dict[str, Any]) -> Dict[str, Any]:
        """执行ER关系分析，基于BusinessDomain->ERRelation->BusinessEntity模型"""
        try:
            # 准备提示词数据
            prompt_data = self._prepare_er_analysis_prompt_data(database_context)
            
            # 渲染提示词
            prompt_text = self.prompt_manager.render_template(
                'tools/er_analysis_conceptual.j2',
                **prompt_data
            )
            
            # 调用LLM
            llm_response = self.llm.invoke(prompt_text)
            
            # 解析LLM响应 - 新的business_domain + er_relation格式
            er_result = self._parse_llm_er_response(llm_response.content)
            
            # 验证ER分析有效性 - 使用实体-属性验证
            validated_er_analysis = self._validate_er_analysis(er_result, database_context)
            
            return validated_er_analysis
            
        except Exception as e:
            self.logger.error(f"ER关系分析失败: {e}")
            # 返回默认的业务域+ER关系结构
            return self._create_default_er_result()
    
    def _prepare_er_analysis_prompt_data(self, database_context: Dict[str, Any]) -> Dict[str, Any]:
        """准备ER分析的提示词数据"""
        # 格式化表结构信息
        formatted_schema = self._format_schema_with_descriptions(database_context)
        
        # 生成外键信息
        fk_info = self._format_foreign_key_info(database_context)
        
        return {
            'formatted_schema': formatted_schema,
            'fk_info': fk_info,
            'tables': database_context['tables'],  # 模板需要的 tables 变量
            'database_name': database_context['database_name']
        }
    
    def _format_schema_with_descriptions(self, database_context: Dict[str, Any]) -> str:
        """格式化带注释的表结构"""
        lines = ["数据库表结构（包含业务注释）："]
        
        for table_name, table_info in database_context['tables'].items():
            lines.append(f"\n表: {table_name}")
            
            # 表注释
            if table_info.get('description'):
                lines.append(f"  注释: {table_info['description']}")
            
            lines.append("  列:")
            for column in table_info['columns']:
                col_info = f"    - {column['name']} ({column.get('data_type', 'unknown')})"
                if column.get('is_primary_key'):
                    col_info += " [主键]"
                if column.get('is_foreign'):
                    col_info += " [外键]"
                if column.get('comment'):
                    col_info += f" -- {column['comment']}"
                lines.append(col_info)
        
        return "\n".join(lines)
    
    def _format_foreign_key_info(self, database_context: Dict[str, Any]) -> str:
        """格式化外键信息"""
        lines = ["外键关系信息："]
        
        # 基于列名和类型推断可能的外键关系
        tables = database_context['tables']
        fk_relations = []
        
        for table_name, table_info in tables.items():
            for column in table_info.get('columns', []):
                col_name = column.get('name', '')
                
                # 检查可能的外键模式：table_id, tableid, table_name_id 等
                if col_name.endswith('_id'):
                    ref_table = col_name[:-3]  # 去掉 _id
                    if ref_table in tables or f"{ref_table}s" in tables:
                        target_table = ref_table if ref_table in tables else f"{ref_table}s"
                        fk_relations.append(f"  {table_name}.{col_name} -> {target_table}.id (推测外键)")
                elif col_name.endswith('id') and len(col_name) > 2:
                    ref_table = col_name[:-2]  # 去掉 id
                    if ref_table in tables or f"{ref_table}s" in tables:
                        target_table = ref_table if ref_table in tables else f"{ref_table}s"
                        fk_relations.append(f"  {table_name}.{col_name} -> {target_table}.id (推测外键)")
        
        if fk_relations:
            lines.extend(fk_relations)
        else:
            lines.append("  未发现明显的外键关系")
        
        return "\n".join(lines)
    
    def _parse_llm_er_response(self, response_content: str) -> Dict[str, Any]:
        """解析LLM的ER关系分析响应 - 新的business_domain + er_relation格式"""
        try:
            # 尝试解析JSON格式的响应
            if '{' in response_content and '}' in response_content:
                # 提取JSON部分
                json_start = response_content.find('{')
                json_end = response_content.rfind('}') + 1
                json_str = response_content[json_start:json_end]
                
                result = json.loads(json_str)
                
                # 验证新格式的必需字段
                if 'business_domain' in result and 'er_relation' in result:
                    # 确保business_domain有必需字段
                    if 'name' not in result['business_domain']:
                        result['business_domain']['name'] = '未命名业务域'
                    if 'description' not in result['business_domain']:
                        result['business_domain']['description'] = '无描述'
                        
                    # 确保er_relation有必需字段
                    er_rel = result['er_relation']
                    if 'relation_id' not in er_rel:
                        er_rel['relation_id'] = f"relation_{int(time.time())}"
                    if 'relation_name' not in er_rel:
                        er_rel['relation_name'] = '未命名关系'
                    if 'business_meaning' not in er_rel:
                        er_rel['business_meaning'] = '无业务含义'
                    if 'entities' not in er_rel:
                        er_rel['entities'] = []
                    if 'inter_entity_relations' not in er_rel:
                        er_rel['inter_entity_relations'] = []
                        
                    return result
            
            # 如果解析失败，返回默认结构
            return self._create_default_er_result()
        
        except Exception as e:
            self.logger.error(f"解析LLM ER响应失败: {e}")
            return self._create_default_er_result()
    
    def _create_default_er_result(self) -> Dict[str, Any]:
        """创建默认的ER分析结果"""
        return {
            'business_domain': {
                'name': '默认业务域',
                'description': 'LLM分析失败，使用默认结果'
            },
            'er_relation': {
                'relation_id': f'default_relation_{int(time.time())}',
                'relation_name': '默认ER关系',
                'business_meaning': '分析失败，无法获取业务含义',
                'complexity_level': 'simple',
                'confidence': 0.1,
                'entities': [],
                'inter_entity_relations': []
            }
        }
    
    def _validate_er_analysis(self, er_analysis: Dict[str, Any], database_context: Dict[str, Any]) -> Dict[str, Any]:
        """验证ER分析结果的有效性"""
        tables = database_context['tables']
        validated_analysis = er_analysis.copy()
        
        # 验证business_domain
        if 'business_domain' not in er_analysis:
            self.logger.warning("缺少business_domain，使用默认值")
            validated_analysis['business_domain'] = {'name': '默认业务域', 'description': '无描述'}
        
        # 验证er_relation
        if 'er_relation' not in er_analysis:
            self.logger.warning("缺少er_relation，使用默认值")
            validated_analysis['er_relation'] = {
                'relation_id': f'default_{int(time.time())}',
                'relation_name': '默认关系',
                'business_meaning': '无业务含义',
                'entities': [],
                'inter_entity_relations': []
            }
        
        # 验证实体和属性
        er_relation = validated_analysis['er_relation']
        valid_entities = []
        
        for entity in er_relation.get('entities', []):
            # 验证实体必需字段
            if 'name' not in entity:
                self.logger.warning(f"实体缺少name字段: {entity}")
                continue
            
            # 验证实体属性
            valid_attributes = []
            for attribute in entity.get('attributes', []):
                # 验证属性必需字段
                if not all(k in attribute for k in ['column', 'table']):
                    self.logger.warning(f"属性缺少必需字段: {attribute}")
                    continue
                
                # 验证表名存在
                if attribute['table'] not in tables:
                    self.logger.warning(f"属性引用的表不存在: {attribute['table']}")
                    continue
                
                # 验证列名存在
                table_columns = [c['name'] for c in tables[attribute['table']]['columns']]
                if attribute['column'] not in table_columns:
                    self.logger.warning(f"属性引用的列不存在: {attribute['table']}.{attribute['column']}")
                    continue
                
                # 设置默认值
                attribute.setdefault('attr_type', 'business_attribute')
                attribute.setdefault('description', f"{attribute['table']}.{attribute['column']}的属性")
                
                valid_attributes.append(attribute)
            
            # 更新实体的有效属性
            entity['attributes'] = valid_attributes
            
            # 设置实体默认值
            entity.setdefault('description', f'{entity["name"]}业务实体')
            entity.setdefault('entity_type', 'core')
            entity.setdefault('role', 'participant')
            
            if valid_attributes:  # 只保留有有效属性的实体
                valid_entities.append(entity)
            else:
                self.logger.warning(f"实体{entity['name']}没有有效属性，已移除")
        
        er_relation['entities'] = valid_entities
        
        # 验证实体间关系
        valid_relations = []
        entity_names = {entity['name'] for entity in valid_entities}
        
        for relation in er_relation.get('inter_entity_relations', []):
            # 验证关系必需字段
            if not all(k in relation for k in ['from_entity', 'to_entity', 'relation_type']):
                self.logger.warning(f"实体关系缺少必需字段: {relation}")
                continue
            
            # 验证实体名存在
            if relation['from_entity'] not in entity_names:
                self.logger.warning(f"源实体不存在: {relation['from_entity']}")
                continue
            
            if relation['to_entity'] not in entity_names:
                self.logger.warning(f"目标实体不存在: {relation['to_entity']}")
                continue
            
            # 设置默认值
            relation.setdefault('business_meaning', f"{relation['from_entity']}与{relation['to_entity']}的{relation['relation_type']}关系")
            
            valid_relations.append(relation)
        
        er_relation['inter_entity_relations'] = valid_relations
        
        # 设置ER关系默认值
        er_relation.setdefault('confidence', 0.8)
        er_relation.setdefault('complexity_level', 'medium')
        
        self.logger.info(f"验证完成，有效实体: {len(valid_entities)}, 有效关系: {len(valid_relations)}")
        return validated_analysis
    
    def _store_er_analysis_with_container(self, neo4j_graph, er_analysis: Dict[str, Any], 
                                         database_context: Dict[str, Any]) -> str:
        """存储基于真正ER模型的分析结果：BusinessDomain -> ERRelation -> BusinessEntity -> Column"""
        
        # 生成分析ID
        timestamp = int(time.time())
        analysis_id = f"er_analysis_{database_context['database_name']}_{timestamp}"
        
        try:
            business_domain = er_analysis['business_domain']
            er_relation = er_analysis['er_relation']
            
            # 1. 创建业务域节点
            domain_cypher = """
            CREATE (bd:BusinessDomain {
                name: $domain_name,
                description: $domain_description,
                analysis_id: $analysis_id,
                database_name: $database_name,
                created_at: datetime()
            })
            """
            
            neo4j_graph.query(domain_cypher, {
                'domain_name': business_domain['name'],
                'domain_description': business_domain['description'],
                'analysis_id': analysis_id,
                'database_name': database_context['database_name']
            })
            
            # 2. 创建ER关系节点
            relation_cypher = """
            MATCH (bd:BusinessDomain {analysis_id: $analysis_id})
            CREATE (er:ERRelation {
                relation_id: $relation_id,
                relation_name: $relation_name,
                business_meaning: $business_meaning,
                complexity_level: $complexity_level,
                confidence: $confidence,
                analysis_id: $analysis_id
            })
            CREATE (bd)-[:CONTAINS]->(er)
            """
            
            neo4j_graph.query(relation_cypher, {
                'analysis_id': analysis_id,
                'relation_id': er_relation['relation_id'],
                'relation_name': er_relation['relation_name'],
                'business_meaning': er_relation['business_meaning'],
                'complexity_level': er_relation.get('complexity_level', 'medium'),
                'confidence': er_relation.get('confidence', 0.8)
            })
            
            # 3. 创建业务实体并连接到ER关系
            entity_ids = {}
            for entity in er_relation['entities']:
                entity_id = f"{analysis_id}_{entity['name']}"
                entity_ids[entity['name']] = entity_id
                
                entity_cypher = """
                MATCH (er:ERRelation {analysis_id: $analysis_id})
                CREATE (be:BusinessEntity {
                    entity_id: $entity_id,
                    name: $entity_name,
                    description: $entity_description,
                    entity_type: $entity_type,
                    analysis_id: $analysis_id
                })
                CREATE (er)-[:INVOLVES {role: $role}]->(be)
                """
                
                neo4j_graph.query(entity_cypher, {
                    'analysis_id': analysis_id,
                    'entity_id': entity_id,
                    'entity_name': entity['name'],
                    'entity_description': entity['description'],
                    'entity_type': entity.get('entity_type', 'core'),
                    'role': entity.get('role', 'participant')
                })
                
                # 4. 连接实体属性到数据库列
                for attribute in entity['attributes']:
                    attr_cypher = """
                    MATCH (be:BusinessEntity {entity_id: $entity_id})
                    MATCH (c:Column {name: $column_name})
                    WHERE EXISTS {
                        MATCH (c)<-[:HAS_COLUMN]-(t:Table {name: $table_name})
                    }
                    CREATE (be)-[:HAS_ATTRIBUTE {
                        attr_type: $attr_type,
                        description: $description
                    }]->(c)
                    """
                    
                    neo4j_graph.query(attr_cypher, {
                        'entity_id': entity_id,
                        'column_name': attribute['column'],
                        'table_name': attribute['table'],
                        'attr_type': attribute.get('attr_type', 'business_attribute'),
                        'description': attribute.get('description', '')
                    })
            
            # 5. 创建实体间关系
            for relation in er_relation.get('inter_entity_relations', []):
                from_entity_id = entity_ids.get(relation['from_entity'])
                to_entity_id = entity_ids.get(relation['to_entity'])
                
                if from_entity_id and to_entity_id:
                    relation_type = relation['relation_type'].upper().replace('-', '_')
                    
                    inter_relation_cypher = f"""
                    MATCH (from_entity:BusinessEntity {{entity_id: $from_entity_id}})
                    MATCH (to_entity:BusinessEntity {{entity_id: $to_entity_id}})
                    CREATE (from_entity)-[:{relation_type} {{
                        business_meaning: $business_meaning,
                        analysis_id: $analysis_id
                    }}]->(to_entity)
                    """
                    
                    neo4j_graph.query(inter_relation_cypher, {
                        'from_entity_id': from_entity_id,
                        'to_entity_id': to_entity_id,
                        'business_meaning': relation['business_meaning'],
                        'analysis_id': analysis_id
                    })
            
            self.logger.info(f"ER分析存储完成，分析ID: {analysis_id}")
            self.logger.info(f"创建了业务域: {business_domain['name']}")
            self.logger.info(f"创建了ER关系: {er_relation['relation_name']}")
            self.logger.info(f"创建了 {len(er_relation['entities'])} 个业务实体")
            
            return analysis_id
            
        except Exception as e:
            self.logger.error(f"存储ER分析到Neo4j失败: {e}")
            import traceback
            traceback.print_exc()
            raise_tool_error(self.name, f"存储ER分析失败: {e}")
    
    def _get_column_description(self, table_name: str, column_name: str, 
                               database_context: Dict[str, Any]) -> str:
        """获取列的业务描述"""
        if not column_name or table_name not in database_context['tables']:
            return ""
            
        for column in database_context['tables'][table_name]['columns']:
            if column['name'] == column_name:
                return column.get('ai_business_desc', '') or column.get('business_desc', '')
        
        return ""
    
    def _build_result_message(self, er_analysis: Dict[str, Any], analysis_id: str) -> str:
        """构建执行结果消息 - 适配新的BusinessDomain+ERRelation格式"""
        business_domain = er_analysis.get('business_domain', {})
        er_relation = er_analysis.get('er_relation', {})
        
        domain_name = business_domain.get('name', '未知业务域')
        relation_name = er_relation.get('relation_name', '未知关系')
        entities = er_relation.get('entities', [])
        inter_relations = er_relation.get('inter_entity_relations', [])
        
        # 构建实体示例展示
        entity_examples = []
        for entity in entities[:3]:  # 只显示前3个实体
            attr_count = len(entity.get('attributes', []))
            role = entity.get('role', 'participant')
            entity_examples.append(f"  • {entity.get('name', 'unknown')} [{role}] ({attr_count}个属性)")
        
        if len(entities) > 3:
            entity_examples.append(f"  ... 还有 {len(entities) - 3} 个实体")
        
        # 构建实体关系示例
        relation_examples = []
        for relation in inter_relations[:3]:  # 只显示前3个关系
            rel_text = f"  • {relation.get('from_entity', 'unknown')} --[{relation.get('relation_type', 'RELATED')}]--> {relation.get('to_entity', 'unknown')}"
            relation_examples.append(rel_text)
        
        if len(inter_relations) > 3:
            relation_examples.append(f"  ... 还有 {len(inter_relations) - 3} 个关系")
        
        entity_text = "\n".join(entity_examples) if entity_examples else "  暂无有效实体"
        relation_text = "\n".join(relation_examples) if relation_examples else "  暂无实体间关系"
        
        result = f"""✅ ER关系分析完成

🎯 分析结果:
  • 业务域: {domain_name}
  • ER关系: {relation_name}
  • 业务实体: {len(entities)}个
  • 实体间关系: {len(inter_relations)}个
  • 分析ID: {analysis_id}

🏢 业务实体:
{entity_text}

🔗 实体间关系:
{relation_text}

💾 完整ER关系图谱已存储到BusinessDomain->ERRelation->BusinessEntity结构，可通过分析ID查询完整结果"""
        
        return result
    
    # ========== 查询接口 ==========
    def get_complete_er_analysis(self, database_name: str = None, analysis_id: str = None) -> Optional[Dict[str, Any]]:
        """获取完整的ER关系分析 - 适配新的BusinessDomain->ERRelation->BusinessEntity结构"""
        if not self.memory_manager:
            return None
            
        neo4j_graph = self.memory_manager.neo4j_graph
        
        conditions = []
        params = {}
        
        if analysis_id:
            conditions.append("bd.analysis_id = $analysis_id")
            params['analysis_id'] = analysis_id
        elif database_name:
            conditions.append("bd.database_name = $database_name")
            params['database_name'] = database_name
        else:
            return None
            
        where_clause = "WHERE " + " AND ".join(conditions)
        
        cypher = f"""
        MATCH (bd:BusinessDomain)-[:CONTAINS]->(er:ERRelation)-[:INVOLVES]->(be:BusinessEntity)
        OPTIONAL MATCH (be)-[ha:HAS_ATTRIBUTE]->(c:Column)<-[:HAS_COLUMN]-(t:Table)
        OPTIONAL MATCH (be1:BusinessEntity)-[rel]->(be2:BusinessEntity)
        WHERE (be1)-[:INVOLVES*0..1]-(:ERRelation)-[:CONTAINS*0..1]-(bd) 
        AND (be2)-[:INVOLVES*0..1]-(:ERRelation)-[:CONTAINS*0..1]-(bd)
        {where_clause}
        
        RETURN bd {{
            .name, .description, .analysis_id, .database_name, .created_at
        }} as business_domain,
        er {{
            .relation_id, .relation_name, .business_meaning, 
            .complexity_level, .confidence
        }} as er_relation,
        collect(DISTINCT be {{
            .entity_id, .name, .description, .entity_type,
            role: [(er)-[inv:INVOLVES]->(be) | inv.role][0],
            attributes: [(be)-[ha2:HAS_ATTRIBUTE]->(c2:Column)<-[:HAS_COLUMN]-(t2:Table) | {{
                column: c2.name,
                table: t2.name,
                attr_type: ha2.attr_type,
                description: ha2.description
            }}]
        }}) as entities,
        collect(DISTINCT {{
            from_entity: be1.name,
            to_entity: be2.name,
            relation_type: type(rel),
            business_meaning: rel.business_meaning
        }}) as inter_entity_relations
        ORDER BY bd.created_at DESC
        LIMIT 1
        """
        
        try:
            result = neo4j_graph.query(cypher, params)
            if result and len(result) > 0:
                row = result[0]
                return {
                    'business_domain': row['business_domain'],
                    'er_relation': {
                        **row['er_relation'],
                        'entities': row['entities'],
                        'inter_entity_relations': [r for r in row['inter_entity_relations'] if r['from_entity'] and r['to_entity']]
                    }
                }
            return None
        except Exception as e:
            self.logger.error(f"查询ER分析失败: {e}")
            return None
    
    def get_latest_er_analysis(self, database_name: str) -> Optional[Dict[str, Any]]:
        """获取指定数据库的最新ER分析"""
        return self.get_complete_er_analysis(database_name=database_name)
    
    def list_er_analyses(self, database_name: str = None) -> List[Dict[str, Any]]:
        """列出所有ER分析记录 - 适配新的BusinessDomain结构"""
        if not self.memory_manager:
            return []
            
        neo4j_graph = self.memory_manager.neo4j_graph
        
        conditions = []
        params = {}
        
        if database_name:
            conditions.append("bd.database_name = $database_name")
            params['database_name'] = database_name
            
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        cypher = f"""
        MATCH (bd:BusinessDomain)-[:CONTAINS]->(er:ERRelation)
        OPTIONAL MATCH (er)-[:INVOLVES]->(be:BusinessEntity)
        {where_clause}
        WITH bd, er, count(be) as entity_count
        RETURN bd.analysis_id as analysis_id,
               bd.database_name as database_name,
               bd.name as business_domain_name,
               er.relation_name as er_relation_name,
               bd.created_at as analysis_timestamp,
               entity_count as total_entities,
               er.confidence as confidence
        ORDER BY bd.created_at DESC
        """
        
        try:
            return neo4j_graph.query(cypher, params)
        except Exception as e:
            self.logger.error(f"列出ER分析记录失败: {e}")
            return []


# ========== 便利函数 ==========
def create_er_analysis_tool(memory_manager=None, database_manager=None) -> ERAnalysisTool:
    """创建 ER 分析工具的便利函数"""
    return ERAnalysisTool(memory_manager=memory_manager, database_manager=database_manager)