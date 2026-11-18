import io
import json
import os
from datetime import datetime
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from docx import Document
from docx.shared import Inches
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from .models import AnalysisResult
from .text_utils import strip_html

QTEST_COLUMNS = (
    "Id", "Name", "Attachments", "Status", "Type", "Description", "Priority",
    "Target Release/Build", "Assigned To", "Application", "Requirement ID",
    "Testable", "Project Details", "Sprint", "Vera Id",
    "Vera Approval Status", "Vera Pending Tasks", "Vera Revision",
    "Vera Approval Route", "Vera Rejection Reason", "Parent Requirement ID",
    "Requirement Level", "Evidence Status", "Source Reference",
    "Implementation Verified", "Review Required",
)


@dataclass(frozen=True)
class OutputBundle:
    document: bytes
    canonical_json: bytes
    qtest_xlsx: bytes


def _sources(requirement: dict) -> list[dict]:
    records = []
    for evidence in requirement.get("sourceEvidence", []):
        symbol = evidence.get("symbol") or ""
        records.append({
            "evidenceType": (
                "CODE" if evidence.get("sourceType") == "CODE"
                else "SUPPORTING_ARTIFACT"
            ),
            "sourceName": evidence["sourceName"],
            "sourceFile": evidence.get("filePath") or evidence["sourceName"],
            "sourceClass": None,
            "sourceMethod": None,
            "sourceSymbol": symbol or None,
            "sourceBranch": None,
            "startLine": evidence.get("lineStart"),
            "endLine": evidence.get("lineEnd"),
            "sectionName": evidence.get("section") or evidence.get("worksheet"),
            "pageNumber": None,
            "evidenceExcerpt": None,
            "evidenceDescription": evidence["evidenceDescription"],
        })
    return records


