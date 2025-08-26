"""CLI interface for NL2SQL Pipeline"""

from .argument_parser import ArgumentParser
# command_registry 在应用程序初始化时导入，以避免循环依赖
from .commands import Command, CommandResult

__all__ = [
    "ArgumentParser",
    "Command",
    "CommandResult"
]