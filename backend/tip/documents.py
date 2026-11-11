import io
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from docx import Document
from docx.shared import Inches, Pt

from .models import AnalysisResult, Diagram, Evidence
from .validation import validate_mermaid


@dataclass(frozen=True)
class DocumentBundle:
    technical: bytes
    business: bytes


def _renderer_paths() -> tuple[Path, Path]:
    frontend = Path(__file__).resolve().parents[2] / "frontend"
    return frontend, frontend / "scripts" / "render-mermaid.mjs"


def mermaid_renderer_configured() -> bool:
    frontend, script = _renderer_paths()
    packages = (
        frontend / "node_modules" / "mermaid" / "package.json",
        frontend / "node_modules" / "jsdom" / "package.json",
        frontend / "node_modules" / "@resvg" / "resvg-js" / "package.json",
    )
    return bool(shutil.which("node") and script.is_file() and all(p.is_file() for p in packages))


def evidence_text(items: list[Evidence], limit: int | None = None) -> str:
    parts = []
    selected = items if limit is None else items[:limit]
    for item in selected:
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
    if limit is not None and len(items) > limit:
        parts.append(f"{len(items) - limit:,} additional evidence citations omitted from the DOCX.")
    return "\n".join(parts)


def _bounded_list_text(items: list, limit: int = 200) -> str:
    shown = items[:limit]
    if len(items) > limit:
        shown = [*shown, f"... {len(items) - limit:,} more entries omitted from the DOCX"]
    return json.dumps(shown, ensure_ascii=False)


def render_diagram(diagram: Diagram) -> bytes:
    validate_mermaid(diagram.mermaid)
    frontend, script = _renderer_paths()
    node = shutil.which("node")
    if not node or not script.is_file():
        raise ValueError(
            "Local Mermaid rendering requires Node.js and the frontend dependencies; "
            "run npm install in frontend."
        )
    try:
        process = subprocess.run(
            [node, str(script)],
            input=diagram.mermaid.encode("utf-8"),
            capture_output=True,
            timeout=45,
            check=False,
            cwd=frontend,
        )
    except subprocess.TimeoutExpired as error:
        raise ValueError(f"Local Mermaid rendering timed out for {diagram.title}") from error
    except FileNotFoundError as error:
        raise ValueError("Local Mermaid rendering could not start Node.js") from error
    image = process.stdout
    if process.returncode or not image.startswith(b"\x89PNG\r\n\x1a\n"):
        details = process.stderr.decode("utf-8", "replace").strip().splitlines()
        detail = f": {details[-1][:300]}" if details else ""
        raise ValueError(f"Local Mermaid rendering failed for {diagram.title}{detail}")
    if len(image) > 10_000_000:
        raise ValueError("Rendered Mermaid image exceeds the size limit")
    return image


def render_generated_diagrams(result: AnalysisResult) -> dict[str, bytes | None]:
    rendered = {}
    for reference, diagram in result.umlDiagrams.entries():
        if not diagram.generated:
            continue
        validate_mermaid(diagram.mermaid)
        try:
            rendered[reference] = render_diagram(diagram)
        except ValueError as error:
            rendered[reference] = None
            warning = (
                f"UML diagram '{diagram.title}' could not be rendered locally ({error}); "
                "a structured text version is included in the Word reports."
            )
            if warning not in result.warnings:
                result.warnings.append(warning)
    return rendered


_MERMAID_ARROW = re.compile(
    r"<-->|-->>|->>|<\|--|--\|>|-\.->|==>|-->|<--|--o|--x|o-->|x-->|->|---|--"
)


def _diagram_node_label(value: str) -> str:
    value = value.strip().rstrip(";")
    participant = re.match(
        r"^(?:participant|actor)\s+\S+(?:\s+as\s+(.+))?$", value, re.IGNORECASE,
    )
    if participant:
        return (participant.group(1) or value.split()[1]).strip()
    if value == "[*]":
        return "Start / end"
    shape = re.match(
        r"^[\w.-]+\s*(?:\[([^\]]*)\]|\(([^)]*)\)|\{([^}]*)\}|<([^>]*)>)",
        value,
    )
    if shape:
        return next((part.strip() for part in shape.groups() if part is not None), value)
    return value


