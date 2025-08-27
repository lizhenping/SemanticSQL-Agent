# SemanticSQL-Agent 实现指南（完整版）

## 1. 环境准备

### 1.1 安装依赖

```bash
# 核心依赖
pip install langchain>=0.1.0 langchain-openai>=0.0.5 langchain-community>=0.0.10
pip install langgraph>=0.0.20  # 可选，用于高级流程控制

# 数据库和工具
pip install pymysql sqlalchemy
pip install pydantic>=2.0 jinja2 pyyaml

# 向量存储（用于专有名词检索）
pip install faiss-cpu  # 或 faiss-gpu
```

### 1.2 配置文件

```yaml
# config.yaml
model:
  name: "Qwen3-14B"  # 或 "gpt-4"
  provider: "openai"  # 或 "custom"
  api_key: "${OPENAI_API_KEY}"
  base_url: "http://192.168.200.216:9009/v1"  # vLLM 服务地址
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
  max_results: 10
  enable_retrieval: true
  enable_thinking: true
  verbose: true

memory:
  type: "buffer"
  max_token_limit: 2000

logging:
  level: "INFO"
  file: "logs/semanticsql.log"
```

## 2. 主程序实现

### 2.1 创建 SQL Agent

```python
# main.py
import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any

from agent.sql_agent import SemanticSQLAgent

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """加载配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 处理环境变量
    if "${" in str(config):
        import re
        
        def replace_env_vars(obj):
            if isinstance(obj, dict):
                return {k: replace_env_vars(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_env_vars(item) for item in obj]
            elif isinstance(obj, str):
                # 替换 ${VAR_NAME} 格式的环境变量
                pattern = r'\$\{(\w+)\}'
                return re.sub(
                    pattern,
                    lambda m: os.environ.get(m.group(1), m.group(0)),
                    obj
                )
            return obj
        
        config = replace_env_vars(config)
    
    return config

def main():
    """主函数"""
    # 加载配置
    config = load_config()
    
    # 创建 SQL Agent
    logger.info("初始化 SemanticSQL Agent...")
    agent = SemanticSQLAgent(config)
    
    # 测试查询
    test_queries = [
        "查询所有客户的信息",
        "统计每个部门的平均工资",
        "找出销售额最高的10个产品",
        "分析上个月的订单趋势"
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"查询: {query}")
        print('='*60)
        
        try:
            # 执行查询
            result = agent.query(query)
            
            # 显示结果
            if result["success"]:
                print(f"\nSQL:\n{result['sql']}")
                print(f"\n结果:\n{result['answer']}")
                print(f"\n执行步骤: {result['steps_count']}")
            else:
                print(f"\n错误: {result['error']}")
                
        except Exception as e:
            logger.error(f"查询执行失败: {str(e)}", exc_info=True)
        
        print("\n" + "-"*60)

if __name__ == "__main__":
    main()
```

### 2.2 SQL Agent 完整实现

