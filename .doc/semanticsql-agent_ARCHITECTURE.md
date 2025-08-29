# SemanticSQL Agent 架构文档

## 1. 系统架构概览

### 1.1 架构原则
- **分析驱动**：以深度数据库分析为核心
- **工具协同**：多个专业工具协同完成复杂任务
- **数据质量**：生成高质量的NL2SQL训练数据
- **可扩展性**：支持新领域和新数据库类型

### 1.2 技术栈
- **编程语言**: Python 3.8+
- **核心框架**:
  - Click: CLI 命令行框架
  - SQLAlchemy: 数据库元数据提取
  - OpenAI SDK: LLM 调用（支持 Qwen）
  - PyYAML: 配置文件解析
- **LLM支持**:
  - Qwen 系列模型（通过 OpenAI 兼容 API）
  - Function Calling 支持

## 2. 分层架构详解

### 2.1 表示层 (CLI Layer)

#### 核心命令
```python
@cli.command()
@click.option('--save-result', '-s', help='保存分析结果的文件路径')
@click.option('--stage-by-stage', is_flag=True, help='分阶段显示执行进度')
def smart_analyze(request, config, save_result, verbose, stage_by_stage):
    """智能分析数据库 - 自动执行完整6步流程"""
    # 1. 连接数据库
    # 2. 分析数据库领域
    # 3. 字段分类分析
    # 4. 表结构分析
    # 5. ER关系分析
    # 6. 场景问题生成
```

### 2.2 业务逻辑层 (Agent Layer)

#### SmartSQLAgent 架构
```python
class SmartSQLAgent(BaseAgent):
    """数据生成专用智能体"""
    
    def get_system_prompt(self) -> str:
        """构建分析任务的系统提示词"""
        return """你是一个专业的数据库分析专家..."""
    
    def smart_analyze(self, user_request: str) -> Dict[str, Any]:
        """执行完整的6步分析流程"""
        execution = self.new_task(user_request)
        return self._format_analysis_result(execution)
    
    def _generate_final_result(self) -> Dict[str, Any]:
        """整合所有分析步骤的结果"""
        # 收集各步骤的分析结果
        # 生成最终的场景和SQL
```

#### ReAct 执行引擎
```python
class BaseAgent:
    """ReAct 模式基础实现"""
    
    def _execute_react_loop(self, task: str) -> Any:
        """执行 ReAct 循环"""
        for step in range(self.max_steps):
            # 1. 生成思考和行动
            response = self._generate_next_action()
            
            # 2. 解析 LLM 响应
            thought, action, action_input = self._parse_response(response)
            
            # 3. 执行工具调用
            if action in self.available_tools:
                result = self._execute_action(action, action_input)
                
            # 4. 观察结果并继续
```

### 2.3 工具层 (Tools Layer)

#### 工具体系结构
```
tools/
├── trae_base_tool.py      # 工具基类
├── sql_tools.py           # SQL相关工具
│   ├── SchemaExtractionTool    # 模式提取
│   ├── SQLGenerationTool       # SQL生成
│   └── SQLExecutionTool        # SQL执行
└── analysis_tools.py      # 分析工具
    ├── DomainAnalysisTool      # 领域分析
    ├── FieldClassificationTool  # 字段分类
    ├── ERAnalysisTool          # 关系分析
    └── SequentialThinkingTool  # 思考辅助
```

#### 工具协同机制
```python
# 工具之间通过上下文共享信息
class AnalysisContext:
    """分析上下文，在工具间共享"""
    database_info: Dict         # 数据库基本信息
    domain_result: Dict        # 领域分析结果
    field_classification: Dict  # 字段分类结果
    table_analysis: Dict       # 表分析结果
    er_relationships: Dict     # ER关系
```

### 2.4 基础设施层

