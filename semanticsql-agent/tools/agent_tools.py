"""
智能体工具集 - 将流水线阶段转换为独立工具
遵循trae_agent工具设计模式
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime

from database.connection_manager import DatabaseManager
from config.trae_config import TraeConfig


class AgentTool(ABC):
    """智能体工具基础类"""
    
    def __init__(self, config: Optional[TraeConfig] = None):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行工具 - 子类需要实现"""
        pass
    
    @abstractmethod 
    def get_description(self) -> str:
        """获取工具描述 - 子类需要实现"""
        pass


class DatabaseConnectionTool(AgentTool):
    """数据库连接工具"""
    
    def __init__(self, config: TraeConfig):
        super().__init__(config)
        self.db_manager = DatabaseManager(config.database)
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """连接数据库并获取基本信息"""
        try:
            # 连接数据库
            if not self.db_manager.initialize():
                return {
                    "success": False,
                    "error": "数据库连接失败"
                }
            
            # 获取数据库信息
            db_info = self.db_manager.get_database_info()
            
            return {
                "success": True,
                "database_info": db_info,
                "message": f"成功连接到数据库 {db_info.get('database', 'unknown')}"
            }
            
        except Exception as e:
            self.logger.error(f"数据库连接失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_description(self) -> str:
        return "连接数据库并获取基本信息（表数量、数据库版本等）"


class SchemaAnalysisTool(AgentTool):
    """数据库架构分析工具"""
    
    def __init__(self, config: TraeConfig):
        super().__init__(config)
        self.db_manager = DatabaseManager(config.database)
    
    def execute(self, table_name: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """分析数据库架构"""
        try:
            if not self.db_manager.initialize():
                return {"success": False, "error": "数据库连接失败"}
            
            if table_name:
                # 分析特定表
                schema_info = self.db_manager.get_table_info(table_name)
                return {
                    "success": True,
                    "table_name": table_name,
                    "schema": schema_info,
                    "message": f"已获取表 {table_name} 的架构信息"
                }
            else:
                # 分析所有表
                all_tables = self.db_manager.get_tables()
                schema_info = {}
                
                for table in all_tables[:5]:  # 限制为前5个表避免过多输出
                    schema_info[table] = self.db_manager.get_table_info(table)
                
                return {
                    "success": True,
                    "tables_analyzed": len(schema_info),
                    "total_tables": len(all_tables),
                    "schemas": schema_info,
                    "message": f"已分析 {len(schema_info)} 个表的架构"
                }
                
        except Exception as e:
            self.logger.error(f"架构分析失败: {e}")
            return {"success": False, "error": str(e)}
    
    def get_description(self) -> str:
        return "分析数据库表结构，获取字段信息、数据类型、约束等。可指定table_name分析特定表"


class QueryGenerationTool(AgentTool):
    """SQL查询生成工具"""
    
    def __init__(self, config: TraeConfig, llm_client=None):
        super().__init__(config)
        self.llm_client = llm_client
    
    def execute(self, question: str, schema_context: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """根据自然语言问题生成SQL查询"""
        try:
            if not self.llm_client:
                return {"success": False, "error": "LLM客户端未初始化"}
            
            # 构建提示词
            prompt = self._build_sql_generation_prompt(question, schema_context)
            
            # 调用LLM生成SQL
            response = self.llm_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.config.llm.model,
                temperature=0.1,
                max_tokens=1000
            )
            
            sql = response.choices[0].message.content.strip()
            
            # 清理SQL（移除markdown标记等）
            sql = self._clean_sql(sql)
            
            return {
                "success": True,
                "question": question,
                "generated_sql": sql,
                "message": f"已生成SQL查询: {sql[:100]}..."
            }
            
        except Exception as e:
            self.logger.error(f"SQL生成失败: {e}")
            return {"success": False, "error": str(e)}
    
    def _build_sql_generation_prompt(self, question: str, schema_context: Optional[Dict]) -> str:
        """构建SQL生成提示词"""
        prompt = f"""# SQL查询生成任务

请根据以下自然语言问题生成SQL查询：

**问题**: {question}

"""
        
        if schema_context:
            prompt += f"""**数据库架构信息**:
{json.dumps(schema_context, ensure_ascii=False, indent=2)}

"""
        
        prompt += """**要求**:
1. 生成标准的SQL查询语句
2. 确保SQL语法正确
3. 只返回SQL语句，不要其他解释
4. 使用适当的表名和字段名

SQL查询:"""
        
        return prompt
    
    def _clean_sql(self, sql: str) -> str:
        """清理SQL语句"""
        # 移除markdown代码块标记
        sql = sql.replace("```sql", "").replace("```", "")
        # 移除多余的空白
        sql = sql.strip()
        return sql
    
    def get_description(self) -> str:
        return "根据自然语言问题生成SQL查询语句。需要参数: question (必需), schema_context (可选)"


class QueryExecutionTool(AgentTool):
    """SQL查询执行工具"""
    
    def __init__(self, config: TraeConfig):
        super().__init__(config)
        self.db_manager = DatabaseManager(config.database)
    
    def execute(self, sql: str, limit: int = 10, **kwargs) -> Dict[str, Any]:
        """执行SQL查询"""
        try:
            if not self.db_manager.initialize():
                return {"success": False, "error": "数据库连接失败"}
            
            # 添加LIMIT限制（如果不存在）
            if "LIMIT" not in sql.upper() and "SELECT" in sql.upper():
                sql = f"{sql.rstrip(';')} LIMIT {limit}"
            
            # 执行查询
            results = self.db_manager.execute_query(sql)
            
            return {
                "success": True,
                "sql": sql,
                "results": results.get("data", []),
                "row_count": results.get("row_count", 0),
                "execution_time": results.get("execution_time", 0),
                "message": f"查询执行成功，返回 {results.get('row_count', 0)} 行数据"
            }
            
        except Exception as e:
            self.logger.error(f"SQL执行失败: {e}")
            return {"success": False, "error": str(e), "sql": sql}
    
    def get_description(self) -> str:
        return "执行SQL查询并返回结果。参数: sql (必需), limit (可选，默认10)"


class DataAnalysisTool(AgentTool):
    """数据分析工具"""
    
    def __init__(self, config: TraeConfig, llm_client=None):
        super().__init__(config)
        self.llm_client = llm_client
    
    def execute(self, data: List[Dict], question: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """分析查询结果数据"""
        try:
            if not data:
                return {
                    "success": True,
                    "analysis": "没有数据需要分析",
                    "insights": []
                }
            
            # 基础统计信息
            basic_stats = self._calculate_basic_stats(data)
            
            # 如果有LLM，进行智能分析
            insights = []
            if self.llm_client and question:
                try:
                    ai_analysis = self._perform_ai_analysis(data, question)
                    insights.append(ai_analysis)
                except Exception as e:
                    self.logger.warning(f"AI分析失败: {e}")
            
            return {
                "success": True,
                "data_summary": basic_stats,
                "insights": insights,
                "message": f"已分析 {len(data)} 行数据"
            }
            
        except Exception as e:
            self.logger.error(f"数据分析失败: {e}")
            return {"success": False, "error": str(e)}
    
    def _calculate_basic_stats(self, data: List[Dict]) -> Dict[str, Any]:
        """计算基础统计信息"""
        if not data:
            return {}
        
        stats = {
            "total_rows": len(data),
            "columns": list(data[0].keys()) if data else [],
            "column_count": len(data[0].keys()) if data else 0
        }
        
        # 简单的数值列分析
        numeric_columns = []
        for col in stats["columns"]:
            try:
                first_val = data[0][col]
                if isinstance(first_val, (int, float)):
                    numeric_columns.append(col)
            except:
                pass
        
        stats["numeric_columns"] = numeric_columns
        return stats
    
    def _perform_ai_analysis(self, data: List[Dict], question: str) -> str:
        """使用AI进行数据分析"""
        # 构建分析提示词
        data_sample = data[:3]  # 只取前3行作为样本
        prompt = f"""# 数据分析任务

原始问题: {question}

数据样本 (前3行):
{json.dumps(data_sample, ensure_ascii=False, indent=2)}

总行数: {len(data)}

请分析这些数据并提供洞察，包括:
1. 数据的主要特征
2. 回答原始问题的关键信息  
3. 任何值得注意的模式或异常

分析结果:"""
        
        response = self.llm_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=self.config.llm.model,
            temperature=0.3,
            max_tokens=500
        )
        
        return response.choices[0].message.content.strip()
    
    def get_description(self) -> str:
        return "分析查询结果数据，提供统计信息和洞察。参数: data (必需), question (可选)"


class ReasoningTool(AgentTool):
    """推理思考工具"""
    
    def __init__(self, config: TraeConfig, llm_client=None):
        super().__init__(config)
        self.llm_client = llm_client
    
    def execute(self, context: str, goal: str, **kwargs) -> Dict[str, Any]:
        """进行推理思考"""
        try:
            if not self.llm_client:
                return {"success": False, "error": "LLM客户端未初始化"}
            
            prompt = f"""# 推理思考任务

当前上下文: {context}

目标: {goal}

请基于当前上下文，思考下一步应该采取什么行动来达成目标。
考虑以下方面:
1. 当前已有的信息
2. 还需要什么信息
3. 最合适的下一步行动
4. 可能的风险和备选方案

思考结果:"""
            
            response = self.llm_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.config.llm.model,
                temperature=0.5,
                max_tokens=300
            )
            
            reasoning = response.choices[0].message.content.strip()
            
            return {
                "success": True,
                "reasoning": reasoning,
                "context": context,
                "goal": goal,
                "message": "推理思考完成"
            }
            
        except Exception as e:
            self.logger.error(f"推理失败: {e}")
            return {"success": False, "error": str(e)}
    
    def get_description(self) -> str:
        return "进行推理思考，分析当前情况并规划下一步行动。参数: context (必需), goal (必需)"


class DomainAnalysisTool(AgentTool):
    """领域分析工具"""
    
    def __init__(self, config: TraeConfig, llm_client=None):
        super().__init__(config)
        self.llm_client = llm_client
    
    def execute(self, database_info: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """分析数据库业务领域"""
        try:
            if not self.llm_client:
                return {"success": False, "error": "LLM客户端未初始化"}
            
            prompt = f"""# 数据库领域分析任务

数据库信息:
{json.dumps(database_info, ensure_ascii=False, indent=2)}

请基于表名、数据库名称等信息，分析这个数据库的业务领域和应用场景:
1. 推断业务领域 (如: 电商、CRM、制造业等)
2. 识别可能的应用场景
3. 分析表名的命名规律和设计模式
4. 推断业务模块的划分

分析结果:"""
            
            response = self.llm_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.config.llm.model,
                temperature=0.3,
                max_tokens=800
            )
            
            analysis = response.choices[0].message.content.strip()
            
            return {
                "success": True,
                "domain_analysis": analysis,
                "database_info": database_info,
                "message": "领域分析完成"
            }
            
        except Exception as e:
            self.logger.error(f"领域分析失败: {e}")
            return {"success": False, "error": str(e)}
    
    def get_description(self) -> str:
        return "分析数据库的业务领域和应用场景。参数: database_info (必需)"