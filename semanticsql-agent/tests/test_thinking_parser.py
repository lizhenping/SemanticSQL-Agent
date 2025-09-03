"""测试 Thinking Parser"""

import pytest
from utils.thinking_parser import ThinkingOutputParser, ReActThinkingParser


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


class TestReActThinkingParser:
    """测试 ReActThinkingParser"""
    
    def test_parse_react_with_thinking(self):
        """测试带thinking的ReAct格式解析"""
        parser = ReActThinkingParser()
        
        input_text = """<thinking>
        我需要使用工具来解决这个问题
        </thinking>
        
        Thought: 我需要查询数据库
        Action: query_tool
        Action Input: {"query": "SELECT * FROM users"}"""
        
        result = parser.parse(input_text)
        
        assert "我需要使用工具" in result["thinking"]
        assert result["thought"] == "我需要查询数据库"
        assert result["action"] == "query_tool"
        assert result["action_input"] == '{"query": "SELECT * FROM users"}'
        assert result["is_final"] is False
    
    def test_parse_react_final_answer(self):
        """测试最终答案格式"""
        parser = ReActThinkingParser()
        
        input_text = """Thought: 我已经得到了所有需要的信息
        Final Answer: 数据库中有100个用户"""
        
        result = parser.parse(input_text)
        
        assert result["thought"] == "我已经得到了所有需要的信息"
        assert result["final_answer"] == "数据库中有100个用户"
        assert result["is_final"] is True
        assert result["action"] is None
    
    def test_parse_complex_react(self):
        """测试复杂的ReAct输出"""
        parser = ReActThinkingParser()
        
        input_text = """<thinking>
        这是一个复杂的问题，需要多步处理
        1. 首先查询用户表
        2. 然后分析数据
        </thinking>
        
        Thought: 根据我的分析，需要先获取用户数据。
        让我查询一下数据库。
        Action: sql_query
        Action Input: {
            "query": "SELECT COUNT(*) FROM users WHERE active = true",
            "database": "main"
        }"""
        
        result = parser.parse(input_text)
        
        assert "这是一个复杂的问题" in result["thinking"]
        assert "需要先获取用户数据" in result["thought"]
        assert result["action"] == "sql_query"
        # Action Input应该包含完整的JSON
        assert '"query"' in result["action_input"]
        assert '"database"' in result["action_input"]


def test_format_instructions():
    """测试格式说明"""
    parser = ThinkingOutputParser()
    instructions = parser.get_format_instructions()
    
    assert "<thinking>" in instructions
    assert "</thinking>" in instructions


if __name__ == "__main__":
    pytest.main([__file__, "-v"])