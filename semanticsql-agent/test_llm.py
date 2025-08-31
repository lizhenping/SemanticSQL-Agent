#!/usr/bin/env python
"""
测试LLM连接
"""

import openai
from config.settings import Settings

def test_llm_connection():
    """测试LLM连接和模型调用"""
    settings = Settings()
    
    print(f"🤖 测试LLM连接...")
    print(f"📍 模型: {settings.llm_model}")
    print(f"🌐 地址: {settings.llm_base_url}")
    print(f"🔑 API Key: {settings.llm_api_key}")
    
    try:
        # 创建OpenAI客户端
        client = openai.OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url
        )
        
        # 测试简单调用
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "user", "content": "你好，请回复'连接成功'"}
            ],
            temperature=0.1,
            max_tokens=50
        )
        
        result = response.choices[0].message.content.strip()
        print(f"✅ LLM响应: {result}")
        return True
        
    except Exception as e:
        print(f"❌ LLM连接失败: {e}")
        return False

if __name__ == "__main__":
    test_llm_connection()