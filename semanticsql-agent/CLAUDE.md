# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
SemanticSQL Agent is a natural language to SQL query system built with Python, now fully refactored to follow trae_agent design patterns. It uses an LLM-based agent architecture with ReAct pattern for converting natural language queries into SQL and executing them against databases.

## Core Architecture (trae_agent Style)

### Agent System (`agent/`)
- **BaseAgent (`trae_base_agent.py`)**: Abstract ReAct pattern implementation with tool calling
- **SQLAgent (`sql_agent.py`)**: trae_agent-style SQL query agent
- **AgentState/StepState**: Enum-based state management

### Tools (`tools/`)
- **TraeBaseTool (`trae_base_tool.py`)**: Standardized tool interface base class
- **SchemaExtractionTool**: Database schema analysis
- **SQLGenerationTool**: Natural language to SQL conversion
- **SQLValidationTool**: SQL syntax validation
- **SQLExecutionTool**: Safe query execution
- **DomainAnalysisTool**: Business domain understanding
- **FieldClassificationTool**: Field categorization
- **ERAnalysisTool**: Entity-relationship analysis
- **SequentialThinkingTool**: Multi-step reasoning

### Configuration System (`config/`)
- **TraeConfig**: Unified configuration management
- **DatabaseConfig**: Database connection configuration
- **LLMConfig**: LLM client configuration
- **Environment-based configuration loading**

### Database Management (`database/`)
- **DatabaseManager**: Connection pool management
- **SchemaCache**: Schema caching and refresh
- **QueryExecutor**: Safe query execution with validation

### CLI Interface (`cli/trae_cli.py`)
- **init**: Generate trae_agent-style configuration
- **run**: Execute single query
- **interactive**: REPL-style interactive mode
- **schema**: View database schema
- **test**: Test database connection

## Development Setup

### Dependencies
Install required packages:
```bash
pip install click pyyaml sqlalchemy langchain-community aiomysql aiosqlite asyncpg
```

### Configuration
1. Generate config: `python main.py init`
2. Edit `trae_config.yaml` with database and LLM settings
3. Supports model database configuration from `模型数据库配置.md`

### Running the System

#### Generate Configuration
```bash
python main.py init --database-type mysql --host 192.168.200.216 --port 13306 --database testdb --model Qwen3-14B
```

#### Single Query
```bash
python main.py run "查询所有用户的数量" --config trae_config.yaml --verbose
```

#### Interactive Mode
```bash
python main.py interactive --config trae_config.yaml
```

#### Schema Inspection
```bash
python main.py schema --config trae_config.yaml
python main.py schema --table users --config trae_config.yaml
```

#### Test Connection
```bash
python main.py test --config trae_config.yaml
```

## Key Configuration (trae_agent Style)

### Database Support (from 模型数据库配置.md)
- **MySQL**: `mysql+aiomysql://user:pass@host:port/db`
- **PostgreSQL**: `postgresql+asyncpg://user:pass@host:port/db`
- **SQLite**: `sqlite+aiosqlite:///path/to/db`

### LLM Configuration
- **Model**: Qwen3-14B (configurable)
- **Base URL**: http://192.168.200.216:9009/v1 (configurable)
- **Temperature**: 0.1 (configurable)
- **Max tokens**: 2000 (configurable)

### Environment Variables
- `LLM_MODEL`, `LLM_BASE_URL`, `LLM_API_KEY`
- `DB_TYPE`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- `APP_NAME`, `APP_VERSION`, `ENVIRONMENT`

## Important Files (trae_agent Architecture)

### Core Components
- `agent/trae_base_agent.py`: Abstract BaseAgent implementation
- `agent/sql_agent.py`: SQLAgent with SQLQueryResult
- `config/trae_config.py`: Unified configuration system
- `tools/trae_base_tool.py`: Tool interface base class
- `database/connection_manager.py`: Database connection management

### CLI Commands
- `cli/trae_cli.py`: trae_agent-style CLI interface
- `main.py`: Main entry point

### Configuration Files
- `trae_config.yaml`: trae_agent configuration template
- `config/database_models.py`: Database configuration models

## Testing

### Run Tests
```bash
# 配置测试
python -m pytest tests/test_config.py -v

# 工具测试
python -m pytest tests/test_tools.py -v

# 数据库测试
python -m pytest tests/test_database.py -v
```

### Test Coverage Areas
1. **Configuration loading and validation**
2. **Tool parameter validation and execution**
3. **Database connection management**
4. **Schema caching and refresh**
5. **Query execution and safety validation**

## Architecture Patterns

### trae_agent Design Patterns
1. **Abstract Base Classes**: `BaseAgent`, `TraeBaseTool`
2. **Factory Pattern**: `ToolFactory.create_tools()`
3. **Configuration Management**: Unified `TraeConfig`
4. **Async/Await**: Full async support throughout
5. **Type Safety**: Dataclasses and enums
6. **Error Handling**: Graceful degradation and validation

### Data Flow
1. **CLI → Configuration → Agent → Tools → Database**
2. **Natural Language → ReAct Agent → SQL → Results**
3. **Configuration → Environment Variables → CLI Arguments**

## Extension Points

### Adding New Tools
1. Inherit from `TraeBaseTool`
2. Implement `parameters` and `execute` methods
3. Register in `ToolFactory`

### Adding Database Support
1. Extend `DatabaseType` enum
2. Update connection string builders
3. Add database-specific SQL handlers

### Custom Configuration
1. Extend `TraeConfig` dataclass
2. Add validation logic
3. Update configuration templates

## Performance Considerations

- **Connection Pooling**: Automatic pool management
- **Schema Caching**: TTL-based caching
- **Query Limits**: Configurable row limits
- **Async Execution**: Non-blocking operations

## Security Features

- **SQL Injection Prevention**: Safe query execution
- **Query Validation**: SELECT-only restriction
- **Connection Security**: SSL/TLS support
- **Environment Variables**: Secure configuration loading