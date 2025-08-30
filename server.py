# basic import 
import sys
import logging
from fastmcp import FastMCP
from scraper import Scraper

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create handler that writes to file
handler = logging.FileHandler('server.log')
handler.setLevel(logging.DEBUG)

# Formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

# Add handler to logger
logger.addHandler(handler)
logger.propagate = False  # prevent duplication

logger.debug("Starting server script...")
logger.debug("FastMCP imported")
logger.debug("Scraper imported")

# instantiate an MCP server client
logger.debug("Creating FastMCP instance...")
mcp = FastMCP("Hello World", log_level="DEBUG")
logger.debug("FastMCP instance created")

# DEFINE TOOLS


# DEFINE RESOURCES
@mcp.resource("products://{supermarket}/{branch}/products", mime_type="application/json", annotations={
    "readOnlyHint": True,
    "idempotentHint": True
}, description="Retrieves a list of products from a specific supermarket branch.")
async def get_products(supermarket: str, branch: str) -> str:
    logger.debug(f"Getting products for {supermarket} branch {branch}")
    scraper = Scraper()
    products = await scraper.scrape(supermarket, branch)
    return products


# Product aggregation resources
@mcp.resource("products://{supermarket}/{branch}/most_expensive", 
              mime_type="application/json",
              annotations={"readOnlyHint": True, "idempotentHint": True},
              description="Get the most expensive product from a supermarket branch")
async def get_most_expensive_product(supermarket: str, branch: str) -> str:
    scraper = Scraper()
    products = await scraper.scrape(supermarket, branch)
    if not products:
        return '{"error": "No products found"}'
    
    import json
    if isinstance(products, str):
        products = json.loads(products)
    
    most_expensive = max(products, key=lambda x: float(x.get('item_price', 0)))
    return json.dumps(most_expensive)

@mcp.resource("products://{supermarket}/{branch}/cheapest", 
              mime_type="application/json",
              annotations={"readOnlyHint": True, "idempotentHint": True},
              description="Get the cheapest product from a supermarket branch")
async def get_cheapest_product(supermarket: str, branch: str) -> str:
    scraper = Scraper()
    products = await scraper.scrape(supermarket, branch)
    if not products:
        return '{"error": "No products found"}'
    
    import json
    if isinstance(products, str):
        products = json.loads(products)
    
    cheapest = min(products, key=lambda x: float(x.get('price', 0)))
    return json.dumps(cheapest)

@mcp.resource("products://{supermarket}/{branch}/sorted/{sort_by}/limit/{limit}", 
              mime_type="application/json",
              annotations={"readOnlyHint": True, "idempotentHint": True},
              description="Get sorted and limited products (sort_by: price_asc, price_desc, name)")
async def get_sorted_products(supermarket: str, branch: str, sort_by: str, limit: str) -> str:
    scraper = Scraper()
    products = await scraper.scrape(supermarket, branch)
    if not products:
        return '{"error": "No products found"}'
    
    import json
    if isinstance(products, str):
        products = json.loads(products)
    
    # Sort products
    if sort_by == "price_asc":
        products = sorted(products, key=lambda x: float(x.get('price', 0)))
    elif sort_by == "price_desc":
        products = sorted(products, key=lambda x: float(x.get('price', 0)), reverse=True)
    elif sort_by == "name":
        products = sorted(products, key=lambda x: x.get('name', ''))
    
    # Limit results
    try:
        limit_num = int(limit)
        products = products[:limit_num]
    except ValueError:
        pass
    
    return json.dumps(products)

@mcp.resource("products://{supermarket}/{branch}/stats", 
              mime_type="application/json",
              annotations={"readOnlyHint": True, "idempotentHint": True},
              description="Get price statistics for products from a supermarket branch")
async def get_product_stats(supermarket: str, branch: str) -> str:
    scraper = Scraper()
    products = await scraper.scrape(supermarket, branch)
    if not products:
        return '{"error": "No products found"}'
    
    import json
    if isinstance(products, str):
        products = json.loads(products)
    
    prices = [float(p.get('price', 0)) for p in products if p.get('price')]
    if not prices:
        return '{"error": "No valid prices found"}'
    
    stats = {
        "count": len(products),
        "price_count": len(prices),
        "most_expensive": max(prices),
        "cheapest": min(prices),
        "average_price": sum(prices) / len(prices),
        "total_value": sum(prices)
    }
    return json.dumps(stats)


# Template with multiple parameters and annotations
@mcp.resource(
    "test://ping"
)
async def ping() -> dict:
    """Pings the server."""
    logger.debug("Ping resource called")
    return {"message": "pong"}

# execute and return the stdio output
if __name__ == "__main__":
    logger.debug("Entering main block...")
    try:
        logger.debug("Starting MCP server...")
        mcp.run(transport="stdio")
        # mcp.run(transport="http", host="127.0.0.1", port=8000)
    except Exception as e:
        logger.error(f'Error occurred while starting the server: {e}')
        raise

