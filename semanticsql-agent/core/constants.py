"""
系统常量定义
"""

# 支持的数据库类型
SUPPORTED_DATABASES = ["mysql", "postgresql", "sqlite"]

# 默认配置
DEFAULT_MAX_STEPS = 30
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 6000
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 3

# SQL操作类型及描述
SQL_TYPES = {
    "SELECT": "基础查询",
    "JOIN": "关联查询", 
    "GROUP": "聚合查询",
    "SUBQUERY": "子查询",
    "WINDOW": "窗口函数",
    "CTE": "公共表表达式",
    "UNION": "联合查询"
}

# 难度分布
DIFFICULTY_DISTRIBUTION = {
    "easy": 0.3,    # 30% 基础单表查询
    "medium": 0.5,  # 50% 关联和聚合查询
    "hard": 0.2     # 20% 复杂查询和高级特性
}

# 场景类别
SCENARIO_CATEGORIES = [
    "销售分析",
    "库存管理",
    "客户分析",
    "财务报表",
    "订单处理",
    "产品分析",
    "员工管理",
    "供应链管理",
    "营销分析",
    "运营监控"
]

# 字段类型分类
FIELD_TYPES = {
    "identifier": ["id", "code", "no", "key"],
    "timestamp": ["date", "time", "created", "updated", "modified"],
    "numeric": ["amount", "price", "quantity", "count", "total", "sum"],
    "category": ["type", "status", "category", "class", "group"],
    "description": ["name", "title", "description", "comment", "remark"]
}

# 表关系类型
RELATIONSHIP_TYPES = {
    "one-to-one": "一对一",
    "one-to-many": "一对多",
    "many-to-many": "多对多"
}

# 输出格式
OUTPUT_FORMATS = ["json", "jsonl", "csv", "parquet"]

# 日志级别
LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# 执行状态
EXECUTION_STATUS = {
    "running": "运行中",
    "completed": "已完成",
    "failed": "失败",
    "cancelled": "已取消"
}

# 工具类别
TOOL_CATEGORIES = {
    "analysis": "分析工具",
    "generation": "生成工具",
    "validation": "验证工具",
    "reflection": "反思工具"
}

# 质量评分权重
QUALITY_WEIGHTS = {
    "syntax_correctness": 0.3,  # SQL语法正确性
    "semantic_match": 0.3,      # 语义匹配度
    "execution_success": 0.2,   # 执行成功率
    "result_relevance": 0.2     # 结果相关性
}

# 批处理配置
BATCH_SIZE = 10
MAX_BATCH_SIZE = 100

# 缓存配置
CACHE_TTL = 3600  # 1小时
MAX_CACHE_SIZE = 1000

# API限流配置
RATE_LIMIT_PER_MINUTE = 60
RATE_LIMIT_PER_HOUR = 1000

# 文件路径
DEFAULT_CONFIG_PATH = "configs/config.yaml"
DEFAULT_OUTPUT_DIR = "output"
DEFAULT_LOG_DIR = "logs"
DEFAULT_CACHE_DIR = ".cache"

# 提示词模板路径
SYSTEM_PROMPT_PATH = "prompts/system_prompt.yaml"
TOOL_PROMPTS_PATH = "prompts/tool_prompts.yaml"

# 数据集配置
MIN_DATASET_SIZE = 10
MAX_DATASET_SIZE = 10000
DEFAULT_DATASET_SIZE = 100

# 验证配置
SQL_VALIDATION_TIMEOUT = 5  # 秒
SQL_EXECUTION_TIMEOUT = 30  # 秒
MAX_RESULT_ROWS = 1000

# 错误重试配置
MAX_ERROR_RETRIES = 3
RETRY_DELAY = 1  # 秒
RETRY_BACKOFF = 2  # 指数退避因子