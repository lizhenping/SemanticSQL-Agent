# SemanticSQL Agent 架构文档

## 1. 系统架构概览

### 1.1 架构原则
- **简洁实用**：避免过度设计，专注核心功能
- **模块化**：组件职责清晰，便于维护和扩展
- **标准兼容**：遵循 OpenAI API 标准，支持 Function Calling
- **配置驱动**：通过配置文件控制行为

### 1.2 技术栈
- **编程语言**: Python 3.8+
- **核心框架**:
  - Click: CLI 命令行框架
  - SQLAlchemy: 数据库操作
  - OpenAI SDK: LLM 调用（支持 Qwen）
  - PyYAML: 配置文件解析
- **支持的数据库**:
  - MySQL (通过 pymysql)
  - PostgreSQL (通过 psycopg2)
  - SQLite (内置支持)

## 2. 分层架构详解

### 2.1 表示层 (CLI Layer)

#### 目录结构
```
cli/
├── __init__.py
└── cli.py          # CLI 主入口，所有命令定义
```

#### 核心命令
- `init`: 初始化配置文件
- `run`: 执行单次查询
- `interactive`: 交互式查询模式
- `test`: 测试数据库连接
- `schema`: 查看数据库结构
- `generate`: 批量生成测试数据（开发用）

### 2.2 业务逻辑层 (Agent Layer)

#### 目录结构
```
agent/
├── __init__.py
├── base_agent.py      # ReAct 模式基础实现
└── smart_sql_agent.py # SQL 查询智能体
```

#### BaseAgent 核心设计
```python
class BaseAgent(ABC):
    """ReAct 模式基础类"""
    
    def execute_sync(self, task: str) -> AgentExecution:
        """同步执行任务"""
        # 1. 初始化执行记录
        # 2. 执行 ReAct 循环
        # 3. 返回执行结果
        
    def _execute_react_loop(self, task: str) -> Any:
        """ReAct 循环: Observe → Think → Act"""
        for step in range(self.max_steps):
            # 生成下一步行动
            response = self._generate_next_action()
            # 解析并执行
            thought, action, action_input = self._parse_response(response)
            # 执行工具调用
            result = self._execute_action(action, action_input)
```

#### SmartSQLAgent 实现
```python
class SmartSQLAgent(BaseAgent):
    """SQL 查询专用智能体"""
    
    def query(self, question: str) -> SQLQueryResult:
        """执行自然语言查询"""
        # 1. 理解查询需求
        # 2. 分析数据库结构
        # 3. 生成 SQL
        # 4. 执行查询
        # 5. 返回格式化结果
```

### 2.3 工具层 (Tools Layer)

#### 目录结构
```
tools/
├── __init__.py
├── trae_base_tool.py   # 工具基类
├── sql_tools.py        # SQL 相关工具
├── analysis_tools.py   # 分析类工具
└── agent_tools.py      # Agent 辅助工具
```

#### 工具基类设计
```python
class TraeBaseTool(ABC):
    """工具基类"""
    name: str              # 工具名称
    description: str       # 工具描述
    
    @abstractmethod
    def get_parameters(self) -> List[ToolParameter]:
        """定义工具参数"""
        pass
    
    @abstractmethod
    def run(self, **kwargs) -> Dict[str, Any]:
        """执行工具"""
        pass
```

#### SQL 工具集
1. **SyncSchemaExtractionTool**: 提取数据库模式
   - 获取所有表名
   - 获取表结构信息
   - 识别主键和外键

2. **SyncSQLGenerationTool**: 生成 SQL 语句
   - 调用 LLM 生成 SQL
   - 基于表结构上下文
   - 支持 Function Calling

3. **SyncSQLExecutionTool**: 执行 SQL 查询
   - 执行 SELECT 语句
   - 结果格式化
   - 错误处理

### 2.4 基础设施层 (Infrastructure Layer)

#### 配置管理 (`config/`)
```
config/
├── __init__.py
└── trae_config.py     # 统一配置管理
```

**配置结构**:
```python
@dataclass
class DatabaseConfig:
    type: str         # mysql/postgresql/sqlite
    host: str
    port: int
    database: str
    username: str
    password: str

@dataclass
class LLMConfig:
    model: str        # Qwen3-14B
    base_url: str     # OpenAI 兼容端点
    api_key: str
    temperature: float = 0.1
    max_tokens: int = 2000

@dataclass
class TraeConfig:
    app: AppConfig
    database: DatabaseConfig
    llm: LLMConfig
    agent: AgentConfig
```

#### 数据库管理 (`database/`)
```
database/
├── __init__.py
└── connection_manager.py  # 数据库连接管理
```

**连接管理特性**:
- 连接池支持
- 自动重连
- 多数据库兼容
- 连接健康检查

#### LLM 客户端
- 使用标准 OpenAI SDK
- 支持自定义 base_url
- Function Calling 支持
- 请求/响应日志

## 3. 核心流程