```python
# agent/sql_agent.py
from langchain.agents import create_react_agent, AgentExecutor
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import MemorySaver
from typing import List, Dict, Any, Optional
import logging

from tools import create_all_tools
from prompts.manager import PromptManager
from agent.callbacks import TrajectoryCallback, ValidationCallback

logger = logging.getLogger(__name__)

class SemanticSQLAgent:
    """基于 LangChain 的 SQL Agent"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        logger.info("初始化数据库连接...")
        self.db = self._init_database()
        
        logger.info("初始化 LLM...")
        self.llm = self._init_llm()
        
        logger.info("初始化记忆系统...")
        self.memory = MemorySaver()
        
        logger.info("创建工具...")
        self.tools = self._create_tools()
        
        logger.info("创建智能体...")
        self.agent_executor = self._create_agent_executor()
        
        # 轨迹记录
        self.trajectory_callback = TrajectoryCallback()
        self.validation_callback = ValidationCallback()
    
    def _init_database(self) -> SQLDatabase:
        """初始化数据库连接"""
        db_config = self.config["database"]
        
        # 构建连接 URI
        uri = (
            f"mysql+pymysql://{db_config['user']}:{db_config['password']}@"
            f"{db_config['host']}:{db_config['port']}/{db_config['database']}"
            f"?charset={db_config.get('charset', 'utf8mb4')}"
        )
        
        db = SQLDatabase.from_uri(uri)
        
        # 测试连接
        tables = db.get_usable_table_names()
        logger.info(f"成功连接数据库，找到 {len(tables)} 个表")
        
        return db
    
    def _init_llm(self):
        """初始化 LLM"""
        model_config = self.config["model"]
        
        # 使用 init_chat_model 支持多种模型
        llm = init_chat_model(
            model_config["name"],
            model_provider=model_config.get("provider", "openai"),
            api_key=model_config.get("api_key"),
            base_url=model_config.get("base_url"),
            temperature=model_config.get("temperature", 0.1),
            max_tokens=model_config.get("max_tokens", 2000)
        )
        
        return llm
    
    def _create_tools(self) -> List:
        """创建工具集合"""
        # 1. 基础 SQL 工具包
        toolkit = SQLDatabaseToolkit(db=self.db, llm=self.llm)
        tools = toolkit.get_tools()
        
        # 2. 添加自定义工具
        custom_tools = create_all_tools(
            db=self.db,
            llm=self.llm,
            config=self.config
        )
        tools.extend(custom_tools)
        
        logger.info(f"创建了 {len(tools)} 个工具")
        for tool in tools:
            logger.info(f"  - {tool.name}: {tool.description[:50]}...")
        
        return tools
    
    def _create_agent_executor(self) -> AgentExecutor:
        """创建智能体执行器"""
        # 获取系统提示词
        pm = PromptManager()
        system_prompt = pm.get_system_prompt(
            "sql_agent",
            dialect=self.db.dialect,
            tables=self.db.get_usable_table_names()[:10],  # 只显示前10个表
            max_results=self.config["agent"].get("max_results", 10)
        )
        
        # 创建 ReAct agent
        agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=system_prompt
        )
        
        # 创建执行器
        executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=self.config["agent"].get("verbose", True),
            max_iterations=self.config["agent"].get("max_iterations", 15),
            handle_parsing_errors=True,
            callbacks=[self.trajectory_callback, self.validation_callback]
        )
        
        return executor
    
    def query(self, question: str, thread_id: Optional[str] = None) -> Dict[str, Any]:
        """执行查询"""
        logger.info(f"执行查询: {question}")
        
        # 配置线程 ID（用于会话记忆）
        config = {
            "configurable": {
                "thread_id": thread_id or f"query_{hash(question)}"
            }
        }
        
        try:
            # 重置回调
            self.trajectory_callback.reset()
            
            # 执行智能体
            result = self.agent_executor.invoke(
                {
                    "input": question,
                    "chat_history": []  # 可以传入历史对话
                },
                config
            )
            
            # 提取结果
            sql = self._extract_sql(result)
            answer = result.get("output", "")
            
            # 获取执行轨迹
            trajectory = self.trajectory_callback.get_trajectory()
            
            return {
                "success": True,
                "question": question,
                "sql": sql,
                "answer": answer,
                "steps_count": len(trajectory["steps"]),
                "trajectory": trajectory
            }
            
        except Exception as e:
            logger.error(f"查询执行失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "question": question,
                "error": str(e),
                "sql": None,
                "answer": None
            }
    
    def _extract_sql(self, result: Dict[str, Any]) -> Optional[str]:
        """从结果中提取 SQL"""
        output = result.get("output", "")
        
        # 查找 SQL 代码块
        import re
        sql_pattern = r'```sql\n(.*?)\n```'
        matches = re.findall(sql_pattern, output, re.DOTALL)
        
        if matches:
            # 返回最后一个 SQL（应该是最终版本）
            return matches[-1].strip()
        
        # 备选方案：查找 SELECT/INSERT/UPDATE 等语句
        sql_keywords = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'WITH']
        for keyword in sql_keywords:
            pattern = rf'({keyword}\s+.*?)(?:;|$)'
            match = re.search(pattern, output, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        
        return None
    
    def stream_query(self, question: str, thread_id: Optional[str] = None):
        """流式执行查询"""
        config = {
            "configurable": {
                "thread_id": thread_id or f"query_{hash(question)}"
            }
        }
        
        # 流式输出
        for step in self.agent_executor.stream(
            {"input": question},
            config,
            stream_mode="values"
        ):
            yield step
```

