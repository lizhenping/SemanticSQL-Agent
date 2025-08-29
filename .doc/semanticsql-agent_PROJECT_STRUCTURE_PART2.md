# SemanticSQL Agent 项目结构设计 - 第二部分

### 2.3 SQL智能体 (agent/smart_sql_agent.py)

```python
"""
Smart SQL Agent - NL2SQL数据生成智能体
"""
from typing import Dict, Any, List
from agent.base_agent import BaseAgent
from config.settings import Config

# 导入所有工具
from tools.analysis import (
    SchemaAnalyzer, DomainAnalyzer, 
    FieldClassifier, RelationshipAnalyzer
)
from tools.generation import (
    ScenarioGenerator, QuestionGenerator, SQLGenerator
)
from tools.sql import SQLValidator, SQLExecutor
from tools.reflection import ExecutionAnalyzer, QualityImprover


class SmartSQLAgent(BaseAgent):
    """智能SQL数据生成Agent"""
    
    def __init__(self, config: Config):
        """初始化智能体"""
        super().__init__(config)
        self._initialize_tools()
        
    def _initialize_tools(self):
        """初始化并注册所有工具"""
        # 分析工具
        self.register_tool("schema_analyzer", SchemaAnalyzer(self.config))
        self.register_tool("domain_analyzer", DomainAnalyzer(self.config))
        self.register_tool("field_classifier", FieldClassifier(self.config))
        self.register_tool("relationship_analyzer", RelationshipAnalyzer(self.config))
        
        # 生成工具
        self.register_tool("scenario_generator", ScenarioGenerator(self.config))
        self.register_tool("question_generator", QuestionGenerator(self.config))
        self.register_tool("sql_generator", SQLGenerator(self.config))
        
        # SQL工具
        self.register_tool("sql_validator", SQLValidator(self.config))
        self.register_tool("sql_executor", SQLExecutor(self.config))
        
        # 反思工具
        if self.enable_reflection:
            self.register_tool("execution_analyzer", ExecutionAnalyzer(self.config))
            self.register_tool("quality_improver", QualityImprover(self.config))
    
    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        tools_desc = self._get_tools_description()
        
        return f"""你是一个智能SQL训练数据生成专家。

你的任务是生成高质量的NL2SQL训练数据，包括：
1. 分析数据库结构和业务领域
2. 生成多样化的业务场景
3. 为每个场景生成自然语言问题
4. 生成对应的SQL查询
5. 验证和优化生成的内容

使用ReAct模式工作：
- Thought: 分析当前状态，决定下一步行动
- Action: 选择并调用合适的工具
- Observation: 观察工具执行结果

可用工具：
{tools_desc}

重要原则：
1. 系统地完成所有必要步骤
2. 确保生成的数据质量高、多样性好
3. SQL必须语法正确且符合业务逻辑
4. 遇到错误时合理处理并继续

完成标志：
- 已生成所需数量的高质量训练样本
- 所有样本都经过验证
- 如果启用了反思，已完成质量优化
"""
    
    def _get_tools_description(self) -> str:
        """获取工具描述"""
        lines = []
        for name, tool in self.tools.items():
            lines.append(f"- {name}: {tool.description}")
        return "\n".join(lines)
    
    def smart_analyze(self, database_config: Dict[str, Any], 
                     target_count: int = 100) -> Dict[str, Any]:
        """智能分析并生成数据"""
        task = f"""分析数据库并生成{target_count}条高质量的NL2SQL训练数据。

要求：
1. 首先全面分析数据库结构
2. 识别业务领域和特征
3. 生成多样化的查询场景
4. 为每个场景生成自然语言问题和SQL
5. 验证所有生成的SQL
6. 如果启用反思，优化质量

数据库配置已提供，请开始执行。
"""
        
        context = {
            "database_config": database_config,
            "target_count": target_count
        }
        
        # 执行任务
        execution = self.run(task, context)
        
        # 整理结果
        return self._format_results(execution)
    
    def _format_results(self, execution: AgentExecution) -> Dict[str, Any]:
        """格式化执行结果"""
        if execution.status != "completed":
            return {
                "status": "failed",
                "error": execution.error,
                "steps": len(execution.steps)
            }
        
        # 提取各工具的结果
        results = execution.final_result
        
        # 组装训练数据集
        dataset = {
            "status": "success",
            "dataset_id": execution.task_id,
            "created_at": execution.started_at.isoformat(),
            "execution_time": (
                execution.completed_at - execution.started_at
            ).total_seconds() if execution.completed_at else None,
            "steps_count": len(execution.steps),
            "results": results
        }
        
        # 如果有生成的样本，格式化输出
        if "sql_generator" in results:
            dataset["examples"] = self._format_examples(results)
            dataset["statistics"] = self._calculate_statistics(dataset["examples"])
            
        return dataset
    
    def _format_examples(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """格式化训练样本"""
        examples = []
        
        # 获取生成的问题和SQL
        questions = results.get("question_generator", {}).get("questions", [])
        sqls = results.get("sql_generator", {}).get("sqls", [])
        validations = results.get("sql_validator", {}).get("results", [])
        executions = results.get("sql_executor", {}).get("results", [])
        
        # 组合成训练样本
        for i, (question, sql) in enumerate(zip(questions, sqls)):
            example = {
                "id": f"example_{i+1}",
                "question": question,
                "sql": sql,
                "validation": validations[i] if i < len(validations) else None,
                "execution": executions[i] if i < len(executions) else None
            }
            examples.append(example)
            
        return examples
    
    def _calculate_statistics(self, examples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算统计信息"""
        return {
            "total_examples": len(examples),
            "validated_count": sum(
                1 for e in examples 
                if e.get("validation", {}).get("syntax_valid", False)
            ),
            "executed_count": sum(
                1 for e in examples 
                if e.get("execution", {}).get("success", False)
            )
        }
```

