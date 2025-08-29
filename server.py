# basic import 
from mcp.server.fastmcp import FastMCP
import math

# instantiate an MCP server client
mcp = FastMCP("Hello World")

# DEFINE TOOLS


# DEFINE RESOURCES
@mcp.resource("price")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    return f"Hello, {name}!"
    
 
# execute and return the stdio output
if __name__ == "__main__":
    mcp.run(transport="stdio")
