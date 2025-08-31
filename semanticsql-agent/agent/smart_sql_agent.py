"""
SmartSQLAgent - Intelligent SQL generation agent using ReAct pattern
Based on the design specification - focused on SQL query generation
"""

import json
import logging
from typing import Dict, Any, Optional

from .base_agent import BaseAgent
from config.settings import Settings
from config.database import DatabaseConfig
from models.schemas import SQLQueryResult
from utils.database import DatabaseManager

# Import tools
from tools.analysis_tools.schema_extraction_tool import SchemaExtractionTool
from tools.generation_tools.sql_generation_tool import SQLGenerationTool
from tools.validation_tools.sql_validation_tool import SQLValidationTool
from tools.validation_tools.sql_execution_tool import SQLExecutionTool
from tools.thinking_tools.sequential_thinking_tool import SequentialThinkingTool


class SmartSQLAgent(BaseAgent):
    """Intelligent SQL agent using ReAct pattern for database analysis"""
    
    def __init__(self, settings: Settings, db_config: DatabaseConfig):
        """Initialize SmartSQL Agent"""
        # Initialize database manager BEFORE calling super().__init__
        self.db_manager = DatabaseManager(db_config)
        if not self.db_manager.initialize():
            raise Exception("Failed to initialize database connection")
        
        # Current analysis context
        self.current_database_info = None
        self.current_schema_info = None
        self.analysis_results = {}
        
        # Call parent initialization (which will call _initialize_tools)
        super().__init__(settings, db_config)
        
    def _initialize_tools(self):
        """Initialize agent tools"""
        # Create and configure schema extraction tool
        schema_tool = SchemaExtractionTool(self.settings)
        schema_tool.set_database_manager(self.db_manager)
        
        # Register all available tools
        self.register_tool(
            "extract_schema",
            schema_tool,
            "Extract database schema information including tables, columns, and relationships"
        )
        
        self.register_tool(
            "generate_sql",
            SQLGenerationTool(self.settings),
            "Generate SQL queries from natural language questions"
        )
        
        self.register_tool(
            "validate_sql",
            SQLValidationTool(self.settings),
            "Validate SQL query syntax and logic"
        )
        
        self.register_tool(
            "execute_sql",
            SQLExecutionTool(self.db_manager),
            "Execute SQL queries safely and return results"
        )
        
        self.register_tool(
            "sequential_thinking",
            SequentialThinkingTool(),
            "Perform structured sequential thinking and analysis"
        )
    
    def get_system_prompt(self) -> str:
        """Get system prompt for the agent"""
        tools_desc = "\n".join([
            f"- **{name}**: {desc}" 
            for name, desc in self.tool_descriptions.items()
        ])
        
        return f"""# Smart SQL Generation Agent

You are a professional database analysis expert capable of:
1. Analyzing database structures and relationships
2. Understanding natural language queries and generating SQL
3. Validating and executing queries safely
4. Providing insights and recommendations

## Available Tools
{tools_desc}

## Workflow
Please follow the ReAct (Reasoning + Acting) pattern:

1. **Observation**: Observe current state and user requirements
2. **Thought**: Think about what action to take next
3. **Action**: Choose and execute appropriate tool
4. **Observation**: Observe tool execution results
5. Repeat until task is completed

## Response Format
Please respond strictly in the following format:

```
Thought: I need to [your thinking process]
Action: [exact_tool_name]
Action Input: {{"parameter": "value"}}
```

**Important**: Action must be followed by an exact tool name!

## Available Tool Names (use exactly)
- extract_schema
- generate_sql
- validate_sql
- execute_sql
- sequential_thinking

## Guidelines
- Always extract schema first before generating SQL
- Validate SQL before execution
- Provide clear explanations of results
- Focus on safety and accuracy
- Use sequential thinking for complex problems

Current database: {self.db_config.database} ({self.db_config.type.value})
"""
    
    def query(self, natural_language_query: str) -> SQLQueryResult:
        """
        Process natural language query and return SQL result
        
        Args:
            natural_language_query: User's question in natural language
            
        Returns:
            SQLQueryResult with SQL, data, and metadata
        """
        try:
            # Start new agent task
            execution = self.new_task(f"Convert to SQL: {natural_language_query}")
            
            if execution.status == "completed":
                # Extract result from execution
                final_result = execution.final_result
                
                if isinstance(final_result, dict):
                    return SQLQueryResult(
                        success=True,
                        question=natural_language_query,
                        sql=final_result.get("sql", ""),
                        answer=final_result.get("answer", ""),
                        data=final_result.get("data", []),
                        row_count=final_result.get("row_count", 0),
                        execution_time=execution.get_duration() or 0.0,
                        steps=len(execution.steps)
                    )
                else:
                    return SQLQueryResult(
                        success=True,
                        question=natural_language_query,
                        answer=str(final_result),
                        execution_time=execution.get_duration() or 0.0,
                        steps=len(execution.steps)
                    )
            else:
                return SQLQueryResult(
                    success=False,
                    question=natural_language_query,
                    error=execution.error or "Agent execution failed",
                    execution_time=execution.get_duration() or 0.0,
                    steps=len(execution.steps)
                )
        
        except Exception as e:
            self.logger.error(f"Query processing failed: {e}")
            return SQLQueryResult(
                success=False,
                question=natural_language_query,
                error=str(e)
            )
    
    def _generate_final_result(self) -> Any:
        """Generate final result with SQL query information"""
        # Look for SQL generation results in execution steps
        sql_result = None
        execution_result = None
        
        for step in self.current_execution.steps:
            if step.tool_name == "generate_sql" and step.tool_output:
                if isinstance(step.tool_output, dict) and step.tool_output.get("success"):
                    sql_result = step.tool_output.get("data", {})
            
            if step.tool_name == "execute_sql" and step.tool_output:
                if isinstance(step.tool_output, dict) and step.tool_output.get("success"):
                    execution_result = step.tool_output.get("data", {})
        
        # Combine results
        result = {
            "task_completed": True,
            "sql": sql_result.get("sql", "") if sql_result else "",
            "data": execution_result.get("data", []) if execution_result else [],
            "row_count": execution_result.get("row_count", 0) if execution_result else 0,
            "answer": self._generate_answer(sql_result, execution_result)
        }
        
        return result
    
    def _generate_answer(self, sql_result: Dict, execution_result: Dict) -> str:
        """Generate human-readable answer from SQL and execution results"""
        if not execution_result or not execution_result.get("data"):
            return "No data returned from query"
        
        data = execution_result["data"]
        row_count = execution_result.get("row_count", len(data))
        
        if row_count == 1 and len(data) == 1:
            # Single result
            first_row = data[0]
            if len(first_row) == 1:
                # Single value result (like COUNT)
                value = list(first_row.values())[0]
                return f"Result: {value}"
        
        return f"Query returned {row_count} rows"
    
    def close(self):
        """Close database connection"""
        if self.db_manager:
            self.db_manager.close()