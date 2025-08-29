# SemanticSQL Agent 实现指南

## 1. 快速开始

### 1.1 项目定位
SemanticSQL Agent 是一个 **NL2SQL 训练数据生成系统**，通过六步智能分析流程，基于规则和模板自动生成高质量的"自然语言问题-SQL查询"训练数据对。

### 1.2 环境准备

#### 基本要求
- Python 3.8+
- 目标数据库（MySQL/PostgreSQL/SQLite）
- Qwen 模型服务（支持 OpenAI 兼容 API）

#### 安装步骤
```bash
# 1. 克隆项目
git clone <repository-url>
cd semanticsql-agent

# 2. 创建虚拟环境（推荐使用conda）
conda create -n semanticsql python=3.8
conda activate semanticsql

# 3. 安装依赖
pip install click pyyaml sqlalchemy openai rich tabulate
pip install pymysql  # MySQL
pip install psycopg2-binary  # PostgreSQL
```

### 1.3 配置准备

#### 使用命令行初始化配置
```bash
python main.py init \
    --database-type mysql \
    --host 192.168.200.216 \
    --port 13306 \
    --database testdb \
    --username testuser \
    --password testpass \
    --model Qwen3-14B \
    --base-url http://192.168.200.216:9009/v1 \
    --api-key not-needed \
    --output configs/config.yaml
```

#### 配置文件结构
```yaml
# configs/config.yaml
app:
  name: "SemanticSQL Agent"
  version: "2.0.0"
  environment: "production"
  debug: false

database:
  type: "mysql"
  host: "192.168.200.216"
  port: 13306
  database: "testdb"
  username: "testuser"
  password: "testpass"
  connection_timeout: 30
  pool_size: 5
  echo: false  # 是否打印SQL

llm:
  model: "Qwen3-14B"
  base_url: "http://192.168.200.216:9009/v1"
  api_key: "not-needed"
  temperature: 0.7  # 用于生成多样性
  max_tokens: 2000
  timeout: 30

agent:
  max_steps: 20  # ReAct最大步数
  enable_thinking: true
  enable_reflection: true
  verbose: false
```

## 2. 核心功能使用

### 2.1 执行智能分析（核心命令）

#### 基本用法
```bash
# 执行完整的6步分析流程
python main.py smart-analyze "全面分析这个数据库系统" \
    --config configs/config.yaml \
    --verbose \
    --save-result output/analysis_result.json
```

#### 分阶段显示进度
```bash
# 显示每个步骤的执行情况
python main.py smart-analyze "为电商系统生成查询场景" \
    --config configs/config.yaml \
    --stage-by-stage \
    --save-result ecommerce_scenarios.json
```

#### 六步执行流程
```
📊 开始执行智能分析流程:
   1️⃣ 连接数据库 - 获取基本信息
   2️⃣ 分析数据库领域 - 识别业务类型
   3️⃣ 字段分类分析 - 理解字段含义
   4️⃣ 表结构分析 - 识别核心表
   5️⃣ ER关系分析 - 分析表关系
   6️⃣ 场景问题生成 - 基于规则生成NL-SQL对
```

### 2.2 查看和理解结果

#### 生成的结果文件结构
```json
{
  "success": true,
  "task": "全面分析这个数据库系统",
  "steps_taken": 6,
  "execution_time": 45.8,
  "final_result": {
    "database_connection": {
      "database": "testdb",
      "type": "mysql",
      "total_tables": 12,
      "version": "8.0.23"
    },
    "domain_analysis": {
      "domain": "电子商务",
      "confidence": 0.92,
      "key_entities": ["用户", "商品", "订单", "支付"],
      "domain_features": ["交易流程", "库存管理", "用户体系"]
    },
    "field_classification": {
      "identifiers": ["user_id", "order_id", "product_id"],
      "timestamps": ["created_at", "updated_at", "deleted_at"],
      "amounts": ["price", "total_amount", "discount"],
      "status": ["order_status", "payment_status"],
      "descriptive": ["name", "description", "address"]
    },
    "schema_analysis": {
      "core_tables": {
        "users": "用户主表",
        "orders": "订单主表",
        "products": "商品主表"
      },
      "lookup_tables": {
        "categories": "商品分类",
        "payment_methods": "支付方式"
      }
    },
    "er_analysis": {
      "relationships": [
        {
          "from": "orders.user_id",
          "to": "users.id",
          "type": "many-to-one",
          "description": "订单属于用户"
        }
      ]
    },
    "generated_scenarios": [
      {
        "id": "S001",
        "category": "用户分析",
        "question": "查询最近30天内下单次数超过5次的活跃用户",
        "sql": "SELECT u.id, u.name, COUNT(o.id) as order_count FROM users u INNER JOIN orders o ON u.id = o.user_id WHERE o.created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) GROUP BY u.id, u.name HAVING order_count > 5",
        "difficulty": "medium",
        "concepts": ["JOIN", "时间函数", "GROUP BY", "HAVING"],
        "tables": ["users", "orders"]
      }
    ]
  }
}
```

