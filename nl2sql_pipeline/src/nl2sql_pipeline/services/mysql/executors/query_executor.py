"""查询执行器

负责执行SQL查询和处理结果。
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, Union
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class MySQLQueryExecutor:
    """MySQL查询执行器
    
    职责：
    1. 执行SQL查询
    2. 处理查询结果
    3. 管理参数化查询
    4. 提供批量操作支持
    """
    
    def __init__(self, connection_manager):
        """初始化查询执行器
        
        参数:
            connection_manager: 连接管理器实例
        """
        self.connection_manager = connection_manager
    
    def execute_query(self, query: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """执行查询并返回结果
        
        参数:
            query: SQL查询语句
            params: 查询参数（用于参数化查询）
            
        返回:
            查询结果列表（每行是一个字典）
        """
        try:
            with self.connection_manager.cursor_context() as cursor:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                results = cursor.fetchall()
                return results if results else []
                
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            logger.error(f"Query: {query}")
            if params:
                logger.error(f"Parameters: {params}")
            raise
    
    def execute_single(self, query: str, params: Optional[Tuple] = None) -> Optional[Dict[str, Any]]:
        """执行查询并返回单行结果
        
        参数:
            query: SQL查询语句
            params: 查询参数
            
        返回:
            单行结果或None
        """
        results = self.execute_query(query, params)
        return results[0] if results else None
    
    def execute_scalar(self, query: str, params: Optional[Tuple] = None) -> Any:
        """执行查询并返回单个值
        
        参数:
            query: SQL查询语句
            params: 查询参数
            
        返回:
            查询结果的第一行第一列的值
        """
        result = self.execute_single(query, params)
        if result:
            # 返回第一个值
            return next(iter(result.values()))
        return None
    
    def execute_update(self, query: str, params: Optional[Tuple] = None) -> int:
        """执行更新操作（INSERT/UPDATE/DELETE）
        
        参数:
            query: SQL语句
            params: 查询参数
            
        返回:
            影响的行数
        """
        try:
            with self.connection_manager.cursor_context() as cursor:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                return cursor.rowcount
                
        except Exception as e:
            logger.error(f"Update execution failed: {e}")
            logger.error(f"Query: {query}")
            if params:
                logger.error(f"Parameters: {params}")
            raise
    
    def execute_many(self, query: str, params_list: List[Tuple]) -> int:
        """批量执行相同的SQL语句
        
        参数:
            query: SQL语句模板
            params_list: 参数列表
            
        返回:
            总影响行数
        """
        if not params_list:
            return 0
        
        try:
            with self.connection_manager.cursor_context() as cursor:
                cursor.executemany(query, params_list)
                return cursor.rowcount
                
        except Exception as e:
            logger.error(f"Batch execution failed: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Number of parameter sets: {len(params_list)}")
            raise
    
    def execute_with_pagination(self, 
                              query: str, 
                              params: Optional[Tuple] = None,
                              page_size: int = 1000) -> 'PaginatedResults':
        """执行分页查询
        
        参数:
            query: SQL查询语句（不应包含LIMIT子句）
            params: 查询参数
            page_size: 每页大小
            
        返回:
            分页结果迭代器
        """
        return PaginatedResults(self, query, params, page_size)
    
    def get_column_examples(self, 
                          table_name: str, 
                          column_name: str,
                          schema: Optional[str] = None,
                          limit: int = 100) -> List[Any]:
        """获取列的样例值
        
        参数:
            table_name: 表名
            column_name: 列名
            schema: 数据库名
            limit: 限制数量
            
        返回:
            样例值列表
        """
        table_ref = f"`{schema}`.`{table_name}`" if schema else f"`{table_name}`"
        
        # 构建查询
        query = f"""
        SELECT DISTINCT `{column_name}`
        FROM {table_ref}
        WHERE `{column_name}` IS NOT NULL
        LIMIT %s
        """
        
        results = self.execute_query(query, (limit,))
        return [row[column_name] for row in results]
    
    def get_table_sample(self, 
                        table_name: str,
                        schema: Optional[str] = None,
                        limit: int = 10,
                        random: bool = False) -> List[Dict[str, Any]]:
        """获取表的样本数据
        
        参数:
            table_name: 表名
            schema: 数据库名
            limit: 限制数量
            random: 是否随机采样
            
        返回:
            样本数据列表
        """
        table_ref = f"`{schema}`.`{table_name}`" if schema else f"`{table_name}`"
        
        if random:
            # 随机采样
            query = f"""
            SELECT * FROM {table_ref}
            ORDER BY RAND()
            LIMIT %s
            """
        else:
            # 顺序采样
            query = f"""
            SELECT * FROM {table_ref}
            LIMIT %s
            """
        
        return self.execute_query(query, (limit,))
    
    def count_rows(self, 
                  table_name: str,
                  schema: Optional[str] = None,
                  where_clause: Optional[str] = None) -> int:
        """统计表的行数
        
        参数:
            table_name: 表名
            schema: 数据库名
            where_clause: WHERE子句（不含WHERE关键字）
            
        返回:
            行数
        """
        table_ref = f"`{schema}`.`{table_name}`" if schema else f"`{table_name}`"
        
        query = f"SELECT COUNT(*) AS cnt FROM {table_ref}"
        if where_clause:
            query += f" WHERE {where_clause}"
        
        return self.execute_scalar(query) or 0


class PaginatedResults:
    """分页结果迭代器"""
    
    def __init__(self, executor: MySQLQueryExecutor, query: str, 
                 params: Optional[Tuple], page_size: int):
        self.executor = executor
        self.base_query = query
        self.params = params
        self.page_size = page_size
        self.current_offset = 0
    
    def __iter__(self):
        """迭代器协议"""
        self.current_offset = 0
        return self
    
    def __next__(self) -> List[Dict[str, Any]]:
        """获取下一页数据"""
        # 构建分页查询
        paginated_query = f"{self.base_query} LIMIT {self.page_size} OFFSET {self.current_offset}"
        
        # 执行查询
        results = self.executor.execute_query(paginated_query, self.params)
        
        # 如果没有结果，停止迭代
        if not results:
            raise StopIteration
        
        # 更新偏移量
        self.current_offset += self.page_size
        
        return results
    
    def fetch_all(self) -> List[Dict[str, Any]]:
        """获取所有结果（注意内存使用）"""
        all_results = []
        for page in self:
            all_results.extend(page)
        return all_results