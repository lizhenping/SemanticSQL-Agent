# SemanticSQL Agent 设计规范

## 1. 项目概述

### 1.1 项目背景
SemanticSQL Agent 是一个基于大语言模型（LLM）的自然语言转 SQL 查询智能体。该项目专注于将中文自然语言查询转换为准确的 SQL 语句并执行，为非技术用户提供便捷的数据库查询能力。

### 1.2 设计理念
- **简单易用**：用户只需输入中文问题，无需了解 SQL 语法
- **工具化思维**：将 NL2SQL 任务分解为多个专业工具的协同工作
- **模型兼容**：基于 OpenAI API 标准，完美支持 Qwen 等兼容模型
- **实用优先**：专注核心功能，避免过度设计

### 1.3 核心特性
- 支持 Qwen 模型的 OpenAI 兼容 API（包括 Function Calling）
- 支持多种数据库（MySQL、PostgreSQL、SQLite）
- 基于 ReAct 模式的智能推理
- 灵活的 YAML 配置系统
- 完整的命令行界面

## 2. 系统架构设计

### 2.1 整体架构
```
┌─────────────────────────────────────────────────────────┐
│                      用户接口层                           │
│                   (CLI Interface)                        │
└────────────────────────┬────────────────────────────────┘
                        │
┌────────────────────────┴────────────────────────────────┐
│                     智能体层                              │
│                  (Agent Layer)                           │
│  ┌─────────────┐  ┌──────────────┐                     │
│  │  BaseAgent  │  │SmartSQLAgent │                     │
│  │  (ReAct基类)│  │ (SQL专用实现) │                     │
│  └─────────────┘  └──────────────┘                     │
└────────────────────────┬────────────────────────────────┘
                        │
┌────────────────────────┴────────────────────────────────┐
│                     工具层                                │
│                  (Tools Layer)                           │
│  ┌────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │数据库连接   │  │  模式分析     │  │  SQL生成      │  │
│  ├────────────┤  ├──────────────┤  ├───────────────┤  │
│  │SQL执行     │  │  领域分析     │  │  数据分析     │  │
│  └────────────┘  └──────────────┘  └───────────────┘  │
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

#### 2.2.1 智能体设计 (Agent Design)
- **BaseAgent**: ReAct 模式基础实现
  - 观察-思考-行动循环
  - 工具调用管理
  - 执行状态跟踪
  - LLM 交互接口

- **SmartSQLAgent**: SQL 查询专用智能体
  - 继承 BaseAgent 的 ReAct 能力
  - 集成 SQL 相关工具链
  - 返回结构化的查询结果
  - 智能错误处理

#### 2.2.2 工具系统设计 (Tool System)
- **工具基类** (TraeBaseTool)
  - 标准化的工具接口
  - 参数定义（ToolParameter）
  - 统一的执行方法
  
- **SQL 工具集**:
  1. **连接管理**: `connect_database` - 建立数据库连接
  2. **模式分析**: `analyze_schema` - 分析表结构和关系
  3. **SQL生成**: `generate_sql` - 将自然语言转换为 SQL
  4. **查询执行**: `execute_sql` - 执行 SQL 并返回结果
  5. **领域分析**: `analyze_domain` - 理解业务领域

#### 2.2.3 LLM 集成设计
- **Qwen 模型支持**:
  - 完全兼容 OpenAI API 格式
  - 支持 Function Calling（工具调用）
  - 流式响应支持（可选）
  - 自定义 base_url 配置

- **Function Calling 实现**:
  ```python
  # 工具定义格式
  {
      "type": "function",
      "function": {
          "name": "execute_sql",
          "description": "执行SQL查询",
          "parameters": {
              "type": "object",
              "properties": {
                  "sql": {"type": "string", "description": "要执行的SQL语句"}
              },
              "required": ["sql"]
          }
      }
  }
  ```

### 2.3 数据流设计

#### 2.3.1 查询处理流程
```
用户输入中文查询
    ↓
CLI 接收并解析 → 加载配置 → 初始化 Agent
    ↓
连接数据库 → 分析表结构 → 缓存模式信息
    ↓
ReAct 执行循环:
    ├─ Thought: 理解查询需求
    ├─ Action: 调用合适的工具
    ├─ Observation: 观察执行结果
    └─ 继续或完成
    ↓
