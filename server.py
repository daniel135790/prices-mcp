# basic import 
import sys
print("Starting server script...", file=sys.stderr)
from fastmcp import FastMCP
print("FastMCP imported", file=sys.stderr)
from scraper import Scraper
print("Scraper imported", file=sys.stderr)

# instantiate an MCP server client
print("Creating FastMCP instance...", file=sys.stderr)
mcp = FastMCP("Hello World")
print("FastMCP instance created", file=sys.stderr)

# DEFINE TOOLS


# DEFINE RESOURCES
@mcp.resource("products://{supermarket}/{branch}/products", mime_type="application/json", annotations={
    "readOnlyHint": True,
    "idempotentHint": True
}, description="Retrieves a list of products from a specific supermarket branch.")
async def get_products(supermarket: str, branch: str) -> str:
    print(supermarket, branch)
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
    
    most_expensive = max(products, key=lambda x: float(x.get('price', 0)))
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
    "repos://{owner}/{repo}/info",
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True
    }
)
async def get_repo_info(owner: str, repo: str) -> dict:
    """Retrieves information about a GitHub repository."""
    # In a real implementation, this would call the GitHub API
    return {
        "owner": owner,
        "name": repo,
        "full_name": f"{owner}/{repo}",
        "stars": 120,
        "forks": 48
    }

# execute and return the stdio output
if __name__ == "__main__":
    print("Entering main block...", file=sys.stderr)
    try:
        print("Starting MCP server...", file=sys.stderr)
        mcp.run(transport="stdio")
        # mcp.run(transport="http", host="127.0.0.1", port=8000)
    except Exception as e:
        print(f'Error occurred while starting the server: {e}', file=sys.stderr)
        raise

