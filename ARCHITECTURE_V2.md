# SemanticSQL-Agent 架构设计文档（简化版）

## 1. 项目概述

SemanticSQL-Agent 是一个基于智能体架构的自然语言到SQL转换系统，继承了 TRAEAgent 的设计理念，并参考了 nl2sql_pipeline 的实现方式。

### 1.1 核心特性
- 基于 ReAct (Thought-Action-Observation) 模式
- 工具驱动的渐进式理解
- 简单有效的反思机制
- 模块化的组件设计（参考 nl2sql_pipeline）

### 1.2 设计原则
- **简洁性优先**：避免过度设计
- **同步执行**：不使用异步编程
- **继承复用**：基于 TRAEAgent 的成熟模式
- **实用主义**：参考 nl2sql_pipeline 的实现

## 2. 架构层次设计

```
semanticsql-agent/
│
├── 配置层 (Configuration Layer)
│   └── config/
│       ├── __init__.py
│       ├── database.py              # 数据库配置（参考 nl2sql_pipeline）
│       └── environment.py           # 环境配置
│
├── 服务层 (Service Layer)
│   └── services/
│       ├── __init__.py
│       ├── database_service.py      # 数据库服务基类
│       └── mysql_database_service.py # MySQL服务实现
│
├── 智能体核心层 (Agent Core Layer)
│   └── agent/
│       ├── __init__.py
│       ├── agent_basics.py          # 状态定义
│       ├── base_agent.py            # 基础智能体类
│       └── nl2sql_agent.py          # NL2SQL 智能体实现
│
├── 工具层 (Tools Layer)
│   └── tools/
│       ├── __init__.py
│       ├── base.py                  # 工具基类
│       ├── schema_extraction_tool.py # 数据库结构提取
│       ├── initial_domain_analysis_tool.py # 初始领域分析
│       ├── field_classification_tool.py    # 字段分类
│       ├── table_description_tool.py       # 表描述生成
│       ├── column_description_tool.py      # 列描述生成
│       ├── er_analysis_tool.py            # 实体关系分析
│       ├── scenario_generation_tool.py     # 场景生成
│       ├── sql_generation_tool.py          # SQL生成
│       ├── sequential_thinking_tool.py     # 深度思考（可选）
│       └── task_done_tool.py              # 任务完成标记
│
├── LLM 客户端层
│   └── utils/
│       └── llm_clients/
│           ├── __init__.py
│           ├── llm_basics.py        # LLM 基础类型
│           ├── base_client.py       # 客户端基类
│           └── openai_client.py     # OpenAI 实现
│
└── 提示词层
    └── prompt/
        └── agent_prompt.py          # 系统提示词
```

## 3. 核心组件设计

### 3.1 数据库配置（参考 nl2sql_pipeline）

```python
# config/database.py
class DatabaseConfig:
    """数据库配置管理器"""
    
    def __init__(self, 
                 host: str = None,
                 port: int = None,
                 user: str = None,
                 password: str = None,
                 database: str = None):
        self.host = host
        self.port = port or 3306
        self.user = user
        self.password = password
        self.database = database
    
    def validate(self) -> bool:
        """验证配置是否完整"""
        required_fields = ['host', 'user', 'password', 'database']
        return all(getattr(self, field) is not None for field in required_fields)
```

### 3.2 数据库服务（参考 nl2sql_pipeline）

```python
# services/database_service.py
class DatabaseService(ABC):
    """数据库服务抽象基类"""
    
    @abstractmethod
    def connect(self, config: Dict[str, Any]):
        """建立数据库连接"""
        pass
    
    @abstractmethod
    def get_tables(self) -> List[Dict[str, Any]]:
        """获取所有表信息"""
        pass
    
    @abstractmethod
    def get_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """获取表的列信息"""
        pass
```

### 3.3 智能体实现（简化版）

```python
# agent/base_agent.py
class BaseAgent(ABC):
    """通用智能体基类 - 同步执行"""
    
    def __init__(self, config: AgentConfig):
        self._llm_client = LLMClient(config.model)
        self._tools: List[Tool] = []
        self._max_steps = config.max_steps
        
    def execute_task(self) -> AgentExecution:
        """执行任务 - TAO 循环"""
        execution = AgentExecution(task=self._task)
        messages = self._initial_messages
        
        for step_number in range(1, self._max_steps + 1):
            # Thought
            llm_response = self._llm_client.chat(messages, self._tools)
            
            # Action
            if llm_response.tool_calls:
                tool_results = self._execute_tools(llm_response.tool_calls)
                
                # Observation
                messages.extend(self._create_messages(tool_results))
                
                # 简单反思
                reflection = self.reflect_on_result(tool_results)
                if reflection:
                    messages.append(LLMMessage(role="assistant", content=reflection))
            
            if self._is_task_completed(llm_response):
                break
                
        return execution
```

## 4. 执行流程

### 4.1 典型执行序列

```
用户查询: "查询每个部门的平均工资"

Step 1: 提取数据库结构
  - Tool: schema_extraction_tool
  - Result: 获取 employees, departments 等表结构

Step 2: 初始领域分析
  - Tool: initial_domain_analysis_tool  
  - Result: 识别为"人力资源"领域

Step 3: 字段分类
  - Tool: field_classification_tool
  - Result: salary -> 度量字段, dept_id -> 外键

Step 4: 生成查询场景
  - Tool: scenario_generation_tool
  - Result: "按部门分组统计平均值"

Step 5: 生成SQL
  - Tool: sql_generation_tool
  - Result: "SELECT d.dept_name, AVG(e.salary) FROM employees e JOIN departments d ON e.dept_id = d.id GROUP BY d.dept_name"

Step 6: 任务完成
  - Tool: task_done_tool
```

## 5. 配置示例

```yaml
# semanticsql_config.yaml
model:
  provider: openai
  model: gpt-4
  temperature: 0.1

database:
  host: localhost
  port: 3306
  user: root
  password: password
  database: test_db

agent:
  max_steps: 15
  tools:
    - schema_extraction
    - initial_domain_analysis
    - field_classification
    - table_description
    - column_description
    - er_analysis
    - scenario_generation
    - sql_generation
    - sequential_thinking
    - task_done
```

## 6. 简化特性

1. **无异步编程**：所有操作都是同步的
2. **无并行执行**：工具按顺序执行
3. **无复杂监控**：只保留基础日志
4. **无性能优化**：专注功能实现
5. **无安全审查**：信任内部使用
6. **无国际化**：仅支持中英文
7. **无CI/CD**：手动部署

## 7. 开发指南

### 7.1 添加新工具

```python
# tools/my_tool.py
class MyTool(Tool):
    def get_name(self) -> str:
        return "my_tool"
        
    def get_description(self) -> str:
        return "工具描述"
        
    def execute(self, **kwargs) -> ToolResult:
        try:
            # 实现逻辑
            return ToolResult(success=True, data={})
        except Exception as e:
            return ToolResult(success=False, error=str(e))
```

### 7.2 使用示例

```python
from semanticsql import NL2SQLAgent, DatabaseConfig

# 配置数据库
db_config = DatabaseConfig(
    host="localhost",
    user="root", 
    password="password",
    database="test_db"
)

# 创建智能体
agent = NL2SQLAgent(db_config)

# 执行查询
result = agent.execute_nl2sql("查询所有订单的总金额")
print(result.sql)
```

## 8. 联系方式

作者邮箱：lizhenping18@mails.ucas.ac.cn