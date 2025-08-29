"""
智能SQL Agent - 自动执行完整数据分析流程
"""

import json
import logging
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime

# 不再需要BaseAgent，SmartSQLAgent是独立实现
from config.trae_config import TraeConfig
from tools.sql_tools import (
    SyncSchemaExtractionTool as SchemaExtractionTool,
    SyncSQLGenerationTool as SQLGenerationTool,
    SyncSQLValidationTool as SQLValidationTool,
    SyncSQLExecutionTool as SQLExecutionTool
)
from tools.analysis_tools import (
    SyncDomainAnalysisTool as DomainAnalysisTool,
    SyncFieldClassificationTool as FieldClassificationTool,
    SyncERAnalysisTool as ERAnalysisTool,
    SyncSequentialThinkingTool as SequentialThinkingTool
)
import openai
from database.connection_manager import DatabaseManager

logger = logging.getLogger(__name__)


class AnalysisStage(Enum):
    """分析阶段枚举"""
    CONNECT = "connect"              # 连接数据库
    DOMAIN_ANALYSIS = "domain"       # 分析数据库领域
    FIELD_CLASSIFICATION = "field"   # 字段分类
    TABLE_ANALYSIS = "table"         # 表结构分析
    ER_ANALYSIS = "er"              # ER关系分析
    SCENARIO_GENERATION = "scenario" # 场景问题生成
    COMPLETED = "completed"          # 完成


class SmartAnalysisResult:
    """智能分析结果"""
    
    def __init__(self):
        self.success = True
        self.current_stage = AnalysisStage.CONNECT
        self.stages_completed = []
        self.database_info = {}
        self.domain_analysis = {}
        self.field_classification = {}
        self.table_analysis = {}
        self.er_analysis = {}
        self.generated_scenarios = []
        self.execution_time = 0.0
        self.error = None
        self.steps_taken = 0
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "current_stage": self.current_stage.value,
            "stages_completed": [stage.value for stage in self.stages_completed],
            "database_info": self.database_info,
            "domain_analysis": self.domain_analysis,
            "field_classification": self.field_classification,
            "table_analysis": self.table_analysis,
            "er_analysis": self.er_analysis,
            "generated_scenarios": self.generated_scenarios,
            "execution_time": self.execution_time,
            "error": self.error,
            "steps_taken": self.steps_taken
        }


