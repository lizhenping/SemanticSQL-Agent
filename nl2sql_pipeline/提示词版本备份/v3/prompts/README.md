# 提示词模板管理

本目录统一管理 NL2SQL Pipeline 项目中的所有提示词模板。

## 目录结构

```
prompts/
├── config.yaml              # 提示词配置文件
├── templates/              # 所有提示词模板
│   ├── analysis/          # 数据分析相关模板
│   │   ├── 02_domain_analysis_structured.j2   # 领域分析（结构化）
│   │   ├── 03_field_classification.j2         # 字段分类
│   │   ├── 04_column_description.j2           # 列描述生成
│   │   ├── 05_column_correction.j2            # 列描述修正
│   │   ├── 06_table_description.j2            # 表描述生成
│   │   ├── 07_domain_optimization.j2          # 领域优化
│   │   ├── 08_er_analysis.j2                  # 实体关系分析
│   │   ├── domain_expert_system.j2            # 领域专家系统
│   │   └── initial_domain_human.j2            # 初始领域分析（人工）
│   └── generation/        # 问题生成相关模板
│       └── question_generation.j2              # 问题生成模板
└── __init__.py

```

## 模板说明

### Analysis（分析）模板

1. **02_domain_analysis_structured.j2**
   - 用途：对数据库进行结构化的领域分析
   - 输入：数据库schema信息
   - 输出：结构化的领域分析结果

2. **03_field_classification.j2**
   - 用途：对数据库字段进行分类
   - 输入：表和列信息
   - 输出：字段的业务分类

3. **04_column_description.j2**
   - 用途：生成列的业务描述
   - 输入：列的基本信息和上下文
   - 输出：中文业务描述

4. **05_column_correction.j2**
   - 用途：修正和优化列描述
   - 输入：初始列描述
   - 输出：优化后的列描述

5. **06_table_description.j2**
   - 用途：生成表的业务描述
   - 输入：表结构和列信息
   - 输出：表的业务说明

6. **07_domain_optimization.j2**
   - 用途：优化领域模型
   - 输入：初始领域分析结果
   - 输出：优化后的领域模型

7. **08_er_analysis.j2**
   - 用途：分析实体关系
   - 输入：表结构和外键信息
   - 输出：实体关系图谱

### Generation（生成）模板

1. **question_generation.j2**
   - 用途：生成自然语言查询问题
   - 输入：场景、复杂度、数据库信息
   - 输出：符合要求的查询问题
   - 特点：包含复杂和专家级别的业务规则说明

## 使用方法

### 1. 通过 PromptService 使用

```python
from nl2sql_pipeline.services import PromptService

# 初始化服务
prompt_service = PromptService()

# 渲染模板
result = prompt_service.render_template(
    'analysis/02_domain_analysis_structured.j2',
    database_info=db_info,
    other_params=values
)
```

### 2. 直接在 Pipeline 中使用

```python
from jinja2 import Environment, FileSystemLoader

# 设置模板目录
template_dir = Path(__file__).parent / 'prompts/templates'
env = Environment(loader=FileSystemLoader(str(template_dir)))

# 加载并渲染模板
template = env.get_template('generation/question_generation.j2')
result = template.render(**context)
```

## 注意事项

1. 所有提示词模板必须使用 `.j2` 扩展名
2. 模板中使用 Jinja2 语法
3. 新增模板时请更新此 README
4. 模板命名应清晰表达其用途
5. 复杂的业务逻辑应在模板中详细说明

## 模板开发指南

1. **变量命名**：使用下划线分隔的小写字母
2. **条件判断**：使用 `{% if %}` 语法
3. **循环**：使用 `{% for %}` 语法
4. **注释**：使用 `{# 注释内容 #}`
5. **业务规则**：对于复杂级别，必须包含明确的评判标准