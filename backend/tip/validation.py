import re

from .models import AnalysisResult, Artifact, Evidence, InputContext


def validate_plantuml(text: str):
    stripped = text.strip()
    if (
        not stripped.startswith("@startuml")
        or not stripped.endswith("@enduml")
        or stripped.count("@startuml") != 1
        or stripped.count("@enduml") != 1
        or len(stripped) > 50_000
    ):
        raise ValueError("PlantUML must contain one bounded, self-contained diagram")
    if re.search(
        r"(?im)^\s*!|https?://|file:|<img|\[\[|%\w+\s*\(|"
        r"(?im:^\s*(?:url|image|sprite|theme)\b)", text
    ):
        raise ValueError("External resources and executable PlantUML directives are not allowed")
    if not re.search(r"(?im)^\s*title\s+\S", text):
        raise ValueError("Generated PlantUML must include a descriptive title")


def validate_result(result: AnalysisResult, artifacts: list[Artifact],
                    context: InputContext, target: str):
    if result.inputContext != context or result.analysisScope.analysisMode != context.analysisMode:
        raise ValueError("Model changed the supplied analysis scope or input context")
    if result.documentInformation.targetApplication != target:
        raise ValueError("Model changed the target application")

    def check(evidence: Evidence):
        candidates = [
            artifact for artifact in artifacts
            if artifact.sourceType == evidence.sourceType
            and artifact.sourceName == evidence.sourceName
            and (evidence.filePath is None or artifact.filePath == evidence.filePath)
            and (evidence.externalId is None or artifact.externalId == evidence.externalId)
            and (evidence.worksheet is None or artifact.worksheet == evidence.worksheet)
            and (evidence.row is None or artifact.row == evidence.row)
        ]
        if not candidates:
            raise ValueError(f"Model cited an unknown evidence source: {evidence.sourceName}")
        if evidence.lineStart is not None and not any(
            len(a.content.splitlines()) >= (evidence.lineEnd or evidence.lineStart)
            for a in candidates
        ):
            raise ValueError("Model cited a line outside the supplied artifact")
        if evidence.section and not any(evidence.section in a.content for a in candidates):
            raise ValueError("Model cited a section not present in the supplied artifact")
        # Symbols and evidence descriptions still require human review; matching a file
        # reference cannot prove that the claimed behavior is semantically correct.

    requirements = [*result.highLevelRequirements, *result.nonFunctionalRequirements]
    for prefix, group in (
        ("HLR", result.highLevelRequirements), ("NFR", result.nonFunctionalRequirements)
    ):
        if [r.id for r in group] != [
            f"{prefix}-{i:03d}" for i in range(1, len(group) + 1)
        ]:
            raise ValueError("Requirement IDs are not sequential")
    for requirement in requirements:
        for evidence in requirement.sourceEvidence:
            check(evidence)
        origins = {e.sourceType for e in requirement.sourceEvidence}
        if set(requirement.requirementOrigin) != origins:
            raise ValueError("Requirement origin does not match the cited evidence types")
        if requirement.implementationEvidenceStatus in {
            "IMPLEMENTATION_EVIDENCED", "IMPLEMENTATION_PARTIALLY_EVIDENCED",
        } and "CODE" not in origins:
            raise ValueError("Requirement claims implementation without cited code")
    generated_names = set()
    for name, diagram in result.umlDiagrams.entries():
        if diagram.generated:
            validate_plantuml(diagram.plantUml)
            generated_names.update((name, diagram.title))
            for evidence in diagram.sourceEvidence:
                check(evidence)
        elif "[" in name:
            raise ValueError("Diagram arrays cannot contain non-generated placeholders")
    by_id = {r.id: r for r in requirements}
    trace_ids = [t.requirementId for t in result.requirementsToDesignTraceability]
    if len(trace_ids) != len(set(trace_ids)) or set(trace_ids) != set(by_id):
        raise ValueError("Traceability must map every requirement exactly once")
    for trace in result.requirementsToDesignTraceability:
        requirement = by_id[trace.requirementId]
        if (
            trace.sourceEvidence != requirement.sourceEvidence
            or trace.implementationEvidenceStatus != requirement.implementationEvidenceStatus
            or set(trace.requirementOrigin) != set(requirement.requirementOrigin)
            or trace.validationStatus != requirement.evidenceStatus
        ):
            raise ValueError("Traceability disagrees with its requirement")
        if not set(trace.relevantGeneratedDiagrams).issubset(generated_names):
            raise ValueError("Traceability references an ungenerated or unknown diagram")
    actual_code = {a.filePath: a for a in artifacts if a.sourceType == "CODE"}
    inventory_paths = [entry.relativePath for entry in result.codebaseInventory]
    if len(inventory_paths) != len(set(inventory_paths)) or set(inventory_paths) != set(actual_code):
        raise ValueError("Code inventory must contain exactly the supplied code files")
    for entry in result.codebaseInventory:
        artifact = actual_code[entry.relativePath]
        if entry.sha256 != artifact.sha256:
            raise ValueError("Model altered an artifact fingerprint")
    actual_support = {
        (a.sourceType, a.sourceName, a.externalId)
        for a in artifacts if a.sourceType != "CODE"
    }
    supplied_support = {
        (a.sourceType, a.sourceName, a.externalId) for a in result.supportingArtifactInventory
    }
    if actual_support != supplied_support:
        raise ValueError("Supporting inventory does not match the supplied artifacts")


def add_backend_warnings(result: AnalysisResult, context: InputContext,
                         artifacts: list[Artifact], warnings: list[str]):
    additions = list(warnings)
    if context.analysisMode != "FULL":
        additions.append(
            f"{context.analysisMode} scope: results describe only the supplied artifacts, "
            "not the complete application."
        )
    if not any(a.sourceType == "CODE" for a in artifacts):
        additions.append("No code implementation evidence was supplied; implementation is not verified.")
    for warning in additions:
        if warning not in result.warnings:
            result.warnings.append(warning)
        if warning not in result.limitations:
            result.limitations.append(warning)
        if warning not in result.analysisScope.limitations:
            result.analysisScope.limitations.append(warning)