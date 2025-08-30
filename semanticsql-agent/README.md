# SemanticSQL Agent 🤖

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

一个基于智能体架构的 NL2SQL 合成数据生成系统，通过 ReAct（Reasoning + Acting）模式自动生成高质量的自然语言到 SQL 查询训练数据。

## ✨ 特性

- 🧠 **智能体驱动**：基于 ReAct 模式的自主任务执行
- 🔧 **模块化工具系统**：分析、生成、验证、反思四大工具类别
- 📊 **完整执行追踪**：详细记录每个执行步骤，支持调试和优化
- 🎯 **多维质量评估**：语法正确性、语义匹配、执行成功率等多维度评分
- 🔄 **自动优化**：通过反思机制持续改进生成质量
- 🌐 **多数据库支持**：MySQL、PostgreSQL、SQLite
- 🤖 **LLM 集成**：支持 OpenAI API 兼容模型（包括 Qwen）

## 🚀 快速开始

### 环境准备

```bash
# 克隆项目
git clone https://github.com/yourusername/semanticsql-agent.git
cd semanticsql-agent

# 创建虚拟环境（推荐使用conda）
conda create -n semanticsql python=3.8
conda activate semanticsql

# 或使用已有环境
source activate alphasql

# 安装依赖
pip install -r requirements.txt
```

### 配置设置

1. 复制环境变量示例文件：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，配置数据库和 LLM：
```bash
# LLM设置
LLM_MODEL=Qwen3-14B
LLM_BASE_URL=http://192.168.200.216:9009/v1
LLM_API_KEY=not-needed

# 数据库设置
DB_TYPE=mysql
DB_HOST=192.168.200.216
DB_PORT=13306
DB_NAME=testdb
DB_USER=testuser
DB_PASSWORD=testpass
```

3. 初始化配置文件：
```bash
python main.py init \
  --database-type mysql \
  --host 192.168.200.216 \
  --port 13306 \
  --database testdb \
  --username testuser \
  --password testpass \
  --model Qwen3-14B \
  --base-url http://192.168.200.216:9009/v1
```

### 基本使用

#### 1. 测试数据库连接
```bash
python main.py test --config configs/config.yaml
```

#### 2. 查看数据库结构
```bash
python main.py schema --config configs/config.yaml
```

#### 3. 生成 NL2SQL 训练数据
```bash
# 生成 100 条训练数据
python main.py generate --count 100 --output dataset.json

# 使用智能分析模式
python main.py smart-analyze "分析数据库并生成查询" --verbose
```

#### 4. 交互式查询
```bash
python main.py interactive --config configs/config.yaml
```

## 📁 项目结构

```
semanticsql-agent/
├── core/               # 核心模块（模型、异常、常量）
├── agent/              # 智能体实现
├── tools/              # 工具系统
│   ├── analysis/       # 分析工具
│   ├── generation/     # 生成工具
│   ├── validation/     # 验证工具
│   └── reflection/     # 反思工具
├── prompts/            # 提示词管理
├── config/             # 配置管理
├── cli/                # 命令行接口
└── utils/              # 工具函数
```

## 🔧 架构设计

### ReAct 执行模式

```
Think（思考） → Act（行动） → Observe（观察） → Reflect（反思）
```

### 数据生成流程

```
1. 数据库分析 → 提取结构、识别领域
2. 场景生成 → 创建业务场景
3. 问题生成 → 生成自然语言问题
4. SQL生成 → 生成对应SQL查询
5. 验证执行 → 语法验证、执行测试
6. 反思优化 → 质量评估、优化建议
```

## 📊 生成数据示例

```json
{
  "question": "查询本月销售额最高的前10个产品及其销售总额",
  "sql": "SELECT product_id, product_name, SUM(amount) as total_sales FROM orders WHERE DATE_FORMAT(order_date, '%Y-%m') = DATE_FORMAT(NOW(), '%Y-%m') GROUP BY product_id, product_name ORDER BY total_sales DESC LIMIT 10;",
  "difficulty": "medium",
  "quality_score": 92.5
}
```

## 🛠️ 高级功能

### 自定义工具

```python
from tools.base_tool import BaseTool

class CustomTool(BaseTool):
    @property
    def name(self):
        return "custom_tool"
    
    def _execute(self, **kwargs):
        # 实现自定义逻辑
        return result
```

### 批量生成

```python
from agent.enhanced_smart_sql_agent import EnhancedSmartSQLAgent
from config.trae_config import TraeConfig

config = TraeConfig.from_yaml("configs/config.yaml")
agent = EnhancedSmartSQLAgent(config)

# 生成数据
examples = await agent.generate_training_data(count=1000)

# 导出为不同格式
json_data = agent.export_training_data(format="json")
openai_data = agent.export_training_data(format="openai")
```

## 📈 性能指标

- **生成速度**：~2秒/样本
- **验证通过率**：>90%
- **质量评分**：平均 85+
- **支持规模**：单次可生成 10,000+ 样本

## 🤝 贡献

欢迎贡献代码！请查看 [CONTRIBUTING.md](docs/CONTRIBUTING.md) 了解详情。

## 📝 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 🙏 致谢

- 感谢 OpenAI 和阿里云通义千问团队提供的 LLM 支持
- 感谢所有贡献者的努力

## 📧 联系方式

- 问题反馈：[GitHub Issues](https://github.com/yourusername/semanticsql-agent/issues)
- 邮件：your-email@example.com

---

**注意**：请确保在使用前正确配置数据库连接和 LLM API，详细配置说明请参考[配置文档](docs/CONFIG.md)。