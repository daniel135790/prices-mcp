#!/usr/bin/env python3
"""
Test singleton behavior of CacheManager
"""

from cache import CacheManager

def test_singleton():
    """Test that CacheManager behaves as a singleton"""
    print("Testing CacheManager singleton behavior...")
    
    # Create two instances with different configs
    config1 = {'type': 'memory', 'default_ttl': 1000, 'max_size': 500}
    config2 = {'type': 'memory', 'default_ttl': 2000, 'max_size': 1000}
    
    cache1 = CacheManager(config1)
    cache2 = CacheManager(config2)
    
    # They should be the same instance
    print(f"cache1 is cache2: {cache1 is cache2}")
    print(f"cache1 id: {id(cache1)}")
    print(f"cache2 id: {id(cache2)}")
    
    # Should use the first config (config1)
    print(f"cache1.default_ttl: {cache1.default_ttl}")
    print(f"cache2.default_ttl: {cache2.default_ttl}")
    print(f"cache1.max_size: {cache1.max_size}")
    print(f"cache2.max_size: {cache2.max_size}")
    
    # Test get_instance method
    cache3 = CacheManager.get_instance()
    print(f"cache1 is cache3: {cache1 is cache3}")
    
    print("✓ Singleton test passed!")
    return cache1 is cache2 and cache1 is cache3

def test_reset():
    """Test singleton reset functionality"""
    print("\nTesting singleton reset...")
    
    # Get initial instance
    cache1 = CacheManager({'default_ttl': 1000})
    print(f"Initial cache ttl: {cache1.default_ttl}")
    
    # Reset and create new instance with different config
    CacheManager.reset_instance()
    cache2 = CacheManager({'default_ttl': 5000})
    
    print(f"After reset cache ttl: {cache2.default_ttl}")
    print(f"cache1 is cache2: {cache1 is cache2}")
    
    print("✓ Reset test passed!")

if __name__ == "__main__":
    test_singleton()
    test_reset()
    print("\nAll tests passed! ✓")