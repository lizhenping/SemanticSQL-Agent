# SemanticSQL Agent 设计规范

## 1. 项目概述

### 1.1 项目定位
SemanticSQL Agent 是一个基于智能体（Agent）架构的 NL2SQL 合成数据生成系统。该系统通过分析数据库结构，自动生成高质量的自然语言问题和对应的 SQL 查询，用于训练 NL2SQL 模型。

### 1.2 核心价值
- **自动化数据生成**：减少人工标注成本
- **高质量训练数据**：确保生成的问题和 SQL 的准确性
- **领域适应性**：根据不同数据库自动适应业务领域
- **可扩展架构**：基于智能体的灵活架构

### 1.3 技术特点
- **ReAct 模式**：基于 Reasoning + Acting 的智能体决策
- **工具生态**：模块化的工具系统
- **Qwen 支持**：使用通义千问的 OpenAI 兼容 API
- **轨迹记录**：完整的执行过程追踪

## 2. 系统架构

### 2.1 架构原则
- **智能体驱动**：核心逻辑由智能体自主完成
- **工具解耦**：工具独立开发和测试
- **配置灵活**：支持 YAML 和环境变量配置
- **易于扩展**：新功能通过添加工具实现

### 2.2 核心组件
1. **智能体系统**
   - BaseAgent：ReAct 模式实现
   - SmartSQLAgent：NL2SQL 专用智能体

2. **工具系统**
   - 分析工具：数据库和领域分析
   - 生成工具：场景、问题、SQL 生成
   - SQL 工具：验证和执行
   - 反思工具：质量改进

3. **基础设施**
   - 配置管理
   - LLM 客户端
   - 数据库连接
   - 日志系统

## 3. 功能设计

### 3.1 数据生成流程

#### 3.1.1 分析阶段
1. **数据库结构提取**
   - 表信息（名称、注释）
   - 列信息（名称、类型、约束）
   - 索引和关系

2. **领域识别**
   - 基于表名和字段名分析
   - 识别业务领域（电商、金融、教育等）
   - 提取领域关键词

3. **字段分类**
   - 标识符字段（ID、编码）
   - 时间戳字段
   - 数值字段（金额、数量）
   - 分类字段（状态、类型）
   - 描述性字段

4. **关系分析**
   - 主外键关系
   - 关联表识别
   - 实体关系图构建

#### 3.1.2 生成阶段
1. **场景生成（基于规则）**
   - 单表查询场景
   - 多表关联场景
   - 聚合统计场景
   - 复杂业务场景

2. **问题生成**
   - 基于场景生成自然语言
   - 覆盖不同难度级别
   - 确保问题的自然性和多样性

3. **SQL 生成（一步完成）**
   - 根据问题直接生成 SQL
   - 确保 SQL 的正确性
   - 支持多种 SQL 类型

#### 3.1.3 验证反思阶段
1. **SQL 验证**
   - 语法检查
   - 语义验证
   - 与数据库结构匹配

2. **SQL 执行**
   - 实际运行测试
   - 性能评估
   - 结果合理性检查

3. **质量反思**
   - 分析执行结果
   - 提供优化建议
   - 生成改进版本

### 3.2 智能体行为设计

#### 3.2.1 ReAct 循环
```
while not done and steps < max_steps:
    thought = think(current_context)    # 分析现状，决定下一步
    action = decide_action(thought)     # 选择工具和参数
    observation = execute(action)       # 执行并观察结果
    context = update(context, observation)  # 更新上下文
```

#### 3.2.2 决策逻辑
- 基于任务进度选择工具
- 处理工具执行失败
- 动态调整执行策略
- 判断任务完成条件

### 3.3 工具设计规范

#### 3.3.1 工具接口
```python
class BaseTool:
    name: str               # 工具唯一标识
    description: str        # 工具功能描述
    
    def get_schema() -> Dict:  # Function Calling Schema
    def run(**kwargs) -> Any:  # 执行工具
```

#### 3.3.2 工具分类
- **分析工具**：提取和分析信息
- **生成工具**：创建新内容
- **验证工具**：检查正确性
- **执行工具**：运行操作
- **反思工具**：评估和改进

## 4. 数据模型

### 4.1 核心实体

#### 4.1.1 任务请求
```python
class TaskRequest:
    database_config: Dict      # 数据库连接配置
    target_count: int         # 目标生成数量
    difficulty_distribution: Dict  # 难度分布
```

