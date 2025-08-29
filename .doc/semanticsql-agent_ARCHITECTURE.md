# SemanticSQL Agent 架构文档

## 1. 系统架构概览

### 1.1 架构原则
- **分析驱动**：以深度数据库分析为核心
- **工具协同**：多个专业工具协同完成复杂任务
- **规则为主**：场景生成基于规则而非纯LLM
- **质量优先**：确保生成的NL2SQL数据质量

### 1.2 技术栈
- **编程语言**: Python 3.8+
- **核心依赖**:
  - Click: CLI 命令行框架
  - SQLAlchemy: 数据库连接和元数据提取
  - OpenAI SDK: LLM 调用（支持 Qwen）
  - PyYAML: 配置文件解析
- **数据库支持**:
  - MySQL (pymysql)
  - PostgreSQL (psycopg2)
  - SQLite (内置)

## 2. 分层架构详解

### 2.1 表示层 (CLI Layer)

#### CLI 命令结构
```python
cli.py
├── @cli.group()           # 主命令组
├── init                   # 初始化配置
├── test                   # 测试数据库连接
├── schema                 # 查看数据库结构
├── run                    # 执行单次查询
├── interactive            # 交互式模式
└── smart-analyze          # 智能分析（核心）
```

#### smart-analyze 命令流程
```python
@cli.command()
def smart_analyze(ctx, request, config, save_result, verbose, stage_by_stage):
    """智能分析数据库 - 自动执行完整6步流程"""
    # 1. 加载配置
    # 2. 创建 SmartSQLAgent
    # 3. 执行分析
    # 4. 显示结果
    # 5. 保存结果
```

### 2.2 业务逻辑层 (Agent Layer)

#### BaseAgent - ReAct 模式实现
```python
class BaseAgent(ABC):
    """ReAct 模式基础类"""
    
    def execute_sync(self, task: str) -> AgentExecution:
        """同步执行任务"""
        return self._execute_react_loop(task)
    
    def _execute_react_loop(self, task: str) -> Any:
        """ReAct 循环实现"""
        for step in range(self.max_steps):
            # 1. Thought - 生成思考
            response = self._generate_next_action()
            
            # 2. Action - 解析行动
            thought, action, action_input = self._parse_response(response)
            
            # 3. Observation - 执行并观察
            tool_output = self._execute_action(action, action_input)
            
            # 4. 记录步骤
            self._add_step(step_type, content, tool_output)
```

#### SmartSQLAgent - 分析专用实现
```python
class SmartSQLAgent(BaseAgent):
    """智能SQL分析Agent"""
    
    def _initialize_tools(self):
        """注册6步分析所需的工具"""
        # 数据库连接工具
        self.register_tool("connect_database", DatabaseConnectionTool)
        # 领域分析工具  
        self.register_tool("analyze_domain", DomainAnalysisTool)
        # 模式分析工具
        self.register_tool("analyze_schema", SchemaAnalysisTool)
        # 更多工具...
    
    def smart_analyze(self, request: str) -> Dict[str, Any]:
        """执行6步智能分析"""
        execution = self.new_task(request)
        return self._format_analysis_result(execution)
    
    def _generate_final_result(self) -> Dict[str, Any]:
        """整合所有步骤的分析结果"""
        # 收集6个步骤的输出
        # 生成最终的场景数据
```

### 2.3 工具层 (Tools Layer)

#### 工具继承体系
```
TraeBaseTool (抽象基类)
├── AgentTool (agent_tools.py)
│   ├── DatabaseConnectionTool
│   ├── SchemaAnalysisTool
│   ├── QueryGenerationTool
│   ├── QueryExecutionTool
│   ├── DataAnalysisTool
│   ├── ReasoningTool
│   └── DomainAnalysisTool
├── SyncTool (sql_tools.py)
│   ├── SyncSchemaExtractionTool
│   ├── SyncSQLGenerationTool
│   ├── SyncSQLValidationTool
│   └── SyncSQLExecutionTool
└── AnalysisTool (analysis_tools.py)
    ├── SyncDomainAnalysisTool
    ├── SyncFieldClassificationTool
    ├── SyncERAnalysisTool
    └── SyncSequentialThinkingTool
```

#### 工具接口规范
```python
class TraeBaseTool(ABC):
    """工具基类"""
    
    @abstractmethod
    def get_parameters(self) -> List[ToolParameter]:
        """定义工具参数"""
        pass
    
    @abstractmethod
    def run(self, **kwargs) -> Dict[str, Any]:
        """执行工具逻辑"""
        pass
    
    def format_result(self, result: Any) -> Dict[str, Any]:
        """统一结果格式"""
        return {
            "success": True,
            "result": result,
            "tool": self.name,
            "timestamp": datetime.now()
        }
```

### 2.4 基础设施层

#### 配置系统架构
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
        """配置加载流程"""
        # 1. 加载YAML文件
        # 2. 环境变量覆盖
        # 3. 验证配置
        # 4. 创建配置对象
