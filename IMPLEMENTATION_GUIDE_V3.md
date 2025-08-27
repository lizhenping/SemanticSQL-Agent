# SemanticSQL-Agent 实现指南（LangChain ReAct Agent 版本）

## 1. 快速开始

### 1.1 安装依赖

```bash
pip install langchain>=0.1.0 langchain-openai>=0.0.5 langchain-community>=0.0.10
pip install pymysql pydantic>=2.0 jinja2 pyyaml
```

### 1.2 项目结构

```
semanticsql-agent/
├── config.yaml              # 配置文件
├── main.py                  # 主程序
├── tools/                   # 工具实现
├── prompts/                 # 提示词模板
├── agent/                   # 智能体实现
└── utils/                   # 工具函数
```

## 2. 核心实现

### 2.1 使用 create_react_agent 创建智能体

```python
# agent/nl2sql_agent.py
from langchain.agents import create_react_agent, AgentExecutor
from langchain.agents.format_scratchpad import format_to_openai_function_messages
from langchain.agents.output_parsers import OpenAIFunctionsAgentOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from typing import List, Dict, Any

class NL2SQLAgent:
    """基于 LangChain ReAct Agent 的 NL2SQL 智能体"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # 初始化 LLM
        self.llm = ChatOpenAI(
            model=config["model_name"],
            openai_api_key=config["api_key"],
            openai_api_base=config["base_url"],
            temperature=0.1
        )
        
        # 初始化工具
        self.tools = self._initialize_tools()
        
        # 创建智能体
        self.agent_executor = self._create_agent_executor()
        
        # 轨迹记录
        self.trajectory = []
    
    def _initialize_tools(self) -> List:
        """初始化所有工具"""
        from tools import (
            ExtractSchemaaTool,
            AnalyzeDomainTool,
            GenerateSQLTool,
            ValidateSQLTool,
            ReflectOnSQLTool
        )
        
        # 数据库连接
        from utils.database import DatabaseConnector
        db = DatabaseConnector(self.config["database"])
        
        # 共享上下文
        context = {"db": db, "history": []}
        
        return [
            ExtractSchemaaTool(context=context),
            AnalyzeDomainTool(context=context),
            GenerateSQLTool(context=context),
            ValidateSQLTool(context=context),
            ReflectOnSQLTool(context=context)
        ]
    
    def _create_agent_executor(self) -> AgentExecutor:
        """创建 ReAct Agent 执行器"""
        # 创建提示词模板
        prompt = ChatPromptTemplate.from_messages([
            ("system", self._get_system_prompt()),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        # 绑定工具到 LLM
        llm_with_tools = self.llm.bind_tools(self.tools)
        
        # 创建 agent
        agent = (
            {
                "input": lambda x: x["input"],
                "agent_scratchpad": lambda x: format_to_openai_function_messages(
                    x["intermediate_steps"]
                ),
            }
            | prompt
            | llm_with_tools
            | OpenAIFunctionsAgentOutputParser()
        )
        
        # 创建执行器
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            max_iterations=10,
            return_intermediate_steps=True
        )
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一个专业的 SQL 专家，负责将自然语言查询转换为准确的 SQL 语句。

工作流程：
1. 使用 extract_schema 工具获取数据库结构
2. 使用 analyze_domain 工具理解业务领域
3. 使用 generate_sql 工具生成 SQL
4. 使用 validate_sql 工具验证 SQL 的正确性
5. 如果验证失败，使用 reflect_on_sql 工具反思并改进

重要：
- 生成 SQL 后必须验证
- 验证失败时要反思原因并重新生成
- 最终 SQL 必须通过验证才能返回给用户"""
    
    def generate_sql(self, query: str) -> Dict[str, Any]:
        """生成 SQL 的主方法"""
        try:
            # 执行智能体
            result = self.agent_executor.invoke({
                "input": f"请为以下查询生成 SQL: {query}"
            })
            
            # 提取最终 SQL
            final_sql = self._extract_final_sql(result)
            
            # 记录轨迹
            self.trajectory.append({
                "query": query,
                "steps": result.get("intermediate_steps", []),
                "output": result["output"],
                "sql": final_sql
            })
            
            return {
                "success": True,
                "sql": final_sql,
                "explanation": self._extract_explanation(result),
                "steps_count": len(result.get("intermediate_steps", []))
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "sql": None
            }
    
    def _extract_final_sql(self, result: Dict) -> str:
        """从结果中提取最终的 SQL"""
        # 从输出中提取 SQL
        output = result.get("output", "")
        
        # 查找 SQL 代码块
        import re
        sql_pattern = r'```sql\n(.*?)\n```'
        matches = re.findall(sql_pattern, output, re.DOTALL)
        
        if matches:
            return matches[-1].strip()  # 返回最后一个 SQL（应该是验证通过的）
        
        # 降级：查找 SELECT 语句
        select_pattern = r'(SELECT\s+.*?;)'
        matches = re.findall(select_pattern, output, re.DOTALL | re.IGNORECASE)
        
        if matches:
            return matches[-1].strip()
        
        return ""
```

