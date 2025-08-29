# SemanticSQL Agent 正确运行指南

## 核心流程理解

你的代码遵循 **数据库分析 → 问题理解 → SQL生成 → 验证执行** 的完整流程：

1. **数据库分析阶段** - 自动提取数据库schema、表结构、字段类型
2. **问题理解阶段** - 分析用户查询意图，理解业务需求
3. **SQL生成阶段** - 基于数据库结构生成合适的SQL查询
4. **验证执行阶段** - 验证SQL语法并安全执行

## 正确的运行命令

### 1. 初始化配置（只需一次）
```bash
python3 main.py init \
  --database-type mysql \
  --host 192.168.200.216 \
  --port 13306 \
  --database testdb \
  --username your_user \
  --password your_password \
  --model Qwen3-14B \
  --base-url http://192.168.200.216:9009/v1
```

### 2. 数据库分析 + 问题查询（核心命令）
```bash
# 单条查询 - 自动完成数据库分析 → 问题理解 → SQL生成 → 执行
python3 main.py run "查询所有用户的注册数量" --config trae_config.yaml --verbose

# 复杂业务查询 - 系统会自动分析业务域和表关系
python3 main.py run "统计2024年每个用户的订单总金额" --config trae_config.yaml --verbose

# 带保存结果的查询
python3 main.py run "找出购买次数最多的前10个用户" \
  --config trae_config.yaml \
  --save-result result.json \
  --save-trajectory analysis_steps.json
```

### 3. 交互式模式（推荐）
```bash
# 进入交互模式，系统会预先分析数据库结构
python3 main.py interactive --config trae_config.yaml --save-history

# 在交互模式中，你可以连续提问：
# → "查看所有表的结构"
# → "统计用户表的总记录数"  
# → "分析订单表中金额最高的记录"
```

### 4. 数据库结构分析（独立分析）
```bash
# 分析整个数据库结构
python3 main.py schema --config trae_config.yaml

# 分析特定表结构
python3 main.py schema --table users --config trae_config.yaml

# 测试数据库连接和分析能力
python3 main.py test --config trae_config.yaml
```

## 实际运行示例

### 示例1：电商数据库分析
```bash
# 1. 配置数据库连接
python3 main.py init \
  --database-type mysql \
  --host 192.168.200.216 \
  --port 13306 \
  --database ecommerce \
  --username admin \
  --password secret

# 2. 查看数据库结构（自动分析）
python3 main.py schema --config trae_config.yaml

# 3. 执行业务查询（自动理解+生成SQL）
python3 main.py run "查询2024年每个月的销售总额" --verbose
python3 main.py run "找出购买金额超过1000元的高端客户" --verbose
```

### 示例2：用户行为分析
```bash
# 分析用户活跃度
python3 main.py run "统计最近7天登录过的用户数量" --verbose

# 分析用户留存
python3 main.py run "查询注册后30天内有过购买行为的用户比例" --verbose

# 复杂关联分析
python3 main.py run "分析每个用户的平均订单金额和购买频次" --verbose
```

## 高级用法

### 批量分析
```bash
# 创建查询文件
 cat > queries.txt << EOF
查询用户表的总记录数
统计订单表中不同状态的数量
找出价格最高的前5个商品
分析每个分类的平均价格
EOF

# 批量执行
while IFS= read -r query; do
  echo "=== 分析: $query ==="
  python3 main.py run "$query" --config trae_config.yaml
  echo ""
done < queries.txt
```

### 调试模式
```bash
# 查看完整分析过程
python3 main.py run "复杂业务查询" \
  --config trae_config.yaml \
  --verbose \
  --max-steps 10 \
  --save-trajectory debug_analysis.json
```

## 流程验证

要验证系统是否正确执行了"数据库分析→问题生成"流程：

1. **检查数据库分析日志**：添加`--verbose`参数查看schema提取过程
2. **检查SQL生成依据**：查看生成的SQL是否基于实际表结构
3. **验证业务理解**：确认系统是否正确理解了查询的业务意图

```bash
# 验证流程
python3 main.py run "查询用户表中邮箱包含gmail的用户数量" \
  --config trae_config.yaml \
  --verbose \
  --save-trajectory flow_verification.json
```

## 环境要求

确保已安装：
```bash
pip install click pyyaml sqlalchemy langchain-community aiomysql aiosqlite asyncpg
```

## 配置文件模板

系统会自动生成`trae_config.yaml`，包含：
- 数据库连接信息
- LLM模型配置  
- 分析工具设置
- 执行参数调优