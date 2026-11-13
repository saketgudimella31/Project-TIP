import io
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from docx import Document
from docx.shared import Inches

from .models import AnalysisResult, Diagram, Evidence
from .validation import validate_mermaid

_CLASS_DIAGRAM_HEADER = re.compile(r"^\s*classDiagram\b", re.IGNORECASE)
_CLASS_DECLARATION_WITH_MEMBERS = re.compile(r"^(\s*class\s+[^{}]+?)\s*\{(.*)$")
_CLASS_RELATION_OPERATOR = re.compile(
    r"<\|--|--\|>|<\|\.\.|\.{2}\|>|<-->|<--|-->|<\.\.|\.\.>|\*--|o--|--|\.\."
)
_FLOWCHART_HEADER = re.compile(
    r"^\s*(?:flowchart|graph)\s+(?:TB|TD|BT|RL|LR)\b",
    re.IGNORECASE,
)

_HTML_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)
_HTML_TAG = re.compile(r"</?[A-Za-z][^>]*>")
_MERMAID_INIT_DIRECTIVE = re.compile(r"^\s*%%\{.*?\}%%\s*$")
_FLOWCHART_EDGE_LABEL = re.compile(r"(\S)\s*\|[^|\r\n]*\|\s*(?=\S)")


@dataclass(frozen=True)
class DocumentBundle:
    technical: bytes
    business: bytes


def _renderer_paths() -> tuple[Path, Path]:
    default_frontend = Path(__file__).resolve().parents[2] / "frontend"
    frontend = Path(os.environ.get("TIP_FRONTEND_DIR") or default_frontend).resolve()
    return frontend, Path(__file__).with_name("render-mermaid.mjs")


def mermaid_renderer_issue() -> str | None:
    frontend, script = _renderer_paths()
    if not shutil.which("node"):
        return "Node.js 22.12+ is unavailable on the backend PATH."
    if not script.is_file():
        return (
            "The TIP Mermaid renderer script is missing from backend/tip. "
            "Sync the current backend files and reinstall the backend package."
        )
    packages = {
        "mermaid": frontend / "node_modules" / "mermaid" / "package.json",
        "jsdom": frontend / "node_modules" / "jsdom" / "package.json",
        "@resvg/resvg-js": frontend / "node_modules" / "@resvg" / "resvg-js" / "package.json",
    }
    missing = [name for name, path in packages.items() if not path.is_file()]
    if missing:
        return (
            "Mermaid renderer dependencies are missing from frontend/node_modules "
            f"({', '.join(missing)}); run npm install in frontend and restart TIP."
        )
    return None


def mermaid_renderer_configured() -> bool:
    return mermaid_renderer_issue() is None


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


def _class_diagram_render_source(source: str) -> tuple[str, bool, bool]:
    if not _CLASS_DIAGRAM_HEADER.match(source):
        return source, False, False

    lines = []
    member_details_omitted = False
    captions_omitted = False
    member_depth = 0
    for line in source.splitlines():
        if member_depth:
            member_depth += line.count("{") - line.count("}")
            member_text = line.split("}", 1)[0].strip()
            if member_text:
                member_details_omitted = True
            continue

        class_declaration = _CLASS_DECLARATION_WITH_MEMBERS.match(line)
        if class_declaration:
            declaration, body = class_declaration.groups()
            closing = body.find("}")
            if closing >= 0:
                member_details_omitted |= bool(body[:closing].strip())
            else:
                member_details_omitted |= bool(body.strip())
                member_depth = 1 + body.count("{") - body.count("}")
            lines.append(declaration.rstrip())
            continue

        if line.lstrip().startswith("%%"):
            lines.append(line)
            continue
        operator = _CLASS_RELATION_OPERATOR.search(line)
        if operator:
            label = re.search(r"\s+:\s*", line[operator.end():])
            if label:
                line = line[:operator.end() + label.start()].rstrip()
                captions_omitted = True
        lines.append(line)
    if member_depth:
        return source, False, False
    return "\n".join(lines), member_details_omitted, captions_omitted

