#!/usr/bin/env python3
"""
Intelligent Cache Coherence System
Event-driven invalidation for 95%+ hit rate
Date: November 21, 2024
"""

import logging
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
import hashlib

logger = logging.getLogger(__name__)


class InvalidationStrategy(Enum):
    """Cache invalidation strategies"""
    EXACT = 'exact'        # Exact key match
    PREFIX = 'prefix'      # Prefix wildcard
    TAG = 'tag'           # Tag-based invalidation
    PATTERN = 'pattern'   # Regex pattern


class CacheLevel(Enum):
    """Cache hierarchy levels"""
    L1 = 'l1'  # In-memory (fastest, <1ms, limited)
    L2 = 'l2'  # Redis (medium, 5-10ms, larger)
    L3 = 'l3'  # Persistent (slow, 50-200ms, unlimited)


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: Any
    ttl_seconds: int
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0
    tags: Set[str] = field(default_factory=set)
    dependencies: Set[str] = field(default_factory=set)

    def is_expired(self) -> bool:
        """Check if entry has expired"""
        if self.ttl_seconds <= 0:
            return False

        age = (datetime.utcnow() - self.created_at).total_seconds()
        return age > self.ttl_seconds

    def touch(self):
        """Update last access time"""
        self.last_accessed = datetime.utcnow()
        self.access_count += 1

    def get_hash(self) -> str:
        """Get entry hash"""
        data = f"{self.key}:{self.created_at.isoformat()}"
        return hashlib.md5(data.encode()).hexdigest()


@dataclass
class CacheInvalidationEvent:
    """Cache invalidation event"""
    event_id: str
    timestamp: datetime
    strategy: InvalidationStrategy
    pattern: str  # Key pattern or tag
    source: str = 'system'  # Who triggered the invalidation
    cascade: bool = False  # Invalidate dependent entries


class L1Cache:
    """Level 1 in-memory cache (fastest)"""

    def __init__(self, max_entries: int = 1000):
        self.cache: Dict[str, CacheEntry] = {}
        self.max_entries = max_entries
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Get from L1 cache"""
        if key not in self.cache:
            self.misses += 1
            return None

        entry = self.cache[key]

        if entry.is_expired():
            del self.cache[key]
            self.misses += 1
            return None

        entry.touch()
        self.hits += 1
        return entry.value

    def set(self, key: str, value: Any, ttl_seconds: int = 3600,
            tags: Set[str] = None, dependencies: Set[str] = None):
        """Set in L1 cache"""
        if len(self.cache) >= self.max_entries:
            # Evict least recently used
            self._evict_lru()

        entry = CacheEntry(
            key=key,
            value=value,
            ttl_seconds=ttl_seconds,
            tags=tags or set(),
            dependencies=dependencies or set()
        )

        self.cache[key] = entry

    def invalidate_by_pattern(self, pattern: str, strategy: InvalidationStrategy):
        """Invalidate cache entries by pattern"""
        keys_to_delete = []

        for key in self.cache.keys():
            if strategy == InvalidationStrategy.EXACT:
                if key == pattern:
                    keys_to_delete.append(key)
            elif strategy == InvalidationStrategy.PREFIX:
                if key.startswith(pattern):
                    keys_to_delete.append(key)
            elif strategy == InvalidationStrategy.TAG:
                if pattern in self.cache[key].tags:
                    keys_to_delete.append(key)

        for key in keys_to_delete:
            del self.cache[key]

        return len(keys_to_delete)

    def _evict_lru(self):
        """Evict least recently used entry"""
        if not self.cache:
            return

        lru_key = min(self.cache.keys(),
                     key=lambda k: self.cache[k].last_accessed)
        del self.cache[lru_key]

    def get_stats(self) -> Dict:
        """Get cache statistics"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0

        return {
            'level': 'L1',
            'entries': len(self.cache),
            'max_entries': self.max_entries,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': f"{hit_rate:.2f}%",
            'memory_usage_percent': f"{(len(self.cache) / self.max_entries * 100):.1f}%"
        }


