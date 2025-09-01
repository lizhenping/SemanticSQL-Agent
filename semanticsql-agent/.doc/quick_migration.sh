#!/bin/bash
# SemanticSQL Agent 快速改造脚本
# 使用方法: bash quick_migration.sh [阶段编号]

set -e  # 遇到错误立即退出

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印带颜色的信息
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# 第一阶段：清理和准备
stage1() {
    print_info "开始第一阶段：清理和准备"
    
    # 创建分支
    print_info "创建功能分支..."
    git checkout -b feature/langchain-integration || print_warning "分支可能已存在"
    
    # 删除冗余文件
    print_info "删除冗余文件..."
    rm -f debug_model.py list_models.py main.py simple_test.py test_llm.py setup.py
    rm -f agent/simple_generation_agent.py
    rm -f config/trae_config.py
    
    # 安装依赖
    print_info "安装依赖包..."
    pip install langchain==0.2.16
    pip install langchain-openai==0.1.25
    pip install langchain-community==0.2.16
    pip install jinja2==3.1.2
    
    print_info "第一阶段完成！"
}

# 第二阶段：创建基础模块
stage2() {
    print_info "开始第二阶段：创建基础模块"
    
    # 移动callbacks
    print_info "移动callbacks.py..."
    if [ -f "agent/callbacks.py" ]; then
        mv agent/callbacks.py utils/callbacks.py
    else
        print_warning "agent/callbacks.py 不存在或已移动"
    fi
    
    # 创建memory.py
    print_info "创建memory.py..."
    cat > utils/memory.py << 'EOF'
"""
记忆管理模块 - 基于 LangChain BaseMemory
"""
from typing import Dict, Any, List
from langchain.memory import BaseMemory
from pydantic import Field

class DatabaseAnalysisMemory(BaseMemory):
    """数据库分析结果记忆管理"""
    
    memories: Dict[str, Any] = Field(default_factory=dict)
    memory_key: str = "db_analysis"
    
    def clear(self):
        self.memories = {}
    
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {self.memory_key: self.memories}
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]):
        tool_name = inputs.get("tool_name")
        if tool_name:
            self.memories[tool_name] = outputs
    
    def update_analysis(self, analysis_type: str, result: Dict[str, Any]):
        self.memories[analysis_type] = result
EOF
    
    # 创建缺失的工具
    print_info "创建column_meaning_tool.py..."
    mkdir -p tools/analysis_tools
    cat > tools/analysis_tools/column_meaning_tool.py << 'EOF'
from typing import Dict, Any, Type
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

class ColumnMeaningInput(BaseModel):
    memory: Dict[str, Any] = Field(description="数据库分析记忆")

class ColumnMeaningTool(BaseTool):
    name = "column_meaning_analysis"
    description = "分析数据库列的业务含义"
    args_schema: Type[BaseModel] = ColumnMeaningInput
    
    def _run(self, memory: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "column_meanings": {},
            "business_terms": {},
            "data_patterns": {}
        }
EOF
    
    print_info "创建table_meaning_tool.py..."
    cat > tools/analysis_tools/table_meaning_tool.py << 'EOF'
from typing import Dict, Any, Type
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

class TableMeaningInput(BaseModel):
    memory: Dict[str, Any] = Field(description="数据库分析记忆")

class TableMeaningTool(BaseTool):
    name = "table_meaning_analysis"
    description = "分析数据库表的业务含义"
    args_schema: Type[BaseModel] = TableMeaningInput
    
    def _run(self, memory: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "table_purposes": {},
            "table_relationships": {},
            "business_entities": {}
        }
EOF
    
    print_info "第二阶段完成！"
}

# 第三阶段：改造工具（示例）
stage3() {
    print_info "开始第三阶段：改造工具"
    print_warning "这个阶段需要手动修改每个工具，脚本只能提供指导"
    
    # 删除base_tool.py
    rm -f tools/base_tool.py
    
    print_info "请按照以下步骤手动修改每个工具："
    echo "1. 将 'from tools.base_tool import BaseTool' 改为 'from langchain.tools import BaseTool'"
    echo "2. 创建 Pydantic 输入模型（继承 BaseModel）"
    echo "3. 将 _execute 方法改为 _run"
    echo "4. 统一参数为 memory"
    echo "5. 更新异常处理"
    
    print_info "工具列表："
    find tools -name "*.py" -type f | grep -v __pycache__ | grep -v __init__
}

# 验证阶段
verify_stage() {
    stage=$1
    print_info "验证第${stage}阶段..."
    
    case $stage in
        1)
            # 验证文件删除
            if [ ! -f "debug_model.py" ] && [ ! -f "main.py" ]; then
                print_info "✓ 冗余文件已删除"
            else
                print_error "✗ 仍有冗余文件存在"
            fi
            
            # 验证依赖
            python -c "import langchain" && print_info "✓ LangChain 已安装" || print_error "✗ LangChain 未安装"
            ;;
        2)
            # 验证模块
            python -c "from utils.memory import DatabaseAnalysisMemory" && print_info "✓ Memory 模块正常" || print_error "✗ Memory 模块错误"
            ;;
        *)
            print_warning "暂无第${stage}阶段的自动验证"
            ;;
    esac
}

# 主函数
main() {
    if [ $# -eq 0 ]; then
        print_info "使用方法: $0 [阶段编号]"
        print_info "阶段列表:"
        echo "  1 - 清理和准备"
        echo "  2 - 创建基础模块"
        echo "  3 - 改造工具（指导）"
        echo "  verify [阶段] - 验证特定阶段"
        exit 1
    fi
    
    case $1 in
        1)
            stage1
            verify_stage 1
            ;;
        2)
            stage2
            verify_stage 2
            ;;
        3)
            stage3
            ;;
        verify)
            if [ $# -eq 2 ]; then
                verify_stage $2
            else
                print_error "请指定要验证的阶段"
            fi
            ;;
        *)
            print_error "未知的阶段: $1"
            exit 1
            ;;
    esac
}

# 运行主函数
main "$@"