# SemanticSQL Agent API 文档

欢迎使用 SemanticSQL Agent API 文档。本文档提供了系统所有模块的详细 API 说明。

## 📚 文档结构

### 综合文档
- [**SemanticSQL Agent API 手册**](./SemanticSQL-Agent-API手册.md) - 完整的 API 参考手册

### 模块文档

#### 1. Agent 模块
智能体核心实现，包括基础架构和具体实现。

- [BaseAgent 类 API 文档](./agent模块/BaseAgent类API文档.md) - 智能体基类
- [SmartSQLAgent 类 API 文档](./agent模块/SmartSQLAgent类API文档.md) - SQL 生成智能体
- [DataGenerationAgent 类 API 文档](./agent模块/DataGenerationAgent类API文档.md) - 数据生成智能体
- [回调系统 API 文档](./agent模块/回调系统API文档.md) - 执行监控和回调

#### 2. Models 模块
数据模型和异常定义。

- [数据模型 API 文档](./models模块/数据模型API文档.md) - 所有数据结构定义
- [异常类 API 文档](./models模块/异常类API文档.md) - 自定义异常体系

#### 3. Tools 模块
各种专门的工具实现。

- [BaseTool 基类 API 文档](./tools模块/BaseTool基类API文档.md) - 工具基类

##### 分析工具
- [SchemaExtractionTool 文档](./tools模块/分析工具/SchemaExtractionTool文档.md) - 数据库结构提取
- [DomainAnalysisTool 文档](./tools模块/分析工具/DomainAnalysisTool文档.md) - 业务领域分析

##### 生成工具
- [SQLGenerationTool 文档](./tools模块/生成工具/SQLGenerationTool文档.md) - SQL 生成

##### 验证工具
- [SQLValidationTool 文档](./tools模块/验证工具/SQLValidationTool文档.md) - SQL 验证
- [SQLExecutionTool 文档](./tools模块/验证工具/SQLExecutionTool文档.md) - SQL 执行

##### 反思工具
- [SQLReflectionTool 文档](./tools模块/反思工具/SQLReflectionTool文档.md) - SQL 反思优化

#### 4. Utils 模块
系统工具类。

- [DatabaseManager 文档](./utils模块/DatabaseManager文档.md) - 数据库管理
- [LLMClient 文档](./utils模块/LLMClient文档.md) - LLM 客户端
- [TrajectoryRecorder 文档](./utils模块/TrajectoryRecorder文档.md) - 轨迹记录

#### 5. Config 模块
配置管理。

- [Settings 配置文档](./config模块/Settings配置文档.md) - 全局配置
- [DatabaseConfig 配置文档](./config模块/DatabaseConfig配置文档.md) - 数据库配置

## 🚀 快速导航

### 按功能查找

**SQL 生成流程**
1. [数据库结构提取](./tools模块/分析工具/SchemaExtractionTool文档.md)
2. [领域分析](./tools模块/分析工具/DomainAnalysisTool文档.md)
3. [SQL 生成](./tools模块/生成工具/SQLGenerationTool文档.md)
4. [SQL 验证](./tools模块/验证工具/SQLValidationTool文档.md)
5. [SQL 执行](./tools模块/验证工具/SQLExecutionTool文档.md)
6. [结果反思](./tools模块/反思工具/SQLReflectionTool文档.md)

**系统配置**
1. [创建配置](./config模块/Settings配置文档.md)
2. [数据库连接](./config模块/DatabaseConfig配置文档.md)
3. [初始化智能体](./agent模块/SmartSQLAgent类API文档.md)

**扩展开发**
1. [创建新工具](./tools模块/BaseTool基类API文档.md)
2. [添加回调](./agent模块/回调系统API文档.md)
3. [自定义智能体](./agent模块/BaseAgent类API文档.md)

### 按使用场景查找

**基础使用**
- 开始使用：查看 [API 手册](./SemanticSQL-Agent-API手册.md) 的快速开始部分
- SQL 查询：使用 [SmartSQLAgent](./agent模块/SmartSQLAgent类API文档.md)
- 结果处理：查看 [数据模型](./models模块/数据模型API文档.md) 中的 SQLQueryResult

**高级功能**
- 训练数据生成：使用 [DataGenerationAgent](./agent模块/DataGenerationAgent类API文档.md)
- 执行监控：使用 [回调系统](./agent模块/回调系统API文档.md)
- 性能分析：使用 [TrajectoryRecorder](./utils模块/TrajectoryRecorder文档.md)

**故障排查**
- 错误处理：查看 [异常类](./models模块/异常类API文档.md)
- 日志配置：查看 [Settings 配置](./config模块/Settings配置文档.md)
- 数据库问题：查看 [DatabaseManager](./utils模块/DatabaseManager文档.md)

## 📖 阅读建议

1. **新手用户**：先阅读 [API 手册](./SemanticSQL-Agent-API手册.md) 了解整体架构
2. **开发者**：重点关注 [BaseAgent](./agent模块/BaseAgent类API文档.md) 和 [BaseTool](./tools模块/BaseTool基类API文档.md)
3. **运维人员**：关注 [配置文档](./config模块/) 和 [数据库管理](./utils模块/DatabaseManager文档.md)

## 🔄 更新说明

- 文档版本：2.0.0
- 最后更新：2024年
- 适用版本：SemanticSQL Agent v2.0.0

## 📝 反馈

如有任何问题或建议，请通过以下方式反馈：
- 提交 Issue
- 发送邮件
- 提交 PR

---

*本文档由 SemanticSQL Agent 团队维护*