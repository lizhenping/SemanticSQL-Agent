# SemanticSQL Agent 实施指南

## 1. 快速开始

### 1.1 环境准备
```bash
# 克隆项目
git clone https://github.com/yourusername/semanticsql-agent.git
cd semanticsql-agent

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -e .
```

### 1.2 配置设置
```bash
# 设置 API Key
export DASHSCOPE_API_KEY="your_qwen_api_key"

# 创建配置文件
cp config/example.yaml config/config.yaml
# 编辑 config/config.yaml 设置数据库连接
```

### 1.3 首次运行
```bash
# 测试数据库连接
semanticsql-agent test-connection

# 运行智能分析
semanticsql-agent smart-analyze --count 10
```

## 2. 核心概念理解

### 2.1 智能体 (Agent)
智能体是系统的核心，它：
- 理解任务目标
- 自主选择工具
- 执行 ReAct 循环
- 生成最终结果

### 2.2 工具 (Tools)
工具是智能体的能力单元：
- 每个工具完成特定功能
- 工具之间相互独立
- 通过智能体协调工作

### 2.3 ReAct 模式
```
Thought（思考） → Action（行动） → Observation（观察）
```
- **Thought**: 分析当前状态，决定下一步
- **Action**: 选择工具并执行
- **Observation**: 观察执行结果

## 3. 开发指南

### 3.1 添加新工具

#### 步骤 1: 创建工具类
```python
# tools/generation/my_tool.py
from tools.base import BaseTool
from typing import Dict, Any

class MyCustomTool(BaseTool):
    """我的自定义工具"""
    
    @property
    def name(self) -> str:
        return "my_custom_tool"
    
    @property
    def description(self) -> str:
        return "执行自定义功能的工具"
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "input_data": {
                            "type": "string",
                            "description": "输入数据"
                        }
                    },
                    "required": ["input_data"]
                }
            }
        }
    
    def run(self, input_data: str) -> Dict[str, Any]:
        """执行工具逻辑"""
        # 实现你的功能
        result = process_data(input_data)
        return {
            "status": "success",
            "result": result
        }
```

#### 步骤 2: 注册工具
```python
# agent/smart_sql_agent.py
def _initialize_tools(self):
    # ... 现有工具
    
    # 添加新工具
    from tools.generation.my_tool import MyCustomTool
    self.register_tool("my_custom_tool", MyCustomTool())
```

### 3.2 自定义智能体行为

#### 创建专用智能体
```python
# agent/custom_agent.py
from agent.base_agent import BaseAgent

class CustomAgent(BaseAgent):
    """自定义智能体"""
    
    def get_system_prompt(self) -> str:
        return """你是一个专门的数据分析智能体。
        
你的特殊能力：
1. 深度数据分析
2. 模式识别
3. 异常检测

使用 ReAct 模式工作，可用工具：
{tools_description}
"""
    
    def _should_finish(self, thought: str) -> bool:
        """自定义完成判断逻辑"""
        # 检查是否包含完成标志
        if "任务完成" in thought or "DONE" in thought:
            return True
        
        # 检查是否达到特定条件
        if self._check_custom_condition():
            return True
            
        return False
    
    def _check_custom_condition(self) -> bool:
        """检查自定义条件"""
        # 实现你的逻辑
        pass
```

### 3.3 扩展数据模型

#### 添加新的数据模型
```python
# core/models.py

class CustomAnalysis(BaseModel):
    """自定义分析结果"""
    analysis_type: str
    findings: List[Dict[str, Any]]
    confidence_scores: Dict[str, float]
    recommendations: List[str]
    
class ExtendedSQL(GeneratedSQL):
    """扩展的 SQL 模型"""
    execution_plan: Optional[str]
    estimated_cost: Optional[float]
    optimization_hints: List[str]
```

## 4. 配置详解

### 4.1 完整配置示例
```yaml
# config/config.yaml

# 数据库配置
database:
  type: mysql                    # 数据库类型: mysql/postgresql/sqlite
  host: localhost               # 数据库地址
  port: 3306                    # 端口
  username: root                # 用户名
  password: ${DB_PASSWORD}      # 密码（支持环境变量）
  database: shop_db             # 数据库名
  # 高级选项
  pool_size: 5                  # 连接池大小
  pool_timeout: 30              # 连接池超时
  echo: false                   # 是否打印 SQL

# LLM 配置
llm:
  model: qwen-plus              # 模型名称
  base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
  api_key: ${DASHSCOPE_API_KEY}
  temperature: 0.7              # 生成温度
  max_tokens: 4096              # 最大 token 数
  timeout: 60                   # 请求超时

# 智能体配置
agent:
  max_steps: 20                 # 最大执行步骤
  enable_reflection: true       # 是否启用反思
  verbose: true                 # 详细日志
  save_trajectory: true         # 保存执行轨迹

# 输出配置
output:
  format: json                  # 输出格式: json/csv/sql
  directory: ./output           # 输出目录
  filename_pattern: "dataset_{timestamp}.{format}"
  
# 生成配置
generation:
  scenarios_per_domain: 10      # 每个领域的场景数
  questions_per_scenario: 5     # 每个场景的问题数
  difficulty_weights:
    easy: 0.3
    medium: 0.5
    hard: 0.2
```

