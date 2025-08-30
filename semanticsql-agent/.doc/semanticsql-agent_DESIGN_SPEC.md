# SemanticSQL Agent 设计规范

## 1. 项目概述

### 1.1 项目定位
SemanticSQL Agent 是一个基于智能体架构的 NL2SQL 合成数据生成系统。该系统通过智能分析数据库结构，自动生成高质量的自然语言问题和对应的 SQL 查询，用于训练 NL2SQL 模型。

### 1.2 核心价值
- **自动化生成**：减少人工标注成本，快速生成大量训练数据
- **高质量保证**：通过验证和反思机制确保数据质量
- **领域适应**：自动识别业务领域，生成符合领域特征的数据
- **灵活扩展**：基于工具的架构，易于添加新功能

### 1.3 设计原则
- **智能体驱动**：采用 ReAct 模式，智能体自主决策执行流程
- **模块化设计**：工具职责单一，通过智能体协调
- **简洁实用**：避免过度设计，保持代码简单高效
- **可追踪性**：完整记录执行过程，便于调试和优化

## 2. 功能规范

### 2.1 核心功能

#### 2.1.1 数据库分析
- **结构提取**：获取表、列、索引、约束等信息
- **领域识别**：基于表名和字段识别业务领域
- **字段分类**：将字段分类为标识符、时间戳、数值、分类、描述等类型
- **关系分析**：识别主外键关系，构建 ER 图

#### 2.1.2 数据生成流程
1. **场景生成**：基于规则生成业务场景
2. **操作选择**：为场景选择合适的 SQL 操作类型
3. **问题生成**：生成自然语言问题
4. **SQL 生成**：一步生成对应的 SQL 查询

#### 2.1.3 验证与优化
- **语法验证**：检查 SQL 语法正确性
- **执行测试**：实际执行 SQL 验证可行性
- **反思优化**：分析执行结果，提供优化建议

### 2.2 数据生成规范

#### 2.2.1 场景类型
- **基础查询**：单表查询、条件筛选
- **关联查询**：多表 JOIN、子查询
- **聚合统计**：GROUP BY、聚合函数
- **时间分析**：时间范围、趋势分析
- **复杂查询**：窗口函数、CTE、复杂条件

#### 2.2.2 难度分布
```yaml
difficulty_distribution:
  easy: 30%    # 基础单表查询
  medium: 20%  # 关联和聚合查询
  hard: 30%    # 复杂查询和高级特性
  expert: 20%    # 复杂查询和高级特性
```

#### 2.2.3 质量标准
- SQL 语法必须正确
- 问题表述自然流畅
- SQL 与问题语义匹配
- 执行结果合理有效

## 3. 接口规范

### 3.1 工具接口

```python
class BaseTool(ABC):
    """工具基类接口规范"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """工具唯一标识，用于注册和调用"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """工具功能描述，用于 LLM 理解"""
        pass
    
    @abstractmethod
    def run(self, **kwargs) -> Dict[str, Any]:
        """
        工具执行接口
        
        返回格式：
        {
            "success": bool,      # 执行是否成功
            "data": Any,         # 成功时的返回数据
            "error": str,        # 失败时的错误信息
            "metadata": dict     # 可选的元数据
        }
        """
        pass
```

### 3.2 智能体接口

```python
class BaseAgent(ABC):
    """智能体基类接口规范"""
    
    @abstractmethod
    def run(self, task: str, context: Dict = None) -> AgentExecution:
        """执行任务"""
        pass
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        pass
    
    def register_tool(self, tool: BaseTool) -> None:
        """注册工具"""
        pass
```

### 3.3 命令行接口

```bash
# 基础生成命令
semanticsql-agent generate [OPTIONS]

Options:
  --config PATH           配置文件路径
  --count INTEGER        生成数据条数 [default: 100]
  --db-type TEXT         数据库类型 [mysql|postgresql|sqlite]
  --host TEXT            数据库主机
  --port INTEGER         数据库端口
  --database TEXT        数据库名称
  --username TEXT        用户名
  --password TEXT        密码
  --output PATH          输出文件路径
  --format TEXT          输出格式 [json|jsonl|csv]
  --verbose              详细输出
  --help                 显示帮助信息

# 其他命令
semanticsql-agent test-connection  # 测试数据库连接
semanticsql-agent init            # 初始化配置
semanticsql-agent version         # 显示版本信息
```

## 4. 数据模型规范

### 4.1 核心数据结构

