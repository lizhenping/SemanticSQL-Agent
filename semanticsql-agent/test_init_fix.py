"""
测试并修复初始化问题
"""

# 测试Pydantic验证问题
from pydantic import BaseModel, Field
from typing import Type

class MyModel(BaseModel):
    name: str = "test"
    description: str = "test"
    
    # 这会导致验证错误
    # custom_field: str = Field()
    
    def __init__(self, custom_param=None, **kwargs):
        super().__init__(**kwargs)
        if custom_param:
            object.__setattr__(self, 'custom_param', custom_param)

# 测试
try:
    model = MyModel(custom_param="test")
    print("成功创建model")
    print(f"name: {model.name}")
    print(f"custom_param: {getattr(model, 'custom_param', 'NOT SET')}")
except Exception as e:
    print(f"错误: {e}")