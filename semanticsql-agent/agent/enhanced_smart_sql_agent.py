"""
增强版SmartSQLAgent - 集成新架构的所有组件
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base_agent import BaseAgent
from .execution_tracker import ExecutionTracker
from core.models import (
    AgentExecution, AgentStep, AgentStepType,
    QueryScenario, GeneratedExample, TrainingExample
)
from core.exceptions import AgentExecutionError
from prompts.prompt_manager import get_prompt_manager

# 导入所有工具
from tools.generation import (
    ScenarioTool,
    OperationSelectionTool,
    QuestionGenerationTool,
    SQLGenerationTool
)
from tools.validation import (
    SQLValidationTool,
    SQLExecutionTool
)
from tools.reflection import SQLReflectionTool
from tools.analysis_tools import SyncDomainAnalysisTool
from tools.sql_tools import SyncSchemaExtractionTool

from config.trae_config import TraeConfig
from models.sql_result import SQLQueryResult


class EnhancedSmartSQLAgent(BaseAgent):
    """增强版智能SQL Agent - 完整实现架构规范"""
    
    def __init__(self, config: TraeConfig):
        """初始化增强版智能体"""
        super().__init__(config)
        self.logger = logging.getLogger("EnhancedSmartSQLAgent")
        self.prompt_manager = get_prompt_manager()
        self.execution_tracker = None
        
        # 存储分析结果
        self.schema_info = None
        self.domain_info = None
        self.generated_examples = []
    
    def _initialize_tools(self):
        """初始化所有工具"""
        # 分析工具
        self.register_tool(
            "extract_schema",
            SyncSchemaExtractionTool(self.config.database),
            "提取数据库结构信息"
        )
        
        self.register_tool(
            "analyze_domain",
            SyncDomainAnalysisTool(self.config.database),
            "分析业务领域"
        )
        
        # 生成工具
        self.register_tool(
            "generate_scenario",
            ScenarioTool(self.config),
            "生成查询场景"
        )
        
        self.register_tool(
            "select_operations",
            OperationSelectionTool(self.config),
            "选择SQL操作类型"
        )
        
        self.register_tool(
            "generate_question",
            QuestionGenerationTool(self.config),
            "生成自然语言问题"
        )
        
        self.register_tool(
            "generate_sql",
            SQLGenerationTool(self.config),
            "生成SQL查询"
        )
        
        # 验证工具
        self.register_tool(
            "validate_sql",
            SQLValidationTool(self.config),
            "验证SQL语法"
        )
        
        self.register_tool(
            "execute_sql",
            SQLExecutionTool(self.config),
            "执行SQL查询"
        )
        
        # 反思工具
        self.register_tool(
            "reflect_on_sql",
            SQLReflectionTool(self.config),
            "分析和优化SQL"
        )
    
    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        # 使用提示词管理器获取
        return self.prompt_manager.get_system_prompt("smart_sql_agent")
    
    async def run_with_tracking(self, task: str, context: Dict = None) -> AgentExecution:
        """带执行追踪的运行方法"""
        # 创建执行追踪器
        self.execution_tracker = ExecutionTracker(task=task, save_to_file=True)
        
        with self.execution_tracker:
            try:
                # 执行任务
                result = await self.run(task, context)
                self.execution_tracker.complete(result=result)
                return self.execution_tracker.execution
                
            except Exception as e:
                self.execution_tracker.complete(error=str(e))
                raise
    
    def generate_training_data(self, count: int = 10) -> List[GeneratedExample]:
        """
        生成NL2SQL训练数据
        
        Args:
            count: 生成数量
            
        Returns:
            生成的训练样本列表
        """
        self.generated_examples = []
        
        # 创建执行追踪器
        self.execution_tracker = ExecutionTracker(
            task=f"Generate {count} NL2SQL training examples",
            save_to_file=True
        )
        
        with self.execution_tracker:
            try:
                # Step 1: 分析数据库
                self.execution_tracker.record_thought("开始分析数据库结构")
                self._analyze_database()
                
                # Step 2: 生成场景
                self.execution_tracker.record_thought(f"生成{count}个查询场景")
                scenarios = self._generate_scenarios(count)
                
                # Step 3: 为每个场景生成数据
                for i, scenario in enumerate(scenarios):
                    self.execution_tracker.record_thought(
                        f"处理场景 {i+1}/{len(scenarios)}: {scenario.business_purpose}"
                    )
                    
                    example = self._generate_example_for_scenario(scenario)
                    if example and example.is_valid():
                        self.generated_examples.append(example)
                
                # Step 4: 批量反思优化
                self.execution_tracker.record_thought("对生成的数据进行反思和优化")
                self._reflect_on_batch()
                
                self.execution_tracker.complete(result={
                    "generated_count": len(self.generated_examples),
                    "success_rate": len(self.generated_examples) / count if count > 0 else 0
                })
                
                return self.generated_examples
                
            except Exception as e:
                self.execution_tracker.complete(error=str(e))
                raise AgentExecutionError("generate_training_data", str(e), e)
    
    def _analyze_database(self):
        """分析数据库结构和领域"""
        # 提取数据库结构
        self.execution_tracker.record_action(
            "extract_schema", {}, "提取数据库结构"
        )
        
        schema_result = self.call_tool("extract_schema")
        
        if schema_result["success"]:
            self.schema_info = schema_result["data"]
            self.execution_tracker.record_observation(
                self.schema_info,
                f"成功提取{len(self.schema_info.get('tables', {}))}个表的结构"
            )
        else:
            raise AgentExecutionError(
                "analyze_database",
                f"Schema extraction failed: {schema_result['error']}"
            )
        
        # 分析业务领域
        self.execution_tracker.record_action(
            "analyze_domain", {"scope": "all"}, "分析业务领域"
        )
        
        domain_result = self.call_tool("analyze_domain", scope="all")
        
        if domain_result["success"]:
            self.domain_info = domain_result["data"]
            self.execution_tracker.record_observation(
                self.domain_info,
                "成功分析业务领域和表关系"
            )
    
    def _generate_scenarios(self, count: int) -> List[QueryScenario]:
        """生成查询场景"""
        self.execution_tracker.record_action(
            "generate_scenario",
            {
                "schema_info": "...",
                "domain_info": "...",
                "count": count
            },
            f"生成{count}个查询场景"
        )
        
        result = self.call_tool(
            "generate_scenario",
            schema_info=self.schema_info,
            domain_info=self.domain_info,
            count=count,
            difficulty="mixed"
        )
        
        if result["success"]:
            scenarios = result["data"]
            self.execution_tracker.record_observation(
                f"Generated {len(scenarios)} scenarios",
                f"成功生成{len(scenarios)}个场景"
            )
            return scenarios
        else:
            self.execution_tracker.record_observation(
                None,
                f"场景生成失败: {result['error']}",
                error=result['error']
            )
            return []
    
    def _generate_example_for_scenario(self, scenario: QueryScenario) -> Optional[GeneratedExample]:
        """为单个场景生成完整示例"""
        try:
            # 1. 选择操作
            operations_result = self.call_tool(
                "select_operations",
                scenario=scenario.__dict__ if hasattr(scenario, '__dict__') else scenario,
                schema_info=self.schema_info
            )
            
            if not operations_result["success"]:
                return None
            
            operations = operations_result["data"]["operations"]
            
            # 2. 生成问题
            question_result = self.call_tool(
                "generate_question",
                scenario=scenario.__dict__ if hasattr(scenario, '__dict__') else scenario,
                operations=operations,
                schema_info=self.schema_info,
                style="formal"
            )
            
            if not question_result["success"]:
                return None
            
            question = question_result["data"]["question"]
            
            # 3. 生成SQL
            sql_result = self.call_tool(
                "generate_sql",
                question=question,
                schema_info=self.schema_info,
                operations=operations
            )
            
            if not sql_result["success"]:
                return None
            
            sql = sql_result["data"]["sql"]
            
            # 4. 验证SQL
            validation_result = self.call_tool(
                "validate_sql",
                sql=sql,
                schema_info=self.schema_info
            )
            
            # 5. 执行测试（可选）
            execution_result = {}
            if validation_result["success"] and validation_result["data"]["valid"]:
                exec_result = self.call_tool(
                    "execute_sql",
                    sql=sql,
                    dry_run=True  # 使用干运行模式
                )
                execution_result = exec_result["data"] if exec_result["success"] else {}
            
            # 6. 创建示例
            example = GeneratedExample(
                scenario_id=scenario.id if hasattr(scenario, 'id') else None,
                question=question,
                sql=sql,
                difficulty=scenario.complexity if hasattr(scenario, 'complexity') else "medium",
                validation_result=validation_result["data"] if validation_result["success"] else {},
                execution_result=execution_result
            )
            
            # 7. 单个反思
            if example.is_valid():
                reflection_result = self.call_tool(
                    "reflect_on_sql",
                    question=question,
                    sql=sql,
                    validation_result=validation_result["data"] if validation_result["success"] else {},
                    execution_result=execution_result
                )
                
                if reflection_result["success"]:
                    example.quality_score = reflection_result["data"]["quality_score"]
                    
                    # 如果有优化的SQL，更新
                    if reflection_result["data"].get("optimized_sql"):
                        example.sql = reflection_result["data"]["optimized_sql"]
            
            return example
            
        except Exception as e:
            self.logger.error(f"Failed to generate example for scenario: {e}")
            return None
    
    def _reflect_on_batch(self):
        """对批量生成的数据进行反思"""
        if not self.generated_examples:
            return
        
        self.execution_tracker.record_reflection(
            f"分析{len(self.generated_examples)}个生成的样本"
        )
        
        # 统计分析
        stats = {
            "total": len(self.generated_examples),
            "valid": sum(1 for e in self.generated_examples if e.is_valid()),
            "avg_quality": sum(e.quality_score for e in self.generated_examples) / len(self.generated_examples),
            "difficulty_distribution": {}
        }
        
        # 难度分布
        for example in self.generated_examples:
            difficulty = example.difficulty.value if hasattr(example.difficulty, 'value') else str(example.difficulty)
            stats["difficulty_distribution"][difficulty] = stats["difficulty_distribution"].get(difficulty, 0) + 1
        
        self.execution_tracker.record_reflection(
            f"批量分析结果: {json.dumps(stats, indent=2)}"
        )
        
        # 识别需要改进的样本
        low_quality_examples = [
            e for e in self.generated_examples
            if e.quality_score < 70
        ]
        
        if low_quality_examples:
            self.execution_tracker.record_reflection(
                f"发现{len(low_quality_examples)}个低质量样本，需要优化"
            )
    
    def export_training_data(self, format: str = "json") -> str:
        """导出训练数据"""
        if not self.generated_examples:
            return ""
        
        if format == "json":
            data = {
                "database_id": self.config.database.database,
                "examples": [e.to_dict() for e in self.generated_examples],
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "total_count": len(self.generated_examples),
                    "model": self.config.llm.model
                }
            }
            return json.dumps(data, indent=2, ensure_ascii=False)
        
        elif format == "jsonl":
            lines = []
            for example in self.generated_examples:
                training_example = TrainingExample.from_generated_example(
                    example,
                    self.config.database.database
                )
                lines.append(json.dumps(training_example.to_dict(), ensure_ascii=False))
            return "\n".join(lines)
        
        elif format == "openai":
            lines = []
            for example in self.generated_examples:
                training_example = TrainingExample.from_generated_example(
                    example,
                    self.config.database.database
                )
                lines.append(json.dumps(training_example.to_openai_format(), ensure_ascii=False))
            return "\n".join(lines)
        
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def get_execution_report(self) -> str:
        """获取执行报告"""
        if self.execution_tracker:
            return self.execution_tracker.export_to_markdown()
        return "No execution data available"