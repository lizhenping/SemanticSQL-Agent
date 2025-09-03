# 更新日志

## [2024-01-17] - LLM 客户端规范化

### 删除
1. **冗余的 LLM 客户端**
   - 删除了 `utils/llm_client.py`（未使用）
   - 项目统一使用 LangChain 的 `ChatOpenAI`

### 新增
1. **Thinking 标签处理**（LangChain 标准实现）
   - `utils/thinking_parser.py` - 符合 LangChain 的输出解析器
   - `chains/thinking_chain.py` - 完整的思考链实现
   - 支持 LCEL 和多步思考链

### 文档
1. **LLM 使用规范**
   - 创建 `docs/LLM_USAGE.md` 说明统一使用 LangChain
   - 明确不使用直接的 OpenAI SDK

## [2024-01-16] - 系统清理和优化

### 改进
1. **系统提示词统一**
   - 删除了多余的系统提示词（agent_system.j2, main.j2）
   - 只保留main.j2（原main_flexible.j2）作为唯一系统提示词
   - 强化了必须执行的步骤说明

2. **文件清理**
   - 删除了所有临时测试文件
   - 删除了调试文件和文档
   - 清理了不再需要的辅助文件

3. **参数匹配修复**
   - 修复了工具参数定义与提示词调用的匹配问题
   - 恢复了args_schema的使用
   - 简化了参数处理逻辑

## [2024-01-15] - Memory Chain优化

### 改进
1. **Memory数据流优化**
   - 确保每个分析工具都正确使用前面步骤的记忆
   - domain_analysis: 增加了pattern_examples等统计信息传递给LLM
   - column_meaning: 增加了key_entities和business_characteristics上下文
   - field_classification: 修复了提示词模板格式，正确使用domain信息
   - 所有工具返回字典而非JSON字符串，方便memory存储和后续使用

2. **提示词模板更新**
   - field_classification.j2: 重写以匹配新的输入格式
   - column_description.j2: 添加了更多业务上下文（关键实体、业务特征）
   - 所有模板都确保使用前面步骤的分析结果

3. **文档完善**
   - 创建MEMORY_DATAFLOW.md详细说明每个工具的输入输出
   - 更新README.md简化说明
   - 创建MEMORY_CHAIN_EXAMPLE.md展示完整执行流程

4. **代码清理**
   - 删除了不必要的测试文件和文档
   - 修复了Agent中的memory传递机制
   - 确保所有工具正确初始化（传入llm和db_manager）

### 修复
- 修复了tools返回JSON字符串而非字典的问题
- 修复了base_agent.py中set_memory_reference方法名错误
- 修复了field_classification提示词模板格式问题

### 关键原则
- 每个分析步骤都基于前面所有步骤的结果
- LLM调用时传递完整的上下文信息
- 结构化输出便于后续工具使用
- 从技术信息逐步提升到业务语义理解