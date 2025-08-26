"""文件操作工具模块

提供常用的文件操作功能
"""

import os
import shutil
from pathlib import Path
from typing import Union, Optional


def ensure_directory_exists(path: Union[str, Path], is_file_path: bool = False) -> Path:
    """确保目录存在，如果不存在则创建
    
    Args:
        path: 目录路径或文件路径
        is_file_path: 如果为True，则path被视为文件路径，将创建其父目录
        
    Returns:
        目录的Path对象
    """
    path = Path(path)
    
    if is_file_path:
        directory = path.parent
    else:
        directory = path
    
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)
    
    return directory


def copy_file_safely(source: Union[str, Path], destination: Union[str, Path]) -> Path:
    """安全地复制文件，确保目标目录存在
    
    Args:
        source: 源文件路径
        destination: 目标文件路径
        
    Returns:
        目标文件的Path对象
        
    Raises:
        FileNotFoundError: 如果源文件不存在
    """
    source = Path(source)
    destination = Path(destination)
    
    if not source.exists():
        raise FileNotFoundError(f"源文件不存在: {source}")
    
    # 确保目标目录存在
    ensure_directory_exists(destination, is_file_path=True)
    
    # 复制文件
    shutil.copy2(source, destination)
    
    return destination


def get_output_directory(output_path: Optional[str], default_dir: str = 'output') -> str:
    """获取输出目录路径
    
    Args:
        output_path: 输出文件路径
        default_dir: 默认目录名
        
    Returns:
        输出目录路径
    """
    if output_path:
        output_dir = os.path.dirname(output_path)
        if not output_dir:  # 如果没有目录路径，使用当前目录
            output_dir = '.'
    else:
        output_dir = default_dir
    
    return output_dir