### 2.4 工具基类 (tools/base.py)

```python
"""
工具基类定义
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Type
from pydantic import BaseModel
from utils.logger import get_logger


class BaseTool(ABC):
    """工具基类"""
    
    def __init__(self, config: Any):
        """初始化工具"""
        self.config = config
        self.logger = get_logger(self.__class__.__name__)
    
    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""
        pass
    
    @abstractmethod
    def get_input_schema(self) -> Type[BaseModel]:
        """获取输入参数的Pydantic模型"""
        pass
    
    @abstractmethod
    def run(self, **kwargs) -> Any:
        """执行工具"""
        pass
    
    def get_schema(self) -> Dict[str, Any]:
        """获取Function Calling的schema"""
        input_schema = self.get_input_schema()
        
        # 从Pydantic模型生成JSON Schema
        properties = {}
        required = []
        
        for field_name, field in input_schema.model_fields.items():
            properties[field_name] = {
                "type": self._get_json_type(field.annotation),
                "description": field.description or ""
            }
            if field.is_required():
                required.append(field_name)
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }
    
    def _get_json_type(self, python_type: Type) -> str:
        """Python类型转JSON Schema类型"""
        type_mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object"
        }
        
        # 处理Optional类型
        if hasattr(python_type, "__origin__"):
            if python_type.__origin__ is list:
                return "array"
            elif python_type.__origin__ is dict:
                return "object"
        
        return type_mapping.get(python_type, "string")
    
    def validate_input(self, **kwargs) -> Dict[str, Any]:
        """验证输入参数"""
        schema = self.get_input_schema()
        validated = schema(**kwargs)
        return validated.model_dump()
```

### 2.5 具体工具示例 (tools/analysis/schema_analyzer.py)

