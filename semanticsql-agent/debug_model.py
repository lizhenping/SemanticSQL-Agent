#!/usr/bin/env python
"""
调试模型调用问题
"""

import openai
from config.settings import Settings

def debug_model_call():
    """调试模型调用"""
    settings = Settings()
    
    print(f"🔧 调试模型调用...")
    print(f"📍 配置的模型: '{settings.llm_model}'")
    print(f"🌐 配置的地址: '{settings.llm_base_url}'")
    
    # 创建客户端
    client = openai.OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url
    )
    
    # 测试和agent相同的调用方式
    llm_config = {
        'model': settings.llm_model,
        'temperature': settings.llm_temperature,
        'max_tokens': settings.llm_max_tokens
    }
    
    print(f"🔧 LLM配置: {llm_config}")
    
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "user", "content": "简单回复'OK'"}
            ],
            **llm_config
        )
        
        result = response.choices[0].message.content.strip()
        print(f"✅ 模型响应: {result}")
        
        # 测试可用模型列表
        try:
            models = client.models.list()
            print(f"📋 可用模型数量: {len(models.data)}")
            if models.data:
                print("📋 前5个可用模型:")
                for model in models.data[:5]:
                    print(f"  - {model.id}")
        except Exception as e:
            print(f"⚠️ 无法获取模型列表: {e}")
            
        return True
        
    except Exception as e:
        print(f"❌ 模型调用失败: {e}")
        
        # 尝试获取错误详情
        if "404" in str(e):
            print("🔍 404错误通常表示模型名称不正确")
            print("💡 建议检查您的LLM服务中的实际模型名称")
        
        return False

if __name__ == "__main__":
    debug_model_call()