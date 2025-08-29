# SemanticSQL Agent 实现指南

## 1. 快速开始

### 1.1 项目定位
SemanticSQL Agent 是一个 **NL2SQL 训练数据生成系统**，通过分析数据库结构自动生成高质量的"自然语言问题-SQL查询"对。

### 1.2 环境准备

#### 基本要求
- Python 3.8+
- 目标数据库（MySQL/PostgreSQL/SQLite）
- Qwen 模型服务（支持 OpenAI API）

#### 安装步骤
```bash
# 1. 克隆项目
git clone <repository-url>
cd semanticsql-agent

# 2. 创建虚拟环境
conda create -n semanticsql python=3.8
conda activate semanticsql

# 3. 安装依赖
pip install click pyyaml sqlalchemy openai
pip install pymysql psycopg2-binary  # 根据数据库类型
```

### 1.3 配置准备

#### 初始化配置
```bash
# 生成配置文件
python main.py init \
    --database-type mysql \
    --host 192.168.200.216 \
    --port 13306 \
    --database testdb \
    --username testuser \
    --password testpass \
    --model Qwen3-14B \
    --base-url http://192.168.200.216:9009/v1 \
    --api-key not-needed
```

#### 配置文件示例
```yaml
# configs/config.yaml
app:
  name: "SemanticSQL Agent"
  version: "2.0.0"
  environment: "production"

database:
  type: "mysql"
  host: "192.168.200.216"
  port: 13306
  database: "testdb"
  username: "testuser"
  password: "testpass"

llm:
  model: "Qwen3-14B"
  base_url: "http://192.168.200.216:9009/v1"
  api_key: "not-needed"
  temperature: 0.7  # 生成多样性
  max_tokens: 2000
```

## 2. 核心功能使用

### 2.1 执行数据生成

#### 基本命令
```bash
# 执行完整的数据库分析和数据生成
python main.py smart-analyze "全面分析这个数据库系统" \
    --config configs/config.yaml \
    --verbose \
    --save-result output/analysis_result.json

# 分阶段查看执行进度
python main.py smart-analyze "为电商系统生成查询场景" \
    --stage-by-stage \
    --save-result ecommerce_scenarios.json
```

#### 执行流程说明
```
执行步骤：
1️⃣ 连接数据库 - 建立连接，获取基本信息
2️⃣ 分析数据库领域 - 识别业务类型（电商/教育/金融等）
3️⃣ 字段分类分析 - 理解每个字段的业务含义
4️⃣ 表结构分析 - 识别核心表和辅助表
5️⃣ ER关系分析 - 分析表之间的关联关系
6️⃣ 场景问题生成 - 生成自然语言问题和SQL对
```

### 2.2 查看分析结果

#### 结果文件结构
```json
{
  "success": true,
  "execution_time": 45.8,
  "steps_taken": 6,
  "final_result": {
    "database_connection": {
      "database": "testdb",
      "type": "mysql",
      "total_tables": 12
    },
    "domain_analysis": {
      "domain": "电子商务",
      "confidence": 0.92,
      "key_entities": ["用户", "商品", "订单"]
    },
    "generated_scenarios": [
      {
        "id": "scenario_001",
        "category": "用户分析",
        "question": "查询最近30天内下单次数超过5次的活跃用户",
        "sql": "SELECT user_id, COUNT(*) as order_count FROM orders WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) GROUP BY user_id HAVING order_count > 5",
        "difficulty": "medium",
        "concepts": ["时间筛选", "分组", "Having条件"]
      }
    ]
  }
}
```

### 2.3 辅助功能

#### 测试数据库连接
```bash
python main.py test --config configs/config.yaml
```

#### 查看数据库结构
```bash
python main.py schema --config configs/config.yaml
```

## 3. 深入理解工作原理

### 3.1 智能体工作流程

#### ReAct 模式示例
```
用户输入: "全面分析这个数据库系统"

Agent 执行过程:
Thought: 我需要先连接数据库了解基本信息
Action: connect_database
Action Input: {}
Observation: 成功连接，发现12个表

Thought: 现在我需要分析这是什么类型的业务系统
Action: analyze_domain
Action Input: {"tables": ["users", "products", "orders", ...]}
Observation: 识别为电子商务系统，置信度0.92

Thought: 接下来分析各个字段的含义
Action: classify_fields
...继续执行直到完成6个步骤
```