def _diagram_rows(diagram: Diagram) -> list[tuple[str, str, str]]:
    rows = []
    current_class = ""
    for raw_line in diagram.mermaid.splitlines()[1:]:
        line = raw_line.strip().rstrip(";")
        if not line or line.startswith("%%"):
            continue
        participant = re.match(
            r"^(?:participant|actor)\s+(\S+)(?:\s+as\s+(.+))?$",
            line,
            re.IGNORECASE,
        )
        if participant:
            rows.append((participant.group(2) or participant.group(1), "participant", ""))
            continue
        class_declaration = re.match(r"^class\s+([\w.-]+)", line, re.IGNORECASE)
        if class_declaration:
            current_class = class_declaration.group(1)
            rows.append((current_class, "class", ""))
            continue
        if current_class and re.match(r"^[+\-#~]\s*[\w.-]+", line):
            rows.append((current_class, "member", line))
            continue
        er_relation = re.match(
            r"^([\w.-]+)\s+([|o{}<>-]+)\s+([\w.-]+)(?:\s*:\s*(.*))?$",
            line,
        )
        if er_relation and any(symbol in er_relation.group(2) for symbol in ("|", "o", "{", "}")):
            rows.append((
                _diagram_node_label(er_relation.group(1)),
                er_relation.group(4) or er_relation.group(2),
                _diagram_node_label(er_relation.group(3)),
            ))
            continue
        arrow = _MERMAID_ARROW.search(line)
        if arrow:
            left = line[:arrow.start()].strip()
            right = line[arrow.end():].strip()
            label_match = re.match(r"\|([^|]+)\|\s*(.*)", right)
            if label_match:
                relation = label_match.group(1).strip()
                right = label_match.group(2).strip()
            else:
                relation = ""
            if ":" in right:
                right, message = right.split(":", 1)
                relation = relation or message.strip()
            rows.append((
                _diagram_node_label(left),
                relation or arrow.group(0),
                _diagram_node_label(right),
            ))
            continue
        if ":" in line:
            left, detail = line.split(":", 1)
            rows.append((_diagram_node_label(left), "detail", detail.strip()))
        else:
            rows.append(("", "element", line))
    return rows


def _add_diagram_fallback(document, diagram: Diagram, *, include_source: bool):
    document.add_paragraph(
        "Graphical rendering is unavailable; this structured outline preserves the "
        "diagram's elements and relationships."
    )
    rows = _diagram_rows(diagram)
    table = document.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    for cell, label in zip(table.rows[0].cells, ("From / element", "Relationship", "To / detail")):
        cell.text = label
        for run in cell.paragraphs[0].runs:
            run.bold = True
    for source, relation, target in rows[:100]:
        cells = table.add_row().cells
        for cell, value in zip(cells, (source, relation, target)):
            cell.text = value
    if len(rows) > 100:
        document.add_paragraph(f"{len(rows) - 100:,} additional diagram elements omitted.")
    if include_source:
        document.add_paragraph("Mermaid source:")
        source_lines = diagram.mermaid.splitlines()
        shown_lines = source_lines[:200]
        if sum(len(line) for line in shown_lines) > 20_000:
            shown_lines = shown_lines[:100]
        for line in shown_lines:
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.space_after = Pt(0)
            run = paragraph.add_run(line)
            run.font.name = "Consolas"
            run.font.size = Pt(8)
        if len(shown_lines) < len(source_lines):
            document.add_paragraph("Additional Mermaid source lines omitted.")


