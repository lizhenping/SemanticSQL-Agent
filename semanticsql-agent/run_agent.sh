#!/bin/bash

# SemanticSQL Agent V2 运行脚本

# 设置 Python 路径
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# 默认配置文件
DEFAULT_CONFIG="examples/config.yaml"

# 检查是否提供了参数
if [ $# -eq 0 ]; then
    echo "SemanticSQL Agent V2 - 优化的 NL2SQL 智能体"
    echo ""
    echo "用法:"
    echo "  ./run_agent.sh query <查询内容>              # 执行单次查询"
    echo "  ./run_agent.sh interactive                   # 进入交互模式"
    echo "  ./run_agent.sh validate                      # 验证配置文件"
    echo "  ./run_agent.sh list-tools                    # 列出可用工具"
    echo "  ./run_agent.sh --help                        # 显示帮助"
    echo ""
    echo "示例:"
    echo "  ./run_agent.sh query \"查询所有订单\""
    echo "  ./run_agent.sh query \"统计每月销售额\" --config myconfig.yaml"
    echo "  ./run_agent.sh interactive --mode multiline"
    echo ""
    exit 0
fi

# 运行 CLI
python cli_v2.py "$@"