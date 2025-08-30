import sys
print("Test server starting...", file=sys.stderr)

from fastmcp import FastMCP
print("FastMCP imported", file=sys.stderr)

mcp = FastMCP("Test Server")
print("FastMCP instance created", file=sys.stderr)

@mcp.resource("test://hello", description="Simple test resource")
def test_resource():
    return {"message": "Hello from test server"}

print("Resource defined", file=sys.stderr)

if __name__ == "__main__":
    print("Starting server...", file=sys.stderr)
    mcp.run(transport="stdio")