def create_document(
    result: AnalysisResult, rendered_diagrams: dict[str, bytes | None] | None = None,
) -> bytes:
    if rendered_diagrams is None:
        rendered_diagrams = render_generated_diagrams(result)
    analyzed_code_files = (
        result.analysisScope.analyzedCodeFiles or len(result.codebaseInventory)
    )
    analyzed_supporting = (
        result.analysisScope.analyzedSupportingArtifacts
        or len(result.supportingArtifactInventory)
    )
    batch_count = result.analysisScope.analysisBatchCount or 1
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
    document.add_paragraph(
        f"Analyzed {analyzed_code_files:,} code files and "
        f"{analyzed_supporting:,} supporting artifacts across {batch_count:,} model batches."
    )
    for key in ("includedFiles", "excludedFiles", "unsupportedFiles", "unreadableFiles", "limitations"):
        document.add_paragraph(f"{key}: {_bounded_list_text(getattr(result.analysisScope, key))}")
    document.add_heading("3. Source Artifact Inventory", 1)
    document.add_heading("3.1 Codebase Artifacts", 2)
    inventory_limit = 200
    document.add_paragraph(
        f"Showing {min(len(result.codebaseInventory), inventory_limit):,} of "
        f"{analyzed_code_files:,} analyzed code files."
    )
    for item in result.codebaseInventory[:inventory_limit]:
        document.add_paragraph(
            f"{item.relativePath} [{item.processingStatus}]: {item.purpose}\n"
            f"SHA-256: {item.sha256 or 'Not supplied'}"
        )
    if not result.codebaseInventory:
        document.add_paragraph("No code files were supplied.")
    if analyzed_code_files > inventory_limit:
        document.add_paragraph(
            "The complete code inventory is not printed in this DOCX to keep the report manageable."
        )
    for number, name, kind in (
        ("3.2", "Design Documents", "DESIGN_DOCUMENT"),
        ("3.3", "Jira User Stories", "JIRA_USER_STORY"),
        ("3.4", "Raw Requirements", "RAW_REQUIREMENT"),
    ):
        document.add_heading(f"{number} {name}", 2)
        items = [i for i in result.supportingArtifactInventory if i.sourceType == kind]
        for item in items[:inventory_limit]:
            document.add_paragraph(
                f"{item.sourceName} [{item.processingStatus}] "
                f"{item.externalId or ''}: {item.purpose}"
            )
        if len(items) > inventory_limit:
            document.add_paragraph(
                f"{len(items) - inventory_limit:,} additional inventory entries omitted from the DOCX."
            )
        if not items:
            document.add_paragraph("Not supplied.")
    document.add_heading("4. Application Overview", 1)
    document.add_paragraph(result.applicationOverview.purpose)
    for key, value in result.applicationOverview.model_dump().items():
        if key != "purpose":
            document.add_heading(key, 2)
            for entry in value[:inventory_limit]:
                document.add_paragraph(
                    entry if isinstance(entry, str) else json.dumps(entry, ensure_ascii=False)
                )
            if len(value) > inventory_limit:
                document.add_paragraph(
                    f"{len(value) - inventory_limit:,} additional entries omitted from the DOCX."
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
            document.add_paragraph(evidence_text(requirement.sourceEvidence, limit=10))
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
        generated = [
            (diagram_index, diagram)
            for diagram_index, diagram in enumerate(diagrams)
            if diagram.generated
        ]
        if not generated:
            document.add_paragraph("Not evidenced in the supplied artifacts.")
        for diagram_index, diagram in generated:
            document.add_heading(diagram.title, 3)
            document.add_paragraph(diagram.description)
            reference = f"{key}[{diagram_index}]" if isinstance(value, list) else key
            if reference in rendered_diagrams:
                image = rendered_diagrams[reference]
            else:
                image = render_diagram(diagram)
            if image is None:
                _add_diagram_fallback(document, diagram, include_source=True)
            else:
                document.add_picture(io.BytesIO(image), width=Inches(6))
            document.add_paragraph(evidence_text(diagram.sourceEvidence, limit=10))
    document.add_heading("8. Requirements-to-Source-and-Design Traceability", 1)
    for trace in result.requirementsToDesignTraceability:
        document.add_heading(trace.requirementId, 2)
        document.add_paragraph(trace.requirementSummary)
        document.add_paragraph(
            f"{trace.implementationEvidenceStatus}; {trace.validationStatus}\n"
            f"Diagrams: {', '.join(trace.relevantGeneratedDiagrams)}\n"
            f"Design elements: {', '.join(trace.relevantDesignElements)}"
        )
        document.add_paragraph(evidence_text(trace.sourceEvidence, limit=10))
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


def _business_requirement(text: str) -> str:
    return re.sub(
        r"^(?:the )?(?:system|application) shall\b",
        "The application will",
        text.strip(),
        count=1,
        flags=re.IGNORECASE,
    )


def create_business_document(
    result: AnalysisResult, rendered_diagrams: dict[str, bytes | None] | None = None,
) -> bytes:
    if rendered_diagrams is None:
        rendered_diagrams = render_generated_diagrams(result)
    analyzed_code_files = (
        result.analysisScope.analyzedCodeFiles or len(result.codebaseInventory)
    )
    analyzed_supporting = (
        result.analysisScope.analyzedSupportingArtifacts
        or len(result.supportingArtifactInventory)
    )
    batch_count = result.analysisScope.analysisBatchCount or 1
    document = Document()
    application = result.documentInformation.targetApplication
    document.add_heading(f"{application} - Business Requirements", 0)
    document.add_paragraph("Plain-language companion for business users and stakeholders.")
    document.add_paragraph("Draft for Human Validation")
    document.add_paragraph("Fiserv Internal Use Only")
    document.add_heading("How to use this document", 1)
    document.add_paragraph(
        "This document summarizes the same evidence-based analysis as the developer report, "
        "but leaves out file-level implementation details. Requirement IDs match the technical "
        "report so readers can find more detail when needed."
    )
    document.add_heading("What is changing", 1)
    document.add_paragraph(result.applicationOverview.purpose)
    document.add_heading("Why it matters", 1)
    document.add_paragraph(result.executiveSummary)
    document.add_heading("What was reviewed", 1)
    document.add_paragraph(
        f"The analysis reviewed {analyzed_code_files:,} code files and "
        f"{analyzed_supporting:,} supporting documents across "
        f"{batch_count:,} model batches. The results are a draft "
        "and should be confirmed by business and technical owners."
    )
    document.add_heading("Business requirements", 1)
    for requirement in result.highLevelRequirements:
        document.add_heading(f"{requirement.id}: {requirement.capability}", 2)
        document.add_paragraph(_business_requirement(requirement.requirement))
        if requirement.priority is not None:
            document.add_paragraph(f"Importance: {str(requirement.priority).title()}")
    if not result.highLevelRequirements:
        document.add_paragraph("No functional requirements were evidenced in the supplied materials.")
    document.add_heading("Quality and service expectations", 1)
    for requirement in result.nonFunctionalRequirements:
        document.add_heading(f"{requirement.id}: {requirement.category}", 2)
        document.add_paragraph(_business_requirement(requirement.requirement))
        if requirement.priority is not None:
            document.add_paragraph(f"Importance: {str(requirement.priority).title()}")
    if not result.nonFunctionalRequirements:
        document.add_paragraph("No quality or service expectations were evidenced in the supplied materials.")
    document.add_heading("Process diagrams", 1)
    generated_diagrams = [
        (reference, diagram)
        for reference, diagram in result.umlDiagrams.entries()
        if diagram.generated
    ]
    if not generated_diagrams:
        document.add_paragraph("No diagrams were available in the validated analysis.")
    for reference, diagram in generated_diagrams:
        document.add_heading(diagram.title, 2)
        document.add_paragraph(diagram.description)
        if reference in rendered_diagrams:
            image = rendered_diagrams[reference]
        else:
            image = render_diagram(diagram)
        if image is None:
            _add_diagram_fallback(document, diagram, include_source=False)
        else:
            document.add_picture(io.BytesIO(image), width=Inches(6))
        document.add_paragraph(
            "How to read it: boxes show parts of the process, and connecting lines show "
            "how information or work moves between them."
        )
    open_items = [
        *result.evidenceConflicts,
        *result.assumptions,
        *result.limitations,
    ]
    document.add_heading("Items to confirm", 1)
    if open_items:
        for item in open_items[:200]:
            text = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
            document.add_paragraph(text, style="List Bullet")
        if len(open_items) > 200:
            document.add_paragraph(
                f"{len(open_items) - 200:,} additional items are omitted from this document."
            )
    else:
        document.add_paragraph(
            "No additional open items were generated. Review the requirements before approval."
        )
    glossary = (
        ("APM", "An alternative payment method, such as a digital wallet or payment service."),
        ("Chargeback", "A transaction dispute that can result in money being returned."),
        ("Reversal", "An adjustment that offsets or cancels an earlier chargeback."),
        ("Suspense", "Items set aside for review or a decision before they are finalized."),
        ("Funding", "Money movement or settlement related to a merchant or business."),
        ("Drill-down", "Opening the detailed records that support a summary amount."),
        ("UML", "A set of diagrams used to show processes, relationships, and system parts."),
        ("DGAMS", "A related system named in the source materials; its full name was not provided."),
        ("DBOR", "A related system named in the source materials; its full name was not provided."),
        ("IDFI", "A report term from the source materials; its business definition should be confirmed."),
        ("network code", "A system label used to identify a payment network."),
        ("product code", "A system label used to group or classify transactions."),
        ("rcode", "A system classification used to distinguish transaction types."),
        ("corp file", "A data file published for use by another process or system."),
    )
    analysis_text = "\n".join([
        result.executiveSummary,
        result.applicationOverview.purpose,
        *(requirement.requirement for requirement in (
            *result.highLevelRequirements, *result.nonFunctionalRequirements
        )),
        *(diagram.title + " " + diagram.description
          for _, diagram in generated_diagrams),
    ]).casefold()
    relevant_terms = [
        (term, definition) for term, definition in glossary
        if term.casefold() in analysis_text
    ]
    if relevant_terms:
        document.add_heading("Key terms", 1)
        for term, definition in relevant_terms:
            paragraph = document.add_paragraph(style="List Bullet")
            paragraph.add_run(f"{term}: ").bold = True
            paragraph.add_run(definition)
    document.add_heading("Review and approval", 1)
    document.add_paragraph(result.validationStatement)
    document.add_paragraph("Business reviewer: ____________________  Date: ____________________")
    stream = io.BytesIO()
    document.save(stream)
    return stream.getvalue()