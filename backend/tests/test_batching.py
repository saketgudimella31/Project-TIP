import hashlib

from tip.batching import AnalysisAccumulator, iter_artifact_batches
from tip.models import Artifact, InputContext, SupportingInputs
from tip.validation import (
    CHUNK_RELATIVE_CITATION_WARNING,
    INVALID_DIAGRAM_WARNING,
    OMITTED_LINE_CITATION_WARNING,
    validate_merged_result,
    validate_result,
)

from .fixtures import sample_result


def context():
    return InputContext(
        analysisMode="INCREMENTAL", inputType="LOCAL_FILES", sourceProvider=None,
        repository=None, branch=None, selectedPath=None, analysisFocus="order status",
        supportingInputs=SupportingInputs(
            designDocumentsProvided=False, jiraUserStoriesProvided=False,
            rawRequirementsProvided=False,
        ),
    )


def artifact(path: str, content: str) -> Artifact:
    return Artifact(
        sourceType="CODE", sourceName=path, content=content, filePath=path,
        sha256=hashlib.sha256(content.encode()).hexdigest(),
    )


def test_artifact_batches_preserve_content_and_original_line_offsets():
    source = artifact("src/orders.py", "a = 1\nb = 2\nc = 3\nd = 4\n")

    batches = list(iter_artifact_batches(
        [source], max_files=5, max_characters=12,
    ))
    parts = [item for batch in batches for item in batch]

    assert len(batches) == 2
    assert [item.lineOffset for item in parts] == [0, 2]
    assert "".join(item.content for item in parts) == source.content
    assert all(len(item.content) <= 12 for item in parts)


def test_accumulator_merges_batch_evidence_diagrams_and_traceability():
    analysis_context = context()
    artifacts = [
        artifact("src/orders.py", "def order_status(): return 'ready'\n"),
        artifact("src/payments.py", "def authorize(): return True\n"),
    ]
    accumulator = AnalysisAccumulator()

    for item in artifacts:
        batch_result = sample_result(
            "Orders", analysis_context, [item], with_diagram=True,
        )
        validate_result(batch_result, [item], analysis_context, "Orders")
        accumulator.add(batch_result)

    merged = accumulator.finish(
        analysis_context, expected_code_files=2, expected_supporting_artifacts=0,
    )
    validate_merged_result(
        merged, analysis_context, "Orders",
        expected_code_files=2, expected_supporting_artifacts=0,
    )

    assert [item.relativePath for item in merged.codebaseInventory] == [
        "src/orders.py", "src/payments.py",
    ]
    assert len(merged.highLevelRequirements[0].sourceEvidence) == 2
    assert len(merged.umlDiagrams.componentDiagram.sourceEvidence) == 2
    assert merged.requirementsToDesignTraceability[0].relevantGeneratedDiagrams == [
        "Synthetic order-status component",
    ]
    assert merged.analysisScope.analyzedCodeFiles == 2
    assert merged.analysisScope.analysisBatchCount == 2


def test_validation_synchronizes_repeated_traceability_fields():
    analysis_context = context()
    source = artifact("src/orders.py", "def order_status(): return 'ready'\n")
    result = sample_result("Orders", analysis_context, [source])
    requirement = result.highLevelRequirements[0]
    trace = result.requirementsToDesignTraceability[0]
    trace.requirementSummary = "An inconsistent summary"
    trace.requirementOrigin = []
    trace.sourceEvidence = []
    trace.implementationEvidenceStatus = "IMPLEMENTATION_NOT_EVIDENCED"
    trace.validationStatus = "PARTIALLY_EVIDENCED"

    validate_result(result, [source], analysis_context, "Orders")

    assert trace.requirementSummary == requirement.requirement
    assert trace.requirementOrigin == requirement.requirementOrigin
    assert trace.sourceEvidence == requirement.sourceEvidence
    assert trace.implementationEvidenceStatus == requirement.implementationEvidenceStatus
    assert trace.validationStatus == requirement.evidenceStatus
    assert result.warnings == [
        "Repeated traceability details were synchronized from their linked requirements "
        "because the model output disagreed.",
    ]
    accumulator = AnalysisAccumulator()
    accumulator.add(result)
    merged = accumulator.finish(
        analysis_context, expected_code_files=1, expected_supporting_artifacts=0,
    )
    validate_merged_result(
        merged, analysis_context, "Orders",
        expected_code_files=1, expected_supporting_artifacts=0,
    )
    assert result.warnings[0] in merged.warnings