```python
"""
数据库结构分析工具
"""
from typing import Dict, Any, List, Type
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, inspect, MetaData
from tools.base import BaseTool
from core.models import SchemaAnalysis, TableInfo, DatabaseType
from utils.database import get_connection_string


class SchemaAnalyzerInput(BaseModel):
    """结构分析工具输入"""
    database_config: Dict[str, Any] = Field(description="数据库连接配置")
    include_row_counts: bool = Field(default=False, description="是否包含行数统计")


class SchemaAnalyzer(BaseTool):
    """数据库结构分析工具"""
    
    @property
    def name(self) -> str:
        return "schema_analyzer"
    
    @property
    def description(self) -> str:
        return "分析数据库结构，提取表、列、索引和关系信息"
    
    def get_input_schema(self) -> Type[BaseModel]:
        return SchemaAnalyzerInput
    
    def run(self, database_config: Dict[str, Any], 
            include_row_counts: bool = False) -> SchemaAnalysis:
        """执行数据库结构分析"""
        try:
            # 创建数据库连接
            connection_string = get_connection_string(database_config)
            engine = create_engine(connection_string)
            
            # 使用SQLAlchemy的Inspector
            inspector = inspect(engine)
            
            # 获取所有表
            table_names = inspector.get_table_names()
            tables = []
            
            for table_name in table_names:
                # 获取表信息
                table_info = self._analyze_table(
                    inspector, table_name, engine, include_row_counts
                )
                tables.append(table_info)
            
            # 构建分析结果
            result = SchemaAnalysis(
                database_name=database_config.get("database", "unknown"),
                database_type=DatabaseType(database_config.get("type", "mysql")),
                tables=tables,
                total_tables=len(tables)
            )
            
            self.logger.info(f"Analyzed {len(tables)} tables")
            return result
            
        except Exception as e:
            self.logger.error(f"Schema analysis failed: {e}")
            raise
        finally:
            if 'engine' in locals():
                engine.dispose()
    
    def _analyze_table(self, inspector, table_name: str, 
                      engine, include_row_counts: bool) -> TableInfo:
        """分析单个表"""
        # 获取列信息
        columns = []
        for col in inspector.get_columns(table_name):
            columns.append({
                "name": col["name"],
                "type": str(col["type"]),
                "nullable": col["nullable"],
                "default": col["default"],
                "comment": col.get("comment", "")
            })
        
        # 获取主键
        pk_constraint = inspector.get_pk_constraint(table_name)
        primary_key = pk_constraint["constrained_columns"][0] if pk_constraint["constrained_columns"] else None
        
        # 获取外键
        foreign_keys = []
        for fk in inspector.get_foreign_keys(table_name):
            foreign_keys.append({
                "column": fk["constrained_columns"][0],
                "referred_table": fk["referred_table"],
                "referred_column": fk["referred_columns"][0]
            })
        
        # 获取表注释
        table_comment = inspector.get_table_comment(table_name).get("text", "")
        
        # 获取行数（可选）
        row_count = None
        if include_row_counts:
            try:
                result = engine.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = result.scalar()
            except:
                pass
        
        return TableInfo(
            name=table_name,
            columns=columns,
            primary_key=primary_key,
            foreign_keys=foreign_keys,
            row_count=row_count,
            comment=table_comment
        )
```

### 2.6 CLI入口 (cli/cli.py)

