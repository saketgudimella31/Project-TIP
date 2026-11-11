import re

from .models import AnalysisResult, Artifact, Diagram, Evidence, InputContext

INVALID_DIAGRAM_WARNING = (
    "One or more generated UML diagrams were omitted because their Mermaid source "
    "was invalid or unsupported."
)
CHUNK_RELATIVE_CITATION_WARNING = (
    "One or more chunk-relative line citations were converted to original file line numbers."
)
OMITTED_LINE_CITATION_WARNING = (
    "One or more line citations fell outside the supplied artifact chunk; line numbers were "
    "omitted while retaining the source-file references."
)


def validate_mermaid(text: str):
    stripped = text.strip()
    if (
        not re.match(
            r"(?:flowchart|graph|sequenceDiagram|classDiagram|stateDiagram-v2|erDiagram)\b",
            stripped,
            re.IGNORECASE,
        )
        or len(stripped) > 50_000
        or len(stripped.splitlines()) > 1_000
    ):
        raise ValueError("Mermaid must contain one bounded, supported diagram")
    if re.search(
        r"^\s*%%\s*\{|^\s*click\s+\S|"
        r"https?://|file:|data:|javascript:|url\s*\(|"
        r"\bhref\s*[:=]|<\s*(?:script|iframe|img|foreignObject|svg|style)\b",
        text,
        re.IGNORECASE | re.MULTILINE,
    ):
        raise ValueError("External resources, directives, and executable Mermaid content are not allowed")


def _synchronize_traceability(result: AnalysisResult) -> None:
    requirements = {
        requirement.id: requirement
        for requirement in [
            *result.highLevelRequirements, *result.nonFunctionalRequirements,
        ]
    }
    repaired = False
    for trace in result.requirementsToDesignTraceability:
        requirement = requirements.get(trace.requirementId)
        if requirement is None:
            continue
        if (
            trace.requirementSummary != requirement.requirement
            or trace.requirementOrigin != requirement.requirementOrigin
            or trace.sourceEvidence != requirement.sourceEvidence
            or trace.implementationEvidenceStatus != requirement.implementationEvidenceStatus
            or trace.validationStatus != requirement.evidenceStatus
        ):
            repaired = True
        trace.requirementSummary = requirement.requirement
        trace.requirementOrigin = list(requirement.requirementOrigin)
        trace.sourceEvidence = list(requirement.sourceEvidence)
        trace.implementationEvidenceStatus = requirement.implementationEvidenceStatus
        trace.validationStatus = requirement.evidenceStatus
    if repaired:
        warning = (
            "Repeated traceability details were synchronized from their linked requirements "
            "because the model output disagreed."
        )
        if warning not in result.warnings:
            result.warnings.append(warning)


def _sanitize_invalid_diagrams(result: AnalysisResult) -> None:
    diagrams = result.umlDiagrams
    valid_references: dict[str, str] = {}
    invalid_references = set()
    invalid_count = 0

    for name in type(diagrams).model_fields:
        value = getattr(diagrams, name)
        if isinstance(value, list):
            retained = []
            for index, diagram in enumerate(value):
                reference = f"{name}[{index}]"
                if diagram.generated:
                    try:
                        validate_mermaid(diagram.mermaid)
                    except ValueError:
                        invalid_count += 1
                        invalid_references.update((reference, diagram.title))
                        continue
                    valid_references[reference] = f"{name}[{len(retained)}]"
                    valid_references[diagram.title] = diagram.title
                retained.append(diagram)
            setattr(diagrams, name, retained)
            continue

        if not value.generated:
            continue
        try:
            validate_mermaid(value.mermaid)
        except ValueError:
            invalid_count += 1
            invalid_references.update((name, value.title))
            setattr(diagrams, name, Diagram(
                generated=False,
                title="",
                description="",
                mermaid="",
                sourceEvidence=[],
                reason="Not evidenced in the supplied artifacts.",
            ))
        else:
            valid_references[name] = name
            valid_references[value.title] = value.title

    if not invalid_count:
        return
    for trace in result.requirementsToDesignTraceability:
        trace.relevantGeneratedDiagrams = [
            valid_references.get(reference, reference)
            for reference in trace.relevantGeneratedDiagrams
            if reference not in invalid_references or reference in valid_references
        ]
    if INVALID_DIAGRAM_WARNING not in result.warnings:
        result.warnings.append(INVALID_DIAGRAM_WARNING)


