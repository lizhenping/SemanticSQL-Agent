# PromptManager API 文档

提示词管理器，管理和渲染所有提示词模板。

## 类定义

```python
from jinja2 import Environment, FileSystemLoader
from typing import Dict, Any, Optional
from semanticsql_agent.prompts.manager import PromptManager

class PromptManager:
    """
    提示词管理器
    
    使用 Jinja2 模板引擎管理所有提示词。
    
    Attributes:
        env: Jinja2 环境
        templates_dir: 模板目录路径
    """
```

## 构造函数

```python
def __init__(self, templates_dir: str = "prompts/templates"):
    """
    初始化提示词管理器
    
    Args:
        templates_dir: 模板目录路径
    
    Example:
        ```python
        manager = PromptManager()
        ```
    """
```

## 核心方法

### get_system_prompt

```python
def get_system_prompt(
    self,
    agent_type: str,
    **kwargs
) -> str:
    """
    获取系统提示词
    
    Args:
        agent_type: Agent 类型 (sql_agent)
        **kwargs: 模板变量
    
    Returns:
        str: 渲染后的系统提示词
    
    Example:
        ```python
        prompt = manager.get_system_prompt(
            "sql_agent",
            mode="query",
            database_type="MySQL"
        )
        ```
    """
```

### get_tool_prompt

```python
def get_tool_prompt(
    self,
    tool_name: str,
    **kwargs
) -> str:
    """
    获取工具提示词
    
    Args:
        tool_name: 工具名称
        **kwargs: 模板变量
    
    Returns:
        str: 渲染后的工具提示词
    """
```

### get_analysis_prompt

```python
def get_analysis_prompt(
    self,
    analysis_type: str,
    **kwargs
) -> str:
    """
    获取分析提示词
    
    Args:
        analysis_type: 分析类型
        **kwargs: 模板变量
    
    Returns:
        str: 渲染后的分析提示词
    """
```

## 模板结构

```
prompts/templates/
├── system/                 # 系统提示词
│   ├── sql_agent.j2       # SQL Agent 系统提示词
│   └── base_agent.j2      # 基础 Agent 提示词
│
├── tools/                  # 工具提示词
│   ├── schema_extraction.j2
│   ├── domain_analysis.j2
│   ├── sql_generation.j2
│   └── ...
│
└── analysis/              # 分析提示词
    ├── field_classification.j2
    ├── column_meaning.j2
    └── table_meaning.j2
```

## 模板语法

### 系统提示词模板示例
```jinja2
{# sql_agent.j2 #}
你是一个专业的 SQL 查询助手，专门帮助用户生成 {{ database_type }} 数据库的查询语句。

## 你的能力
1. 理解自然语言查询需求
2. 生成准确的 SQL 查询
3. 利用数据库分析结果优化查询

## 工作流程
{% if enable_reflection %}
1. 分析数据库结构
2. 理解用户问题
3. 生成 SQL 查询
4. 验证和反思结果
{% else %}
1. 分析数据库结构
2. 理解用户问题
3. 生成 SQL 查询
{% endif %}

## 注意事项
- 始终使用数据库分析结果中的准确表名和字段名
- 考虑查询性能
- 确保 SQL 语法正确
```

### 工具提示词模板示例
```jinja2
{# sql_generation.j2 #}
基于以下信息生成 SQL 查询：

问题：{{ question }}

数据库结构：
{{ schema_info | tojson(indent=2) }}

{% if domain_info %}
领域信息：
{{ domain_info | tojson(indent=2) }}
{% endif %}

要求：
1. 生成符合 MySQL 语法的 SQL
2. 使用正确的表名和字段名
3. 考虑性能优化

请生成 SQL 查询。
```

## 高级功能

### 自定义过滤器

```python
def register_filter(self, name: str, func):
    """
    注册自定义 Jinja2 过滤器
    
    Example:
        ```python
        def format_table_name(name):
            return f"`{name}`"
        
        manager.register_filter("table", format_table_name)
        
        # 在模板中使用
        # {{ table_name | table }}
        ```
    """
```

### 模板缓存

```python
def preload_templates(self):
    """
    预加载所有模板以提高性能
    """

def clear_cache(self):
    """
    清除模板缓存
    """
```

### 动态模板

```python
def render_string(self, template_str: str, **kwargs) -> str:
    """
    渲染字符串模板
    
    Args:
        template_str: 模板字符串
        **kwargs: 模板变量
    
    Returns:
        str: 渲染结果
    """
```

## 使用示例

### 基本使用
```python
# 创建管理器
manager = PromptManager()

# 获取系统提示词
system_prompt = manager.get_system_prompt(
    "sql_agent",
    database_type="MySQL",
    enable_reflection=True
)

# 获取工具提示词
tool_prompt = manager.get_tool_prompt(
    "sql_generation",
    question="查询订单总数",
    schema_info={"tables": ["orders"]}
)
```

### 自定义模板路径
```python
# 使用自定义模板目录
manager = PromptManager(templates_dir="./custom_prompts")

# 添加额外的模板目录
manager.add_template_dir("./shared_prompts")
```

### 模板继承
```jinja2
{# base_tool.j2 #}
{% block description %}
这是一个基础工具模板
{% endblock %}

{% block requirements %}
- 要求1
- 要求2
{% endblock %}

{# sql_generation.j2 #}
{% extends "base_tool.j2" %}

{% block description %}
SQL 生成工具
{% endblock %}
```

## 最佳实践

1. **模板组织**：按类型组织模板文件
2. **变量验证**：在渲染前验证必需变量
3. **默认值**：为可选变量提供默认值
4. **版本控制**：模板文件纳入版本控制

## 注意事项

1. 模板文件使用 UTF-8 编码
2. 支持 Jinja2 的所有特性
3. 模板变量自动转义
4. 可以包含条件逻辑和循环

---

相关文档：
- [SQLAgent API](../agent模块/SQLAgent-API.md)
- [工具 API](../tools模块/)