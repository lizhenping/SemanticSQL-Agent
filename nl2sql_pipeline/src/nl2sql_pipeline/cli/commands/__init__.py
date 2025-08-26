"""Command handlers for NL2SQL Pipeline CLI"""

from .base import Command, CommandResult

# 具体的命令类在command_registry中延迟导入，以避免循环依赖
__all__ = [
    "Command",
    "CommandResult"
]