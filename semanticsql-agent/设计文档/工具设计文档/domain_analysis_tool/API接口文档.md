# Domain Analysis Tool API 接口文档

## 概述

Domain Analysis Tool API 文档详细描述了基于 LLM 智能分析的业务领域分析工具的所有接口规范、数据流操作和技术实现细节。本工具采用直接 Neo4j 操作架构，结合 `nl2sql_pipeline` 的成熟算法，实现深度业务理解。

## 核心技术架构

### LLM 集成模式
- **提示词工程**：基于 `02_domain_analysis_structured.j2` 的结构化分析
- **六维分析法**：domain_type、business_problems、solution_approaches、key_entities、business_rules、special_fields
- **JSON 结构化输出**：确保分析结果的机器可读性和一致性

### Neo4j 直接操作
- **跳过三元组抽象**：直接创建业务知识图谱节点和关系
- **图结构设计**：Database → Domain → BusinessProblem/Entity/Rule 的层次化结构
- **持久化存储**：支持增量更新和历史追踪

## 主要接口规范

### 1. DomainAnalysisTool 类

```python
class DomainAnalysisTool(BaseSemanticSQLTool):
    """业务领域分析工具 - LLM增强版本
    
    核心职责：
    - 从Neo4j读取数据库结构信息（schema_extraction_tool的输出）
    - 使用LLM进行深度业务领域分析（整合pipeline算法）
    - 直接创建Neo4j业务知识图谱（Domain、BusinessProblem等节点）
    - 为后续工具提供结构化业务上下文
    """
```

#### 构造函数

```python
def __init__(self, **kwargs) -> None:
    """初始化领域分析工具
    
    参数:
        **kwargs: 继承自BaseSemanticSQLTool的参数
            - memory_manager: Neo4jMemoryManager实例
            - database_manager: DatabaseManager实例 (可选)
            - logger: 日志记录器实例 (可选)
    
    初始化内容:
        - 加载settings配置
        - 初始化LLM服务连接
        - 设置工具元数据
    """
```

#### 主要执行方法

```python
def _run(self, *args, **kwargs) -> str:
    """执行领域分析 - 基于LLM的智能分析流程
    
    执行步骤:
        1. 验证依赖：确保schema_extraction_tool已执行
        2. 从Neo4j读取数据库结构信息
        3. 格式化为LLM可理解的DDL格式
        4. 使用LLM进行深度领域分析
        5. 直接存储到Neo4j知识图谱
        6. 返回分析结果
    
    返回:
        str: 执行结果消息，包含领域识别结果和统计信息
    
    异常:
        DependencyError: 当schema_extraction_tool未执行时
        Neo4jError: 当Neo4j操作失败时
        LLMError: 当LLM服务调用失败时
    """
```

### 2. 核心业务方法

#### 依赖检查方法

```python
def _check_schema_extraction_dependency(self) -> None:
    """验证schema_extraction_tool依赖
    
    检查内容:
        - Neo4j中是否存在Database节点
        - 是否存在完整的Table和Column结构
        - 检查schema_extraction_tool的execution_status
    
    Cypher查询:
        MATCH (d:Database)-[:HAS_TABLE]->(t:Table)-[:HAS_COLUMN]->(c:Column)
        RETURN count(d) as db_count, count(t) as table_count, count(c) as column_count
    
    异常:
        DependencyError: 依赖检查失败时抛出
    """
```

#### Neo4j架构查询方法

```python
def _query_neo4j_schema(self) -> Dict[str, Any]:
    """从Neo4j查询数据库结构信息
    
    查询内容:
        - 数据库基本信息
        - 表结构和列信息
        - 主键、外键关系
        - 字段样本值和熵值等级
    
    Cypher查询:
        MATCH (d:Database {name: $database_name})
        OPTIONAL MATCH (d)-[:HAS_TABLE]->(t:Table)
        OPTIONAL MATCH (t)-[:HAS_COLUMN]->(c:Column)
        RETURN d, collect(DISTINCT t) as tables, collect(c) as columns
    
    返回:
        Dict[str, Any]: 包含数据库结构的字典
        {
            "database_name": str,
            "tables": List[Dict],
            "columns": List[Dict],
            "relationships": List[Dict]
        }
    """
```

#### DDL格式化方法

