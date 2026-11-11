"""
Main entry point for codebase-rag package.

Usage:
    python -m codebase_rag [--web|--mcp|--version]
"""

import sys
import argparse


def main():
    """Main entry point for the package."""
    parser = argparse.ArgumentParser(
        description="Codebase RAG - Code Knowledge Graph and RAG System"
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version information",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Start web server (FastAPI)",
    )
    parser.add_argument(
        "--mcp",
        action="store_true",
        help="Start MCP server",
    )
    parser.add_argument(
        "--graph-backend", choices=["kuzu", "sqlite", "neo4j"],
        help="Web graph backend (default: TIP_GRAPH_BACKEND or kuzu); neo4j selects the legacy server",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio")

    args = parser.parse_args()

    if args.version:
        from codebase_rag import __version__
        print(f"codebase-rag version {__version__}")
        return 0

    if args.mcp:
        if args.graph_backend == "neo4j":
            from codebase_rag.server.mcp import main as mcp_main
            return mcp_main()
        from codebase_rag.server.local_mcp import main as local_mcp_main
        return local_mcp_main(
            args.api_url, args.transport, args.host, 8001 if args.port == 8000 else args.port,
        )

    if args.web or not any([args.web, args.mcp, args.version]):
        # Default: start web server
        if args.graph_backend == "neo4j":
            print("Starting legacy Neo4j web server...")
            from codebase_rag.server.web import main as web_main
            return web_main()
        from codebase_rag.server.local import main as local_main
        return local_main(host=args.host, port=args.port, backend=args.graph_backend)

    return 0


if __name__ == "__main__":
    sys.exit(main())