## 3. 工具实现

### 3.1 工具工厂函数

```python
# tools/__init__.py
from typing import List, Dict, Any
from langchain.tools import BaseTool

from .sql_tools import create_sql_tools
from .analysis_tools import create_analysis_tools
from .validation_tools import create_validation_tools
from .retrieval_tools import create_retrieval_tools
from .thinking_tools import create_thinking_tools

def create_all_tools(db, llm, config: Dict[str, Any]) -> List[BaseTool]:
    """创建所有工具"""
    tools = []
    
    # SQL 工具（已由 SQLDatabaseToolkit 提供）
    # 这里可以添加自定义的 SQL 工具
    
    # 分析工具
    tools.extend(create_analysis_tools(db, llm))
    
    # 验证工具
    tools.extend(create_validation_tools(db, llm))
    
    # 检索工具
    if config["agent"].get("enable_retrieval", True):
        tools.extend(create_retrieval_tools(db, llm))
    
    # 思考工具
    if config["agent"].get("enable_thinking", True):
        tools.extend(create_thinking_tools(llm))
    
    return tools
```

### 3.2 分析工具集实现

```python
# tools/analysis_tools/__init__.py
from typing import List
from langchain.tools import BaseTool

from .schema_extraction_tool import SchemaExtractionTool
from .domain_analysis_tool import DomainAnalysisTool
from .field_classification_tool import FieldClassificationTool
from .table_description_tool import TableDescriptionTool
from .column_description_tool import ColumnDescriptionTool
from .er_analysis_tool import ERAnalysisTool

def create_analysis_tools(db, llm) -> List[BaseTool]:
    """创建分析工具集"""
    return [
        SchemaExtractionTool(db=db),
        DomainAnalysisTool(db=db, llm=llm),
        FieldClassificationTool(db=db, llm=llm),
        TableDescriptionTool(db=db, llm=llm),
        ColumnDescriptionTool(db=db, llm=llm),
        ERAnalysisTool(db=db, llm=llm)
    ]
```

## 4. 回调实现

### 4.1 轨迹记录回调

```python
# agent/callbacks.py
from langchain.callbacks.base import BaseCallbackHandler
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

class TrajectoryCallback(BaseCallbackHandler):
    """轨迹记录回调"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """重置轨迹"""
        self.trajectory = {
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "steps": [],
            "tool_calls": [],
            "thoughts": [],
            "errors": []
        }
        self.current_step = None
    
    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs
    ):
        """LLM 开始思考"""
        thought = {
            "timestamp": datetime.now().isoformat(),
            "type": "thinking",
            "prompt_preview": prompts[0][:500] if prompts else ""
        }
        self.trajectory["thoughts"].append(thought)
    
    def on_llm_end(self, response, **kwargs):
        """LLM 结束思考"""
        if self.trajectory["thoughts"]:
            self.trajectory["thoughts"][-1]["response_preview"] = (
                str(response)[:500] if response else ""
            )
    
    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        **kwargs
    ):
        """工具开始执行"""
        tool_call = {
            "timestamp": datetime.now().isoformat(),
            "tool": serialized.get("name", "unknown"),
            "input": input_str,
            "status": "started"
        }
        self.trajectory["tool_calls"].append(tool_call)
        self.current_step = tool_call
    
    def on_tool_end(self, output: str, **kwargs):
        """工具执行结束"""
        if self.current_step:
            self.current_step.update({
                "output": output[:1000],  # 限制输出长度
                "status": "completed",
                "end_time": datetime.now().isoformat()
            })
            
            # 添加到步骤
            self.trajectory["steps"].append({
                "type": "tool_execution",
                "tool": self.current_step["tool"],
                "timestamp": self.current_step["timestamp"],
                "duration": self._calculate_duration(
                    self.current_step["timestamp"],
                    self.current_step["end_time"]
                )
            })
            
            self.current_step = None
    
    def on_tool_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        **kwargs
    ):
        """工具执行错误"""
        error_info = {
            "timestamp": datetime.now().isoformat(),
            "tool": self.current_step["tool"] if self.current_step else "unknown",
            "error": str(error),
            "type": type(error).__name__
        }
        self.trajectory["errors"].append(error_info)
        
        if self.current_step:
            self.current_step["status"] = "failed"
            self.current_step["error"] = str(error)
    
    def on_agent_action(self, action, **kwargs):
        """智能体执行动作"""
        self.trajectory["steps"].append({
            "type": "agent_action",
            "timestamp": datetime.now().isoformat(),
            "action": action.tool,
            "input": str(action.tool_input)[:500],
            "log": action.log[:500] if hasattr(action, 'log') else ""
        })
    
    def on_agent_finish(self, finish, **kwargs):
        """智能体完成"""
        self.trajectory["end_time"] = datetime.now().isoformat()
        self.trajectory["final_output"] = str(finish)[:1000]
    
    def get_trajectory(self) -> Dict[str, Any]:
        """获取轨迹"""
        return self.trajectory
    
    def save_trajectory(self, filepath: str):
        """保存轨迹到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.trajectory, f, ensure_ascii=False, indent=2)
    
    def _calculate_duration(self, start: str, end: str) -> float:
        """计算持续时间"""
        from datetime import datetime
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
        return (end_dt - start_dt).total_seconds()

class ValidationCallback(BaseCallbackHandler):
    """SQL 验证回调"""
    
    def __init__(self):
        self.sql_generated = False
        self.validation_triggered = False
    
    def on_tool_end(self, output: str, **kwargs):
        """工具结束时检查"""
        # 检测 SQL 生成
        if "```sql" in output.lower() or "sql" in output.lower():
            self.sql_generated = True
            logger.info("检测到 SQL 生成，准备触发验证")
            
            # 提取 SQL
            import re
            sql_match = re.search(r'```sql\n(.*?)\n```', output, re.DOTALL)
            if sql_match:
                sql = sql_match.group(1)
                logger.info(f"提取的 SQL: {sql[:100]}...")
                
                # 这里可以触发额外的验证逻辑
                # 例如：发送到验证队列