```python
def _format_schema_to_ddl(self, database_schema: Dict[str, Any]) -> str:
    """格式化数据库结构为DDL语句
    
    参数:
        database_schema: _query_neo4j_schema返回的结构信息
    
    格式化内容:
        - CREATE TABLE语句
        - 列定义（类型、约束、默认值）
        - PRIMARY KEY声明
        - FOREIGN KEY关系
    
    返回:
        str: 标准DDL格式字符串，供LLM分析使用
    
    示例输出:
        CREATE TABLE `users` (
          `id` INT NOT NULL AUTO_INCREMENT,
          `username` VARCHAR(50) NOT NULL,
          `email` VARCHAR(100) NOT NULL,
          `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (`id`),
          UNIQUE KEY `uk_username` (`username`)
        );
    """
```

#### LLM分析方法

```python
def _analyze_domain_with_llm(self, ddl_content: str) -> DomainKnowledge:
    """使用LLM进行深度领域分析
    
    参数:
        ddl_content: 格式化的DDL字符串
    
    分析流程:
        1. 构建结构化提示词（基于02_domain_analysis_structured.j2）
        2. 调用LLM服务生成分析
        3. 解析JSON结构化响应
        4. 构建DomainKnowledge对象
    
    LLM提示词结构:
        - 角色设定：跨行业首席数据架构师和业务专家
        - 分析要求：使用业务语言，基于Schema推理
        - 输出格式：严格JSON格式，六个维度分析
    
    返回:
        DomainKnowledge: 包含六维分析结果的数据模型
        
    异常:
        LLMError: LLM服务调用失败
        JSONDecodeError: 响应解析失败
    """
```

#### Neo4j存储方法

```python
def _store_domain_knowledge_to_neo4j(self, domain_knowledge: DomainKnowledge, 
                                   database_schema: Dict[str, Any]) -> None:
    """直接存储领域知识到Neo4j图谱
    
    参数:
        domain_knowledge: LLM分析结果
        database_schema: 原始数据库结构信息
    
    存储结构:
        - Domain节点：领域类型和基本信息
        - BusinessProblem节点：业务问题描述
        - SolutionApproach节点：解决方案方法
        - KeyEntity节点：核心业务实体
        - BusinessRule节点：业务规则
        - SpecialField节点：特殊字段规则
    
    关系创建:
        - (Database)-[:BELONGS_TO_DOMAIN]->(Domain)
        - (Domain)-[:HAS_PROBLEM]->(BusinessProblem)
        - (Domain)-[:HAS_SOLUTION]->(SolutionApproach)
        - (Domain)-[:CONTAINS_ENTITY]->(KeyEntity)
        - (Domain)-[:FOLLOWS_RULE]->(BusinessRule)
        - (Domain)-[:HAS_SPECIAL_FIELD]->(SpecialField)
    """
```

## 数据模型定义

### DomainKnowledge 数据类

```python
@dataclass
class DomainKnowledge:
    """领域知识数据模型 - 基于pipeline的结构化设计"""
    
    # 核心属性
    domain_type: str              # 精准的业务领域名称
    business_problems: List[str]  # 系统要解决的业务问题
    solution_approaches: List[str] # 解决问题的方式
    key_entities: List[str]       # 核心业务实体描述
    business_rules: List[str]     # 业务约束和关系规则
    special_fields: List[str]     # 特殊业务字段规则
    
    # 元数据
    confidence: float = 0.0       # 分析置信度
    analysis_timestamp: str = ""  # 分析时间戳
    
    # 方法
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
    
    def validate(self) -> bool:
        """验证数据完整性"""
```

## Neo4j 图结构设计

### 节点类型规范

#### Domain 节点
```cypher
CREATE (d:Domain {
    name: "电商订单管理",
    domain_type: "电商订单管理", 
    confidence: 0.95,
    analysis_timestamp: "2024-01-15T10:30:00",
    created_by: "domain_analysis_tool"
})
```

#### BusinessProblem 节点
```cypher
CREATE (bp:BusinessProblem {
    id: "bp_001",
    description: "需要管理客户订单的完整生命周期",
    domain_name: "电商订单管理",
    priority: "high",
    created_timestamp: "2024-01-15T10:30:00"
})
```

#### KeyEntity 节点
```cypher
CREATE (ke:KeyEntity {
    id: "ke_001", 
    description: "订单实体：记录客户购买行为",
    entity_type: "core_business_object",
    domain_name: "电商订单管理",
    business_importance: "critical",
    created_timestamp: "2024-01-15T10:30:00"
})
```

### 关系类型规范

#### 领域归属关系
```cypher
MATCH (db:Database {name: $database_name})
MATCH (d:Domain {name: $domain_name})
CREATE (db)-[:BELONGS_TO_DOMAIN {
    confidence: 0.95,
    analysis_method: "llm_structured_analysis",
    created_timestamp: "2024-01-15T10:30:00"
}]->(d)
```

#### 业务问题关系
```cypher
MATCH (d:Domain {name: $domain_name})
MATCH (bp:BusinessProblem {id: $problem_id})
CREATE (d)-[:HAS_PROBLEM {
    relevance_score: 0.9,
    created_timestamp: "2024-01-15T10:30:00"
}]->(bp)
```

## Cypher 查询接口

### 1. 查询数据库结构

```python
def get_database_schema_query(self, database_name: str) -> str:
    """获取数据库结构的Cypher查询
    
    参数:
        database_name: 数据库名称
        
    返回:
        str: Cypher查询语句
    """
    return """
    MATCH (d:Database {name: $database_name})
    OPTIONAL MATCH (d)-[:HAS_TABLE]->(t:Table)
    OPTIONAL MATCH (t)-[:HAS_COLUMN]->(c:Column)
    OPTIONAL MATCH (t)-[:HAS_FOREIGN_KEY]->(fk:ForeignKey)
    RETURN d.name as database_name,
           collect(DISTINCT {
               name: t.name,
               comment: t.comment,
               row_count: t.row_count
           }) as tables,
           collect(DISTINCT {
               table_name: c.table_name,
               name: c.name, 
               data_type: c.data_type,
               is_nullable: c.is_nullable,
               is_primary: c.is_primary_key,
               default_value: c.default_value,
               sample_values: c.sample_values,
               entropy_level: c.entropy_level
           }) as columns
    """
```

### 2. 创建领域节点

```python
def create_domain_node_query(self) -> str:
    """创建Domain节点的Cypher查询"""
    return """
    MERGE (d:Domain {name: $domain_name})
    SET d.domain_type = $domain_type,
        d.confidence = $confidence,
        d.analysis_timestamp = $timestamp,
        d.created_by = 'domain_analysis_tool'
    RETURN d
    """
```

### 3. 批量创建业务知识节点

```python
def create_business_knowledge_batch_query(self) -> str:
    """批量创建业务知识节点的Cypher查询"""
    return """
    UNWIND $business_problems as problem
    MERGE (bp:BusinessProblem {id: problem.id})
    SET bp.description = problem.description,
        bp.domain_name = $domain_name,
        bp.priority = problem.priority,
        bp.created_timestamp = $timestamp
    
    WITH collect(bp) as problems
    UNWIND $key_entities as entity  
    MERGE (ke:KeyEntity {id: entity.id})
    SET ke.description = entity.description,
        ke.entity_type = entity.type,
        ke.domain_name = $domain_name,
        ke.business_importance = entity.importance,
        ke.created_timestamp = $timestamp
        
    WITH problems, collect(ke) as entities
    UNWIND $business_rules as rule
    MERGE (br:BusinessRule {id: rule.id})
    SET br.description = rule.description,
        br.rule_type = rule.type,
        br.domain_name = $domain_name,
        br.created_timestamp = $timestamp
        
    RETURN count(problems) as problems_created,
           count(entities) as entities_created,
           count(collect(br)) as rules_created
    """
```

### 4. 查询领域分析结果

```python
def query_domain_analysis_results(self) -> str:
    """查询领域分析结果的Cypher查询"""
    return """
    MATCH (db:Database {name: $database_name})-[:BELONGS_TO_DOMAIN]->(d:Domain)
    OPTIONAL MATCH (d)-[:HAS_PROBLEM]->(bp:BusinessProblem)
    OPTIONAL MATCH (d)-[:HAS_SOLUTION]->(sa:SolutionApproach)  
    OPTIONAL MATCH (d)-[:CONTAINS_ENTITY]->(ke:KeyEntity)
    OPTIONAL MATCH (d)-[:FOLLOWS_RULE]->(br:BusinessRule)
    OPTIONAL MATCH (d)-[:HAS_SPECIAL_FIELD]->(sf:SpecialField)
    
    RETURN d.domain_type as domain_type,
           d.confidence as confidence,
           d.analysis_timestamp as timestamp,
           collect(DISTINCT bp.description) as business_problems,
           collect(DISTINCT sa.description) as solution_approaches,
           collect(DISTINCT ke.description) as key_entities,
           collect(DISTINCT br.description) as business_rules,
           collect(DISTINCT sf.description) as special_fields
    """
```

## LLM 服务集成

### LLM 提示词接口

```python
def build_domain_analysis_prompt(self, ddl_content: str) -> str:
    """构建领域分析提示词
    
    参数:
        ddl_content: 格式化的DDL字符串
        
    返回:
        str: 结构化提示词
        
    基于模板: 02_domain_analysis_structured.j2
    """
    template = self.jinja_env.get_template('analysis/02_domain_analysis_structured.j2')
    return template.render(schema_ddl=ddl_content)
```

### LLM 响应解析

```python
def parse_llm_response(self, response: str) -> DomainKnowledge:
    """解析LLM结构化响应
    
    参数:
        response: LLM返回的JSON字符串
        
    返回:
        DomainKnowledge: 解析后的领域知识对象
        
    解析步骤:
        1. 清理响应格式（移除```json标记）
        2. JSON解析
        3. 数据验证和转换
        4. 构建DomainKnowledge对象
        
    异常处理:
        - JSON格式错误：返回默认DomainKnowledge
        - 字段缺失：使用默认值填充
        - 数据类型错误：进行类型转换
    """
```

