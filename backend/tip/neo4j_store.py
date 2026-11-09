import hashlib
import json
import logging
from typing import Any

from pydantic import SecretStr

from .config import Settings
from .models import AnalysisResult

logger = logging.getLogger(__name__)


class Neo4jStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._driver = None
        values = (
            settings.neo4j_uri,
            settings.neo4j_username,
            settings.neo4j_password.get_secret_value(),
        )
        self.configured = all(values)
        if self.configured:
            try:
                from neo4j import GraphDatabase

                self._driver = GraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=(settings.neo4j_username, values[2]),
                )
            except Exception:
                logger.error("Neo4j driver initialization failed")
                raise ValueError("Neo4j driver initialization failed; check backend dependencies")

    def verify_connectivity(self) -> bool:
        if not self.configured or self._driver is None:
            return False
        try:
            self._driver.verify_connectivity()
            return True
        except Exception:
            logger.warning("Neo4j connectivity check failed")
            return False

    def close(self):
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    @staticmethod
    def _record(tx: Any, record: dict):
        tx.run(
            """
            MERGE (analysis:TIPAnalysis {task_id: $task_id})
            SET analysis.target_application = $target_application,
                analysis.document_title = $document_title,
                analysis.analysis_json = $analysis_json,
                analysis.status = 'SUCCESS',
                analysis.schema_version = '2.0',
                analysis.updated_at = datetime()
            WITH analysis
            UNWIND $requirements AS requirement
            MERGE (item:TIPRequirement {key: requirement.key})
            SET item.task_id = $task_id,
                item.requirement_id = requirement.id,
                item.category = requirement.category,
                item.statement = requirement.statement,
                item.acceptance_criterion = requirement.acceptance_criterion,
                item.priority = requirement.priority,
                item.origin = requirement.origin,
                item.implementation_status = requirement.implementation_status,
                item.evidence_status = requirement.evidence_status
            MERGE (analysis)-[:HAS_REQUIREMENT]->(item)
            WITH item, requirement
            UNWIND requirement.evidence AS evidence
            MERGE (source:TIPEvidence {key: evidence.key})
            SET source.source_type = evidence.source_type,
                source.source_name = evidence.source_name,
                source.file_path = evidence.file_path,
                source.external_id = evidence.external_id,
                source.worksheet = evidence.worksheet,
                source.row = evidence.row,
                source.description = evidence.description
            MERGE (item)-[:SUPPORTED_BY]->(source)
            """,
            **record,
        ).consume()

    @staticmethod
    def make_record(task_id: str, result: AnalysisResult) -> dict:
        source_json = result.model_dump_json()
        requirements = []
        for category, values in (
            ("FUNCTIONAL", result.highLevelRequirements),
            ("NON_FUNCTIONAL", result.nonFunctionalRequirements),
        ):
            for requirement in values:
                evidence = []
                for item in requirement.sourceEvidence:
                    identity = {
                        "sourceType": item.sourceType,
                        "sourceName": item.sourceName,
                        "filePath": item.filePath,
                        "externalId": item.externalId,
                        "worksheet": item.worksheet,
                        "row": item.row,
                    }
                    evidence.append({
                        "key": hashlib.sha256(
                            json.dumps(identity, sort_keys=True).encode("utf-8")
                        ).hexdigest(),
                        "source_type": item.sourceType,
                        "source_name": item.sourceName,
                        "file_path": item.filePath,
                        "external_id": item.externalId,
                        "worksheet": item.worksheet,
                        "row": item.row,
                        "description": item.evidenceDescription,
                    })
                requirements.append({
                    "key": f"{task_id}:{requirement.id}",
                    "id": requirement.id,
                    "category": category,
                    "statement": requirement.requirement,
                    "acceptance_criterion": requirement.acceptanceCriterion,
                    "priority": str(requirement.priority) if requirement.priority is not None else None,
                    "origin": requirement.requirementOrigin,
                    "implementation_status": requirement.implementationEvidenceStatus,
                    "evidence_status": requirement.evidenceStatus,
                    "evidence": evidence,
                })
        return {
            "task_id": task_id,
            "target_application": result.documentInformation.targetApplication,
            "document_title": result.documentTitle,
            "analysis_json": source_json,
            "requirements": requirements,
        }

    def persist(self, task_id: str, result: AnalysisResult):
        if not self.configured or self._driver is None:
            raise ValueError(
                "Neo4j is not configured. Set TIP_NEO4J_URI, TIP_NEO4J_USERNAME, "
                "and TIP_NEO4J_PASSWORD before submitting an analysis."
            )
        record = self.make_record(task_id, result)
        try:
            with self._driver.session(database=self.settings.neo4j_database) as session:
                session.execute_write(self._record, record)
        except Exception:
            logger.error("Neo4j analysis persistence failed for task %s", task_id)
            raise ValueError(
                "Neo4j analysis persistence failed; verify server connectivity, "
                "database name, and write permissions. No successful result was published."
            )