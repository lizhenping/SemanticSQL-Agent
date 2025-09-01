# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
SemanticSQL Agent is a LangChain-based intelligent SQL training data generation system. It uses autonomous agent architecture with ReAct pattern for analyzing databases and generating high-quality NL2SQL training pairs.

## Environment Setup
```bash
# Activate conda environment
source activate alphasql

# Install dependencies
pip install -r requirements.txt

# Start LLM service (required for agent operation)
CUDA_VISIBLE_DEVICES=2 vllm serve /root/autodl-tmp/model/Qwen3-14B \
  --host 0.0.0.0 --port 9991 \
  --trust-remote-code \
  --served-model-name "Qwen3-14B"
```

## Core Architecture (LangChain-Based)

### Agent System (`agent/`)
- **BaseAgent (`base_agent.py`)**: Abstract LangChain agent base class with ReAct pattern
- **SQLAgent (`sql_agent.py`)**: Main SQL generation agent for interactive queries
- **DataGenerationAgent** (legacy): Training data generation agent
- Uses LangChain's `AgentExecutor` with `ChatOpenAI` LLM integration

### Tools System (`tools/`)
All tools inherit from LangChain's `BaseTool` with standardized interfaces:

#### Analysis Tools (`analysis_tools/`)
- **SchemaExtractionTool**: Extract database structure
- **DomainAnalysisTool**: Analyze business domain from schema
- **FieldClassificationTool**: Classify field semantic types
- **ERAnalysisTool**: Entity relationship analysis

#### Generation Tools (`generation_tools/`)
- **ScenarioTool**: Generate query scenarios
- **QuestionGenerationTool**: Generate natural language questions
- **SQLGenerationTool**: Generate SQL queries

#### Validation Tools (`validation_tools/`)
- **SQLValidationTool**: Syntax validation
- **SQLExecutionTool**: Execute SQL against database

#### Reflection Tools (`reflection_tools/`)
- **SQLReflectionTool**: Quality analysis and improvement suggestions

#### Thinking Tools (`thinking_tools/`)
- **SequentialThinkingTool**: Complex analysis and reasoning

### Configuration System (`config/`)
- **Settings (`settings.py`)**: Pydantic-based global configuration
- **DatabaseConfig (`database.py`)**: Database connection settings
- Environment variable support with defaults

### Memory System (`utils/memory.py`)
- **DatabaseAnalysisMemory**: LangChain memory for storing analysis results
- Persistent storage of schema, domain, and field analysis across agent execution

## Development Commands

### Primary CLI Interface
```bash
# Entry point is cli.py (NOT main.py)
python cli.py --help

# Generate training data
python cli.py generate -n 100 -o training_data.jsonl

# Generate with custom config
python cli.py generate -n 50 -c config.yaml -o output.jsonl

# Database analysis only  
python cli.py analyze -d testdb -o analysis.json

# Configuration template (copy and modify)
python cli.py config-template > config.yaml
cp config.example.yaml config.yaml
```

### Configuration Setup
```bash
# Use environment variables or config file
# Config file takes precedence over environment variables
# Environment variables:
export SEMANTICSQL_LLM_MODEL="Qwen3-14B"
export SEMANTICSQL_LLM_BASE_URL="http://127.0.0.1:9991/v1"
export SEMANTICSQL_DB_HOST="192.168.200.216"
export SEMANTICSQL_DB_DATABASE="testdb"

# Or use config.yaml (recommended for development)
cp config.example.yaml config.yaml
# Edit config.yaml as needed
```

### Testing
```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test files
python -m pytest tests/test_agent.py -v
python -m pytest tests/test_tools.py -v
python -m pytest tests/test_data_generation_agent.py -v

# Run single test method
python -m pytest tests/test_agent.py::TestBaseAgent::test_initialization -v

# Run with coverage
python -m pytest tests/ --cov=. --cov-report=html
```

### Development Tools
```bash
# Code formatting
black .

# Linting
flake8 .

# Type checking (if configured)
mypy .
```

## Current System Configuration

### LLM Configuration
```yaml
settings:
  llm_model: "Qwen3-14B"
  llm_base_url: "http://127.0.0.1:9991/v1"
  llm_api_key: "not-needed"
  llm_temperature: 0.7
  llm_max_tokens: 20000
```

### Database Configuration
```yaml
database:
  host: "192.168.200.216"
  port: 13306
  database: "testdb"
  username: "testuser"
  password: "testpass"
  pool_size: 5
```

## Agent Execution Flow

### LangChain Integration
1. **Initialization**: Create `ChatOpenAI` client + `AgentExecutor`
2. **Tool Registration**: All tools auto-registered as LangChain tools
3. **Memory Setup**: `DatabaseAnalysisMemory` for persistent context
4. **Execution**: LangChain handles ReAct loop with tool calling
5. **Trajectory Recording**: Custom callbacks save execution history

### Key Execution Patterns
- **ReAct Loop**: Thought → Action → Action Input → Observation → (repeat)
- **Memory Persistence**: Analysis results stored in LangChain memory
- **Tool Chaining**: Sequential tool execution with shared context
- **Error Handling**: Graceful degradation with trajectory preservation

## Development Notes

### Current Architecture Status
- **Active Framework**: LangChain-based agent system
- **Legacy Components**: Some references to trae_agent patterns remain
- **Entry Point**: `cli.py` (main CLI interface)
- **Configuration**: Pydantic Settings + YAML overrides

### Key Implementation Files
- `agent/base_agent.py` - LangChain agent base class with ReAct pattern
- `agent/data_generation_agent.py` - Main training data generation agent
- `agent/sql_agent.py` - Interactive SQL query agent
- `config/settings.py` - Pydantic configuration models with env variable support
- `utils/memory.py` - LangChain memory for persistent database analysis
- `utils/trajectory.py` - Execution tracking for debugging
- `tools/` - Complete tool ecosystem (14+ tools organized by category)
- `cli.py` - Primary entry point (NOT main.py)

### Tool Parameter Patterns
- All tools use `memory: Dict[str, Any]` as primary input
- Memory contains: `db_analysis`, `schema_info`, `domain_info`, etc.
- Tools auto-extract needed information from memory structure
- No direct schema/table passing - use memory mechanism

### Common Issues
- **Context Length**: LLM has 32K token limit, long conversations may fail
- **Tool Parameters**: Ensure tools receive expected parameter names
- **Memory State**: Analysis tools must store results in memory for later use
- **Serialization**: Complex objects (like slice) need special handling

### Debugging
- **Trajectory Files**: Saved in `trajectories/` directory with execution details
- **Logging**: Structured logging with tool execution details (use `-v` flag)
- **Memory Inspection**: Use `agent.memory.load_memory_variables({})` 
- **Tool Debugging**: Check tool parameter validation in base_tool.py
- **LLM Service Check**: `curl -X POST http://localhost:9991/v1/chat/completions -H "Content-Type: application/json" -d '{"model": "Qwen3-14B", "messages": [{"role": "user", "content": "Hello"}]}'`
- **Database Check**: `mysql -h 192.168.200.216 -P 13306 -u testuser -p testdb`

### Quick Development Workflow
```bash
# 1. Ensure LLM service is running
curl -s http://localhost:9991/v1/models

# 2. Test basic functionality
python cli.py generate -n 2 -o test_output.jsonl -v

# 3. Run tests after changes
python -m pytest tests/test_data_generation_agent.py -v

# 4. Format and lint code
black . && flake8 .
```