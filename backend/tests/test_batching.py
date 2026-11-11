import hashlib

from tip.batching import AnalysisAccumulator, iter_artifact_batches
from tip.models import Artifact, InputContext, SupportingInputs
from tip.validation import validate_merged_result, validate_result

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