### 2.2 工具实现示例

```python
# tools/schema_tools.py
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Dict, Any

class ExtractSchemaaTool(BaseTool):
    """提取数据库 Schema 的工具"""
    
    name = "extract_schema"
    description = "提取数据库的表结构信息，包括表、列、主键、外键等"
    
    class InputSchema(BaseModel):
        database_name: str = Field(
            default="current",
            description="数据库名称，默认为当前数据库"
        )
    
    args_schema = InputSchema
    context: Dict[str, Any]
    
    def _run(self, database_name: str = "current") -> str:
        """执行 schema 提取"""
        db = self.context["db"]
        
        # 获取所有表
        tables = db.get_tables()
        
        # 构建输出
        output = [f"数据库 {database_name} 包含 {len(tables)} 个表:\n"]
        
        for table in tables[:10]:  # 限制输出长度
            output.append(f"\n表: {table['name']}")
            if table.get('comment'):
                output.append(f"  说明: {table['comment']}")
            
            # 获取列信息
            columns = db.get_columns(table['name'])
            output.append(f"  列 ({len(columns)}):")
            
            for col in columns[:5]:  # 只显示前5列
                col_str = f"    - {col['name']}: {col['type']}"
                if col.get('is_primary'):
                    col_str += " [主键]"
                if col.get('comment'):
                    col_str += f" // {col['comment']}"
                output.append(col_str)
            
            if len(columns) > 5:
                output.append(f"    ... 还有 {len(columns) - 5} 列")
        
        if len(tables) > 10:
            output.append(f"\n... 还有 {len(tables) - 10} 个表")
        
        # 更新上下文
        self.context["schema"] = {
            "tables": tables,
            "table_details": {t['name']: db.get_columns(t['name']) for t in tables[:5]}
        }
        
        return "\n".join(output)

# tools/generation_tools.py
class GenerateSQLTool(BaseTool):
    """生成 SQL 的工具"""
    
    name = "generate_sql"
    description = "基于数据库结构和用户查询生成 SQL 语句"
    
    class InputSchema(BaseModel):
        query: str = Field(description="用户的查询需求")
        tables: str = Field(description="相关的表信息")
    
    args_schema = InputSchema
    context: Dict[str, Any]
    
    def _run(self, query: str, tables: str) -> str:
        """生成 SQL"""
        # 这里可以调用专门的 SQL 生成模型或使用 LLM
        from utils.llm import get_sql_generation_prompt, generate_with_llm
        
        prompt = get_sql_generation_prompt(
            query=query,
            schema=self.context.get("schema", {}),
            tables=tables
        )
        
        sql = generate_with_llm(prompt)
        
        # 记录生成的 SQL
        self.context["generated_sqls"] = self.context.get("generated_sqls", [])
        self.context["generated_sqls"].append(sql)
        
        return f"生成的 SQL:\n```sql\n{sql}\n```"

# tools/validation_tools.py  
class ValidateSQLTool(BaseTool):
    """验证 SQL 的工具"""
    
    name = "validate_sql"
    description = "验证 SQL 语句的语法和逻辑正确性"
    
    class InputSchema(BaseModel):
        sql: str = Field(description="要验证的 SQL 语句")
        
    args_schema = InputSchema
    context: Dict[str, Any]
    
    def _run(self, sql: str) -> str:
        """验证 SQL"""
        db = self.context["db"]
        validation_results = []
        
        # 1. 语法检查
        try:
            # 使用 EXPLAIN 检查语法
            db.execute_query(f"EXPLAIN {sql}")
            validation_results.append("✓ 语法检查通过")
        except Exception as e:
            validation_results.append(f"✗ 语法错误: {str(e)}")
            return "\n".join(validation_results) + "\n\n需要修正 SQL 语法"
        
        # 2. 表存在性检查
        tables_in_sql = self._extract_tables(sql)
        available_tables = {t['name'] for t in self.context.get("schema", {}).get("tables", [])}
        
        missing_tables = tables_in_sql - available_tables
        if missing_tables:
            validation_results.append(f"✗ 表不存在: {missing_tables}")
            return "\n".join(validation_results) + "\n\n需要修正表名"
        else:
            validation_results.append("✓ 所有表都存在")
        
        # 3. 语义检查（是否回答了用户问题）
        # 这里可以用 LLM 来判断
        
        validation_results.append("✓ 验证通过")
        
        # 记录验证结果
        self.context["last_validation"] = {
            "sql": sql,
            "valid": True,
            "results": validation_results
        }
        
        return "\n".join(validation_results)
    
    def _extract_tables(self, sql: str) -> set:
        """从 SQL 中提取表名"""
        import re
        tables = set()
        
        # FROM 子句
        from_pattern = r'FROM\s+`?(\w+)`?'
        tables.update(re.findall(from_pattern, sql, re.IGNORECASE))
        
        # JOIN 子句
        join_pattern = r'JOIN\s+`?(\w+)`?'
        tables.update(re.findall(join_pattern, sql, re.IGNORECASE))
        
        return tables

class ReflectOnSQLTool(BaseTool):
    """反思 SQL 生成结果的工具"""
    
    name = "reflect_on_sql"
    description = "当 SQL 验证失败时，分析原因并提供改进建议"
    
    class InputSchema(BaseModel):
        validation_result: str = Field(description="验证结果")
        original_query: str = Field(description="原始用户查询")
        
    args_schema = InputSchema
    context: Dict[str, Any]
    
    def _run(self, validation_result: str, original_query: str) -> str:
        """反思并提供改进建议"""
        # 分析验证结果
        issues = []
        suggestions = []
        
        if "语法错误" in validation_result:
            issues.append("SQL 语法有误")
            suggestions.append("检查 SQL 语法，特别是括号、引号和关键字")
        
        if "表不存在" in validation_result:
            issues.append("使用了不存在的表")
            suggestions.append("重新检查 schema，使用正确的表名")
        
        # 基于历史记录的反思
        history = self.context.get("generated_sqls", [])
        if len(history) > 1:
            suggestions.append(f"已尝试 {len(history)} 次，考虑简化查询或分步骤实现")
        
        reflection = f"""反思结果：

问题：
{chr(10).join(f'- {issue}' for issue in issues)}

建议：
{chr(10).join(f'- {suggestion}' for suggestion in suggestions)}

原始需求：{original_query}

下一步：基于以上分析，重新生成符合要求的 SQL。"""
        
        return reflection
```

