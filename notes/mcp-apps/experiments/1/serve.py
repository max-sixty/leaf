#!/usr/bin/env python3
"""Expose Leaf's stdio MCP server over HTTP for the official reference host."""

import uvicorn
from leaf.mcp_server import make_mcp_server
from starlette.middleware.cors import CORSMiddleware


def main() -> None:
    app = make_mcp_server().streamable_http_app(host="127.0.0.1")
    app = CORSMiddleware(
        app,
        allow_origins=["http://localhost:8080"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
    )
    uvicorn.run(app, host="127.0.0.1", port=3001, log_level="warning")


if __name__ == "__main__":
    main()
