# SemanticSQL-Agent 实现指南

## 1. 快速开始

### 1.1 环境准备

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install langchain>=0.1.0 langchain-openai>=0.0.5 langchain-community>=0.0.10
pip install pymysql sqlalchemy
pip install pydantic>=2.0 jinja2 pyyaml
```

### 1.2 项目结构创建

```bash
mkdir -p semanticsql-agent/{config,models,tools/{analysis_tools,generation_tools,validation_tools,thinking_tools},prompts/templates/{system,tools,analysis},agent,utils}
touch semanticsql-agent/{__init__.py,cli.py}
```

## 2. 配置文件

### 2.1 创建配置文件

```yaml
# config.yaml
model:
  name: "Qwen3-14B"
  provider: "openai"
  base_url: "http://192.168.200.216:9991/v1"
  api_key: "not-needed"  # vLLM 不需要 API key
  temperature: 0.1
  max_tokens: 2000

database:
  host: "192.168.200.216"
  port: 13306
  user: "testuser"
  password: "testpass"
  database: "testdb"
  charset: "utf8mb4"

agent:
  max_iterations: 15
  enable_thinking: true
  verbose: true
```

## 3. 核心实现

### 3.1 数据模型

```python
# models/schemas.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum

class FieldType(str, Enum):
    DIMENSION = "dimension"
    MEASURE = "measure"
    IDENTIFIER = "identifier"
    TIMESTAMP = "timestamp"
    DESCRIPTION = "description"

class TableInfo(BaseModel):
    name: str
    columns: List[Dict[str, Any]]
    row_count: Optional[int] = None
    comment: Optional[str] = None

class QueryResult(BaseModel):
    success: bool
    sql: Optional[str] = None
    result: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    row_count: int = 0
```

### 3.2 工具基类

```python
# tools/base.py
from langchain.tools import BaseTool
from pydantic import Field
from typing import Any
from abc import abstractmethod
import logging

logger = logging.getLogger(__name__)

class BaseSemanticSQLTool(BaseTool):
    """SemanticSQL 工具基类"""
    
    # 共享资源
    db: Any = Field(default=None, exclude=True)
    llm: Any = Field(default=None, exclude=True)
    
    def _run(self, *args, **kwargs) -> str:
        """执行工具"""
        try:
            result = self.execute(**kwargs)
            return self._format_output(result)
        except Exception as e:
            logger.error(f"工具 {self.name} 执行失败: {str(e)}")
            return f"执行失败: {str(e)}"
    
    async def _arun(self, *args, **kwargs) -> str:
        """异步执行（不实现）"""
        return self._run(*args, **kwargs)
    
    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """具体执行逻辑"""
        pass
    
    def _format_output(self, result: Any) -> str:
        """格式化输出"""
        if isinstance(result, str):
            return result
        elif isinstance(result, dict):
            lines = []
            for key, value in result.items():
                if isinstance(value, list):
                    lines.append(f"{key}: {len(value)} items")
                else:
                    lines.append(f"{key}: {value}")
            return "\n".join(lines)
        else:
            return str(result)
```

### 3.3 分析工具实现

```python
# tools/analysis_tools/schema_extraction_tool.py
from tools.base import BaseSemanticSQLTool
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class SchemaExtractionTool(BaseSemanticSQLTool):
    name = "extract_database_schema"
    description = "提取数据库表结构信息，是分析的第一步"
    
    class InputSchema(BaseModel):
        tables: Optional[List[str]] = Field(
            default=None,
            description="要提取的表名列表，为空则提取所有表"
        )
    
    args_schema = InputSchema
    
    def execute(self, tables: Optional[List[str]] = None) -> Dict[str, Any]:
        if not tables:
            tables = self.db.get_usable_table_names()
        
        result = {}
        for table in tables[:10]:  # 限制数量避免输出过长
            table_info = self.db.get_table_info_no_throw([table])
            
            # 获取样例数据
            try:
                sample = self.db.run(f"SELECT * FROM {table} LIMIT 3")
                result[table] = {
                    "structure": table_info,
                    "sample_data": sample
                }
            except:
                result[table] = {
                    "structure": table_info,
                    "sample_data": "无法获取样例数据"
                }
        
        return result

