# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
SemanticSQL Agent is a natural language to SQL query system built with Python, refactored to follow trae_agent design patterns. It uses an LLM-based agent architecture with ReAct pattern for converting natural language queries into SQL and executing them against databases.
我的conda 环境是：source activate alphasql
模型数据库配置是
--model "Qwen3-14B"
--api-key "not-needed"
--base-url "http://192.168.200.216:9991/v1"
--host "192.168.200.216" --port "13306" --user "testuser"
--password "testpass" --database "testdb"
generate --count "20" --output "test_ddd.json"
## Core Architecture (trae_agent Style)

### Agent System (`agent/`)
- **BaseAgent (`base_agent.py`)**: Abstract ReAct pattern implementation with tool calling
- **SQLAgent (`sql_agent.py`)**: Synchronous SQL query agent with `SQLQueryResult` response format
- **SyncSQLAgent (`sync_sql_agent.py`)**: Alternative synchronous implementation
- **AgentExecution/AgentStep**: State management classes

### Tools (`tools/`)
- **TraeBaseTool (`trae_base_tool.py`)**: Standardized tool interface with `ToolParameter` definitions
- **Schema Tools**: `SyncSchemaExtractionTool` for database structure analysis
- **SQL Tools**: `SyncSQLGenerationTool`, `SyncSQLValidationTool`, `SyncSQLExecutionTool`
- **Analysis Tools**: Domain analysis, field classification, ER analysis, sequential thinking
- All tools follow sync/async patterns with consistent naming

### Configuration System (`config/`)
- **TraeConfig (`trae_config.py`)**: Main configuration dataclass with nested configs
- **DatabaseConfig**: Database connection and pool settings
- **LLMConfig**: LLM client parameters (model, base_url, temperature, etc.)
- **AgentConfig**: Agent-specific settings
- Environment variable loading with fallback to defaults

### Database Management (`database/`)
- **ConnectionManager**: Async database connection handling
- Connection pooling and lifecycle management
- Database support (MySQL)

## Development Commands

### Essential Commands
```bash
# Install dependencies
pip install click pyyaml sqlalchemy langchain-community aiomysql aiosqlite asyncpg

# Initialize configuration
python main.py init --database-type mysql --host 192.168.200.216 --port 13306 --database testdb --model Qwen3-14B

# Run single query
python main.py run "查询所有用户的数量" --config trae_config.yaml --verbose

# Interactive mode
python main.py interactive --config trae_config.yaml

# Test database connection
python main.py test --config trae_config.yaml

# View schema
python main.py schema --config trae_config.yaml
```

### Testing
```bash
# Run specific tests
python -m pytest tests/test_config.py -v

# Run all tests
python -m pytest tests/ -v
```

### Quick Development Flow
```bash
# 1. Generate config
python main.py init --database-type mysql --host localhost --port 3306 --database mydb --model Qwen3-14B

# 2. Test connection
python main.py test --config trae_config.yaml

# 3. Verify schema
python main.py schema --config trae_config.yaml

# 4. Test query
python main.py run "count users" --config trae_config.yaml --verbose
```

## Code Architecture Patterns

### Data Flow (Three-Step Process)
1. **Database Connection** (`database/connection_manager.py`): 
   - `DatabaseManager` handles connection pooling and validation
   - Supports MySQL, PostgreSQL, SQLite with async/await patterns

2. **Schema Analysis** (`tools/sql_tools.py`):
   - `SyncSchemaExtractionTool` extracts table structures and relationships
   - Caches schema information for performance

3. **Query Generation** (`agent/sql_agent.py`):
   - `SQLAgent` coordinates tool execution using ReAct pattern
   - Returns `SQLQueryResult` with structured response data

### Tool System Design
- All tools inherit from `TraeBaseTool` with standardized interfaces
- Tools use `ToolParameter` for type-safe parameter definitions
- Consistent sync/async patterns across tool implementations
- Factory pattern for tool creation and registration

### Configuration Hierarchy
```
TraeConfig (root)
├── DatabaseConfig (connection settings)
├── LLMConfig (model parameters)  
├── AgentConfig (agent behavior)
└── Environment variable overrides
```

## Key Implementation Details

### Entry Point
- `main.py` → `cli/cli.py` → Command handlers
- All CLI commands route through unified configuration loading

### Agent Execution Flow
1. Load configuration from YAML + environment variables
2. Initialize `DatabaseManager` and test connection
3. Create tool instances with database config
4. Execute ReAct loop: Observe → Think → Act → Repeat
5. Return structured `SQLQueryResult`

## Configuration Reference

### Database Configuration
- **MySQL**: `mysql+aiomysql://user:pass@host:port/db`

### Environment Variables
```bash
# LLM Settings
LLM_MODEL=Qwen3-14B
LLM_BASE_URL=http://192.168.200.216:9991/v1
LLM_API_KEY=not-needed

# Database Settings  
DB_TYPE=mysql
DB_HOST=192.168.200.216
DB_PORT=13306
DB_NAME=testdb
DB_USER=your_user
DB_PASSWORD=your_password
```

### Default Configuration Template (`trae_config.yaml`)
```yaml
app:
  name: "SemanticSQL Agent"
  version: "1.0.0"
  environment: "development"

database:
  type: "mysql"
  host: "192.168.200.216"
  port: 13306
  database: "testdb"
  username: "your_user"
  password: "your_password"
  connection_timeout: 30
  pool_size: 5

llm:
  model: "Qwen3-14B"
  base_url: "http://192.168.200.216:9991/v1"
  api_key: "not-needed"
  temperature: 0.1
  max_tokens: 20000
  timeout: 30
```

## Key Files for Development

### Core Implementation Files
- `agent/sql_agent.py` - Main SQL agent with `SQLQueryResult` response format
- `tools/trae_base_tool.py` - Base tool class with `ToolParameter` system
- `config/trae_config.py` - Configuration management with dataclasses
- `database/connection_manager.py` - Database connection and pooling

### Important Implementation Notes
- All tools follow `Sync*Tool` naming convention for synchronous operations
- Configuration loading supports environment variable overrides
- Database connections use async patterns but tools provide sync wrappers
- CLI entry point is `main.py` which delegates to `cli/cli.py`
- Error handling preserves context throughout the execution chain