def _safe_mermaid_render_source(source: str) -> tuple[str, bool]:
    """
    Create a conservative Mermaid source for the local PNG renderer.

    The original Mermaid source remains unchanged in the analysis result.
    This version is used only when the native SVG-to-PNG renderer fails.
    """
    sanitized = source
    changed = False

    # Mermaid initialization directives can introduce renderer-specific
    # fonts, themes, or layout settings.
    lines = []
    for line in sanitized.splitlines():
        if _MERMAID_INIT_DIRECTIVE.match(line):
            changed = True
            continue
        lines.append(line)
    sanitized = "\n".join(lines)

    # resvg can fail on some HTML-based Mermaid labels.
    updated = _HTML_BREAK.sub(" ", sanitized)
    changed |= updated != sanitized
    sanitized = updated

    updated = _HTML_TAG.sub("", sanitized)
    changed |= updated != sanitized
    sanitized = updated

    # Remove null/control characters while retaining newline and tab.
    updated = "".join(
        character
        for character in sanitized
        if character in "\n\t" or ord(character) >= 32
    )
    changed |= updated != sanitized
    sanitized = updated

    # Labeled flowchart edges can produce SVG text geometry that triggers
    # native resvg failures. Keep the connection but omit its caption.
    if _FLOWCHART_HEADER.match(sanitized):
        updated = _FLOWCHART_EDGE_LABEL.sub(r"\1 ", sanitized)
        changed |= updated != sanitized
        sanitized = updated

        # Mermaid flowchart nodes cannot safely contain unescaped double quotes
        # inside bracket labels. Model output such as:
        #   B2[Print "codebase-rag version <version>"]
        # is parsed as STR and fails before PNG rendering. For the renderer-only
        # compatibility copy, replace quotes and angle brackets in node labels
        # while preserving the original Mermaid in AnalysisResult.
        safe_flow_lines = []
        node_pattern = re.compile(r'(?P<prefix>\b[A-Za-z_][\w-]*\s*\[)(?P<label>.*?)(?P<suffix>\])')
        for line in sanitized.splitlines():
            def clean_node(match):
                label = match.group("label")
                cleaned = (label.replace('"', "'")
                           .replace("<", "(")
                           .replace(">", ")"))
                return match.group("prefix") + cleaned + match.group("suffix")
            updated_line = node_pattern.sub(clean_node, line)
            changed |= updated_line != line
            safe_flow_lines.append(updated_line)
        sanitized = "\n".join(safe_flow_lines)

    # Avoid extreme SVG geometry caused by unusually long generated lines.
    safe_lines = []
    for line in sanitized.splitlines():
        if len(line) > 1000:
            safe_lines.append(line[:1000])
            changed = True
        else:
            safe_lines.append(line)

    return "\n".join(safe_lines).strip(), changed


def render_diagram(diagram: Diagram) -> bytes:
    validate_mermaid(diagram.mermaid)
    frontend, script = _renderer_paths()
    issue = mermaid_renderer_issue()
    if issue:
        raise ValueError(f"Local Mermaid rendering is unavailable: {issue}")
    node = shutil.which("node")
    if not node or not script.is_file():
        raise ValueError("Local Mermaid rendering became unavailable during analysis.")
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
        
        details = [
            line.strip()
            for line in process.stderr.decode("utf-8", "replace").splitlines()
            if line.strip() and not line.strip().startswith("note:")
        ]

        detail = (
            f": {'; '.join(details)[:2000]}"
            if details
            else ""
        )

        
        raise ValueError(f"Local Mermaid rendering failed for {diagram.title}{detail}")
    if len(image) > 10_000_000:
        raise ValueError("Rendered Mermaid image exceeds the size limit")
    return image


def render_generated_diagrams(result: AnalysisResult) -> dict[str, bytes]:
    rendered = {}

    for reference, original_diagram in result.umlDiagrams.entries():
        if not original_diagram.generated:
            continue

        validate_mermaid(original_diagram.mermaid)

        render_source, members_omitted, captions_omitted = (
            _class_diagram_render_source(original_diagram.mermaid)
        )

        diagram = original_diagram
        if render_source != original_diagram.mermaid:
            diagram = original_diagram.model_copy(
                update={"mermaid": render_source}
            )

        if members_omitted or captions_omitted:
            omitted_parts = []

            if members_omitted:
                omitted_parts.append("class member details")

            if captions_omitted:
                omitted_parts.append("relationship captions")

            omitted = (
                " and ".join(omitted_parts)
                if len(omitted_parts) == 2
                else omitted_parts[0]
            )

            warning = (
                f"{omitted.capitalize()} were omitted from rendered "
                "class-diagram images because of a local SVG renderer "
                "compatibility issue; the original Mermaid source remains "
                "available in the analysis data."
            )

            if warning not in result.warnings:
                result.warnings.append(warning)

        try:
            rendered[reference] = render_diagram(diagram)
            continue
        except ValueError as first_error:
            error_text = str(first_error)

            native_renderer_failure = any(
                marker in error_text
                for marker in (
                    "resvg",
                    "panicked at",
                    "Option::unwrap()",
                    "Local Mermaid rendering failed",
                )
            )

            if not native_renderer_failure:
                raise

            safe_source, changed = _safe_mermaid_render_source(
                diagram.mermaid
            )

            if not changed or safe_source == diagram.mermaid:
                raise

            validate_mermaid(safe_source)

            safe_diagram = diagram.model_copy(
                update={"mermaid": safe_source}
            )

            try:
                rendered[reference] = render_diagram(safe_diagram)
                
            except ValueError as retry_error:
                    warning = (
                        f"The UML diagram '{original_diagram.title}' "
                        "could not be converted to a PNG by the local renderer. "
                        "The diagram image was omitted, but the original Mermaid "
                        "source remains available in the analysis."
                    )

                    if warning not in result.warnings:
                        result.warnings.append(warning)

                    if warning not in result.limitations:
                        result.limitations.append(warning)

                    if warning not in result.analysisScope.limitations:
                        result.analysisScope.limitations.append(
                            warning
                        )

                    continue
    return rendered

