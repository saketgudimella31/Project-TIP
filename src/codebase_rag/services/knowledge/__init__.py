"""Knowledge services; import legacy dependencies only when explicitly selected."""


def __getattr__(name):
    if name in {"Neo4jKnowledgeService", "neo4j_knowledge_service"}:
        from importlib import import_module

        legacy = import_module(".neo4j_knowledge_service", __name__)
        globals().update({key: getattr(legacy, key) for key in __all__})
        return getattr(legacy, name)
    raise AttributeError(name)

__all__ = ["Neo4jKnowledgeService", "neo4j_knowledge_service"]
