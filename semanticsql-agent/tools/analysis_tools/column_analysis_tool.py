"""
列描述分析工具 - 基于field_analysis_tool架构重构

基于schema_extraction_tool和field_analysis_tool的结果，
为数据库列生成详细的业务描述和领域特定说明。
整合pipeline的column_description_pipeline算法。
"""

from typing import Dict, Any, List, Optional
import json
import logging
from datetime import datetime
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


class ColumnAnalysisTool(BaseSemanticSQLTool):
    """列描述分析工具 - 重构版本
    
    核心职责：
    - 从Neo4j读取schema和field_analysis结果
    - 使用LLM生成列的业务描述和领域说明
    - 将描述结果注入到Neo4j Column节点
    - 支持领域知识和熵值信息的智能分析
    
    设计原则：
    - 数据复用：直接从Neo4j读取已有信息
    - LLM驱动：采用column_description模板进行智能分析
    - 快速失败：错误立即暴露，无降级逻辑
    - 属性注入：将结果直接存储到Column节点属性
    """
    
    name: str = "column_analysis_tool"
    description: str = "基于LLM的列业务描述生成，结合领域知识和字段分类信息"
    
    # 组件依赖（可选注入）
    memory_manager: Optional[Neo4jMemoryManager] = Field(default=None, exclude=True)
    database_manager: Optional[DatabaseManager] = Field(default=None, exclude=True)
    llm: Optional[ChatOpenAI] = Field(default=None, exclude=True)
    settings: Optional[Any] = Field(default=None, exclude=True)
    prompt_manager: Optional[Any] = Field(default=None, exclude=True)
    
    def __init__(self, memory_manager: Optional['Neo4jMemoryManager'] = None, 
                 database_manager: Optional[DatabaseManager] = None, **kwargs):
        """
        初始化列描述分析工具
        
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
        """执行列描述分析的主入口方法"""
        self.logger.info(f"🔧 {self.name}: 开始列描述分析")
        
        try:
            # 初始化必要的服务
            if not self.memory_manager:
                self.memory_manager = ComponentManager.create_memory_manager(self.settings)
            
            # 1. 检查依赖：需要schema_extraction_tool和field_analysis_tool的结果
            self._check_dependencies()
            
            # 2. 从Neo4j读取数据库结构和字段分类信息
            analysis_context = self._read_analysis_context_from_neo4j()
            if not analysis_context['columns']:
                return "❌ 列描述分析失败: 未找到列信息"
            
            self.logger.info(f"📖 从Neo4j读取到 {len(analysis_context['columns'])} 个列")
            
            # 3. 逐列生成业务描述
            descriptions = []
            llm_success_count = 0
            
            for column_info in analysis_context['columns']:
                description = self._generate_column_description_with_llm(column_info, analysis_context)
                if description:
                    descriptions.append(description)
                    llm_success_count += 1
                    self.logger.debug(f"✅ 列 {column_info['field_name']} 描述生成完成")
                else:
                    raise_tool_error(
                        self.name,
                        f"列 {column_info['field_name']} LLM描述生成失败"
                    )
            
            # 4. 将描述结果注入到Neo4j Column节点属性
            updated_count = 0
            for description in descriptions:
                try:
                    self._update_column_description(description)
                    updated_count += 1
                except Exception as e:
                    self.logger.error(f"注入列描述失败 {description['field_name']}: {e}")
                    raise_tool_error(self.name, f"列描述注入失败: {str(e)}")
            
            # 5. 生成统计报告
            success_rate = (llm_success_count / len(analysis_context['columns'])) * 100 if analysis_context['columns'] else 0
            
            # 6. 构建返回消息
            result_message = self._build_success_message(len(analysis_context['columns']), updated_count, success_rate)
            
            self.logger.info(f"✅ {self.name}: 列描述分析完成 - 分析了 {len(analysis_context['columns'])} 个列")
            return result_message
            
        except Exception as e:
            error_msg = f"列描述分析失败: {str(e)}"
            self.logger.error(f"❌ {self.name}: {error_msg}")
            return f"❌ {error_msg}"
    
    def _check_dependencies(self) -> None:
        """检查schema_extraction_tool和field_analysis_tool依赖 - 采用快速失败模式"""
        if not self.memory_manager or not getattr(self.memory_manager, 'neo4j_graph', None):
            raise_dependency_error(
                self.name,
                "Neo4j连接不可用，无法读取schema和field信息"
            )
            
        # 检查是否存在Column节点（验证schema_extraction_tool已执行）
        cypher = "MATCH (c:Column) RETURN count(c) as count LIMIT 1"
        result = self.memory_manager.neo4j_graph.query(cypher)
        
        if not result or result[0]['count'] == 0:
            raise_dependency_error(
                self.name,
                "未找到Column节点，需要先执行schema_extraction_tool"
            )
        
        # 检查是否存在category属性（验证field_analysis_tool已执行）
        cypher = "MATCH (c:Column) WHERE c.category IS NOT NULL RETURN count(c) as count LIMIT 1"
        result = self.memory_manager.neo4j_graph.query(cypher)
        
        if not result or result[0]['count'] == 0:
            raise_dependency_error(
                self.name,
                "未找到字段分类信息，需要先执行field_analysis_tool"
            )
    
    def _read_analysis_context_from_neo4j(self) -> Dict[str, Any]:
        """从Neo4j读取分析上下文信息"""
        try:
            # 读取数据库基本信息
            cypher = """
            MATCH (d:Database)
            OPTIONAL MATCH (d)-[:CONTAINS]->(t:Table)-[:HAS_COLUMN]->(c:Column)
            RETURN d.name as database_name,
                   d.business_desc as database_desc,
                   collect(DISTINCT {
                       table_name: t.name,
                       column_name: c.name,
                       field_name: t.name + '.' + c.name,
                       data_type: c.data_type,
                       is_nullable: c.is_nullable,
                       is_primary: c.is_primary,
                       is_foreign: c.is_foreign,
                       category: c.category,
                       category_desc: c.category_desc,
                       entropy_level: c.entropy_level,
                       sample_values: CASE 
                           WHEN size(c.sample_values) > 3 
                           THEN c.sample_values[0..3] 
                           ELSE c.sample_values 
                       END,
                       comment: c.comment
                   }) as columns
            """
            
            result = self.memory_manager.neo4j_graph.query(cypher)
            if not result:
                raise_dependency_error(self.name, "Neo4j查询返回空结果")
            
            context_data = result[0]
            # 过滤掉空的列记录
            if context_data and "columns" in context_data:
                context_data["columns"] = [col for col in context_data["columns"] if col.get("column_name")]
            else:
                context_data = {"database_name": "unknown", "database_desc": "", "columns": []}
            
            # 读取表结构DDL信息
            context_data["table_ddls"] = self._read_table_ddls()
            
            self.logger.info(f"📊 从Neo4j读取到 {len(context_data['columns'])} 个列的上下文信息")
            
            return context_data
        except Exception as e:
            self.logger.error(f"❌ Neo4j上下文查询失败: {e}")
            raise_dependency_error(
                self.name,
                f"Neo4j上下文查询失败: {str(e)}"
            )
    
    def _read_table_ddls(self) -> Dict[str, str]:
        """读取表DDL信息"""
        try:
            cypher = """
            MATCH (d:Database)-[:CONTAINS]->(t:Table)-[:HAS_COLUMN]->(c:Column)
            RETURN t.name as table_name,
                   collect({
                       name: c.name,
                       data_type: c.data_type,
                       is_nullable: c.is_nullable,
                       is_primary: c.is_primary,
                       is_foreign: c.is_foreign,
                       comment: c.comment
                   }) as columns
            ORDER BY t.name
            """
            
            result = self.memory_manager.neo4j_graph.query(cypher)
            table_ddls = {}
            
            for row in result:
                table_name = row['table_name']
                columns = row['columns']
                table_ddls[table_name] = self._format_table_ddl(table_name, columns)
            
            return table_ddls
        except Exception as e:
            self.logger.warning(f"⚠️ 读取表DDL失败: {e}")
            return {}
    
    def _format_table_ddl(self, table_name: str, columns: List[Dict[str, Any]]) -> str:
        """格式化表DDL"""
        lines = [f"CREATE TABLE `{table_name}` ("]
        
        column_defs = []
        for col in columns:
            col_def = f"  `{col['name']}` {col.get('data_type', 'VARCHAR(255)')}"
            if not col.get('is_nullable', True):
                col_def += " NOT NULL"
            if col.get('is_primary', False):
                col_def += " PRIMARY KEY"
            if col.get('comment'):
                col_def += f" COMMENT '{col['comment']}'"
            column_defs.append(col_def)
        
        lines.extend([f"{cd}," if i < len(column_defs) - 1 else cd 
                     for i, cd in enumerate(column_defs)])
        lines.append(");")
        
        return "\\n".join(lines)
    
    def _generate_column_description_with_llm(self, column_info: Dict[str, Any], 
                                           context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """使用LLM对单个列生成业务描述"""
        try:
            # 使用PromptManager渲染模板
            prompt_text = self._render_column_description_prompt(column_info, context)
            
            # 直接调用LLM（使用预初始化的实例）
            response = self.llm.invoke(prompt_text)
            llm_response = response.content if hasattr(response, 'content') else str(response)
            if not llm_response:
                return None
            
            # 解析LLM响应，提取列描述
            description_text = self._parse_description_response(llm_response)
            if not description_text:
                return None
            
            # 构建描述结果
            description = {
                "field_name": column_info['field_name'],
                "table_name": column_info['table_name'],
                "column_name": column_info['column_name'],
                "ai_business_desc": description_text,
                "generated_timestamp": datetime.now().isoformat()
            }
            
            return description
            
        except Exception as e:
            self.logger.error(f"LLM列描述生成失败 {column_info['field_name']}: {e}")
            return None
    
    def _render_column_description_prompt(self, column_info: Dict[str, Any], 
                                        context: Dict[str, Any]) -> str:
        """使用PromptManager渲染列描述提示词模板"""
        # 准备模板变量
        template_vars = {
            "table_name": column_info.get('table_name', ''),
            "column_name": column_info.get('column_name', ''),
            "database_name": context.get('database_name', '未知数据库'),
            "database_domain": self._extract_domain_from_desc(context.get('database_desc', '')),
            "table_ddl": context.get('table_ddls', {}).get(column_info.get('table_name', ''), ''),
            "column_type": column_info.get('data_type', ''),
            "is_nullable": column_info.get('is_nullable', True),
            "is_primary_key": column_info.get('is_primary', False),
            "is_foreign_key": column_info.get('is_foreign', False),
            "column_examples": column_info.get('sample_values', []),
            "field_category": column_info.get('category', 'other'),
            "dim_or_meas": self._get_dim_or_meas(column_info.get('category', 'other')),
            "field_importance": self._get_field_importance(column_info.get('category', 'other')),
            "entropy_info": self._get_entropy_info(column_info)
        }
        
        # 使用实例级别的prompt_manager渲染模板
        return self.prompt_manager.get_tool_prompt("column_description", **template_vars)
    
    def _extract_domain_from_desc(self, database_desc: str) -> str:
        """从数据库描述中提取领域信息"""
        if not database_desc:
            return "通用业务"
        
        # 简单的关键词匹配提取领域
        if "【业务领域】" in database_desc:
            start = database_desc.find("【业务领域】") + 6
            end = database_desc.find("\\n", start)
            if end > start:
                return database_desc[start:end].strip()
        
        return "通用业务"
    
    def _get_dim_or_meas(self, category: str) -> str:
        """直接返回category给LLM"""
        return category
    
    def _get_field_importance(self, category: str) -> str:
        """直接返回category给LLM"""
        return category
    
    def _get_entropy_info(self, column_info: Dict[str, Any]) -> Dict[str, Any]:
        """直接从Neo4j获取熵值信息"""
        return {
            "level": column_info.get('entropy_level', 'medium')
        }
    
    def _parse_description_response(self, response: str) -> Optional[str]:
        """解析LLM描述响应"""
        try:
            # 直接返回响应内容，去除首尾空白
            description = response.strip()
            
            # 检查是否为空或过短
            if not description or len(description) < 2:
                return None
            
            return description
            
        except Exception as e:
            self.logger.warning(f"解析LLM描述响应失败: {e}")
            return None
    
    def _update_column_description(self, description: Dict[str, Any]) -> None:
        """将列描述结果注入到Neo4j Column节点属性中"""
        
        # 使用CONTAINS关系模式，将ai_business_desc作为Column节点属性注入
        cypher = '''
        MATCH (d:Database)-[:CONTAINS]->(t:Table {name: $table_name})-[:HAS_COLUMN]->(c:Column {name: $column_name})
        SET c.ai_business_desc = $ai_business_desc,
            c.ai_business_desc_timestamp = datetime()
        RETURN c
        '''
        
        params = {
            "table_name": description['table_name'],
            "column_name": description['column_name'],
            "ai_business_desc": description['ai_business_desc']
        }
        
        self.memory_manager.neo4j_graph.query(cypher, params)
        
        self.logger.info(f"✅ 已将AI业务描述注入到Column节点 '{description['field_name']}' 的ai_business_desc属性")
    
    def _build_success_message(self, total_columns: int, updated_count: int, success_rate: float) -> str:
        """构建成功返回消息"""
        result = f"""✅ 列描述分析完成

🔍 分析结果:
  • 分析列总数: {total_columns}
  • 成功注入列: {updated_count}
  • LLM生成成功率: {success_rate:.1f}%
  
💾 AI业务描述结果已注入到Neo4j Column节点的ai_business_desc属性，可供后续工具使用"""
        
        return result


# ========== 便利函数 ==========
def create_column_analysis_tool(memory_manager: Optional['Neo4jMemoryManager'] = None,
                               database_manager: Optional[DatabaseManager] = None) -> ColumnAnalysisTool:
    """创建列描述分析工具的便利函数"""
    return ColumnAnalysisTool(
        memory_manager=memory_manager,
        database_manager=database_manager
    )