"""Walking-skeleton MCP server: one tool with a fixed answer (ADR-0003).

It only proves the chain OpenCode -> MCP -> our code works. The real
`find_symbol` lives in the context engine and replaces this stub.
"""

from mcp.server import MCPServer

server = MCPServer("orchestron-stub")


@server.tool()
def find_symbol(name: str) -> str:
    """Return where a Python symbol is defined (stub: always the same answer)."""
    return f"STUB: symbol '{name}' is defined in <stub>.py at line 1"


def main() -> None:
    server.run()  # stdio transport, which OpenCode's "local" MCP type uses


if __name__ == "__main__":
    main()