def validate_result(result: AnalysisResult, artifacts: list[Artifact],
                    context: InputContext, target: str):
    _synchronize_traceability(result)
    _sanitize_invalid_diagrams(result)
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
        if evidence.lineStart is not None:
            line_end = evidence.lineEnd or evidence.lineStart

            def contains_original_lines(artifact: Artifact) -> bool:
                first_line = artifact.lineOffset + 1
                last_line = artifact.lineOffset + len(artifact.content.splitlines())
                return first_line <= evidence.lineStart and line_end <= last_line

            if not any(contains_original_lines(artifact) for artifact in candidates):
                relative_offsets = {
                    artifact.lineOffset for artifact in candidates
                    if artifact.lineOffset > 0
                    and line_end <= len(artifact.content.splitlines())
                }
                if len(relative_offsets) == 1:
                    offset = relative_offsets.pop()
                    evidence.lineStart += offset
                    if evidence.lineEnd is not None:
                        evidence.lineEnd += offset
                    if CHUNK_RELATIVE_CITATION_WARNING not in result.warnings:
                        result.warnings.append(CHUNK_RELATIVE_CITATION_WARNING)
                else:
                    evidence.lineStart = None
                    evidence.lineEnd = None
                    if OMITTED_LINE_CITATION_WARNING not in result.warnings:
                        result.warnings.append(OMITTED_LINE_CITATION_WARNING)
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
            validate_mermaid(diagram.mermaid)
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


def validate_merged_result(
    result: AnalysisResult, context: InputContext, target: str, *,
    expected_code_files: int, expected_supporting_artifacts: int,
):
    _synchronize_traceability(result)
    _sanitize_invalid_diagrams(result)
    if result.inputContext != context or result.analysisScope.analysisMode != context.analysisMode:
        raise ValueError("Merged output changed the supplied analysis scope or input context")
    if result.documentInformation.targetApplication != target:
        raise ValueError("Merged output changed the target application")
    if (
        result.analysisScope.analyzedCodeFiles != expected_code_files
        or result.analysisScope.analyzedSupportingArtifacts != expected_supporting_artifacts
    ):
        raise ValueError("Merged output coverage does not match the analyzed input")

    requirements = [*result.highLevelRequirements, *result.nonFunctionalRequirements]
    for prefix, group in (
        ("HLR", result.highLevelRequirements), ("NFR", result.nonFunctionalRequirements)
    ):
        if [item.id for item in group] != [
            f"{prefix}-{index:03d}" for index in range(1, len(group) + 1)
        ]:
            raise ValueError("Merged requirement IDs are not sequential")
    generated_names = set()
    for name, diagram in result.umlDiagrams.entries():
        if diagram.generated:
            validate_mermaid(diagram.mermaid)
            generated_names.update((name, diagram.title))
    by_id = {item.id: item for item in requirements}
    trace_ids = [item.requirementId for item in result.requirementsToDesignTraceability]
    if len(trace_ids) != len(set(trace_ids)) or set(trace_ids) != set(by_id):
        raise ValueError("Merged traceability must map every requirement exactly once")
    for requirement in requirements:
        origins = {item.sourceType for item in requirement.sourceEvidence}
        if set(requirement.requirementOrigin) != origins:
            raise ValueError("Merged requirement origin does not match its cited evidence")
        if requirement.implementationEvidenceStatus in {
            "IMPLEMENTATION_EVIDENCED", "IMPLEMENTATION_PARTIALLY_EVIDENCED",
        } and "CODE" not in origins:
            raise ValueError("Merged requirement claims implementation without cited code")
    for trace in result.requirementsToDesignTraceability:
        requirement = by_id[trace.requirementId]
        if (
            trace.sourceEvidence != requirement.sourceEvidence
            or trace.implementationEvidenceStatus != requirement.implementationEvidenceStatus
            or set(trace.requirementOrigin) != set(requirement.requirementOrigin)
            or trace.validationStatus != requirement.evidenceStatus
        ):
            raise ValueError("Merged traceability disagrees with its requirement")
        if not set(trace.relevantGeneratedDiagrams).issubset(generated_names):
            raise ValueError("Merged traceability references an omitted or unknown diagram")
    inventory_paths = [item.relativePath for item in result.codebaseInventory]
    if (
        len(inventory_paths) != len(set(inventory_paths))
        or len(inventory_paths) > expected_code_files
        or result.analysisScope.includedFiles != inventory_paths
    ):
        raise ValueError("Merged code inventory is inconsistent with analyzed coverage")
    if len(result.supportingArtifactInventory) > expected_supporting_artifacts:
        raise ValueError("Merged supporting inventory exceeds analyzed coverage")


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