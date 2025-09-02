"""配置服务

负责加载和管理YAML格式的配置文件。
提供统一的配置访问接口，支持：
- 多配置文件加载（app、scenarios、complexity等）
- 点号分隔的嵌套配置访问
- 配置缓存和热重载
- 默认值处理

主要功能：
- 自动加载配置目录下的所有YAML文件
- 提供便捷的配置获取方法
- 支持运行时更新配置（仅内存）
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ConfigService:
    """配置管理服务
    
    提供集中式的配置管理功能，所有配置文件在初始化时自动加载。
    
    属性:
        config_dir: 配置文件目录路径
        _cache: 配置缓存字典
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        """初始化配置服务
        
        参数:
            config_dir: 配置目录路径，如果不提供则使用默认路径
        """
        if config_dir is None:
            # 默认配置目录在项目根目录的config文件夹
            config_dir = Path(__file__).parent.parent.parent.parent / "config"
        
        self.config_dir = Path(config_dir)
        self._cache = {}
        
        # 初始化时加载所有配置
        self._load_all_configs()
    
    def _load_all_configs(self):
        """加载所有配置文件
        
        自动扫描并加载预定义的配置文件。
        如果某个文件不存在或加载失败，会记录警告但不会中断程序。
        """
        # 预定义的配置文件映射
        config_files = {
            'app': 'app.yaml',          # 应用配置
            'scenarios': 'scenarios.yaml',  # 场景定义
            'complexity': 'complexity.yaml', # 复杂度定义
            'logging': 'logging.yaml'    # 日志配置
        }
        
        for key, filename in config_files.items():
            try:
                self._cache[key] = self._load_yaml(filename)
                logger.info(f"成功加载配置: {key} (来自 {filename})")
            except Exception as e:
                logger.warning(f"加载配置文件 {filename} 失败: {e}")
                # 使用空字典作为默认值，避免后续访问出错
                self._cache[key] = {}
    
    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        """加载单个YAML文件
        
        参数:
            filename: YAML文件名
            
        返回:
            解析后的配置字典
            
        异常:
            FileNotFoundError: 文件不存在
            yaml.YAMLError: YAML格式错误
        """
        filepath = self.config_dir / filename
        
        if not filepath.exists():
            logger.warning(f"配置文件不存在: {filepath}")
            return {}
        
        with open(filepath, 'r', encoding='utf-8') as f:
            # safe_load避免执行任意Python代码
            return yaml.safe_load(f) or {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值
        
        支持使用点号访问嵌套配置，例如：
        - 'app.database.host' 获取应用配置中的数据库主机
        - 'scenarios.project_execution.weight' 获取特定场景的权重
        
        参数:
            key: 配置键，支持点号分隔的路径
            default: 找不到配置时的默认值
            
        返回:
            配置值，如果不存在则返回默认值
        """
        # 使用点号分割键路径
        keys = key.split('.')
        
        # 从缓存开始遍历
        value = self._cache
        
        # 逐层深入获取值
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_app_config(self) -> Dict[str, Any]:
        """获取应用配置
        
        返回:
            完整的应用配置字典
        """
        return self._cache.get('app', {})
    
    def get_scenarios(self) -> Dict[str, Any]:
        """获取场景配置
        
        返回:
            所有场景的配置字典
        """
        return self._cache.get('scenarios', {})
    
    def get_complexity_levels(self) -> Dict[str, Any]:
        """获取复杂度级别配置
        
        返回:
            所有复杂度级别的配置字典
        """
        return self._cache.get('complexity', {})
    
    def get_database_config(self, profile: str = 'default') -> Dict[str, Any]:
        """获取数据库配置
        
        支持多个数据库配置文件（profile），方便在不同环境间切换。
        
        参数:
            profile: 配置文件名，默认为'default'
            
        返回:
            数据库连接配置字典
            
        异常:
            ValueError: 指定的profile不存在
        """
        db_configs = self.get('app.database', {})
        
        if profile in db_configs:
            return db_configs[profile]
        elif 'default' in db_configs:
            logger.warning(f"数据库配置 '{profile}' 不存在，使用默认配置")
            return db_configs['default']
        else:
            raise ValueError(f"找不到数据库配置: '{profile}'")
    
    def get_llm_config(self) -> Dict[str, Any]:
        """获取LLM配置
        
        返回:
            LLM服务配置，包含模型名称、温度等参数
            如果配置不存在，返回默认值
        """
        return self.get('app.llm', {
            'model': 'gpt-3.5-turbo',
            'temperature': 0.7,
            'max_tokens': 4096
        })
    
    def reload(self):
        """重新加载所有配置
        
        用于配置文件更新后的热重载。
        注意：这会清空所有缓存，包括运行时的更新。
        """
        self._cache.clear()
        self._load_all_configs()
        logger.info("配置已重新加载")
    
    def update(self, key: str, value: Any):
        """更新配置值（仅在内存中）
        
        这个方法只更新内存中的配置，不会写回文件。
        适用于运行时的临时配置调整。
        
        参数:
            key: 配置键，支持点号分隔的路径
            value: 新的配置值
        """
        keys = key.split('.')
        
        # 导航到父节点
        current = self._cache
        for k in keys[:-1]:
            # 如果中间节点不存在，创建空字典
            if k not in current:
                current[k] = {}
            current = current[k]
        
        # 设置值
        current[keys[-1]] = value
        
        logger.debug(f"更新配置: {key} = {value}")