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
            neo4j_graph = self.memory_manager.get_graph()
            database_context = self._gather_database_context_from_neo4j(neo4j_graph)
            
            # 执行概念ER关系分析
            er_analysis = self._perform_er_analysis(database_context)
            
            # 存储到独立的ER图谱结构
            analysis_id = self._store_er_analysis_with_container(neo4j_graph, er_analysis, database_context)
            
            # 构建执行结果
            result_message = self._build_result_message(er_analysis, analysis_id)
            
            self._log_execution_end(f"分析了 {len(er_analysis.get('triplets', []))} 个ER关系三元组")
            return result_message
            
        except Exception as e:
            error_msg = f"ER关系分析失败: {str(e)}"
            self.logger.error(f"❌ {self.name}: {error_msg}")
            return f"❌ {error_msg}"
    
    # ========== 核心业务逻辑 ==========
    def _gather_database_context_from_neo4j(self, neo4j_graph) -> Dict[str, Any]:
        """从 Neo4j 获取数据库上下文信息"""
        # 读取数据库和表基本信息，以及列的完整分析信息
        cypher = """
        MATCH (d:Database)-[:CONTAINS]->(t:Table)-[:HAS_COLUMN]->(c:Column)
        RETURN d.name as database_name,
               d.business_desc as database_desc,
               t.name as table_name,
               t.ai_business_desc as table_desc,
               collect({
                   name: c.name,
                   data_type: c.data_type,
                   is_primary_key: c.is_primary_key,
                   is_foreign: c.is_foreign,
                   ai_business_desc: c.ai_business_desc,
                   sample_values: c.sample_values
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
                
                tables_info[table_name] = {
                    'name': table_name,
                    'description': table_desc or '',
                    'columns': columns
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
        """执行ER关系分析，生成三元组图谱"""
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
            
            # 解析LLM响应
            er_result = self._parse_llm_er_response(llm_response.content)
            
            # 验证三元组有效性
            validated_triplets = self._validate_triplets(er_result.get('triplets', []), database_context)
            
            return {
                'business_name': er_result.get('business_name', f"{database_context['database_name']}_ER关系分析"),
                'business_description': er_result.get('business_description', f"{database_context['database_name']}数据库的概念ER关系分析"),
                'triplets': validated_triplets,
                'database_name': database_context['database_name']
            }
            
        except Exception as e:
            self.logger.error(f"ER关系分析失败: {e}")
            return {
                'business_name': f"{database_context['database_name']}_ER关系分析",
                'business_description': '分析失败，使用默认结果',
                'triplets': [],
                'database_name': database_context['database_name']
            }
    
    def _prepare_er_analysis_prompt_data(self, database_context: Dict[str, Any]) -> Dict[str, Any]:
        """准备ER分析的提示词数据"""
        # 格式化表结构信息
        formatted_schema = self._format_schema_with_descriptions(database_context)
        
        return {
            'formatted_schema': formatted_schema,
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
                if column.get('ai_business_desc'):
                    col_info += f" -- {column['ai_business_desc']}"
                lines.append(col_info)
        
        return "\n".join(lines)
    
    def _parse_llm_er_response(self, response_content: str) -> Dict[str, Any]:
        """解析LLM的ER关系分析响应"""
        try:
            # 尝试解析JSON格式的响应
            if '{' in response_content and '}' in response_content:
                # 提取JSON部分
                json_start = response_content.find('{')
                json_end = response_content.rfind('}') + 1
                json_str = response_content[json_start:json_end]
                
                result = json.loads(json_str)
                return result
            
            return {
                'business_name': '默认ER分析',
                'business_description': '解析失败',
                'triplets': []
            }
        
        except Exception as e:
            self.logger.error(f"解析LLM ER响应失败: {e}")
            return {
                'business_name': '默认ER分析',
                'business_description': '解析失败',
                'triplets': []
            }
    
    def _validate_triplets(self, triplets: List[Dict[str, Any]], database_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """验证三元组的有效性"""
        valid_triplets = []
        tables = database_context['tables']
        
        for triplet in triplets:
            # 验证必需字段
            if not all(k in triplet for k in ['source_table', 'target_table', 'relation_semantic']):
                self.logger.warning(f"三元组缺少必需字段: {triplet}")
                continue
                
            # 验证表名存在
            if triplet['source_table'] not in tables:
                self.logger.warning(f"源表不存在: {triplet['source_table']}")
                continue
                
            if triplet['target_table'] not in tables:
                self.logger.warning(f"目标表不存在: {triplet['target_table']}")
                continue
                
            # 验证列名存在（如果指定了的话）
            if 'source_column' in triplet and triplet['source_column']:
                source_columns = [c['name'] for c in tables[triplet['source_table']]['columns']]
                if triplet['source_column'] not in source_columns:
                    self.logger.warning(f"源列不存在: {triplet['source_table']}.{triplet['source_column']}")
                    continue
                    
            if 'target_column' in triplet and triplet['target_column']:
                target_columns = [c['name'] for c in tables[triplet['target_table']]['columns']]
                if triplet['target_column'] not in target_columns:
                    self.logger.warning(f"目标列不存在: {triplet['target_table']}.{triplet['target_column']}")
                    continue
            
            # 设置默认值
            triplet.setdefault('confidence', 0.8)
            triplet.setdefault('business_meaning', f"{triplet['source_table']}与{triplet['target_table']}的{triplet['relation_semantic']}关系")
            
            valid_triplets.append(triplet)
        
        self.logger.info(f"验证完成，有效三元组: {len(valid_triplets)}/{len(triplets)}")
        return valid_triplets
    
    def _store_er_analysis_with_container(self, neo4j_graph, er_analysis: Dict[str, Any], 
                                         database_context: Dict[str, Any]) -> str:
        """使用容器节点存储ER分析，方便一次性获取"""
        
        # 生成分析ID
        timestamp = int(time.time())
        analysis_id = f"er_analysis_{database_context['database_name']}_{timestamp}"
        
        try:
            # 1. 创建ER分析容器节点
            container_cypher = """
            CREATE (era:ERAnalysis {
                id: $analysis_id,
                database_name: $database_name,
                business_name: $business_name,
                business_description: $business_description,
                analysis_timestamp: datetime(),
                total_triplets: $total_triplets
            })
            """
            
            neo4j_graph.query(container_cypher, {
                'analysis_id': analysis_id,
                'database_name': database_context['database_name'],
                'business_name': er_analysis.get('business_name', ''),
                'business_description': er_analysis.get('business_description', ''),
                'total_triplets': len(er_analysis['triplets'])
            })
            
            # 2. 创建三元组节点并连接到容器
            for i, triplet in enumerate(er_analysis['triplets']):
                triplet_id = f"triplet_{analysis_id}_{i:03d}"
                
                # 获取注释信息
                source_table_info = database_context['tables'].get(triplet['source_table'], {})
                target_table_info = database_context['tables'].get(triplet['target_table'], {})
                source_column_desc = self._get_column_description(
                    triplet['source_table'], triplet.get('source_column', ''), database_context
                )
                target_column_desc = self._get_column_description(
                    triplet['target_table'], triplet.get('target_column', ''), database_context
                )
                
                triplet_cypher = """
                MATCH (era:ERAnalysis {id: $analysis_id})
                CREATE (ert:ERTriplet {
                    id: $triplet_id,
                    analysis_id: $analysis_id,
                    source_table: $source_table,
                    source_column: $source_column,
                    relation_semantic: $relation_semantic,
                    target_table: $target_table,
                    target_column: $target_column,
                    business_meaning: $business_meaning,
                    confidence: $confidence,
                    source_table_desc: $source_table_desc,
                    source_column_desc: $source_column_desc,
                    target_table_desc: $target_table_desc,
                    target_column_desc: $target_column_desc
                })
                CREATE (era)-[:CONTAINS_TRIPLET]->(ert)
                """
                
                neo4j_graph.query(triplet_cypher, {
                    'analysis_id': analysis_id,
                    'triplet_id': triplet_id,
                    'source_table': triplet['source_table'],
                    'source_column': triplet.get('source_column', ''),
                    'relation_semantic': triplet['relation_semantic'],
                    'target_table': triplet['target_table'],
                    'target_column': triplet.get('target_column', ''),
                    'business_meaning': triplet['business_meaning'],
                    'confidence': triplet.get('confidence', 0.8),
                    'source_table_desc': source_table_info.get('description', ''),
                    'source_column_desc': source_column_desc,
                    'target_table_desc': target_table_info.get('description', ''),
                    'target_column_desc': target_column_desc
                })
            
            self.logger.info(f"ER分析存储完成，分析ID: {analysis_id}")
            return analysis_id
            
        except Exception as e:
            self.logger.error(f"存储ER分析到Neo4j失败: {e}")
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
        """构建执行结果消息"""
        triplet_count = len(er_analysis.get('triplets', []))
        business_name = er_analysis.get('business_name', '未知业务')
        database_name = er_analysis.get('database_name', 'unknown')
        
        # 构建三元组示例展示
        triplet_examples = []
        for triplet in er_analysis.get('triplets', [])[:3]:  # 只显示前3个
            source = f"{triplet['source_table']}.{triplet.get('source_column', '*')}"
            target = f"{triplet['target_table']}.{triplet.get('target_column', '*')}"
            relation = triplet['relation_semantic']
            triplet_examples.append(f"  ({source}, {relation}, {target})")
        
        examples_text = "\n".join(triplet_examples)
        if len(er_analysis.get('triplets', [])) > 3:
            examples_text += f"\n  ... 还有 {triplet_count - 3} 个三元组"
        
        result = f"""✅ ER关系分析完成

