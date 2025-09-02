"""Generation related models"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from enum import Enum
import uuid


class ScenarioType(str, Enum):
    """Predefined scenario types"""
    PROJECT_EXECUTION = "project_execution_monitoring"
    GEOGRAPHICAL_DIST = "project_geographical_distribution"
    PROJECT_TYPE = "project_type_analysis"
    COMPREHENSIVE_EVAL = "project_comprehensive_evaluation"
    RESOURCE_ALLOCATION = "regional_resource_allocation"
    LIFECYCLE_MGMT = "project_lifecycle_management"


class ComplexityLevel(int, Enum):
    """Question complexity levels"""
    LEVEL1 = 1  # Basic
    LEVEL2 = 2  # Intermediate
    LEVEL3 = 3  # Advanced
    LEVEL4 = 4  # Expert


class Scenario(BaseModel):
    """Scenario definition"""
    id: str
    name: str
    type: ScenarioType
    description: str
    sub_scenarios: List[str] = Field(default_factory=list)
    priority: str = "medium"  # high, medium, low
    

class TableMapping(BaseModel):
    """Table mapping for scenario"""
    scenario_id: str
    complexity_level: int
    primary_table: str
    related_tables: List[str] = Field(default_factory=list)
    join_paths: List[Dict[str, str]] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    

class QueryCapability(BaseModel):
    """Query capability definition"""
    main_operations: List[str]  # SELECT, GROUP BY, etc.
    aggregations: List[str]  # COUNT, SUM, AVG, etc.
    filters: List[str]  # WHERE conditions
    sorting: List[str]  # ORDER BY
    special_features: List[str] = Field(default_factory=list)  # HAVING, WINDOW, etc.
    

class FieldMapping(BaseModel):
    """Field mapping for query"""
    sub_scenario: str
    selected_fields: List[str]
    grouping_fields: List[str] = Field(default_factory=list)
    filter_fields: List[str] = Field(default_factory=list)
    output_fields: List[str] = Field(default_factory=list)
    

class Question(BaseModel):
    """Generated SQL question"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    business_question: str
    sql_query: str
    scenario: ScenarioType
    complexity: ComplexityLevel
    tables_used: List[str]
    explanation: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    

class GenerationResult(BaseModel):
    """Complete generation result"""
    total_requested: int
    total_generated: int
    questions: List[Question]
    scenario_distribution: Dict[str, int]
    complexity_distribution: Dict[int, int]