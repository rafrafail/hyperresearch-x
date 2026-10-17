"""MCP server command — start the hyperresearch MCP server for agent integration."""

from __future__ import annotations

import os
import sys

import typer


def mcp(
    read_only: bool = typer.Option(
        False,
        "--read-only",
        help="Expose only non-mutating vault tools (recommended for agent plugins).",
    ),
) -> None:
    """Start the MCP server (stdio transport) for agent integrations.

    Requires: pip install hyperresearch[mcp]
    """
    if read_only:
        # The server reads this before registering any tools. Set it here rather
        # than in a manifest so direct CLI users can still opt in deliberately.
        os.environ["HYPERRESEARCH_MCP_READ_ONLY"] = "1"
    try:
        from hyperresearch.mcp.server import server
    except ImportError:
        print("MCP server requires: pip install hyperresearch[mcp]", file=sys.stderr)
        sys.exit(1)

    server.run()
