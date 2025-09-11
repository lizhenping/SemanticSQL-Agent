"""
表描述分析工具 - 基于column_analysis_tool架构重构

基于schema_extraction_tool和column_analysis_tool的结果，
为数据库表生成详细的业务描述和领域特定说明。
整合pipeline的table_description_pipeline算法。
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
            
            # 2. 从Neo4j读取数据库结构和列描述信息
            analysis_context = self._read_table_context_from_neo4j()
            if not analysis_context['tables']:
                return "❌ 表描述分析失败: 未找到表信息"
            
            self.logger.info(f"📖 从Neo4j读取到 {len(analysis_context['tables'])} 个表")
            
            # 3. 逐表生成业务描述
            descriptions = []
            llm_success_count = 0
            
            for table_info in analysis_context['tables']:
                description = self._generate_table_description_with_llm(table_info, analysis_context)
                if description:
                    descriptions.append(description)
                    llm_success_count += 1
                    self.logger.debug(f"✅ 表 {table_info['table_name']} 描述生成完成")
                else:
                    raise_tool_error(
                        self.name,
                        f"表 {table_info['table_name']} LLM描述生成失败"
                    )
            
            # 4. 将描述结果注入到Neo4j Table节点属性
            updated_count = 0
            for description in descriptions:
                try:
                    self._update_table_description(description)
                    updated_count += 1
                except Exception as e:
                    self.logger.error(f"注入表描述失败 {description['table_name']}: {e}")
                    raise_tool_error(self.name, f"表描述注入失败: {str(e)}")
            
            # 5. 生成统计报告
            success_rate = (llm_success_count / len(analysis_context['tables'])) * 100 if analysis_context['tables'] else 0
            
            # 6. 构建返回消息
            result_message = self._build_success_message(len(analysis_context['tables']), updated_count, success_rate)
            
            self.logger.info(f"✅ {self.name}: 表描述分析完成 - 分析了 {len(analysis_context['tables'])} 个表")
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
            # 读取数据库和表基本信息，以及列的AI描述
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
            
            # 解析LLM响应，提取表描述
            description_text = self._parse_description_response(llm_response)
            if not description_text:
                return None
            
            # 构建描述结果
            description = {
                "table_name": table_info['table_name'],
                "ai_business_desc": description_text,
                "generated_timestamp": datetime.now().isoformat()
            }
            
            return description
            
        except Exception as e:
            self.logger.error(f"LLM表描述生成失败 {table_info['table_name']}: {e}")
            return None
    
    def _render_table_description_prompt(self, table_info: Dict[str, Any], 
                                       context: Dict[str, Any]) -> str:
        """使用PromptManager渲染表描述提示词模板"""
        # 构建包含列注释的DDL
        table_ddl_with_comments = self._build_table_ddl_with_comments(table_info)
        
        # 准备模板变量
        template_vars = {
            "table_name": table_info.get('table_name', ''),
            "database_name": context.get('database_name', '未知数据库'),
            "database_domain": context.get('database_desc', '通用业务领域'),
            "table_schema_with_comments_ddl": table_ddl_with_comments
        }
        
        # 使用实例级别的prompt_manager渲染模板
        return self.prompt_manager.get_tool_prompt("table_description", **template_vars)
    
    def _build_table_ddl_with_comments(self, table_info: Dict[str, Any]) -> str:
        """构建包含列注释的表DDL"""
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
            
            # 添加AI生成的列注释
            ai_desc = col.get('ai_business_desc', '')
            if ai_desc:
                col_def += f" COMMENT '{ai_desc}'"
            elif col.get('comment'):
                col_def += f" COMMENT '{col['comment']}'"
            
            column_defs.append(col_def)
        
        lines.extend([f"{cd}," if i < len(column_defs) - 1 else cd 
                     for i, cd in enumerate(column_defs)])
        lines.append(");")
        
        return "\\n".join(lines)
    
    def _parse_description_response(self, response: str) -> Optional[str]:
        """解析LLM描述响应"""
        try:
            # 直接返回响应内容，去除首尾空白
            description = response.strip()
            
            # 检查是否为空或过短
            if not description or len(description) < 2:
                return None
            
            # 限制长度（最大50汉字）
            if len(description) > 50:
                description = description[:47] + "..."
            
            return description
            
        except Exception as e:
            self.logger.warning(f"解析LLM表描述响应失败: {e}")
            return None
    
    def _update_table_description(self, description: Dict[str, Any]) -> None:
        """将表描述结果注入到Neo4j Table节点属性中"""
        
        # 使用CONTAINS关系模式，将ai_business_desc作为Table节点属性注入
        cypher = '''
        MATCH (d:Database)-[:CONTAINS]->(t:Table {name: $table_name})
        SET t.ai_business_desc = $ai_business_desc,
            t.ai_business_desc_timestamp = datetime()
        RETURN t
        '''
        
        params = {
            "table_name": description['table_name'],
            "ai_business_desc": description['ai_business_desc']
        }
        
        self.memory_manager.neo4j_graph.query(cypher, params)
        
        self.logger.info(f"✅ 已将AI业务描述注入到Table节点 '{description['table_name']}' 的ai_business_desc属性")
    
    def _build_success_message(self, total_tables: int, updated_count: int, success_rate: float) -> str:
        """构建成功返回消息"""
        result = f"""✅ 表描述分析完成

🔍 分析结果:
  • 分析表总数: {total_tables}
  • 成功注入表: {updated_count}
  • LLM生成成功率: {success_rate:.1f}%
  
💾 AI业务描述结果已注入到Neo4j Table节点的ai_business_desc属性，可供后续工具使用"""
        
        return result


# ========== 便利函数 ==========
def create_table_analysis_tool(memory_manager: Optional['Neo4jMemoryManager'] = None,
                               database_manager: Optional[DatabaseManager] = None) -> TableAnalysisTool:
    """创建表描述分析工具的便利函数"""
    return TableAnalysisTool(
        memory_manager=memory_manager,
        database_manager=database_manager
    )