class L2Cache:
    """Level 2 Redis-like cache (larger capacity)"""

    def __init__(self, redis_client=None):
        self.redis = redis_client
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Get from L2 cache"""
        if self.redis is None:
            return None

        try:
            value = self.redis.get(key)
            if value:
                self.hits += 1
                return json.loads(value)
            else:
                self.misses += 1
                return None
        except Exception as e:
            logger.error(f"L2 cache get error: {e}")
            self.misses += 1
            return None

    def set(self, key: str, value: Any, ttl_seconds: int = 3600,
            tags: Set[str] = None, dependencies: Set[str] = None):
        """Set in L2 cache"""
        if self.redis is None:
            return

        try:
            self.redis.setex(key, ttl_seconds, json.dumps(value))

            # Store tags separately for invalidation
            if tags:
                tag_key = f"tags:{key}"
                self.redis.setex(tag_key, ttl_seconds, json.dumps(list(tags)))
        except Exception as e:
            logger.error(f"L2 cache set error: {e}")

    def invalidate_by_pattern(self, pattern: str, strategy: InvalidationStrategy) -> int:
        """Invalidate cache entries by pattern"""
        if self.redis is None:
            return 0

        try:
            if strategy == InvalidationStrategy.EXACT:
                self.redis.delete(pattern)
                return 1
            elif strategy == InvalidationStrategy.PREFIX:
                keys = self.redis.keys(f"{pattern}*")
                if keys:
                    self.redis.delete(*keys)
                    return len(keys)
            elif strategy == InvalidationStrategy.TAG:
                # Find all keys with this tag
                tag_keys = self.redis.keys(f"tags:*")
                keys_to_delete = []

                for tag_key in tag_keys:
                    tags = json.loads(self.redis.get(tag_key))
                    if pattern in tags:
                        # Extract original key from tag_key
                        original_key = tag_key.replace("tags:", "")
                        keys_to_delete.append(original_key)

                if keys_to_delete:
                    self.redis.delete(*keys_to_delete)

                return len(keys_to_delete)

            return 0
        except Exception as e:
            logger.error(f"L2 cache invalidation error: {e}")
            return 0

    def get_stats(self) -> Dict:
        """Get cache statistics"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0

        return {
            'level': 'L2',
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': f"{hit_rate:.2f}%"
        }


class IntelligentCacheCoherence:
    """Multi-level cache with intelligent coherence"""

    def __init__(self, redis_client=None):
        self.l1 = L1Cache(max_entries=1000)
        self.l2 = L2Cache(redis_client)
        self.invalidation_bus: List[CacheInvalidationEvent] = []
        self.total_hits = 0
        self.total_misses = 0

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache hierarchy"""
        # Try L1 first (fastest)
        value = self.l1.get(key)
        if value is not None:
            self.total_hits += 1
            return value

        # Try L2 (medium speed)
        value = self.l2.get(key)
        if value is not None:
            # Promote to L1 for future access
            self.l1.set(key, value, ttl_seconds=300)  # 5 min in L1
            self.total_hits += 1
            return value

        # Cache miss
        self.total_misses += 1
        return None

    async def set(self, key: str, value: Any, ttl_seconds: int = 3600,
                 tags: Set[str] = None, dependencies: Set[str] = None):
        """Set value in cache hierarchy"""
        tags = tags or set()
        dependencies = dependencies or set()

        # Set in both L1 and L2
        self.l1.set(key, value, ttl_seconds=min(ttl_seconds, 300),
                   tags=tags, dependencies=dependencies)
        self.l2.set(key, value, ttl_seconds=ttl_seconds,
                   tags=tags, dependencies=dependencies)

    async def invalidate(self, pattern: str, strategy: InvalidationStrategy,
                        source: str = 'system', cascade: bool = False):
        """Invalidate cache entries"""
        event = CacheInvalidationEvent(
            event_id=f"inv_{datetime.utcnow().timestamp()}",
            timestamp=datetime.utcnow(),
            strategy=strategy,
            pattern=pattern,
            source=source,
            cascade=cascade
        )

        self.invalidation_bus.append(event)

        # Invalidate in both levels
        l1_count = self.l1.invalidate_by_pattern(pattern, strategy)
        l2_count = self.l2.invalidate_by_pattern(pattern, strategy)

        logger.info(
            f"Cache invalidation: strategy={strategy.value}, pattern={pattern}, "
            f"L1 removed={l1_count}, L2 removed={l2_count}"
        )

        if cascade:
            await self._invalidate_dependencies(pattern)

    async def _invalidate_dependencies(self, pattern: str):
        """Invalidate dependent entries (cascade)"""
        # Find all entries that depend on this pattern
        dependent_keys = set()

        for key, entry in self.l1.cache.items():
            if pattern in entry.dependencies:
                dependent_keys.add(key)

        # Invalidate dependents
        for dep_key in dependent_keys:
            await self.invalidate(dep_key, InvalidationStrategy.EXACT,
                                 source='cascade')

    def get_coherence_stats(self) -> Dict:
        """Get cache coherence statistics"""
        total = self.total_hits + self.total_misses
        hit_rate = (self.total_hits / total * 100) if total > 0 else 0

        return {
            'timestamp': datetime.utcnow().isoformat(),
            'overall_hit_rate': f"{hit_rate:.2f}%",
            'total_hits': self.total_hits,
            'total_misses': self.total_misses,
            'l1_stats': self.l1.get_stats(),
            'l2_stats': self.l2.get_stats(),
            'invalidation_events': len(self.invalidation_bus),
            'target_hit_rate': '95%+'
        }

    def get_invalidation_report(self, hours: int = 24) -> Dict:
        """Get cache invalidation report"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent_events = [e for e in self.invalidation_bus if e.timestamp >= cutoff]

        by_strategy = {}
        by_source = {}

        for event in recent_events:
            strategy = event.strategy.value
            source = event.source

            if strategy not in by_strategy:
                by_strategy[strategy] = 0
            if source not in by_source:
                by_source[source] = 0

            by_strategy[strategy] += 1
            by_source[source] += 1

        return {
            'period_hours': hours,
            'total_invalidations': len(recent_events),
            'by_strategy': by_strategy,
            'by_source': by_source,
            'cascade_invalidations': sum(1 for e in recent_events if e.cascade)
        }


