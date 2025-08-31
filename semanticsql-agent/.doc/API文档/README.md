# SemanticSQL Agent API 文档

基于 LangChain 框架的智能 SQL 生成系统 API 文档。

## 📚 文档结构

### 核心文档
- [**API 总览**](./API总览.md) - 系统架构和快速开始指南
- [**LangChain 集成指南**](./LangChain集成指南.md) - 如何使用 LangChain 组件
- [**CLI 使用指南**](./CLI-API.md) - 命令行接口文档

### 模块文档

#### 1. Agent 模块（基于 LangChain）
智能体核心实现，使用 LangChain AgentExecutor。

- [BaseAgent API](./agent模块/BaseAgent-API.md) - 基于 LangChain 的智能体基类
- [SQLAgent API](./agent模块/SQLAgent-API.md) - SQL 查询生成智能体
- [记忆管理 API](./agent模块/记忆管理-API.md) - 基于 LangChain Memory 的数据库分析记忆

#### 2. Tools 模块（基于 LangChain Tools）
所有工具继承自 `langchain.tools.BaseTool`。

##### 分析工具（6个）
- [SchemaExtractionTool](./tools模块/分析工具/SchemaExtractionTool.md) - 数据库结构提取
- [DomainAnalysisTool](./tools模块/分析工具/DomainAnalysisTool.md) - 业务领域分析
- [FieldClassificationTool](./tools模块/分析工具/FieldClassificationTool.md) - 字段语义分类
- [ColumnMeaningTool](./tools模块/分析工具/ColumnMeaningTool.md) - 列业务含义分析
- [TableMeaningTool](./tools模块/分析工具/TableMeaningTool.md) - 表业务含义分析
- [ERAnalysisTool](./tools模块/分析工具/ERAnalysisTool.md) - 实体关系分析

##### 生成工具（4个）
- [ScenarioTool](./tools模块/生成工具/ScenarioTool.md) - 场景生成（基于预定义模板）
- [OperationSelectionTool](./tools模块/生成工具/OperationSelectionTool.md) - SQL操作选择
- [QuestionGenerationTool](./tools模块/生成工具/QuestionGenerationTool.md) - 自然语言问题生成
- [SQLGenerationTool](./tools模块/生成工具/SQLGenerationTool.md) - SQL 查询生成

##### 验证工具（2个）
- [SQLValidationTool](./tools模块/验证工具/SQLValidationTool.md) - SQL 语法验证
- [SQLExecutionTool](./tools模块/验证工具/SQLExecutionTool.md) - SQL 执行测试

##### 反思工具（1个）
- [SQLReflectionTool](./tools模块/反思工具/SQLReflectionTool.md) - SQL 执行结果反思

##### 思考工具（1个）
- [SequentialThinkingTool](./tools模块/思考工具/SequentialThinkingTool.md) - 深度思考和问题分析

#### 3. Prompts 模块
提示词管理系统（基于 Jinja2）。

- [PromptManager API](./prompts模块/PromptManager-API.md) - 提示词管理器

#### 4. Utils 模块
系统工具类。

- [DatabaseManager](./utils模块/DatabaseManager-API.md) - MySQL 数据库管理
- [LLMClient](./utils模块/LLMClient-API.md) - 基于 LangChain 的 LLM 客户端
- [MemoryManager](./utils模块/MemoryManager-API.md) - 记忆管理工具
- [TrajectoryRecorder](./utils模块/TrajectoryRecorder-API.md) - 执行轨迹记录
- [CallbackHandler](./utils模块/CallbackHandler-API.md) - LangChain 回调处理器

#### 5. Config 模块
配置管理（基于 Pydantic）。

- [Settings](./config模块/Settings-API.md) - 全局配置
- [DatabaseConfig](./config模块/DatabaseConfig-API.md) - MySQL 数据库配置

#### 6. Models 模块
数据模型定义（Pydantic）。

- [数据模型](./models模块/数据模型.md) - 所有数据结构定义

## 🚀 快速导航

### 核心流程

**1. 初始化系统**
```python
from semanticsql_agent.agent import SQLAgent
from semanticsql_agent.config import Settings, DatabaseConfig

# 配置
settings = Settings()
db_config = DatabaseConfig(
    host="localhost",
    database="ecommerce",
    username="root",
    password="password"
)

# 创建 Agent
agent = SQLAgent(settings, db_config)
```

**2. 数据库分析流程**
1. [提取数据库结构](./tools模块/分析工具/SchemaExtractionTool.md)
2. [识别业务领域](./tools模块/分析工具/DomainAnalysisTool.md)
3. [字段分类](./tools模块/分析工具/FieldClassificationTool.md)
4. [列含义分析](./tools模块/分析工具/ColumnMeaningTool.md)
5. [表含义分析](./tools模块/分析工具/TableMeaningTool.md)
6. [关系分析](./tools模块/分析工具/ERAnalysisTool.md)

**3. SQL 生成流程**
1. 接收自然语言问题
2. 利用数据库分析记忆
3. [生成 SQL 查询](./tools模块/生成工具/SQLGenerationTool.md)
4. [验证 SQL](./tools模块/验证工具/SQLValidationTool.md)
5. [执行测试](./tools模块/验证工具/SQLExecutionTool.md)
6. [反思优化](./tools模块/反思工具/SQLReflectionTool.md)

### 使用场景

**单次查询**
```python
result = agent.query("查询最近一周的销售额")
print(f"SQL: {result.sql}")
print(f"结果: {result.result}")
```

**命令行使用**
```bash
# 查询
semanticsql query -q "查询订单总数" -d ecommerce -u root

# 数据库分析
semanticsql analyze -d ecommerce -u root -o analysis.json
```

**自定义工具开发**
- 继承 `langchain.tools.BaseTool`
- 实现 `_run` 方法
- 定义输入参数模式

## 📖 阅读建议

1. **新手用户**：先阅读 [API 总览](./API总览.md) 了解整体架构
2. **开发者**：重点关注 [LangChain 集成指南](./LangChain集成指南.md)
3. **工具开发**：参考各工具的 API 文档和 LangChain 文档
4. **命令行用户**：查看 [CLI 使用指南](./CLI-API.md)

## 🔄 版本信息

- 文档版本：1.0.0
- 最后更新：2024-01
- 框架版本：基于 LangChain 0.1.x

## 📝 注意事项

1. 所有工具都基于 LangChain 的 `BaseTool`
2. 使用 LangChain 的 Memory 系统管理数据库分析结果
3. Agent 执行基于 `AgentExecutor`
4. 仅支持 MySQL 数据库
5. 支持 LangChain 的回调和调试功能

---

*本文档严格遵循项目架构设计*