```

#### 数据库管理架构
```python
class DatabaseManager:
    """数据库连接管理"""
    
    def __init__(self, config: DatabaseConfig):
        self.engine = self._create_engine(config)
        self.metadata = MetaData()
        
    def get_tables_info(self) -> Dict[str, Any]:
        """获取数据库元数据"""
        # 表信息
        # 字段信息
        # 约束信息
        
    def execute_query(self, sql: str) -> List[Dict]:
        """执行查询"""
        # 安全检查
        # 执行SQL
        # 返回结果
```

## 3. 六步分析流程架构

### 3.1 执行流程图
```
SmartSQLAgent.smart_analyze()
    │
    ├─> Step 1: 数据库连接
    │   └─> DatabaseConnectionTool
    │       └─> 获取基本信息
    │
    ├─> Step 2: 领域分析  
    │   └─> DomainAnalysisTool
    │       └─> 识别业务领域
    │
    ├─> Step 3: 字段分类
    │   └─> FieldClassificationTool
    │       └─> 分类所有字段
    │
    ├─> Step 4: 表结构分析
    │   └─> SchemaAnalysisTool
    │       └─> 深入分析表结构
    │
    ├─> Step 5: ER关系分析
    │   └─> ERAnalysisTool
    │       └─> 提取实体关系
    │
    └─> Step 6: 场景生成
        └─> 基于前5步结果
            └─> 应用规则生成场景
```

### 3.2 工具执行细节

#### Step 1: DatabaseConnectionTool
```python
输入: 数据库配置
处理: 
  - 建立连接
  - 获取表列表
  - 统计基本信息
输出: {
    "database": "testdb",
    "type": "mysql", 
    "tables": ["users", "orders", ...],
    "total_tables": 12
}
```

#### Step 2: DomainAnalysisTool
```python
输入: 表名列表、数据库信息
处理:
  - 分析表名模式
  - 识别业务关键词
  - 推断业务领域
输出: {
    "domain": "电子商务",
    "confidence": 0.92,
    "key_entities": ["用户", "商品", "订单"],
    "domain_features": ["交易", "支付", "物流"]
}
```

#### Step 3: FieldClassificationTool
```python
输入: 所有表的字段信息
处理:
  - 按类型分类字段
  - 识别业务含义
  - 标记特殊字段
输出: {
    "identifiers": ["id", "user_id", "order_id"],
    "timestamps": ["created_at", "updated_at"],
    "amounts": ["price", "total", "discount"],
    "status": ["status", "state", "is_active"],
    "descriptive": ["name", "description", "address"]
}
```

#### Step 4: SchemaAnalysisTool
```python
输入: 表结构信息
处理:
  - 识别核心业务表
  - 分析表的作用
  - 评估表的重要性
输出: {
    "core_tables": {
        "users": "用户主表",
        "orders": "订单主表",
        "products": "商品主表"
    },
    "lookup_tables": {
        "categories": "商品分类",
        "payment_methods": "支付方式"
    },
    "junction_tables": {
        "order_items": "订单明细"
    }
}
```

#### Step 5: ERAnalysisTool
```python
输入: 表结构和外键信息
处理:
  - 分析外键关系
  - 推断隐式关系
  - 构建关系图
输出: {
    "relationships": [
        {
            "from_table": "orders",
            "from_field": "user_id",
            "to_table": "users",
            "to_field": "id",
            "type": "many-to-one",
            "description": "订单属于用户"
        }
    ],
    "relationship_graph": {...}
}
```

#### Step 6: 场景生成（基于规则）
```python
输入: 前5步的所有分析结果
处理:
  - 应用领域特定规则
  - 基于表结构生成查询模板
  - 组合生成多样化场景
输出: {
    "generated_scenarios": [
        {
            "id": "S001",
            "category": "用户分析",
            "question": "查询最近30天活跃用户数",
            "sql": "SELECT COUNT(DISTINCT user_id) FROM orders WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)",
            "difficulty": "easy",
            "concepts": ["时间函数", "去重计数"]
        },
        // 更多场景...
    ]
}
```

### 3.3 场景生成规则引擎

#### 规则分类
```python
GENERATION_RULES = {
    "电子商务": {
        "用户分析": [
            "活跃用户统计",
            "用户价值分析",
            "用户行为分析"
        ],
        "订单分析": [
            "订单趋势分析",
            "订单状态统计",
            "支付方式分析"
        ],
        "商品分析": [
            "热销商品排行",
            "库存分析",
            "价格分析"
        ]
    },
    "教育系统": {
        "学生分析": [...],
        "课程分析": [...],
        "成绩分析": [...]
    }
}
```

#### 查询模板
```python
QUERY_TEMPLATES = {
    "时间统计": {
        "pattern": "查询{time_period}的{entity}{metric}",
        "sql_template": "SELECT {agg_func}({column}) FROM {table} WHERE {time_column} >= {start_time}",
        "variables": {
            "time_period": ["最近7天", "本月", "今年"],
            "entity": ["用户", "订单", "商品"],
            "metric": ["数量", "总额", "平均值"]
        }
    },
    "分组统计": {
        "pattern": "按{group_by}统计{metric}",
        "sql_template": "SELECT {group_column}, {agg_func}({value_column}) FROM {table} GROUP BY {group_column}",
        "variables": {...}
    }
}
```

## 4. 数据模型架构

### 4.1 执行状态模型
```python
@dataclass
class AgentStep:
    """单个执行步骤"""
    step_type: AgentStepType  # OBSERVATION/THOUGHT/ACTION/REFLECTION
    content: str
    timestamp: datetime
    tool_name: Optional[str]
    tool_input: Optional[Dict]
    tool_output: Optional[Any]
    error: Optional[str]

