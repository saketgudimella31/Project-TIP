"""Synthetic model output used only by tests, never as a production fallback."""
from pathlib import PurePosixPath

from tip.models import AnalysisResult


def sample_result(target, context, artifacts, with_diagram=False):
    evidence = [{
        "sourceType": a.sourceType, "sourceName": a.sourceName, "filePath": a.filePath,
        "symbol": None, "externalId": a.externalId, "section": None,
        "worksheet": a.worksheet, "row": a.row, "lineStart": None, "lineEnd": None,
        "evidenceDescription": "Synthetic test evidence for displaying order status.",
    } for a in artifacts]
    origins = list(dict.fromkeys(e["sourceType"] for e in evidence))
    implementation = (
        "IMPLEMENTATION_EVIDENCED" if "CODE" in origins else "IMPLEMENTATION_NOT_EVIDENCED"
    )
    omitted = {
        "generated": False, "title": "", "description": "", "plantUml": "",
        "sourceEvidence": [], "reason": "Not evidenced in the supplied artifacts.",
    }
    component = omitted
    if with_diagram:
        component = {
            "generated": True, "title": "Synthetic order-status component",
            "description": "A test-only component illustration.",
            "plantUml": "@startuml\ntitle Synthetic order-status component\ncomponent Orders\n@enduml",
            "sourceEvidence": evidence, "reason": "",
        }
    requirement = {
        "id": "HLR-001", "capability": "Order status",
        "requirement": "The system shall display order status.",
        "acceptanceCriterion": "The supplied artifact describes order status.",
        "priority": None, "requirementOrigin": origins, "sourceEvidence": evidence,
        "implementationEvidenceStatus": implementation, "evidenceStatus": "VERIFIED",
        "validationNotes": "",
    }
    support = {
        (a.sourceType, a.sourceName, a.externalId)
        for a in artifacts if a.sourceType != "CODE"
    }
    return AnalysisResult.model_validate({
        "status": "SUCCESS", "schemaVersion": "2.0",
        "documentTitle": f"{target} requirements",
        "documentInformation": {
            "projectName": "Test Intelligence Platform (TIP)", "targetApplication": target,
            "documentType": "Evidence-Derived Requirements and UML Design",
            "version": "1.0", "status": "Draft for Human Validation",
            "classification": "Fiserv Internal Use Only",
        },
        "inputContext": context.model_dump(),
        "executiveSummary": "Synthetic analysis for integration testing, not real model output.",
        "analysisScope": {
            "analysisMode": context.analysisMode, "scopeDescription": "Supplied test artifacts",
            "includedFiles": [a.filePath for a in artifacts if a.filePath],
            "excludedFiles": [], "unsupportedFiles": [], "unreadableFiles": [], "limitations": [],
        },
        "codebaseInventory": [{
            "fileName": PurePosixPath(a.filePath).name, "relativePath": a.filePath,
            "fileType": PurePosixPath(a.filePath).suffix,
            "processingStatus": "ANALYZED", "purpose": "Synthetic example",
            "sha256": a.sha256,
        } for a in artifacts if a.sourceType == "CODE"],
        "supportingArtifactInventory": [{
            "sourceType": kind, "sourceName": name, "externalId": external,
            "processingStatus": "ANALYZED", "purpose": "Synthetic example",
        } for kind, name, external in sorted(support, key=lambda item: (item[0], item[1]))],
        "applicationOverview": {
            "purpose": "Display order status", "modules": [], "components": [],
            "interfaces": [], "dependencies": [], "functionalFlows": [],
        },
        "highLevelRequirements": [requirement], "nonFunctionalRequirements": [],
        "umlDiagrams": {
            "componentDiagram": component, "classDiagram": omitted,
            "sequenceDiagrams": [], "packageDiagram": omitted,
            "activityDiagrams": [], "deploymentDiagram": omitted,
            "stateMachineDiagrams": [], "useCaseDiagram": omitted,
        },
        "requirementsToDesignTraceability": [{
            "requirementId": "HLR-001", "requirementSummary": requirement["requirement"],
            "requirementOrigin": origins, "sourceEvidence": evidence,
            "implementationEvidenceStatus": implementation,
            "relevantGeneratedDiagrams": ["componentDiagram"] if with_diagram else [],
            "relevantDesignElements": [], "validationStatus": "VERIFIED",
        }],
        "evidenceConflicts": [], "assumptions": [], "limitations": [], "warnings": [],
        "validationStatement": "All generated requirements and UML diagrams are draft artifacts requiring human review and validation.",
    })