def canonical_requirements(result: AnalysisResult) -> dict:
    source_code_supplied = bool(
        result.analysisScope.analyzedCodeFiles or result.codebaseInventory
    )
    supporting_supplied = bool(
        result.analysisScope.analyzedSupportingArtifacts
        or result.supportingArtifactInventory
    )
    if source_code_supplied and supporting_supplied:
        mode = "COMBINED"
    elif source_code_supplied:
        mode = "CODEBASE"
    else:
        mode = "DOCUMENTS"

    requirements = []
    for kind, records in (
        ("FUNCTIONAL", result.highLevelRequirements),
        ("NON_FUNCTIONAL", result.nonFunctionalRequirements),
    ):
        for requirement in records:
            requirement_id = requirement.id
            evidence = _sources(requirement.model_dump())
            requirement_data = requirement.model_dump()
            implementation_verified = (
                source_code_supplied
                and requirement_data["implementationEvidenceStatus"]
                == "IMPLEMENTATION_EVIDENCED"
                and any(item["evidenceType"] == "CODE" for item in evidence)
            )
            implementation_partial = (
                source_code_supplied
                and requirement_data["implementationEvidenceStatus"]
                == "IMPLEMENTATION_PARTIALLY_EVIDENCED"
                and any(item["evidenceType"] == "CODE" for item in evidence)
            )
            parent = {
                "requirementId": requirement_id,
                "parentRequirementId": None,
                "requirementLevel": "PARENT",
                "name": requirement_data.get("capability")
                or requirement_data.get("category", requirement_id),
                "description": requirement_data["requirement"],
                "module": None,
                "status": "Draft for Human Validation",
                "type": kind,
                "priority": requirement_data["priority"],
                "testable": bool(requirement_data["acceptanceCriterion"].strip()),
                "businessObjective": None,
                "businessOutcome": None,
                "preconditions": [],
                "mainFlow": [],
                "alternateFlows": [],
                "exceptionFlows": [],
                "acceptanceCriteria": [
                    requirement_data["acceptanceCriterion"].strip()
                ] if requirement_data["acceptanceCriterion"].strip() else [],
                "businessRules": [],
                "postconditions": [],
                "evidenceReferences": evidence,
                "origin": _origin(evidence),
                "evidenceStatus": (
                    "IMPLEMENTATION_EVIDENCED" if implementation_verified
                    else "PARTIAL_EVIDENCE" if requirement_data["evidenceStatus"] == "PARTIALLY_EVIDENCED"
                    else "NOT_IMPLEMENTATION_VERIFIED"
                ),
                "implementationVerified": implementation_verified,
                "implementationVerification": (
                    "PARTIAL" if implementation_partial
                    else "YES" if implementation_verified else "NO"
                ),
                "suggestedTestScenarios": [],
                "reviewRequired": True,
                "children": [],
            }
            for index, child in enumerate(requirement_data.get("childRequirements", []), 1):
                child_status = child["implementationEvidenceStatus"]
                child_evidence = _sources(child)
                child_implemented = (
                    source_code_supplied
                    and child_status == "IMPLEMENTATION_EVIDENCED"
                    and any(item["evidenceType"] == "CODE" for item in child_evidence)
                )
                child_partial = (
                    source_code_supplied
                    and child_status == "IMPLEMENTATION_PARTIALLY_EVIDENCED"
                    and any(item["evidenceType"] == "CODE" for item in child_evidence)
                )
                child_id = f"{requirement_id}.{index}"
                child_record = {
                    **parent,
                    "requirementId": child_id,
                    "parentRequirementId": requirement_id,
                    "requirementLevel": "CHILD",
                    "name": child["name"],
                    "description": child["requirement"],
                    "priority": child["priority"],
                    "testable": bool(child["acceptanceCriterion"].strip()),
                    "acceptanceCriteria": [child["acceptanceCriterion"]]
                    if child["acceptanceCriterion"] else [],
                    "evidenceReferences": child_evidence,
                    "origin": _origin(child_evidence),
                    "evidenceStatus": (
                        "IMPLEMENTATION_EVIDENCED" if child_implemented
                        else "PARTIAL_EVIDENCE" if child["evidenceStatus"] == "PARTIALLY_EVIDENCED"
                        else "NOT_IMPLEMENTATION_VERIFIED"
                    ),
                    "implementationVerified": child_implemented,
                    "implementationVerification": (
                        "PARTIAL" if child_partial
                        else "YES" if child_implemented else "NO"
                    ),
                    "reviewRequired": True,
                    "children": [],
                }
                parent["children"].append(child_record)
                requirements.append(child_record)
            requirements.insert(len(requirements) - len(parent["children"]), parent)

    parents = [item for item in requirements if item["requirementLevel"] == "PARENT"]
    children = [item for item in requirements if item["requirementLevel"] == "CHILD"]
    files_analyzed = (
        result.analysisScope.analyzedCodeFiles
        + result.analysisScope.analyzedSupportingArtifacts
    )
    traceability = []
    for requirement in requirements:
        for evidence in requirement["evidenceReferences"]:
            traceability.append({
                "requirementId": requirement["requirementId"],
                "sourceName": evidence["sourceName"],
                "sourceFile": evidence["sourceFile"],
                "sourceClass": evidence["sourceClass"],
                "sourceMethod": evidence["sourceMethod"],
                "sourceSymbol": evidence["sourceSymbol"],
                "sourceBranch": evidence["sourceBranch"],
                "startLine": evidence["startLine"],
                "endLine": evidence["endLine"],
            })
    if not source_code_supplied:
        implementation_status = "NO"
    elif requirements and all(item["implementationVerified"] for item in requirements):
        implementation_status = "YES"
    elif any(
        item["implementationVerified"] or item["implementationVerification"] == "PARTIAL"
        for item in requirements
    ):
        implementation_status = "PARTIAL"
    else:
        implementation_status = "NO"
    class_coverage = []
    if source_code_supplied:
        for item in result.classCoverage:
            class_file = item.sourceFile
            linked_requirements = [
                requirement["requirementId"]
                for requirement in requirements
                if any(
                    evidence.get("sourceFile") == class_file
                    for evidence in requirement["evidenceReferences"]
                )
            ]
            class_coverage.append({
                "className": item.className,
                "sourceFile": class_file,
                "analysisStatus": item.analysisStatus,
                "parentRequirements": list(dict.fromkeys(
                    requirement_id for requirement_id in linked_requirements
                    if "." not in requirement_id
                )),
                "childRequirements": list(dict.fromkeys(
                    requirement_id for requirement_id in linked_requirements
                    if "." in requirement_id
                )),
                "methodsDiscovered": item.methodsDiscovered,
                "methodsAnalyzed": item.methodsAnalyzed,
                "branchesDiscovered": item.branchesDiscovered,
                "branchesAnalyzed": item.branchesAnalyzed,
                "notes": item.notes,
                "evidenceReferences": _sources(item.model_dump()),
            })
    classes_discovered = len(class_coverage) if class_coverage else None
    classes_analyzed = (
        sum(
            item["analysisStatus"] in {"ANALYZED", "PASSIVE_DATA_STRUCTURE"}
            for item in class_coverage
        )
        if class_coverage else None
    )
    coverage_gaps = [
        *result.analysisScope.limitations,
        *result.limitations,
        *result.warnings,
    ]
    if source_code_supplied and not class_coverage:
        coverage_gaps.append(
            "Class-by-class coverage was not returned; class counts are not claimed."
        )
    elif any(item["analysisStatus"] == "REVIEW_REQUIRED" for item in class_coverage):
        coverage_gaps.append(
            "Some classes need review because their supplied source was incomplete or ambiguous."
        )

    return {
        "schemaVersion": "2.0",
        "project": {
            "projectName": result.documentInformation.targetApplication,
            "analysisMode": mode,
            "status": "Draft for Human Validation",
            "sourceCodeSupplied": source_code_supplied,
            "supportingEvidenceSupplied": supporting_supplied,
            "implementationVerified": implementation_status,
        },
        "analysisSummary": {
            "filesDiscovered": (
                len(result.codebaseInventory) + len(result.supportingArtifactInventory)
            ),
            "filesAnalyzed": files_analyzed,
            "filesExcluded": len(result.analysisScope.excludedFiles),
            "classesDiscovered": classes_discovered,
            "classesAnalyzed": classes_analyzed,
            "parentRequirements": len(parents),
            "childRequirements": len(children),
            "totalRequirements": len(requirements),
        },
        "requirements": requirements,
        "classCoverage": class_coverage,
        "traceability": traceability,
        "coverageGaps": list(dict.fromkeys(coverage_gaps)),
        "excludedArtifacts": result.analysisScope.excludedFiles,
    }