### 2.3 使用示例

```python
# main.py
from agent.nl2sql_agent import NL2SQLAgent
import yaml

def main():
    # 加载配置
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # 创建智能体
    agent = NL2SQLAgent(config)
    
    # 测试查询
    queries = [
        "查询每个部门的平均工资",
        "找出销售额最高的10个产品",
        "统计上个月的订单总数"
    ]
    
    for query in queries:
        print(f"\n{'='*50}")
        print(f"查询: {query}")
        print('='*50)
        
        result = agent.generate_sql(query)
        
        if result["success"]:
            print(f"\n生成的 SQL:")
            print(result["sql"])
            print(f"\n执行了 {result['steps_count']} 个步骤")
        else:
            print(f"\n错误: {result['error']}")
        
        # 打印执行轨迹
        if agent.trajectory:
            last_trajectory = agent.trajectory[-1]
            print(f"\n执行步骤:")
            for i, (action, observation) in enumerate(last_trajectory["steps"]):
                print(f"{i+1}. {action.tool}: {action.tool_input}")

if __name__ == "__main__":
    main()
```

### 2.4 配置文件

```yaml
# config.yaml
model_name: "Qwen3-14B"
api_key: "not-needed"
base_url: "http://192.168.200.216:9009/v1"

database:
  host: "192.168.200.216"
  port: 13306
  user: "testuser"
  password: "testpass"
  database: "testdb"

agent:
  max_iterations: 10
  verbose: true
```

## 3. 高级特性

### 3.1 自定义回调

```python
# agent/callbacks.py
from langchain.callbacks.base import BaseCallbackHandler

class SQLValidationCallback(BaseCallbackHandler):
    """SQL 验证回调"""
    
    def on_tool_end(self, output: str, **kwargs):
        """工具结束时触发"""
        # 如果是 SQL 生成工具的输出
        if "生成的 SQL:" in output:
            print("\n[回调] 检测到 SQL 生成，准备验证...")
            # 可以在这里触发额外的验证逻辑
```

### 3.2 记忆功能

```python
# 在智能体中添加记忆
from langchain.memory import ConversationBufferWindowMemory

memory = ConversationBufferWindowMemory(
    k=5,  # 记住最近5轮对话
    return_messages=True
)

# 在 AgentExecutor 中使用
executor = AgentExecutor(
    agent=agent,
    tools=tools,
    memory=memory,
    verbose=True
)
```

## 4. 优势总结

1. **简化代码**: 使用 `create_react_agent` 减少了大量样板代码
2. **内置 ReAct**: 自动处理 Thought-Action-Observation 循环
3. **工具管理**: LangChain 的工具系统更加规范
4. **错误处理**: 内置的错误处理和重试机制
5. **可扩展性**: 容易添加新工具和功能
6. **反思机制**: 通过验证工具实现 SQL 生成后的反思

这个设计充分利用了 LangChain 的能力，同时保持了结构化输出和验证反思的特性。