```python
"""
命令行接口
"""
import click
import json
import yaml
from pathlib import Path
from config.settings import Config
from agent.smart_sql_agent import SmartSQLAgent
from utils.database import test_connection


@click.group()
@click.version_option(version="0.1.0", prog_name="semanticsql-agent")
def cli():
    """SemanticSQL Agent - 智能NL2SQL数据生成工具"""
    pass


@cli.command()
@click.option('--config', '-c', type=click.Path(exists=True), 
              help='配置文件路径')
@click.option('--db-type', type=click.Choice(['mysql', 'postgresql', 'sqlite']),
              help='数据库类型')
@click.option('--host', help='数据库主机')
@click.option('--port', type=int, help='数据库端口')
@click.option('--database', help='数据库名称')
@click.option('--username', help='用户名')
@click.option('--password', help='密码')
@click.option('--count', '-n', type=int, default=100, help='生成数据条数')
@click.option('--output', '-o', type=click.Path(), help='输出文件路径')
@click.option('--format', type=click.Choice(['json', 'jsonl', 'csv']), 
              default='json', help='输出格式')
def smart_analyze(config, db_type, host, port, database, username, password, 
                 count, output, format):
    """智能分析数据库并生成NL2SQL训练数据"""
    # 加载配置
    if config:
        cfg = Config.from_yaml(config)
    else:
        cfg = Config.from_env()
    
    # 命令行参数覆盖配置
    if db_type:
        cfg.database.type = db_type
    if host:
        cfg.database.host = host
    if port:
        cfg.database.port = port
    if database:
        cfg.database.database = database
    if username:
        cfg.database.username = username
    if password:
        cfg.database.password = password
    
    # 创建智能体
    click.echo("初始化智能体...")
    agent = SmartSQLAgent(cfg)
    
    # 执行分析
    click.echo(f"开始分析数据库并生成{count}条训练数据...")
    result = agent.smart_analyze(
        database_config=cfg.database.to_dict(),
        target_count=count
    )
    
    # 处理结果
    if result["status"] == "success":
        click.echo(f"✓ 成功生成 {len(result.get('examples', []))} 条数据")
        
        # 保存结果
        if output:
            save_results(result, output, format)
            click.echo(f"✓ 结果已保存到: {output}")
        else:
            # 打印示例
            examples = result.get("examples", [])
            if examples:
                click.echo("\n示例数据:")
                for i, example in enumerate(examples[:3], 1):
                    click.echo(f"\n--- 样本 {i} ---")
                    click.echo(f"问题: {example['question']}")
                    click.echo(f"SQL: {example['sql']}")
    else:
        click.echo(f"✗ 生成失败: {result.get('error', 'Unknown error')}")
        

@cli.command()
@click.option('--config', '-c', type=click.Path(exists=True), 
              help='配置文件路径')
def test_connection(config):
    """测试数据库连接"""
    # 加载配置
    if config:
        cfg = Config.from_yaml(config)
    else:
        cfg = Config.from_env()
    
    click.echo("测试数据库连接...")
    
    # 测试连接
    success, message = test_connection(cfg.database.to_dict())
    
    if success:
        click.echo(f"✓ 连接成功: {message}")
    else:
        click.echo(f"✗ 连接失败: {message}")


@cli.command()
def init():
    """初始化项目配置"""
    # 创建配置目录
    config_dir = Path("config")
    config_dir.mkdir(exist_ok=True)
    
    # 复制示例配置
    example_config = {
        "database": {
            "type": "mysql",
            "host": "localhost",
            "port": 3306,
            "username": "root",
            "password": "${DB_PASSWORD}",
            "database": "your_database"
        },
        "llm": {
            "model": "qwen-plus",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key": "${DASHSCOPE_API_KEY}",
            "temperature": 0.7,
            "max_tokens": 4096
        },
        "agent": {
            "max_steps": 20,
            "enable_reflection": True
        },
        "output": {
            "format": "json",
            "directory": "./output"
        }
    }
    
    config_file = config_dir / "config.yaml"
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(example_config, f, allow_unicode=True, default_flow_style=False)
    
    click.echo(f"✓ 配置文件已创建: {config_file}")
    click.echo("\n请编辑配置文件并设置以下环境变量:")
    click.echo("  - DASHSCOPE_API_KEY: 通义千问API密钥")
    click.echo("  - DB_PASSWORD: 数据库密码")


def save_results(result: Dict[str, Any], output_path: str, format: str):
    """保存结果到文件"""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    if format == "json":
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    elif format == "jsonl":
        with open(path, "w", encoding="utf-8") as f:
            for example in result.get("examples", []):
                f.write(json.dumps(example, ensure_ascii=False) + "\n")
    elif format == "csv":
        import csv
        with open(path, "w", encoding="utf-8", newline="") as f:
            if result.get("examples"):
                writer = csv.DictWriter(f, fieldnames=["question", "sql"])
                writer.writeheader()
                for example in result["examples"]:
                    writer.writerow({
                        "question": example["question"],
                        "sql": example["sql"]
                    })


if __name__ == "__main__":
    cli()
```

### 2.7 配置管理 (config/settings.py)

