# SemanticSQL-Agent 设计规范

## 1. 数据模型

### 1.1 核心模型（Pydantic）

```python
# models/schemas.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum

class FieldType(str, Enum):
    """字段类型"""
    DIMENSION = "dimension"
    MEASURE = "measure"
    IDENTIFIER = "identifier"
    TIMESTAMP = "timestamp"
    DESCRIPTION = "description"

class TableInfo(BaseModel):
    """表信息"""
    name: str
    columns: List[Dict[str, Any]]
    row_count: Optional[int] = None
    comment: Optional[str] = None

class DomainAnalysis(BaseModel):
    """领域分析结果"""
    domain: str
    key_entities: List[str]
    business_rules: List[str]

class QueryResult(BaseModel):
    """查询结果"""
    success: bool
    sql: Optional[str] = None
    result: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    row_count: int = 0
```

## 2. 工具实现规范

### 2.1 基础工具类

```python
# tools/base.py
from langchain.tools import BaseTool
from typing import Type, Any
from abc import abstractmethod

class BaseSemanticSQLTool(BaseTool):
    """工具基类"""
    
    def _run(self, *args, **kwargs) -> str:
        """执行工具"""
        try:
            result = self.execute(**kwargs)
            return self._format_output(result)
        except Exception as e:
            return f"工具执行失败: {str(e)}"
    
    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """具体执行逻辑"""
        pass
    
    def _format_output(self, result: Any) -> str:
        """格式化输出"""
        if isinstance(result, str):
            return result
        elif isinstance(result, dict):
            return self._dict_to_string(result)
        else:
            return str(result)
```

### 2.2 分析工具

```python
# tools/analysis_tools/schema_extraction_tool.py
class SchemaExtractionTool(BaseSemanticSQLTool):
    """数据库结构提取工具"""
    
    name = "extract_database_schema"
    description = "提取数据库表结构信息，包括表、列、数据类型等"
    
    def execute(self, tables: List[str] = None) -> Dict[str, Any]:
        """提取 schema"""
        if not tables:
            tables = self.db.get_usable_table_names()
        
        result = {}
        for table in tables:
            table_info = self.db.get_table_info_no_throw([table])
            result[table] = {
                "ddl": table_info,
                "sample_data": self._get_sample_data(table)
            }
        
        return result

# tools/analysis_tools/domain_analysis_tool.py
class DomainAnalysisTool(BaseSemanticSQLTool):
    """业务领域分析工具"""
    
    name = "analyze_business_domain"
    description = "分析数据库的业务领域，识别关键实体和业务规则"
    
    def execute(self, schema_info: Dict[str, Any]) -> Dict[str, Any]:
        """分析业务领域"""
        prompt = self._build_analysis_prompt(schema_info)
        response = self.llm.invoke(prompt)
        
        # 解析响应
        return self._parse_domain_analysis(response.content)
```

### 2.3 生成工具

```python
# tools/generation_tools/sql_generation_tool.py
class SQLGenerationTool(BaseSemanticSQLTool):
    """SQL 生成工具"""
    
    name = "generate_sql"
    description = "基于分析结果生成 SQL 查询语句"
    
    def execute(
        self, 
        query: str,
        schema: Dict[str, Any],
        domain_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """生成 SQL"""
        # 使用 Jinja2 模板构建提示词
        from prompts.manager import PromptManager
        pm = PromptManager()
        
        prompt = pm.get_prompt(
            "sql_generation",
            query=query,
            schema=schema,
            domain=domain_info
        )
        
        # 调用 LLM 生成 SQL
        response = self.llm.invoke(prompt)
        sql = self._extract_sql_from_response(response.content)
        
        return sql
```

### 2.4 验证工具

```python
# tools/validation_tools/sql_validation_tool.py
class SQLValidationTool(BaseSemanticSQLTool):
    """SQL 验证工具"""
    
    name = "validate_sql"
    description = "验证 SQL 语句的语法正确性"
    
    def execute(self, sql: str) -> Dict[str, Any]:
        """验证 SQL"""
        try:
            # 使用 EXPLAIN 验证语法
            self.db.run(f"EXPLAIN {sql}")
            return {
                "valid": True,
                "message": "SQL 语法正确"
            }
        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
                "message": "SQL 语法错误"
            }

# tools/validation_tools/sql_execution_tool.py
class SQLExecutionTool(BaseSemanticSQLTool):
    """SQL 执行工具"""
    
    name = "execute_sql"
    description = "执行 SQL 查询并返回结果"
    
    def execute(self, sql: str, limit: int = 10) -> Dict[str, Any]:
        """执行 SQL"""
        try:
            # 添加 LIMIT 限制
            if limit and 'LIMIT' not in sql.upper():
                sql = f"{sql.rstrip(';')} LIMIT {limit}"
            
            # 执行查询
            result = self.db.run(sql)
            
            # 解析结果
            rows = self._parse_result(result)
            
            return {
                "success": True,
                "rows": rows,
                "row_count": len(rows),
                "sql": sql
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "sql": sql
            }
```

## 3. 提示词管理

### 3.1 提示词管理器

```python
# prompts/manager.py
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import yaml

class PromptManager:
    """Jinja2 提示词管理器"""
    
    def __init__(self):
        self.template_dir = Path(__file__).parent / "templates"
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            trim_blocks=True,
            lstrip_blocks=True
        )
    
    def get_prompt(self, template_name: str, **kwargs) -> str:
        """获取渲染后的提示词"""
        template = self.env.get_template(f"{template_name}.j2")
        return template.render(**kwargs)
```

### 3.2 提示词模板示例

