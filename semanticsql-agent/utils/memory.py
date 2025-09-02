"""
记忆管理模块 - 基于 LangChain BaseMemory
适配 LangChain 0.3.x 版本
"""
from typing import Dict, Any, List
from langchain_core.memory import BaseMemory
from pydantic import Field
import json
import logging


class DatabaseAnalysisMemory(BaseMemory):
    """数据库分析结果记忆管理
    
    基于 LangChain BaseMemory 实现，存储数据库分析的所有结果
    """
    
    # 存储的记忆变量
    memories: Dict[str, Any] = Field(default_factory=dict)
    
    # 记忆键
    memory_key: str = "db_analysis"
    
    # 压缩配置
    enable_compression: bool = Field(default=True)
    max_schema_size: int = Field(default=50000)  # 50KB limit for schema data
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 直接设置为实例属性，避开Pydantic验证
        object.__setattr__(self, 'logger', logging.getLogger(__name__))
    
    # 返回的记忆变量键列表
    @property
    def memory_variables(self) -> List[str]:
        """返回记忆变量列表"""
        return [self.memory_key]
    
    def clear(self):
        """清空记忆"""
        self.memories = {}
    
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """加载记忆变量
        
        Args:
            inputs: 输入参数（LangChain 要求的接口）
            
        Returns:
            包含记忆的字典，结构为 {memory_key: {analysis_type: analysis_data}}
        """
        # 确保返回正确的嵌套结构供工具使用
        return {self.memory_key: self.memories}
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        """保存上下文到记忆
        
        Args:
            inputs: 输入参数，应包含 tool_name 或可以从 inputs 中推断
            outputs: 工具的输出结果
        """
        import sys
        print(f"[MEMORY] save_context 方法被调用 - FORCED OUTPUT")
        sys.stdout.flush()
        try:
            print(f"[MEMORY] save_context 方法被调用")
            print(f"[DEBUG] save_context called with inputs: {inputs}")
            print(f"[DEBUG] outputs type: {type(outputs)}, keys: {list(outputs.keys()) if isinstance(outputs, dict) else 'Not dict'}")
            sys.stdout.flush()
        except Exception as e:
            print(f"[ERROR] Exception in save_context debug prints: {e}")
            import traceback
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            sys.stdout.flush()
            return
        
        # 尝试从多个位置获取工具名称
        tool_name = None
        if "tool_name" in inputs:
            tool_name = inputs["tool_name"]
            print(f"[DEBUG] Found tool_name in inputs: {tool_name}")
        elif "input" in inputs and isinstance(inputs["input"], dict):
            tool_name = inputs["input"].get("tool_name")
            print(f"[DEBUG] Found tool_name in nested input: {tool_name}")
        elif "action" in inputs:
            # 从 LangChain agent 的 action 中获取
            action = inputs["action"]
            if hasattr(action, 'tool'):
                tool_name = action.tool
                print(f"[DEBUG] Found tool_name in action: {tool_name}")
        
        # 如果仍然没有找到工具名称，尝试从输出中推断
        if not tool_name and isinstance(outputs, dict):
            # 检查输出结构特征来推断工具类型
            # 首先检查是否有嵌套的 output 键
            output_data = outputs.get("output", outputs)
            
            if isinstance(output_data, dict):
                if "tables" in output_data and "columns" in output_data:
                    tool_name = "schema_extraction"
                    print(f"[DEBUG] Inferred tool_name from output structure: {tool_name}")
                elif "primary_domain" in output_data and "entities" in output_data:
                    tool_name = "domain_analysis"
                    print(f"[DEBUG] Inferred tool_name from output structure: {tool_name}")
                elif "field_classifications" in output_data:
                    tool_name = "field_classification"
                    print(f"[DEBUG] Inferred tool_name from output structure: {tool_name}")
        
        print(f"[DEBUG] Final tool_name: {tool_name}")
        
        # 根据工具名称更新对应的记忆
        # 获取实际的数据（可能在 output 键中）
        actual_data = outputs.get("output", outputs) if isinstance(outputs, dict) else outputs
        
        if tool_name == "schema_extraction":
            print(f"[DEBUG] Saving schema_extraction data to memory")
            self.memories["schema_info"] = actual_data
            print(f"[DEBUG] Saved schema_info, memory keys: {list(self.memories.keys())}")
        elif tool_name == "domain_analysis":
            self.memories["domain_info"] = actual_data
        elif tool_name == "field_classification":
            self.memories["field_classification"] = actual_data
        elif tool_name == "column_meaning_analysis":
            self.memories["column_meanings"] = actual_data
        elif tool_name == "table_meaning_analysis":
            self.memories["table_meanings"] = actual_data
        elif tool_name == "er_analysis":
            self.memories["er_relations"] = actual_data
        else:
            # 对于其他工具，可以选择保存或忽略
            if tool_name:
                self.memories[f"tool_{tool_name}"] = actual_data
    
    def update_analysis(self, analysis_type: str, result: Dict[str, Any]):
        """更新特定类型的分析结果
        
        Args:
            analysis_type: 分析类型
            result: 分析结果
        """
        # 暂时禁用压缩避免FieldInfo错误
        # if analysis_type == "schema_info" and self.enable_compression:
        #     result = self._compress_schema_data(result)
        
        self.memories[analysis_type] = result
        self.logger.info(f"Successfully updated {analysis_type} in memory (data size: {len(str(result))} chars)")
        self.logger.debug(f"Memory now contains: {list(self.memories.keys())}")
    
    def _compress_schema_data(self, schema_data: Dict[str, Any]) -> Dict[str, Any]:
        """压缩schema数据以减少内存占用"""
        try:
            # 估算原始大小
            original_size = len(json.dumps(schema_data, ensure_ascii=False))
            
            if original_size <= self.max_schema_size:
                return schema_data
            
            self.logger.info(f"Schema data size ({original_size} bytes) exceeds limit, applying compression")
            
            compressed_data = schema_data.copy()
            tables = compressed_data.get("tables", {})
            
            # 压缩策略
            for table_name, table_info in tables.items():
                # 移除样本数据（最占空间）
                if "sample_data" in table_info:
                    del table_info["sample_data"]
                
                # 压缩列信息（适配字典格式）
                columns = table_info.get("columns", {})
                if isinstance(columns, dict):
                    for column_name, column_info in columns.items():
                        # 简化默认值
                        if column_info.get("default") == "NULL":
                            column_info["default"] = None
                        # 移除空注释
                        if not column_info.get("comment"):
                            column_info.pop("comment", None)
                
                # 移除空索引
                if not table_info.get("indexes"):
                    table_info.pop("indexes", None)
                
                # 移除空外键
                if not table_info.get("foreign_keys"):
                    table_info.pop("foreign_keys", None)
            
            # 验证压缩后大小
            compressed_size = len(json.dumps(compressed_data, ensure_ascii=False))
            compression_ratio = compressed_size / original_size
            
            self.logger.info(f"Schema compression: {original_size} -> {compressed_size} bytes (ratio: {compression_ratio:.2f})")
            
            return compressed_data
            
        except Exception as e:
            self.logger.warning(f"Schema compression failed: {e}, using original data")
            return schema_data
    
    def get_analysis(self, analysis_type: str) -> Dict[str, Any]:
        """获取特定类型的分析结果
        
        Args:
            analysis_type: 分析类型
            
        Returns:
            分析结果，如果不存在返回空字典
        """
        result = self.memories.get(analysis_type, {})
        
        if result:
            self.logger.debug(f"Retrieved {analysis_type} from memory (size: {len(str(result))} chars)")
        else:
            self.logger.debug(f"No data found for {analysis_type} in memory. Available: {list(self.memories.keys())}")
        return result
    
    def has_complete_analysis(self) -> bool:
        """检查是否有完整的数据库分析结果"""
        try:
            # 确保memories是字典类型
            if not isinstance(self.memories, dict):
                self.memories = {}
                return False
                
            required_analyses = [
                "schema_info", "domain_info", "field_classification",
                "column_meanings", "table_meanings", "er_relations"
            ]
            return all(analysis in self.memories for analysis in required_analyses)
        except Exception:
            # 如果检查失败，重置memories并返回False
            self.memories = {}
            return False
    
    def get_summary(self) -> str:
        """获取记忆摘要"""
        if not self.memories:
            return "无数据库分析结果"
        
        schema_info = self.memories.get("schema_info", {})
        domain_info = self.memories.get("domain_info", {})
        
        summary_parts = []
        
        # 数据库结构摘要
        if schema_info:
            tables = schema_info.get("tables", {})
            summary_parts.append(f"数据库包含 {len(tables)} 个表")
            if tables:
                table_names = list(tables.keys())[:3]
                summary_parts.append(f"主要表: {', '.join(table_names)}")
        
        # 业务领域摘要
        if domain_info:
            primary_domain = domain_info.get("primary_domain", "")
            if primary_domain:
                summary_parts.append(f"业务领域: {primary_domain}")
        
        # 分析完整性
        analysis_status = []
        for analysis_name in ["field_classification", "column_meanings", "table_meanings", "er_relations"]:
            if analysis_name in self.memories:
                analysis_status.append(analysis_name.replace("_", " "))
        
        if analysis_status:
            summary_parts.append(f"已完成分析: {', '.join(analysis_status)}")
        
        return "; ".join(summary_parts) if summary_parts else "数据库分析进行中"