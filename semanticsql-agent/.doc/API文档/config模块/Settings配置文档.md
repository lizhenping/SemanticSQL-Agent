# Settings 配置文档

## 概述
`Settings` 类定义了 SemanticSQL Agent 的全局配置参数。使用 Pydantic BaseModel 实现，支持环境变量覆盖和类型验证。

## 类定义
```python
class Settings(BaseModel):
    """全局应用设置"""
```

## 配置分类

### 应用配置
| 参数名 | 类型 | 默认值 | 描述 |
|-------|------|--------|------|
| app_name | str | "SemanticSQL Agent" | 应用名称 |
| app_version | str | "2.0.0" | 应用版本 |
| debug | bool | False | 调试模式 |
| environment | str | "development" | 运行环境 |

### LLM 配置
| 参数名 | 类型 | 默认值 | 描述 |
|-------|------|--------|------|
| llm_model | str | "Qwen3-14B" | 使用的语言模型 |
| llm_base_url | str | "http://127.0.0.1:9991/v1" | LLM API 地址 |
| llm_api_key | str | "not-needed" | API 密钥 |
| llm_temperature | float | 0.1 | 生成温度 |
| llm_max_tokens | int | 20000 | 最大 token 数 |
| llm_timeout | int | 30 | 请求超时时间（秒） |
| llm_max_retries | int | 3 | 最大重试次数 |

### 智能体配置
| 参数名 | 类型 | 默认值 | 描述 |
|-------|------|--------|------|
| max_iterations | int | 20 | 最大迭代次数 |
| max_steps | int | 10 | 每次执行的最大步骤数 |
| enable_reflection | bool | True | 是否启用反思功能 |
| enable_trajectory | bool | True | 是否启用轨迹记录 |
| enable_thinking | bool | True | 是否启用思考工具 |
| verbose | bool | True | 是否输出详细信息 |

### 工具配置
| 参数名 | 类型 | 默认值 | 描述 |
|-------|------|--------|------|
| enabled_tools | List[str] | 见下方 | 启用的工具列表 |

**默认启用的工具：**
- `schema_extraction` - 模式提取
- `domain_analysis` - 领域分析
- `field_classification` - 字段分类
- `er_analysis` - ER 分析
- `sql_generation` - SQL 生成
- `sql_validation` - SQL 验证
- `sql_execution` - SQL 执行
- `sequential_thinking` - 顺序思考

### 生成设置
| 参数名 | 类型 | 默认值 | 描述 |
|-------|------|--------|------|
| scenarios_per_batch | int | 10 | 每批生成的场景数 |
| questions_per_scenario | int | 5 | 每个场景的问题数 |

### 输出设置
| 参数名 | 类型 | 默认值 | 描述 |
|-------|------|--------|------|
| output_directory | str | "./output" | 输出目录 |
| output_format | str | "json" | 输出格式 |
| save_intermediate | bool | False | 是否保存中间结果 |

### 日志配置
| 参数名 | 类型 | 默认值 | 描述 |
|-------|------|--------|------|
| log_level | str | "INFO" | 日志级别 |
| log_format | str | 见下方 | 日志格式 |
| log_file_path | Optional[str] | None | 日志文件路径 |
| log_max_file_size | int | 10MB | 日志文件最大大小 |
| log_backup_count | int | 5 | 日志备份数量 |

**默认日志格式：**
```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

### 轨迹配置
| 参数名 | 类型 | 默认值 | 描述 |
|-------|------|--------|------|
| trajectory_enabled | bool | True | 是否启用轨迹记录 |
| trajectory_directory | str | "trajectories" | 轨迹文件目录 |
| trajectory_max_count | int | 100 | 最大保留轨迹数 |
| trajectory_compress_old | bool | True | 是否压缩旧轨迹 |
| trajectory_include_llm_calls | bool | True | 是否记录 LLM 调用 |
| trajectory_include_tool_calls | bool | True | 是否记录工具调用 |

### 路径配置
| 参数名 | 类型 | 默认值 | 描述 |
|-------|------|--------|------|
| config_dir | str | "config" | 配置文件目录 |
| data_dir | str | "data" | 数据目录 |
| logs_dir | str | "logs" | 日志目录 |

## 使用方式

### 1. 直接创建
```python
from config.settings import Settings

settings = Settings(
    debug=True,
    llm_model="gpt-3.5-turbo",
    llm_temperature=0.7,
    max_steps=15
)
```

### 2. 从环境变量加载
```python
# 设置环境变量
export DEBUG=true
export LLM__MODEL=gpt-4
export LLM__TEMPERATURE=0.5

# 加载配置
settings = Settings()  # 自动从环境变量读取
```

### 3. 从 .env 文件加载
```bash
# .env 文件内容
DEBUG=true
LLM__MODEL=gpt-4
LLM__BASE_URL=https://api.openai.com/v1
LLM__API_KEY=sk-xxxxx
```

```python
settings = Settings()  # 自动加载 .env 文件
```

## 环境变量映射

环境变量使用双下划线 `__` 作为嵌套分隔符：

| 配置参数 | 环境变量名 |
|---------|------------|
| debug | DEBUG |
| llm_model | LLM__MODEL |
| llm_base_url | LLM__BASE_URL |
| llm_temperature | LLM__TEMPERATURE |
| max_steps | MAX_STEPS |

## 配置优先级

1. 代码中直接设置的值
2. 环境变量
3. .env 文件
4. 默认值

## 使用示例

### 开发环境配置
```python
dev_settings = Settings(
    debug=True,
    environment="development",
    llm_model="gpt-3.5-turbo",
    llm_temperature=0.7,
    verbose=True,
    trajectory_enabled=True
)
```

### 生产环境配置
```python
prod_settings = Settings(
    debug=False,
    environment="production",
    llm_model="gpt-4",
    llm_temperature=0.1,
    verbose=False,
    log_level="WARNING",
    trajectory_enabled=False
)
```

### 自定义工具集
```python
settings = Settings(
    enabled_tools=[
        "schema_extraction",
        "sql_generation",
        "sql_validation"
    ]
)
```

### 调整性能参数
```python
settings = Settings(
    max_iterations=30,      # 允许更多迭代
    max_steps=20,           # 增加步骤限制
    llm_timeout=60,         # 增加超时时间
    llm_max_retries=5       # 增加重试次数
)
```

## 验证和错误处理

Settings 类会自动验证配置值：

```python
try:
    settings = Settings(
        llm_temperature=3.0  # 错误：温度值过高
    )
except ValueError as e:
    print(f"配置错误: {e}")
```

## 最佳实践

1. **环境隔离**
   - 为不同环境创建不同的配置文件
   - 使用环境变量管理敏感信息

2. **合理设置限制**
   - 根据任务复杂度调整 max_steps
   - 生产环境适当降低 llm_temperature

3. **日志管理**
   - 开发环境使用 DEBUG 级别
   - 生产环境使用 INFO 或 WARNING

4. **轨迹记录**
   - 开发环境启用完整轨迹
   - 生产环境考虑性能影响

5. **资源管理**
   - 定期清理日志和轨迹文件
   - 监控磁盘空间使用

## 注意事项

1. API 密钥等敏感信息不要硬编码
2. 生产环境关闭 debug 模式
3. 合理设置超时和重试参数
4. 注意 LLM token 限制
5. 定期检查和更新配置