class PrefetchingStrategy:
    """Predictive cache prefetching"""

    def __init__(self, cache: IntelligentCacheCoherence):
        self.cache = cache
        self.access_patterns: Dict[str, List[str]] = {}
        self.min_pattern_count = 3

    async def record_access(self, key: str, related_keys: List[str]):
        """Record access pattern"""
        if key not in self.access_patterns:
            self.access_patterns[key] = []

        self.access_patterns[key].extend(related_keys)

    async def prefetch(self, key: str, fetch_function: Callable):
        """Prefetch related keys based on patterns"""
        if key not in self.access_patterns:
            return

        related_keys = self.access_patterns[key]

        # Count occurrences
        key_counts = {}
        for k in related_keys:
            key_counts[k] = key_counts.get(k, 0) + 1

        # Prefetch frequently accessed related keys
        for related_key, count in key_counts.items():
            if count >= self.min_pattern_count:
                try:
                    value = await fetch_function(related_key)
                    if value:
                        await self.cache.set(related_key, value)
                except Exception as e:
                    logger.warning(f"Prefetch failed for {related_key}: {e}")

    def get_pattern_report(self) -> Dict:
        """Get access pattern report"""
        return {
            'known_patterns': len(self.access_patterns),
            'total_pattern_entries': sum(len(v) for v in self.access_patterns.values()),
            'average_pattern_length': (
                sum(len(v) for v in self.access_patterns.values()) /
                max(1, len(self.access_patterns))
            )
        }


# Example usage
if __name__ == '__main__':
    import asyncio

    logging.basicConfig(level=logging.INFO)

    async def main():
        # Create cache system
        cache = IntelligentCacheCoherence(redis_client=None)  # Without Redis

        # Set some values
        await cache.set('user:123', {'id': 123, 'name': 'Alice'},
                       ttl_seconds=3600,
                       tags={'users', 'production'})

        await cache.set('user:124', {'id': 124, 'name': 'Bob'},
                       ttl_seconds=3600,
                       tags={'users', 'production'})

        # Get values
        user_123 = await cache.get('user:123')
        print(f"User 123: {user_123}")

        # Invalidate by tag
        await cache.invalidate('users', InvalidationStrategy.TAG, source='admin')

        # Check hit rate
        print("\n=== Cache Statistics ===")
        print(json.dumps(cache.get_coherence_stats(), indent=2))

        # Check invalidation report
        print("\n=== Invalidation Report ===")
        print(json.dumps(cache.get_invalidation_report(), indent=2))

    asyncio.run(main())
