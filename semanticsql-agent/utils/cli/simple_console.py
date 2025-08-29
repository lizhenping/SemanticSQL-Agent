"""简单控制台实现"""

import sys
from typing import Optional
from .cli_console import CLIConsole, ConsoleMode


class SimpleConsole(CLIConsole):
    """简单的文本控制台"""
    
    STATUS_SYMBOLS = {
        'thinking': '🤔',
        'executing': '⚙️',
        'completed': '✅',
        'error': '❌'
    }
    
    STYLE_COLORS = {
        'error': '\033[91m',  # 红色
        'success': '\033[92m',  # 绿色
        'warning': '\033[93m',  # 黄色
        'info': '\033[94m',  # 蓝色
        'reset': '\033[0m'  # 重置
    }
    
    def start(self):
        """启动控制台"""
        if self.mode == ConsoleMode.INTERACTIVE:
            self.print("SemanticSQL Agent - 交互模式", style="info")
            self.print("输入 'exit' 或 'quit' 退出\n")
    
    def print(self, message: str, style: Optional[str] = None):
        """打印消息"""
        if style and style in self.STYLE_COLORS:
            print(f"{self.STYLE_COLORS[style]}{message}{self.STYLE_COLORS['reset']}")
        else:
            print(message)
    
    def print_table(self, data: list, headers: list):
        """打印简单表格"""
        if not data:
            self.print("没有数据", style="warning")
            return
        
        # 计算列宽
        col_widths = []
        for i, header in enumerate(headers):
            max_width = len(str(header))
            for row in data:
                if i < len(row):
                    max_width = max(max_width, len(str(row[i])))
            col_widths.append(max_width + 2)
        
        # 打印表头
        header_line = "|"
        for i, header in enumerate(headers):
            header_line += f" {str(header):<{col_widths[i]-1}}|"
        print(header_line)
        
        # 打印分隔线
        sep_line = "|"
        for width in col_widths:
            sep_line += "-" * width + "|"
        print(sep_line)
        
        # 打印数据
        for row in data[:10]:  # 限制显示10行
            row_line = "|"
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    row_line += f" {str(cell):<{col_widths[i]-1}}|"
            print(row_line)
        
        if len(data) > 10:
            self.print(f"\n... 还有 {len(data) - 10} 行数据", style="info")
    
    def get_user_input(self, prompt: str = "> ") -> Optional[str]:
        """获取用户输入"""
        try:
            user_input = input(prompt).strip()
            if user_input.lower() in ['exit', 'quit']:
                return None
            return user_input
        except (KeyboardInterrupt, EOFError):
            print("\n")
            return None
    
    def clear(self):
        """清屏"""
        # 简单实现：打印空行
        print("\n" * 3)
    
    def print_status(self, status: str, message: str):
        """打印状态消息"""
        symbol = self.STATUS_SYMBOLS.get(status, '▶')
        
        if status == 'error':
            style = 'error'
        elif status == 'completed':
            style = 'success'
        elif status == 'thinking':
            style = 'info'
        else:
            style = None
        
        self.print(f"{symbol} {message}", style=style)