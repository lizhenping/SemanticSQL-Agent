# SemanticSQL-Agent 架构设计文档

## 1. 项目概述

SemanticSQL-Agent 是一个基于 LangChain 和 TRAEAgent 设计理念的 NL2SQL 系统，参考 `nl2sql_pipeline` 的分析流程，实现高质量的自然语言到 SQL 转换。

### 1.1 核心特性
- 基于 LangChain 的 `create_react_agent` 构建
- 参考 TRAEAgent 的简洁架构设计
- 继承 `nl2sql_pipeline` 的分析流程
- Jinja2 提示词模板管理
- 结构化的执行轨迹记录

### 1.2 技术栈
- **LangChain**: 智能体框架
- **SQLAlchemy**: 数据库连接
- **Jinja2**: 提示词模板
- **Pydantic**: 数据验证
- **PyMySQL**: MySQL 连接

## 2. 架构层次设计

```
semanticsql-agent/
│
├── config/
│   ├── __init__.py
│   ├── settings.py              # 全局配置（参考 nl2sql_pipeline）
│   └── database.py              # 数据库配置
│
├── models/
│   ├── __init__.py
│   └── schemas.py               # Pydantic 模型定义
│
├── tools/
│   ├── __init__.py
│   ├── base.py                  # 工具基类
│   │
│   ├── analysis_tools/          # 分析工具（核心）
│   │   ├── __init__.py
│   │   ├── schema_extraction_tool.py    # 数据库结构提取
│   │   ├── domain_analysis_tool.py      # 领域分析
│   │   ├── field_classification_tool.py # 字段分类
│   │   └── er_analysis_tool.py          # 实体关系分析
│   │
│   ├── generation_tools/        # 生成工具
│   │   ├── __init__.py
│   │   └── sql_generation_tool.py       # SQL 生成
│   │
│   ├── validation_tools/        # 验证工具
│   │   ├── __init__.py
│   │   ├── sql_validation_tool.py       # SQL 验证
│   │   └── sql_execution_tool.py        # SQL 执行测试
│   │
│   └── thinking_tools/          # 思考工具（可选）
│       ├── __init__.py
│       └── sequential_thinking_tool.py   # 深度思考
│
├── prompts/
│   ├── __init__.py
│   ├── templates/               # Jinja2 模板
│   │   ├── system/             # 系统提示词
│   │   ├── tools/              # 工具描述
│   │   └── analysis/           # 分析提示词
│   └── manager.py               # 提示词管理器
│
├── agent/
│   ├── __init__.py
│   ├── sql_agent.py             # 主 SQL Agent
│   └── callbacks.py             # 轨迹记录回调
│
├── utils/
│   ├── __init__.py
│   ├── database.py              # 数据库连接管理
│   └── trajectory.py            # 轨迹记录
│
└── cli.py                       # 命令行接口
```

## 3. 核心组件设计

### 3.1 SQL Agent（基于 LangChain + TRAEAgent 理念）

```python
# agent/sql_agent.py
from langchain.agents import create_react_agent, AgentExecutor
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from typing import List, Dict, Any, Optional

class SemanticSQLAgent:
    """基于 LangChain 的 SQL Agent"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db = self._init_database()
        self.llm = self._init_llm()
        self.tools = self._create_tools()
        self.agent_executor = self._create_agent_executor()
    
    def _create_tools(self) -> List:
        """创建工具集合"""
        # 1. SQL 基础工具
        toolkit = SQLDatabaseToolkit(db=self.db, llm=self.llm)
        tools = toolkit.get_tools()
        
        # 2. 自定义分析工具
        from tools import create_analysis_tools
        tools.extend(create_analysis_tools(self.db, self.llm))
        
        # 3. 验证和执行工具
        from tools import create_validation_tools
        tools.extend(create_validation_tools(self.db))
        
        # 4. 思考工具（可选）
        if self.config.get("enable_thinking", True):
            from tools import create_thinking_tools
            tools.extend(create_thinking_tools(self.llm))
        
        return tools
    
    def query(self, question: str) -> Dict[str, Any]:
        """执行查询"""
        try:
            result = self.agent_executor.invoke({
                "input": question
            })
            
            return {
                "success": True,
                "question": question,
                "sql": self._extract_sql(result),
                "answer": result.get("output", ""),
                "execution_result": self._extract_execution_result(result)
            }
        except Exception as e:
            return {
                "success": False,
                "question": question,
                "error": str(e)
            }
```

### 3.2 工具设计（参考 TRAEAgent）

工具采用简洁设计，每个工具专注单一职责：

1. **分析工具**：理解数据库结构和业务领域
2. **生成工具**：生成 SQL 语句
3. **验证工具**：验证并执行 SQL
4. **思考工具**：处理复杂逻辑（可选）

### 3.3 执行流程

```
用户查询
    ↓
智能体分析
    ↓
工具调用序列：
1. schema_extraction → 获取相关表结构
2. domain_analysis → 理解业务含义
3. field_classification → 分类字段类型
4. sql_generation → 生成 SQL
5. sql_validation → 验证语法
6. sql_execution → 执行并获取结果
    ↓
返回结果
```

## 4. 配置管理（参考 nl2sql_pipeline）

```yaml
# config.yaml
model:
  name: "Qwen3-14B"
  provider: "openai"
  base_url: "http://192.168.200.216:9991/v1"
  temperature: 0.1

database:
  host: "192.168.200.216"
  port: 13306
  user: "testuser"
  password: "testpass"
  database: "testdb"

agent:
  max_iterations: 15
  enable_thinking: true
```

## 5. 主要特点

1. **简洁性**：遵循 TRAEAgent 的简洁设计理念
2. **模块化**：工具独立，易于扩展
3. **实用性**：专注 NL2SQL 核心功能
4. **可追踪**：完整的执行轨迹记录

## 6. 与 nl2sql_pipeline 的集成

保留 `nl2sql_pipeline` 的核心分析流程：
- 数据库结构分析
- 业务领域理解
- 字段类型分类
- 实体关系分析

同时采用 LangChain 的智能体框架，获得更好的工具协调能力。