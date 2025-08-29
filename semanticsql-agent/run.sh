#!/bin/bash

# SemanticSQL Agent 运行脚本

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 帮助信息
usage() {
    echo "用法: $0 [命令] [参数]"
    echo ""
    echo "命令:"
    echo "  init           - 初始化配置"
    echo "  run            - 执行单条查询"
    echo "  interactive    - 交互模式"
    echo "  schema         - 查看数据库结构"
    echo "  test           - 测试数据库连接"
    echo "  help           - 显示帮助"
    echo ""
    echo "示例:"
    echo "  $0 init mysql 192.168.200.216 13306 testdb"
    echo "  $0 run \"查询所有用户数量\""
    echo "  $0 interactive"
    echo "  $0 schema"
    echo "  $0 test"
}

# 检查Python环境
check_python() {
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}错误: Python3 未安装${NC}"
        exit 1
    fi
    
    if ! python3 -c "import click" &> /dev/null; then
        echo -e "${YELLOW}安装依赖中...${NC}"
        pip install click pyyaml sqlalchemy langchain-community aiomysql aiosqlite asyncpg
    fi
}

# 初始化配置
init_config() {
    local db_type=${1:-mysql}
    local host=${2:-192.168.200.216}
    local port=${3:-13306}
    local database=${4:-testdb}
    
    echo -e "${GREEN}初始化配置...${NC}"
    python3 main.py init \
        --database-type "$db_type" \
        --host "$host" \
        --port "$port" \
        --database "$database" \
        --model Qwen3-14B
    
    echo -e "${GREEN}配置已生成: trae_config.yaml${NC}"
}

# 执行查询
run_query() {
    local query="$1"
    if [ -z "$query" ]; then
        echo -e "${RED}错误: 查询语句不能为空${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}执行查询: $query${NC}"
    python3 main.py run "$query" --config trae_config.yaml --verbose
}

# 交互模式
run_interactive() {
    echo -e "${GREEN}启动交互模式...${NC}"
    python3 main.py interactive --config trae_config.yaml
}

# 查看数据库结构
show_schema() {
    local table="$1"
    if [ -n "$table" ]; then
        echo -e "${GREEN}查看表结构: $table${NC}"
        python3 main.py schema --table "$table" --config trae_config.yaml
    else
        echo -e "${GREEN}查看所有表结构...${NC}"
        python3 main.py schema --config trae_config.yaml
    fi
}

# 测试连接
test_connection() {
    echo -e "${GREEN}测试数据库连接...${NC}"
    python3 main.py test --config trae_config.yaml
}

# 主程序
main() {
    check_python
    
    case "${1:-help}" in
        "init")
            init_config "$2" "$3" "$4" "$5"
            ;;
        "run")
            run_query "$2"
            ;;
        "interactive")
            run_interactive
            ;;
        "schema")
            show_schema "$2"
            ;;
        "test")
            test_connection
            ;;
        "help"|*)
            usage
            ;;
    esac
}

# 执行主程序
main "$@"