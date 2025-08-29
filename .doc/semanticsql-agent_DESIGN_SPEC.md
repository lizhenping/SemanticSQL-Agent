# SemanticSQL Agent 设计规范

## 1. 项目概述

### 1.1 项目背景
SemanticSQL Agent 是一个基于大语言模型（LLM）的 NL2SQL 训练数据生成系统。该项目通过智能分析数据库结构，基于规则和模板自动生成高质量的自然语言问题和对应的 SQL 查询对，用于训练和评估 NL2SQL 模型。

### 1.2 设计理念
- **智能分析优先**：深度理解数据库结构和业务含义
- **规则驱动生成**：基于规则和模板生成场景，而非完全依赖LLM
- **工具链架构**：将复杂的分析任务分解为专业工具的协同工作
- **数据质量导向**：生成真实、多样、准确的训练数据

### 1.3 核心特性
- 基于 ReAct 模式的智能数据库分析
- 六步渐进式分析流程
- 规则驱动的场景问题生成
- 支持 Qwen 模型的 OpenAI 兼容 API（包括 Function Calling）
- 支持多种数据库（MySQL、PostgreSQL、SQLite）

## 2. 系统架构设计

### 2.1 整体架构
```
┌─────────────────────────────────────────────────────────┐
│                      用户接口层                           │
│                   (CLI Interface)                        │
│            smart-analyze 命令（核心入口）                  │
└────────────────────────┬────────────────────────────────┘
                        │
┌────────────────────────┴────────────────────────────────┐
│                     智能体层                              │
│                  (Agent Layer)                           │
│  ┌─────────────┐  ┌──────────────┐                     │
│  │  BaseAgent  │  │SmartSQLAgent │                     │
│  │  (ReAct基类)│  │ (分析专用)   │                     │
│  └─────────────┘  └──────────────┘                     │
└────────────────────────┬────────────────────────────────┘
                        │
┌────────────────────────┴────────────────────────────────┐
│                   工具层                                  │
│                (Tools Layer)                             │
│  ┌────────────────────────────────────────────────────┐ │
│  │              Agent Tools                            │ │
│  │  ├─ DatabaseConnectionTool (数据库连接)              │ │
│  │  ├─ SchemaAnalysisTool (模式分析)                   │ │
│  │  ├─ QueryGenerationTool (SQL生成)                   │ │
│  │  ├─ QueryExecutionTool (SQL执行)                    │ │
│  │  ├─ DataAnalysisTool (数据分析)                     │ │
│  │  └─ ReasoningTool (推理辅助)                        │ │
│  ├────────────────────────────────────────────────────┤ │
│  │              SQL Tools                              │ │
│  │  ├─ SyncSchemaExtractionTool                       │ │
│  │  ├─ SyncSQLGenerationTool                          │ │
│  │  ├─ SyncSQLValidationTool                          │ │
│  │  └─ SyncSQLExecutionTool                           │ │
│  ├────────────────────────────────────────────────────┤ │
│  │           Analysis Tools                            │ │
│  │  ├─ SyncDomainAnalysisTool (领域分析)               │ │
│  │  ├─ SyncFieldClassificationTool (字段分类)          │ │
│  │  ├─ SyncERAnalysisTool (ER关系分析)                │ │
│  │  └─ SyncSequentialThinkingTool (序列思考)          │ │
│  └────────────────────────────────────────────────────┘ │
└────────────────────────┬────────────────────────────────┘
                        │
┌────────────────────────┴────────────────────────────────┐
│                    基础设施层                             │
│               (Infrastructure Layer)                     │
│  ┌────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ 配置管理   │  │  LLM客户端    │  │  数据库管理   │  │
│  │TraeConfig  │  │  Qwen支持     │  │  连接池       │  │
│  └────────────┘  └──────────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 2.2 核心组件设计

#### 2.2.1 六步分析流程
完整的数据生成流程包含六个阶段：

1. **数据库连接** (`connect_database`)
   - 建立数据库连接
   - 获取基本信息（表数量、数据库类型等）

2. **领域分析** (`analyze_domain`)
   - 基于表名、字段名识别业务领域
   - 理解数据库的业务用途
   - 使用 DomainAnalysisTool

3. **字段分类** (`classify_fields`)
   - 分析每个字段的业务含义
   - 识别主键、外键、业务字段
   - 使用 FieldClassificationTool

4. **表结构分析** (`analyze_schema`)
   - 深入分析每张表的结构
   - 识别核心业务表和辅助表
   - 使用 SchemaAnalysisTool

5. **ER关系分析** (`analyze_er`)
   - 分析表之间的关联关系
   - 构建实体关系图谱
   - 使用 ERAnalysisTool

6. **场景问题生成**
   - 基于前5步的分析结果
   - 使用规则和模板生成查询场景
   - 生成自然语言问题和对应SQL
   - 通过智能体协调多个工具完成

#### 2.2.2 工具系统设计

**工具基类** (TraeBaseTool)
```python
class TraeBaseTool(ABC):
    name: str              # 工具名称
    description: str       # 工具描述
    
    @abstractmethod
    def get_parameters(self) -> List[ToolParameter]:
        """定义工具参数"""
    
    @abstractmethod
    def run(self, **kwargs) -> Dict[str, Any]:
        """执行工具逻辑"""
