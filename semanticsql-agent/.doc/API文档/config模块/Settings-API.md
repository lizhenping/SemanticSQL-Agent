# Settings API 文档

全局配置类，管理 SemanticSQL Agent 的所有配置项。

## 类定义

```python
from pydantic import BaseSettings, Field
from typing import Optional
from semanticsql_agent.config import Settings

class Settings(BaseSettings):
    """
    全局配置
    
    使用 Pydantic BaseSettings 实现，支持环境变量覆盖。
    
    环境变量前缀: SEMANTICSQL_
    """
```

## 配置项

### LLM 配置

```python
# LLM 模型配置
llm_model: str = Field(
    default="Qwen",
    description="LLM 模型名称"
)

llm_base_url: str = Field(
    default="http://localhost:9991/v1",
    description="LLM API 基础 URL（OpenAI 兼容格式）"
)

llm_api_key: str = Field(
    default="dummy",
    description="API Key（本地部署可使用任意值）"
)

llm_temperature: float = Field(
    default=0.7,
    ge=0.0,
    le=2.0,
    description="生成温度，控制输出的随机性"
)

llm_max_tokens: int = Field(
    default=2000,
    ge=1,
    description="最大生成 token 数"
)

llm_timeout: int = Field(
    default=60,
    ge=1,
    description="LLM 调用超时时间（秒）"
)
```

### Agent 配置

```python
# Agent 执行配置
max_iterations: int = Field(
    default=15,
    ge=1,
    le=50,
    description="Agent 最大迭代次数"
)

enable_reflection: bool = Field(
    default=True,
    description="是否启用反思机制"
)

enable_thinking_tool: bool = Field(
    default=True,
    description="是否启用深度思考工具"
)

agent_verbose: bool = Field(
    default=False,
    description="是否输出详细的执行过程"
)
```

### 轨迹记录配置

```python
# 轨迹记录配置
trajectory_dir: str = Field(
    default="./trajectories",
    description="轨迹文件保存目录"
)

save_trajectory: bool = Field(
    default=True,
    description="是否保存执行轨迹"
)

trajectory_format: str = Field(
    default="json",
    regex="^(json|yaml)$",
    description="轨迹文件格式"
)
```

### 日志配置

```python
# 日志配置
log_level: str = Field(
    default="INFO",
    regex="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
    description="日志级别"
)

log_format: str = Field(
    default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    description="日志格式"
)

log_file: Optional[str] = Field(
    default=None,
    description="日志文件路径（None 表示只输出到控制台）"
)
```

## 环境变量支持

```python
class Config:
    """Pydantic 配置"""
    env_prefix = "SEMANTICSQL_"
    env_file = ".env"
    env_file_encoding = "utf-8"
```

### 环境变量示例
```bash
# .env 文件
SEMANTICSQL_LLM_MODEL=Qwen
SEMANTICSQL_LLM_BASE_URL=http://localhost:9991/v1
SEMANTICSQL_LLM_TEMPERATURE=0.5
SEMANTICSQL_MAX_ITERATIONS=20
SEMANTICSQL_ENABLE_REFLECTION=true
```

## 配置加载

### 从环境变量加载
```python
# 自动从环境变量加载
settings = Settings()
```

### 从文件加载
```python
# 从 .env 文件加载
settings = Settings(_env_file=".env")

# 从自定义配置文件
settings = Settings(_env_file="config/production.env")
```

### 程序化配置
```python
# 直接创建配置
settings = Settings(
    llm_temperature=0.3,
    max_iterations=10,
    enable_reflection=False
)
```

## 配置验证

```python
from pydantic import ValidationError
from semanticsql_agent.models.exceptions import (
    InvalidConfigError,
    MissingConfigError
)

# Pydantic 自动验证
try:
    settings = Settings(llm_temperature=3.0)  # 超出范围
except ValidationError as e:
    # 转换为自定义异常
    raise InvalidConfigError(
        config_name="llm_temperature",
        value=3.0,
        expected="0.0 <= value <= 2.0"
    ) from e

# 检查必需配置
if not settings.llm_api_key:
    raise MissingConfigError("llm_api_key")
```

## 使用示例

### 基本使用
```python
from semanticsql_agent.config import Settings

# 加载默认配置
settings = Settings()

print(f"LLM Model: {settings.llm_model}")
print(f"Max iterations: {settings.max_iterations}")
```

### 在 Agent 中使用
```python
from semanticsql_agent.agent import SQLAgent
from semanticsql_agent.config import Settings, DatabaseConfig

# 创建配置
settings = Settings(
    llm_temperature=0.5,
    enable_reflection=True,
    agent_verbose=True
)

db_config = DatabaseConfig(
    host="localhost",
    database="test_db"
)

# 创建 Agent
agent = SQLAgent(settings, db_config)
```

### 动态修改配置
```python
# 创建配置副本并修改
import copy

base_settings = Settings()

# 为特定任务创建修改后的配置
task_settings = copy.deepcopy(base_settings)
task_settings.llm_temperature = 0.3
task_settings.max_iterations = 5
```

## 配置最佳实践

### 1. 环境相关配置
```python
# development.env
SEMANTICSQL_LLM_BASE_URL=http://localhost:9991/v1
SEMANTICSQL_LOG_LEVEL=DEBUG
SEMANTICSQL_AGENT_VERBOSE=true

# production.env  
SEMANTICSQL_LLM_BASE_URL=http://llm-server:9991/v1
SEMANTICSQL_LOG_LEVEL=INFO
SEMANTICSQL_AGENT_VERBOSE=false
```

### 2. 配置分组
```python
def get_query_settings() -> Settings:
    """查询模式的优化配置"""
    return Settings(
        llm_temperature=0.3,
        max_iterations=10,
        enable_reflection=False
    )

def get_analysis_settings() -> Settings:
    """分析模式的配置"""
    return Settings(
        llm_temperature=0.7,
        max_iterations=20,
        enable_reflection=True,
        enable_thinking_tool=True
    )
```

## 扩展配置

```python
# 自定义配置类
class CustomSettings(Settings):
    """扩展的配置类"""
    
    # 添加自定义配置项
    custom_feature: bool = Field(
        default=False,
        description="自定义功能开关"
    )
    
    class Config:
        env_prefix = "SEMANTICSQL_"
```

## 注意事项

1. 环境变量优先级高于默认值
2. 使用 Pydantic 自动类型转换和验证
3. 支持 .env 文件便于本地开发
4. 生产环境建议使用环境变量

---

相关文档：
- [DatabaseConfig API](./DatabaseConfig-API.md)
- [SQLAgent API](../agent模块/SQLAgent-API.md)