### 2.3 其他命令

#### 测试数据库连接
```bash
python main.py test --config configs/config.yaml
# 输出：
# ✅ 数据库连接成功!
# 📊 数据库: testdb (mysql)
# 📁 表数量: 12
```

#### 查看数据库结构
```bash
python main.py schema --config configs/config.yaml
# 显示所有表的结构信息
```

#### 交互式模式
```bash
python main.py interactive --config configs/config.yaml
# 进入交互式查询界面
```

## 3. 理解工作原理

### 3.1 ReAct 执行模式

#### 智能体的思考-行动循环
```
示例执行过程:

Thought: 我需要先连接数据库了解基本信息
Action: connect_database
Action Input: {}
Observation: 成功连接MySQL数据库testdb，包含12个表

Thought: 现在我需要分析这是什么类型的业务系统
Action: analyze_domain  
Action Input: {"database_info": {...}}
Observation: 识别为电子商务系统，置信度0.92，关键实体：用户、商品、订单

Thought: 接下来需要对所有字段进行分类
Action: classify_fields
Action Input: {"tables": [...]}
Observation: 完成字段分类，识别出标识符、时间戳、金额等类型

... (继续执行直到完成6个步骤)
```

### 3.2 工具协同机制

#### 工具之间的数据流
```python
# 每个工具的输出会被后续工具使用
Step1_Output (数据库连接) 
    ↓
Step2_Input (领域分析) → Step2_Output
    ↓
Step3_Input (字段分类) → Step3_Output
    ↓
Step4_Input (表分析) → Step4_Output
    ↓
Step5_Input (ER分析) → Step5_Output
    ↓
Step6_Input (场景生成) → 最终结果
```

### 3.3 场景生成机制（基于规则）

#### 规则示例
```python
# 电商领域的场景生成规则
ECOMMERCE_RULES = {
    "用户分析": {
        "活跃用户": {
            "template": "查询{time_period}内{action}的用户",
            "sql_pattern": "SELECT ... FROM users WHERE ...",
            "difficulty": "easy"
        },
        "用户价值": {
            "template": "统计{group}用户的{metric}",
            "sql_pattern": "SELECT ... GROUP BY ...",
            "difficulty": "medium"
        }
    }
}
```

## 4. 高级配置

### 4.1 自定义分析深度

#### 调整Agent行为
```yaml
agent:
  max_steps: 30  # 增加分析步数
  enable_thinking: true  # 显示思考过程
  enable_reflection: true  # 启用反思
  verbose: true  # 详细输出
  # 可选：指定要使用的工具
  tools:
    - connect_database
    - analyze_domain
    - classify_fields
    - analyze_schema
    - analyze_er
    - reasoning  # 额外的推理工具
```

### 4.2 控制场景生成

#### 场景生成参数（在代码中配置）
```python
# 修改 smart_sql_agent.py 中的生成策略
GENERATION_CONFIG = {
    "scenarios_per_category": 10,  # 每个类别生成10个场景
    "difficulty_distribution": {
        "easy": 0.3,    # 30% 简单查询
        "medium": 0.5,  # 50% 中等难度
        "hard": 0.2     # 20% 复杂查询
    },
    "include_features": {
        "joins": True,
        "subqueries": True,
        "window_functions": False,  # 不包含窗口函数
        "cte": False  # 不包含CTE
    }
}
```