### 4.2 环境变量
```bash
# .env 文件
DASHSCOPE_API_KEY=sk-xxxxx
DB_PASSWORD=your_password
LOG_LEVEL=INFO
SEMANTICSQL_CONFIG_PATH=/path/to/config.yaml
```

## 5. 使用场景

### 5.1 批量生成训练数据
```bash
# 生成大量数据
semanticsql-agent smart-analyze \
    --count 1000 \
    --output-dir ./training_data \
    --format json \
    --parallel 4
```

### 5.2 特定领域数据生成
```python
# custom_generation.py
from semanticsql_agent import SmartSQLAgent
from config.trae_config import TraeConfig

# 自定义配置
config = TraeConfig.from_yaml("config/finance.yaml")

# 创建智能体
agent = SmartSQLAgent(config)

# 生成金融领域数据
result = agent.run(
    task="生成金融交易相关的查询，重点关注：交易统计、风险分析、账户查询",
    constraints={
        "domain": "finance",
        "complexity": ["medium", "hard"],
        "sql_types": ["aggregate", "window", "subquery"]
    }
)
```

### 5.3 增量数据生成
```python
# 基于现有数据集增量生成
existing_dataset = load_dataset("existing_data.json")

result = agent.run(
    task="基于现有数据集，生成更多样化的查询",
    context={
        "existing_patterns": analyze_patterns(existing_dataset),
        "avoid_duplicates": True,
        "focus_on_gaps": identify_gaps(existing_dataset)
    }
)
```

## 6. 最佳实践

### 6.1 工具开发最佳实践

#### 1. 单一职责
```python
# ❌ 错误：工具做太多事情
class ComplexTool(BaseTool):
    def run(self, **kwargs):
        data = self.extract_data()
        analyzed = self.analyze_data(data)
        sql = self.generate_sql(analyzed)
        validated = self.validate_sql(sql)
        return validated

# ✅ 正确：每个工具一个功能
class DataExtractorTool(BaseTool):
    def run(self, **kwargs):
        return self.extract_data()

class SQLGeneratorTool(BaseTool):
    def run(self, data, **kwargs):
        return self.generate_sql(data)
```

#### 2. 明确的输入输出
```python
# ✅ 使用 Pydantic 模型定义清晰的接口
class SQLGeneratorInput(BaseModel):
    question: str
    schema: SchemaAnalysis
    difficulty: str = "medium"

class SQLGeneratorOutput(BaseModel):
    sql: str
    confidence: float
    explanation: str

class SQLGeneratorTool(BaseTool):
    def run(self, **kwargs) -> SQLGeneratorOutput:
        input_data = SQLGeneratorInput(**kwargs)
        # 处理逻辑
        return SQLGeneratorOutput(...)
```

#### 3. 错误处理
```python
class RobustTool(BaseTool):
    def run(self, **kwargs):
        try:
            # 主要逻辑
            result = self.process(**kwargs)
            return {"status": "success", "data": result}
        except ValidationError as e:
            return {"status": "error", "error": f"输入验证失败: {e}"}
        except DatabaseError as e:
            return {"status": "error", "error": f"数据库错误: {e}"}
        except Exception as e:
            self.logger.error(f"未预期的错误: {e}")
            return {"status": "error", "error": "内部错误"}
```

### 6.2 智能体调试技巧

#### 1. 启用详细日志
```python
# 设置日志级别
import logging
logging.basicConfig(level=logging.DEBUG)

# 或在配置中
agent:
  verbose: true
  log_level: DEBUG
```

#### 2. 使用轨迹记录
```python
# 执行后分析轨迹
execution = agent.run(task)

# 打印每个步骤
for step in execution.steps:
    print(f"{step.step_type}: {step.content[:100]}...")
    
# 保存轨迹供分析
with open("execution_trace.json", "w") as f:
    json.dump(execution.to_dict(), f, indent=2)
```

#### 3. 模拟模式
```python
# 使用模拟 LLM 进行测试
class MockLLMClient:
    def chat_completions_create(self, **kwargs):
        # 返回预定义的响应
        return mock_response

agent.llm_client = MockLLMClient()
```

### 6.3 性能优化

#### 1. 批处理
```python
# 批量处理多个数据库
databases = ["db1", "db2", "db3"]
results = []

for db in databases:
    config.database.database = db
    agent = SmartSQLAgent(config)
    result = agent.run(f"分析{db}数据库")
    results.append(result)
```

#### 2. 缓存
```python
from functools import lru_cache

class CachedTool(BaseTool):
    @lru_cache(maxsize=100)
    def _get_schema(self, db_name: str):
        # 缓存数据库结构
        return extract_schema(db_name)
```

#### 3. 异步执行
```python
import asyncio

async def generate_async(agent, task):
    return await agent.arun(task)

# 并发执行多个任务
tasks = [generate_async(agent, t) for t in task_list]
results = await asyncio.gather(*tasks)
```

