"""
SQL生成日志记录工具
记录问题、生成的SQL和执行结果到本地文件
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class SQLLogger:
    """SQL生成活动日志记录器"""
    
    def __init__(self, log_dir: str = "logs/sql_generation"):
        """初始化SQL日志记录器
        
        Args:
            log_dir: 日志文件存储目录
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建日志文件路径
        today = datetime.now().strftime("%Y%m%d")
        self.log_file = self.log_dir / f"sql_generation_{today}.jsonl"
        
        logger.info(f"SQL Logger initialized, log file: {self.log_file}")
    
    def log_sql_generation(
        self,
        question_id: str,
        question_text: str,
        database_name: str,
        generated_sql: str,
        execution_result: Optional[Dict[str, Any]] = None,
        execution_error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录SQL生成活动
        
        Args:
            question_id: 问题ID
            question_text: 问题文本
            database_name: 数据库名称
            generated_sql: 生成的SQL语句
            execution_result: SQL执行结果
            execution_error: SQL执行错误信息
            metadata: 额外的元数据信息
        """
        try:
            # 创建日志记录
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "question_id": question_id,
                "question_text": question_text,
                "database_name": database_name,
                "generated_sql": generated_sql,
                "execution_status": "success" if execution_result is not None else "error",
                "execution_result": execution_result,
                "execution_error": execution_error,
                "metadata": metadata or {}
            }
            
            # 写入到JSONL文件（每行一个JSON记录）
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
                
            logger.debug(f"Logged SQL generation for question {question_id}")
            
        except Exception as e:
            logger.error(f"Failed to log SQL generation: {e}")
    
    def log_batch_results(self, results: List[Dict[str, Any]]) -> None:
        """批量记录SQL生成结果
        
        Args:
            results: 批量结果列表，每个结果包含question_id, question_text等信息
        """
        for result in results:
            self.log_sql_generation(
                question_id=result.get("question_id", ""),
                question_text=result.get("question_text", ""),
                database_name=result.get("database_name", ""),
                generated_sql=result.get("generated_sql", ""),
                execution_result=result.get("execution_result"),
                execution_error=result.get("execution_error"),
                metadata=result.get("metadata")
            )
    
    def get_recent_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取最近的日志记录
        
        Args:
            limit: 返回记录数量限制
            
        Returns:
            最近的日志记录列表
        """
        if not self.log_file.exists():
            return []
        
        logs = []
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                # 取最后limit行
                for line in lines[-limit:]:
                    if line.strip():
                        logs.append(json.loads(line.strip()))
        except Exception as e:
            logger.error(f"Failed to read logs: {e}")
        
        return logs
    
    def get_logs_by_database(self, database_name: str) -> List[Dict[str, Any]]:
        """根据数据库名称获取日志记录
        
        Args:
            database_name: 数据库名称
            
        Returns:
            指定数据库的日志记录列表
        """
        all_logs = self.get_recent_logs(limit=1000)
        return [log for log in all_logs if log.get("database_name") == database_name]
    
    def get_error_logs(self) -> List[Dict[str, Any]]:
        """获取所有错误日志记录
        
        Returns:
            错误日志记录列表
        """
        all_logs = self.get_recent_logs(limit=1000)
        return [log for log in all_logs if log.get("execution_status") == "error"]
    
    def export_logs_to_csv(self, output_file: str) -> None:
        """导出日志到CSV文件
        
        Args:
            output_file: 输出CSV文件路径
        """
        import csv
        
        logs = self.get_recent_logs(limit=10000)
        if not logs:
            logger.warning("No logs to export")
            return
        
        # 定义CSV列
        fieldnames = [
            "timestamp", "question_id", "question_text", "database_name",
            "generated_sql", "execution_status", "execution_error"
        ]
        
        try:
            with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for log in logs:
                    # 只写入基本字段，避免复杂的嵌套结构
                    row = {field: log.get(field, "") for field in fieldnames}
                    writer.writerow(row)
                    
            logger.info(f"Exported {len(logs)} logs to {output_file}")
            
        except Exception as e:
            logger.error(f"Failed to export logs to CSV: {e}")


# 全局SQL日志记录器实例
_sql_logger: Optional[SQLLogger] = None


def get_sql_logger(log_dir: str = "logs/sql_generation") -> SQLLogger:
    """获取全局SQL日志记录器实例
    
    Args:
        log_dir: 日志目录路径
        
    Returns:
        SQLLogger实例
    """
    global _sql_logger
    if _sql_logger is None:
        _sql_logger = SQLLogger(log_dir)
    return _sql_logger


def log_sql_activity(
    question_id: str,
    question_text: str,
    database_name: str,
    generated_sql: str,
    execution_result: Optional[Dict[str, Any]] = None,
    execution_error: Optional[str] = None,
    **metadata
) -> None:
    """便捷函数：记录SQL生成活动
    
    Args:
        question_id: 问题ID
        question_text: 问题文本  
        database_name: 数据库名称
        generated_sql: 生成的SQL语句
        execution_result: SQL执行结果
        execution_error: SQL执行错误信息
        **metadata: 额外的元数据
    """
    logger_instance = get_sql_logger()
    logger_instance.log_sql_generation(
        question_id=question_id,
        question_text=question_text,
        database_name=database_name,
        generated_sql=generated_sql,
        execution_result=execution_result,
        execution_error=execution_error,
        metadata=metadata
    )