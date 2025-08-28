"""
Schema缓存管理
"""

import json
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path

from .connection_manager import DatabaseManager


class SchemaCache:
    """Schema缓存管理器"""
    
    def __init__(self, cache_dir: str = "cache", ttl: int = 3600):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.ttl = ttl  # 缓存过期时间（秒）
        self._cache: Dict[str, Dict[str, Any]] = {}
    
    def _get_cache_key(self, database: str, table: str = None) -> str:
        """生成缓存键"""
        if table:
            return f"{database}_{table}"
        return database
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{cache_key}_schema.json"
    
    def is_valid(self, cache_key: str) -> bool:
        """检查缓存是否有效"""
        if cache_key not in self._cache:
            return False
        
        cache_data = self._cache[cache_key]
        timestamp = cache_data.get("timestamp")
        if not timestamp:
            return False
        
        cache_time = datetime.fromisoformat(timestamp)
        return datetime.now() - cache_time < timedelta(seconds=self.ttl)
    
    def get(self, database: str, table: str = None) -> Optional[Dict[str, Any]]:
        """获取缓存的Schema信息"""
        cache_key = self._get_cache_key(database, table)
        
        # 检查内存缓存
        if self.is_valid(cache_key):
            return self._cache[cache_key].get("data")
        
        # 检查文件缓存
        cache_path = self._get_cache_path(cache_key)
        if cache_path.exists():
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    
                # 检查文件缓存是否有效
                timestamp = cache_data.get("timestamp")
                if timestamp:
                    cache_time = datetime.fromisoformat(timestamp)
                    if datetime.now() - cache_time < timedelta(seconds=self.ttl):
                        self._cache[cache_key] = cache_data
                        return cache_data.get("data")
                    else:
                        # 删除过期缓存
                        cache_path.unlink()
                        
            except Exception as e:
                print(f"读取缓存文件失败: {e}")
        
        return None
    
    def set(self, database: str, data: Dict[str, Any], table: str = None) -> None:
        """设置Schema缓存"""
        cache_key = self._get_cache_key(database, table)
        
        cache_data = {
            "timestamp": datetime.now().isoformat(),
            "data": data,
            "database": database,
            "table": table
        }
        
        # 设置内存缓存
        self._cache[cache_key] = cache_data
        
        # 设置文件缓存
        cache_path = self._get_cache_path(cache_key)
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"写入缓存文件失败: {e}")
    
    def invalidate(self, database: str, table: str = None) -> None:
        """使缓存失效"""
        cache_key = self._get_cache_key(database, table)
        
        # 清除内存缓存
        if cache_key in self._cache:
            del self._cache[cache_key]
        
        # 清除文件缓存
        cache_path = self._get_cache_path(cache_key)
        if cache_path.exists():
            try:
                cache_path.unlink()
            except Exception as e:
                print(f"删除缓存文件失败: {e}")
    
    def invalidate_all(self) -> None:
        """清除所有缓存"""
        self._cache.clear()
        
        # 清除所有缓存文件
        for cache_file in self.cache_dir.glob("*_schema.json"):
            try:
                cache_file.unlink()
            except Exception as e:
                print(f"删除缓存文件失败: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        valid_entries = 0
        expired_entries = 0
        
        for cache_key, cache_data in self._cache.items():
            if self.is_valid(cache_key):
                valid_entries += 1
            else:
                expired_entries += 1
        
        # 检查文件缓存
        file_entries = 0
        for cache_file in self.cache_dir.glob("*_schema.json"):
            file_entries += 1
        
        return {
            "memory_entries": len(self._cache),
            "valid_entries": valid_entries,
            "expired_entries": expired_entries,
            "file_entries": file_entries,
            "cache_dir": str(self.cache_dir)
        }


class AsyncSchemaCache(SchemaCache):
    """异步Schema缓存"""
    
    def __init__(self, database_manager: DatabaseManager, cache_dir: str = "cache", ttl: int = 3600):
        super().__init__(cache_dir, ttl)
        self.db_manager = database_manager
    
    async def refresh_schema(self, database: str, table: str = None) -> Dict[str, Any]:
        """刷新Schema缓存"""
        try:
            if table:
                # 刷新单个表
                table_info = await self.db_manager.get_table_info(table)
                self.set(database, table_info, table)
                return table_info
            else:
                # 刷新所有表
                tables = await self.db_manager.get_tables()
                schema_info = {"tables": {}}
                
                for table_name in tables:
                    table_info = await self.db_manager.get_table_info(table_name)
                    schema_info["tables"][table_name] = table_info
                
                self.set(database, schema_info)
                return schema_info
                
        except Exception as e:
            print(f"刷新Schema缓存失败: {e}")
            return {}
    
    async def get_schema_with_refresh(self, database: str, table: str = None, force_refresh: bool = False) -> Dict[str, Any]:
        """获取Schema，必要时刷新"""
        # 检查缓存
        cached_schema = self.get(database, table)
        if cached_schema and not force_refresh:
            return cached_schema
        
        # 刷新缓存
        return await self.refresh_schema(database, table)
    
    async def get_table_relationships(self, database: str) -> Dict[str, Any]:
        """获取表关系信息"""
        cache_key = f"{database}_relationships"
        
        # 检查缓存
        cached = self.get(database, cache_key)
        if cached:
            return cached
        
        try:
            # 获取所有表
            tables = await self.db_manager.get_tables()
            relationships = {
                "tables": tables,
                "relationships": []
            }
            
            # 分析表之间的关系（简化版）
            for table in tables:
                table_info = await self.db_manager.get_table_info(table)
                for column in table_info.get("columns", []):
                    column_name = column.get("name", "").lower()
                    if column_name.endswith("_id") or column_name.endswith("id"):
                        # 可能是外键
                        referenced_table = column_name.replace("_id", "").replace("id", "")
                        if referenced_table in tables and referenced_table != table:
                            relationships["relationships"].append({
                                "from_table": table,
                                "from_column": column_name,
                                "to_table": referenced_table,
                                "to_column": "id",
                                "type": "potential_foreign_key"
                            })
            
            self.set(database, relationships, cache_key)
            return relationships
            
        except Exception as e:
            print(f"获取表关系信息失败: {e}")
            return {"tables": [], "relationships": []}