## 错误处理和异常

### 异常类型定义

```python
class DomainAnalysisError(Exception):
    """领域分析基础异常"""
    pass

class LLMAnalysisError(DomainAnalysisError):
    """LLM分析失败异常"""
    pass

class Neo4jStorageError(DomainAnalysisError):
    """Neo4j存储失败异常"""  
    pass

class DependencyError(DomainAnalysisError):
    """依赖检查失败异常"""
    pass
```

### 错误处理策略

```python
def handle_llm_failure(self, error: Exception) -> DomainKnowledge:
    """LLM失败降级处理
    
    降级策略:
        1. 使用关键词匹配进行基础分析
        2. 基于表名和字段名推断业务类型
        3. 返回低置信度的分析结果
        
    参数:
        error: LLM调用异常
        
    返回:
        DomainKnowledge: 降级分析结果（置信度 < 0.5）
    """
```

## 性能监控接口

### 执行统计

```python
def get_execution_stats(self) -> Dict[str, Any]:
    """获取执行统计信息
    
    返回:
        Dict[str, Any]: 包含以下统计信息
        {
            "total_tables_analyzed": int,
            "llm_call_duration": float,
            "neo4j_write_duration": float, 
            "analysis_confidence": float,
            "nodes_created": int,
            "relationships_created": int
        }
    """
```

