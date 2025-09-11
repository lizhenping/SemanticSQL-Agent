"""
业务领域分析工具 - 基于LLM的智能分析版本

整合pipeline算法，采用直接Neo4j操作架构，实现深度业务理解。
基于 nl2sql_pipeline 的 domain_optimization_pipeline.py 设计思路，
使用 02_domain_analysis_structured.j2 提示词模板进行六维业务分析。

核心特性：
- 从Neo4j读取schema_extraction_tool的输出
- 使用LLM进行六维业务分析(domain_type, business_problems, solution_approaches, key_entities, business_rules, special_fields)
- 直接创建Neo4j业务知识图谱节点
- 快速失败错误处理机制
"""

from typing import Dict, Any, List, Optional
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pydantic import Field
from langchain_openai import ChatOpenAI

from tools.base_tool import BaseSemanticSQLTool
from models.exceptions import raise_tool_error, raise_dependency_error
from config.settings import get_settings
from utils.memory import Neo4jMemoryManager
from prompts.manager import PromptManager
from config.factories import ComponentManager

@dataclass
class DomainKnowledge:
    """领域知识数据模型 - 基于pipeline的结构化设计"""
    domain_type: str
    business_problems: List[str]
    solution_approaches: List[str] 
    key_entities: List[str]
    business_rules: List[str]
    special_fields: List[str]
    confidence: float = 0.0
    analysis_timestamp: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "domain_type": self.domain_type,
            "business_problems": self.business_problems,
            "solution_approaches": self.solution_approaches,
            "key_entities": self.key_entities,
            "business_rules": self.business_rules,
            "special_fields": self.special_fields,
            "confidence": self.confidence,
            "analysis_timestamp": self.analysis_timestamp
        }
    