#### 4.1.2 分析结果
```python
class SchemaAnalysis:
    tables: List[TableInfo]   # 表信息
    database_type: str        # 数据库类型

class DomainAnalysis:
    domain: str              # 领域名称
    confidence: float        # 置信度
    keywords: List[str]      # 关键词
```

#### 4.1.3 生成结果
```python
class GeneratedQuestion:
    text: str                # 问题文本
    difficulty: str          # 难度级别
    scenario_id: str         # 场景ID

class GeneratedSQL:
    query: str               # SQL查询
    tables_used: List[str]   # 使用的表
    query_type: str          # 查询类型
```

### 4.2 执行跟踪
```python
class AgentStep:
    step_type: str           # THOUGHT/ACTION/OBSERVATION
    content: str             # 步骤内容
    timestamp: datetime      # 时间戳

class AgentExecution:
    task: str                # 任务描述
    steps: List[AgentStep]   # 执行步骤
    final_result: Any        # 最终结果
```

## 5. 接口设计

### 5.1 CLI 接口
```bash
# 智能分析生成
semanticsql-agent smart-analyze \
    --db-type mysql \
    --host localhost \
    --database shop_db \
    --count 100

# 交互模式
semanticsql-agent interactive

# 测试连接
semanticsql-agent test-connection
```

### 5.2 配置接口
```yaml
# config.yaml
database:
  type: mysql
  host: localhost
  port: 3306
  database: shop_db
  
llm:
  model: qwen-plus
  base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
  api_key: ${DASHSCOPE_API_KEY}
  
agent:
  max_steps: 20
  enable_reflection: true
```

### 5.3 输出接口
```json
{
  "dataset_id": "uuid",
  "created_at": "2024-01-01T00:00:00",
  "statistics": {
    "total_examples": 100,
    "difficulty_distribution": {},
    "query_type_distribution": {}
  },
  "examples": [
    {
      "question": "查询最近30天的订单总额",
      "sql": "SELECT SUM(amount) FROM orders WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)",
      "difficulty": "medium",
      "scenario": "time_based_aggregation"
    }
  ]
}
```

## 6. 非功能需求

### 6.1 性能要求
- 生成 100 条数据 < 5 分钟
- LLM 调用优化（批处理、缓存）
- 数据库查询优化

### 6.2 可靠性要求
- 错误恢复机制
- 中断续传支持
- 结果持久化

### 6.3 可维护性要求
- 模块化设计
- 完整的日志记录
- 代码规范遵循

### 6.4 安全要求
- 数据库凭据加密
- API Key 安全存储
- SQL 注入防护

## 7. 技术选型

### 7.1 核心技术
- **语言**：Python 3.8+
- **LLM**：Qwen (通义千问)
- **框架**：基于 trae_agent 理念

### 7.2 主要依赖
- **openai**：LLM 客户端
- **sqlalchemy**：数据库操作
- **click**：CLI 框架
- **pydantic**：数据验证
- **pyyaml**：配置管理

### 7.3 开发工具
- **pytest**：单元测试
- **black**：代码格式化
- **mypy**：类型检查

## 8. 部署方案

### 8.1 环境要求
- Python 3.8+
- 支持的数据库：MySQL、PostgreSQL、SQLite
- 内存：建议 4GB+
- 网络：需要访问 LLM API

### 8.2 安装部署
```bash
# 安装
pip install semanticsql-agent

# 配置
export DASHSCOPE_API_KEY=your_api_key

# 运行
semanticsql-agent smart-analyze --config config.yaml
```

### 8.3 Docker 支持
```dockerfile
FROM python:3.8-slim
WORKDIR /app
COPY . .
RUN pip install -e .
CMD ["semanticsql-agent", "smart-analyze"]
```

## 9. 测试策略

### 9.1 单元测试
- 工具功能测试
- 数据模型测试
- 工具集成测试

### 9.2 集成测试
- 智能体执行测试
- 端到端流程测试
- 配置加载测试

### 9.3 质量测试
- 生成 SQL 正确性
- 问题自然度评估
- 数据多样性检查

## 10. 项目规划

### 10.1 第一阶段（MVP）
- [x] 基础架构搭建
- [x] 核心工具实现
- [x] 智能体基本功能
- [ ] CLI 接口

### 10.2 第二阶段（功能完善）
- [ ] 更多数据库支持
- [ ] 高级 SQL 类型
- [ ] 批量处理优化
- [ ] Web UI

### 10.3 第三阶段（生态建设）
- [ ] 插件系统
- [ ] 社区工具
- [ ] 云服务集成
- [ ] 多语言支持