```jinja2
{# prompts/templates/sql_generation.j2 #}
## 任务：生成 SQL 查询

用户查询：{{ query }}

### 数据库结构
{% for table, info in schema.items() %}
表：{{ table }}
{{ info.ddl }}
{% endfor %}

{% if domain %}
### 业务领域信息
- 领域：{{ domain.domain }}
- 关键实体：{{ domain.key_entities | join(', ') }}
{% endif %}

### 要求
1. 生成准确的 SQL 查询
2. 只使用存在的表和列
3. 考虑性能，避免 SELECT *
4. 添加适当的 LIMIT 限制

请生成 SQL：
```

## 4. 回调实现

### 4.1 轨迹记录回调

```python
# agent/callbacks.py
from langchain.callbacks.base import BaseCallbackHandler
from typing import Dict, Any, List
from datetime import datetime

class TrajectoryCallback(BaseCallbackHandler):
    """轨迹记录回调"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """重置轨迹"""
        self.trajectory = {
            "start_time": datetime.now().isoformat(),
            "steps": [],
            "tool_calls": []
        }
    
    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs):
        """工具开始执行"""
        self.trajectory["tool_calls"].append({
            "timestamp": datetime.now().isoformat(),
            "tool": serialized.get("name", "unknown"),
            "input": input_str
        })
    
    def on_tool_end(self, output: str, **kwargs):
        """工具执行结束"""
        if self.trajectory["tool_calls"]:
            self.trajectory["tool_calls"][-1]["output"] = output[:500]
            
            # 特殊处理：SQL 执行结果
            if "execute_sql" in self.trajectory["tool_calls"][-1]["tool"]:
                self._handle_sql_execution(output)
    
    def _handle_sql_execution(self, output: str):
        """处理 SQL 执行结果"""
        # 这里可以提取执行结果
        import json
        try:
            result = json.loads(output)
            if result.get("success"):
                self.trajectory["sql_result"] = {
                    "row_count": result.get("row_count", 0),
                    "preview": result.get("rows", [])[:5]
                }
        except:
            pass
```

## 5. 主程序实现

```python
# agent/sql_agent.py
from langchain.agents import create_react_agent, AgentExecutor
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain.chat_models import init_chat_model
from typing import Dict, Any, Optional

class SemanticSQLAgent:
    """SQL 智能体"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db = self._init_database()
        self.llm = self._init_llm()
        self.tools = self._create_tools()
        self.trajectory_callback = TrajectoryCallback()
        self.agent_executor = self._create_agent_executor()
    
    def _init_database(self) -> SQLDatabase:
        """初始化数据库"""
        db_config = self.config["database"]
        uri = (
            f"mysql+pymysql://{db_config['user']}:{db_config['password']}@"
            f"{db_config['host']}:{db_config['port']}/{db_config['database']}"
        )
        return SQLDatabase.from_uri(uri)
    
    def _init_llm(self):
        """初始化 LLM"""
        model_config = self.config["model"]
        return init_chat_model(
            model_config["name"],
            model_provider=model_config.get("provider", "openai"),
            base_url=model_config.get("base_url"),
            temperature=model_config.get("temperature", 0.1)
        )
    
    def _create_agent_executor(self) -> AgentExecutor:
        """创建智能体执行器"""
        # 系统提示词
        from prompts.manager import PromptManager
        pm = PromptManager()
        system_prompt = pm.get_prompt("system/sql_agent", 
            tables=self.db.get_usable_table_names()
        )
        
        # 创建 agent
        agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=system_prompt
        )
        
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            max_iterations=self.config["agent"].get("max_iterations", 15),
            callbacks=[self.trajectory_callback]
        )
    
    def query(self, question: str) -> Dict[str, Any]:
        """执行查询"""
        self.trajectory_callback.reset()
        
        try:
            result = self.agent_executor.invoke({"input": question})
            
            # 提取 SQL 和执行结果
            trajectory = self.trajectory_callback.trajectory
            sql = self._extract_sql(result)
            execution_result = trajectory.get("sql_result")
            
            return {
                "success": True,
                "question": question,
                "sql": sql,
                "answer": result.get("output", ""),
                "execution_result": execution_result,
                "steps": len(trajectory["tool_calls"])
            }
            
        except Exception as e:
            raise e  # 直接抛出异常，不做降级处理
```

## 6. 使用示例

```python
# 基础使用
from agent.sql_agent import SemanticSQLAgent
import yaml

# 加载配置
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# 创建 agent
agent = SemanticSQLAgent(config)

# 执行查询
result = agent.query("查询每个部门的平均工资")

if result["success"]:
    print(f"SQL: {result['sql']}")
    print(f"结果: {result['answer']}")
    if result["execution_result"]:
        print(f"返回 {result['execution_result']['row_count']} 行")
```

## 7. 命令行接口

```python
# cli.py
import click
import yaml
from agent.sql_agent import SemanticSQLAgent

@click.command()
@click.option('--config', '-c', default='config.yaml', help='配置文件路径')
def interactive(config: str):
    """交互式查询"""
    # 加载配置
    with open(config, 'r') as f:
        cfg = yaml.safe_load(f)
    
    # 创建 agent
    agent = SemanticSQLAgent(cfg)
    
    print("SemanticSQL Agent 已启动")
    print("输入 'exit' 退出\n")
    
    while True:
        query = input("SQL> ")
        if query.lower() == 'exit':
            break
        
        try:
            result = agent.query(query)
            if result["success"]:
                print(f"\nSQL:\n{result['sql']}")
                print(f"\n结果:\n{result['answer']}\n")
            else:
                print(f"\n错误: {result['error']}\n")
        except Exception as e:
            print(f"\n执行失败: {e}\n")
    
    print("再见!")

if __name__ == '__main__':
    interactive()
```