### 3.2 领域分析逻辑

#### 领域识别规则
```python
# 电商领域特征
E_COMMERCE_INDICATORS = {
    "tables": ["products", "orders", "cart", "payment"],
    "fields": ["price", "quantity", "shipping", "discount"],
    "patterns": ["user_product", "order_item", "shopping_cart"]
}

# 教育领域特征
EDUCATION_INDICATORS = {
    "tables": ["students", "courses", "grades", "enrollment"],
    "fields": ["score", "semester", "credit", "gpa"],
    "patterns": ["student_course", "teacher_class"]
}
```

### 3.3 场景生成策略

#### 生成模板
```python
SCENARIO_TEMPLATES = {
    "电子商务": {
        "用户分析": [
            "查询活跃用户",
            "用户购买行为统计",
            "用户价值分析"
        ],
        "商品分析": [
            "热销商品排行",
            "库存预警查询",
            "商品类别统计"
        ],
        "订单分析": [
            "订单趋势分析",
            "支付方式统计",
            "物流时效分析"
        ]
    }
}
```

## 4. 高级配置

### 4.1 自定义分析深度

#### Agent 配置
```yaml
agent:
  max_steps: 20  # 增加分析步骤上限
  enable_thinking: true  # 显示思考过程
  verbose: true  # 详细输出
  tools:
    - connect_database
    - analyze_domain
    - classify_fields
    - analyze_tables  # 可选：深度表分析
    - analyze_er
    - generate_scenarios
```

### 4.2 场景生成配置

#### 控制生成数量和难度
```python
# 在代码中配置
GENERATION_CONFIG = {
    "scenarios_per_category": 5,  # 每个类别生成5个场景
    "difficulty_distribution": {
        "easy": 0.3,    # 30% 简单查询
        "medium": 0.5,  # 50% 中等难度
        "hard": 0.2     # 20% 复杂查询
    },
    "max_tables_in_query": 3,  # 最多涉及3个表
    "include_advanced_features": True  # 包含窗口函数等高级特性
}
```

### 4.3 Prompt 优化

#### 自定义系统提示词
```python
CUSTOM_SYSTEM_PROMPT = """你是一个数据库分析和SQL生成专家。

分析任务要求：
1. 深入理解数据库的业务含义
2. 生成真实、实用的查询场景
3. 确保SQL语法正确且高效
4. 覆盖不同难度级别

生成的查询场景应该：
- 贴近实际业务需求
- 问题描述自然流畅
- SQL逻辑清晰准确
- 包含适当的注释说明
"""
```

## 5. 工具开发指南

### 5.1 添加新的分析工具

#### 示例：数据质量分析工具
```python
from tools.trae_base_tool import TraeBaseTool, ToolParameter

class DataQualityTool(TraeBaseTool):
    """分析数据质量"""
    
    def __init__(self, database_config):
        super().__init__(
            name="analyze_data_quality",
            description="分析数据库中的数据质量问题"
        )
        self.db_config = database_config
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="tables",
                type="array",
                description="要分析的表列表",
                required=True
            )
        ]
    
    def run(self, **kwargs) -> Dict[str, Any]:
        tables = kwargs.get("tables", [])
        quality_issues = []
        
        for table in tables:
            # 检查空值
            null_check = self._check_nulls(table)
            # 检查重复
            duplicate_check = self._check_duplicates(table)
            # 检查数据一致性
            consistency_check = self._check_consistency(table)
            
            quality_issues.append({
                "table": table,
                "null_percentage": null_check,
                "duplicate_rows": duplicate_check,
                "consistency_score": consistency_check
            })
        
        return {
            "success": True,
            "quality_analysis": quality_issues,
            "overall_score": self._calculate_score(quality_issues)
        }
```

### 5.2 扩展场景生成

#### 添加领域特定模板
```python
# 金融领域场景模板
FINANCE_TEMPLATES = {
    "风险分析": {
        "template": "查询{time_period}内{risk_type}的{entity}",
        "variables": {
            "time_period": ["最近30天", "本季度", "今年"],
            "risk_type": ["信用风险", "市场风险", "操作风险"],
            "entity": ["客户", "产品", "交易"]
        },
        "sql_pattern": """
        SELECT {columns}
        FROM {main_table}
        WHERE {time_condition}
        AND risk_level > {threshold}
        GROUP BY {group_by}
        """
    }
}
```