### 4.3 环境变量配置

```bash
# .env 文件
# 数据库配置
DB_HOST=192.168.200.216
DB_PORT=13306
DB_NAME=testdb
DB_USER=testuser
DB_PASSWORD=testpass

# LLM配置
LLM_MODEL=Qwen3-14B
LLM_BASE_URL=http://192.168.200.216:9009/v1
LLM_API_KEY=not-needed

# Agent配置
AGENT_MAX_STEPS=20
AGENT_VERBOSE=true
```

## 5. 扩展开发

### 5.1 添加新的分析工具

#### 创建自定义工具
```python
# tools/custom_tools.py
from tools.trae_base_tool import TraeBaseTool, ToolParameter

class DataQualityAnalysisTool(TraeBaseTool):
    """数据质量分析工具"""
    
    def __init__(self, database_config):
        super().__init__(
            name="analyze_data_quality",
            description="分析数据库的数据质量"
        )
        self.db_config = database_config
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="tables",
                type="array",
                description="要分析的表列表",
                required=True
            ),
            ToolParameter(
                name="checks",
                type="array", 
                description="质量检查项",
                required=False
            )
        ]
    
    def run(self, **kwargs) -> Dict[str, Any]:
        tables = kwargs.get("tables", [])
        results = {}
        
        for table in tables:
            # 空值检查
            null_count = self._check_nulls(table)
            # 重复检查
            duplicate_count = self._check_duplicates(table)
            # 数据分布
            distribution = self._analyze_distribution(table)
            
            results[table] = {
                "null_percentage": null_count,
                "duplicate_rows": duplicate_count,
                "data_distribution": distribution
            }
        
        return self.format_result({
            "quality_analysis": results,
            "overall_score": self._calculate_score(results)
        })
```

#### 注册到智能体
```python
# 在 smart_sql_agent.py 的 _initialize_tools 方法中添加
self.register_tool(
    "analyze_data_quality",
    DataQualityAnalysisTool(self.config),
    "分析数据质量"
)
```

### 5.2 添加新的场景生成规则

#### 扩展领域规则
```python
# 添加医疗领域规则
MEDICAL_RULES = {
    "患者分析": {
        "患者统计": {
            "templates": [
                "查询{department}科室的患者数量",
                "统计{disease}疾病的患者分布",
                "分析{time_period}的就诊趋势"
            ],
            "sql_patterns": [
                "SELECT COUNT(*) FROM patients WHERE department = ?",
                "SELECT disease, COUNT(*) FROM diagnoses GROUP BY disease",
                "SELECT DATE(visit_time), COUNT(*) FROM visits WHERE ..."
            ]
        }
    },
    "医生分析": {
        "工作量统计": {
            "templates": [...],
            "sql_patterns": [...]
        }
    }
}

# 在场景生成时应用规则
def generate_scenarios_for_domain(domain, analysis_results):
    if domain == "医疗系统":
        return apply_rules(MEDICAL_RULES, analysis_results)
    elif domain == "电子商务":
        return apply_rules(ECOMMERCE_RULES, analysis_results)
    # ... 更多领域
```

## 6. 质量保证

### 6.1 验证生成的SQL

```python
def validate_generated_sql(sql: str, schema: Dict) -> bool:
    """验证SQL的正确性"""
    try:
        # 1. 语法检查
        parsed = sqlparse.parse(sql)
        if not parsed:
            return False
            
        # 2. 表名验证
        tables_in_sql = extract_table_names(sql)
        for table in tables_in_sql:
            if table not in schema:
                return False
                
        # 3. 试执行（使用EXPLAIN）
        test_sql = f"EXPLAIN {sql}"
        # 执行测试...
        
        return True
    except:
        return False
```

### 6.2 场景质量评分

```python
def score_scenario(scenario: Dict) -> float:
    """对生成的场景评分"""
    score = 100.0
    
    # 问题自然度
    if len(scenario["question"]) < 10:
        score -= 10
    
    # SQL复杂度匹配
    actual_complexity = analyze_sql_complexity(scenario["sql"])
    if actual_complexity != scenario["difficulty"]:
        score -= 20
    
    # 业务相关性
    if not has_business_keywords(scenario["question"]):
        score -= 15
        
    return score / 100.0
```

