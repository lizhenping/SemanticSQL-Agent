"""NL2SQL Pipeline 主入口

兼容que_gen_ddd的命令行接口
"""

import sys
from pathlib import Path

# 确保项目根目录在sys.path中
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from .application import NL2SQLApplication


def main():
    """主函数入口"""
    app = NL2SQLApplication()
    app.initialize()
    exit_code = app.run(sys.argv[1:])
    sys.exit(exit_code)


if __name__ == '__main__':
    main()