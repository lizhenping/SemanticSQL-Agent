# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the **TRAE-Agent** project for NL2SQL (Natural Language to SQL) training data generation. The system consists of two main components:

1. **SemanticSQL Agent** (`semanticsql-agent/`) - A ReAct-based autonomous agent for SQL generation using LangChain
2. **NL2SQL Pipeline** (`nl2sql_pipeline/`) - A structured pipeline for database analysis and question generation

## Architecture

### High-Level System Design

The system follows a dual-architecture approach:

- **Agent-based approach** (semanticsql-agent): Uses LangChain's ReAct pattern with tools for autonomous SQL generation
- **Pipeline-based approach** (nl2sql_pipeline): Structured workflows for systematic database analysis and training data generation

Both systems share similar goals but use different execution paradigms - the agent system is more autonomous while the pipeline system is more structured and deterministic.

### Key Components

#### SemanticSQL Agent Architecture
- **Agent Core** (`agent/sql_agent.py`): Main ReAct agent implementation using LangChain AgentExecutor
- **Tools System** (`tools/`): Specialized tools for analysis, generation, and reflection
  - Analysis tools: Schema extraction, domain analysis, field classification, etc.
  - Generation tools: Question generation, SQL generation, scenario operations
  - Reflection tools: SQL validation and reflection
- **State Management** (`agent/state.py`): Minimal 2-field state (current_input, database_params)
- **Memory System** (`utils/memory.py`): Neo4j-based knowledge storage and retrieval
- **Configuration** (`config/settings.py`): Pydantic-based settings with environment variable support

#### NL2SQL Pipeline Architecture
- **Workflows** (`workflows/`): High-level business process orchestration
- **Pipelines** (`pipelines/`): Component-level processing flows (analysis, generation)
- **Services** (`services/`): Core services (database, LLM, prompt, configuration)
- **Models** (`models/`): Data structures and state representations
- **CLI System** (`cli/`): Command-line interface with argument parsing

### Memory and State Management

- **Neo4j Integration**: Both systems use Neo4j for persistent knowledge storage
- **Agent State**: Minimal state design with only essential fields
- **Pipeline State**: Rich state models for tracking analysis and generation progress
- **Caching**: Intelligent caching system for analysis results to avoid redundant work

## Common Development Commands

### SemanticSQL Agent Commands

Run from the `semanticsql-agent/` directory:

```bash
# Generate training data (main command)
python cli.py generate -n 20 -o training_data.jsonl

# Generate with specific database
python cli.py generate -n 50 -d testdb -o contract_training.jsonl

# Analyze database structure
python cli.py analyze -d testdb -o analysis_result.json

# Configuration via environment variables
export SEMANTICSQL_LLM_MODEL="Qwen3-14B"
export SEMANTICSQL_LLM_BASE_URL="http://127.0.0.1:9991/v1" 
export SEMANTICSQL_NEO4J_URI="bolt://127.0.0.1:7687"
export SEMANTICSQL_DB_HOST="127.0.0.1"
export SEMANTICSQL_DB_DATABASE="testdb"
```

### NL2SQL Pipeline Commands  

Run from the `nl2sql_pipeline/src/` directory:

```bash
# Main pipeline execution
python -m nl2sql_pipeline --host localhost --user root --database testdb generate --count 100

# Database analysis only
python -m nl2sql_pipeline --host localhost --user root --database testdb analyze

# Cache management
python -m nl2sql_pipeline cache list
python -m nl2sql_pipeline cache clear testdb

# With custom LLM configuration
OPENAI_BASE_URL=http://127.0.0.1:9991/v1 OPENAI_MODEL=Qwen3-14B python -m nl2sql_pipeline --database testdb generate --count 50
```

### Testing and Quality

The project currently lacks comprehensive test suites. When adding tests:

- Python testing framework appears to be standard `unittest` or `pytest` (no specific framework detected)
- No specific linting configuration found - use standard Python tools (`black`, `flake8`, `mypy`)

## Configuration Management

### Environment Variables

Both systems support extensive environment variable configuration:

**SemanticSQL Agent**:
- `SEMANTICSQL_LLM_*`: LLM configuration (MODEL, BASE_URL, API_KEY, TEMPERATURE)
- `SEMANTICSQL_NEO4J_*`: Neo4j configuration (URI, USER, PASSWORD) 
- `SEMANTICSQL_DB_*`: Database configuration (HOST, PORT, DATABASE, USERNAME, PASSWORD)

**NL2SQL Pipeline**:
- `OPENAI_*`: LLM configuration (BASE_URL, MODEL, API_KEY)
- Database parameters via command line arguments

### Configuration Files

- `semanticsql-agent/config/settings.py`: Pydantic-based settings with defaults
- `nl2sql_pipeline/config/app.yaml`: YAML-based pipeline configuration
- Multiple environment-specific configs supported

## Key Architecture Patterns

### Tool-Based Design

Both systems use tool-based architectures where business logic is encapsulated in tools:

- **Base Tool Pattern**: All tools inherit from `BaseSemanticSQLTool` 
- **Memory Integration**: Tools integrate with Neo4j for knowledge persistence
- **Error Handling**: Comprehensive error handling and retry mechanisms
- **Async Support**: Tools support both synchronous and asynchronous execution

### State Management Patterns

- **Agent State**: Minimal state with `current_input` and `database_params`
- **Pipeline State**: Rich state models tracking analysis phases and results
- **Memory Persistence**: Neo4j graph database for long-term knowledge storage
- **Caching Strategy**: File-based caching for expensive analysis operations

### Prompt Management

- **Jinja2 Templates**: Centralized prompt template management
- **Dynamic Rendering**: Context-aware prompt generation
- **Version Control**: Multiple prompt versions and A/B testing support
- **Internationalization**: Support for multiple languages in prompts

## Database Integration

### Supported Databases
- **Primary**: MySQL (extensively supported)
- **Connection Management**: Robust connection pooling and retry logic
- **Schema Analysis**: Comprehensive database introspection capabilities

### Database Configuration
- Host, port, username, password configuration
- Multiple database support within single system
- Connection validation and health checks

## Development Guidelines

### Code Organization
- **Separation of Concerns**: Clear separation between agent logic, tools, and configuration
- **Dependency Injection**: Services and components use dependency injection patterns  
- **Error Boundaries**: Comprehensive error handling at tool and service levels
- **Logging**: Structured logging throughout the system

### Configuration Best Practices
- **Environment-First**: Production configurations should use environment variables
- **Development Defaults**: Sensible defaults for development environments
- **Validation**: Pydantic-based configuration validation
- **Security**: No hardcoded credentials in production

## Working with the Codebase

### Adding New Tools
1. Inherit from `BaseSemanticSQLTool` in `tools/base_tool.py`
2. Implement `_run()` method with business logic
3. Add memory integration if needed
4. Register tool in appropriate factory functions

### Extending Pipelines
1. Create new pipeline classes inheriting from base pipeline patterns
2. Implement step-by-step processing logic
3. Add to workflow orchestration
4. Update configuration as needed

### Memory System Integration
- Use Neo4j for persistent knowledge storage
- Follow triple-store patterns for knowledge representation
- Implement proper error handling for graph operations
- Consider performance implications of complex queries

## Runtime Environment

- **Python Version**: 3.11.13
- **Environment**: conda environment `alphasql` 
- **Key Dependencies**: LangChain, Neo4j, PyMySQL, Pydantic, Jinja2
- **Execution Context**: Linux environment with GPU support (autodl platform)