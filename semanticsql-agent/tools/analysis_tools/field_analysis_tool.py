"""
Field Analysis Tool - 基于field_classification_pipeline算法的Agent工具
集成LLM智能分类，直接使用schema_extraction_tool提供的数据
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

# 导入Pipeline的分类模型
try:
    import sys
    import os
    # 添加nl2sql_pipeline路径到sys.path
    pipeline_path = os.path.join(os.path.dirname(__file__), '../../../../nl2sql_pipeline/src')
    if pipeline_path not in sys.path:
        sys.path.append(pipeline_path)
    
    from nl2sql_pipeline.models.analysis import FieldCategory, FieldClassification
except ImportError as e:
    # 如果无法导入Pipeline模块，使用本地定义
    from enum import Enum
    from pydantic import BaseModel
    
    class FieldCategory(Enum):
        IDENTIFIER = "identifier"
        MEASURE = "measure" 
        DIMENSION = "dimension"
        DATETIME = "datetime"
        TEXT = "text"
        BOOLEAN = "boolean"
        OTHER = "other"


class FieldAnalysisTool(BaseSemanticSQLTool):
    """Field Analysis Tool - 集成Pipeline LLM分类算法
    
    核心职责：
    - 读取schema_extraction_tool提供的字段基础信息
    - 使用LLM进行智能字段分类
    - 更新Neo4j Column节点的分类属性
    - 生成分析统计报告
    
    设计原则：
    - 数据复用：直接使用已有的entropy_level和sample_values
    - LLM驱动：采用field_classification_pipeline的成熟算法
    - 简化处理：无批处理，逐字段分析
    - 属性更新：直接更新Neo4j Column节点属性
    """
    
    name: str = "field_analysis_tool"
    description: str = "基于LLM的智能字段语义分析和分类工具"
    
    # 组件依赖（可选注入）
    memory_manager: Optional[Neo4jMemoryManager] = Field(default=None, exclude=True)
    database_manager: Optional[DatabaseManager] = Field(default=None, exclude=True)
    llm: Optional[ChatOpenAI] = Field(default=None, exclude=True)
    settings: Optional[Any] = Field(default=None, exclude=True)
    prompt_manager: Optional[Any] = Field(default=None, exclude=True)
    
    def __init__(self, memory_manager: Optional['Neo4jMemoryManager'] = None, 
                 database_manager: Optional[DatabaseManager] = None, **kwargs):
        """
        初始化字段分析工具
        
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
        """执行字段分析的主入口方法"""
        self.logger.info(f"🔧 {self.name}: 开始字段分析")
        
        try:
            # 初始化必要的服务
            if not self.memory_manager:
                self.memory_manager = ComponentManager.create_memory_manager(self.settings)
            
            # 1. 检查依赖：需要schema_extraction_tool的结果
            self._check_schema_extraction_dependency()
            
            # 2. 从Neo4j读取字段信息
            field_infos = self._read_field_info_from_neo4j()
            if not field_infos:
                return "❌ 字段分析失败: 未找到字段信息"
            
            self.logger.info(f"📖 从Neo4j读取到 {len(field_infos)} 个字段")
            
            # 3. 逐字段进行LLM分类
            classifications = []
            llm_success_count = 0
            
            for field_info in field_infos:
                classification = self._classify_field_with_llm(field_info)
                if classification:
                    classifications.append(classification)
                    llm_success_count += 1
                    self.logger.debug(f"✅ 字段 {field_info['field_name']} 分类完成: {classification.get('category', 'unknown')}")
                else:
                    raise_tool_error(
                        self.name,
                        f"字段 {field_info['field_name']} LLM分类失败"
                    )
            
            # 4. 将分类结果注入到Neo4j Column节点属性
            updated_count = 0
            for classification in classifications:
                try:
                    self._update_column_classification(classification)
                    updated_count += 1
                except Exception as e:
                    self.logger.error(f"注入字段分类失败 {classification['field_name']}: {e}")
                    raise_tool_error(self.name, f"字段分类注入失败: {str(e)}")
            
            # 5. 生成统计报告

            # success_rate = (llm_success_count / len(field_infos)) * 100 if field_infos else 0
            # self.logger.info(f"✅ {self.name}: 字段分析完成 - 分析了 {len(field_infos)} 个字段,其中成功率是{success_rate}")
            result_message = "✅ field_analysis_tool分析完成，已存储到Neo4j，请务必继续执行 column_analysis_tool 工具。"
            return result_message
            
        except Exception as e:
            error_msg = f"字段分析失败: {str(e)}"
            self.logger.error(f"❌ {self.name}: {error_msg}")
            return f"❌ {error_msg}"
    
    def _init_config(self) -> Dict[str, Any]:
        """初始化配置参数"""
        return {
            "max_retries": 3,
            "sample_count": 3,  # 用于LLM分析的样本数量
            "default_importance": {
                "identifier": "high",
                "measure": "medium", 
                "dimension": "medium",
                "datetime": "medium",
                "text": "low",
                "boolean": "low",
                "other": "low"
            }
        }
    
    def _check_schema_extraction_dependency(self) -> None:
        """检查schema_extraction_tool依赖 - 采用快速失败模式"""
        if not self.memory_manager or not getattr(self.memory_manager, 'neo4j_graph', None):
            raise_dependency_error(
                self.name,
                "Neo4j连接不可用，无法读取schema信息"
            )
            
        # 检查是否存在Column节点（验证schema_extraction_tool已执行）  
        cypher = "MATCH (c:Column) RETURN count(c) as count LIMIT 1"
        result = self.memory_manager.neo4j_graph.query(cypher)
        
        if not result or result[0]['count'] == 0:
            raise_dependency_error(
                self.name,
                "未找到Column节点，需要先执行schema_extraction_tool"
            )
    
    def _read_field_info_from_neo4j(self) -> List[Dict[str, Any]]:
        """从Neo4j读取字段信息"""
        try:
            cypher = """
            MATCH (d:Database)-[:CONTAINS]->(t:Table)-[:HAS_COLUMN]->(c:Column)
            RETURN t.name as table_name,
                   c.name as column_name,
                   c.data_type as data_type,
                   c.is_primary as is_primary,
                   c.is_foreign as is_foreign,
                   c.is_nullable as is_nullable,
                   c.entropy_level as entropy_level,
                   c.sample_values as sample_values,
                   c.business_desc as business_desc
            ORDER BY t.name, c.name
            """
            
            results = self.memory_manager.neo4j_graph.query(cypher)
            
            field_infos = []
            for row in results:
                field_info = {
                    "field_name": f"{row['table_name']}.{row['column_name']}",
                    "table_name": row['table_name'],
                    "column_name": row['column_name'], 
                    "data_type": row['data_type'],
                    "is_primary": row.get('is_primary', False),
                    "is_foreign": row.get('is_foreign', False),
                    "is_nullable": row.get('is_nullable', True),
                    "entropy_level": row.get('entropy_level', 'medium'),  # 直接使用字符串等级
                    "sample_values": row.get('sample_values', []),
                    "business_desc": row.get('business_desc', '')
                }
                field_infos.append(field_info)
            
            return field_infos
        except Exception as e:
            raise_tool_error(self.name, f"Neo4j字段信息读取失败: {str(e)}")
    
    def _classify_field_with_llm(self, field_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """使用LLM对单个字段进行分类"""
        try:
            # 使用PromptManager渲染模板
            prompt_text = self._render_classification_prompt(field_info)
            
            # 直接调用LLM（使用预初始化的实例）
            response = self.llm.invoke(prompt_text)
            llm_response = response.content if hasattr(response, 'content') else str(response)
            if not llm_response:
                return None
            
            # 解析LLM响应，提取category和中文解释
            llm_result = self._parse_llm_response(llm_response)
            if not llm_result or 'category' not in llm_result or 'category_desc' not in llm_result:
                return None
            
            # 构建包含中文解释的分类结果
            classification = {
                "field_name": field_info['field_name'],
                "table_name": field_info['table_name'],
                "column_name": field_info['column_name'],
                "category": self._parse_category(llm_result.get('category', 'other')),
                "category_desc": llm_result['category_desc']
            }
            
            return classification
            
        except Exception as e:
            self.logger.error(f"LLM分类失败 {field_info['field_name']}: {e}")
            return None
    
    def _render_classification_prompt(self, field_info: Dict[str, Any]) -> str:
        """使用PromptManager渲染分类提示词模板"""
        # 准备模板变量
        template_vars = {
            "database_name": getattr(self, 'database_name', '未知数据库'),
            "table_name": field_info.get('table_name', ''),
            "field_name": field_info['field_name'],
            "data_type": field_info['data_type'], 
            "sample_values": field_info.get('sample_values', []),
            "entropy_level": field_info['entropy_level'],
            "is_primary": field_info.get('is_primary', False),
            "is_foreign": field_info.get('is_foreign', False),
            "is_nullable": field_info.get('is_nullable', True),
            "business_desc": field_info.get('business_desc', ''),
            "domain_type": getattr(self, 'domain_type', None),
            "domain_description": getattr(self, 'domain_description', None)
        }
        
        # 使用实例级别的prompt_manager渲染模板
        return self.prompt_manager.get_tool_prompt("field_analysis", **template_vars)
    
    
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """解析LLM响应 - 提取category和中文解释"""
        try:
            # 提取JSON
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                result = json.loads(json_str)
                
                # 提取category和category_desc
                if 'category' in result and 'category_desc' in result:
                    return {
                        'category': result['category'],
                        'category_desc': result['category_desc']
                    }
                    
        except Exception as e:
            self.logger.warning(f"解析LLM响应失败: {e}")
        
        return {}
    
    
    def _parse_category(self, category_str: str) -> str:
        """解析类别字符串（移植自Pipeline）"""
        category_map = {
            'identifier': FieldCategory.IDENTIFIER.value,
            'measure': FieldCategory.MEASURE.value,
            'dimension': FieldCategory.DIMENSION.value,
            'datetime': FieldCategory.DATETIME.value,
            'text': FieldCategory.TEXT.value,
            'boolean': FieldCategory.BOOLEAN.value,
            'other': FieldCategory.OTHER.value
        }
        return category_map.get(category_str.lower(), FieldCategory.OTHER.value)
    
    
    def _update_column_classification(self, classification: Dict[str, Any]) -> None:
        """将字段分类结果注入到Neo4j Column节点属性中"""
        
        # 使用CONTAINS关系模式，将category和category_desc作为Column节点属性注入
        cypher = '''
        MATCH (d:Database)-[:CONTAINS]->(t:Table {name: $table_name})-[:HAS_COLUMN]->(c:Column {name: $column_name})
        SET c.category = $category,
            c.category_desc = $category_desc,
            c.classification_timestamp = datetime()
        RETURN c
        '''
        
        params = {
            "table_name": classification['table_name'],
            "column_name": classification['column_name'],
            "category": classification['category'],
            "category_desc": classification['category_desc']
        }
        
        self.memory_manager.neo4j_graph.query(cypher, params)
        
        self.logger.info(f"✅ 已将字段类别 '{classification['category']}({classification['category_desc']})' 注入到Column节点 '{classification['field_name']}'")
    
    
    def _generate_classification_stats(self, classifications: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成分类统计信息 - 简化版本"""
        from collections import Counter
        
        category_counts = Counter()
        
        for c in classifications:
            category_counts[c['category']] += 1
        
        return {
            'total_fields': len(classifications),
            'category_distribution': dict(category_counts)
        }
    

# ========== 便利函数 ==========
def create_field_analysis_tool(memory_manager: Optional['Neo4jMemoryManager'] = None,
                               database_manager: Optional[DatabaseManager] = None) -> FieldAnalysisTool:
    """创建字段分析工具的便利函数"""
    return FieldAnalysisTool(
        memory_manager=memory_manager,
        database_manager=database_manager
    )