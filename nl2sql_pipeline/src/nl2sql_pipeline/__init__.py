"""NL2SQL Pipeline - Database Analysis and Question Generation

A pipeline that analyzes database schemas and generates SQL questions using:
- LangGraph for workflow orchestration
- LangChain for LLM interactions
- Jinja2 for prompt templating
"""

from .application import NL2SQLApplication

__version__ = "0.1.0"

__all__ = [
    "NL2SQLApplication",
    "__version__"
]