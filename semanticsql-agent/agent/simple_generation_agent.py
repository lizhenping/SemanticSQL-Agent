"""
简化的数据生成Agent - 绕过复杂的schema传递问题
直接基于已知表信息生成训练数据
"""

import json
import logging
from typing import Dict, Any, List

from .base_agent import BaseAgent
from config.settings import Settings
from config.database import DatabaseConfig
from utils.database import DatabaseManager

# 只导入必需的工具
from tools.generation_tools.sql_generation_tool import SQLGenerationTool
from tools.validation_tools.sql_execution_tool import SQLExecutionTool


class SimpleGenerationAgent(BaseAgent):
    """简化的训练数据生成Agent"""
    
    def __init__(self, settings: Settings, db_config: DatabaseConfig):
        """Initialize Simple Generation Agent"""
        # Initialize database manager
        self.db_manager = DatabaseManager(db_config)
        if not self.db_manager.initialize():
            raise Exception("Failed to initialize database connection")
        
        # 预定义的表信息（基于已知的testdb结构）
        self.known_tables = {
            "aid_info": ["id", "date", "amount", "total_amount", "aid_type", "memo", "sum", "sum_tmp"],
            "sjckc_zyccq_htjcxx": ["htbzh", "htmc", "htlb", "htlx", "htzje", "htqdrq"],
            "sjckc_zyccq_htdtxx": ["htbzh", "jgrq", "tqsj", "ljzfjf", "cgsl"],
            "sjckc_zyccq_czdwxx": ["jgbzh", "jgmc", "czdwxz"],
            "sjckc_zyccq_zlwt": ["zlwtbs", "htbzh", "zlwtbh", "wtmc", "fxsj"]
        }
        
        # 生成的训练数据
        self.training_examples = []
        
        # Call parent initialization
        super().__init__(settings, db_config)
    
    def _initialize_tools(self):
        """Initialize simplified tools"""
        # SQL generation tool
        sql_gen_tool = SQLGenerationTool(self.settings)
        
        # SQL execution tool
        execution_tool = SQLExecutionTool(self.db_manager)
        
        # Register tools
        self.register_tool("sql_generation", sql_gen_tool, "根据问题生成SQL查询")
        self.register_tool("sql_execution", execution_tool, "执行SQL查询并获取结果")
    
    def get_system_prompt(self) -> str:
        """简化的系统提示词"""
        tables_info = "\\n".join([f"- {table}: {', '.join(columns)}" for table, columns in self.known_tables.items()])
        
        return f"""你是NL2SQL训练数据生成专家。使用工具生成高质量的问题-SQL对。

数据库: {self.db_config.database}
表结构:
{tables_info}

任务：使用工具生成多样化的自然语言问题和对应SQL查询。

必须按照此格式使用工具：

Thought: [你的思考过程]
Action: sql_generation
Action Input: {{"question": "具体问题", "schema_info": "表名表包含字段名"}}

注意：
1. schema_info传递简单字符串格式
2. 一次只生成一个问题
3. 必须正确格式JSON
4. 生成多种类型的问题（统计、查询、过滤）
"""
    
    def generate_training_data(self, count: int, output_file: str) -> Dict[str, Any]:
        """生成训练数据"""
        task = f"生成{count}条NL2SQL训练数据，包含自然语言问题和对应的SQL查询。重点关注aid_info表和合同相关表的查询。"
        
        # Agent自主执行
        execution = self.new_task(task)
        
        # 提取生成的数据
        training_data = self._extract_training_data_from_execution(execution)
        
        # 完全依赖Agent生成，不使用硬编码样本
        if len(training_data) < count:
            self.logger.warning(f"Agent只生成了{len(training_data)}条数据，期望{count}条")
            # 不添加硬编码样本，完全依赖Agent智能生成
            if len(training_data) == 0:
                raise Exception("Agent没有生成任何数据，请检查工具调用")
        
        # 保存输出（只保存实际生成的数据）
        if training_data:
            self._save_training_data(training_data, output_file)
        else:
            # 创建空文件
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump([], f)
        
        return {
            'total_generated': len(training_data),
            'output_file': output_file,
            'execution_steps': len(execution.steps),
            'task_id': execution.task_id
        }
    
    
    def _extract_training_data_from_execution(self, execution) -> List[Dict[str, Any]]:
        """从执行轨迹提取训练数据"""
        training_data = []
        
        for step in execution.steps:
            # 从成功的sql_generation工具调用中提取数据
            if (step.tool_name == "sql_generation" and 
                step.tool_input and 
                step.tool_output and 
                isinstance(step.tool_output, dict) and 
                step.tool_output.get('success')):
                
                try:
                    # 从工具输入获取问题
                    question = step.tool_input.get('question', '')
                    
                    # 从工具输出获取SQL
                    sql_data = step.tool_output.get('data', {})
                    sql = sql_data.get('sql', '')
                    
                    if question and sql:
                        training_data.append({
                            'question': question,
                            'sql': sql,
                            'database_id': self.db_config.database
                        })
                        self.logger.info(f"提取到训练数据: {question} -> {sql[:50]}...")
                        
                except Exception as e:
                    self.logger.warning(f"提取训练数据失败: {e}")
                    continue
        
        return training_data
    
    def _save_training_data(self, data: List[Dict[str, Any]], output_file: str):
        """保存训练数据"""
        import os
        os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"训练数据已保存到: {output_file}")
    
    def close(self):
        """关闭连接"""
        if hasattr(self, 'db_manager') and self.db_manager:
            self.db_manager.close()