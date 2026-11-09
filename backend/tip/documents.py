import io
import json
import subprocess

from docx import Document
from docx.shared import Inches

from .config import Settings
from .models import AnalysisResult, Diagram, Evidence
from .validation import validate_plantuml


def evidence_text(items: list[Evidence]) -> str:
    parts = []
    for item in items:
        location = item.filePath or item.sourceName
        if item.externalId:
            location += f" [{item.externalId}]"
        if item.worksheet:
            location += f" / {item.worksheet}"
        if item.row:
            location += f" row {item.row}"
        if item.lineStart:
            location += f" lines {item.lineStart}-{item.lineEnd or item.lineStart}"
        if item.section:
            location += f" / {item.section}"
        parts.append(f"{item.sourceType}: {location}: {item.evidenceDescription}")
    return "\n".join(parts)


def render_diagram(diagram: Diagram, settings: Settings) -> bytes:
    validate_plantuml(diagram.plantUml)
    if not settings.plantuml_jar or not settings.plantuml_jar.is_file():
        raise ValueError(
            "The model generated UML, but TIP_PLANTUML_JAR is not configured. "
            "Install the local PlantUML renderer and resubmit; no incomplete Word file was published."
        )
    process = subprocess.run(
        [
            "java", "-Xmx256m", "-Djava.awt.headless=true",
            "-DPLANTUML_SECURITY_PROFILE=SANDBOX",
            "-jar", str(settings.plantuml_jar.resolve()),
            "-pipe", "-tpng", "-failfast2",
        ],
        input=diagram.plantUml.encode("utf-8"), capture_output=True,
        timeout=40, check=False,
    )
    image = process.stdout
    if process.returncode or not image.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"Local PlantUML rendering failed for {diagram.title}")
    if len(image) > 10_000_000:
        raise ValueError("Rendered UML image exceeds the size limit")
    return image


def create_document(result: AnalysisResult, settings: Settings) -> bytes:
    document = Document()
    document.add_heading(result.documentTitle, 0)
    document.add_paragraph("Draft for Human Validation")
    document.add_paragraph("Fiserv Internal Use Only")
    document.add_heading("Document Information", 1)
    for key, value in result.documentInformation.model_dump().items():
        document.add_paragraph(f"{key}: {value}")
    document.add_heading("Document Basis", 1)
    document.add_paragraph(
        "Derived only from supplied readable artifacts. Requirements evidence and implementation "
        "evidence are distinct. All content requires human review."
    )
    document.add_heading("1. Executive Summary", 1)
    document.add_paragraph(result.executiveSummary)
    document.add_heading("2. Analysis Scope", 1)
    document.add_paragraph(result.analysisScope.scopeDescription)
    document.add_paragraph(f"Analysis mode: {result.analysisScope.analysisMode}")
    for key in ("includedFiles", "excludedFiles", "unsupportedFiles", "unreadableFiles", "limitations"):
        document.add_paragraph(f"{key}: {json.dumps(getattr(result.analysisScope, key), ensure_ascii=False)}")
    document.add_heading("3. Source Artifact Inventory", 1)
    document.add_heading("3.1 Codebase Artifacts", 2)
    for item in result.codebaseInventory:
        document.add_paragraph(
            f"{item.relativePath} [{item.processingStatus}]: {item.purpose}\n"
            f"SHA-256: {item.sha256 or 'Not supplied'}"
        )
    for number, name, kind in (
        ("3.2", "Design Documents", "DESIGN_DOCUMENT"),
        ("3.3", "Jira User Stories", "JIRA_USER_STORY"),
        ("3.4", "Raw Requirements", "RAW_REQUIREMENT"),
    ):
        document.add_heading(f"{number} {name}", 2)
        items = [i for i in result.supportingArtifactInventory if i.sourceType == kind]
        for item in items:
            document.add_paragraph(
                f"{item.sourceName} [{item.processingStatus}] "
                f"{item.externalId or ''}: {item.purpose}"
            )
        if not items:
            document.add_paragraph("Not supplied.")
    document.add_heading("4. Application Overview", 1)
    document.add_paragraph(result.applicationOverview.purpose)
    for key, value in result.applicationOverview.model_dump().items():
        if key != "purpose":
            document.add_heading(key, 2)
            for entry in value:
                document.add_paragraph(
                    entry if isinstance(entry, str) else json.dumps(entry, ensure_ascii=False)
                )
    for title, requirements in (
        ("5. High-Level Functional Requirements", result.highLevelRequirements),
        ("6. Non-Functional Requirements", result.nonFunctionalRequirements),
    ):
        document.add_heading(title, 1)
        for requirement in requirements:
            document.add_heading(requirement.id, 2)
            for key, value in requirement.model_dump(exclude={"sourceEvidence", "id"}).items():
                document.add_paragraph(f"{key}: {value if value is not None else 'Not supplied'}")
            document.add_paragraph(evidence_text(requirement.sourceEvidence))
        if not requirements:
            document.add_paragraph("Not evidenced in the supplied artifacts.")
    document.add_heading("7. UML Diagrams", 1)
    for index, (key, title) in enumerate((
        ("componentDiagram", "Component Diagram"), ("classDiagram", "Class Diagram"),
        ("sequenceDiagrams", "Sequence Diagrams"), ("packageDiagram", "Package Diagram"),
        ("activityDiagrams", "Activity Diagrams"), ("deploymentDiagram", "Deployment Diagram"),
        ("stateMachineDiagrams", "State Machine Diagrams"), ("useCaseDiagram", "Use Case Diagram"),
    ), 1):
        document.add_heading(f"7.{index} {title}", 2)
        value = getattr(result.umlDiagrams, key)
        diagrams = value if isinstance(value, list) else [value]
        generated = [diagram for diagram in diagrams if diagram.generated]
        if not generated:
            document.add_paragraph("Not evidenced in the supplied artifacts.")
        for diagram in generated:
            document.add_heading(diagram.title, 3)
            document.add_paragraph(diagram.description)
            image = render_diagram(diagram, settings)
            document.add_picture(io.BytesIO(image), width=Inches(6))
            document.add_paragraph(evidence_text(diagram.sourceEvidence))
    document.add_heading("8. Requirements-to-Source-and-Design Traceability", 1)
    for trace in result.requirementsToDesignTraceability:
        document.add_heading(trace.requirementId, 2)
        document.add_paragraph(trace.requirementSummary)
        document.add_paragraph(
            f"{trace.implementationEvidenceStatus}; {trace.validationStatus}\n"
            f"Diagrams: {', '.join(trace.relevantGeneratedDiagrams)}\n"
            f"Design elements: {', '.join(trace.relevantDesignElements)}"
        )
        document.add_paragraph(evidence_text(trace.sourceEvidence))
    for title, entries in (
        ("9. Evidence Conflicts and Validation Items", [
            *result.evidenceConflicts, *result.warnings,
            *[f"{r.id}: {r.validationNotes}" for r in (
                *result.highLevelRequirements, *result.nonFunctionalRequirements
            ) if r.validationNotes],
        ]),
        ("10. Assumptions and Limitations", [*result.assumptions, *result.limitations]),
    ):
        document.add_heading(title, 1)
        for entry in entries:
            document.add_paragraph(
                entry if isinstance(entry, str) else json.dumps(entry, ensure_ascii=False)
            )
    document.add_heading("11. Human Validation and Approval Statement", 1)
    document.add_paragraph(result.validationStatement)
    document.add_paragraph("Reviewer: ____________________  Date: ____________________")
    stream = io.BytesIO()
    document.save(stream)
    return stream.getvalue()