```python
"""
配置管理
"""
import os
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import yaml


@dataclass
class DatabaseConfig:
    """数据库配置"""
    type: str = "mysql"
    host: str = "localhost"
    port: int = 3306
    username: str = "root"
    password: str = ""
    database: str = ""
    pool_size: int = 5
    pool_timeout: int = 30
    echo: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "database": self.database
        }


@dataclass
class LLMConfig:
    """LLM配置"""
    model: str = "qwen-plus"
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    api_key: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 60


@dataclass
class AgentConfig:
    """智能体配置"""
    max_steps: int = 20
    enable_reflection: bool = True
    verbose: bool = True
    save_trajectory: bool = True


@dataclass
class OutputConfig:
    """输出配置"""
    format: str = "json"
    directory: str = "./output"
    filename_pattern: str = "dataset_{timestamp}.{format}"


@dataclass
class Config:
    """统一配置"""
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    
    @classmethod
    def from_yaml(cls, path: str) -> "Config":
        """从YAML文件加载配置"""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        # 处理环境变量
        data = cls._resolve_env_vars(data)
        
        return cls(
            database=DatabaseConfig(**data.get("database", {})),
            llm=LLMConfig(**data.get("llm", {})),
            agent=AgentConfig(**data.get("agent", {})),
            output=OutputConfig(**data.get("output", {}))
        )
    
    @classmethod
    def from_env(cls) -> "Config":
        """从环境变量加载配置"""
        return cls(
            database=DatabaseConfig(
                type=os.getenv("DB_TYPE", "mysql"),
                host=os.getenv("DB_HOST", "localhost"),
                port=int(os.getenv("DB_PORT", "3306")),
                username=os.getenv("DB_USERNAME", "root"),
                password=os.getenv("DB_PASSWORD", ""),
                database=os.getenv("DB_DATABASE", "")
            ),
            llm=LLMConfig(
                api_key=os.getenv("DASHSCOPE_API_KEY", ""),
                model=os.getenv("LLM_MODEL", "qwen-plus")
            )
        )
    
    @staticmethod
    def _resolve_env_vars(data: Dict[str, Any]) -> Dict[str, Any]:
        """解析配置中的环境变量"""
        if isinstance(data, dict):
            return {
                k: Config._resolve_env_vars(v) 
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [Config._resolve_env_vars(item) for item in data]
        elif isinstance(data, str) and data.startswith("${") and data.endswith("}"):
            env_var = data[2:-1]
            return os.getenv(env_var, "")
        else:
            return data
```

## 3. 项目配置文件

### 3.1 setup.py

```python
"""
安装配置
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="semanticsql-agent",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="智能NL2SQL训练数据生成工具",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/semanticsql-agent",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.8",
    install_requires=[
        "openai>=1.0.0",
        "sqlalchemy>=2.0.0",
        "click>=8.0.0",
        "pydantic>=2.0.0",
        "pyyaml>=6.0",
        "python-dotenv>=1.0.0",
        "rich>=13.0.0",
        "jinja2>=3.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
            "pre-commit>=3.0.0",
        ],
        "mysql": ["pymysql>=1.0.0"],
        "postgresql": ["psycopg2-binary>=2.9.0"],
    },
    entry_points={
        "console_scripts": [
            "semanticsql-agent=cli.cli:cli",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.yaml", "*.yml", "*.j2"],
    },
)
```

### 3.2 requirements.txt

```
# 核心依赖
openai>=1.0.0
sqlalchemy>=2.0.0
click>=8.0.0
pydantic>=2.0.0
pyyaml>=6.0
python-dotenv>=1.0.0
rich>=13.0.0
jinja2>=3.0.0

# 数据库驱动
pymysql>=1.0.0
psycopg2-binary>=2.9.0

# 开发依赖
pytest>=7.0.0
pytest-cov>=4.0.0
black>=23.0.0
flake8>=6.0.0
mypy>=1.0.0
pre-commit>=3.0.0
```

### 3.3 .env.example

```bash
# API配置
DASHSCOPE_API_KEY=your_api_key_here

# 数据库配置
DB_TYPE=mysql
DB_HOST=localhost
DB_PORT=3306
DB_USERNAME=root
DB_PASSWORD=your_password
DB_DATABASE=your_database

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=semanticsql-agent.log

# 输出配置
OUTPUT_DIR=./output
OUTPUT_FORMAT=json
```

