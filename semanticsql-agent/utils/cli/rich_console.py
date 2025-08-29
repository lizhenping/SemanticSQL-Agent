"""Rich 控制台实现"""

from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from .cli_console import CLIConsole, ConsoleMode


class RichConsole(CLIConsole):
    """使用 Rich 库的增强控制台"""
    
    def __init__(self, mode: ConsoleMode = ConsoleMode.RUN):
        super().__init__(mode)
        self.console = Console()
        self.progress = None
    
    def start(self):
        """启动控制台"""
        if self.mode == ConsoleMode.INTERACTIVE:
            self.console.print(
                Panel.fit(
                    "[bold cyan]SemanticSQL Agent[/bold cyan]\n"
                    "[dim]交互模式 - 输入 'exit' 或 'quit' 退出[/dim]",
                    border_style="cyan"
                )
            )
    
    def print(self, message: str, style: Optional[str] = None):
        """打印消息"""
        if style == 'error':
            self.console.print(f"[red]{message}[/red]")
        elif style == 'success':
            self.console.print(f"[green]{message}[/green]")
        elif style == 'warning':
            self.console.print(f"[yellow]{message}[/yellow]")
        elif style == 'info':
            self.console.print(f"[blue]{message}[/blue]")
        else:
            self.console.print(message)
    
    def print_table(self, data: list, headers: list):
        """打印 Rich 表格"""
        if not data:
            self.console.print("[yellow]没有数据[/yellow]")
            return
        
        table = Table(show_header=True, header_style="bold magenta")
        
        # 添加列
        for header in headers:
            table.add_column(header)
        
        # 添加行（限制10行）
        for row in data[:10]:
            table.add_row(*[str(cell) for cell in row])
        
        self.console.print(table)
        
        if len(data) > 10:
            self.console.print(f"\n[dim]... 还有 {len(data) - 10} 行数据[/dim]")
    
    def get_user_input(self, prompt: str = "> ") -> Optional[str]:
        """获取用户输入"""
        try:
            user_input = Prompt.ask(prompt)
            if user_input.lower() in ['exit', 'quit']:
                return None
            return user_input
        except (KeyboardInterrupt, EOFError):
            self.console.print("\n")
            return None
    
    def clear(self):
        """清屏"""
        self.console.clear()
    
    def print_status(self, status: str, message: str):
        """打印状态消息"""
        status_styles = {
            'thinking': ('[blue]🤔[/blue]', 'blue'),
            'executing': ('[yellow]⚙️[/yellow]', 'yellow'),
            'completed': ('[green]✅[/green]', 'green'),
            'error': ('[red]❌[/red]', 'red')
        }
        
        symbol, color = status_styles.get(status, ('▶', 'white'))
        self.console.print(f"{symbol} [{color}]{message}[/{color}]")
    
    def show_progress(self, description: str):
        """显示进度条"""
        if not self.progress:
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            )
            self.progress.start()
        
        return self.progress.add_task(description, total=None)
    
    def hide_progress(self):
        """隐藏进度条"""
        if self.progress:
            self.progress.stop()
            self.progress = None