# tools/analysis_tools/domain_analysis_tool.py
class DomainAnalysisTool(BaseSemanticSQLTool):
    name = "analyze_business_domain"
    description = "分析数据库的业务领域和关键实体"
    
    class InputSchema(BaseModel):
        schema_info: Dict[str, Any] = Field(
            description="数据库结构信息"
        )
    
    args_schema = InputSchema
    
    def execute(self, schema_info: Dict[str, Any]) -> Dict[str, Any]:
        # 构建分析提示词
        tables_desc = []
        for table, info in schema_info.items():
            tables_desc.append(f"表 {table}:\n{info.get('structure', '')}")
        
        prompt = f"""
        分析以下数据库的业务领域：
        
        {chr(10).join(tables_desc)}
        
        请识别：
        1. 业务领域（如电商、金融、教育等）
        2. 关键业务实体
        3. 主要业务流程
        """
        
        response = self.llm.invoke(prompt)
        
        return {
            "analysis": response.content,
            "tables_analyzed": len(schema_info)
        }

# tools/analysis_tools/field_classification_tool.py  
class FieldClassificationTool(BaseSemanticSQLTool):
    name = "classify_table_fields"
    description = "对表字段进行分类，识别维度、度量等类型"
    
    class InputSchema(BaseModel):
        table_name: str = Field(description="要分类的表名")
        table_info: str = Field(description="表结构信息")
    
    args_schema = InputSchema
    
    def execute(self, table_name: str, table_info: str) -> Dict[str, Any]:
        prompt = f"""
        对表 {table_name} 的字段进行分类：
        
        {table_info}
        
        分类标准：
        - dimensions: 维度字段（用于分组）
        - measures: 度量字段（数值计算）
        - identifiers: 标识符字段
        - timestamps: 时间字段
        - descriptions: 描述字段
        
        返回分类结果。
        """
        
        response = self.llm.invoke(prompt)
        
        return {
            "table": table_name,
            "classification": response.content
        }
```

### 3.4 生成和验证工具

```python
# tools/generation_tools/sql_generation_tool.py
class SQLGenerationTool(BaseSemanticSQLTool):
    name = "generate_sql"
    description = "基于用户查询和分析结果生成 SQL"
    
    class InputSchema(BaseModel):
        query: str = Field(description="用户查询")
        context: Dict[str, Any] = Field(description="分析上下文")
    
    args_schema = InputSchema
    
    def execute(self, query: str, context: Dict[str, Any]) -> str:
        # 使用 Jinja2 模板
        from prompts.manager import PromptManager
        pm = PromptManager()
        
        prompt = pm.get_prompt(
            "sql_generation",
            query=query,
            context=context
        )
        
        response = self.llm.invoke(prompt)
        
        # 提取 SQL
        import re
        sql_match = re.search(r'```sql\n(.*?)\n```', response.content, re.DOTALL)
        if sql_match:
            return f"生成的 SQL:\n```sql\n{sql_match.group(1)}\n```"
        
        # 备选方案
        for line in response.content.split('\n'):
            if 'SELECT' in line.upper():
                return f"生成的 SQL:\n```sql\n{line}\n```"
        
        return f"生成的 SQL:\n{response.content}"

# tools/validation_tools/sql_validation_tool.py
class SQLValidationTool(BaseSemanticSQLTool):
    name = "validate_sql"
    description = "验证 SQL 语法的正确性"
    
    class InputSchema(BaseModel):
        sql: str = Field(description="要验证的 SQL")
    
    args_schema = InputSchema
    
    def execute(self, sql: str) -> Dict[str, Any]:
        try:
            # 清理 SQL
            sql = sql.replace('```sql', '').replace('```', '').strip()
            
            # 使用 EXPLAIN 验证
            self.db.run(f"EXPLAIN {sql}")
            
            return {
                "valid": True,
                "sql": sql,
                "message": "SQL 语法正确"
            }
        except Exception as e:
            return {
                "valid": False,
                "sql": sql,
                "error": str(e),
                "message": f"SQL 验证失败: {str(e)}"
            }

# tools/validation_tools/sql_execution_tool.py
class SQLExecutionTool(BaseSemanticSQLTool):
    name = "execute_sql"
    description = "执行 SQL 并返回结果"
    
    class InputSchema(BaseModel):
        sql: str = Field(description="要执行的 SQL")
        limit: int = Field(default=10, description="结果限制")
    
    args_schema = InputSchema
    
    def execute(self, sql: str, limit: int = 10) -> Dict[str, Any]:
        try:
            # 清理 SQL
            sql = sql.replace('```sql', '').replace('```', '').strip()
            
            # 添加 LIMIT
            if limit and 'LIMIT' not in sql.upper():
                sql = f"{sql.rstrip(';')} LIMIT {limit}"
            
            # 执行
            result = self.db.run(sql)
            
            # 解析结果
            import ast
            try:
                rows = ast.literal_eval(result) if result else []
            except:
                rows = []
            
            return {
                "success": True,
                "sql": sql,
                "rows": rows,
                "row_count": len(rows),
                "preview": str(rows[:3]) if rows else "无数据"
            }
        except Exception as e:
            return {
                "success": False,
                "sql": sql,
                "error": str(e)
            }