格式化结果 → 返回给用户
```

#### 2.3.2 Function Calling 流程
```
Agent 发送消息给 LLM
    ↓
LLM 返回 function_call
    ↓
解析函数名和参数 → 验证参数合法性
    ↓
调用对应工具执行 → 获取执行结果
    ↓
将结果作为 function response 发送给 LLM
    ↓
LLM 生成最终回复
```

## 3. 关键设计决策

### 3.1 模型选择
- 使用 Qwen 系列模型（如 Qwen3-14B）
- 通过 OpenAI 兼容 API 调用
- 支持本地部署和云端 API

### 3.2 工具设计原则
- 每个工具专注单一职责
- 工具之间松耦合
- 参数和返回值标准化
- 错误信息友好明确

### 3.3 配置管理
- 使用 YAML 格式，易读易写
- 支持环境变量覆盖
- 敏感信息（如密码）支持加密存储

## 4. 接口设计

### 4.1 CLI 接口
```bash
# 初始化配置
python main.py init --model Qwen3-14B --base-url http://localhost:9009/v1

# 执行查询
python main.py run "查询所有用户的数量"

# 交互模式
python main.py interactive

# 测试连接
python main.py test

# 查看数据库结构
python main.py schema
```

### 4.2 核心 API
```python
# Agent 接口
class SmartSQLAgent:
    def query(self, question: str) -> SQLQueryResult:
        """执行自然语言查询"""
        pass

# 工具接口
class TraeBaseTool:
    def get_parameters(self) -> List[ToolParameter]:
        """获取工具参数定义"""
        pass
    
    def run(self, **kwargs) -> Dict[str, Any]:
        """执行工具"""
        pass
```

### 4.3 配置格式
```yaml
# 应用配置
app:
  name: "SemanticSQL Agent"
  version: "2.0.0"
  environment: "production"

# 数据库配置
database:
  type: "mysql"
  host: "192.168.200.216"
  port: 13306
  database: "testdb"
  username: "testuser"
  password: "testpass"

# LLM 配置
llm:
  model: "Qwen3-14B"
  base_url: "http://192.168.200.216:9009/v1"
  api_key: "not-needed"  # Qwen 本地部署可能不需要
  temperature: 0.1
  max_tokens: 2000
```

## 5. 扩展性设计

### 5.1 添加新工具
```python
# 1. 继承 TraeBaseTool
class MyCustomTool(TraeBaseTool):
    def __init__(self):
        super().__init__(
            name="my_tool",
            description="自定义工具描述"
        )
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(name="param1", type="string", required=True)
        ]
    
    def run(self, **kwargs) -> Dict[str, Any]:
        # 实现工具逻辑
        return {"success": True, "result": "..."}

# 2. 注册到工具列表
AVAILABLE_TOOLS.append(MyCustomTool)
```

### 5.2 支持新数据库
- 实现数据库方言适配器
- 添加对应的连接驱动
- 更新配置验证逻辑

## 6. 部署方案

### 6.1 本地部署
```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置数据库和 LLM
python main.py init

# 3. 运行服务
python main.py interactive
```

### 6.2 Docker 部署
```dockerfile
FROM python:3.8-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "main.py", "interactive"]
```

## 7. 性能考虑

### 7.1 优化策略
- 数据库模式缓存，避免重复查询
- 连接池管理，复用数据库连接
- 合理的 LLM 参数设置（temperature、max_tokens）

### 7.2 资源限制
- 单次查询超时控制
- 结果集大小限制
- 并发请求限制

## 8. 安全设计

### 8.1 查询安全
- SQL 注入防护
- 只允许 SELECT 查询（可配置）
- 敏感表/字段访问控制

### 8.2 配置安全
- 密码加密存储
- API Key 环境变量管理
- 访问日志记录

## 9. 未来规划

### 9.1 功能增强
- 支持更复杂的多表查询
- 查询结果可视化
- 查询历史和收藏

### 9.2 模型优化
- 针对特定领域的 Prompt 优化
- Few-shot 示例管理
- 查询意图分类

### 9.3 生态集成
- REST API 服务化
- Jupyter Notebook 插件
- 数据分析平台集成