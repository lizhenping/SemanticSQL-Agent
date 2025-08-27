# SemanticSQL-Agent 项目计划（LangChain & LangGraph 版本）

## 项目概览

**项目名称**: SemanticSQL-Agent  
**技术栈**: LangChain + LangGraph + MySQL  
**版本**: 0.1.0  
**作者**: 李振平 (lizhenping18@mails.ucas.ac.cn)

## 技术架构

- **工作流引擎**: LangGraph（状态管理和流程编排）
- **AI 框架**: LangChain（工具、提示词、输出解析）
- **LLM**: 支持 vLLM 服务（Qwen3-14B）
- **数据库**: MySQL（通过 LangChain SQL）
- **数据验证**: Pydantic v2

## 开发计划

### Phase 1: 基础架构（第1-2周）

#### 目标
建立基于 LangChain 和 LangGraph 的基础框架

#### 任务清单
- [ ] 项目结构搭建
- [ ] LangGraph 状态定义（TypedDict）
- [ ] Pydantic 模型设计（格式化输入输出）
- [ ] LangChain 工具基类
- [ ] 数据库连接器（基于 SQLDatabase）
- [ ] LLM 客户端配置（支持 vLLM）

#### 交付物
- 可运行的基础框架
- 状态流转演示
- 数据库连接测试

### Phase 2: 工具开发（第3-4周）

#### 目标
实现所有 LangChain 工具

#### 任务清单
- [ ] SchemaExtractionTool（使用 LangChain SQL）
- [ ] InitialDomainAnalysisTool
- [ ] FieldClassificationTool
- [ ] TableDescriptionTool
- [ ] ColumnDescriptionTool
- [ ] ERAnalysisTool
- [ ] ScenarioGenerationTool
- [ ] SQLGenerationTool
- [ ] 工具单元测试

#### 交付物
- 完整的工具集
- 工具使用示例
- 测试报告

### Phase 3: 提示词工程（第5周）

#### 目标
优化提示词模板和输出解析

#### 任务清单
- [ ] 提示词模板管理器（PromptTemplate）
- [ ] 各步骤提示词模板
- [ ] Few-shot 示例准备
- [ ] 输出解析器（PydanticOutputParser）
- [ ] SQL 专用解析器
- [ ] 错误修复解析器

#### 交付物
- 提示词模板库
- 解析器测试用例
- 提示词优化报告

### Phase 4: 工作流实现（第6-7周）

#### 目标
完成 LangGraph 工作流

#### 任务清单
- [ ] 工作流图定义
- [ ] 所有节点实现
- [ ] 状态转换逻辑
- [ ] 错误处理机制
- [ ] 内存管理（ConversationMemory）
- [ ] 执行追踪

#### 交付物
- 完整的工作流
- 流程可视化
- 性能测试结果

### Phase 5: 集成与优化（第8周）

#### 目标
系统集成和优化

#### 任务清单
- [ ] 主智能体类实现
- [ ] CLI 接口
- [ ] 批量处理支持
- [ ] 查询历史管理
- [ ] 配置管理优化
- [ ] 文档完善

#### 交付物
- 可用的 NL2SQL 系统
- 用户文档
- 部署指南

## 关键技术点

### LangChain 集成
1. **工具系统**
   - 继承 `BaseTool`
   - 使用 `args_schema` 定义参数
   - 实现 `_run` 方法

2. **提示词管理**
   - 使用 `ChatPromptTemplate`
   - 支持 `FewShotPromptTemplate`
   - Jinja2 模板集成

3. **输出解析**
   - `PydanticOutputParser` 为主
   - `OutputFixingParser` 修复错误
   - 自定义 SQL 解析器

### LangGraph 集成
1. **状态管理**
   - 使用 `TypedDict` 定义状态
   - 支持嵌套的复杂状态
   - 状态持久化

2. **节点设计**
   - 每个节点返回状态更新
   - 支持条件分支
   - 错误状态处理

3. **工作流编排**
   - 线性流程为主
   - 支持错误重试
   - 可视化调试

### 数据格式化
1. **输入格式化**
   - Pydantic 模型验证
   - 统一的请求格式
   - 参数默认值

2. **输出格式化**
   - 结构化的 SQL 结果
   - 执行步骤记录
   - 错误信息标准化

## 测试策略

### 单元测试
- 每个工具独立测试
- Mock LLM 响应
- 验证输出格式

### 集成测试
- 完整工作流测试
- 真实数据库测试
- 端到端场景测试

### 性能测试
- 响应时间测试
- Token 使用统计
- 并发处理能力

## 风险管理

### 技术风险
1. **LangGraph 稳定性**
   - 缓解：保持版本稳定，充分测试
   
2. **提示词效果**
   - 缓解：迭代优化，A/B 测试

3. **输出解析失败**
   - 缓解：多层解析策略，降级处理

### 项目风险
1. **复杂度控制**
   - 缓解：模块化设计，渐进式开发

2. **性能问题**
   - 缓解：缓存机制，优化提示词

## 里程碑

- **M1（第2周）**: 基础框架完成，可执行简单工作流
- **M2（第4周）**: 所有工具完成，可提取和分析 Schema
- **M3（第6周）**: 工作流完成，可生成简单 SQL
- **M4（第8周）**: 系统完成，支持复杂查询

## 成功标准

1. **功能完整性**
   - 支持常见 SQL 查询类型
   - 正确识别表关系
   - 生成语法正确的 SQL

2. **性能指标**
   - 平均响应时间 < 5秒
   - SQL 正确率 > 80%
   - 系统稳定性 > 95%

3. **用户体验**
   - 清晰的错误提示
   - 详细的执行日志
   - 友好的 CLI 界面

## 后续规划

1. **v0.2.0**
   - 支持更多数据库
   - 查询优化建议
   - Web UI

2. **v0.3.0**
   - 多轮对话支持
   - 查询意图理解
   - 自动纠错

3. **v1.0.0**
   - 生产级稳定性
   - 企业级功能
   - SaaS 部署