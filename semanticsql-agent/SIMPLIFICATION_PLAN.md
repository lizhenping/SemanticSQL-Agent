# SemanticSQL-Agent 简化计划

## 1. 当前问题总结

### 1.1 与 TRAEAgent 的差异
- ✅ 已修复：trajectory_recorder.py 移到 utils/
- ❌ 待修复：models/ 目录过度设计（611行）
- ❌ 待修复：tools/ 过度分类（4层子目录）
- ❌ 待修复：过多的模型抽象

### 1.2 代码统计
```
目录/文件                    行数
models/                      611行 (过度设计)
tools/*/*                    ~1500行 (过度分类)
agent/                       396行 (已简化)
utils/                       ~800行 (合理)
```

## 2. 简化方案

### 2.1 扁平化工具结构
**当前结构**:
```
tools/
├── analysis_tools/
│   ├── schema_extraction_tool.py
│   ├── domain_analysis_tool.py
│   ├── field_classification_tool.py
│   └── er_analysis_tool.py
├── generation_tools/
│   └── sql_generation_tool.py
├── validation_tools/
│   ├── sql_validation_tool.py
│   └── sql_execution_tool.py
└── thinking_tools/
    └── sequential_thinking_tool.py
```

**目标结构** (参考 TRAEAgent):
```
tools/
├── base.py
├── schema_extraction.py
├── domain_analysis.py
├── field_classification.py
├── er_analysis.py
├── sql_generation.py
├── sql_validation.py
├── sql_execution.py
└── sequential_thinking.py
```

### 2.2 简化模型管理

**方案1: 完全移除 models/ (推荐)**
- 在每个工具中定义简单的输入/输出类
- 共享的基础类型放在 utils/types.py

**方案2: 最小化 models/**
- 只保留 QueryResult 等真正共享的模型
- 其他模型就近定义

### 2.3 实施步骤

#### Phase 1: 扁平化工具 (立即执行)
```bash
# 1. 移动所有工具到 tools/ 根目录
mv tools/analysis_tools/*.py tools/
mv tools/generation_tools/*.py tools/
mv tools/validation_tools/*.py tools/
mv tools/thinking_tools/*.py tools/

# 2. 删除空目录
rm -rf tools/*/

# 3. 重命名文件（去掉 _tool 后缀）
mv tools/schema_extraction_tool.py tools/schema_extraction.py
# ... 其他文件类似
```

#### Phase 2: 简化模型 (逐步执行)
1. 创建 utils/types.py 存放基础类型
2. 在各工具中内联定义输入/输出模型
3. 逐步移除 models/ 目录

## 3. 代码示例

### 3.1 简化后的工具示例
```python
# tools/schema_extraction.py
from dataclasses import dataclass
from typing import List, Optional
from tools.base import BaseSemanticSQLTool

class SchemaExtractionTool(BaseSemanticSQLTool):
    """数据库结构提取工具"""
    
    name = "extract_database_schema"
    description = "提取数据库结构信息"
    
    @dataclass
    class Config:
        """工具配置"""
        tables: Optional[List[str]] = None
        include_indexes: bool = False
    
    def execute(self, **kwargs):
        config = self.Config(**kwargs)
        # 执行逻辑
        return {
            "tables": [...],
            "summary": "..."
        }
```

### 3.2 共享类型示例
```python
# utils/types.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class QueryResult:
    """查询结果 - 真正的共享类型"""
    success: bool
    question: str
    sql: Optional[str] = None
    answer: Optional[str] = None
    error: Optional[str] = None
```

## 4. 预期效果

### 4.1 代码减少
- models/: 611行 → 0行（或 <50行）
- tools/: 更清晰的结构
- 总体减少 ~30% 代码量

### 4.2 结构简化
- 更接近 TRAEAgent 的设计
- 减少导入复杂度
- 提高可维护性

## 5. 风险与对策

### 5.1 风险
- 重构可能影响现有功能
- 需要更新所有导入路径

### 5.2 对策
- 分阶段执行
- 保持功能测试
- 使用版本控制跟踪变更

## 6. 执行优先级

1. **立即**: 扁平化工具目录
2. **本周**: 简化工具内的模型定义
3. **下周**: 评估是否完全移除 models/