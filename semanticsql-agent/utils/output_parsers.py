"""LangChain 输出解析器

用于解析 LLM 的输出为结构化数据。
"""

from typing import Dict, Any, Type, List, Optional
from langchain_core.output_parsers import PydanticOutputParser, JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.exceptions import OutputParserException
from pydantic import BaseModel, ValidationError
import json
import re
import logging

logger = logging.getLogger(__name__)


class SmartJsonOutputParser(JsonOutputParser):
    """智能 JSON 输出解析器
    
    能够从文本中提取 JSON 块，并提供更好的错误处理。
    """
    
    def parse(self, text: str) -> Dict[str, Any]:
        """解析输出文本中的 JSON"""
        try:
            # 尝试直接解析
            return super().parse(text)
        except OutputParserException:
            # 尝试提取 JSON 块
            json_str = self._extract_json(text)
            if json_str:
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON 解析失败: {e}")
            
            # 如果还是失败，返回空字典
            logger.warning("无法解析 JSON，返回空字典")
            return {}
    
    def _extract_json(self, text: str) -> Optional[str]:
        """从文本中提取 JSON 字符串"""
        # 查找 JSON 代码块
        json_block_match = re.search(r'```json\s*\n(.*?)\n```', text, re.DOTALL)
        if json_block_match:
            return json_block_match.group(1).strip()
        
        # 查找大括号包围的内容
        brace_match = re.search(r'\{.*\}', text, re.DOTALL)
        if brace_match:
            return brace_match.group(0)
        
        # 查找方括号包围的内容
        bracket_match = re.search(r'\[.*\]', text, re.DOTALL)
        if bracket_match:
            return bracket_match.group(0)
        
        return None


class SmartPydanticOutputParser(PydanticOutputParser):
    """智能 Pydantic 输出解析器
    
    增强了错误处理和 JSON 提取能力。
    """
    
    def __init__(self, pydantic_object: Type[BaseModel], fallback_to_dict: bool = True):
        super().__init__(pydantic_object=pydantic_object)
        self.fallback_to_dict = fallback_to_dict
        self.json_parser = SmartJsonOutputParser()
    
    def parse(self, text: str) -> BaseModel:
        """解析输出文本为 Pydantic 模型"""
        try:
            # 尝试使用父类解析
            return super().parse(text)
        except (OutputParserException, ValidationError) as e:
            logger.warning(f"Pydantic 解析失败: {e}")
            
            # 尝试提取 JSON 并解析
            try:
                json_data = self.json_parser.parse(text)
                if json_data:
                    return self.pydantic_object(**json_data)
            except Exception as json_error:
                logger.error(f"JSON 转换失败: {json_error}")
            
            # 如果允许，返回带默认值的模型
            if self.fallback_to_dict:
                logger.warning("使用默认值创建模型")
                return self._create_default_model()
            
            raise e
    
    def _create_default_model(self) -> BaseModel:
        """创建带默认值的模型实例"""
        # 获取模型的必填字段
        required_fields = {}
        for field_name, field_info in self.pydantic_object.__fields__.items():
            if field_info.required:
                # 根据类型提供默认值
                if field_info.type_ == str:
                    required_fields[field_name] = ""
                elif field_info.type_ == int:
                    required_fields[field_name] = 0
                elif field_info.type_ == float:
                    required_fields[field_name] = 0.0
                elif field_info.type_ == bool:
                    required_fields[field_name] = False
                elif field_info.type_ == list:
                    required_fields[field_name] = []
                elif field_info.type_ == dict:
                    required_fields[field_name] = {}
                else:
                    required_fields[field_name] = None
        
        return self.pydantic_object(**required_fields)


def create_structured_output_parser(
    model_class: Type[BaseModel],
    fallback: bool = True
) -> SmartPydanticOutputParser:
    """创建结构化输出解析器"""
    return SmartPydanticOutputParser(
        pydantic_object=model_class,
        fallback_to_dict=fallback
    )


def get_format_instructions(parser: PydanticOutputParser) -> str:
    """获取格式化指令"""
    return parser.get_format_instructions()


class ListOutputParser(JsonOutputParser):
    """列表输出解析器
    
    专门用于解析列表格式的输出。
    """
    
    def parse(self, text: str) -> List[Any]:
        """解析输出为列表"""
        result = super().parse(text)
        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            # 如果是字典，尝试提取值列表
            return list(result.values())
        else:
            return [result]


class TextToStructuredParser:
    """文本到结构化数据解析器
    
    用于将自由格式的文本解析为结构化数据。
    """
    
    def __init__(self, patterns: Dict[str, str]):
        """
        Args:
            patterns: 键值对，键是字段名，值是正则表达式模式
        """
        self.patterns = patterns
    
    def parse(self, text: str) -> Dict[str, Any]:
        """解析文本"""
        result = {}
        
        for field, pattern in self.patterns.items():
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                # 如果有捕获组，使用第一个捕获组
                if match.groups():
                    result[field] = match.group(1).strip()
                else:
                    result[field] = match.group(0).strip()
        
        return result


# 预定义的解析器模板

def create_domain_analysis_parser():
    """创建领域分析输出解析器"""
    from models.analysis_models import DomainKnowledge
    return create_structured_output_parser(DomainKnowledge)


def create_field_classification_parser():
    """创建字段分类输出解析器"""
    patterns = {
        "category": r"分类[:：]\s*(\w+)",
        "confidence": r"置信度[:：]\s*([\d.]+)",
        "reason": r"理由[:：]\s*(.+?)(?:\n|$)"
    }
    return TextToStructuredParser(patterns)


def create_relationship_parser():
    """创建关系解析器"""
    from models.analysis_models import Relationship
    return create_structured_output_parser(Relationship)


# 用于提示词的格式化指令生成器

def get_json_format_instruction(
    description: str,
    example: Dict[str, Any]
) -> str:
    """生成 JSON 格式指令"""
    example_str = json.dumps(example, ensure_ascii=False, indent=2)
    return f"""
请以 JSON 格式返回{description}。格式示例：

```json
{example_str}
```

确保返回的是有效的 JSON 格式，可以被解析。
"""


def get_pydantic_format_instruction(
    model_class: Type[BaseModel],
    description: str = ""
) -> str:
    """生成 Pydantic 模型的格式指令"""
    parser = PydanticOutputParser(pydantic_object=model_class)
    base_instruction = parser.get_format_instructions()
    
    if description:
        return f"{description}\n\n{base_instruction}"
    return base_instruction