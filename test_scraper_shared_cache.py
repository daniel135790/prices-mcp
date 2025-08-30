#!/usr/bin/env python3
"""
Test that multiple Scraper instances share the same cache
"""

import asyncio
from scraper import Scraper
from cache import CacheManager

async def test_shared_cache():
    """Test that multiple scraper instances share the same cache"""
    print("Testing shared cache between multiple Scraper instances...")
    
    # Reset cache to start fresh
    CacheManager.reset_instance()
    
    # Create multiple scraper instances
    scraper1 = Scraper()
    scraper2 = Scraper()
    scraper3 = Scraper()
    
    # Check that they all have the same cache instance
    print(f"scraper1.cache is scraper2.cache: {scraper1.cache is scraper2.cache}")
    print(f"scraper2.cache is scraper3.cache: {scraper2.cache is scraper3.cache}")
    print(f"scraper1.cache id: {id(scraper1.cache)}")
    print(f"scraper2.cache id: {id(scraper2.cache)}")
    print(f"scraper3.cache id: {id(scraper3.cache)}")
    
    # Test that data set by one scraper can be read by another
    test_data = {"product": "test_product", "price": 10.99}
    
    # Set data using scraper1's cache
    await scraper1.cache.set("test", "shared_data", test_data)
    
    # Try to get data using scraper2's cache
    retrieved_data = await scraper2.cache.get("test", "shared_data")
    
    print(f"Data set by scraper1: {test_data}")
    print(f"Data retrieved by scraper2: {retrieved_data}")
    print(f"Data matches: {test_data == retrieved_data}")
    
    # Check cache stats from different scrapers
    stats1 = await scraper1.cache.get_stats()
    stats2 = await scraper2.cache.get_stats()
    
    print(f"Stats from scraper1: size={stats1['size']}")
    print(f"Stats from scraper2: size={stats2['size']}")
    print(f"Stats match: {stats1 == stats2}")
    
    all_tests_passed = (
        scraper1.cache is scraper2.cache and
        scraper2.cache is scraper3.cache and
        test_data == retrieved_data and
        stats1 == stats2
    )
    
    if all_tests_passed:
        print("✓ All shared cache tests passed!")
    else:
        print("✗ Some tests failed!")
    
    return all_tests_passed

if __name__ == "__main__":
    asyncio.run(test_shared_cache())