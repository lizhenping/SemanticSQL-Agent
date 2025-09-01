# SemanticSQL Agent

基于 LangChain 的智能 SQL 训练数据生成系统。

## 快速开始

### 1. 环境准备

```bash
# 激活环境
source activate alphasql

# 安装依赖（如果需要）
pip install -r requirements.txt
```

### 2. 启动 LLM 服务

```bash
# 启动 Qwen3-14B 模型服务
CUDA_VISIBLE_DEVICES=2 vllm serve /root/autodl-tmp/model/Qwen3-14B \
  --host 0.0.0.0 --port 9991 \
  --trust-remote-code \
  --served-model-name "Qwen3-14B"
```

### 3. 配置系统

```bash
# 复制配置文件
cp config.example.yaml config.yaml

# 编辑配置（可选）
vim config.yaml
```

### 4. 生成训练数据

```bash
# 生成 100 条训练数据
python cli.py generate -n 100 -o training_data.jsonl

# 使用配置文件
python cli.py generate -n 50 -c config.yaml -o output.jsonl
```

## 主要功能

### 批量生成训练数据

```bash
# 基本用法
python cli.py generate -n <数量> -o <输出文件>

# 参数说明
-n, --count      生成的数据条数
-o, --output     输出文件路径
-d, --database   数据库名称（可选）
-f, --format     输出格式：json 或 jsonl（默认）
-c, --config     配置文件路径（可选）
-v, --verbose    详细输出模式
```

### 数据库分析

```bash
# 分析数据库结构
python cli.py analyze -d testdb

# 保存分析结果
python cli.py analyze -d testdb -o analysis.json
```

### 生成配置模板

```bash
# 生成配置文件模板
python cli.py config-template > my_config.yaml
```

## 系统配置

### 环境变量

系统支持通过环境变量配置：

```bash
# LLM 配置
export SEMANTICSQL_LLM_MODEL="Qwen3-14B"
export SEMANTICSQL_LLM_BASE_URL="http://127.0.0.1:9991/v1"
export SEMANTICSQL_LLM_TEMPERATURE="0.7"

# 数据库配置
export SEMANTICSQL_DB_HOST="192.168.200.216"
export SEMANTICSQL_DB_PORT="13306"
export SEMANTICSQL_DB_DATABASE="testdb"
export SEMANTICSQL_DB_USERNAME="testuser"
export SEMANTICSQL_DB_PASSWORD="testpass"
```

### 配置文件

参考 `config.example.yaml` 创建自己的配置文件。

## 系统架构

### 工具链

系统包含 14 个专业工具：

- **分析工具** (6个)：数据库结构分析、领域识别、字段分类等
- **生成工具** (4个)：场景选择、操作选择、问题生成、SQL生成
- **验证工具** (2个)：SQL语法验证、执行测试
- **反思工具** (1个)：结果质量评估和问题诊断
- **思考工具** (1个)：深度分析和策略制定

### 执行流程

1. **数据库分析**：一次性分析数据库，结果保存到记忆
2. **问题生成循环**：
   - 选择场景和操作
   - 生成问题和SQL
   - 验证和执行
   - 反思和优化
3. **智能修正**：发现问题时自动回退并修正

## 输出格式

### JSON 格式

```json
{
  "metadata": {...},
  "data": [
    {
      "id": "q_20240115_abc123",
      "question": "查询所有用户的总数",
      "sql": "SELECT COUNT(*) FROM users",
      "scenario": {...},
      "validation": {...},
      "quality_score": 0.95
    }
  ]
}
```

### JSONL 格式

```jsonl
{"id": "q_001", "question": "...", "sql": "...", "timestamp": "..."}
{"id": "q_002", "question": "...", "sql": "...", "timestamp": "..."}
```

## 故障排除

### LLM 服务问题

```bash
# 测试 LLM 服务
curl -X POST http://localhost:9991/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "Qwen3-14B", "messages": [{"role": "user", "content": "Hello"}]}'
```

### 数据库连接问题

```bash
# 测试数据库连接
mysql -h 192.168.200.216 -P 13306 -u testuser -p testdb
```

## 许可证

MIT License

## 更多信息

- 详细命令说明：`.doc/命令行指令.md`
- 架构设计：`.doc/semanticsql-agent_ARCHITECTURE.md`
- API 文档：`.doc/API文档/`