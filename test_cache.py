#!/usr/bin/env python3
"""
Test script to verify the caching functionality in the scraper
"""
import asyncio
import json
from scraper import Scraper

async def test_caching():
    """Test caching functionality with mock data"""
    print("Testing caching functionality...")
    
    scraper = Scraper()
    
    # Test cache key generation
    cache_key = scraper._generate_cache_key("shufersal", "3")
    print(f"Generated cache key: {cache_key}")
    assert cache_key == "products:shufersal:3", f"Expected 'products:shufersal:3', got '{cache_key}'"
    
    # Test caching products (mock data)
    mock_products = [
        {
            "item_code": "123456789",
            "item_name": "Test Product",
            "item_price": 10.99,
            "chain_id": "7290027600007",
            "store_id": "003"
        },
        {
            "item_code": "987654321", 
            "item_name": "Another Product",
            "item_price": 25.50,
            "chain_id": "7290027600007",
            "store_id": "003"
        }
    ]
    
    # Cache the products
    await scraper._cache_products("shufersal", "3", mock_products)
    print("✓ Products cached successfully")
    
    # Try to retrieve from cache
    cached_products = await scraper._get_cached_products("shufersal", "3")
    if cached_products:
        print(f"✓ Retrieved {len(cached_products)} products from cache")
        print(f"First product: {cached_products[0]['item_name']}")
        assert len(cached_products) == 2, f"Expected 2 products, got {len(cached_products)}"
        assert cached_products[0]['item_name'] == "Test Product", f"Product name mismatch"
    else:
        print("✗ Failed to retrieve products from cache")
        return False
    
    # Test cache miss for different branch
    cache_miss = await scraper._get_cached_products("shufersal", "5") 
    if cache_miss is None:
        print("✓ Cache miss for different branch works correctly")
    else:
        print("✗ Expected cache miss, but got data")
        return False
    
    # Test cache statistics
    stats = await scraper.cache.get_stats()
    print(f"Cache stats: {json.dumps(stats, indent=2)}")
    
    print("\n✓ All caching tests passed!")
    return True

async def test_cache_ttl():
    """Test cache TTL functionality"""
    print("\nTesting cache TTL...")
    
    scraper = Scraper()
    
    # Cache with short TTL for testing
    test_data = {"test": "data"}
    await scraper.cache.set('test', 'short_ttl', test_data, ttl=1)  # 1 second TTL
    
    # Immediate retrieval should work
    cached_data = await scraper.cache.get('test', 'short_ttl')
    if cached_data:
        print("✓ Immediate cache retrieval works")
    else:
        print("✗ Immediate cache retrieval failed")
        return False
    
    # Wait for expiration
    print("Waiting for cache to expire...")
    await asyncio.sleep(2)
    
    # Should be expired now
    expired_data = await scraper.cache.get('test', 'short_ttl') 
    if expired_data is None:
        print("✓ Cache expiration works correctly")
    else:
        print("✗ Cache did not expire as expected")
        return False
    
    print("✓ TTL test passed!")
    return True

if __name__ == "__main__":
    async def main():
        try:
            success1 = await test_caching()
            success2 = await test_cache_ttl()
            
            if success1 and success2:
                print("\n🎉 All tests passed! Caching is working correctly.")
            else:
                print("\n❌ Some tests failed.")
        except Exception as e:
            print(f"\n❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(main())