def ensure_source_component_diagram(result: AnalysisResult) -> bool:
    if any(diagram.generated for _, diagram in result.umlDiagrams.entries()):
        return False
    files = sorted({
        item.relativePath
        for item in result.codebaseInventory
        if item.processingStatus == "ANALYZED" and item.relativePath
    })
    if not files:
        return False

    shown_files = files[:40]
    nodes = []
    evidence = []
    for index, path in enumerate(shown_files):
        label = path if len(path) <= 100 else f"...{path[-97:]}"
        label = re.sub(r"[^A-Za-z0-9._/-]+", "_", label)
        nodes.extend([
            f'  class file_{index}["{label}"]',
            f"  <<component>> file_{index}",
        ])
        evidence.append(Evidence(
            sourceType="CODE", sourceName=path, filePath=path, symbol=None,
            externalId=None, section=None, worksheet=None, row=None,
            lineStart=None, lineEnd=None,
            evidenceDescription="Analyzed source file included in this requirements run.",
        ))

    mermaid = "\n".join([
        "classDiagram",
        *nodes,
    ])
    validate_mermaid(mermaid)
    inventory_text = (
        f"the first {len(shown_files):,} of {len(files):,} paths retained "
        "in the validated inventory"
        if len(files) > len(shown_files)
        else f"all {len(files):,} paths retained in the validated inventory"
    )
    analyzed_files = max(result.analysisScope.analyzedCodeFiles, len(files))
    file_label = "file" if analyzed_files == 1 else "files"
    result.umlDiagrams.componentDiagram = Diagram(
        generated=True,
        title="Source Component Diagram",
        description=(
            f"Evidence-backed source component view showing {inventory_text}. "
            f"The analysis covered {analyzed_files:,} eligible code {file_label}. "
            "Each UML component represents an analyzed source file. No dependency links are drawn "
            "because no validated relationship diagram was available."
        ),
        mermaid=mermaid,
        sourceEvidence=evidence,
        reason="",
    )
    result.warnings.append(
        "No validated UML diagram was available; generated a source component diagram "
        "without inferring dependency relationships."
    )
    return True