#### 配置管理
```python
@dataclass
class TraeConfig:
    """统一配置管理"""
    app: AppConfig
    database: DatabaseConfig
    llm: LLMConfig
    agent: AgentConfig
    
    @classmethod
    def load_config(cls, config_path: str) -> 'TraeConfig':
        """加载并验证配置"""
        # 支持 YAML 文件
        # 支持环境变量覆盖
        # 验证配置完整性
```

#### 数据库连接管理
```python
class DatabaseManager:
    """数据库连接和元数据管理"""
    
    def get_tables_info(self) -> Dict[str, Any]:
        """获取所有表的元数据"""
        # 表名、字段、类型、约束等
        
    def get_relationships(self) -> List[Dict]:
        """提取外键关系"""
        # 分析表之间的关联
```

## 3. 核心分析流程

### 3.1 六步分析流程详解

#### Step 1: 数据库连接
```python
Tool: connect_database
输入: 数据库配置
输出: {
    "database": "testdb",
    "type": "mysql",
    "total_tables": 15,
    "version": "8.0.23"
}
```

#### Step 2: 领域分析
```python
Tool: analyze_domain
输入: 数据库元信息
输出: {
    "domain": "电子商务",
    "confidence": 0.92,
    "key_entities": ["用户", "商品", "订单", "支付"],
    "domain_features": ["交易流程", "库存管理", "用户体系"]
}
```

#### Step 3: 字段分类
```python
Tool: classify_fields
输入: 所有表的字段信息
输出: {
    "identifiers": ["user_id", "order_id", "product_id"],
    "timestamps": ["created_at", "updated_at"],
    "amounts": ["price", "total_amount", "discount"],
    "status": ["order_status", "payment_status"],
    "descriptive": ["product_name", "user_name", "address"]
}
```

#### Step 4: 表结构分析
```python
Tool: analyze_tables
输入: 表结构和字段分类结果
输出: {
    "core_tables": ["users", "orders", "products"],
    "lookup_tables": ["categories", "payment_methods"],
    "junction_tables": ["order_items"],
    "table_purposes": {
        "users": "用户主表",
        "orders": "订单主表",
        "order_items": "订单明细表"
    }
}
```

#### Step 5: ER关系分析
```python
Tool: analyze_er
输入: 表结构和外键信息
输出: {
    "relationships": [
        {
            "from": "orders.user_id",
            "to": "users.id",
            "type": "many-to-one",
            "description": "订单属于用户"
        }
    ],
    "entity_graph": {...}
}
```

#### Step 6: 场景生成
```python
Tool: generate_scenarios
输入: 前5步的分析结果
输出: {
    "scenarios": [
        {
            "category": "用户分析",
            "question": "查询每个用户的订单总数和总金额",
            "sql": "SELECT u.id, u.name, COUNT(o.id) as order_count, SUM(o.total_amount) as total_amount FROM users u LEFT JOIN orders o ON u.id = o.user_id GROUP BY u.id, u.name",
            "difficulty": "medium",
            "concepts": ["JOIN", "GROUP BY", "聚合函数"]
        }
    ]
}
```

### 3.2 数据生成策略

#### 场景分类
```python
SCENARIO_TEMPLATES = {
    "basic_queries": [
        "单表查询",
        "条件筛选",
        "排序和分页"
    ],
    "aggregations": [
        "分组统计",
        "聚合计算",
        "Having筛选"
    ],
    "joins": [
        "两表关联",
        "多表关联",
        "自连接"
    ],
    "advanced": [
        "子查询",
        "窗口函数",
        "CTE查询"
    ]
}
```

#### 难度分级
```python
DIFFICULTY_LEVELS = {
    "easy": {
        "max_tables": 1,
        "max_conditions": 2,
        "allow_aggregation": False
    },
    "medium": {
        "max_tables": 2,
        "max_conditions": 3,
        "allow_aggregation": True
    },
    "hard": {
        "max_tables": 3,
        "max_conditions": 5,
        "allow_aggregation": True,
        "allow_subquery": True
    }
}
```