@dataclass
class AgentExecution:
    """完整执行记录"""
    task: str
    steps: List[AgentStep]
    final_result: Optional[Any]
    success: bool
    total_steps: int
    execution_time: float
```

### 4.2 分析结果模型
```python
@dataclass
class AnalysisResult:
    """6步分析的完整结果"""
    database_connection: DatabaseInfo
    domain_analysis: DomainAnalysis
    field_classification: FieldClassification
    schema_analysis: SchemaAnalysis
    er_analysis: ERAnalysis
    generated_scenarios: List[QueryScenario]

@dataclass
class QueryScenario:
    """生成的查询场景"""
    id: str
    category: str          # 场景类别
    question: str          # 自然语言问题
    sql: str              # 对应SQL
    difficulty: str       # 难度等级
    concepts: List[str]   # SQL概念
    tables: List[str]     # 涉及的表
```

## 5. 关键实现细节

### 5.1 ReAct 响应解析
```python
def _parse_response(self, response: str) -> Tuple[Optional[str], Optional[str], Optional[Dict]]:
    """解析LLM响应，提取思考、行动和输入"""
    thought_match = re.search(r'Thought:\s*(.+?)(?=Action:|$)', response)
    action_match = re.search(r'Action:\s*(\w+)', response)
    input_match = re.search(r'Action Input:\s*({.+?})', response)
    
    thought = thought_match.group(1) if thought_match else None
    action = action_match.group(1) if action_match else None
    action_input = json.loads(input_match.group(1)) if input_match else {}
    
    return thought, action, action_input
```

### 5.2 工具调用机制
```python
def _execute_action(self, action: str, action_input: Dict) -> Any:
    """执行工具调用"""
    if action not in self.tools:
        raise ValueError(f"未知的工具: {action}")
    
    tool = self.tools[action]
    try:
        result = tool.execute(**action_input)
        return result
    except Exception as e:
        self.logger.error(f"工具执行失败: {e}")
        return {"success": False, "error": str(e)}
```

### 5.3 上下文共享
```python
class AnalysisContext:
    """分析上下文，在工具间共享"""
    
    def __init__(self):
        self.database_info = None
        self.domain_result = None
        self.field_classification = None
        self.schema_analysis = None
        self.er_relationships = None
    
    def update(self, step_name: str, result: Any):
        """更新特定步骤的结果"""
        setattr(self, step_name, result)
    
    def get_all(self) -> Dict[str, Any]:
        """获取所有分析结果"""
        return {
            k: v for k, v in self.__dict__.items() 
            if v is not None
        }
```

## 6. 扩展点架构

### 6.1 添加新工具
```python
# 1. 创建工具类
class NewAnalysisTool(TraeBaseTool):
    def __init__(self):
        super().__init__(
            name="new_analysis",
            description="新的分析工具"
        )
    
    def run(self, **kwargs) -> Dict[str, Any]:
        # 实现分析逻辑
        pass

# 2. 注册到工具映射
TOOL_MAPPING["new_analysis"] = NewAnalysisTool

# 3. 在Agent中使用
self.register_tool("new_analysis", NewAnalysisTool())
```

### 6.2 添加新领域
```python
# 在规则引擎中添加新领域
DOMAIN_RULES["医疗系统"] = {
    "患者分析": [
        "患者统计",
        "疾病分布",
        "治疗效果"
    ],
    "医生分析": [...],
    "药品分析": [...]
}

# 添加对应的查询模板
MEDICAL_TEMPLATES = {
    "患者查询": {
        "pattern": "查询{condition}的患者{metric}",
        "sql_template": "..."
    }
}
```

## 7. 性能优化

### 7.1 缓存机制
- 数据库元数据缓存
- 分析结果缓存
- 工具执行结果缓存

### 7.2 并行处理
- 字段分类可并行分析多表
- 场景生成可并行生成多个类别

### 7.3 资源管理
- 数据库连接池
- LLM调用限流
- 内存使用控制