```

**工具分类**：
1. **Agent工具** (agent_tools.py)
   - 智能体直接调用的高级工具
   - 包含LLM交互能力

2. **SQL工具** (sql_tools.py)
   - 同步SQL操作工具
   - 不依赖LLM的基础工具

3. **分析工具** (analysis_tools.py)
   - 专门的分析工具
   - 提供深度数据库理解

#### 2.2.3 场景生成机制
- **基于规则**：根据识别的领域和表结构应用预定义规则
- **模板驱动**：使用查询模板生成多样化的问题
- **难度分级**：生成不同复杂度的查询场景
- **覆盖全面**：确保覆盖各种SQL特性和业务场景

### 2.3 数据流设计

#### 2.3.1 分析执行流程
```
用户启动分析命令
    ↓
加载配置 → 初始化 SmartSQLAgent
    ↓
执行六步分析流程:
    ├─ Step 1: 连接数据库，获取元数据
    ├─ Step 2: 分析业务领域特征
    ├─ Step 3: 对字段进行语义分类
    ├─ Step 4: 深入分析表结构
    ├─ Step 5: 提取实体关系
    └─ Step 6: 基于规则生成查询场景
    ↓
整合分析结果 → 生成训练数据集
    ↓
保存结果（JSON格式）
```

#### 2.3.2 ReAct 执行模式
```
对于每个分析步骤:
    ├─ Thought: 分析当前需要什么信息
    ├─ Action: 调用相应的分析工具
    ├─ Observation: 观察工具返回结果
    └─ 继续或进入下一步
```

## 3. 项目结构

```
semanticsql-agent/
├── agent/                      # 智能体核心模块
│   ├── __init__.py
│   ├── base_agent.py          # ReAct模式基础实现
│   └── smart_sql_agent.py     # SQL分析专用智能体
│
├── cli/                       # 命令行接口
│   ├── __init__.py
│   └── cli.py                 # CLI命令定义
│
├── config/                    # 配置管理
│   ├── __init__.py
│   └── trae_config.py         # 统一配置系统
│
├── database/                  # 数据库管理
│   ├── __init__.py
│   └── connection_manager.py  # 连接池管理
│
├── models/                    # 数据模型
│   ├── __init__.py
│   └── sql_result.py          # 查询结果模型
│
├── tools/                     # 工具集合
│   ├── __init__.py           # 工具注册
│   ├── trae_base_tool.py     # 工具基类
│   ├── agent_tools.py        # Agent工具
│   ├── sql_tools.py          # SQL工具
│   └── analysis_tools.py     # 分析工具
│
├── utils/                    # 工具类
│   ├── __init__.py
│   ├── trajectory_recorder.py # 轨迹记录
│   └── cli/                  # CLI工具
│
├── tests/                    # 测试
├── main.py                   # 程序入口
└── 配置文件和文档
```

## 4. 关键设计决策

### 4.1 规则驱动的场景生成
- 不完全依赖LLM生成
- 基于领域和表结构的规则
- 确保生成质量的可控性
- 提高生成效率

### 4.2 工具协同机制
- 工具之间通过共享上下文协作
- 后续工具可访问前序工具的结果
- 智能体协调工具执行顺序

### 4.3 质量控制
- 生成的SQL必须语法正确
- 问题描述自然、准确
- 场景覆盖全面
- 难度分布合理

## 5. 接口设计

### 5.1 CLI 接口
```bash
# 核心命令 - 智能分析
python main.py smart-analyze "全面分析数据库" \
    --config config.yaml \
    --save-result analysis_result.json \
    --verbose \
    --stage-by-stage