def _origin(evidence: list[dict]) -> str:
    types = {item["evidenceType"] for item in evidence}
    if types == {"CODE"}:
        return "CODE"
    if types == {"SUPPORTING_ARTIFACT"}:
        return "SUPPORTING_ARTIFACT"
    return "COMBINED"


def _safe_excel(value):
    if value is None:
        return ""
    text = str(value)
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def _configured_qtest_columns() -> tuple[str, ...]:
    raw_mapping = os.environ.get("TIP_QTEST_FIELD_MAPPING_JSON", "").strip()
    if not raw_mapping:
        return QTEST_COLUMNS
    try:
        mapping = json.loads(raw_mapping)
    except json.JSONDecodeError as error:
        raise ValueError("TIP_QTEST_FIELD_MAPPING_JSON must contain a JSON object") from error
    if not isinstance(mapping, dict) or any(
        key not in QTEST_COLUMNS or not isinstance(value, str) or not value.strip()
        for key, value in mapping.items()
    ):
        raise ValueError(
            "TIP_QTEST_FIELD_MAPPING_JSON must map known qTest column names to non-empty labels"
        )
    columns = tuple(mapping.get(column, column) for column in QTEST_COLUMNS)
    if len(set(columns)) != len(columns):
        raise ValueError("Configured qTest column labels must be unique")
    return columns


def _configured_qtest_defaults() -> dict[str, str]:
    raw_defaults = os.environ.get("TIP_QTEST_DEFAULT_VALUES_JSON", "").strip()
    if not raw_defaults:
        return {}
    try:
        defaults = json.loads(raw_defaults)
    except json.JSONDecodeError as error:
        raise ValueError("TIP_QTEST_DEFAULT_VALUES_JSON must contain a JSON object") from error
    configurable = {"Target Release/Build", "Assigned To", "Sprint"}
    if not isinstance(defaults, dict) or any(
        key not in configurable or not isinstance(value, str)
        for key, value in defaults.items()
    ):
        raise ValueError(
            "TIP_QTEST_DEFAULT_VALUES_JSON may set Target Release/Build, Assigned To, and Sprint"
        )
    return defaults