def test_invalid_generated_diagram_is_omitted_without_failing_analysis():
    analysis_context = context()
    source = artifact("src/orders.py", "def order_status(): return 'ready'\n")
    result = sample_result("Orders", analysis_context, [source], with_diagram=True)
    result.umlDiagrams.componentDiagram.mermaid = "unsupportedDiagram"
    valid_sequence = result.umlDiagrams.componentDiagram.model_copy(update={
        "title": "Valid order sequence",
        "mermaid": "sequenceDiagram\n participant User\n User->>User: submit\n",
    })
    invalid_sequence = result.umlDiagrams.componentDiagram.model_copy(update={
        "title": "Invalid order sequence",
        "mermaid": "unsupportedDiagram",
    })
    result.umlDiagrams.sequenceDiagrams = [invalid_sequence, valid_sequence]
    result.requirementsToDesignTraceability[0].relevantGeneratedDiagrams.extend([
        "Invalid order sequence", "sequenceDiagrams[0]",
        "Valid order sequence", "sequenceDiagrams[1]",
    ])

    validate_result(result, [source], analysis_context, "Orders")

    assert not result.umlDiagrams.componentDiagram.generated
    assert [item.title for item in result.umlDiagrams.sequenceDiagrams] == [
        "Valid order sequence",
    ]
    assert result.requirementsToDesignTraceability[0].relevantGeneratedDiagrams == [
        "Valid order sequence", "sequenceDiagrams[0]",
    ]
    assert INVALID_DIAGRAM_WARNING in result.warnings

    accumulator = AnalysisAccumulator()
    accumulator.add(result)
    merged = accumulator.finish(
        analysis_context, expected_code_files=1, expected_supporting_artifacts=0,
    )
    validate_merged_result(
        merged, analysis_context, "Orders",
        expected_code_files=1, expected_supporting_artifacts=0,
    )
    assert not merged.umlDiagrams.componentDiagram.generated
    assert [item.title for item in merged.umlDiagrams.sequenceDiagrams] == [
        "Valid order sequence",
    ]
    assert INVALID_DIAGRAM_WARNING in merged.warnings


def test_validation_converts_chunk_relative_line_citations():
    analysis_context = context()
    source = artifact("src/orders.py", "def order_status(): return 'ready'\n")
    source.lineOffset = 40
    result = sample_result("Orders", analysis_context, [source])
    evidence = result.highLevelRequirements[0].sourceEvidence[0]
    evidence.lineStart = 1
    evidence.lineEnd = 1

    validate_result(result, [source], analysis_context, "Orders")

    assert evidence.lineStart == 41
    assert evidence.lineEnd == 41
    assert CHUNK_RELATIVE_CITATION_WARNING in result.warnings


def test_validation_omits_unverifiable_line_citation_without_failing():
    analysis_context = context()
    source = artifact("src/orders.py", "def order_status(): return 'ready'\n")
    result = sample_result("Orders", analysis_context, [source])
    evidence = result.highLevelRequirements[0].sourceEvidence[0]
    evidence.lineStart = 999
    evidence.lineEnd = 999

    validate_result(result, [source], analysis_context, "Orders")

    assert evidence.lineStart is None
    assert evidence.lineEnd is None
    assert OMITTED_LINE_CITATION_WARNING in result.warnings