# 辅助命令
python main.py init        # 初始化配置
python main.py test        # 测试连接
python main.py schema      # 查看结构
python main.py run         # 单次查询
python main.py interactive # 交互模式
```

### 5.2 核心 API
```python
class SmartSQLAgent(BaseAgent):
    def smart_analyze(self, request: str) -> Dict[str, Any]:
        """执行完整的6步智能分析流程"""
        
    def _generate_final_result(self) -> Dict[str, Any]:
        """整合分析结果，生成最终的场景数据"""
```

### 5.3 分析结果格式
```json
{
    "success": true,
    "execution_time": 45.2,
    "steps_taken": 6,
    "final_result": {
        "database_connection": {
            "database": "testdb",
            "type": "mysql",
            "total_tables": 12
        },
        "domain_analysis": {
            "domain": "电子商务",
            "confidence": 0.92,
            "key_entities": ["用户", "订单", "商品"]
        },
        "field_classification": {
            "identifiers": ["user_id", "order_id"],
            "timestamps": ["created_at", "updated_at"],
            "amounts": ["price", "total_amount"]
        },
        "schema_analysis": {
            "core_tables": ["users", "orders", "products"],
            "relationships": [...]
        },
        "er_analysis": {
            "entities": [...],
            "relationships": [...]
        },
        "generated_scenarios": [
            {
                "id": "scenario_001",
                "category": "用户分析",
                "question": "查询最近30天内下单次数超过5次的活跃用户",
                "sql": "SELECT user_id, COUNT(*) as order_count FROM orders WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) GROUP BY user_id HAVING order_count > 5",
                "difficulty": "medium",
                "concepts": ["时间筛选", "分组", "Having条件"]
            }
        ]
    }
}
```

## 6. 场景生成策略

### 6.1 基于规则的生成
- 根据识别的领域应用相应规则
- 基于表结构生成合适的查询类型
- 考虑字段类型生成条件

### 6.2 场景类别
1. **基础查询**：单表简单查询
2. **聚合统计**：分组、计数、求和等
3. **多表关联**：JOIN查询
4. **时间相关**：基于时间的分析
5. **复杂分析**：子查询、窗口函数等

### 6.3 难度控制
- Easy: 单表、简单条件
- Medium: 多表、聚合函数
- Hard: 复杂JOIN、子查询

## 7. 扩展性设计

### 7.1 添加新工具
- 继承 TraeBaseTool
- 实现必要的方法
- 在工具注册中添加

### 7.2 支持新领域
- 添加领域识别规则
- 定制领域查询模板
- 扩展场景生成规则

### 7.3 支持新数据库
- 实现数据库方言适配
- 调整元数据提取
- 适配SQL语法差异

## 8. 质量保证

### 8.1 生成验证
- SQL语法检查
- 执行可行性验证
- 结果合理性评估

### 8.2 覆盖度保证
- 确保覆盖主要SQL特性
- 涵盖不同业务场景
- 平衡难度分布

## 9. 未来规划

### 9.1 功能增强
- 更智能的场景生成规则
- 支持更多SQL特性
- 自动化质量评估

### 9.2 性能优化
- 并行分析能力
- 缓存机制优化
- 大规模数据库支持

### 9.3 生态建设
- Web界面
- API服务化
- 与NL2SQL训练框架集成