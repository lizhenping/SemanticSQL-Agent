"""
trae_agent风格的SemanticSQL Agent主入口 - 同步版本
"""

import sys
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from cli.cli import cli

if __name__ == "__main__":
    cli()