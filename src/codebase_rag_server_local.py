"""Neo4j-free RAG API sharing TIP's ingestion, retrieval, and analysis contracts."""

from codebase_rag.services.graph.code_graph import Backend


def create_app():
    from tip.app import create_app as create_tip_app

    return create_tip_app()


def main(host: str = "127.0.0.1", port: int = 8000, backend: Backend | None = None):
    import uvicorn
    from tip.app import create_app as create_tip_app
    from tip.config import Settings

    config = Settings(**({"graph_backend": backend} if backend else {}))
    uvicorn.run(create_tip_app(config), host=host, port=port)