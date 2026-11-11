import json
import re
from collections import OrderedDict
from typing import Iterable, Iterator

from .models import AnalysisResult, Artifact, InputContext

MAX_CODE_INVENTORY = 2_000
MAX_SUPPORTING_INVENTORY = 1_000
MAX_MERGED_REQUIREMENTS = 1_000
MAX_REQUIREMENT_EVIDENCE = 50
MAX_OVERVIEW_ITEMS = 1_000
MAX_DIAGRAMS_PER_GROUP = 10
MAX_DIAGRAM_EVIDENCE = 50
MAX_TEXT_ITEMS = 500
MAX_SUMMARIES = 20
MAX_SUMMARY_CHARACTERS = 50_000


def iter_artifact_batches(
    artifacts: Iterable[Artifact], *, max_files: int, max_characters: int,
) -> Iterator[list[Artifact]]:
    if max_files < 1 or max_characters < 1:
        raise ValueError("Analysis batch limits must be positive")
    batch: list[Artifact] = []
    characters = 0
    for artifact in artifacts:
        for part in _split_artifact(artifact, max_characters):
            size = len(part.content)
            if batch and (
                len(batch) >= max_files or characters + size > max_characters
            ):
                yield batch
                batch = []
                characters = 0
            batch.append(part)
            characters += size
            if len(batch) >= max_files or characters >= max_characters:
                yield batch
                batch = []
                characters = 0
    if batch:
        yield batch


def _split_artifact(artifact: Artifact, max_characters: int) -> Iterator[Artifact]:
    content = artifact.content
    if len(content) <= max_characters:
        yield artifact
        return
    cursor = 0
    while cursor < len(content):
        end = min(cursor + max_characters, len(content))
        if end < len(content):
            boundary = max(
                content.rfind("\n", cursor, end),
                content.rfind("\r", cursor, end),
            )
            if boundary > cursor + max_characters // 2:
                end = boundary + 1
        part = content[cursor:end]
        yield Artifact.model_validate({
            **artifact.model_dump(),
            "content": part,
            "lineOffset": artifact.lineOffset + len(
                re.findall(r"\r\n|\r|\n", content[:cursor])
            ),
        })
        cursor = end


