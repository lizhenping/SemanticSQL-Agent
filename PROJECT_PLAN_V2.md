# SemanticSQL-Agent 项目计划（简化版）

## 项目概览

**项目名称**: SemanticSQL-Agent  
**版本**: 0.1.0  
**目标**: 构建一个简单实用的 NL2SQL 智能体系统  
**作者**: 李振平 (lizhenping18@mails.ucas.ac.cn)

## 开发计划

### 第一阶段：基础框架（1-2周）

- [ ] 项目结构搭建
- [ ] 基础类型定义 (agent_basics.py)
- [ ] 工具框架 (tools/base.py)
- [ ] 数据库配置 (参考 nl2sql_pipeline)
- [ ] MySQL 服务实现

### 第二阶段：智能体核心（3-4周）

- [ ] BaseAgent 实现
- [ ] NL2SQLAgent 实现
- [ ] LLM 客户端 (OpenAI)
- [ ] 基础提示词设计

### 第三阶段：工具开发（5-6周）

- [ ] schema_extraction_tool
- [ ] initial_domain_analysis_tool  
- [ ] field_classification_tool
- [ ] table_description_tool
- [ ] column_description_tool
- [ ] er_analysis_tool
- [ ] scenario_generation_tool
- [ ] sql_generation_tool
- [ ] sequential_thinking_tool
- [ ] task_done_tool

### 第四阶段：整合测试（7-8周）

- [ ] 集成测试
- [ ] 命令行工具
- [ ] 使用文档
- [ ] 示例代码

## 技术选型

- **语言**: Python 3.11+
- **LLM**: OpenAI GPT-4
- **数据库**: MySQL
- **主要依赖**: pymysql, openai, pyyaml

## 设计原则

1. **简单优先**: 避免过度设计
2. **同步执行**: 不使用异步
3. **单一数据库**: 只支持 MySQL
4. **基础功能**: 专注核心 NL2SQL

## 不包含的功能

- 异步执行
- 并行工具调用
- 性能优化
- 监控系统
- 安全审查
- 国际化
- CI/CD
- Web界面

## 测试策略

- 单元测试：每个工具独立测试
- 集成测试：端到端流程测试
- 手动测试：实际数据库测试

## 交付标准

1. 可运行的 NL2SQL 系统
2. 支持常见 SQL 查询类型
3. 清晰的使用文档
4. 基础的错误处理

## 风险管理

1. **LLM API 稳定性**: 增加重试机制
2. **复杂查询准确性**: 逐步改进，从简单查询开始
3. **数据库兼容性**: 专注 MySQL，确保兼容性

## 里程碑

- **M1 (第4周)**: 基础框架完成，可提取 schema
- **M2 (第6周)**: 所有工具完成，可生成简单 SQL
- **M3 (第8周)**: 系统完整，文档齐全

## 后续规划

- 支持更多数据库类型
- 优化 SQL 生成质量
- 添加查询结果验证
- 构建测试数据集