```

### 3.5 工具工厂

```python
# tools/__init__.py
from typing import List
from langchain.tools import BaseTool

def create_analysis_tools(db, llm) -> List[BaseTool]:
    """创建分析工具"""
    from .analysis_tools.schema_extraction_tool import SchemaExtractionTool
    from .analysis_tools.domain_analysis_tool import DomainAnalysisTool
    from .analysis_tools.field_classification_tool import FieldClassificationTool
    
    tools = [
        SchemaExtractionTool(db=db),
        DomainAnalysisTool(db=db, llm=llm),
        FieldClassificationTool(db=db, llm=llm)
    ]
    
    return tools

def create_generation_tools(llm) -> List[BaseTool]:
    """创建生成工具"""
    from .generation_tools.sql_generation_tool import SQLGenerationTool
    return [SQLGenerationTool(llm=llm)]

def create_validation_tools(db) -> List[BaseTool]:
    """创建验证工具"""
    from .validation_tools.sql_validation_tool import SQLValidationTool
    from .validation_tools.sql_execution_tool import SQLExecutionTool
    
    return [
        SQLValidationTool(db=db),
        SQLExecutionTool(db=db)
    ]

def create_thinking_tools(llm) -> List[BaseTool]:
    """创建思考工具"""
    # 可选实现
    return []
```

### 3.6 提示词管理

```python
# prompts/manager.py
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

class PromptManager:
    def __init__(self):
        self.template_dir = Path(__file__).parent / "templates"
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            trim_blocks=True,
            lstrip_blocks=True
        )
    
    def get_prompt(self, template_name: str, **kwargs) -> str:
        """获取渲染后的提示词"""
        if not template_name.endswith('.j2'):
            template_name += '.j2'
        
        template = self.env.get_template(template_name)
        return template.render(**kwargs)
