"""
业务领域分析工具 - 基于LLM的智能分析版本

整合pipeline算法，采用直接Neo4j操作架构，实现深度业务理解。
基于 nl2sql_pipeline 的 domain_optimization_pipeline.py 设计思路，
使用 02_domain_analysis_structured.j2 提示词模板进行六维业务分析。

核心特性：
- 从Neo4j读取schema_extraction_tool的输出
- 使用LLM进行六维业务分析(domain_type, business_problems, solution_approaches, key_entities, business_rules, special_fields)
- 直接创建Neo4j业务知识图谱节点
- 支持优雅降级和错误处理
"""

from typing import Dict, Any, List, Optional
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from jinja2 import Environment, BaseLoader
from pydantic import Field

from tools.base_tool import BaseSemanticSQLTool
from models.exceptions import raise_tool_error, raise_dependency_error
from config.settings import get_settings
from utils.memory import Neo4jMemoryManager

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
    - 智能降级处理和错误恢复
    - 支持缓存和性能优化
    """
    
    name: str = "domain_analysis_tool"  
    description: str = "基于LLM的智能业务领域分析，识别业务问题、解决方案和核心实体"
    memory_manager: Optional[Neo4jMemoryManager] = Field(default=None, exclude=True)
    
    def __init__(self, memory_manager: Optional[Neo4jMemoryManager] = None, **kwargs):
        """初始化领域分析工具"""
        super().__init__(**kwargs)
        self.settings = get_settings()
    
    def _run(self, *args, **kwargs) -> str:
        """执行领域分析 - 基于LLM的智能分析流程"""
        self.logger.info(f"🔧 {self.name}: 开始执行 - 基于LLM的领域分析")
        
        try:
            # 1. 验证依赖：确保schema_extraction_tool已执行
            self._check_schema_extraction_dependency()
            from config.factories import ComponentManager
            
            # LLM是必需的
            self.llm = ComponentManager.create_llm(self.settings)
            self.memory_manager = ComponentManager.create_memory_manager(self.settings)
               
            # 2. 从Neo4j读取数据库结构信息
            database_schema = self._query_neo4j_schema()
            if not database_schema.get("tables"):
                raise_dependency_error(self.name, "schema_extraction_tool", "未找到数据库表结构信息")
            
            # 3. 格式化为LLM可理解的DDL格式
            ddl_content = self._format_schema_to_ddl(database_schema)
            
            # 4. 使用LLM进行深度领域分析
            domain_knowledge = self.llm(ddl_content)
            
            # 5. 直接存储到Neo4j知识图谱
            self._store_domain_knowledge_to_neo4j(domain_knowledge, database_schema)
            
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
        cypher = '''
        MATCH (d:Database)-[:HAS_TABLE]->(t:Table)-[:HAS_COLUMN]->(c:Column)
        RETURN count(DISTINCT d) as db_count, 
               count(DISTINCT t) as table_count, 
               count(DISTINCT c) as column_count
        '''
        
        result = self.memory_manager.query(cypher)
        if not result or result[0]["db_count"] == 0:
            raise_dependency_error(
                self.name, 
                "schema_extraction_tool", 
                "Neo4j中未找到Database和Table结构，请先执行schema_extraction_tool"
            )
        
        self.logger.info(f"✅ 依赖检查通过: 发现 {result[0]['table_count']} 个表，{result[0]['column_count']} 个字段")
    
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
        OPTIONAL MATCH (d)-[:HAS_TABLE]->(t:Table)
        OPTIONAL MATCH (t)-[:HAS_COLUMN]->(c:Column)
        RETURN d.name as database_name,
               collect(DISTINCT {
                   name: t.name,
                   comment: t.comment,
                   row_count: t.row_count,
                   columns: [(t)-[:HAS_COLUMN]->(col:Column) | {
                       name: col.name,
                       data_type: col.data_type,
                       is_nullable: col.is_nullable,
                       is_primary_key: col.is_primary_key,
                       default_value: col.default_value,
                       comment: col.comment,
                       sample_values: col.sample_values,
                       entropy_level: col.entropy_level
                   }]
               }) as tables
        '''
        
        result = self.memory_manager.query(cypher)
        if not result:
            raise_dependency_error(self.name, "schema_extraction_tool", "Neo4j查询返回空结果")
        
        schema_data = result[0]
        # 过滤掉空的表记录
        schema_data["tables"] = [table for table in schema_data["tables"] if table["name"]]
        
        self.logger.info(f"📊 从Neo4j读取到 {len(schema_data['tables'])} 个表的结构信息")
        
        return schema_data
    
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
                
                if col.get('default_value'):
                    col_def += f" DEFAULT {col['default_value']}"
                
                if col.get('comment'):
                    col_def += f" COMMENT '{col['comment']}'"
                
                column_defs.append(col_def)
                
                # 收集主键信息
                if col.get('is_primary_key', False):
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
            
            # 2. 调用LLM服务
            llm_response = self._call_llm_service(structured_prompt)
            
            # 3. 解析结构化响应
            domain_knowledge = self._parse_structured_response(llm_response)
            
            self.logger.info(f"✅ LLM分析完成，识别领域: {domain_knowledge.domain_type} (置信度: {domain_knowledge.confidence:.2f})")
            
            return domain_knowledge
            
        except Exception as e:
            self.logger.warning(f"⚠️ LLM分析失败，启动降级处理: {e}")
            return self._fallback_analysis(ddl_content)
    
    def _build_structured_prompt(self, ddl_content: str) -> str:
        """构建结构化提示词 - 基于 02_domain_analysis_structured.j2"""
        
        template_content = '''您现担任跨行业首席数据架构师和业务专家。请依据所提供之数据库 Schema，分析该数据库的业务领域，并严格按照以下JSON格式输出分析结果。

分析要求：
1. 使用业务语言而非技术术语（避免使用"表"、"字段"、"外键"等技术词汇）
2. 基于 Schema 信息进行合理推理，不要臆测没有依据的内容
3. 所有描述都必须是完整的句子，不能是简单的名词或短语
4. 严格遵循下面的JSON格式，不要输出任何JSON之外的内容

请直接输出以下格式的JSON：

{
  "domain_type": "精准的业务领域名称（如：电商订单管理、国防工业合同管理等）",
  
  "business_problems": [
    "系统旨在解决的第一个业务问题的完整描述",
    "系统旨在解决的第二个业务问题的完整描述",
    "系统旨在解决的第三个业务问题的完整描述"
  ],
  
  "solution_approaches": [
    "解决上述问题的第一种方式的完整描述",
    "解决上述问题的第二种方式的完整描述",
    "解决上述问题的第三种方式的完整描述"
  ],
  
  "key_entities": [
    "第一个核心业务实体的完整描述：它是什么，代表什么业务对象，在业务流程中扮演什么角色",
    "第二个核心业务实体的完整描述：它如何支撑业务运转，承载哪些业务信息，如何与其他实体协作",
    "第三个核心业务实体的完整描述：它与其他概念的关联，生命周期如何，对业务有什么影响"
  ],
  
  "business_rules": [
    "若第一个条件发生，则系统必须执行的动作，以及这样做的业务目的",
    "当第二个状态变化时，系统自动触发的行为，以及对业务的影响",
    "必须满足的第三个约束条件，才能执行的操作，以及这个约束的业务意义",
    "第一对实体之间的关系规则：实体间存在什么样的业务关联，这种关联如何支撑业务流程",
    "第二对实体之间的关系规则：这种关系在业务中的意义，以及它如何影响业务决策"
  ],
  
  "special_fields": [
    "特殊业务字段及其规则：字段名称代表的业务含义，以及基于该字段的业务规则",
    "如果没有明确的特殊字段规则，此数组可以为空"
  ]
}

重要提示：
- 每个数组中的元素都必须是完整的描述性句子
- business_rules 包含业务约束和实体关系规则，使用条件句式（若...则...、当...时...、必须...才能...）
- key_entities 整合了原有的业务概念和实体描述，避免重复
- 不要输出JSON之外的任何解释或说明文字
- 如果某些信息无法从Schema中推断，相应字段可以包含较少的条目，但不要臆造

Schema 如下：
{{ schema_ddl }}'''
        
        template = self.jinja_env.from_string(template_content)
        return template.render(schema_ddl=ddl_content)
    
    def _call_llm_service(self, prompt: str) -> str:
        """调用LLM服务"""
        # 这里需要根据实际的LLM服务接口实现
        # 目前返回模拟响应，实际实现时需要集成真实的LLM服务
        
        self.logger.info("📡 调用LLM服务进行分析...")
        
        # TODO: 实际实现LLM服务调用
        # 示例代码结构：
        # from services.llm_service import LLMService
        # llm_service = LLMService(self.settings)
        # response = llm_service.generate(
        #     prompt=prompt,
        #     temperature=self.LLM_CONFIG["temperature"],
        #     max_tokens=self.LLM_CONFIG["max_tokens"],
        #     timeout=self.LLM_CONFIG["timeout"]
        # )
        # return response
        
        # 临时模拟响应
        mock_response = '''{
  "domain_type": "业务管理系统",
  "business_problems": [
    "需要管理和跟踪各种业务实体的生命周期和状态变化",
    "需要建立不同业务对象之间的关联关系以支撑复杂的业务流程",
    "需要确保数据的完整性和业务规则的一致性执行"
  ],
  "solution_approaches": [
    "通过标准化的数据模型来统一管理各类业务实体",
    "建立完善的状态管理机制来跟踪业务流程的执行进度",
    "实施严格的数据验证和业务规则引擎来保障系统稳定性"
  ],
  "key_entities": [
    "核心业务实体：代表系统中的主要业务对象，承载核心业务信息和状态",
    "关联实体：负责建立不同业务对象间的关系，支撑复杂的业务逻辑",
    "配置实体：管理系统的配置信息和业务参数，确保系统的灵活性"
  ],
  "business_rules": [
    "当业务实体状态发生变更时，系统必须记录变更日志以确保审计追踪",
    "若删除核心业务实体，则系统必须检查关联关系以防止数据孤岛",
    "业务实体与关联实体之间存在依赖关系：关联关系的建立必须基于有效的业务实体"
  ],
  "special_fields": [
    "状态字段代表业务实体的当前状态，遵循预定义的状态流转规则"
  ]
}'''
        
        return mock_response
    
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
        """直接存储领域知识到Neo4j图谱"""
        
        self.logger.info("💾 开始存储业务知识到Neo4j图谱...")
        
        database_name = database_schema.get("database_name", "unknown")
        domain_name = domain_knowledge.domain_type
        timestamp = domain_knowledge.analysis_timestamp
        
        try:
            # 1. 创建Domain节点
            self._create_domain_node(database_name, domain_knowledge)
            
            # 2. 批量创建业务知识节点
            nodes_created = self._create_business_knowledge_nodes(domain_knowledge)
            
            # 3. 建立关系网络
            relationships_created = self._create_business_relationships(database_name, domain_knowledge)
            
            self.logger.info(f"✅ Neo4j存储完成: 创建 {nodes_created} 个节点，{relationships_created} 个关系")
            
        except Exception as e:
            self.logger.error(f"❌ Neo4j存储失败: {e}")
            raise
    
    def _create_domain_node(self, database_name: str, domain_knowledge: DomainKnowledge) -> None:
        """创建Domain节点"""
        cypher = '''
        MERGE (d:Domain {name: $domain_name})
        SET d.domain_type = $domain_type,
            d.confidence = $confidence,
            d.analysis_timestamp = $timestamp,
            d.created_by = 'domain_analysis_tool'
        RETURN d
        '''
        
        params = {
            "domain_name": domain_knowledge.domain_type,
            "domain_type": domain_knowledge.domain_type,
            "confidence": domain_knowledge.confidence,
            "timestamp": domain_knowledge.analysis_timestamp
        }
        
        self.memory_manager.execute(cypher, params)
        
        # 建立Database到Domain的关系
        relationship_cypher = '''
        MATCH (db:Database {name: $database_name})
        MATCH (d:Domain {name: $domain_name})
        MERGE (db)-[:BELONGS_TO_DOMAIN {
            confidence: $confidence,
            analysis_method: 'llm_structured_analysis',
            created_timestamp: $timestamp
        }]->(d)
        '''
        
        rel_params = {
            "database_name": database_name,
            "domain_name": domain_knowledge.domain_type,
            "confidence": domain_knowledge.confidence,
            "timestamp": domain_knowledge.analysis_timestamp
        }
        
        self.memory_manager.execute(relationship_cypher, rel_params)
    
    def _create_business_knowledge_nodes(self, domain_knowledge: DomainKnowledge) -> int:
        """批量创建业务知识节点"""
        
        nodes_created = 0
        
        # 创建BusinessProblem节点
        for i, problem in enumerate(domain_knowledge.business_problems):
            cypher = '''
            MERGE (bp:BusinessProblem {id: $problem_id})
            SET bp.description = $description,
                bp.domain_name = $domain_name,
                bp.priority = $priority,
                bp.created_timestamp = $timestamp
            RETURN bp
            '''
            
            params = {
                "problem_id": f"bp_{i+1}",
                "description": problem,
                "domain_name": domain_knowledge.domain_type,
                "priority": "high" if i == 0 else "medium",
                "timestamp": domain_knowledge.analysis_timestamp
            }
            
            self.memory_manager.execute(cypher, params)
            nodes_created += 1
        
        # 创建KeyEntity节点
        for i, entity in enumerate(domain_knowledge.key_entities):
            cypher = '''
            MERGE (ke:KeyEntity {id: $entity_id})
            SET ke.description = $description,
                ke.entity_type = $entity_type,
                ke.domain_name = $domain_name,
                ke.business_importance = $importance,
                ke.created_timestamp = $timestamp
            RETURN ke
            '''
            
            params = {
                "entity_id": f"ke_{i+1}",
                "description": entity,
                "entity_type": "core_business_object",
                "domain_name": domain_knowledge.domain_type,
                "importance": "critical" if i < 2 else "important",
                "timestamp": domain_knowledge.analysis_timestamp
            }
            
            self.memory_manager.execute(cypher, params)
            nodes_created += 1
        
        # 创建BusinessRule节点
        for i, rule in enumerate(domain_knowledge.business_rules):
            cypher = '''
            MERGE (br:BusinessRule {id: $rule_id})
            SET br.description = $description,
                br.rule_type = $rule_type,
                br.domain_name = $domain_name,
                br.created_timestamp = $timestamp
            RETURN br
            '''
            
            params = {
                "rule_id": f"br_{i+1}",
                "description": rule,
                "rule_type": "business_constraint" if "必须" in rule else "business_process",
                "domain_name": domain_knowledge.domain_type,
                "timestamp": domain_knowledge.analysis_timestamp
            }
            
            self.memory_manager.execute(cypher, params)
            nodes_created += 1
        
        return nodes_created
    
    def _create_business_relationships(self, database_name: str, domain_knowledge: DomainKnowledge) -> int:
        """创建业务关系网络"""
        
        relationships_created = 0
        domain_name = domain_knowledge.domain_type
        
        # Domain与BusinessProblem的关系
        for i in range(len(domain_knowledge.business_problems)):
            cypher = '''
            MATCH (d:Domain {name: $domain_name})
            MATCH (bp:BusinessProblem {id: $problem_id})
            MERGE (d)-[:HAS_PROBLEM {
                relevance_score: $relevance,
                created_timestamp: $timestamp
            }]->(bp)
            '''
            
            params = {
                "domain_name": domain_name,
                "problem_id": f"bp_{i+1}",
                "relevance": 0.9 if i == 0 else 0.7,
                "timestamp": domain_knowledge.analysis_timestamp
            }
            
            self.memory_manager.execute(cypher, params)
            relationships_created += 1
        
        # Domain与KeyEntity的关系
        for i in range(len(domain_knowledge.key_entities)):
            cypher = '''
            MATCH (d:Domain {name: $domain_name})
            MATCH (ke:KeyEntity {id: $entity_id})
            MERGE (d)-[:CONTAINS_ENTITY {
                importance_score: $importance,
                created_timestamp: $timestamp
            }]->(ke)
            '''
            
            params = {
                "domain_name": domain_name,
                "entity_id": f"ke_{i+1}",
                "importance": 0.9 if i < 2 else 0.7,
                "timestamp": domain_knowledge.analysis_timestamp
            }
            
            self.memory_manager.execute(cypher, params)
            relationships_created += 1
        
        # Domain与BusinessRule的关系
        for i in range(len(domain_knowledge.business_rules)):
            cypher = '''
            MATCH (d:Domain {name: $domain_name})
            MATCH (br:BusinessRule {id: $rule_id})
            MERGE (d)-[:FOLLOWS_RULE {
                compliance_level: $compliance,
                created_timestamp: $timestamp
            }]->(br)
            '''
            
            params = {
                "domain_name": domain_name,
                "rule_id": f"br_{i+1}",
                "compliance": 0.8,
                "timestamp": domain_knowledge.analysis_timestamp
            }
            
            self.memory_manager.execute(cypher, params)
            relationships_created += 1
        
        return relationships_created
    
    def _build_analysis_result(self, domain_knowledge: DomainKnowledge) -> str:
        """构建执行结果消息"""
        
        confidence = domain_knowledge.confidence
        problems_count = len(domain_knowledge.business_problems)
        entities_count = len(domain_knowledge.key_entities)
        rules_count = len(domain_knowledge.business_rules)
        
        # 构建简洁的实体描述
        entity_preview = ""
        if domain_knowledge.key_entities:
            first_entity = domain_knowledge.key_entities[0]
            # 提取实体描述的核心部分
            entity_core = first_entity.split("：")[0] if "：" in first_entity else first_entity[:20]
            entity_preview = f"{entity_core}等{entities_count}个核心实体"
        
        # 构建业务问题预览
        problem_preview = ""
        if domain_knowledge.business_problems:
            first_problem = domain_knowledge.business_problems[0][:30] + "..." if len(domain_knowledge.business_problems[0]) > 30 else domain_knowledge.business_problems[0]
            problem_preview = first_problem
        
        result = f"""✅ 业务领域分析完成

