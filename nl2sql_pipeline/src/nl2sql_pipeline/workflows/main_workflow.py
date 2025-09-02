"""主工作流

协调数据库分析和问题生成两个主要阶段。
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import os
import pickle
from pathlib import Path
from dataclasses import dataclass

from ..models.states import AnalysisResult

from ..models.analysis import (
    DomainKnowledge, TableDescription, ColumnDescription,
    FieldClassification, ERRelationship
)
from ..services import (
    ConfigService,
    MySQLDatabaseService,
    LangChainLLMService,
    PromptService,
    ServiceContainer  # 导入共享的ServiceContainer
)
from .analysis_workflow import AnalysisWorkflow
from .scenario_generation_workflow import ScenarioGenerationWorkflow

logger = logging.getLogger(__name__)


class MainWorkflow:
    """主工作流
    
    管理完整的NL2SQL问题生成流程：
    1. 数据库分析（8步）
    2. 问题生成（场景×复杂度×5阶段）
    """
    
    # ========== 初始化相关方法 ==========
    
    def __init__(self, config_path: Optional[str] = None):
        """初始化主工作流
        
        参数:
            config_path: 配置文件路径
        """
        # 初始化配置
        self.config_service = self._create_config_service(config_path)
        
        # 初始化服务容器
        self.services = self._init_services()
        
        # 初始化工作流
        self.analysis_workflow = AnalysisWorkflow(self.services)
        self.generation_workflow = ScenarioGenerationWorkflow(self.services)
        
        # 初始化缓存目录
        self.cache_dir = self._setup_cache_directory()
    
    def _create_config_service(self, config_path: Optional[str]) -> ConfigService:
        """创建配置服务"""
        if config_path:
            return ConfigService(config_path)
        
        # 使用常量定义路径层级
        CONFIG_PATH_DEPTH = 4
        config_dir = Path(__file__).parents[CONFIG_PATH_DEPTH - 1] / "config"
        return ConfigService(config_dir)
    
    def _init_services(self) -> ServiceContainer:
        """初始化所有服务"""
        # LLM配置
        llm_config = self._prepare_llm_config()
        
        # 创建服务容器
        self.services = ServiceContainer(
            database_service=MySQLDatabaseService(),
            llm_service=LangChainLLMService(llm_config),
            prompt_service=PromptService(),
            config_service=self.config_service
        )
        
        logger.info("所有服务初始化完成")
        return self.services
    
    def _prepare_llm_config(self) -> Dict[str, Any]:
        """准备LLM配置，支持环境变量覆盖"""
        llm_config = self.config_service.get("llm", {})
        
        # 环境变量覆盖
        env_mappings = {
            'OPENAI_BASE_URL': 'base_url',
            'OPENAI_MODEL': 'model',
            'OPENAI_API_KEY': 'api_key'
        }
        
        for env_var, config_key in env_mappings.items():
            value = os.getenv(env_var)
            if value:
                llm_config[config_key] = value
                if config_key != 'api_key':  # 不记录API密钥
                    logger.info(f"使用环境变量 {env_var}: {value}")
                else:
                    logger.info(f"使用环境变量 {env_var}")
        
        return llm_config
    
    def _setup_cache_directory(self) -> str:
        """设置缓存目录"""
        cache_dir = self.config_service.get('analysis.cache_dir', 'cache/analysis')
        os.makedirs(cache_dir, exist_ok=True)
        return cache_dir
    
    # ========== 主要公开方法 ==========
    
    def analyze_database(self, 
                        database_name: str,
                        database_config: Optional[Dict[str, Any]] = None,
                        cache_path: Optional[str] = None,
                        use_cache: bool = True) -> AnalysisResult:
        """执行数据库分析
        
        参数:
            database_name: 数据库名称
            database_config: 数据库连接配置（如果为None，从配置文件读取）
            cache_path: 分析结果缓存路径
            use_cache: 是否使用缓存
            
        返回:
            分析结果
        """
        # 如果没有指定缓存路径，使用默认路径
        if cache_path is None:
            cache_path = os.path.join(self.cache_dir, f"{database_name}_analysis.pkl")
        
        # 检查缓存
        if use_cache and os.path.exists(cache_path):
            logger.info(f"从缓存加载分析结果: {cache_path}")
            return self._load_analysis_cache(cache_path)
        
        # 准备数据库配置
        if database_config is None:
            database_config = self.config_service.get("database", {})
        
        # 确保数据库名称
        database_config['database'] = database_name
        
        logger.info(f"开始分析数据库: {database_name}")
        
        # 执行分析
        analysis_result = self.analysis_workflow.run(
            database_name=database_name,
            database_config=database_config
        )
        
        # 缓存结果
        if use_cache:
            self._save_analysis_cache(analysis_result, cache_path)
        
        logger.info("数据库分析完成")
        return analysis_result
    
    def generate_questions(self,
                         analysis_result: AnalysisResult,
                         target_count: int = 100,
                         output_path: Optional[str] = None,
                         cache_analysis: bool = True) -> List[Dict[str, Any]]:
        """生成问题
        
        参数:
            analysis_result: 分析结果
            target_count: 目标问题数量
            output_path: 输出文件路径
            cache_analysis: 是否缓存分析结果到生成过程中
            
        返回:
            生成的问题列表
        """
        
        # 如果需要缓存分析结果到生成过程
        if cache_analysis:
            # 保存轻量级的分析摘要供生成使用
            analysis_cache_path = os.path.join(
                self.cache_dir, 
                f"{analysis_result.database_name}_analysis_summary.json"
            )
            self._save_analysis_summary(analysis_result, analysis_cache_path)
        
        logger.info(f"开始生成问题，目标数量: {target_count}")
        
        # 执行生成
        result = self.generation_workflow.run(
            analysis_result=analysis_result,
            target_count=target_count
        )
        
        # 提取问题列表
        questions = result.get('questions', [])
        
        # 输出结果
        if output_path:
            self._save_questions(questions, output_path)
        
        logger.info(f"问题生成完成，共生成 {len(questions)} 个问题")
        
        # 打印统计信息
        if result.get('statistics'):
            logger.info("生成统计:")
            stats = result['statistics']
            logger.info(f"  按复杂度: {stats.get('by_complexity', {})}")
            logger.info(f"  按场景数: {len(stats.get('by_scenario', {}))}")
        
        return questions
    
    def run_complete_pipeline(self,
                            database_name: str,
                            database_config: Optional[Dict[str, Any]] = None,
                            target_count: int = 100,
                            output_dir: str = "output",
                            use_cache: bool = True) -> Dict[str, Any]:
        """运行完整的管道
        
        参数:
            database_name: 数据库名称
            database_config: 数据库连接配置
            target_count: 目标问题数量
            output_dir: 输出目录
            use_cache: 是否使用缓存
            
        返回:
            包含分析结果和生成问题的字典
        """
        start_time = datetime.now()
        timestamp = start_time.strftime("%Y%m%d_%H%M%S")
        
        # 准备输出目录
        output_dir = self._prepare_output_directory(output_dir)
        
        # 执行分析阶段
        analysis_result = self._execute_analysis_phase(
            database_name, database_config, use_cache
        )
        
        # 执行生成阶段
        questions = self._execute_generation_phase(
            analysis_result, target_count, output_dir, timestamp
        )
        
        # 创建总结报告
        summary = self._create_pipeline_summary(
            database_name, analysis_result, questions,
            start_time, target_count, use_cache,
            output_dir, timestamp
        )
        
        # 保存总结报告
        self._save_pipeline_summary(summary, output_dir, database_name, timestamp)
        
        return {
            "analysis_result": analysis_result,
            "questions": questions,
            "summary": summary
        }
    
    def clear_cache(self, database_name: Optional[str] = None):
        """清理缓存
        
        参数:
            database_name: 数据库名称，如果为None则清理所有缓存
        """
        if database_name:
            # 清理特定数据库的缓存
            cache_files = [
                os.path.join(self.cache_dir, f"{database_name}_analysis.pkl"),
                os.path.join(self.cache_dir, f"{database_name}_analysis_summary.json")
            ]
            
            for cache_file in cache_files:
                if os.path.exists(cache_file):
                    os.remove(cache_file)
                    logger.info(f"已删除缓存: {cache_file}")
        else:
            # 清理所有缓存
            import shutil
            if os.path.exists(self.cache_dir):
                shutil.rmtree(self.cache_dir)
                os.makedirs(self.cache_dir)
                logger.info("已清理所有缓存")
    
    # ========== Pipeline相关的私有方法 ==========
    
    def _prepare_output_directory(self, output_dir: str) -> str:
        """准备输出目录"""
        os.makedirs(output_dir, exist_ok=True)
        return output_dir
    
    def _execute_analysis_phase(self,
                               database_name: str,
                               database_config: Optional[Dict[str, Any]],
                               use_cache: bool) -> AnalysisResult:
        """执行分析阶段"""
        logger.info("=== 步骤1：数据库分析 ===")
        analysis_cache_path = os.path.join(self.cache_dir, f"{database_name}_analysis.pkl")
        
        return self.analyze_database(
            database_name=database_name,
            database_config=database_config,
            cache_path=analysis_cache_path,
            use_cache=use_cache
        )
    
    def _execute_generation_phase(self,
                                 analysis_result: AnalysisResult,
                                 target_count: int,
                                 output_dir: str,
                                 timestamp: str) -> List[Dict[str, Any]]:
        """执行生成阶段"""
        logger.info("=== 步骤2：问题生成 ===")
        questions_output_path = os.path.join(
            output_dir,
            f"{analysis_result.database_name}_questions_{timestamp}.json"
        )
        
        return self.generate_questions(
            analysis_result=analysis_result,
            target_count=target_count,
            output_path=questions_output_path,
            cache_analysis=True
        )
    
    def _create_pipeline_summary(self,
                                database_name: str,
                                analysis_result: AnalysisResult,
                                questions: List[Dict[str, Any]],
                                start_time: datetime,
                                target_count: int,
                                use_cache: bool,
                                output_dir: str = None,
                                timestamp: str = None) -> Dict[str, Any]:
        """创建管道执行总结"""
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        analysis_cache_path = os.path.join(self.cache_dir, f"{database_name}_analysis.pkl")
        
        summary = {
            "database_name": database_name,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "analysis": {
                "total_tables": len(analysis_result.database_schema.tables),
                "total_columns": sum(
                    len(t.columns) for t in analysis_result.database_schema.tables
                ),
                "domain_type": analysis_result.domain_knowledge.domain_type,
                "cache_used": use_cache and os.path.exists(analysis_cache_path)
            },
            "generation": {
                "target_count": target_count,
                "actual_count": len(questions),
                "scenarios": self._count_by_scenario(questions),
                "complexities": self._count_by_complexity(questions)
            }
        }
        
        # 添加输出文件信息
        if output_dir and timestamp:
            summary["output_files"] = {
                "questions": os.path.join(output_dir, f"{database_name}_questions_{timestamp}.json"),
                "summary": os.path.join(output_dir, f"{database_name}_summary_{timestamp}.json")
            }
        
        logger.info(f"完整管道执行完成，耗时: {duration:.2f}秒")
        return summary
    
    def _save_pipeline_summary(self,
                             summary: Dict[str, Any],
                             output_dir: str,
                             database_name: str,
                             timestamp: str):
        """保存管道执行总结"""
        summary_path = os.path.join(output_dir, f"{database_name}_summary_{timestamp}.json")
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        logger.info(f"输出文件保存在: {output_dir}")
    
    # ========== 缓存相关的私有方法 ==========
    
    def _load_analysis_cache(self, cache_path: str) -> AnalysisResult:
        """加载分析缓存
        
        参数:
            cache_path: 缓存文件路径
            
        返回:
            分析结果
        """
        with open(cache_path, 'rb') as f:
            data = pickle.load(f)
        
        if not isinstance(data, AnalysisResult):
            raise TypeError(f"缓存数据类型错误，期望 AnalysisResult，实际为 {type(data)}")
        
        logger.info("成功从缓存加载分析结果")
        return data
    
    def _save_analysis_cache(self, analysis_result: AnalysisResult, cache_path: str):
        """保存分析缓存
        
        参数:
            analysis_result: 分析结果
            cache_path: 缓存文件路径
        """
        # 确保目录存在
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        
        # 使用pickle保存完整对象
        with open(cache_path, 'wb') as f:
            pickle.dump(analysis_result, f)
        
        logger.info(f"分析结果已缓存到: {cache_path}")
    
    def _save_analysis_summary(self, analysis_result: AnalysisResult, summary_path: str):
        """保存分析摘要（轻量级）
        
        参数:
            analysis_result: 分析结果
            summary_path: 摘要文件路径
        """
        # 提取关键信息用于生成
        summary = {
            "database_name": analysis_result.database_name,
            "timestamp": analysis_result.analysis_timestamp.isoformat(),
            "tables": [
                {
                    "name": table.name,
                    "columns": len(table.columns),
                    "rows": next(
                        (desc.row_count for desc in analysis_result.table_descriptions 
                         if desc.table_name == table.name),
                        None
                    )
                }
                for table in analysis_result.database_schema.tables
            ],
            "domain": {
                "type": analysis_result.domain_knowledge.domain_type,
                "description": analysis_result.domain_knowledge.description,
                "key_entities": analysis_result.domain_knowledge.key_entities
            },
            "statistics": analysis_result.analysis_stats
        }
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
    
    # ========== 文件保存相关的私有方法 ==========
    
    def _save_questions(self, questions: List[Dict[str, Any]], output_path: str):
        """保存生成的问题
        
        参数:
            questions: 问题列表（字典格式）
            output_path: 输出文件路径
        """
        # 新格式的问题已经是字典，可以直接序列化
        questions_data = questions
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(questions_data, f, ensure_ascii=False, indent=2)
    
    # ========== 统计相关的私有方法 ==========
    
    def _count_by_scenario(self, questions: List[Dict[str, Any]]) -> Dict[str, int]:
        """按场景统计问题数量
        
        参数:
            questions: 问题列表
            
        返回:
            场景统计
        """
        counts = {}
        for q in questions:
            # 从metadata中获取场景信息
            metadata = q.get('metadata', {})
            main_scenario = metadata.get('main_scenario', 'unknown')
            sub_scenario = metadata.get('sub_scenario', 'unknown')
            scenario_name = f"{main_scenario}/{sub_scenario}"
            counts[scenario_name] = counts.get(scenario_name, 0) + 1
        return counts
    
    def _count_by_complexity(self, questions: List[Dict[str, Any]]) -> Dict[int, int]:
        """按复杂度统计问题数量
        
        参数:
            questions: 问题列表
            
        返回:
            复杂度统计
        """
        counts = {}
        for q in questions:
            # 从metadata中获取复杂度信息
            metadata = q.get('metadata', {})
            complexity = metadata.get('complexity', 'unknown')
            complexity_level = metadata.get('complexity_level', complexity)
            counts[complexity_level] = counts.get(complexity_level, 0) + 1
        return counts