## 7. 故障排除

### 7.1 常见问题

#### LLM 连接问题
```bash
# 错误：API key 无效
Error: Invalid API key

# 解决方案：
1. 检查环境变量：echo $DASHSCOPE_API_KEY
2. 验证 API key 格式
3. 确认 API key 权限
```

#### 数据库连接失败
```bash
# 错误：无法连接到数据库
Error: Can't connect to MySQL server

# 解决方案：
1. 检查数据库服务：systemctl status mysql
2. 验证连接参数
3. 检查防火墙设置
4. 测试连接：semanticsql-agent test-connection
```

#### 生成质量问题
```python
# 问题：生成的 SQL 质量不高

# 解决方案：
1. 调整温度参数
config.llm.temperature = 0.5  # 降低随机性

2. 增加反思步骤
config.agent.enable_reflection = True

3. 提供更多上下文
agent.run(task, context={"examples": good_examples})
```

### 7.2 调试命令

```bash
# 验证安装
semanticsql-agent --version

# 检查配置
semanticsql-agent config --validate

# 测试单个工具
semanticsql-agent test-tool --name schema_extraction

# 运行诊断
semanticsql-agent diagnose --full
```

## 8. 高级功能

### 8.1 自定义场景规则
```python
# scenarios/custom_rules.py
class CustomScenarioGenerator:
    def generate_scenarios(self, domain: str, schema: SchemaAnalysis):
        scenarios = []
        
        # 基于领域的特定规则
        if domain == "e-commerce":
            scenarios.extend(self._ecommerce_scenarios(schema))
        elif domain == "finance":
            scenarios.extend(self._finance_scenarios(schema))
            
        return scenarios
    
    def _ecommerce_scenarios(self, schema):
        return [
            {
                "name": "hot_products",
                "description": "查询热销商品",
                "tables": ["products", "orders", "order_items"],
                "complexity": "medium"
            },
            # 更多场景...
        ]
```

### 8.2 质量评估
```python
# quality/evaluator.py
class QualityEvaluator:
    def evaluate_dataset(self, dataset: TrainingDataset):
        metrics = {
            "syntax_correctness": self._check_syntax(dataset),
            "semantic_accuracy": self._check_semantics(dataset),
            "diversity_score": self._calculate_diversity(dataset),
            "complexity_distribution": self._analyze_complexity(dataset)
        }
        return metrics
```

### 8.3 导出适配器
```python
# output/adapters.py
class HuggingFaceAdapter:
    """导出为 HuggingFace 数据集格式"""
    def export(self, dataset: TrainingDataset):
        return {
            "version": "1.0",
            "data": [
                {
                    "instruction": example.question.text,
                    "input": "",
                    "output": example.sql.query,
                    "metadata": {
                        "difficulty": example.question.difficulty,
                        "tables": example.sql.tables_used
                    }
                }
                for example in dataset.examples
            ]
        }
```

## 9. 集成指南

### 9.1 与现有 NL2SQL 系统集成
```python
# 作为数据生成服务
from semanticsql_agent import DataGenerationService

service = DataGenerationService(config)

# API 端点
@app.post("/generate")
async def generate_data(request: GenerationRequest):
    result = await service.generate(
        database_config=request.database,
        count=request.count
    )
    return result
```

### 9.2 CI/CD 集成
```yaml
# .github/workflows/generate.yml
name: Generate Training Data

on:
  schedule:
    - cron: '0 2 * * 1'  # 每周一凌晨2点

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Python
        uses: actions/setup-python@v2
        
      - name: Install dependencies
        run: pip install -e .
        
      - name: Generate data
        env:
          DASHSCOPE_API_KEY: ${{ secrets.DASHSCOPE_API_KEY }}
        run: |
          semanticsql-agent smart-analyze \
            --config config/production.yaml \
            --count 500
            
      - name: Upload artifacts
        uses: actions/upload-artifact@v2
        with:
          name: training-data
          path: output/
```

## 10. 维护和监控

### 10.1 日志管理
```python
# 配置日志
import logging.config

LOGGING_CONFIG = {
    'version': 1,
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'semanticsql-agent.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['file']
    }
}

logging.config.dictConfig(LOGGING_CONFIG)
```

### 10.2 性能监控
```python
# 添加监控指标
from prometheus_client import Counter, Histogram

# 定义指标
task_counter = Counter('agent_tasks_total', 'Total tasks executed')
task_duration = Histogram('agent_task_duration_seconds', 'Task duration')
tool_calls = Counter('tool_calls_total', 'Tool calls', ['tool_name'])

# 在代码中使用
@task_duration.time()
def run_task(task):
    task_counter.inc()
    # 执行任务
```

### 10.3 健康检查
```bash
# 健康检查端点
semanticsql-agent health --check all

# 输出示例
{
  "status": "healthy",
  "checks": {
    "database": "ok",
    "llm_api": "ok",
    "disk_space": "ok",
    "memory": "ok"
  }
}
```