def _plain_description(requirement: dict) -> str:
    sections = ["Requirement:", strip_html(requirement["description"])]
    criteria = requirement.get("acceptanceCriteria") or []
    if criteria:
        sections.extend(["", "Acceptance Criteria:"])
        sections.extend(f"- {strip_html(item)}" for item in criteria)
    evidence = requirement.get("evidenceReferences") or []
    if evidence:
        sections.extend(["", "Evidence:"])
        for item in evidence:
            location = item["sourceName"]
            if item.get("sourceSymbol"):
                location += f" → {item['sourceSymbol']}"
            if item.get("sourceBranch"):
                location += f" → {item['sourceBranch']}"
            if item.get("sectionName"):
                location += f" / {item['sectionName']}"
            if item.get("startLine"):
                location += f" → lines {item['startLine']}–{item['endLine'] or item['startLine']}"
            sections.append(f"- {strip_html(location)}")
    return "\n".join(sections)


def _qtest_priority(value, requirement_id: str) -> str:
    if value is None or (isinstance(value, str) and not value.strip()):
        return ""
    allowed = {
        "must have": "Must have",
        "should have": "Should have",
        "nice to have": "Nice to Have",
    }
    if isinstance(value, str):
        normalized = " ".join(value.split()).casefold()
        if normalized in allowed:
            return allowed[normalized]
    raise ValueError(
        f"qTest priority for {requirement_id} is not supported: {value!r}. "
        "Use Must have, Should have, or Nice to Have, or leave priority unspecified; "
        "TIP will not guess a mapping."
    )


