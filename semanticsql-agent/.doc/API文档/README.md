# SemanticSQL Agent API 文档

基于 LangChain 框架的智能 SQL 生成系统 API 文档。

## 📚 文档结构

### 核心文档
- [**API 总览**](./API总览.md) - 系统架构和快速开始指南
- [**LangChain 集成指南**](./LangChain集成指南.md) - 如何使用 LangChain 组件

### 模块文档

#### 1. Agent 模块（基于 LangChain）
智能体核心实现，使用 LangChain AgentExecutor。

- [BaseAgent API](./agent模块/BaseAgent-API.md) - 基于 LangChain 的智能体基类
- [SQLAgent API](./agent模块/SQLAgent-API.md) - SQL 生成智能体（支持单次查询和批量生成）
- [记忆管理 API](./agent模块/记忆管理-API.md) - 基于 LangChain Memory 的数据库分析记忆

#### 2. Tools 模块（基于 LangChain Tools）
所有工具继承自 `langchain.tools.BaseTool`。

##### 分析工具
- [SchemaExtractionTool](./tools模块/分析工具/SchemaExtractionTool.md) - 数据库结构提取
- [DomainAnalysisTool](./tools模块/分析工具/DomainAnalysisTool.md) - 业务领域分析
- [FieldClassificationTool](./tools模块/分析工具/FieldClassificationTool.md) - 字段语义分类
- [ColumnMeaningTool](./tools模块/分析工具/ColumnMeaningTool.md) - 列业务含义分析
- [TableMeaningTool](./tools模块/分析工具/TableMeaningTool.md) - 表业务含义分析
- [ERAnalysisTool](./tools模块/分析工具/ERAnalysisTool.md) - 实体关系分析

##### 生成工具
- [ScenarioTool](./tools模块/生成工具/ScenarioTool.md) - 场景生成（基于预定义模板）
- [OperationSelectionTool](./tools模块/生成工具/OperationSelectionTool.md) - SQL操作选择
- [QuestionGenerationTool](./tools模块/生成工具/QuestionGenerationTool.md) - 自然语言问题生成
- [SQLGenerationTool](./tools模块/生成工具/SQLGenerationTool.md) - SQL 查询生成

##### 验证工具
- [SQLValidationTool](./tools模块/验证工具/SQLValidationTool.md) - SQL 语法验证
- [SQLExecutionTool](./tools模块/验证工具/SQLExecutionTool.md) - SQL 执行测试

##### 反思工具
- [SQLReflectionTool](./tools模块/反思工具/SQLReflectionTool.md) - SQL 执行结果反思

##### 思考工具
- [SequentialThinkingTool](./tools模块/思考工具/SequentialThinkingTool.md) - 深度思考和问题分析

#### 3. Models 模块
数据模型定义（Pydantic）。

- [数据模型](./models模块/数据模型.md) - 所有数据结构定义
- [异常定义](./models模块/异常定义.md) - 自定义异常类

#### 4. Utils 模块
系统工具类。

- [DatabaseManager](./utils模块/DatabaseManager.md) - MySQL 数据库管理
- [LLMClient](./utils模块/LLMClient.md) - 基于 LangChain 的 LLM 客户端
- [TrajectoryRecorder](./utils模块/TrajectoryRecorder.md) - 执行轨迹记录
- [Callbacks](./utils模块/Callbacks.md) - LangChain 回调处理器

#### 5. Config 模块
配置管理。

- [Settings](./config模块/Settings.md) - 全局配置（基于 Pydantic）
- [DatabaseConfig](./config模块/DatabaseConfig.md) - MySQL 数据库配置

#### 6. Prompts 模块
提示词管理（基于 LangChain）。

- [PromptTemplates](./prompts模块/PromptTemplates.md) - LangChain 提示词模板
- [SystemPrompts](./prompts模块/SystemPrompts.md) - 系统提示词配置

## 🚀 快速导航

### 核心流程

**1. 初始化系统**
```python
from semanticsql_agent import SQLAgent
from langchain.callbacks import StdOutCallbackHandler

# 创建 Agent
agent = SQLAgent(
    config=config,
    callbacks=[StdOutCallbackHandler()]
)
```

**2. 数据库分析流程**
1. [提取数据库结构](./tools模块/分析工具/SchemaExtractionTool.md)
2. [识别业务领域](./tools模块/分析工具/DomainAnalysisTool.md)
3. [字段分类](./tools模块/分析工具/FieldClassificationTool.md)
4. [列含义分析](./tools模块/分析工具/ColumnMeaningTool.md)
5. [表含义分析](./tools模块/分析工具/TableMeaningTool.md)
6. [关系分析](./tools模块/分析工具/ERAnalysisTool.md)

**3. SQL 生成流程**
1. [场景生成](./tools模块/生成工具/ScenarioTool.md)
2. [操作选择](./tools模块/生成工具/OperationSelectionTool.md)
3. [问题生成](./tools模块/生成工具/QuestionGenerationTool.md)
4. [SQL 生成](./tools模块/生成工具/SQLGenerationTool.md)
5. [验证执行](./tools模块/验证工具/SQLValidationTool.md)
6. [反思优化](./tools模块/反思工具/SQLReflectionTool.md)

### 使用场景

**单次查询**
```python
response = agent.query("查询最近一周的销售额")
print(response.sql)
```

**批量生成训练数据**
```python
result = agent.generate_training_data(
    count=100,
    output_file="training_data.json"
)
```

**自定义工具开发**
- 继承 `langchain.tools.BaseTool`
- 实现 `_run` 方法
- 定义输入参数模式

## 📖 阅读建议

1. **新手用户**：先阅读 [API 总览](./API总览.md) 了解整体架构
2. **开发者**：重点关注 [LangChain 集成指南](./LangChain集成指南.md)
3. **工具开发**：参考各工具的 API 文档和 LangChain 文档

## 🔄 版本信息

- 文档版本：3.0.0
- 最后更新：2024-12
- 框架版本：基于 LangChain 0.1.x

## 📝 注意事项

1. 所有工具都基于 LangChain 的 `BaseTool`
2. 使用 LangChain 的 Memory 系统管理数据库分析结果
3. Agent 执行基于 `AgentExecutor`
4. 支持 LangChain 的回调和调试功能

---

*本文档基于 LangChain 框架设计*