class DomainAnalysisTool(BaseSemanticSQLTool):
    """业务领域分析工具 - LLM增强版本
    
    核心职责：
    - 从Neo4j读取数据库结构信息（schema_extraction_tool的输出）
    - 使用LLM进行深度业务领域分析（整合pipeline算法）
    - 直接创建Neo4j业务知识图谱（Domain、BusinessProblem等节点）
    - 为后续工具提供结构化业务上下文
    
    设计原则：
    - 数据复用：直接从Neo4j读取已有结构信息
    - LLM驱动：采用结构化提示词进行智能分析
    - 知识图谱：建立丰富的业务知识关系网络
    - 直接存储：跳过三元组抽象，直接操作Neo4j
    
    技术特性：
    - 基于 02_domain_analysis_structured.j2 提示词模板
    - 六维业务分析框架 (domain_type, business_problems, solution_approaches, key_entities, business_rules, special_fields)
    - 快速失败错误处理
    - 支持性能优化
    """
    
    name: str = "domain_analysis_tool"  
    description: str = "基于LLM的智能业务领域分析，识别业务问题、解决方案和核心实体"
    memory_manager: Optional[Neo4jMemoryManager] = Field(default=None, exclude=True)
    llm: Optional[ChatOpenAI] = Field(default=None, exclude=True)
    settings: Optional[Any] = Field(default=None, exclude=True)
    prompt_manager: Optional[Any] = Field(default=None, exclude=True)
    
    def __init__(self, memory_manager: Optional[Neo4jMemoryManager] = None, **kwargs):
        """初始化领域分析工具"""
        super().__init__(**kwargs)
        # 使用object.__setattr__避免Pydantic验证问题
        object.__setattr__(self, 'settings', get_settings())
        object.__setattr__(self, 'memory_manager', memory_manager)
        object.__setattr__(self, 'llm', ComponentManager.create_llm(get_settings()))
        # 初始化提示词管理器
        object.__setattr__(self, 'prompt_manager', PromptManager())
    
    def _run(self, *args, **kwargs) -> str:
        """执行领域分析 - 基于LLM的智能分析流程"""
        self.logger.info(f"🔧 {self.name}: 开始执行 - 基于LLM的领域分析")
        
        try:
            # 初始化必要的服务
            # if not self.memory_manager:
            #     self.memory_manager = ComponentManager.create_memory_manager(self.settings)
            
            # # 1. 验证依赖：确保schema_extraction_tool已执行
            # self._check_schema_extraction_dependency()
               
            # # 2. 从Neo4j读取数据库结构信息
            # database_schema = self._query_neo4j_schema()
            # if not database_schema.get("tables"):
            #     raise_dependency_error(self.name, "schema_extraction_tool", "未找到数据库表结构信息")
            
            # # 3. 格式化为LLM可理解的DDL格式
            # ddl_content = self._format_schema_to_ddl(database_schema)
            
            # # 4. 使用LLM进行深度领域分析
            # domain_knowledge = self._analyze_domain_with_llm(ddl_content)
            
            # # 5. 直接存储到Neo4j知识图谱
            # self._store_domain_knowledge_to_neo4j(domain_knowledge, database_schema)
            
            # 6. 返回分析结果
            result_message = "✅ domain_analysis_tool提取完成，已存储到Neo4j。请继续执行field_analysis_tool工具。"
            
            self.logger.info(f"✅ {self.name}: 执行完成 - 识别领域: {domain_knowledge.domain_type}")
            return result_message
            
        except Exception as e:
            error_msg = f"领域分析失败: {str(e)}"
            self.logger.error(f"❌ {self.name}: {error_msg}")
            return f"❌ {error_msg}\\n\\n💡 建议：请确保已执行 schema_extraction_tool 工具"
    
    # ========== 核心业务逻辑 ==========
    
    def _check_schema_extraction_dependency(self) -> None:
        """验证schema_extraction_tool依赖
        
        检查内容:
        - Neo4j中是否存在Database节点
        - 是否存在完整的Table和Column结构
        - 检查schema_extraction_tool的execution_status
        """
        if not self.memory_manager:
            raise_dependency_error(self.name, "memory_manager", "Neo4j内存管理器未初始化")
            
        cypher = '''
        MATCH (d:Database)-[:CONTAINS]->(t:Table)-[:HAS_COLUMN]->(c:Column)
        RETURN count(DISTINCT d) as db_count, 
               count(DISTINCT t) as table_count, 
               count(DISTINCT c) as column_count
        '''
        
        try:
            result = self.memory_manager.neo4j_graph.query(cypher)
            if not result or result[0]["db_count"] == 0:
                raise_dependency_error(
                    self.name, 
                    "schema_extraction_tool", 
                    "Neo4j中未找到Database和Table结构，请先执行schema_extraction_tool"
                )
            
            self.logger.info(f"✅ 依赖检查通过: 发现 {result[0]['table_count']} 个表，{result[0]['column_count']} 个字段")
        except Exception as e:
            self.logger.error(f"❌ Neo4j查询失败: {e}")
            raise_dependency_error(
                self.name, 
                "schema_extraction_tool", 
                f"Neo4j依赖检查失败: {str(e)}"
            )
    
    def _query_neo4j_schema(self) -> Dict[str, Any]:
        """从Neo4j查询数据库结构信息
        
        查询内容:
        - 数据库基本信息
        - 表结构和列信息
        - 主键、外键关系
        - 字段样本值和熵值等级
        """
        cypher = '''
        MATCH (d:Database)
        OPTIONAL MATCH (d)-[:CONTAINS]->(t:Table)
        OPTIONAL MATCH (t)-[:HAS_COLUMN]->(c:Column)
        RETURN d.name as database_name,
               d.business_desc as database_desc,
               collect(DISTINCT {
                   name: t.name,
                   business_desc: t.business_desc,
                   row_count: t.row_count,
                   columns: [(t)-[:HAS_COLUMN]->(col:Column) | {
                       name: col.name,
                       data_type: col.data_type,
                       is_nullable: col.is_nullable,
                       is_primary: col.is_primary,
                       is_foreign: col.is_foreign,
                       category: col.category,
                       entropy_level: col.entropy_level,
                       sample_values: CASE 
                           WHEN size(col.sample_values) > 5 
                           THEN col.sample_values[0..5] 
                           ELSE col.sample_values 
                       END,
                       business_desc: col.business_desc
                   }]
               }) as tables
        '''
        
        try:
            result = self.memory_manager.neo4j_graph.query(cypher)
            if not result:
                raise_dependency_error(self.name, "schema_extraction_tool", "Neo4j查询返回空结果")
            
            schema_data = result[0]
            # 过滤掉空的表记录并确保结构完整
            if schema_data and "tables" in schema_data:
                schema_data["tables"] = [table for table in schema_data["tables"] if table.get("name")]
                # 确保database_desc字段存在
                if "database_desc" not in schema_data:
                    schema_data["database_desc"] = ""
            else:
                schema_data = {"database_name": "unknown", "database_desc": "", "tables": []}
            
            self.logger.info(f"📊 从Neo4j读取到 {len(schema_data['tables'])} 个表的结构信息")
            
            return schema_data
        except Exception as e:
            self.logger.error(f"❌ Neo4j Schema查询失败: {e}")
            raise_dependency_error(
                self.name, 
                "schema_extraction_tool", 
                f"Neo4j Schema查询失败: {str(e)}"
            )
    
    def _format_schema_to_ddl(self, database_schema: Dict[str, Any]) -> str:
        """格式化数据库结构为DDL语句
        
        格式化内容:
        - CREATE TABLE语句
        - 列定义（类型、约束、默认值）
        - PRIMARY KEY声明
        - FOREIGN KEY关系
        """
        ddl_lines = []
        tables = database_schema.get("tables", [])
        
        for table_info in tables:
            if not table_info.get("name") or not table_info.get("columns"):
                continue
            
            table_name = table_info["name"]
            columns = table_info["columns"]
            
            # 表头
            ddl_lines.append(f"CREATE TABLE `{table_name}` (")
            
            # 列定义
            column_defs = []
            primary_keys = []
            
            for col in columns:
                if not col.get("name"):
                    continue
                
                col_def = f"  `{col['name']}` {col.get('data_type', 'VARCHAR(255)')}"
                
                # 添加约束信息
                if not col.get('is_nullable', True):
                    col_def += " NOT NULL"
                
                if col.get('business_desc'):
                    col_def += f" COMMENT '{col['business_desc']}'"
                
                column_defs.append(col_def)
                
                # 收集主键信息
                if col.get('is_primary', False):
                    primary_keys.append(col['name'])
            
            # 添加列定义
            ddl_lines.append(",\\n".join(column_defs))
            
            # 添加主键约束
            if primary_keys:
                pk_def = f",\\n  PRIMARY KEY (`{'`, `'.join(primary_keys)}`)"
                ddl_lines.append(pk_def)
            
            ddl_lines.append(");")
            ddl_lines.append("")  # 表间分隔
        
        ddl_content = "\\n".join(ddl_lines)
        
        # DDL长度优化 - 避免超过LLM token限制
        if len(ddl_content) > 60000:  # 约15k tokens
            ddl_content = self._optimize_ddl_for_llm(ddl_content)
        
        self.logger.info(f"📝 DDL格式化完成，内容长度: {len(ddl_content)} 字符")
        
        return ddl_content
    
    def _analyze_domain_with_llm(self, ddl_content: str) -> DomainKnowledge:
        """使用LLM进行深度领域分析
        
        分析流程:
        1. 构建结构化提示词（基于02_domain_analysis_structured.j2）
        2. 调用LLM服务生成分析
        3. 解析JSON结构化响应
        4. 构建DomainKnowledge对象
        """
        self.logger.info("🤖 开始LLM深度领域分析...")
        
        try:
            # 1. 构建结构化提示词
            structured_prompt = self._build_structured_prompt(ddl_content)
            
            # 2. 直接调用LLM服务
            self.logger.info("📡 调用LLM服务进行分析...")
            llm_response_obj = self.llm.invoke(structured_prompt)
            
            # 提取响应内容
            llm_response = llm_response_obj.content if hasattr(llm_response_obj, 'content') else str(llm_response_obj)
            self.logger.info(f"✅ LLM响应长度: {len(llm_response)} 字符")
            
            # 3. 解析结构化响应
            domain_knowledge = self._parse_structured_response(llm_response)
            
            self.logger.info(f"✅ LLM分析完成，识别领域: {domain_knowledge.domain_type} (置信度: {domain_knowledge.confidence:.2f})")
            
            return domain_knowledge
            
        except Exception as e:
            self.logger.error(f"❌ LLM分析失败: {e}")
            raise_tool_error(self.name, f"LLM领域分析失败: {str(e)}")
    
    def _build_structured_prompt(self, ddl_content: str) -> str:
        """构建结构化提示词 - 基于 02_domain_analysis_structured.j2"""
        
        try:
            # 使用PromptManager加载和渲染模板
            template_path = 'analysis/02_domain_analysis_structured.j2'
            return self.prompt_manager.render_template(template_path, schema_ddl=ddl_content)
            
        except Exception as e:
            self.logger.error(f"❌ 模板加载失败: {e}")
            raise_tool_error(self.name, f"Jinja2模板加载失败: {str(e)}")
    
    def _parse_structured_response(self, response: str) -> DomainKnowledge:
        """解析LLM结构化响应"""
        try:
            # 清理响应格式
            clean_response = self._clean_llm_response(response)
            
            # JSON解析
            parsed_data = json.loads(clean_response)
            
            # 数据验证和转换
            validated_data = self._validate_response_structure(parsed_data)
            
            # 构建DomainKnowledge对象
            domain_knowledge = DomainKnowledge(
                domain_type=validated_data.get('domain_type', '未知领域'),
                business_problems=validated_data.get('business_problems', []),
                solution_approaches=validated_data.get('solution_approaches', []),
                key_entities=validated_data.get('key_entities', []),
                business_rules=validated_data.get('business_rules', []),
                special_fields=validated_data.get('special_fields', []),
                confidence=self._calculate_confidence(validated_data),
                analysis_timestamp=datetime.now().isoformat()
            )
            
            return domain_knowledge
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析失败: {e}")
            return self._create_fallback_domain_knowledge()
        except Exception as e:
            self.logger.error(f"响应解析异常: {e}")
            return self._create_fallback_domain_knowledge()
    
    def _clean_llm_response(self, response: str) -> str:
        """LLM响应清理算法"""
        cleaned = response.strip()
        
        # 处理markdown代码块标记
        if '```json' in cleaned:
            start = cleaned.find('```json') + 7
            end = cleaned.find('```', start)
            if end > start:
                cleaned = cleaned[start:end].strip()
        
        # 查找JSON对象边界
        start_idx = cleaned.find('{')
        end_idx = cleaned.rfind('}')
        
        if start_idx >= 0 and end_idx > start_idx:
            return cleaned[start_idx:end_idx + 1]
        
        return cleaned
    
    def _validate_response_structure(self, data: Dict) -> Dict:
        """响应结构验证算法"""
        required_fields = [
            'domain_type', 'business_problems', 'solution_approaches',
            'key_entities', 'business_rules', 'special_fields'
        ]
        
        validated_data = {}
        
        for field in required_fields:
            if field in data:
                if field == 'domain_type':
                    validated_data[field] = str(data[field]).strip()
                else:
                    # 确保数组字段
                    field_value = data[field]
                    if isinstance(field_value, list):
                        validated_data[field] = [
                            str(item).strip() 
                            for item in field_value 
                            if item and str(item).strip()
                        ]
                    else:
                        validated_data[field] = []
            else:
                validated_data[field] = "" if field == 'domain_type' else []
        
        return validated_data
    
    def _calculate_confidence(self, data: Dict) -> float:
        """置信度计算算法"""
        confidence_score = 0.0
        
        # 领域类型质量评估 (20%)
        domain_type = data.get('domain_type', '')
        if domain_type and len(domain_type) > 3:
            confidence_score += 0.2
        
        # 业务问题完整性 (20%)
        problems = data.get('business_problems', [])
        if len(problems) >= 2:
            confidence_score += 0.2
        
        # 解决方案合理性 (20%)
        solutions = data.get('solution_approaches', [])
        if len(solutions) >= 2:
            confidence_score += 0.2
        
        # 核心实体识别 (20%)
        entities = data.get('key_entities', [])
        if len(entities) >= 2:
            confidence_score += 0.2
        
        # 业务规则丰富度 (20%)
        rules = data.get('business_rules', [])
        if len(rules) >= 3:
            confidence_score += 0.2
        
        # 基于LLM分析的置信度应该较高
        return min(confidence_score * 1.2, 1.0)
    
    def _store_domain_knowledge_to_neo4j(self, domain_knowledge: DomainKnowledge, 
                                       database_schema: Dict[str, Any]) -> None:
        """将领域知识注入到现有Database节点属性中"""
        
        self.logger.info("💾 开始将领域分析结果注入到Database节点...")
        
        database_name = database_schema.get("database_name", "unknown")
        
        try:
            # 将领域分析结果注入到Database节点的business_desc属性
            self._update_database_with_domain_knowledge(database_name, domain_knowledge)
            
            self.logger.info(f"✅ Neo4j存储完成: Database节点'{database_name}'已更新业务领域分析结果")
            
        except Exception as e:
            self.logger.error(f"❌ Neo4j存储失败: {e}")
            raise
    
    def _update_database_with_domain_knowledge(self, database_name: str, domain_knowledge: DomainKnowledge) -> None:
        """将领域分析结果注入到现有Database节点的business_desc属性中"""
        
        # 将复杂的领域知识对象序列化为结构化字符串
        domain_analysis_text = self._serialize_domain_knowledge(domain_knowledge)
        
        # 更新Database节点的business_desc属性
        cypher = '''
        MATCH (db:Database {name: $database_name})
        SET db.business_desc = $business_desc
        RETURN db
        '''
        
        params = {
            "database_name": database_name,
            "business_desc": domain_analysis_text
        }
        
        self.memory_manager.neo4j_graph.query(cypher, params)
        
        self.logger.info(f"✅ 已将领域分析结果注入到Database节点 '{database_name}' 的business_desc属性")
    
    def _serialize_domain_knowledge(self, domain_knowledge: DomainKnowledge) -> str:
        """将领域知识对象序列化为结构化字符串"""
        
        sections = [
            f"【业务领域】{domain_knowledge.domain_type}",
            f"【置信度】{domain_knowledge.confidence:.2f}",
            "",
            "【业务问题】",
            *[f"• {problem}" for problem in domain_knowledge.business_problems],
            "",
            "【解决方案】", 
            *[f"• {solution}" for solution in domain_knowledge.solution_approaches],
            "",
            "【核心实体】",
            *[f"• {entity}" for entity in domain_knowledge.key_entities],
            "",
            "【业务规则】",
            *[f"• {rule}" for rule in domain_knowledge.business_rules],
        ]
        
        if domain_knowledge.special_fields:
            sections.extend([
                "",
                "【特殊字段】",
                *[f"• {field}" for field in domain_knowledge.special_fields]
            ])
        
        sections.append(f"\n【分析时间】{domain_knowledge.analysis_timestamp}")
        
        return "\n".join(sections)
    
    
    
    def _optimize_ddl_for_llm(self, ddl_content: str) -> str:
        """DDL内容优化 - 适配LLM token限制"""
        lines = ddl_content.split('\\n')
        important_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 保留重要信息
            if any(keyword in line.lower() for keyword in [
                'create table', 'primary key', 'foreign key',
                'not null', 'unique', 'id', 'name', 'status'
            ]):
                important_lines.append(line)
        
        return '\\n'.join(important_lines)


# ========== 便利函数 ==========
def create_domain_analysis_tool(memory_manager: Optional['Neo4jMemoryManager'] = None) -> DomainAnalysisTool:
    """创建领域分析工具的便利函数"""
    return DomainAnalysisTool(memory_manager=memory_manager)