#### 4.1.1 执行记录
```python
@dataclass
class AgentStep:
    """单个执行步骤"""
    step_type: AgentStepType  # thought/action/observation
    content: str              # 步骤内容
    timestamp: datetime       # 时间戳
    tool_name: Optional[str]  # 使用的工具
    tool_output: Optional[Any]  # 工具输出
    error: Optional[str]      # 错误信息

@dataclass
class AgentExecution:
    """完整执行记录"""
    task_id: str              # 任务ID
    task: str                 # 任务描述
    started_at: datetime      # 开始时间
    completed_at: Optional[datetime]  # 结束时间
    steps: List[AgentStep]    # 执行步骤
    final_result: Optional[Any]  # 最终结果
    status: str               # running/completed/failed
    error: Optional[str]      # 错误信息
```

#### 4.1.2 生成数据
```python
@dataclass
class QueryScenario:
    """查询场景"""
    id: str
    category: str            # 场景类别
    business_purpose: str    # 业务目的
    complexity: str          # easy/medium/hard
    applicable_tables: List[str]

@dataclass
class GeneratedExample:
    """生成的训练样本"""
    id: str
    scenario_id: str
    question: str            # 自然语言问题
    sql: str                # SQL 查询
    difficulty: str          # 难度级别
    validation_result: Dict  # 验证结果
    execution_result: Dict   # 执行结果
    quality_score: float     # 质量分数
```

### 4.2 配置规范

```yaml
# 完整配置示例
database:
  type: mysql              # 数据库类型
  host: localhost         
  port: 3306              
  username: root          
  password: ${DB_PASSWORD}  # 支持环境变量
  database: shop_db       
  
llm:
  model: Qwen3-14B        # 模型名称
  base_url: http://192.168.200.216:9009/v1
  api_key: ${DASHSCOPE_API_KEY}
  temperature: 0.7        # 生成温度
  max_tokens: 4096        # 最大token数
  
agent:
  max_steps: 30           # 最大执行步骤
  enable_reflection: true # 启用反思
  verbose: true           # 详细日志
  
generation:
  scenarios_per_batch: 10      # 每批场景数
  questions_per_scenario: 5    # 每场景问题数
  sql_complexity_weights:      # SQL复杂度权重
    simple: 0.3
    medium: 0.5
    complex: 0.2
    
output:
  directory: ./output     # 输出目录
  format: json           # 默认格式
  save_intermediate: false  # 是否保存中间结果
```

## 5. 错误处理规范

### 5.1 错误分类
- **配置错误**：配置文件缺失、格式错误、必需参数缺失
- **连接错误**：数据库连接失败、LLM API 连接失败
- **执行错误**：工具执行失败、SQL 执行错误
- **验证错误**：SQL 语法错误、数据验证失败
- **系统错误**：内存不足、权限问题

### 5.2 错误处理策略
```python
# 工具级错误处理
def run(self, **kwargs) -> Dict[str, Any]:
    try:
        # 执行逻辑
        result = self._execute(**kwargs)
        return {
            "success": True,
            "data": result
        }
    except ValidationError as e:
        return {
            "success": False,
            "error": f"参数验证失败: {e}",
            "error_type": "validation"
        }
    except Exception as e:
        self.logger.error(f"工具执行失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "error_type": "execution"
        }

# Agent 级错误恢复
def _execute_with_retry(self, action: Dict, max_retries: int = 3):
    """带重试的执行"""
    for attempt in range(max_retries):
        try:
            return self._execute_tool(action)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            self.logger.warning(f"执行失败，重试 {attempt + 1}/{max_retries}")
            time.sleep(2 ** attempt)  # 指数退避
```

## 6. 日志规范

### 6.1 日志级别
- **DEBUG**：详细的调试信息，包括 LLM 交互
- **INFO**：正常的执行流程信息
- **WARNING**：警告信息，如重试、降级
- **ERROR**：错误信息，但不影响继续执行
- **CRITICAL**：严重错误，导致程序终止

### 6.2 日志格式
```python
# 日志配置
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'detailed': {
            'format': '%(asctime)s [%(levelname)s] %(name)s.%(funcName)s:%(lineno)d - %(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
            'stream': 'ext://sys.stdout'
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'detailed',
            'filename': 'semanticsql-agent.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console', 'file']
    }
}
```

## 7. 文档规范

### 7.1 代码文档
- 所有公共接口必须有 docstring
- 复杂逻辑添加行内注释
- 示例代码保持可运行

### 7.2 用户文档
- README.md：项目介绍和快速开始
- INSTALL.md：详细安装指南
- USAGE.md：使用教程
- API.md：API 参考

### 7.3 开发文档
- CONTRIBUTING.md：贡献指南
- DEVELOPMENT.md：开发环境搭建
- ARCHITECTURE.md：架构设计
- DESIGN.md：设计决策