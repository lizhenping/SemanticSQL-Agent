# CLI API 文档

命令行接口，提供 SemanticSQL Agent 的命令行使用方式。

## 模块定义

```python
import click
from semanticsql_agent.config import Settings, DatabaseConfig
from semanticsql_agent.agent import SQLAgent

# CLI 主入口
@click.group()
@click.version_option(version="1.0.0")
def cli():
    """SemanticSQL Agent - 自然语言转 SQL 查询工具"""
    pass
```

## 核心命令

### query

```python
@cli.command()
@click.option('--question', '-q', required=True, help='自然语言查询问题')
@click.option('--host', '-h', default='localhost', help='数据库主机')
@click.option('--port', '-p', default=3306, help='数据库端口')
@click.option('--database', '-d', required=True, help='数据库名称')
@click.option('--user', '-u', required=True, help='数据库用户名')
@click.option('--password', '-P', prompt=True, hide_input=True, help='数据库密码')
@click.option('--execute', '-e', is_flag=True, help='执行生成的 SQL')
@click.option('--verbose', '-v', is_flag=True, help='显示详细信息')
def query(question, host, port, database, user, password, execute, verbose):
    """
    执行单次查询
    
    Example:
        ```bash
        # 基本查询
        semanticsql query -q "查询所有订单" -d ecommerce -u root
        
        # 执行 SQL
        semanticsql query -q "统计本月销售额" -d ecommerce -u root -e
        
        # 详细模式
        semanticsql query -q "查询VIP客户" -d ecommerce -u root -v
        ```
    """
```

### analyze

```python
@cli.command()
@click.option('--host', '-h', default='localhost', help='数据库主机')
@click.option('--database', '-d', required=True, help='数据库名称')
@click.option('--user', '-u', required=True, help='数据库用户名')
@click.option('--password', '-P', prompt=True, hide_input=True, help='数据库密码')
@click.option('--output', '-o', help='分析结果输出文件')
@click.option('--format', '-f', type=click.Choice(['json', 'yaml', 'table']), default='table')
def analyze(host, database, user, password, output, format):
    """
    分析数据库结构
    
    Example:
        ```bash
        # 分析并显示
        semanticsql analyze -d ecommerce -u root
        
        # 保存分析结果
        semanticsql analyze -d ecommerce -u root -o analysis.json -f json
        ```
    """
```

### config

```python
@cli.group()
def config():
    """管理配置"""
    pass

@config.command('init')
@click.option('--force', '-f', is_flag=True, help='覆盖已存在的配置')
def config_init(force):
    """
    初始化配置文件
    
    创建默认的 .env 配置文件
    
    Example:
        ```bash
        semanticsql config init
        ```
    """

@config.command('show')
def config_show():
    """
    显示当前配置
    
    Example:
        ```bash
        semanticsql config show
        ```
    """
```

### server

```python
@cli.command()
@click.option('--host', '-h', default='0.0.0.0', help='服务器主机')
@click.option('--port', '-p', default=8000, help='服务器端口')
@click.option('--reload', is_flag=True, help='自动重载')
def server(host, port, reload):
    """
    启动 API 服务器
    
    Example:
        ```bash
        # 启动服务器
        semanticsql server
        
        # 开发模式
        semanticsql server --reload
        
        # 自定义端口
        semanticsql server -p 8080
        ```
    """
```

## 高级选项

### 全局选项

```python
@cli.option('--config-file', '-c', envvar='SEMANTICSQL_CONFIG', help='配置文件路径')
@cli.option('--log-level', '-l', type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']), default='INFO')
```

### 环境变量支持

```bash
# 通过环境变量设置
export SEMANTICSQL_LLM_BASE_URL=http://localhost:9991/v1
export SEMANTICSQL_DB_HOST=localhost
export SEMANTICSQL_DB_NAME=ecommerce

# 使用环境变量
semanticsql query -q "查询订单"
```

## 交互模式

```python
@cli.command()
@click.option('--database', '-d', required=True, help='数据库名称')
def interactive(database):
    """
    进入交互模式
    
    Example:
        ```bash
        semanticsql interactive -d ecommerce
        
        SemanticSQL> 查询所有订单
        生成的 SQL: SELECT * FROM orders
        
        SemanticSQL> 统计每个客户的订单数
        生成的 SQL: SELECT customer_id, COUNT(*) FROM orders GROUP BY customer_id
        
        SemanticSQL> exit
        ```
    """
```

## 输出格式

### JSON 输出
```bash
semanticsql query -q "查询订单" -d ecommerce -u root --output-format json
```

```json
{
  "question": "查询订单",
  "sql": "SELECT * FROM orders",
  "execution_time": 0.5,
  "success": true
}
```

### 表格输出
```bash
semanticsql query -q "查询订单" -d ecommerce -u root -e
```

```
+----------+-------------+--------+
| order_id | customer_id | total  |
+----------+-------------+--------+
| 1        | 101         | 99.99  |
| 2        | 102         | 149.99 |
+----------+-------------+--------+
2 rows in set (0.05 sec)
```

## 错误处理

```python
def handle_errors(func):
    """错误处理装饰器"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except DatabaseConnectionError as e:
            click.echo(f"数据库连接失败: {e}", err=True)
            sys.exit(1)
        except Exception as e:
            if click.get_current_context().obj.get('verbose'):
                click.echo(traceback.format_exc(), err=True)
            else:
                click.echo(f"错误: {e}", err=True)
            sys.exit(1)
    return wrapper
```

## 插件系统

```python
@cli.command()
@click.option('--plugin', '-p', multiple=True, help='加载插件')
def run_with_plugins(plugin):
    """
    使用插件运行
    
    Example:
        ```bash
        semanticsql query -q "查询" -p custom_tool -p custom_prompt
        ```
    """
```

## 使用示例

### 基本使用流程
```bash
# 1. 初始化配置
semanticsql config init

# 2. 编辑 .env 文件
vim .env

# 3. 测试连接
semanticsql analyze -d ecommerce -u root

# 4. 执行查询
semanticsql query -q "查询本月销售额" -d ecommerce -u root -e

# 5. 启动交互模式
semanticsql interactive -d ecommerce
```

### 脚本集成
```bash
#!/bin/bash
# 批量查询脚本

QUERIES=(
    "统计订单总数"
    "查询今日销售额"
    "列出VIP客户"
)

for query in "${QUERIES[@]}"; do
    echo "执行查询: $query"
    semanticsql query -q "$query" -d ecommerce -u root -e
    echo "---"
done
```

### Docker 使用
```dockerfile
FROM python:3.8

WORKDIR /app
COPY . .
RUN pip install -e .

ENTRYPOINT ["semanticsql"]
```

```bash
# 构建镜像
docker build -t semanticsql .

# 运行查询
docker run -it semanticsql query -q "查询订单" -d ecommerce -u root
```

## 注意事项

1. 密码通过提示输入更安全
2. 支持配置文件和环境变量
3. 详细模式有助于调试
4. 交互模式支持历史记录

---

相关文档：
- [Settings API](./config模块/Settings-API.md)
- [SQLAgent API](./agent模块/SQLAgent-API.md)