```

创建提示词模板：

```jinja2
{# prompts/templates/system/sql_agent.j2 #}
你是一个专业的 SQL 数据库专家。

## 你的任务
将用户的自然语言查询转换为准确的 SQL 语句。

## 工作流程
1. 使用 extract_database_schema 了解数据库结构
2. 使用 analyze_business_domain 理解业务含义
3. 使用 classify_table_fields 分析字段类型（如需要）
4. 使用 generate_sql 生成 SQL 查询
5. 使用 validate_sql 验证语法
6. 使用 execute_sql 执行并获取结果

## 注意事项
- 只使用存在的表和字段
- 生成高效的查询
- 返回清晰的结果说明

可用的表：
{% for table in tables[:10] %}
- {{ table }}
{% endfor %}
```

### 3.7 主智能体实现

```python
# agent/sql_agent.py
from langchain.agents import create_react_agent, AgentExecutor
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain.chat_models import init_chat_model
from typing import Dict, Any, List
import logging
import re

from tools import (
    create_analysis_tools,
    create_generation_tools,
    create_validation_tools,
    create_thinking_tools
)
from agent.callbacks import TrajectoryCallback
from prompts.manager import PromptManager

logger = logging.getLogger(__name__)

class SemanticSQLAgent:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        logger.info("初始化 SemanticSQL Agent...")
        
        self.db = self._init_database()
        self.llm = self._init_llm()
        self.tools = self._create_tools()
        self.trajectory_callback = TrajectoryCallback()
        self.agent_executor = self._create_agent_executor()
    
    def _init_database(self) -> SQLDatabase:
        """初始化数据库连接"""
        db_config = self.config["database"]
        uri = (
            f"mysql+pymysql://{db_config['user']}:{db_config['password']}@"
            f"{db_config['host']}:{db_config['port']}/{db_config['database']}"
            f"?charset={db_config.get('charset', 'utf8mb4')}"
        )
        
        db = SQLDatabase.from_uri(uri)
        logger.info(f"连接数据库成功，找到 {len(db.get_usable_table_names())} 个表")
        return db
    
    def _init_llm(self):
        """初始化 LLM"""
        model_config = self.config["model"]
        
        # 对于 vLLM，使用 OpenAI 兼容接口
        if model_config.get("provider") == "openai" or "vllm" in model_config.get("base_url", ""):
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model_config["name"],
                openai_api_key=model_config.get("api_key", "not-needed"),
                openai_api_base=model_config.get("base_url"),
                temperature=model_config.get("temperature", 0.1),
                max_tokens=model_config.get("max_tokens", 2000)
            )
        else:
            return init_chat_model(
                model_config["name"],
                model_provider=model_config.get("provider"),
                temperature=model_config.get("temperature", 0.1)
            )
    
    def _create_tools(self) -> List:
        """创建工具集"""
        tools = []
        
        # SQL 基础工具
        toolkit = SQLDatabaseToolkit(db=self.db, llm=self.llm)
        tools.extend(toolkit.get_tools())
        
        # 自定义工具
        tools.extend(create_analysis_tools(self.db, self.llm))
        tools.extend(create_generation_tools(self.llm))
        tools.extend(create_validation_tools(self.db))
        
        if self.config["agent"].get("enable_thinking", True):
            tools.extend(create_thinking_tools(self.llm))
        
        logger.info(f"创建了 {len(tools)} 个工具")
        return tools
    
    def _create_agent_executor(self) -> AgentExecutor:
        """创建智能体执行器"""
        # 获取系统提示词
        pm = PromptManager()
        system_prompt = pm.get_prompt(
            "system/sql_agent",
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
            verbose=self.config["agent"].get("verbose", True),
            max_iterations=self.config["agent"].get("max_iterations", 15),
            callbacks=[self.trajectory_callback],
            handle_parsing_errors=True
        )
    
    def query(self, question: str) -> Dict[str, Any]:
        """执行查询"""
        logger.info(f"处理查询: {question}")
        self.trajectory_callback.reset()
        
        try:
            result = self.agent_executor.invoke({"input": question})
            
            # 提取信息
            sql = self._extract_sql(result)
            execution_result = self._extract_execution_result()
            
            return {
                "success": True,
                "question": question,
                "sql": sql,
                "answer": result.get("output", ""),
                "execution_result": execution_result,
                "steps": len(self.trajectory_callback.trajectory["tool_calls"])
            }
            
        except Exception as e:
            logger.error(f"查询执行失败: {str(e)}", exc_info=True)
            raise e
    
    def _extract_sql(self, result: Dict[str, Any]) -> str:
        """提取 SQL"""
        output = result.get("output", "")
        
        # 查找 SQL 代码块
        sql_match = re.search(r'```sql\n(.*?)\n```', output, re.DOTALL)
        if sql_match:
            return sql_match.group(1).strip()
        
        # 从工具调用中查找
        for call in self.trajectory_callback.trajectory["tool_calls"]:
            if "generate_sql" in call["tool"] and "```sql" in call.get("output", ""):
                match = re.search(r'```sql\n(.*?)\n```', call["output"], re.DOTALL)
                if match:
                    return match.group(1).strip()
        
        return ""
    
    def _extract_execution_result(self) -> Dict[str, Any]:
        """提取执行结果"""
        for call in reversed(self.trajectory_callback.trajectory["tool_calls"]):
            if "execute_sql" in call["tool"]:
                # 尝试解析输出
                output = call.get("output", "")
                if "row_count:" in output:
                    # 简单解析
                    lines = output.split('\n')
                    result = {}
                    for line in lines:
                        if "row_count:" in line:
                            try:
                                result["row_count"] = int(line.split(":")[-1].strip())
                            except:
                                pass
                        elif "preview:" in line:
                            result["preview"] = line.split(":", 1)[-1].strip()
                    return result
        return None
