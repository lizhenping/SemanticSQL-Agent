"""
分析工具基类 - 所有分析工具的基类
参考pipeline的简洁设计，去除冗余功能
"""
from typing import Dict, Any, Optional, Union
from pydantic import BaseModel, Field
import json
import logging

from tools.base_tool import BaseSemanticSQLTool
from utils.database import DatabaseManager

logger = logging.getLogger(__name__)


class AnalysisToolInput(BaseModel):
    """分析工具的基础输入模型"""
    input: Union[Dict[str, Any], str] = Field(
        default={},
        description="输入数据，可能是字典或JSON字符串"
    )


class BaseAnalysisTool(BaseSemanticSQLTool):
    """分析工具基类
    
    提供：
    - 数据库管理器访问
    - 记忆管理
    - 通用的输入解析
    """
    
    def __init__(self, **kwargs):
        # 提取我们自己的参数
        db_manager = kwargs.pop('db_manager', None)
        # 调用父类初始化
        super().__init__(**kwargs)
        # 设置db_manager
        if db_manager:
            object.__setattr__(self, 'db_manager', db_manager)
    
    def parse_input(self, input_data: Union[Dict[str, Any], str]) -> Dict[str, Any]:
        """解析输入数据
        
        Args:
            input_data: 输入数据，可能是字典或JSON字符串
            
        Returns:
            解析后的字典
        """
        if isinstance(input_data, str):
            try:
                return json.loads(input_data)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON input: {input_data}")
                return {}
        elif isinstance(input_data, dict):
            return input_data
        else:
            return {}
    
    def get_schema_info(self) -> Dict[str, Any]:
        """获取数据库结构信息
        
        Returns:
            schema信息字典
        """
        return self.get_from_memory("schema_info")
    
    def get_domain_info(self) -> Dict[str, Any]:
        """获取领域信息
        
        Returns:
            领域信息字典
        """
        return self.get_from_memory("domain_info")
    
    def get_field_classification(self) -> Dict[str, Any]:
        """获取字段分类信息
        
        Returns:
            字段分类信息字典
        """
        return self.get_from_memory("field_classification")
    
    def get_column_meanings(self) -> Dict[str, Any]:
        """获取列含义信息
        
        Returns:
            列含义信息字典
        """
        return self.get_from_memory("column_meanings")
    
    def get_table_meanings(self) -> Dict[str, Any]:
        """获取表含义信息
        
        Returns:
            表含义信息字典
        """
        return self.get_from_memory("table_meanings")
    
    def get_er_relations(self) -> Dict[str, Any]:
        """获取ER关系信息
        
        Returns:
            ER关系信息字典
        """
        return self.get_from_memory("er_relations")