### 3.4 .gitignore

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
venv/
ENV/
env/
.venv

# IDE
.vscode/
.idea/
*.swp
*.swo
*~
.project
.pydevproject

# Config
.env
config/config.yaml
config/local.yaml

# Output
output/
*.log
*.db

# Testing
.coverage
.pytest_cache/
htmlcov/
.tox/
.coverage.*

# macOS
.DS_Store

# Temporary files
*.tmp
*.bak
.cache/
```

## 4. 工具实现示例

### 4.1 场景生成工具 (tools/generation/scenario_generator.py)

```python
"""
场景生成工具 - 基于规则生成查询场景
"""
from typing import Dict, Any, List, Type
from pydantic import BaseModel, Field
from tools.base import BaseTool
from core.models import QueryScenario, SchemaAnalysis, DomainAnalysis, DifficultyLevel
import uuid


class ScenarioGeneratorInput(BaseModel):
    """场景生成工具输入"""
    schema_analysis: Dict[str, Any] = Field(description="数据库结构分析结果")
    domain_analysis: Dict[str, Any] = Field(description="领域分析结果")
    count: int = Field(default=10, description="生成场景数量")


class ScenarioGenerator(BaseTool):
    """基于规则的场景生成工具"""
    
    @property
    def name(self) -> str:
        return "scenario_generator"
    
    @property
    def description(self) -> str:
        return "基于数据库结构和业务领域，使用规则生成查询场景"
    
    def get_input_schema(self) -> Type[BaseModel]:
        return ScenarioGeneratorInput
    
    def run(self, schema_analysis: Dict[str, Any], 
            domain_analysis: Dict[str, Any], 
            count: int = 10) -> List[QueryScenario]:
        """生成查询场景"""
        scenarios = []
        
        # 获取表信息
        tables = schema_analysis.get("tables", [])
        domain = domain_analysis.get("domain", "general")
        
        # 基于规则生成不同类型的场景
        scenario_types = [
            self._generate_single_table_scenarios,
            self._generate_join_scenarios,
            self._generate_aggregation_scenarios,
            self._generate_time_based_scenarios,
            self._generate_complex_scenarios
        ]
        
        # 平均分配场景数量
        per_type = max(1, count // len(scenario_types))
        
        for generator in scenario_types:
            type_scenarios = generator(tables, domain, per_type)
            scenarios.extend(type_scenarios)
        
        # 确保达到目标数量
        scenarios = scenarios[:count]
        
        self.logger.info(f"Generated {len(scenarios)} scenarios")
        return scenarios
    
    def _generate_single_table_scenarios(self, tables: List[Dict], 
                                       domain: str, count: int) -> List[QueryScenario]:
        """生成单表查询场景"""
        scenarios = []
        
        for i in range(min(count, len(tables))):
            table = tables[i % len(tables)]
            scenario = QueryScenario(
                id=str(uuid.uuid4()),
                category="single_table",
                business_purpose=f"查询{table['name']}表的基本信息",
                data_requirements=[
                    f"从{table['name']}表中检索数据",
                    "支持条件筛选",
                    "可能需要排序"
                ],
                complexity=DifficultyLevel.EASY,
                applicable_tables=[table['name']]
            )
            scenarios.append(scenario)
            
        return scenarios
    
    def _generate_join_scenarios(self, tables: List[Dict], 
                               domain: str, count: int) -> List[QueryScenario]:
        """生成关联查询场景"""
        scenarios = []
        
        # 找出有外键关系的表
        related_tables = []
        for table in tables:
            if table.get("foreign_keys"):
                for fk in table["foreign_keys"]:
                    related_tables.append({
                        "from": table["name"],
                        "to": fk["referred_table"]
                    })
        
        for i in range(min(count, len(related_tables))):
            relation = related_tables[i % len(related_tables)]
            scenario = QueryScenario(
                id=str(uuid.uuid4()),
                category="join",
                business_purpose=f"关联{relation['from']}和{relation['to']}的数据",
                data_requirements=[
                    "需要JOIN操作",
                    "关联多个表的数据",
                    "基于外键关系"
                ],
                complexity=DifficultyLevel.MEDIUM,
                applicable_tables=[relation['from'], relation['to']]
            )
            scenarios.append(scenario)
            
        return scenarios
    
    def _generate_aggregation_scenarios(self, tables: List[Dict], 
                                      domain: str, count: int) -> List[QueryScenario]:
        """生成聚合查询场景"""
        scenarios = []
        
        aggregation_purposes = [
            "统计总数",
            "计算平均值",
            "找出最大/最小值",
            "分组统计",
            "汇总数据"
        ]
        
        for i in range(count):
            table = tables[i % len(tables)]
            purpose = aggregation_purposes[i % len(aggregation_purposes)]
            
            scenario = QueryScenario(
                id=str(uuid.uuid4()),
                category="aggregation",
                business_purpose=f"{purpose} - {table['name']}",
                data_requirements=[
                    "使用聚合函数",
                    "可能需要GROUP BY",
                    "可能需要HAVING子句"
                ],
                complexity=DifficultyLevel.MEDIUM,
                applicable_tables=[table['name']]
            )
            scenarios.append(scenario)
            
        return scenarios
    
    def _generate_time_based_scenarios(self, tables: List[Dict], 
                                     domain: str, count: int) -> List[QueryScenario]:
        """生成时间相关查询场景"""
        scenarios = []
        
        time_patterns = [
            "最近N天",
            "特定时间范围",
            "按月/季度/年统计",
            "时间趋势分析"
        ]
        
        # 找出包含时间字段的表
        time_tables = []
        for table in tables:
            for col in table.get("columns", []):
                if any(t in col.get("type", "").lower() 
                      for t in ["date", "time", "timestamp"]):
                    time_tables.append(table)
                    break
        
        if not time_tables:
            time_tables = tables
            
        for i in range(count):
            table = time_tables[i % len(time_tables)]
            pattern = time_patterns[i % len(time_patterns)]
            
            scenario = QueryScenario(
                id=str(uuid.uuid4()),
                category="time_based",
                business_purpose=f"{pattern}的{table['name']}数据分析",
                data_requirements=[
                    "时间范围筛选",
                    "日期函数使用",
                    "可能需要时间分组"
                ],
                complexity=DifficultyLevel.MEDIUM,
                applicable_tables=[table['name']]
            )
            scenarios.append(scenario)
            
        return scenarios
    
    def _generate_complex_scenarios(self, tables: List[Dict], 
                                  domain: str, count: int) -> List[QueryScenario]:
        """生成复杂查询场景"""
        scenarios = []
        
        complex_patterns = [
            "子查询分析",
            "窗口函数应用",
            "复杂条件组合",
            "多表关联统计"
        ]
        
        for i in range(count):
            # 选择多个表
            num_tables = min(3, len(tables))
            selected_tables = [tables[j]["name"] 
                             for j in range(i, i + num_tables) 
                             if j < len(tables)]
            
            pattern = complex_patterns[i % len(complex_patterns)]
            
            scenario = QueryScenario(
                id=str(uuid.uuid4()),
                category="complex",
                business_purpose=f"{pattern} - 涉及{len(selected_tables)}个表",
                data_requirements=[
                    "复杂SQL结构",
                    "可能包含子查询",
                    "多重条件和逻辑",
                    "高级SQL特性"
                ],
                complexity=DifficultyLevel.HARD,
                applicable_tables=selected_tables[:3]  # 最多3个表
            )
            scenarios.append(scenario)
            
        return scenarios
```

## 5. 总结

这个完整的项目结构设计包含了：

1. **清晰的目录结构**：按功能模块组织
2. **完整的代码实现**：
   - 数据模型定义
   - 基础智能体实现
   - 具体智能体实现
   - 工具基类和示例
   - CLI接口
   - 配置管理
3. **项目配置文件**：
   - setup.py
   - requirements.txt
   - .env.example
   - .gitignore
4. **基于智能体的架构**：
   - ReAct模式实现
   - 工具注册和调用
   - 执行轨迹记录
   - 灵活的任务执行

这个结构完全基于智能体架构，而非流水线架构，符合现代AI Agent的设计理念。