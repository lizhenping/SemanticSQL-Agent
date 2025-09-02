# Pipelines层说明

## 职责定义

**Pipelines层**负责组件内部的细粒度流程管理，主要用于：

1. **组件内部的多步骤处理**
   - 例如：ER分析的三层处理（物理层→逻辑层→概念层）
   - 例如：描述生成的多步骤（生成→矫正→优化）

2. **可复用的处理流程**
   - 独立于LangGraph的轻量级流程
   - 可以被workflows调用，也可以独立使用

3. **Pipeline模式实现**
   - 基于`PipelineStep`抽象类
   - 支持步骤的串联执行
   - 每个步骤负责单一职责

## 与Workflows的区别

- **Workflows（LangGraph）**：顶层业务流程编排，管理状态流转
- **Pipelines（Pipeline模式）**：组件级别的处理流程，无状态管理

## 目录结构

```
pipelines/
├── base.py                    # Pipeline基础类
├── analysis/                  # 分析相关的内部流程
│   ├── er_analysis_pipeline.py       # ER三层分析流程
│   ├── field_classification_pipeline.py # 字段分类+熵计算流程
│   └── description_pipeline.py        # 描述生成流程
└── generation/                # 生成相关的内部流程（待添加）
```