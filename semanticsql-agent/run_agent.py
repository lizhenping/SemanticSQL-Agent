#!/usr/bin/env python3
"""SemanticSQL Agent V2 入口脚本"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cli_v2 import cli

if __name__ == "__main__":
    cli()