```

## 5. 命令行界面

### 5.1 交互式 CLI

```python
# cli.py
import click
import yaml
from pathlib import Path
from typing import Optional
import readline  # 支持命令历史

from agent.sql_agent import SemanticSQLAgent

# 配置命令历史
histfile = Path.home() / '.semanticsql_history'
try:
    readline.read_history_file(histfile)
except FileNotFoundError:
    pass

@click.group()
def cli():
    """SemanticSQL Agent 命令行工具"""
    pass

@cli.command()
@click.option('--config', '-c', default='config.yaml', help='配置文件路径')
@click.option('--verbose', '-v', is_flag=True, help='详细输出')
def interactive(config: str, verbose: bool):
    """交互式查询模式"""
    # 加载配置
    with open(config, 'r') as f:
        cfg = yaml.safe_load(f)
    
    if verbose:
        cfg['agent']['verbose'] = True
    
    # 创建 agent
    click.echo("初始化 SemanticSQL Agent...")
    agent = SemanticSQLAgent(cfg)
    click.echo("Agent 初始化完成！\n")
    
    # 显示帮助
    click.echo("欢迎使用 SemanticSQL Agent！")
    click.echo("输入自然语言查询，或使用以下命令：")
    click.echo("  /help    - 显示帮助")
    click.echo("  /tables  - 显示所有表")
    click.echo("  /schema <table> - 显示表结构")
    click.echo("  /save <file> - 保存查询历史")
    click.echo("  /exit    - 退出\n")
    
    # 会话 ID
    thread_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    while True:
        try:
            # 获取输入
            query = click.prompt('\nSQL>', type=str)
            
            # 处理命令
            if query.startswith('/'):
                handle_command(query, agent)
                continue
            
            if query.lower() in ['exit', 'quit']:
                break
            
            # 执行查询
            click.echo("\n处理中...")
            result = agent.query(query, thread_id)
            
            # 显示结果
            if result['success']:
                click.echo(f"\n生成的 SQL:")
                click.echo(click.style(result['sql'], fg='green'))
                
                click.echo(f"\n结果:")
                click.echo(result['answer'])
                
                if verbose:
                    click.echo(f"\n执行了 {result['steps_count']} 个步骤")
            else:
                click.echo(click.style(f"\n错误: {result['error']}", fg='red'))
        
        except KeyboardInterrupt:
            click.echo("\n使用 /exit 退出")
            continue
        except Exception as e:
            click.echo(click.style(f"\n发生错误: {str(e)}", fg='red'))
    
    # 保存历史
    readline.write_history_file(histfile)
    click.echo("\n再见！")

