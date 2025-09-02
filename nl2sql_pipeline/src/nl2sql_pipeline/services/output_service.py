"""Output Service for managing LLM output parsing"""

from typing import Type, Dict, Any, Optional
from pydantic import BaseModel
from langchain.output_parsers import PydanticOutputParser
from langchain.output_parsers.json import SimpleJsonOutputParser
from langchain.output_parsers.list import CommaSeparatedListOutputParser
import logging

from ..models.analysis import (
    DomainKnowledge, FieldClassification, ColumnDescription, 
    TableDescription, PhysicalRelation, LogicalRelation, ConceptualModel
)
from ..models.generation import (
    TableMapping, QueryCapability, FieldMapping, Question
)


logger = logging.getLogger(__name__)


class OutputService:
    """Service for managing output parsing with LangChain"""
    
    def __init__(self):
        """Initialize output service"""
        self.parsers = {}
        self._register_default_parsers()
        
    def _register_default_parsers(self):
        """Register default parsers for common models"""
        # Analysis models
        self.register_parser("domain_knowledge", DomainKnowledge)
        self.register_parser("field_classification", FieldClassification)
        self.register_parser("column_description", ColumnDescription)
        self.register_parser("table_description", TableDescription)
        self.register_parser("physical_relation", PhysicalRelation)
        self.register_parser("logical_relation", LogicalRelation)
        self.register_parser("conceptual_model", ConceptualModel)
        
        # Generation models
        self.register_parser("table_mapping", TableMapping)
        self.register_parser("query_capability", QueryCapability)
        self.register_parser("field_mapping", FieldMapping)
        self.register_parser("question", Question)
        
        # Simple parsers
        self.parsers["json"] = SimpleJsonOutputParser()
        self.parsers["list"] = CommaSeparatedListOutputParser()
        
    def register_parser(self, name: str, model: Type[BaseModel]):
        """Register a Pydantic parser
        
        Args:
            name: Name for the parser
            model: Pydantic model class
        """
        self.parsers[name] = PydanticOutputParser(pydantic_object=model)
        
    def get_parser(self, name: str):
        """Get a parser by name
        
        Args:
            name: Name of the parser
            
        Returns:
            Parser instance
        """
        if name not in self.parsers:
            raise ValueError(f"Parser '{name}' not found")
        return self.parsers[name]
    
    def parse(self, output: str, parser_name: str) -> Any:
        """Parse output using named parser
        
        Args:
            output: Raw LLM output
            parser_name: Name of the parser to use
            
        Returns:
            Parsed output
        """
        parser = self.get_parser(parser_name)
        try:
            return parser.parse(output)
        except Exception as e:
            logger.error(f"Failed to parse output with parser '{parser_name}': {e}")
            # Try to fix and reparse
            if hasattr(parser, 'parse_with_prompt'):
                return parser.parse_with_prompt(output)
            raise
    
    def get_format_instructions(self, parser_name: str) -> str:
        """Get format instructions for a parser
        
        Args:
            parser_name: Name of the parser
            
        Returns:
            Format instructions string
        """
        parser = self.get_parser(parser_name)
        if hasattr(parser, 'get_format_instructions'):
            return parser.get_format_instructions()
        return ""
    
    def create_custom_parser(self, model: Type[BaseModel]):
        """Create a custom parser for a Pydantic model
        
        Args:
            model: Pydantic model class
            
        Returns:
            PydanticOutputParser instance
        """
        return PydanticOutputParser(pydantic_object=model)
    
    def validate_output(self, output: Any, model: Type[BaseModel]) -> bool:
        """Validate output against a model
        
        Args:
            output: Output to validate
            model: Pydantic model to validate against
            
        Returns:
            True if valid, False otherwise
        """
        try:
            if isinstance(output, dict):
                model(**output)
            elif isinstance(output, model):
                return True
            else:
                return False
            return True
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return False