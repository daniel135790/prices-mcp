import hashlib
import json
import time
from typing import Any, Dict, Optional
from dataclasses import asdict, dataclass
import logging
import pickle
import sqlite3
from pathlib import Path

# MCP imports

# Caching imports
try:
    from diskcache import Cache
    HAS_DISKCACHE = True
except ImportError:
    Cache = None
    HAS_DISKCACHE = False

# Our supermarket scraper

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    data: Any
    timestamp: float
    ttl: float
    key: str
    size: int = 0
    
    def is_expired(self) -> bool:
        return time.time() > (self.timestamp + self.ttl)
    
    def to_dict(self) -> Dict:
        return asdict(self)


class CacheManager:
    """Multi-tier caching system - Singleton"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls, config: Dict[str, Any] = None):
        if cls._instance is None:
            cls._instance = super(CacheManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, config: Dict[str, Any] = None):
        # Only initialize once
        if self._initialized:
            return
            
        if config is None:
            config = {'type': 'memory', 'default_ttl': 3600}
            
        self.config = config
        self.cache_type = config.get('type', 'memory')
        self.default_ttl = config.get('default_ttl', 3600)  # 1 hour
        
        # Initialize cache backend
        if self.cache_type == 'disk':
            self._init_disk_cache()
        elif self.cache_type == 'sqlite':
            self._init_sqlite_cache()
        else:  # memory
            self._init_memory_cache()
            
        self._initialized = True
    
    @classmethod
    def get_instance(cls, config: Dict[str, Any] = None) -> 'CacheManager':
        """Get the singleton instance"""
        return cls(config)
    
    @classmethod
    def reset_instance(cls):
        """Reset the singleton instance (useful for testing)"""
        cls._instance = None
        cls._initialized = False
    
    def _init_memory_cache(self):
        """Initialize in-memory cache with LRU eviction"""
        self.cache = {}
        self.access_order = {}
        self.max_size = self.config.get('max_size', 1000)
        logger.info("Initialized memory cache")
    
    def _init_disk_cache(self):
        """Initialize disk-based cache"""
        if not HAS_DISKCACHE:
            logger.warning("diskcache not available, falling back to memory cache")
            self._init_memory_cache()
            return
        cache_dir = self.config.get('cache_dir', './cache')
        Path(cache_dir).mkdir(exist_ok=True)
        self.cache = Cache(cache_dir, size_limit=self.config.get('size_limit', 1024**3))  # 1GB
        logger.info(f"Initialized disk cache at {cache_dir}")
    
    def _init_sqlite_cache(self):
        """Initialize SQLite cache"""
        db_path = self.config.get('db_path', './cache.db')
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                data BLOB,
                timestamp REAL,
                ttl REAL,
                size INTEGER
            )
        ''')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON cache(timestamp)')
        self.conn.commit()
        logger.info(f"Initialized SQLite cache at {db_path}")
    
    def _generate_key(self, namespace: str, identifier: str, params: Dict = None) -> str:
        """Generate cache key"""
        key_data = f"{namespace}:{identifier}"
        if params:
            param_str = json.dumps(params, sort_keys=True)
            key_data += f":{hashlib.md5(param_str.encode()).hexdigest()}"
        return key_data
    
    async def get(self, namespace: str, identifier: str, params: Dict = None) -> Optional[Any]:
        """Get item from cache"""
        key = self._generate_key(namespace, identifier, params)
        
        try:
            if self.cache_type == 'memory':
                return await self._get_memory(key)
            elif self.cache_type == 'disk':
                return await self._get_disk(key)
            elif self.cache_type == 'sqlite':
                return await self._get_sqlite(key)
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
    
    async def set(self, namespace: str, identifier: str, data: Any, 
                 ttl: Optional[float] = None, params: Dict = None) -> bool:
        """Set item in cache"""
        key = self._generate_key(namespace, identifier, params)
        ttl = ttl or self.default_ttl
        
        try:
            if self.cache_type == 'memory':
                return await self._set_memory(key, data, ttl)
            elif self.cache_type == 'disk':
                return await self._set_disk(key, data, ttl)
            elif self.cache_type == 'sqlite':
                return await self._set_sqlite(key, data, ttl)
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    async def _get_memory(self, key: str) -> Optional[Any]:
        if key not in self.cache:
            return None
        
        entry = self.cache[key]
        if entry.is_expired():
            del self.cache[key]
            if key in self.access_order:
                del self.access_order[key]
            return None
        
        # Update access order for LRU
        self.access_order[key] = time.time()
        return entry.data
    
    async def _set_memory(self, key: str, data: Any, ttl: float) -> bool:
        # Evict if at capacity
        if len(self.cache) >= self.max_size:
            await self._evict_lru()
        
        entry = CacheEntry(
            data=data,
            timestamp=time.time(),
            ttl=ttl,
            key=key,
            size=len(str(data))
        )
        
        self.cache[key] = entry
        self.access_order[key] = time.time()
        return True
    
    async def _evict_lru(self):
        """Evict least recently used items"""
        if not self.access_order:
            return
        
        # Remove oldest 10% of items
        sorted_items = sorted(self.access_order.items(), key=lambda x: x[1])
        items_to_remove = max(1, len(sorted_items) // 10)
        
        for key, _ in sorted_items[:items_to_remove]:
            if key in self.cache:
                del self.cache[key]
            del self.access_order[key]
    
    async def _get_disk(self, key: str) -> Optional[Any]:
        try:
            entry_dict = self.cache.get(key)
            if entry_dict is None:
                return None
            
            entry = CacheEntry(**entry_dict)
            if entry.is_expired():
                del self.cache[key]
                return None
            
            return entry.data
        except Exception:
            return None
    
    async def _set_disk(self, key: str, data: Any, ttl: float) -> bool:
        try:
            entry = CacheEntry(
                data=data,
                timestamp=time.time(),
                ttl=ttl,
                key=key
            )
            
            self.cache.set(key, entry.to_dict(), expire=ttl)
            return True
        except Exception as e:
            logger.error(f"Disk cache error: {e}")
            return False
    
    async def _get_sqlite(self, key: str) -> Optional[Any]:
        try:
            cursor = self.conn.execute(
                'SELECT data, timestamp, ttl FROM cache WHERE key = ?',
                (key,)
            )
            row = cursor.fetchone()
            
            if row is None:
                return None
            
            data_blob, timestamp, ttl = row
            
            # Check expiration
            if time.time() > (timestamp + ttl):
                self.conn.execute('DELETE FROM cache WHERE key = ?', (key,))
                self.conn.commit()
                return None
            
            return pickle.loads(data_blob)
        except Exception as e:
            logger.error(f"SQLite get error: {e}")
            return None
    
    async def _set_sqlite(self, key: str, data: Any, ttl: float) -> bool:
        try:
            data_blob = pickle.dumps(data)
            timestamp = time.time()
            size = len(data_blob)
            
            self.conn.execute('''
                INSERT OR REPLACE INTO cache (key, data, timestamp, ttl, size)
                VALUES (?, ?, ?, ?, ?)
            ''', (key, data_blob, timestamp, ttl, size))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"SQLite set error: {e}")
            return False
    
    async def invalidate(self, namespace: str, identifier: str = None, params: Dict = None):
        """Invalidate cache entries"""
        if identifier:
            key = self._generate_key(namespace, identifier, params)
            await self._delete_key(key)
        else:
            # Invalidate all keys in namespace
            await self._delete_namespace(namespace)
    
    async def _delete_key(self, key: str):
        """Delete specific key"""
        try:
            if self.cache_type == 'memory':
                if key in self.cache:
                    del self.cache[key]
                if key in self.access_order:
                    del self.access_order[key]
            elif self.cache_type == 'disk':
                if key in self.cache:
                    del self.cache[key]
            elif self.cache_type == 'sqlite':
                self.conn.execute('DELETE FROM cache WHERE key = ?', (key,))
                self.conn.commit()
        except Exception as e:
            logger.error(f"Delete key error: {e}")
    
    async def _delete_namespace(self, namespace: str):
        """Delete all keys in namespace"""
        try:
            if self.cache_type == 'memory':
                keys_to_delete = [k for k in self.cache.keys() if k.startswith(f"{namespace}:")]
                for key in keys_to_delete:
                    del self.cache[key]
                    if key in self.access_order:
                        del self.access_order[key]
            elif self.cache_type == 'disk':
                # DiskCache doesn't have pattern delete, iterate
                keys_to_delete = [k for k in self.cache if k.startswith(f"{namespace}:")]
                for key in keys_to_delete:
                    del self.cache[key]
            elif self.cache_type == 'sqlite':
                self.conn.execute('DELETE FROM cache WHERE key LIKE ?', (f"{namespace}:%",))
                self.conn.commit()
        except Exception as e:
            logger.error(f"Delete namespace error: {e}")
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = {
            'type': self.cache_type,
            'default_ttl': self.default_ttl
        }
        
        try:
            if self.cache_type == 'memory':
                stats.update({
                    'size': len(self.cache),
                    'max_size': self.max_size,
                    'hit_ratio': 'not_tracked'
                })
            elif self.cache_type == 'disk':
                stats.update({
                    'size': len(self.cache),
                    'volume': self.cache.volume()
                })
            elif self.cache_type == 'sqlite':
                cursor = self.conn.execute('SELECT COUNT(*), SUM(size) FROM cache')
                count, total_size = cursor.fetchone()
                stats.update({
                    'size': count or 0,
                    'total_size': total_size or 0
                })
        except Exception as e:
            stats['error'] = str(e)
        
        return stats

