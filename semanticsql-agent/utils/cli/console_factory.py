"""控制台工厂（参考 TRAEAgent）"""

from .cli_console import CLIConsole, ConsoleMode, ConsoleType
from .simple_console import SimpleConsole
from .rich_console import RichConsole


class ConsoleFactory:
    """创建不同类型控制台的工厂类"""
    
    @staticmethod
    def create_console(
        console_type: ConsoleType,
        mode: ConsoleMode = ConsoleMode.RUN
    ) -> CLIConsole:
        """创建控制台实例
        
        Args:
            console_type: 控制台类型
            mode: 操作模式
            
        Returns:
            CLIConsole 实例
        """
        if console_type == ConsoleType.SIMPLE:
            return SimpleConsole(mode=mode)
        elif console_type == ConsoleType.RICH:
            return RichConsole(mode=mode)
        else:
            # 默认使用简单控制台
            return SimpleConsole(mode=mode)
    
    @staticmethod
    def get_recommended_console_type(mode: ConsoleMode) -> ConsoleType:
        """获取推荐的控制台类型
        
        Args:
            mode: 操作模式
            
        Returns:
            推荐的控制台类型
        """
        # 交互模式推荐使用 Rich 控制台
        if mode == ConsoleMode.INTERACTIVE:
            try:
                # 检查是否安装了 rich
                import rich
                return ConsoleType.RICH
            except ImportError:
                return ConsoleType.SIMPLE
        else:
            # 运行模式使用简单控制台
            return ConsoleType.SIMPLE