## 6. 数据质量保证

### 6.1 SQL 验证

#### 执行前验证
```python
def validate_generated_sql(sql: str, schema: Dict) -> Dict[str, Any]:
    """验证生成的SQL"""
    validation_result = {
        "is_valid": True,
        "errors": [],
        "warnings": []
    }
    
    # 1. 语法检查
    try:
        parsed = sqlparse.parse(sql)[0]
    except:
        validation_result["is_valid"] = False
        validation_result["errors"].append("SQL语法错误")
    
    # 2. 表名验证
    tables_in_sql = extract_table_names(sql)
    for table in tables_in_sql:
        if table not in schema:
            validation_result["errors"].append(f"表 {table} 不存在")
    
    # 3. 字段验证
    # ... 更多验证逻辑
    
    return validation_result
```

### 6.2 场景质量评估

#### 自动评分系统
```python
def score_scenario(scenario: Dict) -> float:
    """对生成的场景进行评分"""
    score = 100.0
    
    # 问题自然度评分
    if len(scenario["question"]) < 10:
        score -= 10  # 问题太短
    
    # SQL 复杂度评分
    sql_complexity = analyze_sql_complexity(scenario["sql"])
    if sql_complexity != scenario["difficulty"]:
        score -= 15  # 难度不匹配
    
    # 业务相关性评分
    if not contains_business_terms(scenario["question"]):
        score -= 20  # 缺乏业务术语
    
    return score / 100.0
```

## 7. 批量处理

### 7.1 多数据库批量分析

```bash
# 批量分析脚本
#!/bin/bash

databases=("ecommerce_db" "education_db" "finance_db")

for db in "${databases[@]}"; do
    echo "分析数据库: $db"
    python main.py smart-analyze "分析 $db 数据库" \
        --config configs/${db}_config.yaml \
        --save-result output/${db}_scenarios.json
done
```

### 7.2 结果合并处理

```python
# merge_results.py
import json
from pathlib import Path

def merge_scenario_files(output_dir: str, merged_file: str):
    """合并多个场景文件"""
    all_scenarios = []
    
    for json_file in Path(output_dir).glob("*_scenarios.json"):
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            scenarios = data.get("final_result", {}).get("generated_scenarios", [])
            
            # 添加来源标记
            for scenario in scenarios:
                scenario["source_db"] = json_file.stem
                
            all_scenarios.extend(scenarios)
    
    # 保存合并结果
    with open(merged_file, 'w', encoding='utf-8') as f:
        json.dump({
            "total_scenarios": len(all_scenarios),
            "scenarios": all_scenarios
        }, f, ensure_ascii=False, indent=2)
```

## 8. 故障排查

### 8.1 常见问题

#### LLM 调用失败
```python
# 测试 LLM 连接
import openai

client = openai.OpenAI(
    base_url="http://192.168.200.216:9009/v1",
    api_key="not-needed"
)

try:
    response = client.chat.completions.create(
        model="Qwen3-14B",
        messages=[{"role": "user", "content": "测试"}]
    )
    print("LLM 连接正常")
except Exception as e:
    print(f"LLM 连接失败: {e}")
```

#### 分析中断处理
```bash
# 启用详细日志
export LOG_LEVEL=DEBUG
python main.py smart-analyze "分析数据库" --verbose

# 查看具体错误
# 通常是因为：
# 1. 表结构过于复杂
# 2. LLM 响应超时
# 3. 数据库连接断开
```

### 8.2 性能优化

#### 大型数据库处理
```python
# 配置优化建议
LARGE_DB_CONFIG = {
    # 限制分析表数量
    "max_tables_to_analyze": 50,
    
    # 采样分析
    "enable_sampling": True,
    "sample_size": 1000,
    
    # 并行处理
    "parallel_analysis": True,
    "worker_threads": 4
}
```

## 9. 最佳实践

### 9.1 数据准备
- 确保数据库有合理的表名和字段名
- 建立明确的外键关系
- 为表和字段添加注释

### 9.2 生成策略
- 先在小型数据库上测试
- 逐步调整生成参数
- 人工审核生成质量

### 9.3 使用建议
- 定期更新场景模板
- 根据实际需求调整难度分布
- 保存高质量的生成结果作为种子数据