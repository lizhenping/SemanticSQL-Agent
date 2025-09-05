# Models组织结构

基于Django/FastAPI的标准做法，采用功能域拆分和就近原则组织模型。

## 目录结构

```
models/
├── __init__.py      # 导出公用模型
├── base.py          # 基础类和枚举
├── database.py      # 数据库相关模型
├── agent.py         # Agent执行相关
├── analysis.py      # 分析结果模型
├── training.py      # 训练数据模型
├── execution.py     # SQL执行模型
└── exceptions.py    # 异常定义
```

## 设计原则

### 1. 功能域拆分
- 相关的模型放在同一个文件中
- 每个文件专注于一个功能域
- 文件名清晰表达其内容

### 2. 就近原则
- 工具特定的Input/Output模型定义在工具文件顶部
- 只有跨模块使用的模型才放在`models`目录
- 降低认知负担，一个文件看到完整逻辑

### 3. 公用模型管理
放在`models`目录的模型应满足：
- 被多个模块使用
- 代表核心业务概念
- 需要统一的数据格式

## 模型分类

### 基础模型 (base.py)
- `DifficultyLevel`: 难度级别枚举
- `SQLOperation`: SQL操作类型枚举
- `BaseToolInput/Output`: 工具IO基类

### 数据库模型 (database.py)
- `ColumnInfo`: 列信息
- `TableInfo`: 表信息
- `DatabaseSchema`: 数据库结构
- `TableRelationship`: 表关系

### Agent模型 (agent.py)
- `AgentStep`: 执行步骤
- `AgentExecution`: 执行记录
- `AgentStepType`: 步骤类型枚举

### 分析模型 (analysis.py)
- `DomainAnalysis`: 领域分析结果
- `FieldClassification`: 字段分类
- `ColumnMeaning`: 列含义
- `TableMeaning`: 表含义
- `ERRelation`: 实体关系

### 训练模型 (training.py)
- `GeneratedExample`: 生成的样本
- `TrainingExample`: 训练样本
- `TrainingDataResult`: 生成结果

### 执行模型 (execution.py)
- `ExecutionResult`: SQL执行结果
- `ValidationResult`: 验证结果
- `SQLQueryResult`: 查询结果

## 工具特定模型

以下模型定义在各自的工具文件中：

### 分析工具
- `SchemaExtractionInput` → schema_extraction_tool.py
- `DomainAnalysisInput` → domain_analysis_tool.py
- `FieldClassificationInput` → field_classification_tool.py
- `ColumnMeaningInput` → column_meaning_tool.py
- `TableMeaningInput` → table_meaning_tool.py
- `ERAnalysisInput` → er_analysis_tool.py

### 生成工具
- `ScenarioOperationInput` → scenario_operation_tool.py
- `QuestionGenerationInput` → question_generation_tool.py
- `GeneratedQuestion` → question_generation_tool.py
- `SQLGenerationInput` → sql_generation_tool.py
- `GeneratedSQL` → sql_generation_tool.py

### 验证工具
- `SQLValidationInput` → sql_validation_tool.py
- `SQLExecutionInput` → sql_execution_tool.py

### 反思工具
- `SQLReflectionInput` → sql_reflection_tool.py
- `ReflectionResult` → sql_reflection_tool.py

### 思考工具
- `SequentialThinkingInput` → sequential_thinking_tool.py

## 使用示例

### 导入公用模型
```python
from models import DifficultyLevel, DatabaseSchema, AgentExecution
from models.database import TableInfo
```

### 定义工具特定模型
```python
# 在tool文件顶部定义
from pydantic import BaseModel, Field

class MyToolInput(BaseModel):
    """工具输入"""
    param: str = Field(description="参数")

class MyToolOutput(BaseModel):
    """工具输出"""
    result: str = Field(description="结果")
```

## 最佳实践

1. **保持模型简洁**：每个模型只包含必要的字段
2. **使用Field描述**：为每个字段添加description
3. **提供默认值**：使用Field的default或default_factory
4. **类型注解**：使用typing模块提供准确的类型信息
5. **验证逻辑**：利用Pydantic的验证器确保数据正确性