### 3.1 查询执行流程
```
1. 用户输入: "查询每个部门的平均工资"
   ↓
2. Agent 初始化
   - 加载配置
   - 建立数据库连接
   - 初始化 LLM 客户端
   ↓
3. ReAct 执行
   - Thought: "需要找到部门表和员工表"
   - Action: analyze_schema
   - Observation: "发现 departments 和 employees 表"
   ↓
4. SQL 生成
   - Thought: "需要 JOIN 两个表并计算平均值"
   - Action: generate_sql
   - Result: "SELECT d.name, AVG(e.salary) ..."
   ↓
5. 查询执行
   - Action: execute_sql
   - Result: 查询结果数据
   ↓
6. 返回结果
   - 格式化输出
   - 包含 SQL 和数据
```

### 3.2 Function Calling 流程
```python
# 1. 定义工具
tools = [{
    "type": "function",
    "function": {
        "name": "execute_sql",
        "description": "执行SQL查询",
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "要执行的SQL语句"
                }
            },
            "required": ["sql"]
        }
    }
}]

# 2. 发送给 LLM
response = client.chat.completions.create(
    model="Qwen3-14B",
    messages=messages,
    tools=tools,
    tool_choice="auto"
)

# 3. 处理 function_call
if response.choices[0].message.tool_calls:
    for tool_call in response.choices[0].message.tool_calls:
        if tool_call.function.name == "execute_sql":
            result = execute_sql(tool_call.function.arguments["sql"])
```

## 4. 数据模型

### 4.1 核心数据结构

#### Agent 执行状态
```python
@dataclass
class AgentStep:
    step_type: AgentStepType  # OBSERVATION/THOUGHT/ACTION
    content: str
    timestamp: datetime
    tool_name: Optional[str]
    tool_input: Optional[Dict]
    tool_output: Optional[Any]

@dataclass
class AgentExecution:
    task: str
    steps: List[AgentStep]
    final_result: Optional[Any]
    success: bool
    execution_time: float
```

#### SQL 查询结果
```python
@dataclass
class SQLQueryResult:
    success: bool
    question: str           # 原始问题
    sql: Optional[str]      # 生成的 SQL
    data: Optional[List]    # 查询结果
    row_count: Optional[int]
    execution_time: float
    error: Optional[str]
```

## 5. 关键实现细节

### 5.1 数据库模式缓存
```python
class SchemaCache:
    """数据库模式缓存"""
    
    def __init__(self):
        self._cache = {}
        self._ttl = 3600  # 1小时过期
    
    def get_schema(self, db_name: str) -> Optional[Dict]:
        if db_name in self._cache:
            schema, timestamp = self._cache[db_name]
            if time.time() - timestamp < self._ttl:
                return schema
        return None
```

### 5.2 SQL 安全检查
```python
def validate_sql(sql: str) -> bool:
    """验证 SQL 安全性"""
    # 转换为小写进行检查
    sql_lower = sql.lower().strip()
    
    # 只允许 SELECT 语句
    if not sql_lower.startswith('select'):
        return False
    
    # 禁止危险关键字
    dangerous_keywords = ['drop', 'delete', 'update', 'insert', 'alter']
    for keyword in dangerous_keywords:
        if keyword in sql_lower:
            return False
    
    return True
```

### 5.3 结果格式化
```python
def format_query_result(result: List[Dict]) -> str:
    """格式化查询结果为表格"""
    if not result:
        return "查询结果为空"
    
    # 使用 tabulate 生成表格
    headers = list(result[0].keys())
    rows = [list(row.values()) for row in result]
    
    return tabulate(rows, headers=headers, tablefmt="grid")
```

## 6. 扩展点

### 6.1 添加新工具
1. 在 `tools/` 目录创建新工具类
2. 继承 `TraeBaseTool`
3. 实现必需的方法
4. 在 `__init__.py` 中注册

### 6.2 支持新的 LLM
- 只要支持 OpenAI API 标准即可
- 修改 `base_url` 和认证方式
- 调整模型特定参数

### 6.3 数据库扩展
1. 添加新的数据库驱动
2. 实现连接字符串生成
3. 适配 SQL 方言差异

## 7. 性能优化

### 7.1 缓存策略
- 数据库模式缓存（减少元数据查询）
- SQL 模板缓存（相似查询复用）
- 连接池（避免频繁建立连接）

### 7.2 查询优化
- 限制结果集大小（LIMIT）
- 索引利用建议
- 查询计划分析

## 8. 错误处理

### 8.1 错误分类
- **连接错误**: 数据库连接失败
- **SQL错误**: SQL 语法错误或执行错误  
- **LLM错误**: API 调用失败或超时
- **工具错误**: 工具执行异常

### 8.2 错误恢复
- 数据库连接自动重试
- LLM 调用失败回退
- 友好的错误提示

## 9. 监控和日志

### 9.1 日志级别
- INFO: 正常操作日志
- DEBUG: 详细调试信息
- WARNING: 警告信息
- ERROR: 错误信息

### 9.2 关键指标
- 查询成功率
- 平均响应时间
- LLM Token 使用量
- 数据库连接状态