## 4. 数据模型

### 4.1 分析结果模型
```python
@dataclass
class AnalysisResult:
    """完整分析结果"""
    database_info: DatabaseInfo
    domain_analysis: DomainAnalysis
    field_classification: FieldClassification
    table_analysis: TableAnalysis
    er_relationships: ERRelationships
    generated_scenarios: List[QueryScenario]
    
@dataclass
class QueryScenario:
    """生成的查询场景"""
    id: str
    category: str           # 查询类别
    question: str          # 自然语言问题
    sql: str              # 对应的SQL
    difficulty: str       # 难度级别
    concepts: List[str]   # 涉及的SQL概念
    tables: List[str]     # 涉及的表
    expected_rows: int    # 预期结果行数
```

### 4.2 工具输入输出规范
```python
# 统一的工具输入格式
ToolInput = {
    "context": Dict,      # 共享上下文
    "parameters": Dict,   # 工具特定参数
    "options": Dict      # 可选配置
}

# 统一的工具输出格式
ToolOutput = {
    "success": bool,
    "result": Any,       # 工具特定结果
    "metadata": Dict,    # 元数据
    "error": Optional[str]
}
```

## 5. LLM 集成

### 5.1 Function Calling 实现
```python
def build_tool_functions() -> List[Dict]:
    """构建 OpenAI Function Calling 格式的工具定义"""
    return [
        {
            "type": "function",
            "function": {
                "name": "analyze_domain",
                "description": "分析数据库的业务领域",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "table_names": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "数据库中的表名列表"
                        }
                    },
                    "required": ["table_names"]
                }
            }
        }
    ]
```

### 5.2 Prompt 工程
```python
ANALYSIS_PROMPTS = {
    "domain": """基于以下表名和字段，分析这个数据库属于什么业务领域：
    {table_info}
    
    请识别：
    1. 主要业务领域
    2. 核心业务实体
    3. 业务特征""",
    
    "scenario": """基于以下数据库分析结果，生成真实的查询场景：
    领域：{domain}
    核心表：{core_tables}
    关系：{relationships}
    
    请生成5个不同难度的查询场景，包含问题和SQL。"""
}
```

## 6. 扩展点

### 6.1 新增分析工具
```python
# 1. 继承 TraeBaseTool
class DataQualityAnalysisTool(TraeBaseTool):
    """数据质量分析工具"""
    
    def run(self, **kwargs) -> Dict:
        # 分析数据完整性
        # 检查数据一致性
        # 评估数据质量
        pass

# 2. 注册到工具映射
TOOL_MAPPING["analyze_quality"] = DataQualityAnalysisTool
```

### 6.2 领域定制
```python
# 领域特定的场景模板
DOMAIN_TEMPLATES = {
    "e-commerce": {
        "scenarios": [
            "用户购买行为分析",
            "商品销售统计",
            "库存预警查询"
        ]
    },
    "education": {
        "scenarios": [
            "学生成绩分析",
            "课程选修统计",
            "教师工作量查询"
        ]
    }
}
```

## 7. 性能优化

### 7.1 缓存策略
- 数据库元数据缓存
- 分析结果缓存
- LLM响应缓存（相同输入）

### 7.2 并行处理
- 字段分类可并行处理多表
- 场景生成可并行生成多个类别

## 8. 质量控制

### 8.1 SQL验证
```python
def validate_generated_sql(sql: str, schema: Dict) -> bool:
    """验证生成的SQL"""
    # 1. 语法检查
    # 2. 表名字段验证
    # 3. 执行可行性测试
    pass
```

### 8.2 场景评分
```python
def score_scenario(scenario: QueryScenario) -> float:
    """对生成的场景进行质量评分"""
    # 考虑因素：
    # - 问题的自然度
    # - SQL的正确性
    # - 难度的合理性
    # - 业务相关性
    pass
```