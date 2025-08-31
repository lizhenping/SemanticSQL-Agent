#!/usr/bin/env python
"""
获取可用模型列表
"""

import openai
from config.settings import Settings

def list_available_models():
    """获取可用模型列表"""
    settings = Settings()
    
    print(f"🔍 查询可用模型...")
    print(f"🌐 LLM服务地址: {settings.llm_base_url}")
    
    try:
        client = openai.OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url
        )
        
        # 获取模型列表
        models = client.models.list()
        
        print(f"📋 共找到 {len(models.data)} 个可用模型:")
        print("=" * 50)
        
        for i, model in enumerate(models.data, 1):
            print(f"{i:2d}. {model.id}")
            if hasattr(model, 'created'):
                print(f"    创建时间: {model.created}")
            if hasattr(model, 'owned_by'):
                print(f"    所有者: {model.owned_by}")
            print()
        
        # 查找包含Qwen的模型
        qwen_models = [m.id for m in models.data if 'qwen' in m.id.lower()]
        if qwen_models:
            print(f"🎯 找到Qwen相关模型:")
            for model in qwen_models:
                print(f"  - {model}")
        
        return True
        
    except Exception as e:
        print(f"❌ 获取模型列表失败: {e}")
        return False

if __name__ == "__main__":
    list_available_models()