### 缓存管理

```python
def cache_analysis_result(self, database_name: str, result: DomainKnowledge) -> None:
    """缓存分析结果
    
    参数:
        database_name: 数据库名称
        result: 分析结果
        
    缓存策略:
        - Redis缓存，TTL=24小时
        - 键格式：domain_analysis:{database_name}:{schema_hash}
    """

def get_cached_result(self, database_name: str) -> Optional[DomainKnowledge]:
    """获取缓存的分析结果
    
    参数:
        database_name: 数据库名称
        
    返回:
        Optional[DomainKnowledge]: 缓存的结果，不存在则返回None
    """
```

## 配置管理

### 工具配置接口

```python
class DomainAnalysisConfig:
    """领域分析配置管理"""
    
    # LLM配置
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 4000
    LLM_TIMEOUT: int = 120
    
    # 分析配置  
    MIN_CONFIDENCE_THRESHOLD: float = 0.6
    MAX_RETRY_ATTEMPTS: int = 3
    ENABLE_CACHE: bool = True
    
    # Neo4j配置
    BATCH_SIZE: int = 50
    CONNECTION_TIMEOUT: int = 30
    
    @classmethod
    def load_from_settings(cls) -> 'DomainAnalysisConfig':
        """从配置文件加载设置"""
```

## 集成测试接口

### 单元测试支持

```python
def create_test_instance(self, mock_llm: bool = True, 
                        mock_neo4j: bool = False) -> DomainAnalysisTool:
    """创建测试实例
    
    参数:
        mock_llm: 是否模拟LLM服务
        mock_neo4j: 是否模拟Neo4j服务
        
    返回:
        DomainAnalysisTool: 配置好的测试实例
    """

def validate_analysis_result(self, result: DomainKnowledge) -> List[str]:
    """验证分析结果质量
    
    参数:
        result: 分析结果
        
    返回:
        List[str]: 验证失败的错误信息列表，空列表表示通过验证
    """
```

## 版本兼容性

### API 版本管理

```python
class DomainAnalysisAPIVersion:
    """API版本管理"""
    
    CURRENT_VERSION = "2.0.0"
    SUPPORTED_VERSIONS = ["1.0.0", "2.0.0"]
    
    @staticmethod
    def is_compatible(version: str) -> bool:
        """检查版本兼容性"""
        
    @staticmethod  
    def migrate_from_v1(old_result: Dict) -> DomainKnowledge:
        """从v1.0格式迁移到v2.0"""
```

---

## 总结

Domain Analysis Tool API 设计采用现代化的 LLM + 图数据库架构，通过结构化的六维分析法和直接的 Neo4j 操作，实现了高效、准确的业务领域理解。API 设计注重：

1. **类型安全**：完整的类型注解和数据验证
2. **错误处理**：多层次的异常处理和降级策略  
3. **性能优化**：缓存机制和批量操作支持
4. **可测试性**：完善的测试接口和模拟支持
5. **扩展性**：灵活的配置管理和版本兼容性

该 API 设计为后续的代码实现提供了清晰的技术规范和实现指南。