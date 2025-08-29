# SemanticSQL Agent 运行指南

## 安装依赖

```bash
pip install click pyyaml sqlalchemy langchain-community aiomysql aiosqlite asyncpg
```

## 基础运行命令

### 1. 初始化配置
```bash
python main.py init --database-type mysql --host 192.168.200.216 --port 13306 --database testdb --model Qwen3-14B
```

### 2. 单条查询
```bash
python main.py run "查询所有用户的数量" --config trae_config.yaml --verbose
```

### 3. 交互模式
```bash
python main.py interactive --config trae_config.yaml
```

### 4. 查看数据库结构
```bash
# 查看所有表
python main.py schema --config trae_config.yaml

# 查看特定表结构
python main.py schema --table users --config trae_config.yaml
```

### 5. 测试数据库连接
```bash
python main.py test --config trae_config.yaml
```

## 数据库配置示例

### MySQL
```bash
python main.py init \
  --database-type mysql \
  --host 192.168.200.216 \
  --port 13306 \
  --database testdb \
  --user your_user \
  --password your_password \
  --model Qwen3-14B
```

### PostgreSQL
```bash
python main.py init \
  --database-type postgresql \
  --host localhost \
  --port 5432 \
  --database testdb \
  --user your_user \
  --password your_password \
  --model Qwen3-14B
```

### SQLite
```bash
python main.py init \
  --database-type sqlite \
  --database-path /path/to/your/database.db \
  --model Qwen3-14B
```

## 查询示例

### 基础查询
```bash
python main.py run "查询所有用户的姓名和邮箱" --config trae_config.yaml
python main.py run "统计订单总数" --config trae_config.yaml
python main.py run "找出最贵的10个产品" --config trae_config.yaml
```

### 复杂查询
```bash
python main.py run "查询2024年每个月的销售总额" --config trae_config.yaml
python main.py run "找出购买次数最多的前5个用户" --config trae_config.yaml
python main.py run "统计每个分类的平均产品价格" --config trae_config.yaml
```

## 环境变量配置

可以在运行前设置环境变量：

```bash
export LLM_MODEL=Qwen3-14B
export LLM_BASE_URL=http://192.168.200.216:9009/v1
export LLM_API_KEY=your_api_key

export DB_TYPE=mysql
export DB_HOST=192.168.200.216
export DB_PORT=13306
export DB_NAME=testdb
export DB_USER=your_user
export DB_PASSWORD=your_password
```

## 测试运行

### 运行测试套件
```bash
# 配置测试
python -m pytest tests/test_config.py -v

# 工具测试
python -m pytest tests/test_tools.py -v

# 数据库测试
python -m pytest tests/test_database.py -v

# 运行所有测试
python -m pytest tests/ -v
```

## 调试模式

### 开启详细日志
```bash
python main.py run "你的查询" --config trae_config.yaml --verbose --debug
```

### 查看配置文件
```bash
cat trae_config.yaml
```

## 常见问题

### 1. 连接问题
```bash
# 测试连接
python main.py test --config trae_config.yaml

# 检查配置
python main.py init --check-config --config trae_config.yaml
```

### 2. 权限问题
```bash
# 检查数据库权限
python main.py run "SHOW GRANTS" --config trae_config.yaml
```

### 3. 性能优化
```bash
# 使用连接池
python main.py run "你的查询" --config trae_config.yaml --pool-size 10
```

## 高级用法

### 自定义模型参数
```bash
python main.py init \
  --database-type mysql \
  --host 192.168.200.216 \
  --port 13306 \
  --database testdb \
  --model Qwen3-14B \
  --temperature 0.1 \
  --max-tokens 2000 \
  --timeout 30
```

### 批量查询
```bash
# 创建查询文件 queries.txt
echo "查询用户总数
统计订单数量
查找最新产品" > queries.txt

# 批量执行
while IFS= read -r query; do
  python main.py run "$query" --config trae_config.yaml
done < queries.txt
```

## 配置文件模板

生成的 `trae_config.yaml` 示例：

```yaml
app:
  name: "SemanticSQL Agent"
  version: "1.0.0"
  environment: "development"

database:
  type: "mysql"
  host: "192.168.200.216"
  port: 13306
  database: "testdb"
  username: "your_user"
  password: "your_password"
  connection_timeout: 30
  pool_size: 5

llm:
  model: "Qwen3-14B"
  base_url: "http://192.168.200.216:9009/v1"
  api_key: "your_api_key"
  temperature: 0.1
  max_tokens: 2000
  timeout: 30

logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```