🎯 分析结果:
  • 数据库: {database_name}  
  • 业务名称: {business_name}
  • 三元组总数: {triplet_count}个
  • 分析ID: {analysis_id}

🔗 三元组示例:
{examples_text if examples_text else "  暂无有效三元组"}

💾 完整ER关系图谱已存储到独立的ERAnalysis结构，可通过分析ID查询完整结果"""
        
        return result
    
    # ========== 查询接口 ==========
    def get_complete_er_analysis(self, database_name: str = None, analysis_id: str = None) -> Optional[Dict[str, Any]]:
        """一次性获取完整的ER关系分析"""
        if not self.memory_manager:
            return None
            
        neo4j_graph = self.memory_manager.get_graph()
        
        conditions = []
        params = {}
        
        if analysis_id:
            conditions.append("era.id = $analysis_id")
            params['analysis_id'] = analysis_id
        elif database_name:
            conditions.append("era.database_name = $database_name")
            params['database_name'] = database_name
        else:
            return None
            
        where_clause = "WHERE " + " AND ".join(conditions)
        
        cypher = f"""
        MATCH (era:ERAnalysis)-[:CONTAINS_TRIPLET]->(ert:ERTriplet)
        {where_clause}
        RETURN era {{
            .id, .database_name, .business_name, .business_description,
            .analysis_timestamp, .total_triplets
        }} as analysis_info,
        collect(ert {{
            .id, .source_table, .source_column, .relation_semantic,
            .target_table, .target_column, .business_meaning, .confidence,
            .source_table_desc, .source_column_desc, 
            .target_table_desc, .target_column_desc
        }}) as triplets
        ORDER BY era.analysis_timestamp DESC
        LIMIT 1
        """
        
        try:
            result = neo4j_graph.query(cypher, params)
            return result[0] if result else None
        except Exception as e:
            self.logger.error(f"查询ER分析失败: {e}")
            return None
    
    def get_latest_er_analysis(self, database_name: str) -> Optional[Dict[str, Any]]:
        """获取指定数据库的最新ER分析"""
        return self.get_complete_er_analysis(database_name=database_name)
    
    def list_er_analyses(self, database_name: str = None) -> List[Dict[str, Any]]:
        """列出所有ER分析记录"""
        if not self.memory_manager:
            return []
            
        neo4j_graph = self.memory_manager.get_graph()
        
        conditions = []
        params = {}
        
        if database_name:
            conditions.append("era.database_name = $database_name")
            params['database_name'] = database_name
            
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        cypher = f"""
        MATCH (era:ERAnalysis)
        {where_clause}
        RETURN era.id, era.database_name, era.business_name, 
               era.analysis_timestamp, era.total_triplets
        ORDER BY era.analysis_timestamp DESC
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