🎯 领域识别结果:
  • 主要领域: {domain_knowledge.domain_type} (置信度: {confidence:.2f})
  • 核心业务问题: {problem_preview}
  • 关键业务实体: {entity_preview}
  • 业务规则: {rules_count}项规则

📊 分析统计:
  • 业务问题识别: {problems_count}个
  • 解决方案设计: {len(domain_knowledge.solution_approaches)}个
  • 业务规则提取: {rules_count}个
  • 特殊字段规则: {len(domain_knowledge.special_fields)}个

💾 业务知识图谱已构建完成，包含Domain、BusinessProblem、KeyEntity、BusinessRule等节点

⚡ 建议执行: field_analysis_tool - 进行字段语义分析"""
        
        return result
    
    # ========== 降级处理 ==========
    
    def _fallback_analysis(self, ddl_content: str) -> DomainKnowledge:
        """智能降级分析算法"""
        self.logger.info("🔄 启动降级分析模式")
        
        # 基于关键词的领域识别
        domain_type = self._rule_based_domain_detection(ddl_content)
        
        # 基于表名的业务问题推断
        business_problems = self._infer_business_problems(ddl_content)
        
        # 基于字段模式的实体识别
        key_entities = self._extract_entities_from_schema(ddl_content)
        
        # 基于约束的业务规则推断
        business_rules = self._infer_business_rules(ddl_content)
        
        fallback_knowledge = DomainKnowledge(
            domain_type=domain_type,
            business_problems=business_problems,
            solution_approaches=[
                f"通过{domain_type}系统管理相关业务流程",
                f"建立标准化的{domain_type}操作规范"
            ],
            key_entities=key_entities,
            business_rules=business_rules,
            special_fields=[],
            confidence=0.4,  # 降级分析的置信度较低
            analysis_timestamp=datetime.now().isoformat()
        )
        
        self.logger.info("✅ 降级分析完成")
        return fallback_knowledge
    
    def _rule_based_domain_detection(self, ddl_content: str) -> str:
        """基于规则的领域检测"""
        domain_keywords = {
            "电商系统": ["order", "product", "customer", "cart", "payment"],
            "用户管理系统": ["user", "account", "profile", "auth", "permission"],
            "内容管理系统": ["article", "post", "content", "media", "category"],
            "财务管理系统": ["transaction", "account", "invoice", "payment", "balance"],
            "库存管理系统": ["inventory", "stock", "warehouse", "supplier", "goods"]
        }
        
        content_lower = ddl_content.lower()
        domain_scores = {}
        
        for domain, keywords in domain_keywords.items():
            score = sum(1 for keyword in keywords if keyword in content_lower)
            if score > 0:
                domain_scores[domain] = score
        
        if domain_scores:
            return max(domain_scores, key=domain_scores.get)
        
        return "通用业务系统"
    
    def _infer_business_problems(self, ddl_content: str) -> List[str]:
        """推断业务问题"""
        return [
            "需要管理和维护系统中的核心业务数据",
            "需要确保业务流程的规范化和标准化执行"
        ]
    
    def _extract_entities_from_schema(self, ddl_content: str) -> List[str]:
        """从Schema提取实体"""
        entities = []
        # 简单提取CREATE TABLE后的表名作为实体
        import re
        table_matches = re.findall(r'CREATE TABLE `([^`]+)`', ddl_content)
        
        for table_name in table_matches[:3]:  # 最多3个
            entities.append(f"{table_name}实体：代表系统中的{table_name}业务对象")
        
        return entities
    
    def _infer_business_rules(self, ddl_content: str) -> List[str]:
        """推断业务规则"""
        rules = []
        
        if "NOT NULL" in ddl_content:
            rules.append("当创建业务记录时，系统必须确保关键字段不能为空")
        
        if "PRIMARY KEY" in ddl_content:
            rules.append("每个业务实体必须具有唯一标识符以确保数据完整性")
        
        return rules
    
    def _create_fallback_domain_knowledge(self) -> DomainKnowledge:
        """创建降级的领域知识"""
        return DomainKnowledge(
            domain_type="通用业务系统",
            business_problems=["需要管理业务数据和流程"],
            solution_approaches=["通过系统化方法管理业务"],
            key_entities=["业务实体：系统中的核心业务对象"],
            business_rules=["业务数据必须满足完整性约束"],
            special_fields=[],
            confidence=0.3,
            analysis_timestamp=datetime.now().isoformat()
        )
    
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