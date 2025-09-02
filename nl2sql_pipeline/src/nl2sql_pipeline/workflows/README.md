# Workflows层说明

## 职责定义

**Workflows层**负责使用LangGraph进行顶层业务流程编排，主要用于：

1. **端到端的业务流程**
   - 主流程：分析→生成→输出
   - 分析流程：8步数据库分析
   - 生成流程：5阶段问题生成

2. **状态管理**
   - 使用LangGraph的状态机制
   - 跟踪流程执行进度
   - 支持断点续传和回溯

3. **流程控制**
   - 条件分支
   - 并行执行
   - 错误处理和重试

## 与Pipelines的区别

- **Workflows（LangGraph）**：业务级别的流程编排，有状态管理
- **Pipelines（Pipeline模式）**：技术级别的处理流程，无状态

## 目录结构

```
workflows/
├── main_workflow.py              # 主工作流（分析+生成）
├── analysis_workflow.py          # 分析工作流（8步）
├── generation_workflow.py        # 旧生成工作流（已弃用）
└── scenario_generation_workflow.py # 新场景驱动生成工作流
```

## 使用方式

```python
# 创建并执行工作流
workflow = MainWorkflow(services)
result = workflow.execute({
    "database_name": "testdb",
    "target_count": 100
})
```