def _stable_key(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _merge_evidence(existing: list[dict], incoming: list[dict], limit: int) -> list[dict]:
    merged: OrderedDict[str, dict] = OrderedDict(
        (_stable_key(item), item) for item in existing
    )
    first_by_type = {}
    for item in [*existing, *incoming]:
        first_by_type.setdefault(item["sourceType"], item)
        key = _stable_key(item)
        if key not in merged and len(merged) < limit:
            merged[key] = item
    for item in first_by_type.values():
        key = _stable_key(item)
        if key not in merged:
            if len(merged) >= limit:
                merged.popitem()
            merged[key] = item
    return list(merged.values())


class AnalysisAccumulator:
    def __init__(self):
        self._base: dict | None = None
        self._code_inventory: list[dict] = []
        self._code_paths: set[str] = set()
        self._supporting_inventory: list[dict] = []
        self._supporting_ids: set[tuple] = set()
        self._requirements = {
            "highLevelRequirements": OrderedDict(),
            "nonFunctionalRequirements": OrderedDict(),
        }
        self._overview = {
            key: [] for key in ("modules", "components", "interfaces", "dependencies", "functionalFlows")
        }
        self._overview_seen = {key: set() for key in self._overview}
        self._purposes: list[str] = []
        self._purpose_seen: set[str] = set()
        self._summaries: list[str] = []
        self._summary_seen: set[str] = set()
        self._summary_characters = 0
        self._text = {
            key: [] for key in ("evidenceConflicts", "assumptions", "limitations", "warnings")
        }
        self._text_seen = {key: set() for key in self._text}
        self._scope_lists = {
            key: [] for key in ("excludedFiles", "unsupportedFiles", "unreadableFiles")
        }
        self._scope_lists_seen = {key: set() for key in self._scope_lists}
        self._diagram_singletons: dict[str, dict] = {}
        self._diagram_arrays: dict[str, OrderedDict[str, dict]] = {
            key: OrderedDict() for key in ("sequenceDiagrams", "activityDiagrams", "stateMachineDiagrams")
        }
        self._diagram_titles: dict[str, str] = {}
        self.batch_count = 0
        self._truncated = set()

    @staticmethod
    def _add_bounded(items: list, seen: set, value, limit: int) -> None:
        key = _stable_key(value)
        if key in seen:
            return
        if len(items) >= limit:
            return
        seen.add(key)
        items.append(value)

    def _add_text(self, field: str, values: list) -> None:
        for value in values:
            key = _stable_key(value)
            if key in self._text_seen[field]:
                continue
            if len(self._text[field]) >= MAX_TEXT_ITEMS:
                self._truncated.add(field)
                continue
            self._text_seen[field].add(key)
            self._text[field].append(value)

    def _add_diagram(
        self, key: str, diagram: dict, *, array: bool, reference: str,
    ) -> None:
        if not diagram["generated"]:
            return
        self._diagram_titles[reference] = diagram["title"]
        self._diagram_titles[diagram["title"]] = diagram["title"]
        if array:
            entries = self._diagram_arrays[key]
            identity = _stable_key([diagram["title"], diagram["mermaid"]])
            previous = entries.get(identity)
            if previous:
                previous["sourceEvidence"] = _merge_evidence(
                    previous["sourceEvidence"], diagram["sourceEvidence"], MAX_DIAGRAM_EVIDENCE,
                )
            elif len(entries) < MAX_DIAGRAMS_PER_GROUP:
                entries[identity] = diagram
            else:
                self._truncated.add("diagrams")
            return

        previous = self._diagram_singletons.get(key)
        if previous is None:
            self._diagram_singletons[key] = diagram
        elif previous["mermaid"] == diagram["mermaid"]:
            previous["sourceEvidence"] = _merge_evidence(
                previous["sourceEvidence"], diagram["sourceEvidence"], MAX_DIAGRAM_EVIDENCE,
            )
        else:
            self._truncated.add("diagrams")

    def _add_requirement(self, field: str, requirement: dict, trace: dict | None) -> None:
        key = _stable_key([
            _normalized(requirement["requirement"]),
            _normalized(requirement["acceptanceCriterion"]),
        ])
        records = self._requirements[field]
        record = records.get(key)
        if record is None:
            if sum(len(items) for items in self._requirements.values()) >= MAX_MERGED_REQUIREMENTS:
                self._truncated.add("requirements")
                return
            record = {
                "value": requirement,
                "evidence": [],
                "implementationStatuses": set(),
                "evidenceStatuses": set(),
                "validationNotes": [],
                "validationNotesSeen": set(),
                "diagramReferences": [],
                "diagramReferencesSeen": set(),
                "designElements": [],
                "designElementsSeen": set(),
            }
            records[key] = record

        if record["value"]["priority"] is None and requirement["priority"] is not None:
            record["value"]["priority"] = requirement["priority"]
        record["evidence"] = _merge_evidence(
            record["evidence"], requirement["sourceEvidence"], MAX_REQUIREMENT_EVIDENCE,
        )
        record["implementationStatuses"].add(requirement["implementationEvidenceStatus"])
        record["evidenceStatuses"].add(requirement["evidenceStatus"])
        note = requirement["validationNotes"].strip()
        if note:
            self._add_bounded(
                record["validationNotes"], record["validationNotesSeen"], note, 20,
            )
        if trace:
            for value in trace["relevantGeneratedDiagrams"]:
                title = self._diagram_titles.get(value, value)
                self._add_bounded(
                    record["diagramReferences"], record["diagramReferencesSeen"], title, 50,
                )
            for value in trace["relevantDesignElements"]:
                self._add_bounded(
                    record["designElements"], record["designElementsSeen"], value, 100,
                )

    def add(self, result: AnalysisResult) -> None:
        payload = result.model_dump()
        if self._base is None:
            self._base = payload
        self.batch_count += 1

        for item in payload["codebaseInventory"]:
            path = item["relativePath"]
            if path in self._code_paths:
                continue
            self._code_paths.add(path)
            if len(self._code_inventory) < MAX_CODE_INVENTORY:
                self._code_inventory.append(item)
            else:
                self._truncated.add("code inventory")

        for item in payload["supportingArtifactInventory"]:
            identity = (item["sourceType"], item["sourceName"], item["externalId"])
            if identity in self._supporting_ids:
                continue
            self._supporting_ids.add(identity)
            if len(self._supporting_inventory) < MAX_SUPPORTING_INVENTORY:
                self._supporting_inventory.append(item)
            else:
                self._truncated.add("supporting inventory")

        overview = payload["applicationOverview"]
        purpose = overview["purpose"].strip()
        normalized_purpose = _normalized(purpose)
        if normalized_purpose and normalized_purpose not in self._purpose_seen:
            self._purpose_seen.add(normalized_purpose)
            if len(self._purposes) < MAX_SUMMARIES:
                self._purposes.append(purpose)
            else:
                self._truncated.add("overview")
        for field in self._overview:
            for item in overview[field]:
                key = _stable_key(item)
                if key in self._overview_seen[field]:
                    continue
                if len(self._overview[field]) >= MAX_OVERVIEW_ITEMS:
                    self._truncated.add("overview")
                    continue
                self._overview_seen[field].add(key)
                self._overview[field].append(item)

        summary = payload["executiveSummary"].strip()
        summary_key = _normalized(summary)
        if summary and summary_key not in self._summary_seen:
            if (
                len(self._summaries) < MAX_SUMMARIES
                and self._summary_characters + len(summary) <= MAX_SUMMARY_CHARACTERS
            ):
                self._summary_seen.add(summary_key)
                self._summaries.append(summary)
                self._summary_characters += len(summary)
            else:
                self._truncated.add("summaries")

        for field in self._text:
            self._add_text(field, payload[field])
        self._add_text("limitations", payload["analysisScope"]["limitations"])
        for field in self._scope_lists:
            for value in payload["analysisScope"][field]:
                key = _stable_key(value)
                if key in self._scope_lists_seen[field]:
                    continue
                if len(self._scope_lists[field]) >= MAX_TEXT_ITEMS:
                    self._truncated.add(field)
                    continue
                self._scope_lists_seen[field].add(key)
                self._scope_lists[field].append(value)

        trace_by_id = {
            item["requirementId"]: item
            for item in payload["requirementsToDesignTraceability"]
        }
        diagrams = payload["umlDiagrams"]
        for key, value in diagrams.items():
            if isinstance(value, list):
                for index, diagram in enumerate(value):
                    self._add_diagram(
                        key, diagram, array=True, reference=f"{key}[{index}]",
                    )
            else:
                self._add_diagram(key, value, array=False, reference=key)
        for field in self._requirements:
            for requirement in payload[field]:
                self._add_requirement(
                    field, requirement, trace_by_id.get(requirement["id"]),
                )

    def finish(
        self, context: InputContext, *, expected_code_files: int,
        expected_supporting_artifacts: int,
    ) -> AnalysisResult:
        if self._base is None or self.batch_count == 0:
            raise ValueError("No model batches completed; no analysis result can be published")
        if len(self._code_paths) != expected_code_files:
            raise ValueError(
                "Merged model output did not account for every eligible code file; "
                "no report was published."
            )
        if len(self._supporting_ids) != expected_supporting_artifacts:
            raise ValueError(
                "Merged model output did not account for every supplied supporting artifact; "
                "no report was published."
            )

        payload = self._base.copy()
        payload["inputContext"] = context.model_dump()
        payload["codebaseInventory"] = self._code_inventory
        payload["supportingArtifactInventory"] = self._supporting_inventory
        retained_diagram_titles = {
            item["title"]
            for item in [
                *self._diagram_singletons.values(),
                *(diagram for entries in self._diagram_arrays.values() for diagram in entries.values()),
            ]
        }
        payload["applicationOverview"] = {
            "purpose": " ".join(self._purposes) or payload["applicationOverview"]["purpose"],
            **self._overview,
        }

        requirement_values = {}
        traceability = []
        for field, prefix in (
            ("highLevelRequirements", "HLR"),
            ("nonFunctionalRequirements", "NFR"),
        ):
            requirement_values[field] = []
            for index, record in enumerate(self._requirements[field].values(), 1):
                requirement = record["value"].copy()
                requirement["id"] = f"{prefix}-{index:03d}"
                evidence = record["evidence"]
                requirement["sourceEvidence"] = evidence
                requirement["requirementOrigin"] = list(dict.fromkeys(
                    item["sourceType"] for item in evidence
                ))
                statuses = record["implementationStatuses"]
                if "CODE" not in requirement["requirementOrigin"]:
                    requirement["implementationEvidenceStatus"] = (
                        "NOT_APPLICABLE"
                        if statuses == {"NOT_APPLICABLE"}
                        else "IMPLEMENTATION_NOT_EVIDENCED"
                    )
                elif "IMPLEMENTATION_NOT_EVIDENCED" in statuses:
                    requirement["implementationEvidenceStatus"] = "IMPLEMENTATION_NOT_EVIDENCED"
                elif "IMPLEMENTATION_PARTIALLY_EVIDENCED" in statuses:
                    requirement["implementationEvidenceStatus"] = "IMPLEMENTATION_PARTIALLY_EVIDENCED"
                else:
                    requirement["implementationEvidenceStatus"] = "IMPLEMENTATION_EVIDENCED"
                requirement["evidenceStatus"] = (
                    "PARTIALLY_EVIDENCED"
                    if "PARTIALLY_EVIDENCED" in record["evidenceStatuses"]
                    else "VERIFIED"
                )
                requirement["validationNotes"] = "; ".join(record["validationNotes"])
                requirement_values[field].append(requirement)
                traceability.append({
                    "requirementId": requirement["id"],
                    "requirementSummary": requirement["requirement"],
                    "requirementOrigin": requirement["requirementOrigin"],
                    "sourceEvidence": evidence,
                    "implementationEvidenceStatus": requirement["implementationEvidenceStatus"],
                    "relevantGeneratedDiagrams": [
                        item for item in record["diagramReferences"]
                        if item in retained_diagram_titles
                    ],
                    "relevantDesignElements": record["designElements"],
                    "validationStatus": requirement["evidenceStatus"],
                })

        payload.update(requirement_values)
        payload["requirementsToDesignTraceability"] = traceability
        diagrams = {}
        for key, old in payload["umlDiagrams"].items():
            if isinstance(old, list):
                diagrams[key] = list(self._diagram_arrays[key].values())
            else:
                diagrams[key] = self._diagram_singletons.get(key, old)
        payload["umlDiagrams"] = diagrams

        included_files = [item["relativePath"] for item in self._code_inventory]
        payload["analysisScope"]["includedFiles"] = included_files
        for field, values in self._scope_lists.items():
            payload["analysisScope"][field] = values
        payload["analysisScope"]["analyzedCodeFiles"] = expected_code_files
        payload["analysisScope"]["analyzedSupportingArtifacts"] = expected_supporting_artifacts
        payload["analysisScope"]["analysisBatchCount"] = self.batch_count
        payload["analysisScope"]["limitations"] = self._text["limitations"]
        payload["evidenceConflicts"] = self._text["evidenceConflicts"]
        payload["assumptions"] = self._text["assumptions"]
        payload["limitations"] = self._text["limitations"]
        payload["warnings"] = self._text["warnings"]
        payload["executiveSummary"] = "\n\n".join(self._summaries) or payload["executiveSummary"]
        payload["validationStatement"] = (
            "Generated requirements and UML diagrams are draft artifacts requiring human review "
            f"and validation. This result merges {self.batch_count:,} independently validated "
            "model batches."
        )

        if len(self._code_paths) > MAX_CODE_INVENTORY:
            self._truncated.add("code inventory")
        if len(self._supporting_ids) > MAX_SUPPORTING_INVENTORY:
            self._truncated.add("supporting inventory")
        if self._truncated:
            details = []
            if "code inventory" in self._truncated:
                details.append(
                    f"the response inventory lists only the first {MAX_CODE_INVENTORY:,} code paths"
                )
            if "supporting inventory" in self._truncated:
                details.append(
                    f"the response inventory lists only the first {MAX_SUPPORTING_INVENTORY:,} supporting artifacts"
                )
            if "requirements" in self._truncated:
                details.append(
                    f"only the first {MAX_MERGED_REQUIREMENTS:,} distinct requirements were retained"
                )
            if "diagrams" in self._truncated:
                details.append(
                    f"diagram output was capped at {MAX_DIAGRAMS_PER_GROUP} per diagram group"
                )
            if "overview" in self._truncated:
                details.append("application overview lists were capped")
            if "summaries" in self._truncated:
                details.append("some per-batch summaries were omitted")
            if self._truncated & {"evidenceConflicts", "assumptions", "limitations", "warnings"}:
                details.append("some repeated validation notes were omitted")
            if self._truncated & {"excludedFiles", "unsupportedFiles", "unreadableFiles"}:
                details.append("some file-scope lists were omitted")
            warning = "Merged output limits applied: " + "; ".join(details) + "."
            for target in (
                payload["warnings"], payload["limitations"], payload["analysisScope"]["limitations"],
            ):
                if warning not in target:
                    target.append(warning)

        return AnalysisResult.model_validate(payload)