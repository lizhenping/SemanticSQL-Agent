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

### generate

```python
@cli.command()
@click.option('--count', '-c', required=True, type=int, help='生成数量')
@click.option('--output', '-o', required=True, help='输出文件路径')
@click.option('--host', '-h', default='localhost', help='数据库主机')
@click.option('--port', '-p', default=3306, help='数据库端口')
@click.option('--database', '-d', required=True, help='数据库名称')
@click.option('--user', '-u', required=True, help='数据库用户名')
@click.option('--password', '-P', prompt=True, hide_input=True, help='数据库密码')
@click.option('--verbose', '-v', is_flag=True, help='显示详细信息')
def generate(count, output, host, port, database, user, password, verbose):
    """
    批量生成训练数据
    
    Example:
        ```bash
        # 生成100条训练数据
        semanticsql generate -c 100 -o training_data.jsonl -d ecommerce -u root
        
        # 详细模式
        semanticsql generate -c 50 -o data.json -d ecommerce -u root -v
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
semanticsql generate -c 100 -o data.json
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
semanticsql generate -c 10 -o data.json -d ecommerce -u root --output-format json
```

```json
{
  "total_count": 10,
  "success_count": 10,
  "failed_count": 0,
  "output_file": "data.json",
  "execution_time": 45.3
}
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
from functools import wraps
from semanticsql_agent.models.exceptions import (
    DatabaseConnectionError,
    LLMError,
    AgentExecutionError,
    SemanticSQLException
)

def handle_errors(func):
    """统一的错误处理装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except DatabaseConnectionError as e:
            click.echo(f"数据库连接失败 [{e.error_code}]: {e.message}", err=True)
            if e.details:
                click.echo(f"详情: {e.details}", err=True)
            sys.exit(1)
        except LLMError as e:
            click.echo(f"LLM错误 [{e.error_code}]: {e.message}", err=True)
            sys.exit(2)
        except AgentExecutionError as e:
            click.echo(f"执行失败 [{e.error_code}]: {e.message}", err=True)
            sys.exit(3)
        except SemanticSQLException as e:
            # 处理所有其他已知异常
            click.echo(f"错误 [{e.error_code}]: {e.message}", err=True)
            sys.exit(4)
        except Exception as e:
            # 未预期的错误
            if click.get_current_context().obj.get('verbose'):
                click.echo(traceback.format_exc(), err=True)
            else:
                click.echo(f"未预期的错误: {e}", err=True)
            sys.exit(5)
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
# 批量生成训练数据脚本

# 生成不同规模的训练数据集
for count in 10 50 100 500; do
    echo "生成 $count 条训练数据..."
    semanticsql generate -c $count -o "training_${count}.json" -d ecommerce -u root
    echo "完成: training_${count}.json"
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

# 生成训练数据
docker run -v $(pwd):/data -it semanticsql generate -c 100 -o /data/training.json -d ecommerce -u root
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