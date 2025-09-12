"""
表描述分析工具 - 基于column_analysis_tool架构重构

基于schema_extraction_tool和column_analysis_tool的结果，
为数据库表生成详细的业务描述和领域特定说明。
整合pipeline的table_description_pipeline算法。
"""

from typing import Dict, Any, List, Optional
import json
import logging
from pydantic import Field
from langchain_openai import ChatOpenAI

from tools.base_tool import BaseSemanticSQLTool
from utils.database import DatabaseManager
from models.exceptions import raise_tool_error, raise_dependency_error
from config.settings import get_settings
from utils.memory import Neo4jMemoryManager

# 导入提示词管理和LLM组件
from prompts.manager import PromptManager
from config.factories import ComponentManager
# Removed to avoid circular import - parser not actually used in this file
# from agent.parsers import SemanticSQLOutputParser

class TableAnalysisTool(BaseSemanticSQLTool):
    """表描述分析工具 - 重构版本
    
    核心职责：
    - 从Neo4j读取schema和column_analysis结果
    - 使用LLM生成表的业务描述和领域说明
    - 将描述结果注入到Neo4j Table节点
    - 支持领域知识和列描述的智能分析
    
    设计原则：
    - 数据复用：直接从Neo4j读取已有信息
    - LLM驱动：采用table_description模板进行智能分析
    - 快速失败：错误立即暴露，无降级逻辑
    - 属性注入：将结果直接存储到Table节点属性
    """
    
    name: str = "table_analysis_tool"
    description: str = "基于LLM的表业务描述生成，结合列描述和领域知识信息"
    
    # 组件依赖（可选注入）
    memory_manager: Optional[Neo4jMemoryManager] = Field(default=None, exclude=True)
    database_manager: Optional[DatabaseManager] = Field(default=None, exclude=True)
    llm: Optional[ChatOpenAI] = Field(default=None, exclude=True)
    settings: Optional[Any] = Field(default=None, exclude=True)
    prompt_manager: Optional[Any] = Field(default=None, exclude=True)
    
    def __init__(self, memory_manager: Optional['Neo4jMemoryManager'] = None, 
                 database_manager: Optional[DatabaseManager] = None, **kwargs):
        """
        初始化表描述分析工具
        
        Args:
            memory_manager: Neo4j记忆管理器实例
            database_manager: 数据库管理器实例（可选）
        """
        super().__init__(memory_manager=memory_manager, **kwargs)
        # 使用object.__setattr__避免Pydantic验证问题
        object.__setattr__(self, 'settings', get_settings())
        object.__setattr__(self, 'memory_manager', memory_manager)
        object.__setattr__(self, 'database_manager', database_manager)
        object.__setattr__(self, 'llm', ComponentManager.create_llm(get_settings()))
        object.__setattr__(self, 'prompt_manager', PromptManager())
    
    def _run(self, *args, **kwargs) -> str:
        """执行表描述分析的主入口方法"""
        self.logger.info(f"🔧 {self.name}: 开始表描述分析")
        
        try:
            # 初始化必要的服务
            if not self.memory_manager:
                self.memory_manager = ComponentManager.create_memory_manager(self.settings)
            
            # 1. 检查依赖：需要schema_extraction_tool和column_analysis_tool的结果
            self._check_dependencies()
            
            # # 2. 从Neo4j读取数据库结构和列描述信息
            # analysis_context = self._read_table_context_from_neo4j()
            # if not analysis_context['tables']:
            #     return "❌ 表描述分析失败: 未找到表信息"
            
            # self.logger.info(f"📖 从Neo4j读取到 {len(analysis_context['tables'])} 个表")
            
            # # 3. 逐表生成业务描述
            # descriptions = []
            # llm_success_count = 0
            
            # for table_info in analysis_context['tables']:
            #     description = self._generate_table_description_with_llm(table_info, analysis_context)
            #     if description:
            #         descriptions.append(description)
            #         llm_success_count += 1
            #         self.logger.debug(f"✅ 表 {table_info['table_name']} 描述生成完成")
            #     else:
            #         raise_tool_error(
            #             self.name,
            #             f"表 {table_info['table_name']} LLM描述生成失败"
            #         )
            
            # # 4. 将描述结果注入到Neo4j Table节点属性
            # updated_count = 0
            # for description in descriptions:
            #     try:
            #         self._update_table_description(description)
            #         updated_count += 1
            #     except Exception as e:
            #         self.logger.error(f"注入表描述失败 {description['table_name']}: {e}")
            #         raise_tool_error(self.name, f"表描述注入失败: {str(e)}")
            

            # 6. 构建返回消息
            result_message = "✅ table_analysis_tool 分析完成，已存储到Neo4j，请务必继续执行 er_analysis_tool 工具。"
            
            self.logger.info(f"✅ {self.name}: 表描述分析完成。")
            return result_message
            
        except Exception as e:
            error_msg = f"表描述分析失败: {str(e)}"
            self.logger.error(f"❌ {self.name}: {error_msg}")
            return f"❌ {error_msg}"
    
    def _check_dependencies(self) -> None:
        """检查schema_extraction_tool和column_analysis_tool依赖 - 采用快速失败模式"""
        if not self.memory_manager or not getattr(self.memory_manager, 'neo4j_graph', None):
            raise_dependency_error(
                self.name,
                "Neo4j连接不可用，无法读取schema和column信息"
            )
            
        # 检查是否存在Table节点（验证schema_extraction_tool已执行）
        cypher = "MATCH (t:Table) RETURN count(t) as count LIMIT 1"
        result = self.memory_manager.neo4j_graph.query(cypher)
        
        if not result or result[0]['count'] == 0:
            raise_dependency_error(
                self.name,
                "未找到Table节点，需要先执行schema_extraction_tool"
            )
        
        # 检查是否存在列的ai_business_desc属性（验证column_analysis_tool已执行）
        cypher = "MATCH (c:Column) WHERE c.ai_business_desc IS NOT NULL RETURN count(c) as count LIMIT 1"
        result = self.memory_manager.neo4j_graph.query(cypher)
        
        if not result or result[0]['count'] == 0:
            raise_dependency_error(
                self.name,
                "未找到列AI业务描述信息，需要先执行column_analysis_tool"
            )
    
    def _read_table_context_from_neo4j(self) -> Dict[str, Any]:
        """从Neo4j读取表分析上下文信息"""
        try:
            # 读取数据库和表基本信息，以及列的完整分析信息
            cypher = """
            MATCH (d:Database)-[:CONTAINS]->(t:Table)-[:HAS_COLUMN]->(c:Column)
            WHERE c.ai_business_desc IS NOT NULL
            RETURN d.name as database_name,
                   d.business_desc as database_desc,
                   t.name as table_name,
                   collect({
                       column_name: c.name,
                       data_type: c.data_type,
                       ai_business_desc: c.ai_business_desc,
                       category: c.category,
                       category_desc: c.category_desc,
                       entropy_level: c.entropy_level,
                       sample_values: CASE 
                           WHEN size(c.sample_values) > 5 
                           THEN c.sample_values[0..5] 
                           ELSE c.sample_values 
                       END,
                       is_nullable: c.is_nullable,
                       is_primary: c.is_primary,
                       is_foreign: c.is_foreign,
                       comment: c.comment
                   }) as columns
            ORDER BY t.name
            """
            
            result = self.memory_manager.neo4j_graph.query(cypher)
            if not result:
                raise_dependency_error(self.name, "Neo4j查询返回空结果")
            
            # 按表分组整理数据
            tables = {}
            database_name = "unknown"
            database_desc = ""
            
            for row in result:
                if not database_name or database_name == "unknown":
                    database_name = row['database_name']
                    database_desc = row.get('database_desc', '')
                
                table_name = row['table_name']
                if table_name not in tables:
                    tables[table_name] = {
                        'table_name': table_name,
                        'columns': []
                    }
                
                tables[table_name]['columns'] = row['columns']
            
            context_data = {
                "database_name": database_name,
                "database_desc": database_desc,
                "tables": list(tables.values())
            }
            
            self.logger.info(f"📊 从Neo4j读取到 {len(context_data['tables'])} 个表的上下文信息")
            
            return context_data
        except Exception as e:
            self.logger.error(f"❌ Neo4j表上下文查询失败: {e}")
            raise_dependency_error(
                self.name,
                f"Neo4j表上下文查询失败: {str(e)}"
            )
    
    def _generate_table_description_with_llm(self, table_info: Dict[str, Any], 
                                           context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """使用LLM对单个表生成业务描述"""
        try:
            # 使用PromptManager渲染模板
            prompt_text = self._render_table_description_prompt(table_info, context)
            
            # 直接调用LLM（使用预初始化的实例）
            response = self.llm.invoke(prompt_text)
            llm_response = response.content if hasattr(response, 'content') else str(response)
            if not llm_response:
                return None
            
            # 构建描述结果
            description = {
                "table_name": table_info['table_name'],
                "ai_business_desc": llm_response
            }
            
            return description
            
        except Exception as e:
            self.logger.error(f"LLM表描述生成失败 {table_info['table_name']}: {e}")
            return None
    
    def _render_table_description_prompt(self, table_info: Dict[str, Any], 
                                       context: Dict[str, Any]) -> str:
        """使用PromptManager渲染表描述提示词模板"""
        columns = table_info.get('columns', [])
        
        # 构建包含列注释的DDL
        table_ddl_with_comments = self._build_table_ddl_with_comments(table_info)
        
        # 进行表级特征分析
        category_stats = self._analyze_field_category_distribution(columns)
        entropy_stats = self._analyze_entropy_distribution(columns)
        representative_samples = self._extract_representative_samples(columns)
        business_pattern = self._infer_table_business_pattern(category_stats, entropy_stats)
        entropy_guidance = self._get_entropy_guidance(entropy_stats)
        
        # 统计主键外键数量
        primary_key_count = sum(1 for col in columns if col.get('is_primary', False))
        foreign_key_count = sum(1 for col in columns if col.get('is_foreign', False))
        
        # 准备完整的模板变量
        template_vars = {
            "table_name": table_info.get('table_name', ''),
            "database_name": context.get('database_name', '未知数据库'),
            "database_domain": context.get('database_desc', '通用业务领域'),
            "table_schema_with_comments_ddl": table_ddl_with_comments,
            "total_columns": len(columns),
            "field_category_stats": category_stats,
            "entropy_stats": entropy_stats,
            "representative_samples": representative_samples,
            "table_business_pattern": business_pattern,
            "entropy_guidance": entropy_guidance,
            "primary_key_count": primary_key_count,
            "foreign_key_count": foreign_key_count
        }
        
        # 使用实例级别的prompt_manager渲染模板
        return self.prompt_manager.get_tool_prompt("table_description", **template_vars)
    
    def _build_table_ddl_with_comments(self, table_info: Dict[str, Any]) -> str:
        """构建包含丰富元数据的表DDL"""
        table_name = table_info['table_name']
        columns = table_info['columns']
        
        lines = [f"CREATE TABLE `{table_name}` ("]
        
        column_defs = []
        for col in columns:
            # 基本列定义
            col_def = f"  `{col['column_name']}` {col.get('data_type', 'VARCHAR(255)')}"
            
            # 约束
            if not col.get('is_nullable', True):
                col_def += " NOT NULL"
            if col.get('is_primary', False):
                col_def += " PRIMARY KEY"
            
            # 构建增强的列注释（包含AI描述、类别和样本信息）
            comment_parts = []
            
            # AI业务描述
            ai_desc = col.get('ai_business_desc', '')
            if ai_desc:
                comment_parts.append(ai_desc)
            elif col.get('comment'):
                comment_parts.append(col.get('comment', ''))
            
            # 字段分类信息
            category_desc = col.get('category_desc', '')
            entropy_level = col.get('entropy_level', '')
            if category_desc and entropy_level:
                comment_parts.append(f"[{category_desc}-{entropy_level}熵值]")
            elif category_desc:
                comment_parts.append(f"[{category_desc}]")
            
            # 样本值信息
            sample_values = col.get('sample_values', [])
            if sample_values:
                formatted_samples = []
                for sample in sample_values[:3]:  # 最多显示3个样本
                    if sample is not None:
                        sample_str = str(sample)
                        if len(sample_str) > 15:  # 限制样本值长度
                            sample_str = sample_str[:12] + "..."
                        formatted_samples.append(sample_str)
                
                if formatted_samples:
                    comment_parts.append(f"[样本:{','.join(formatted_samples)}]")
            
            # 组合注释
            if comment_parts:
                full_comment = ' '.join(comment_parts)
                col_def += f" COMMENT '{full_comment}'"
            
            column_defs.append(col_def)
        
        lines.extend([f"{cd}," if i < len(column_defs) - 1 else cd 
                     for i, cd in enumerate(column_defs)])
        lines.append(");")
        
        # 添加表特征摘要注释
        lines.append("")
        lines.append("-- 表特征摘要:")
        
        # 分析字段分布
        category_stats = self._analyze_field_category_distribution(columns)
        entropy_stats = self._analyze_entropy_distribution(columns)
        
        category_summary = []
        for category, stats in category_stats.items():
            category_summary.append(f"{stats['category_desc']}({stats['count']}个)")
        lines.append(f"-- 字段分类: {', '.join(category_summary)}")
        
        lines.append(f"-- 数据特征: 低熵值{entropy_stats['low_percentage']}%, 中熵值{entropy_stats['medium_percentage']}%, 高熵值{entropy_stats['high_percentage']}%")
        
        # 推断业务模式
        business_pattern = self._infer_table_business_pattern(category_stats, entropy_stats)
        lines.append(f"-- 业务模式: {business_pattern}")
        
        return "\\n".join(lines)
    

    def _analyze_field_category_distribution(self, columns: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析字段类别分布统计"""
        category_stats = {}
        total_columns = len(columns)
        
        # 统计各类别数量
        category_counts = {}
        category_examples = {}
        
        for col in columns:
            category = col.get('category', 'other')
            category_desc = col.get('category_desc', '其他字段')
            
            if category not in category_counts:
                category_counts[category] = 0
                category_examples[category] = []
            
            category_counts[category] += 1
            if len(category_examples[category]) < 3:  # 保留前3个作为示例
                category_examples[category].append(col.get('column_name', ''))
        
        # 构建统计结果
        for category, count in category_counts.items():
            category_desc = next((col.get('category_desc', '其他字段') for col in columns 
                                if col.get('category') == category), '其他字段')
            category_stats[category] = {
                'category_desc': category_desc,
                'count': count,
                'percentage': round((count / total_columns) * 100, 1),
                'example_fields': category_examples[category]
            }
        
        return category_stats
    
    def _analyze_entropy_distribution(self, columns: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析Neo4j中已有的熵值分布特征"""
        entropy_counts = {'low': 0, 'medium': 0, 'high': 0}
        total_columns = len(columns) if columns else 1  # 避免除零
        
        # 直接统计Neo4j中已计算的熵值等级
        for col in columns:
            entropy_level = col.get('entropy_level', 'medium')
            if entropy_level in entropy_counts:
                entropy_counts[entropy_level] += 1
            else:
                # 处理可能的其他熵值等级，归类到medium
                entropy_counts['medium'] += 1
        
        return {
            'low_count': entropy_counts['low'],
            'medium_count': entropy_counts['medium'],  
            'high_count': entropy_counts['high'],
            'low_percentage': round((entropy_counts['low'] / total_columns) * 100, 1) if total_columns > 0 else 0,
            'medium_percentage': round((entropy_counts['medium'] / total_columns) * 100, 1) if total_columns > 0 else 0,
            'high_percentage': round((entropy_counts['high'] / total_columns) * 100, 1) if total_columns > 0 else 0
        }
    
    def _extract_representative_samples(self, columns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """提取代表性样本值"""
        representative_samples = []
        
        for col in columns:
            column_name = col.get('column_name', '')
            category_desc = col.get('category_desc', '其他字段')
            sample_values = col.get('sample_values', [])
            
            if sample_values:
                # 格式化样本值，最多显示3个
                formatted_samples = []
                for sample in sample_values[:3]:
                    if sample is not None:
                        sample_str = str(sample)
                        if len(sample_str) > 20:
                            sample_str = sample_str[:17] + "..."
                        formatted_samples.append(sample_str)
                
                if formatted_samples:
                    representative_samples.append({
                        'field_name': column_name,
                        'category_desc': category_desc,
                        'samples': ', '.join(formatted_samples)
                    })
        
        return representative_samples
    
    def _infer_table_business_pattern(self, category_stats: Dict[str, Any], 
                                    entropy_stats: Dict[str, Any]) -> str:
        """基于字段特征推断表的业务模式"""
        # 分析主键外键数量
        has_many_identifiers = category_stats.get('identifier', {}).get('count', 0) >= 2
        has_many_dimensions = category_stats.get('dimension', {}).get('count', 0) >= 3
        has_measures = category_stats.get('measure', {}).get('count', 0) > 0
        
        # 分析熵值分布
        low_entropy_dominant = entropy_stats.get('low_percentage', 0) > 60
        high_entropy_dominant = entropy_stats.get('high_percentage', 0) > 40
        
        if low_entropy_dominant and has_many_dimensions:
            return "字典码表类型 - 主要存储枚举和分类信息"
        elif has_many_identifiers and high_entropy_dominant:
            return "主数据表类型 - 存储核心业务实体信息"
        elif has_measures and has_many_dimensions:
            return "事实表类型 - 记录业务交易和度量数据"
        elif has_many_dimensions:
            return "维度表类型 - 提供业务分析的分类维度"
        else:
            return "通用业务表 - 支持日常业务操作"
    
    def _get_entropy_guidance(self, entropy_stats: Dict[str, Any]) -> str:
        """根据熵值分布生成指导信息"""
        low_pct = entropy_stats.get('low_percentage', 0)
        medium_pct = entropy_stats.get('medium_percentage', 0)
        high_pct = entropy_stats.get('high_percentage', 0)
        
        if low_pct > 60:
            return "数据重复度高，主要为状态、类型、等级等枚举类信息"
        elif high_pct > 40:
            return "数据多样性强，包含大量标识符、名称、金额等独特值"
        elif medium_pct > 50:
            return "数据分散适中，平衡了分类信息和个性化数据"
        else:
            return "数据特征混合，包含多种类型的业务信息"
    
    def _update_table_description(self, description: Dict[str, Any]) -> None:
        """将表描述结果注入到Neo4j Table节点属性中"""
        
        # 使用CONTAINS关系模式，将ai_business_desc作为Table节点属性注入
        cypher = '''
        MATCH (d:Database)-[:CONTAINS]->(t:Table {name: $table_name})
        SET t.ai_business_desc = $ai_business_desc,
            t.ai_business_desc_timestamp = datetime()
        RETURN t
        '''
        # 使用CONTAINS关系模式，将ai_business_desc作为Table节点属性注入
        parser = SemanticSQLOutputParser()
        description['ai_business_desc'] = parser._clean_think_content(description['ai_business_desc'])

        params = {
            "table_name": description['table_name'],
            "ai_business_desc": description['ai_business_desc']
        }
        
        self.memory_manager.neo4j_graph.query(cypher, params)
        
        self.logger.info(f"✅ 已将AI业务描述注入到Table节点 '{description['table_name']}' 的ai_business_desc属性")


# ========== 便利函数 ==========
def create_table_analysis_tool(memory_manager: Optional['Neo4jMemoryManager'] = None,
                               database_manager: Optional[DatabaseManager] = None) -> TableAnalysisTool:
    """创建表描述分析工具的便利函数"""
    return TableAnalysisTool(
        memory_manager=memory_manager,
        database_manager=database_manager
    )