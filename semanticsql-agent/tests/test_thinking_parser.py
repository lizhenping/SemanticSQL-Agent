"""测试 Thinking Parser"""

import pytest
from utils.thinking_parser import ThinkingOutputParser


class TestThinkingOutputParser:
    """测试 ThinkingOutputParser"""
    
    def test_parse_with_thinking_tags(self):
        """测试带有thinking标签的解析"""
        parser = ThinkingOutputParser()
        
        # 测试用例1：标准thinking标签
        input1 = """<thinking>
        我需要分析这个问题...
        首先考虑A，然后考虑B
        </thinking>
        
        最终答案是42。"""
        
        result1 = parser.parse(input1)
        assert "我需要分析这个问题" in result1["thinking"]
        assert result1["answer"] == "最终答案是42。"
        assert result1["has_thinking"] is True
    
    def test_parse_without_thinking_tags(self):
        """测试没有thinking标签的解析"""
        parser = ThinkingOutputParser()
        
        input2 = "这是一个直接的答案。"
        result2 = parser.parse(input2)
        
        assert result2["thinking"] == ""
        assert result2["answer"] == "这是一个直接的答案。"
        assert result2["has_thinking"] is False
    
    def test_parse_multiple_thinking_tags(self):
        """测试多个thinking标签"""
        parser = ThinkingOutputParser()
        
        input3 = """<thinking>第一个思考</thinking>
        中间内容
        <thinking>第二个思考</thinking>
        最终内容"""
        
        result3 = parser.parse(input3)
        assert "第一个思考" in result3["thinking"]
        assert "第二个思考" in result3["thinking"]
        assert result3["answer"] == "中间内容\n        \n        最终内容"
    
    def test_parse_think_tag_variant(self):
        """测试think标签变体"""
        parser = ThinkingOutputParser()
        
        input4 = "<think>简短思考</think>答案"
        result4 = parser.parse(input4)
        
        assert result4["thinking"] == "简短思考"
        assert result4["answer"] == "答案"
    
    def test_case_insensitive(self):
        """测试大小写不敏感"""
        parser = ThinkingOutputParser()
        
        input5 = "<THINKING>大写思考</THINKING>答案"
        result5 = parser.parse(input5)
        
        assert result5["thinking"] == "大写思考"
        assert result5["answer"] == "答案"




def test_format_instructions():
    """测试格式说明"""
    parser = ThinkingOutputParser()
    instructions = parser.get_format_instructions()
    
    assert "<thinking>" in instructions
    assert "</thinking>" in instructions


if __name__ == "__main__":
    pytest.main([__file__, "-v"])