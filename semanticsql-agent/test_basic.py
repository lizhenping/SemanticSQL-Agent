#!/usr/bin/env python3
"""基础功能测试"""

def test_imports():
    """测试基本导入"""
    print("测试导入...")
    
    try:
        # 1. Config
        from utils.config import Config, LLMConfig, DatabaseConfig, AgentConfig
        print("  ✅ Config 导入成功")
        
        # 2. LLM Client
        from utils.llm_clients import LLMClient, LLMMessage, ToolCall, ToolResult
        print("  ✅ LLM Client 导入成功")
        
        # 3. CLI
        from utils.cli import ConsoleFactory, ConsoleMode, ConsoleType
        print("  ✅ CLI 导入成功")
        
        # 4. Agent basics
        from agent.agent_basics import AgentState, AgentStep, AgentExecution
        print("  ✅ Agent basics 导入成功")
        
        # 5. Base Agent
        from agent.base_agent import BaseAgent
        print("  ✅ Base Agent 导入成功")
        
        # 6. Tools
        from tools.base import Tool
        print("  ✅ Tool base 导入成功")
        
        # 7. 具体工具
        from tools.schema_extraction import SchemaExtractionTool
        from tools.sql_generation import SQLGenerationTool
        print("  ✅ 具体工具导入成功")
        
        return True
        
    except ImportError as e:
        print(f"  ❌ 导入失败: {e}")
        return False


def test_dataclass():
    """测试 dataclass"""
    print("\n测试 dataclass...")
    
    try:
        from utils.config import Config, LLMConfig
        import dataclasses
        
        # 检查是否是 dataclass
        if dataclasses.is_dataclass(Config) and dataclasses.is_dataclass(LLMConfig):
            print("  ✅ Config 使用 dataclass")
            
            # 创建实例测试
            config = Config()
            print(f"  ✅ 创建 Config 实例成功")
            return True
        else:
            print("  ❌ Config 不是 dataclass")
            return False
            
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        return False


def test_tool_schema():
    """测试工具的 OpenAI schema"""
    print("\n测试工具 schema...")
    
    try:
        from tools.schema_extraction import SchemaExtractionTool
        
        tool = SchemaExtractionTool()
        schema = tool.to_openai_tool_schema()
        
        # 检查 schema 结构
        assert "type" in schema
        assert "function" in schema
        assert "name" in schema["function"]
        assert "description" in schema["function"]
        
        print(f"  ✅ 工具 schema 生成成功")
        print(f"     - 名称: {schema['function']['name']}")
        print(f"     - 描述: {schema['function']['description'][:50]}...")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        return False


def test_llm_message():
    """测试 LLM 消息"""
    print("\n测试 LLM 消息...")
    
    try:
        from utils.llm_clients import LLMMessage, ToolCall, ToolResult
        
        # 创建普通消息
        msg = LLMMessage(role="user", content="Hello")
        print(f"  ✅ 创建普通消息成功")
        
        # 创建工具调用消息
        tool_call = ToolCall(name="test_tool", call_id="123", arguments={"x": 1})
        msg_with_tool = LLMMessage(role="assistant", content="", tool_call=tool_call)
        print(f"  ✅ 创建工具调用消息成功")
        
        # 创建工具结果消息
        tool_result = ToolResult(name="test_tool", call_id="123", result="OK")
        msg_with_result = LLMMessage(role="tool", content="", tool_result=tool_result)
        print(f"  ✅ 创建工具结果消息成功")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("=" * 60)
    print("🧪 SemanticSQL-Agent 基础功能测试")
    print("=" * 60)
    
    all_passed = True
    
    # 运行测试
    all_passed &= test_imports()
    all_passed &= test_dataclass()
    all_passed &= test_tool_schema()
    all_passed &= test_llm_message()
    
    # 总结
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ 所有测试通过！")
        print("\n核心功能已实现:")
        print("  • 模块化导入结构")
        print("  • Dataclass 配置")
        print("  • OpenAI 工具格式")
        print("  • Tool Calling 消息格式")
    else:
        print("❌ 部分测试失败")
    print("=" * 60)


if __name__ == "__main__":
    main()