def create_document(
    result: AnalysisResult, rendered_diagrams: dict[str, bytes] | None = None,
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
            
            
            image = rendered_diagrams.get(reference)

            if image is not None:
                document.add_picture(
                    io.BytesIO(image),
                    width=Inches(6),
                )
            else:
                document.add_paragraph(
                    "The UML image could not be rendered locally. "
                    "The validated Mermaid source is included below."
                )

                document.add_paragraph(
                    diagram.mermaid
                )

            document.add_paragraph(
                evidence_text(
                    diagram.sourceEvidence,
                    limit=10,
                )
            )
            

            
            
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
    text = re.sub(
        r"\b(?:GET|POST|PUT|PATCH|DELETE)\s+[/\w{}.-]+",
        "a service request",
        text.strip(),
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(?:[\w.-]+/)*[\w.-]+\.(?:py|js|jsx|ts|tsx|java|go|cs|sql)"
        r"(?:\s+lines?\s+\d+(?:-\d+)?)?",
        "the implementation",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\bshall\b", "will", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _business_text(value, limit: int = 500) -> str:
    if isinstance(value, dict):
        parts = [
            str(value[key]).strip()
            for key in (
                "name", "title", "summary", "description", "purpose", "role",
                "trigger", "outcome", "responsibility", "module", "interface",
            )
            if isinstance(value.get(key), str) and value[key].strip()
        ]
        for key in ("steps", "activities", "inputs", "outputs", "participants", "systems"):
            entries = value.get(key)
            if isinstance(entries, list):
                parts.extend(
                    _business_text(entry, limit=120)
                    for entry in entries if str(entry).strip()
                )
        text = " — ".join(parts)
    elif isinstance(value, list):
        text = " → ".join(str(item).strip() for item in value if str(item).strip())
    else:
        text = str(value or "").strip()
    text = _business_requirement(text)
    if len(text) > limit:
        return text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:") + "..."
    return text or "Not supplied in the analyzed artifacts."


def _business_evidence_classification(requirement) -> str:
    origins = set(requirement.requirementOrigin)
    if origins & {"RAW_REQUIREMENT", "JIRA_USER_STORY"}:
        classification = "Explicit business-source evidence"
        if "CODE" in origins:
            classification += " with implementation evidence"
    elif "DESIGN_DOCUMENT" in origins:
        classification = "Design evidence; confirm business intent"
    elif "CODE" in origins:
        classification = "Implementation-derived; not approved business intent"
    else:
        classification = "Evidence source requires review"
    evidence_status = (
        "evidence supported" if requirement.evidenceStatus == "VERIFIED"
        else "partial evidence"
    )
    classification += f"; {evidence_status}"
    return classification


def _business_implementation_status(requirement) -> str:
    return {
        "IMPLEMENTATION_EVIDENCED": "Observed in supplied implementation",
        "IMPLEMENTATION_PARTIALLY_EVIDENCED": "Partially observed in supplied implementation",
        "IMPLEMENTATION_NOT_EVIDENCED": "Not evidenced in supplied implementation",
        "NOT_APPLICABLE": "Implementation evidence not applicable",
    }[requirement.implementationEvidenceStatus]


def _business_evidence_sources(requirement) -> str:
    labels = {
        "CODE": "Observed application behavior",
        "DESIGN_DOCUMENT": "Design document",
        "JIRA_USER_STORY": "User story",
        "RAW_REQUIREMENT": "Business requirement",
    }
    return ", ".join(
        dict.fromkeys(labels.get(origin, origin) for origin in requirement.requirementOrigin)
    )


def _business_theme(requirement, *, functional: bool) -> str:
    if not functional:
        return "Service quality and operational controls"
    text = f"{requirement.capability} {requirement.requirement}".casefold()
    themes = (
        ("Access and data protection", (
            "access", "authoriz", "authenticat", "role", "permission", "security", "privacy",
        )),
        ("Payments, funding and reconciliation", (
            "payment", "chargeback", "reversal", "fund", "settle", "reconcil",
        )),
        ("Reporting and visibility", (
            "report", "display", "show", "view", "summary", "inventory", "dashboard",
        )),
        ("Data quality and separation", (
            "data", "record", "duplicate", "double count", "separat", "exclude", "filter",
            "validat",
        )),
        ("Integration and information exchange", (
            "integration", "interface", "api", "feed", "publish", "downstream", "mcp", "sse",
        )),
        ("Workflow and operations", (
            "workflow", "process", "task", "lifecycle", "queue", "initialize", "shutdown",
            "monitor", "audit", "error", "timeout", "log", "performance", "availability",
        )),
    )
    for theme, terms in themes:
        if any(term in text for term in terms):
            return theme
    return "Core application capabilities"


def _business_requirement_groups(result: AnalysisResult) -> dict[str, list]:
    groups: dict[str, list] = {}
    for functional, requirements in (
        (True, result.highLevelRequirements),
        (False, result.nonFunctionalRequirements),
    ):
        for requirement in requirements:
            theme = _business_theme(requirement, functional=functional)
            groups.setdefault(theme, []).append(requirement)
    return groups


def _add_business_table(document, headers: tuple[str, ...], rows: list[tuple[str, ...]]):
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for cell, label in zip(table.rows[0].cells, headers):
        cell.text = label
        for run in cell.paragraphs[0].runs:
            run.bold = True
    for row in rows:
        cells = table.add_row().cells
        for cell, value in zip(cells, row):
            cell.text = value
    return table


def create_business_document(
    result: AnalysisResult, rendered_diagrams: dict[str, bytes] | None = None,
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
    groups = _business_requirement_groups(result)
    requirements = [
        *result.highLevelRequirements, *result.nonFunctionalRequirements,
    ]
    generated_diagrams = [
        (reference, diagram)
        for reference, diagram in result.umlDiagrams.entries()
        if diagram.generated
    ]
    inputs = result.inputContext.supportingInputs
    business_sources_provided = (
        inputs.jiraUserStoriesProvided or inputs.rawRequirementsProvided
    )
    purpose = _business_text(result.applicationOverview.purpose, limit=700)

    document.add_heading("Functional Requirements Specification (FRS)", 0)
    document.add_paragraph(application)
    document.add_paragraph("Business-facing companion to the evidence-derived technical report")
    document.add_paragraph("Fiserv Internal Use Only")
    _add_business_table(document, ("Document Information", "Value"), [
        ("Initiative / analysis title", _business_text(result.documentTitle, 180)),
        ("Application", application),
        ("Document Type", "Functional Requirements Specification (FRS)"),
        ("Business Area", "Not supplied in the analyzed artifacts"),
        ("Target Release", "Not supplied in the analyzed artifacts"),
        ("Intended Audience", "Product, business, operations, application, technology, and QA/UAT reviewers"),
        ("Document Owner", "Not supplied; assign an accountable owner"),
        ("Version", result.documentInformation.version),
        ("Date", date.today().isoformat()),
        ("Status", result.documentInformation.status),
        ("Classification", result.documentInformation.classification),
    ])
    document.add_paragraph(
        "This stakeholder-focused companion is derived from the same validated analysis as "
        "the technical report. It summarizes evidence in plain language; it does not create "
        "business intent, priorities, release decisions, or approval."
    )
    document.add_heading("Document Use and Audience", 1)
    document.add_paragraph(
        "Use this FRS to review business-facing requirements, acceptance criteria, evidence "
        "classifications, and open decisions. It is a draft for human validation, not an approved "
        "business baseline or release commitment."
    )
    _add_business_table(document, ("Audience", "Review responsibility", "Named reviewer"), [
        ("Product Owner", "Confirm business need, scope, and priority.", "To assign"),
        ("Business / Operations Owner", "Validate business rules and process impact.", "To assign"),
        ("Application Owner", "Confirm application scope and operational context.", "To assign"),
        ("Technology Lead", "Review implementation evidence and technical dependencies.", "To assign"),
        ("QA / UAT Lead", "Confirm measurable acceptance criteria and test ownership.", "To assign"),
    ])
    document.add_page_break()

    document.add_heading("1. Executive Summary", 1)
    if business_sources_provided:
        source_basis = (
            "User-story or raw-requirement material was included, alongside implementation "
            "evidence where available. The business owner must confirm that the synthesized "
            "statements preserve the source intent."
        )
    else:
        source_basis = (
            "No Jira user stories or raw business requirements were supplied. The requirements "
            "are therefore derived primarily from observed implementation behavior and must not "
            "be treated as approved business needs."
        )
    document.add_paragraph(
        f"{source_basis} The analysis reviewed {analyzed_code_files:,} code files and "
        f"{analyzed_supporting:,} supporting artifacts across {batch_count:,} bounded model batches. "
        "The full technical report contains detailed evidence, implementation status, and traceability."
    )
    summary_need = (
        "Confirm that the supplied business requirements and user stories accurately describe "
        "the intended need."
        if business_sources_provided else
        "Not stated directly; confirm the business problem and need with the Product Owner."
    )
    current_challenge = (
        "A business baseline or operational impact was not explicitly identified."
        if not business_sources_provided else
        "The source materials require stakeholder review to confirm the current-state baseline."
    )
    _add_business_table(document, ("Item", "Business summary"), [
        ("Business need", summary_need),
        ("Current challenge", current_challenge),
        ("Proposed change", "This report organizes evidence-derived capabilities for business review; "
         "a target-state change must be confirmed by the owners."),
        ("Primary users", "Not identified in the analyzed artifacts; confirm the affected business roles."),
        ("Expected value", "No quantified business value was supplied; agree measurable outcomes before approval."),
        ("Decision required", "Confirm business scope, priorities, acceptance approach, dependencies, and approval."),
    ])

    document.add_heading("2. Business Problem and Objectives", 1)
    if business_sources_provided:
        document.add_paragraph(
            "The supplied requirements or user stories provide business context, but the analysis "
            "does not establish an approved baseline or quantify the impact of the current problem. "
            "Confirm both with the business owner."
        )
    else:
        document.add_paragraph(
            "No business problem statement was supplied. Source code can show what the application "
            "currently does, but cannot by itself establish user pain, business impact, or the reason "
            "for a proposed change."
        )
    document.add_paragraph(f"Observed application purpose in the supplied evidence: {purpose}")

    document.add_heading("2.1 Business Objectives", 2)
    for objective in (
        "Confirm the business problem, intended users, and expected outcomes.",
        "Validate evidence-derived requirements against approved business intent.",
        "Agree priorities, measurable acceptance criteria, and UAT ownership.",
        "Resolve evidence gaps and record any decisions required before release.",
    ):
        document.add_paragraph(objective, style="List Bullet")
    document.add_paragraph(
        "These are review objectives for this draft. Product-specific business objectives and "
        "benefit targets were not supplied unless explicitly stated in the analyzed requirements."
    )

    document.add_heading("3. Scope", 1)
    _add_business_table(document, ("In scope for this draft", "Not established / pending confirmation"), [
        (
            f"Evidence-derived capabilities from {analyzed_code_files:,} analyzed code files "
            f"and {analyzed_supporting:,} supporting artifacts.",
            "Business area, initiative owner, and target release.",
        ),
        (
            f"{len(result.highLevelRequirements):,} functional and "
            f"{len(result.nonFunctionalRequirements):,} quality/service requirements, grouped by theme.",
            "Final business priorities, user roles, and operational baseline.",
        ),
        (
            (
                f"{len(generated_diagrams):,} validated UML diagram(s), "
                "rendered as PNG images in both reports."
                if generated_diagrams
                else "No UML diagrams were generated from the supplied evidence."
            ),
            "Unprovided business rules, downstream dependencies, and release decisions.",
        ),
        (
            "Evidence gaps, conflicts, and approval questions surfaced by the analysis.",
            "Any behavior or requirement not supported by the selected readable artifacts.",
        ),
    ])

    document.add_heading("3.1 Current State and Future State", 2)
    document.add_paragraph(
        "The analysis is based on implementation and supplied evidence. It does not assume that "
        "observed behavior is the desired future state."
    )
    _add_business_table(document, ("Area", "Evidence-based view"), [
        ("Current state", purpose),
        ("Future state", "Not explicitly defined in the analyzed artifacts; business owners must confirm it."),
        ("Business impact", "Not quantified in the supplied materials; establish a baseline and target."),
        ("Existing behavior to preserve", "Not established by source evidence alone; confirm regression scope."),
    ])

    document.add_heading("4. Business Capabilities, Processes, Modules, and Interfaces", 1)
    document.add_paragraph(
        "The themes below group the derived requirements for review. They describe evidence in the "
        "selected source scope and are not an approved change list."
    )
    if not groups:
        document.add_paragraph("No business capabilities were evidenced in the supplied artifacts.")
    for theme, items in groups.items():
        document.add_heading(f"{theme} ({len(items):,})", 2)
        for requirement in items[:4]:
            label = getattr(requirement, "capability", None) or getattr(
                requirement, "category", "Requirement",
            )
            status = (
                "Verified evidence" if requirement.evidenceStatus == "VERIFIED"
                else "Partial evidence"
            )
            paragraph = document.add_paragraph(style="List Bullet")
            paragraph.add_run(f"{requirement.id} — {label}: ").bold = True
            paragraph.add_run(_business_requirement(requirement.requirement))
            paragraph.add_run(f" [{status}]")
        if len(items) > 4:
            document.add_paragraph(
                f"{len(items) - 4:,} related requirements are summarized in the technical report."
            )

    document.add_heading("4.1 Business Process Overview", 2)
    flows = result.applicationOverview.functionalFlows
    if flows:
        for flow in flows[:10]:
            document.add_paragraph(_business_text(flow, 700), style="List Bullet")
        if len(flows) > 10:
            document.add_paragraph(
                f"{len(flows) - 10:,} additional flow descriptions are omitted from this summary."
            )
    else:
        document.add_paragraph(
            "No end-to-end business process was supplied. The UML diagrams below show only "
            "relationships or interactions supported by the analyzed implementation."
        )
    document.add_heading("4.2 Modules, Components, and Interfaces", 2)
    document.add_paragraph(
        "The following items summarize the analyzed application view. They describe observed "
        "evidence, not a confirmed target operating model."
    )
    for title, items in (
        ("Modules", result.applicationOverview.modules),
        ("Components", result.applicationOverview.components),
        ("Interfaces", result.applicationOverview.interfaces),
        ("Dependencies", result.applicationOverview.dependencies),
    ):
        document.add_heading(title, 3)
        descriptions = [
            _business_text(item, 500)
            for item in items
            if item is not None and str(item).strip()
        ]
        if descriptions:
            for description in descriptions[:50]:
                document.add_paragraph(description, style="List Bullet")
            if len(descriptions) > 50:
                document.add_paragraph(
                    f"{len(descriptions) - 50:,} additional items are listed in the technical report."
                )
        else:
            document.add_paragraph("Not identified in the analyzed artifacts.")
    document.add_heading("4.3 UML Process and System Diagrams", 2)
    if not generated_diagrams:
        document.add_paragraph(
            "No UML diagrams could be generated from the validated evidence without speculation."
        )
    for reference, diagram in generated_diagrams:
        document.add_heading(diagram.title, 2)
        document.add_paragraph(_business_text(diagram.description, 700))
        
        
        
        image = rendered_diagrams.get(reference)

        if image is not None:
            document.add_picture(
                io.BytesIO(image),
                width=Inches(6),
            )
        else:
            document.add_paragraph(
                "The diagram image could not be rendered locally. "
                "The technical requirements document contains the "
                "validated diagram definition for technical review."
            )
        

    document.add_heading("5. Business Rules and Policy Considerations", 1)
    candidate_rules = [
        item for item in requirements
        if re.search(
            r"\b(only|must not|will not|exclude|prevent|separate|distinct|"
            r"not include|shall not|prohibit)\b",
            item.requirement,
            flags=re.IGNORECASE,
        )
    ]
    if candidate_rules:
        document.add_paragraph(
            "Candidate rules inferred from requirement statements; business owners must confirm "
            "that they are intentional policy rather than implementation detail."
        )
        for requirement in candidate_rules[:20]:
            document.add_paragraph(
                f"{requirement.id}: {_business_requirement(requirement.requirement)}",
                style="List Bullet",
            )
        if len(candidate_rules) > 20:
            document.add_paragraph(
                f"{len(candidate_rules) - 20:,} additional candidate rules are available in the technical report."
            )
    else:
        document.add_paragraph(
            "No explicit business rules were identified in the supplied evidence; confirm the "
            "applicable rules with the business owner."
        )

    document.add_heading("6. Audience, Stakeholders, and Responsibilities", 1)
    _add_business_table(document, ("Stakeholder", "Responsibility", "Name / status"), [
        ("Product Owner", "Confirms business scope, priorities, and acceptance.", "To assign"),
        ("Business / Operations Owner", "Validates business rules, process impact, and usability.", "To assign"),
        ("Application Owner", "Confirms application scope and operational readiness.", "To assign"),
        ("Technology Lead", "Validates technical feasibility and solution implications.", "To assign"),
        ("QA / UAT Lead", "Agrees test scenarios and records validation results.", "To assign"),
        ("Data / Integration Owners", "Confirms source data and downstream dependencies, if applicable.", "To assign"),
        ("Release Management", "Confirms release scope and deployment decision.", "To assign"),
    ])

    document.add_heading("7. Benefits and Risks", 1)
    document.add_paragraph(
        "Potential benefits of this evidence-based review—not measured product benefits—include:"
    )
    for benefit in (
        "A shorter stakeholder view of capabilities and requirements.",
        "Clearer identification of evidence gaps and business decisions.",
        "A shared basis for reviewing process diagrams and acceptance criteria.",
        "Links between business-facing summaries and the detailed technical report.",
    ):
        document.add_paragraph(benefit, style="List Bullet")
    document.add_paragraph(
        "The analyzed artifacts provide no quantified operational, financial, or customer-impact "
        "baseline. Those benefits and measures must be supplied by business owners."
    )

    document.add_heading("7.1 Business Risks and Controls", 2)
    risk_rows = [
        (
            "Business intent is not explicit in implementation-only evidence.",
            "Observed behavior may be mistaken for an approved business need.",
            "Confirm the business problem, objectives, and scope with the Product Owner.",
        ),
        (
            "Some evidence may be partial, missing, or conflicting.",
            "Requirements or diagrams may not represent the complete process.",
            "Review the technical report's limitations and resolve open evidence items.",
        ),
        (
            "Priorities, owners, and target release are not established here.",
            "Delivery scope and sequencing may not match business expectations.",
            "Assign owners and approve priority and release scope before commitment.",
        ),
        (
            "Acceptance thresholds and UAT data may be undefined.",
            "Readiness cannot be measured consistently.",
            "Agree measurable pass/fail criteria and representative test data.",
        ),
    ]
    if result.evidenceConflicts:
        risk_rows.append((
            f"{len(result.evidenceConflicts):,} evidence conflict(s) were identified.",
            "Different interpretations could lead to inconsistent outcomes.",
            "Have the accountable business and technical owners resolve each conflict.",
        ))
    _add_business_table(document, ("Risk / open condition", "Potential business impact", "Proposed control"), risk_rows)

    document.add_heading("8. Success Measures", 1)
    for measure in (
        "Business owners approve or update the problem statement, scope, and intended outcomes.",
        "Every requirement is reviewed and assigned an owner and priority.",
        "Acceptance criteria are measurable and mapped to representative QA/UAT scenarios.",
        "Evidence gaps and conflicts are resolved or explicitly accepted.",
        "Stakeholders review the UML diagrams and confirm they reflect the intended process.",
        "Business approval is recorded before the agreed release decision.",
    ):
        document.add_paragraph(measure, style="List Bullet")
    document.add_paragraph(
        "Numeric targets, baselines, and service levels were not supplied and should be agreed "
        "before using these measures for release approval."
    )

    document.add_heading("9. Acceptance Criteria", 1)
    for requirement in requirements:
        criterion = _business_text(requirement.acceptanceCriterion, 500)
        document.add_paragraph(
            f"{requirement.id}: {criterion}",
            style="List Bullet",
        )
    if not requirements:
        document.add_paragraph(
            "No acceptance criteria were evidenced. Business and QA owners must define them."
        )

    open_items = [
        *result.evidenceConflicts, *result.assumptions, *result.limitations,
    ]
    document.add_heading("10. Dependencies and Open Decisions", 1)
    source_status = (
        "Requirements or user stories were supplied; confirm whether additional business context is needed."
        if business_sources_provided else
        "Not supplied; provide an approved source or confirm with the business owner."
    )
    _add_business_table(document, ("Item", "Status", "Owner to confirm", "Decision needed"), [
        ("Business problem and current-state baseline", source_status, "Product Owner", "Confirm problem and impact."),
        ("Future-state outcomes and business measures", "Not established in the analyzed artifacts.", "Business Owner", "Set outcomes and measurable targets."),
        ("Business area, document owner, and target release", "Not supplied in the analyzed artifacts.", "Product Owner / Release Manager", "Assign accountable owners and release."),
        ("Business rules, priorities, and user roles", "To be confirmed against approved policy.", "Business / Application Owner", "Approve rules, priorities, and access roles."),
        ("QA/UAT scenarios and representative data", "Not supplied in the analyzed artifacts.", "QA / Operations", "Agree test data and acceptance thresholds."),
        ("Data and downstream dependencies", "Confirm against the technical report and source owners.", "Data / Integration Owners", "Approve required inputs and outputs."),
        ("Evidence gaps and conflicts", f"{len(open_items):,} item(s) require review.", "Business and Technology Leads", "Resolve or record accepted limitations."),
        ("Business sign-off", "Pending human validation.", "Product Owner / Business Owner", "Approve, reject, or request changes."),
    ])
    detailed_open_items = [
        ("Evidence conflict", item, "Business and Technology Leads")
        for item in result.evidenceConflicts
    ]
    detailed_open_items.extend(
        ("Assumption", item, "Product Owner / Business Owner")
        for item in result.assumptions
    )
    detailed_open_items.extend(
        ("Analysis limitation", item, "Product Owner / Technology Lead")
        for item in result.limitations
    )
    detailed_open_items.extend(
        ("Analysis warning", item, "Technology Lead")
        for item in result.warnings
    )
    detailed_open_items.extend(
        ("Requirement review", f"{item.id}: {item.validationNotes}", "Requirement Owner")
        for item in requirements if item.validationNotes
    )
    detailed_open_items.extend(
        ("Acceptance criteria TBD", item.id, "Business Owner / QA Lead")
        for item in requirements if not item.acceptanceCriterion.strip()
    )
    document.add_heading("Open Items from Evidence Review", 2)
    if detailed_open_items:
        _add_business_table(
            document, ("Type", "Open item", "Owner to confirm"),
            [
                (kind, _business_text(item, 700), owner)
                for kind, item, owner in detailed_open_items
            ],
        )
    else:
        document.add_paragraph("No additional evidence-derived open items were reported.")

    document.add_heading("11. Requirements Matrix and Details", 1)
    summary_rows = []
    for theme, items in groups.items():
        labels = list(dict.fromkeys(
            getattr(item, "capability", None) or getattr(item, "category", "Requirement")
            for item in items
        ))
        priorities = list(dict.fromkeys(
            str(item.priority) for item in items if item.priority is not None
        ))
        outcome = ", ".join(labels[:3])
        if len(labels) > 3:
            outcome += f", and {len(labels) - 3:,} additional capability label(s)"
        summary_rows.append((
            theme, _business_text(outcome, 220), str(len(items)),
            ", ".join(priorities) if priorities else "Not supplied",
        ))
    if summary_rows:
        _add_business_table(
            document, ("Theme", "Business outcome to validate", "Requirements", "Priority"),
            summary_rows,
        )
    else:
        document.add_paragraph("No requirements were available to summarize.")

    typed_requirements = [
        ("Functional", item) for item in result.highLevelRequirements
    ] + [
        ("Quality / service", item) for item in result.nonFunctionalRequirements
    ]
    document.add_heading("11.1 Requirements Matrix", 2)
    document.add_paragraph(
        "The matrix includes every requirement returned by the validated analysis. "
        "Evidence status is not business approval; priorities are shown only when supplied."
    )
    matrix_rows = []
    for kind, requirement in typed_requirements:
        label = getattr(requirement, "capability", None) or getattr(
            requirement, "category", "Requirement",
        )
        matrix_rows.append((
            requirement.id,
            f"{kind}: {_business_text(label, 140)}",
            _business_requirement(requirement.requirement),
            str(requirement.priority) if requirement.priority is not None else "Not supplied",
            _business_evidence_classification(requirement),
        ))
    if matrix_rows:
        _add_business_table(
            document,
            ("ID", "Type / capability", "Business-facing requirement", "Priority", "Evidence classification"),
            matrix_rows,
        )
    else:
        document.add_paragraph("No requirements were available for the matrix.")

    document.add_heading("11.2 Detailed Requirements", 2)
    for kind, requirement in typed_requirements:
        label = getattr(requirement, "capability", None) or getattr(
            requirement, "category", "Requirement",
        )
        document.add_heading(
            f"{requirement.id} — {_business_text(label, 160)}", 3,
        )
        document.add_paragraph(
            f"Requirement: {_business_requirement(requirement.requirement)}"
        )
        document.add_paragraph(
            f"Requirement type: {kind}; priority: "
            f"{requirement.priority if requirement.priority is not None else 'Not supplied'}"
        )
        document.add_paragraph(
            f"Evidence classification: {_business_evidence_classification(requirement)}"
        )
        document.add_paragraph(
            f"Implementation status: {_business_implementation_status(requirement)}"
        )
        document.add_paragraph(
            f"Acceptance criteria: {_business_text(requirement.acceptanceCriterion, 1000)}"
        )
        if requirement.validationNotes:
            document.add_paragraph(
                f"Review note: {_business_text(requirement.validationNotes, 700)}"
            )
    if not typed_requirements:
        document.add_paragraph("No detailed requirements were evidenced in the supplied artifacts.")

    document.add_heading("12. Evidence Classification and Traceability", 1)
    document.add_paragraph(
        "Evidence classifications identify the kind of supplied support, not business approval. "
        "This appendix omits source filenames and line-level implementation detail; use the technical "
        "companion for full evidence citations and design traceability."
    )
    _add_business_table(document, ("Classification", "Meaning"), [
        (
            "Explicit business-source evidence",
            "Derived from supplied business requirements or user stories; confirm the original intent.",
        ),
        (
            "Design evidence",
            "Supported by a supplied design document; this alone does not establish business approval.",
        ),
        (
            "Implementation-derived evidence",
            "Observed application behavior; it must not be treated as an approved business need.",
        ),
        (
            "Evidence supported / partial",
            "Describes evidence coverage only and does not indicate stakeholder sign-off.",
        ),
        (
            "Not supplied / TBD",
            "Requires confirmation by the accountable business or product owner.",
        ),
    ])
    trace_by_id = {
        trace.requirementId: trace for trace in result.requirementsToDesignTraceability
    }
    diagram_titles = {
        reference: diagram.title
        for reference, diagram in result.umlDiagrams.entries()
        if diagram.generated
    }
    trace_rows = []
    for requirement in requirements:
        kind = (
            "Functional" if requirement in result.highLevelRequirements
            else "Quality / service"
        )
        label = getattr(requirement, "capability", None) or getattr(
            requirement, "category", "Requirement",
        )
        trace = trace_by_id.get(requirement.id)
        diagrams = (
            ", ".join(dict.fromkeys(
                diagram_titles.get(reference, reference)
                for reference in trace.relevantGeneratedDiagrams
            ))
            if trace and trace.relevantGeneratedDiagrams
            else "No validated diagram linked"
        )
        trace_rows.append((
            requirement.id,
            f"{kind}: {_business_text(label, 140)}",
            _business_evidence_sources(requirement),
            "Evidence supported" if requirement.evidenceStatus == "VERIFIED"
            else "Partial evidence",
            _business_implementation_status(requirement),
            diagrams,
        ))
    if trace_rows:
        _add_business_table(
            document,
            (
                "ID", "Requirement", "Evidence source type", "Evidence status",
                "Implementation status", "Related UML",
            ),
            trace_rows,
        )
    else:
        document.add_paragraph("No requirements were available for traceability.")

    document.add_heading("Appendix A: Analysis Coverage", 1)
    _add_business_table(document, ("Coverage item", "Value"), [
        ("Analysis mode", result.analysisScope.analysisMode),
        ("Code files analyzed", f"{analyzed_code_files:,}"),
        ("Supporting artifacts analyzed", f"{analyzed_supporting:,}"),
        ("Bounded analysis batches", f"{batch_count:,}"),
        ("Selected scope", _business_text(result.analysisScope.scopeDescription, 700)),
    ])

    document.add_heading("13. Review and Approval", 1)
    document.add_paragraph(result.validationStatement)
    _add_business_table(document, ("Role", "Name", "Decision", "Date", "Comments"), [
        ("Product Owner", "", "Approve / Reject", "", ""),
        ("Business / Operations Owner", "", "Approve / Reject", "", ""),
        ("Application Owner", "", "Approve / Reject", "", ""),
        ("Technology Lead", "", "Approve / Reject", "", ""),
        ("QA / UAT Lead", "", "Approve / Reject", "", ""),
    ])
    stream = io.BytesIO()
    document.save(stream)
    return stream.getvalue()