class SmartSQLAgent:
    """智能SQL Agent - 自动执行完整分析流程"""
    
    def __init__(self, config: TraeConfig):
        """初始化智能SQL Agent"""
        self.config = config
        self.logger = logging.getLogger("agent.smart_sql")
        
        # 初始化LLM客户端（直接使用OpenAI客户端）
        self.llm_client = openai.OpenAI(
            api_key=config.llm.api_key,
            base_url=config.llm.base_url
        )
        self.llm_config = {
            'model': config.llm.model,
            'temperature': config.llm.temperature,
            'max_tokens': config.llm.max_tokens
        }
        
        # 初始化数据库管理器
        self.db_manager = DatabaseManager(config.database)
        
        # 初始化工具
        self.tools = self._create_tools()
        
        # 状态跟踪
        self.current_result = SmartAnalysisResult()
        
    def _create_tools(self) -> Dict[str, Any]:
        """创建所有需要的工具"""
        tools = {}
        
        # 数据库相关工具
        tools['schema_extraction'] = SchemaExtractionTool(self.config.database)
        tools['sql_generation'] = SQLGenerationTool(self.config.database)
        tools['sql_validation'] = SQLValidationTool(self.config.database)
        tools['sql_execution'] = SQLExecutionTool(self.config.database)
        
        # 分析工具
        tools['analyze_domain'] = DomainAnalysisTool(self.config.database)
        tools['classify_fields'] = FieldClassificationTool(self.config.database)
        tools['analyze_relationships'] = ERAnalysisTool(self.config.database)
        tools['sequential_thinking'] = SequentialThinkingTool(self.config.database)
        
        return tools
    
    def smart_analyze(self, user_request: str = "请分析这个数据库") -> SmartAnalysisResult:
        """执行智能分析流程"""
        start_time = datetime.now()
        self.logger.info(f"开始智能分析流程: {user_request}")
        
        try:
            # 执行6步流程
            self._execute_connect_stage()
            self._execute_domain_analysis_stage()
            self._execute_field_classification_stage()
            self._execute_table_analysis_stage()
            self._execute_er_analysis_stage()
            self._execute_scenario_generation_stage()
            
            # 标记完成
            self.current_result.current_stage = AnalysisStage.COMPLETED
            self.current_result.stages_completed.append(AnalysisStage.COMPLETED)
            
        except Exception as e:
            self.logger.error(f"智能分析流程失败: {e}")
            self.current_result.success = False
            self.current_result.error = str(e)
        
        finally:
            # 关闭数据库连接
            self.db_manager.close()
            
            # 计算执行时间
            end_time = datetime.now()
            self.current_result.execution_time = (end_time - start_time).total_seconds()
            
        return self.current_result
    
    def _execute_connect_stage(self):
        """阶段1: 连接数据库"""
        self.logger.info("阶段1: 连接数据库")
        self.current_result.current_stage = AnalysisStage.CONNECT
        
        # 连接数据库
        if not self.db_manager.initialize():
            raise Exception("数据库连接失败")
            
        # 获取数据库基本信息
        self.current_result.database_info = self.db_manager.get_database_info()
        self.current_result.stages_completed.append(AnalysisStage.CONNECT)
        
        self.logger.info(f"数据库连接成功: {self.current_result.database_info}")
    
    def _execute_domain_analysis_stage(self):
        """阶段2: 分析数据库领域"""
        self.logger.info("阶段2: 分析数据库领域")
        self.current_result.current_stage = AnalysisStage.DOMAIN_ANALYSIS
        
        # 使用LLM进行领域分析（不使用工具调用）
        domain_prompt = self._build_domain_analysis_prompt()
        
        response = self.llm_client.chat.completions.create(
            messages=[{"role": "user", "content": domain_prompt}],
            **self.llm_config
        )
        
        # 直接使用文本响应
        self.current_result.domain_analysis = {
            "analysis_method": "text_based",
            "content": response.choices[0].message.content,
            "database_type": self.current_result.database_info.get('type', 'unknown'),
            "timestamp": datetime.now().isoformat()
        }
        
        self.current_result.stages_completed.append(AnalysisStage.DOMAIN_ANALYSIS)
        self.logger.info("领域分析完成")
    
    def _execute_field_classification_stage(self):
        """阶段3: 字段分类分析"""
        self.logger.info("阶段3: 字段分类分析")
        self.current_result.current_stage = AnalysisStage.FIELD_CLASSIFICATION
        
        # 首先获取schema信息
        schema_tool = self.tools['schema_extraction']
        schema_result = schema_tool.execute()
        
        if schema_result.get('success'):
            # 基于schema进行字段分类（不使用工具调用）
            field_prompt = self._build_field_classification_prompt(schema_result)
            
            response = self.llm_client.chat.completions.create(
                messages=[{"role": "user", "content": field_prompt}],
                **self.llm_config
            )
            
            # 直接使用文本响应
            self.current_result.field_classification = {
                "analysis_method": "text_based",
                "content": response.choices[0].message.content,
                "schema_info": schema_result,
                "timestamp": datetime.now().isoformat()
            }
        
        self.current_result.stages_completed.append(AnalysisStage.FIELD_CLASSIFICATION)
        self.logger.info("字段分类分析完成")
    
    def _execute_table_analysis_stage(self):
        """阶段4: 表结构分析"""
        self.logger.info("阶段4: 表结构分析")
        self.current_result.current_stage = AnalysisStage.TABLE_ANALYSIS
        
        # 获取详细的表结构信息
        tables = self.db_manager.get_tables()
        table_details = {}
        
        for table_name in tables:
            table_info = self.db_manager.get_table_info(table_name)
            table_details[table_name] = table_info
        
        self.current_result.table_analysis = {
            "total_tables": len(tables),
            "table_names": tables,
            "table_details": table_details,
            "analysis_timestamp": datetime.now().isoformat()
        }
        
        self.current_result.stages_completed.append(AnalysisStage.TABLE_ANALYSIS)
        self.logger.info(f"表结构分析完成，共{len(tables)}个表")
    
    def _execute_er_analysis_stage(self):
        """阶段5: ER关系分析"""
        self.logger.info("阶段5: ER关系分析")
        self.current_result.current_stage = AnalysisStage.ER_ANALYSIS
        
        er_prompt = self._build_er_analysis_prompt()
        
        response = self.llm_client.chat.completions.create(
            messages=[{"role": "user", "content": er_prompt}],
            **self.llm_config
        )
        
        # 直接使用文本响应
        self.current_result.er_analysis = {
            "analysis_method": "text_based",
            "content": response.choices[0].message.content,
            "table_info": self.current_result.table_analysis,
            "timestamp": datetime.now().isoformat()
        }
        
        self.current_result.stages_completed.append(AnalysisStage.ER_ANALYSIS)
        self.logger.info("ER关系分析完成")
    
    def _execute_scenario_generation_stage(self):
        """阶段6: 场景化问题生成"""
        self.logger.info("阶段6: 场景化问题生成")
        self.current_result.current_stage = AnalysisStage.SCENARIO_GENERATION
        
        scenario_prompt = self._build_scenario_generation_prompt()
        
        response = self.llm_client.chat.completions.create(
            messages=[{"role": "user", "content": scenario_prompt}],
            **self.llm_config
        )
        
        # 解析生成的场景问题
        scenarios = self._parse_generated_scenarios(response.choices[0].message.content)
        self.current_result.generated_scenarios = scenarios
        
        self.current_result.stages_completed.append(AnalysisStage.SCENARIO_GENERATION)
        self.logger.info(f"场景问题生成完成，共生成{len(scenarios)}个场景")
    
    def _build_domain_analysis_prompt(self) -> str:
        """构建领域分析提示词"""
        db_info = self.current_result.database_info
        return f"""
# 数据库领域分析任务

请分析以下数据库的业务领域和应用场景：

**数据库信息:**
- 数据库类型: {db_info.get('type', 'unknown')}
- 数据库名称: {db_info.get('database', 'unknown')}
- 表数量: {db_info.get('tables_count', 0)}
- 表名列表: {', '.join(db_info.get('tables', []))}

**分析要求:**
1. 根据数据库名称和表名模式，推断业务领域
2. 识别可能的应用场景（如：电商、CRM、OA等）
3. 分析数据库的设计模式和架构特点
4. 基于表名前缀和命名规律分析业务模块

请提供详细的分析结果。
"""
    
    def _build_field_classification_prompt(self, schema_result: Dict[str, Any]) -> str:
        """构建字段分类提示词"""
        return f"""
# 字段分类分析任务

基于以下数据库schema信息，对字段进行分类：

**Schema信息:**
{json.dumps(schema_result.get('data', {}), ensure_ascii=False, indent=2)}

**分类要求:**
1. 识别主键、外键字段
2. 分类业务字段（如：用户信息、订单信息、产品信息等）
3. 识别系统字段（如：创建时间、更新时间、状态字段等）
4. 分析字段数据类型和用途
5. 识别字段命名规律和设计模式

请提供详细的字段分类分析结果。
"""
    
    def _build_er_analysis_prompt(self) -> str:
        """构建ER关系分析提示词"""
        return f"""
# ER关系分析任务

基于已分析的数据库信息，分析表与表之间的实体关系：

**已有信息:**
- 领域分析: {json.dumps(self.current_result.domain_analysis, ensure_ascii=False, indent=2)}
- 字段分类: {json.dumps(self.current_result.field_classification, ensure_ascii=False, indent=2)}
- 表结构: {json.dumps(self.current_result.table_analysis, ensure_ascii=False, indent=2)}

**分析要求:**
1. 识别表之间的一对一、一对多、多对多关系
2. 分析外键约束和引用关系
3. 构建实体关系图的逻辑结构
4. 识别核心实体和关联实体
5. 分析数据库设计的规范化程度

请提供详细的ER关系分析结果。
"""
    
    def _build_scenario_generation_prompt(self) -> str:
        """构建场景问题生成提示词"""
        return f"""
# 场景化问题生成任务

基于完整的数据库分析结果，生成实用的查询场景和问题：

**完整分析结果:**
- 数据库信息: {json.dumps(self.current_result.database_info, ensure_ascii=False)}
- 领域分析: {json.dumps(self.current_result.domain_analysis, ensure_ascii=False)}
- 字段分类: {json.dumps(self.current_result.field_classification, ensure_ascii=False)}
- 表结构分析: {json.dumps(self.current_result.table_analysis, ensure_ascii=False)}
- ER关系分析: {json.dumps(self.current_result.er_analysis, ensure_ascii=False)}

**生成要求:**
请生成10-15个实用的查询场景，每个场景包含：
1. 场景描述
2. 业务问题
3. 预期查询类型（统计、筛选、关联等）
4. 涉及的表和字段

**输出格式:**
场景1: [场景名称]
描述: [场景描述]
问题: [具体业务问题]
查询类型: [查询类型]
涉及表: [相关表名]

场景2: ...

请确保场景贴合实际业务需求，问题具有实用价值。
"""
    
    def _parse_generated_scenarios(self, content: str) -> List[Dict[str, Any]]:
        """解析生成的场景问题"""
        scenarios = []
        
        # 简单的文本解析，提取场景信息
        lines = content.split('\n')
        current_scenario = {}
        
        for line in lines:
            line = line.strip()
            if line.startswith('场景') and ':' in line:
                if current_scenario:
                    scenarios.append(current_scenario)
                current_scenario = {
                    "name": line.split(':', 1)[1].strip(),
                    "description": "",
                    "question": "",
                    "query_type": "",
                    "tables": ""
                }
            elif line.startswith('描述:'):
                current_scenario["description"] = line.split(':', 1)[1].strip()
            elif line.startswith('问题:'):
                current_scenario["question"] = line.split(':', 1)[1].strip()
            elif line.startswith('查询类型:'):
                current_scenario["query_type"] = line.split(':', 1)[1].strip()
            elif line.startswith('涉及表:'):
                current_scenario["tables"] = line.split(':', 1)[1].strip()
        
        # 添加最后一个场景
        if current_scenario:
            scenarios.append(current_scenario)
        
        return scenarios
    
    def get_stage_summary(self) -> str:
        """获取当前阶段摘要"""
        stage_names = {
            AnalysisStage.CONNECT: "数据库连接",
            AnalysisStage.DOMAIN_ANALYSIS: "领域分析", 
            AnalysisStage.FIELD_CLASSIFICATION: "字段分类",
            AnalysisStage.TABLE_ANALYSIS: "表结构分析",
            AnalysisStage.ER_ANALYSIS: "ER关系分析", 
            AnalysisStage.SCENARIO_GENERATION: "场景问题生成",
            AnalysisStage.COMPLETED: "分析完成"
        }
        
        completed = [stage_names[stage] for stage in self.current_result.stages_completed]
        current = stage_names[self.current_result.current_stage]
        
        return f"当前阶段: {current}, 已完成: {', '.join(completed)}"
    
    def query(self, question: str) -> 'SQLQueryResult':
        """简单查询功能 - 为兼容性而添加"""
        from models.sql_result import SQLQueryResult
        
        try:
            # 连接数据库
            if not self.db_manager.initialize():
                return SQLQueryResult(
                    success=False,
                    question=question,
                    error="数据库连接失败"
                )
            
            # 简单的LLM调用来生成SQL
            prompt = f"""
根据以下数据库信息回答用户问题：

用户问题: {question}

数据库信息: 
- 类型: MySQL
- 表: {', '.join(self.db_manager.get_tables())}

请生成对应的SQL查询语句。只返回SQL语句，不要其他解释。
"""
            
            response = self.llm_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                **self.llm_config
            )
            
            sql = response.choices[0].message.content.strip()
            
            # 简单清理SQL（移除markdown标记等）
            if sql.startswith('```'):
                sql = sql.split('\n')[1:-1]  # 移除```sql和```
                sql = '\n'.join(sql)
            
            return SQLQueryResult(
                success=True,
                question=question,
                sql=sql,
                answer=f"已生成SQL查询: {sql}"
            )
            
        except Exception as e:
            return SQLQueryResult(
                success=False,
                question=question,
                error=str(e)
            )
        finally:
            self.db_manager.close()