## 7. 批量处理

### 7.1 批量分析多个数据库

```bash
#!/bin/bash
# batch_analyze.sh

databases=("ecommerce_db" "education_db" "medical_db")

for db in "${databases[@]}"; do
    echo "分析数据库: $db"
    
    # 创建配置
    python main.py init \
        --database $db \
        --output configs/${db}_config.yaml
    
    # 执行分析
    python main.py smart-analyze "分析 $db" \
        --config configs/${db}_config.yaml \
        --save-result results/${db}_scenarios.json
done
```

### 7.2 合并多个结果文件

```python
# merge_results.py
import json
from pathlib import Path

def merge_scenario_files(input_dir: str, output_file: str):
    """合并多个场景文件"""
    all_scenarios = []
    
    for json_file in Path(input_dir).glob("*_scenarios.json"):
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        scenarios = data.get("final_result", {}).get("generated_scenarios", [])
        
        # 添加来源标记
        for scenario in scenarios:
            scenario["source"] = json_file.stem
            
        all_scenarios.extend(scenarios)
    
    # 按难度分组
    grouped = {
        "easy": [],
        "medium": [],
        "hard": []
    }
    
    for scenario in all_scenarios:
        difficulty = scenario.get("difficulty", "medium")
        grouped[difficulty].append(scenario)
    
    # 保存合并结果
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "total_scenarios": len(all_scenarios),
            "by_difficulty": grouped,
            "scenarios": all_scenarios
        }, f, ensure_ascii=False, indent=2)

# 使用
merge_scenario_files("results/", "merged_scenarios.json")
```

## 8. 故障排查

### 8.1 常见问题

#### 问题1：LLM连接失败
```python
# 测试LLM连接
import openai

client = openai.OpenAI(
    base_url="http://192.168.200.216:9009/v1",
    api_key="not-needed"
)

try:
    response = client.chat.completions.create(
        model="Qwen3-14B",
        messages=[{"role": "user", "content": "测试"}],
        max_tokens=10
    )
    print("✅ LLM连接正常")
except Exception as e:
    print(f"❌ LLM连接失败: {e}")
```

#### 问题2：分析中断
```bash
# 启用详细日志定位问题
export LOG_LEVEL=DEBUG
python main.py smart-analyze "分析数据库" --verbose

# 常见原因：
# 1. 表数量过多（超过100个表）
# 2. LLM响应超时（增加timeout配置）
# 3. 数据库连接断开（检查网络）
```

#### 问题3：场景生成数量少
```python
# 检查分析结果
# 可能原因：
# 1. 领域识别失败 - 检查domain_analysis结果
# 2. 表关系复杂度低 - 增加分析深度
# 3. 规则覆盖不足 - 添加更多规则模板
```

### 8.2 性能优化

#### 大型数据库优化
```python
# 配置建议
LARGE_DB_CONFIG = {
    # 限制分析范围
    "max_tables_to_analyze": 50,
    "exclude_tables": ["log_*", "tmp_*"],
    
    # 采样策略
    "enable_sampling": True,
    "sample_rows": 1000,
    
    # 并行处理
    "parallel_workers": 4,
    
    # 缓存策略
    "cache_ttl": 3600
}
```

## 9. 最佳实践

### 9.1 数据准备
1. **规范命名**：表名和字段名要有业务含义
2. **建立关系**：明确的外键关系有助于ER分析
3. **添加注释**：表和字段注释提高分析准确度

### 9.2 使用建议
1. **小规模测试**：先在小数据库上验证
2. **逐步调优**：根据结果调整生成参数
3. **人工审核**：对生成结果进行质量检查
4. **持续改进**：根据反馈优化规则

### 9.3 输出管理
1. **版本控制**：对生成的场景进行版本管理
2. **分类存储**：按领域、难度分类保存
3. **质量标记**：标记高质量的场景作为种子
4. **定期更新**：随业务变化更新场景