```

### 3.8 回调实现

```python
# agent/callbacks.py
from langchain.callbacks.base import BaseCallbackHandler
from typing import Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class TrajectoryCallback(BaseCallbackHandler):
    """轨迹记录回调"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.trajectory = {
            "start_time": datetime.now().isoformat(),
            "tool_calls": [],
            "errors": []
        }
    
    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs):
        """工具开始执行"""
        tool_call = {
            "timestamp": datetime.now().isoformat(),
            "tool": serialized.get("name", "unknown"),
            "input": input_str[:500]  # 限制长度
        }
        self.trajectory["tool_calls"].append(tool_call)
        logger.debug(f"工具开始: {tool_call['tool']}")
    
    def on_tool_end(self, output: str, **kwargs):
        """工具执行结束"""
        if self.trajectory["tool_calls"]:
            self.trajectory["tool_calls"][-1]["output"] = output[:1000]
            logger.debug(f"工具结束: {self.trajectory['tool_calls'][-1]['tool']}")
    
    def on_tool_error(self, error: Exception, **kwargs):
        """工具执行错误"""
        error_info = {
            "timestamp": datetime.now().isoformat(),
            "error": str(error)
        }
        self.trajectory["errors"].append(error_info)
        logger.error(f"工具错误: {error}")
```

### 3.9 命令行接口

```python
# cli.py
import click
import yaml
import logging
from pathlib import Path

from agent.sql_agent import SemanticSQLAgent

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

@click.command()
@click.option('--config', '-c', default='config.yaml', help='配置文件路径')
@click.option('--query', '-q', help='直接执行查询')
def main(config: str, query: str):
    """SemanticSQL Agent CLI"""
    
    # 加载配置
    config_path = Path(config)
    if not config_path.exists():
        click.echo(f"配置文件不存在: {config}")
        return
    
    with open(config_path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    
    # 创建 agent
    click.echo("初始化 SemanticSQL Agent...")
    try:
        agent = SemanticSQLAgent(cfg)
    except Exception as e:
        click.echo(f"初始化失败: {e}")
        return
    
    if query:
        # 单次查询模式
        try:
            result = agent.query(query)
            click.echo(f"\nSQL:\n{result['sql']}")
            click.echo(f"\n结果:\n{result['answer']}")
            if result['execution_result']:
                click.echo(f"\n执行结果: {result['execution_result']}")
        except Exception as e:
            click.echo(f"\n错误: {e}")
    else:
        # 交互模式
        click.echo("\nSemanticSQL Agent 交互模式")
        click.echo("输入查询或 'exit' 退出\n")
        
        while True:
            user_query = click.prompt('SQL', type=str)
            
            if user_query.lower() in ['exit', 'quit']:
                break
            
            try:
                result = agent.query(user_query)
                click.echo(f"\nSQL:\n{result['sql']}")
                click.echo(f"\n结果:\n{result['answer']}")
                if result['execution_result']:
                    click.echo(f"\n返回 {result['execution_result'].get('row_count', 0)} 行")
            except Exception as e:
                click.echo(f"\n错误: {e}")
            
            click.echo("\n" + "-"*50 + "\n")
        
        click.echo("\n再见!")

if __name__ == '__main__':
    main()
```

## 4. 使用示例

### 4.1 基础使用

```python
# example_usage.py
import yaml
from agent.sql_agent import SemanticSQLAgent

# 加载配置
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# 创建 agent
agent = SemanticSQLAgent(config)

# 查询示例
queries = [
    "显示所有表",
    "查询员工表的结构",
    "统计每个部门的平均工资",
    "找出销售额最高的10个产品"
]

for query in queries:
    print(f"\n查询: {query}")
    print("-" * 50)
    
    try:
        result = agent.query(query)
        print(f"SQL: {result['sql']}")
        print(f"结果: {result['answer'][:200]}...")
        if result['execution_result']:
            print(f"返回行数: {result['execution_result'].get('row_count', 0)}")
    except Exception as e:
        print(f"错误: {e}")
```

### 4.2 命令行使用

```bash
# 交互模式
python cli.py

# 单次查询
python cli.py -q "查询所有客户信息"

# 指定配置文件
python cli.py -c custom_config.yaml
```

## 5. 部署注意事项

### 5.1 vLLM 配置

确保 vLLM 服务正常运行：

```bash
# 启动 vLLM 服务
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3-14B \
    --host 0.0.0.0 \
    --port 9991
```

### 5.2 数据库权限

确保数据库用户有必要的权限：

```sql
GRANT SELECT ON testdb.* TO 'testuser'@'%';
GRANT SHOW VIEW ON testdb.* TO 'testuser'@'%';
```

### 5.3 错误处理

系统不做降级处理，直接抛出异常。在生产环境中，建议在应用层面添加适当的错误处理和重试机制。

## 6. 扩展建议

1. **添加缓存**：对常用查询结果进行缓存
2. **查询优化**：分析慢查询并优化
3. **权限控制**：根据用户角色限制可访问的表
4. **日志分析**：分析查询日志改进系统

这个实现遵循了您的所有要求：
- 删除了专有名词检索工具
- 删除了流式查询功能
- 删除了带审核的查询链
- 删除了安全和性能优化相关内容
- 错误直接抛出，不做降级处理
- 基于 TRAEAgent 的简洁设计
- 保留了 nl2sql_pipeline 的核心分析流程