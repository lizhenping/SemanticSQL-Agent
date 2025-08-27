"""基于 LangChain 的 SQL Agent"""

from langchain.agents import create_react_agent, AgentExecutor
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain.chat_models import init_chat_model
from langchain_core.prompts import PromptTemplate
from typing import Dict, Any, List, Optional
import logging
import re
from pathlib import Path

from config import Settings, DatabaseConfig
from tools import create_all_tools
from prompts.manager import PromptManager
from models.schemas import QueryResult
from .callbacks import TrajectoryCallback

logger = logging.getLogger(__name__)


class SemanticSQLAgent:
    """SQL 智能体"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化智能体
        
        Args:
            config: 配置字典，如果为 None 则使用默认配置
        """
        # 加载配置
        if config is None:
            self.settings = Settings()
            self.db_config = DatabaseConfig()
        else:
            self.settings = Settings(**config.get("settings", {}))
            self.db_config = DatabaseConfig(**config.get("database", {}))
        
        logger.info("初始化 SemanticSQL Agent...")
        
        # 初始化组件
        self.db = self._init_database()
        self.llm = self._init_llm()
        self.tools = self._create_tools()
        self.trajectory_callback = TrajectoryCallback()
        self.agent_executor = self._create_agent_executor()
        
        logger.info("SemanticSQL Agent 初始化完成")
    
    def _init_database(self) -> SQLDatabase:
        """初始化数据库连接"""
        logger.info(f"连接数据库: {self.db_config.host}:{self.db_config.port}/{self.db_config.database}")
        
        # 创建 SQLDatabase 实例
        db = SQLDatabase.from_uri(
            self.db_config.connection_uri,
            engine_kwargs=self.db_config.get_engine_kwargs()
        )
        
        # 测试连接
        try:
            tables = db.get_usable_table_names()
            logger.info(f"数据库连接成功，找到 {len(tables)} 个表")
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise
        
        return db
    
    def _init_llm(self):
        """初始化 LLM"""
        model_config = self.settings.model
        logger.info(f"初始化 LLM: {model_config.name}")
        
        # 对于 vLLM 或 OpenAI 兼容的服务
        if model_config.provider == "openai" or "vllm" in str(model_config.base_url):
            from langchain_openai import ChatOpenAI
            
            return ChatOpenAI(
                model=model_config.name,
                openai_api_key=model_config.api_key or "not-needed",
                openai_api_base=model_config.base_url,
                temperature=model_config.temperature,
                max_tokens=model_config.max_tokens
            )
        else:
            # 使用通用的 init_chat_model
            return init_chat_model(
                model_config.name,
                model_provider=model_config.provider,
                api_key=model_config.api_key,
                base_url=model_config.base_url,
                temperature=model_config.temperature,
                max_tokens=model_config.max_tokens
            )
    
    def _create_tools(self) -> List:
        """创建工具集"""
        logger.info("创建工具集...")
        
        tools = []
        
        # 1. SQL 基础工具包
        toolkit = SQLDatabaseToolkit(db=self.db, llm=self.llm)
        sql_tools = toolkit.get_tools()
        tools.extend(sql_tools)
        logger.info(f"添加了 {len(sql_tools)} 个 SQL 基础工具")
        
        # 2. 自定义工具
        config_dict = {
            "agent": {
                "enable_thinking": self.settings.agent.enable_thinking
            }
        }
        custom_tools = create_all_tools(self.db, self.llm, config_dict)
        tools.extend(custom_tools)
        logger.info(f"添加了 {len(custom_tools)} 个自定义工具")
        
        # 记录所有工具
        logger.info(f"工具集创建完成，共 {len(tools)} 个工具:")
        for tool in tools:
            logger.info(f"  - {tool.name}: {tool.description[:60]}...")
        
        return tools
    
    def _create_agent_executor(self) -> AgentExecutor:
        """创建智能体执行器"""
        logger.info("创建智能体执行器...")
        
        # 获取系统提示词
        pm = PromptManager()
        system_prompt_text = pm.get_system_prompt(
            "sql_agent",
            tables=self.db.get_usable_table_names()
        )
        
        # 创建提示词模板
        system_prompt = PromptTemplate.from_template(system_prompt_text)
        
        # 创建 ReAct agent
        agent = create_react_agent(
            self.llm,
            self.tools,
            system_prompt
        )
        
        # 创建执行器
        executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=self.settings.agent.verbose,
            max_iterations=self.settings.agent.max_iterations,
            handle_parsing_errors=True,
            callbacks=[self.trajectory_callback]
        )
        
        return executor
    
    def query(self, question: str) -> QueryResult:
        """执行查询
        
        Args:
            question: 用户的自然语言查询
            
        Returns:
            QueryResult: 查询结果
        """
        logger.info(f"处理查询: {question}")
        
        # 重置轨迹记录
        self.trajectory_callback.reset()
        
        try:
            # 执行智能体
            result = self.agent_executor.invoke({
                "input": question
            })
            
            # 提取信息
            sql = self._extract_sql(result)
            execution_result = self._extract_execution_result()
            trajectory = self.trajectory_callback.get_trajectory()
            
            # 创建结果对象
            query_result = QueryResult(
                success=True,
                question=question,
                sql=sql,
                answer=result.get("output", ""),
                execution_result=execution_result,
                steps=len(trajectory.get("tool_calls", []))
            )
            
            logger.info(f"查询成功，执行了 {query_result.steps} 个步骤")
            return query_result
            
        except Exception as e:
            logger.error(f"查询执行失败: {str(e)}", exc_info=True)
            
            # 创建错误结果
            return QueryResult(
                success=False,
                question=question,
                error=str(e)
            )
    
    def _extract_sql(self, result: Dict[str, Any]) -> Optional[str]:
        """从结果中提取 SQL"""
        output = result.get("output", "")
        
        # 1. 从输出中查找 SQL 代码块
        sql_match = re.search(r'```sql\n(.*?)\n```', output, re.DOTALL)
        if sql_match:
            return sql_match.group(1).strip()
        
        # 2. 从工具调用历史中查找
        for call in self.trajectory_callback.trajectory.get("tool_calls", []):
            if "generate_sql" in call.get("tool", ""):
                # 从生成工具的输出中提取
                tool_output = call.get("output", "")
                sql_match = re.search(r'```sql\n(.*?)\n```', tool_output, re.DOTALL)
                if sql_match:
                    return sql_match.group(1).strip()
            
            elif "execute_sql" in call.get("tool", ""):
                # 从执行工具的输入中提取
                tool_input = call.get("input", "")
                # 尝试解析输入
                if "sql" in tool_input:
                    import json
                    try:
                        input_data = json.loads(tool_input)
                        if isinstance(input_data, dict) and "sql" in input_data:
                            return input_data["sql"]
                    except:
                        pass
        
        # 3. 尝试从输出中直接匹配 SQL 语句
        sql_keywords = ['SELECT', 'WITH']
        for keyword in sql_keywords:
            pattern = rf'({keyword}\s+.*?)(?:;|$)'
            match = re.search(pattern, output, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_execution_result(self) -> Optional[Dict[str, Any]]:
        """从轨迹中提取执行结果"""
        # 查找最后一次 SQL 执行的结果
        for call in reversed(self.trajectory_callback.trajectory.get("tool_calls", [])):
            if "execute_sql" in call.get("tool", ""):
                output = call.get("output", "")
                
                # 尝试解析结构化结果
                if "row_count:" in output or "rows:" in output:
                    result = {}
                    
                    # 提取行数
                    row_count_match = re.search(r'row_count:\s*(\d+)', output)
                    if row_count_match:
                        result["row_count"] = int(row_count_match.group(1))
                    
                    # 提取执行时间
                    time_match = re.search(r'execution_time:\s*([\d.]+)', output)
                    if time_match:
                        result["execution_time"] = float(time_match.group(1))
                    
                    # 提取数据预览
                    if "data" in output or "preview" in output:
                        # 简单提取表格部分
                        lines = output.split('\n')
                        table_lines = []
                        in_table = False
                        
                        for line in lines:
                            if '|' in line and not line.strip().startswith('-'):
                                in_table = True
                                table_lines.append(line)
                            elif in_table and line.strip() == '':
                                break
                        
                        if table_lines:
                            result["preview"] = '\n'.join(table_lines[:5])
                    
                    return result if result else None
        
        return None
    
    def get_tables(self) -> List[str]:
        """获取所有表名"""
        return self.db.get_usable_table_names()
    
    def get_table_info(self, table_name: str) -> str:
        """获取表结构信息"""
        return self.db.get_table_info([table_name])