@cli.command()
@click.option('--config', '-c', default='config.yaml', help='配置文件路径')
@click.argument('query')
def query(config: str, query: str):
    """执行单个查询"""
    # 加载配置
    with open(config, 'r') as f:
        cfg = yaml.safe_load(f)
    
    # 创建 agent
    agent = SemanticSQLAgent(cfg)
    
    # 执行查询
    result = agent.query(query)
    
    # 输出结果
    if result['success']:
        click.echo(f"SQL: {result['sql']}")
        click.echo(f"结果: {result['answer']}")
    else:
        click.echo(f"错误: {result['error']}")

def handle_command(command: str, agent: SemanticSQLAgent):
    """处理特殊命令"""
    parts = command.split()
    cmd = parts[0]
    
    if cmd == '/help':
        click.echo("可用命令：")
        click.echo("  /tables - 显示所有表")
        click.echo("  /schema <table> - 显示表结构")
        click.echo("  /save <file> - 保存查询历史")
        click.echo("  /exit - 退出")
    
    elif cmd == '/tables':
        tables = agent.db.get_usable_table_names()
        click.echo(f"数据库包含 {len(tables)} 个表：")
        for table in tables:
            click.echo(f"  - {table}")
    
    elif cmd == '/schema' and len(parts) > 1:
        table = parts[1]
        try:
            schema = agent.db.get_table_info([table])
            click.echo(schema)
        except Exception as e:
            click.echo(f"错误: {str(e)}")
    
    elif cmd == '/save' and len(parts) > 1:
        filename = parts[1]
        # TODO: 实现保存逻辑
        click.echo(f"保存到 {filename}")
    
    else:
        click.echo("未知命令。使用 /help 查看帮助。")

if __name__ == '__main__':
    cli()
```

## 6. 使用示例

### 6.1 基础查询

```python
# examples/basic_usage.py
from agent.sql_agent import SemanticSQLAgent
import yaml

# 加载配置
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# 创建 agent
agent = SemanticSQLAgent(config)

# 简单查询
result = agent.query("显示所有员工信息")
print(f"SQL: {result['sql']}")
print(f"答案: {result['answer']}")

# 复杂查询
result = agent.query(
    "分析每个部门的平均工资，并找出高于公司平均工资的部门"
)
print(f"SQL: {result['sql']}")
```

### 6.2 流式输出

```python
# examples/streaming.py
# 流式查询
for step in agent.stream_query("查找最近一个月的订单趋势"):
    if "messages" in step:
        step["messages"][-1].pretty_print()
```

### 6.3 带审核的查询链

```python
# examples/query_chain.py
from agent.query_chain import QueryChain
from langgraph.checkpoint.memory import MemorySaver

# 创建查询链
chain = QueryChain(agent.db, agent.llm)
graph = chain.create_chain(with_approval=True)

# 配置记忆
memory = MemorySaver()
config = {"configurable": {"thread_id": "review_001"}}

# 执行到审核点
state = graph.invoke(
    {"question": "更新所有产品价格增加10%"},
    config
)

print("生成的 SQL:", state.get("query"))

# 人工审核
if input("是否执行？(y/n): ").lower() == 'y':
    # 继续执行
    final_state = graph.invoke(None, config)
    print("执行结果:", final_state.get("result"))
else:
    print("查询已取消")
```

## 7. 最佳实践

### 7.1 错误处理

```python
try:
    result = agent.query("复杂查询")
except Exception as e:
    logger.error(f"查询失败: {e}")
    # 降级处理
```

### 7.2 性能优化

1. **使用连接池**
2. **缓存常用查询**
3. **限制返回结果**
4. **使用索引提示**

### 7.3 安全考虑

1. **SQL 注入防护**
2. **权限控制**
3. **敏感数据脱敏**
4. **审计日志**

这个实现指南提供了完整的代码示例，展示了如何使用 LangChain 的 `create_react_agent` 构建 SQL Agent，包括：

1. 基于 LangChain 官方示例的架构
2. 完整的工具分类和实现
3. 轨迹记录和验证回调
4. 交互式命令行界面
5. 实际使用示例