def create_qtest_workbook(canonical: dict) -> bytes:
    columns = _configured_qtest_columns()
    defaults = _configured_qtest_defaults()
    time_zone = os.environ.get("TIP_TIME_ZONE", "UTC")
    try:
        exported_at = datetime.now(ZoneInfo(time_zone)).isoformat()
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"Unknown TIP_TIME_ZONE: {time_zone}") from error
    workbook = Workbook()
    cover = workbook.active
    cover.title = "Cover Page"
    project = canonical["project"]
    metadata = [
        ("Project Name", project["projectName"]),
        ("Exported On", exported_at),
        ("Generated By", "TIP"),
        ("Powered By", "Test Intelligence Platform"),
        ("Time Zone", time_zone),
        ("Status", "Draft for Human Validation"),
        ("Analysis Mode", project["analysisMode"]),
    ]
    for row in metadata:
        cover.append([_safe_excel(value) for value in row])
    cover.column_dimensions["A"].width = 28
    cover.column_dimensions["B"].width = 64
    for cell in cover["A"]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1D4ED8")

    sheet = workbook.create_sheet("Requirements")
    sheet.append(columns)
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1D4ED8")
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    for requirement in canonical["requirements"]:
        requirement_type = requirement["type"]
        if requirement_type not in {"FUNCTIONAL", "NON_FUNCTIONAL"}:
            raise ValueError(
                f"Unsupported qTest requirement type for {requirement['requirementId']}: "
                f"{requirement_type!r}."
            )
        evidence = requirement.get("evidenceReferences") or []
        source_reference = "; ".join(dict.fromkeys(
            item.get("sourceFile") or item["sourceName"] for item in evidence
        ))
        values = {
            "Id": "",
            "Name": requirement["name"],
            "Attachments": "",
            "Status": "New",
            "Type": (
                "Functional" if requirement_type == "FUNCTIONAL"
                else "Non-functional"
            ),
            "Description": _plain_description(requirement),
            "Priority": _qtest_priority(requirement.get("priority"), requirement["requirementId"]),
            "Target Release/Build": defaults.get("Target Release/Build", ""),
            "Assigned To": defaults.get("Assigned To", ""),
            "Application": project["projectName"],
            "Requirement ID": requirement["requirementId"],
            "Testable": "Yes" if requirement["testable"] else "No",
            "Project Details": requirement.get("module") or "",
            "Sprint": defaults.get("Sprint", ""),
            "Vera Id": "",
            "Vera Approval Status": "",
            "Vera Pending Tasks": "",
            "Vera Revision": "",
            "Vera Approval Route": "",
            "Vera Rejection Reason": "",
            "Parent Requirement ID": requirement.get("parentRequirementId") or "",
            "Requirement Level": requirement["requirementLevel"].title(),
            "Evidence Status": requirement["evidenceStatus"],
            "Source Reference": source_reference,
            "Implementation Verified": requirement["implementationVerification"],
            "Review Required": "Yes",
        }
        sheet.append([_safe_excel(values[column]) for column in QTEST_COLUMNS])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column, width in {
        "A": 16, "B": 36, "D": 28, "F": 72, "J": 28, "K": 20,
        "M": 28, "U": 22, "V": 18, "W": 28, "X": 48,
    }.items():
        sheet.column_dimensions[column].width = width
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def create_final_document(
    result: AnalysisResult, canonical: dict, rendered_diagrams: dict[str, bytes],
) -> bytes:
    document = Document()
    project = canonical["project"]
    summary = canonical["analysisSummary"]
    document.add_heading("TIP Evidence-Derived Requirements", 0)
    document.add_paragraph(project["projectName"])
    document.add_paragraph("Draft for Human Validation · Fiserv Internal Use Only")
    document.add_heading("1. Executive Summary", 1)
    document.add_paragraph(result.executiveSummary)
    document.add_paragraph(
        f"Analyzed {summary['filesAnalyzed']:,} files. "
        f"Generated {summary['parentRequirements']:,} parent and "
        f"{summary['childRequirements']:,} child requirements."
    )
    if not project["sourceCodeSupplied"]:
        document.add_paragraph(
            "Implementation verification was not performed because source code was not supplied."
        )

    document.add_heading("2. Analysis Scope", 1)
    scope_rows = [
        ("Project", project["projectName"]),
        ("Analysis mode", project["analysisMode"]),
        ("Source code supplied", "Yes" if project["sourceCodeSupplied"] else "No"),
        ("Supporting evidence supplied", "Yes" if project["supportingEvidenceSupplied"] else "No"),
        ("Implementation verified", project["implementationVerified"]),
        ("Status", "Draft for Human Validation"),
        ("Files analyzed", str(summary["filesAnalyzed"])),
        ("Files excluded", str(summary["filesExcluded"])),
        (
            "Classes analyzed",
            str(summary["classesAnalyzed"])
            if summary["classesAnalyzed"] is not None
            else "Not available; no class count is claimed"
            if project["sourceCodeSupplied"] else "Not applicable",
        ),
    ]
    table = document.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    for label, value in scope_rows:
        cells = table.add_row().cells
        cells[0].text = label
        cells[1].text = value

    document.add_heading("3. Business Capability Summary", 1)
    if result.applicationOverview.purpose:
        document.add_paragraph(result.applicationOverview.purpose)
    table = document.add_table(rows=1, cols=5)
    table.style = "Table Grid"
    for cell, label in zip(table.rows[0].cells, (
        "Requirement ID", "Capability", "Purpose", "Children", "Evidence",
    )):
        cell.text = label
    for requirement in canonical["requirements"]:
        if requirement["requirementLevel"] != "PARENT":
            continue
        row = table.add_row().cells
        sources = ", ".join(sorted({
            item["evidenceType"] for item in requirement["evidenceReferences"]
        })) or "Not supplied"
        for cell, value in zip(row, (
            requirement["requirementId"], requirement["name"],
            requirement["description"], str(len(requirement["children"])), sources,
        )):
            cell.text = value

    document.add_heading("4. Parent and Child Requirements", 1)
    for requirement in canonical["requirements"]:
        level = requirement["requirementLevel"].title()
        document.add_heading(
            f"{requirement['requirementId']}: {requirement['name']}", 2,
        )
        document.add_paragraph(
            f"Requirement type: {level} | Status: Draft for Human Validation | "
            f"Evidence: {requirement['evidenceStatus']}"
        )
        document.add_paragraph(requirement["description"])
        if requirement["acceptanceCriteria"]:
            document.add_paragraph("Acceptance criteria")
            for criterion in requirement["acceptanceCriteria"]:
                document.add_paragraph(criterion, style="List Bullet")
        document.add_paragraph("Evidence")
        if requirement["evidenceReferences"]:
            for evidence in requirement["evidenceReferences"]:
                label = evidence["sourceName"]
                for field in ("sourceSymbol", "sourceBranch"):
                    if evidence.get(field):
                        label += f" → {evidence[field]}"
                if evidence.get("sectionName"):
                    label += f" / {evidence['sectionName']}"
                if evidence.get("startLine"):
                    label += f" → lines {evidence['startLine']}–{evidence['endLine'] or evidence['startLine']}"
                document.add_paragraph(label, style="List Bullet")
        else:
            document.add_paragraph("No source evidence was recorded.")
        if project["sourceCodeSupplied"]:
            document.add_paragraph(
                "Technical evidence is limited to the analyzed code and cited source locations."
            )
        else:
            document.add_paragraph(
                "This requirement was derived from supporting evidence. "
                "Implementation could not be verified because source code was not supplied."
            )

    if project["sourceCodeSupplied"]:
        document.add_heading("5. Code Coverage", 1)
        if not canonical["classCoverage"]:
            document.add_paragraph(
                "Class-level coverage was not returned. No class counts or coverage percentage are claimed."
            )
        else:
            table = document.add_table(rows=1, cols=7)
            table.style = "Table Grid"
            for cell, label in zip(table.rows[0].cells, (
                "Class", "Analysis status", "Parents", "Children",
                "Methods analyzed", "Branches analyzed", "Notes",
            )):
                cell.text = label
            for entry in canonical["classCoverage"]:
                row = table.add_row().cells
                values = (
                    f"{entry['className']} ({entry['sourceFile']})",
                    entry["analysisStatus"],
                    ", ".join(entry["parentRequirements"]),
                    ", ".join(entry["childRequirements"]),
                    (
                        f"{len(entry['methodsAnalyzed'])}/{len(entry['methodsDiscovered'])}"
                        if entry["methodsDiscovered"] else "N/A"
                    ),
                    (
                        f"{len(entry['branchesAnalyzed'])}/{len(entry['branchesDiscovered'])}"
                        if entry["branchesDiscovered"] else "N/A"
                    ),
                    entry["notes"],
                )
                for cell, value in zip(row, values):
                    cell.text = value

    document.add_heading("6. Traceability", 1)
    trace_table = document.add_table(rows=1, cols=4)
    trace_table.style = "Table Grid"
    for cell, label in zip(trace_table.rows[0].cells, (
        "Requirement", "Evidence source", "Class / method / section", "Line / page",
    )):
        cell.text = label
    for item in canonical["traceability"]:
        row = trace_table.add_row().cells
        row[0].text = item["requirementId"]
        row[1].text = item["sourceFile"] or item["sourceName"]
        row[2].text = " / ".join(
            part for part in (
                item["sourceClass"], item["sourceMethod"], item["sourceSymbol"],
            ) if part
        )
        row[3].text = (
            f"{item['startLine']}-{item['endLine'] or item['startLine']}"
            if item["startLine"] else ""
        )

    if canonical["coverageGaps"]:
        document.add_heading("7. Gaps and Review Items", 1)
        for gap in canonical["coverageGaps"]:
            document.add_paragraph(str(gap), style="List Bullet")

    diagrams = [
        (reference, diagram)
        for reference, diagram in result.umlDiagrams.entries()
        if diagram.generated
    ]
    if diagrams:
        document.add_heading("8. Evidence-Supported UML", 1)
        for reference, diagram in diagrams:
            document.add_heading(diagram.title, 2)
            document.add_paragraph(diagram.description)
            image = rendered_diagrams.get(reference)
            if image:
                document.add_picture(io.BytesIO(image), width=Inches(6))

    document.add_heading("Human Validation", 1)
    document.add_paragraph(
        "All requirements and diagrams are drafts for human review. Confirm business intent, "
        "evidence, acceptance criteria, traceability, and qTest mappings before approval."
    )
    document.add_paragraph(result.validationStatement)
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def canonical_json_bytes(canonical: dict) -> bytes:
    return json.dumps(canonical, ensure_ascii=False, indent=2).encode("utf-8")
