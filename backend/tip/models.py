import re
from typing import Annotated, Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

SourceType = Literal["CODE", "DESIGN_DOCUMENT", "JIRA_USER_STORY", "RAW_REQUIREMENT"]
ImplementationStatus = Literal[
    "IMPLEMENTATION_EVIDENCED",
    "IMPLEMENTATION_PARTIALLY_EVIDENCED",
    "IMPLEMENTATION_NOT_EVIDENCED",
    "NOT_APPLICABLE",
]
EvidenceStatus = Literal["VERIFIED", "PARTIALLY_EVIDENCED"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SupportingInputs(StrictModel):
    designDocumentsProvided: bool
    jiraUserStoriesProvided: bool = Field(
        validation_alias=AliasChoices(
            "jiraUserStoriesProvided",
            "jiraUserstoriesProvided",
        )
    )
    rawRequirementsProvided: bool


class InputContext(StrictModel):
    analysisMode: Literal["FULL", "INCREMENTAL", "UNKNOWN"]
    inputType: Literal[
        "LOCAL_FILE", "LOCAL_FILES", "LOCAL_FOLDER", "ARCHIVE",
        "REPOSITORY", "REPOSITORY_PATH", "URL", "INTEGRATION",
    ]
    sourceProvider: Literal["GITLAB", "GITHUB", "BITBUCKET", "OTHER"] | None
    repository: str | None
    branch: str | None
    selectedPath: str | None
    supportingInputs: SupportingInputs
    analysisFocus: str = ""


class Evidence(StrictModel):
    sourceType: SourceType
    sourceName: str
    filePath: str | None
    symbol: str | None
    externalId: str | None
    section: str | None
    worksheet: str | None
    row: int | None = Field(ge=1)
    lineStart: int | None = Field(ge=1)
    lineEnd: int | None = Field(ge=1)
    evidenceDescription: str = Field(min_length=1)

    @model_validator(mode="after")
    def line_range(self):
        if self.lineEnd is not None and (
            self.lineStart is None or self.lineEnd < self.lineStart
        ):
            raise ValueError("Invalid evidence line range")
        return self


class Artifact(StrictModel):
    sourceType: SourceType
    sourceName: str
    content: str = Field(min_length=1)
    lineOffset: int = Field(default=0, ge=0)
    filePath: str | None = None
    externalId: str | None = None
    worksheet: str | None = None
    row: int | None = None
    sha256: str | None = None


class Requirement(StrictModel):
    id: str
    requirement: str = Field(min_length=1)
    acceptanceCriterion: str
    priority: str | int | None
    requirementOrigin: list[SourceType] = Field(min_length=1)
    sourceEvidence: list[Evidence] = Field(min_length=1)
    implementationEvidenceStatus: ImplementationStatus
    evidenceStatus: EvidenceStatus
    validationNotes: str


class FunctionalRequirement(Requirement):
    capability: str


class NonFunctionalRequirement(Requirement):
    category: str


class Diagram(StrictModel):
    generated: bool
    title: str
    description: str
    mermaid: str
    sourceEvidence: list[Evidence]
    reason: str

    @model_validator(mode="after")
    def valid_shape(self):
        if self.generated:
            if not all([self.title, self.mermaid, self.sourceEvidence]):
                raise ValueError("Generated diagrams require a title, Mermaid source, and evidence")
        elif (
            self.title or self.description or self.mermaid or self.sourceEvidence
            or self.reason != "Not evidenced in the supplied artifacts."
        ):
            raise ValueError("Invalid non-generated diagram")
        return self


class Diagrams(StrictModel):
    componentDiagram: Diagram
    classDiagram: Diagram
    sequenceDiagrams: list[Diagram]
    packageDiagram: Diagram
    activityDiagrams: list[Diagram]
    deploymentDiagram: Diagram
    stateMachineDiagrams: list[Diagram]
    useCaseDiagram: Diagram

    def entries(self) -> list[tuple[str, Diagram]]:
        result = []
        for key in type(self).model_fields:
            value = getattr(self, key)
            if isinstance(value, list):
                result.extend((f"{key}[{i}]", d) for i, d in enumerate(value))
            else:
                result.append((key, value))
        return result


class DocumentInformation(StrictModel):
    projectName: Literal["Test Intelligence Platform (TIP)"]
    targetApplication: str
    documentType: Literal["Evidence-Derived Requirements and UML Design"]
    version: Literal["1.0"]
    status: Literal["Draft for Human Validation"]
    classification: Literal["Fiserv Internal Use Only"]


class AnalysisScope(StrictModel):
    analysisMode: Literal["FULL", "INCREMENTAL", "UNKNOWN"]
    scopeDescription: str
    includedFiles: list[str]
    excludedFiles: list[str]
    unsupportedFiles: list[str]
    unreadableFiles: list[str]
    limitations: list[str]
    analyzedCodeFiles: int = Field(default=0, ge=0)
    analyzedSupportingArtifacts: int = Field(default=0, ge=0)
    analysisBatchCount: int = Field(default=0, ge=0)


class CodeInventory(StrictModel):
    fileName: str
    relativePath: str
    fileType: str
    processingStatus: Literal[
        "ANALYZED", "EMPTY", "UNSUPPORTED", "BINARY", "GENERATED",
        "VENDOR", "DEPENDENCY", "DUPLICATE", "UNREADABLE",
    ]
    purpose: str
    sha256: str | None


class SupportingInventory(StrictModel):
    sourceType: Literal["DESIGN_DOCUMENT", "JIRA_USER_STORY", "RAW_REQUIREMENT"]
    sourceName: str
    externalId: str | None
    processingStatus: Literal["ANALYZED", "EMPTY", "UNSUPPORTED", "DUPLICATE", "UNREADABLE"]
    purpose: str


class Overview(StrictModel):
    purpose: str
    modules: list
    components: list
    interfaces: list
    dependencies: list
    functionalFlows: list


class Traceability(StrictModel):
    requirementId: str
    requirementSummary: str
    requirementOrigin: list[SourceType]
    sourceEvidence: list[Evidence]
    implementationEvidenceStatus: ImplementationStatus
    relevantGeneratedDiagrams: list[str]
    relevantDesignElements: list[str]
    validationStatus: EvidenceStatus


def _derived_capability(requirement: str, requirement_id: str) -> str:
    label = re.sub(
        r"^(?:the\s+)?(?:system|application)\s+shall\s+",
        "",
        requirement.strip(),
        flags=re.IGNORECASE,
    )
    label = re.split(r"(?<=[.!?])\s+|\s+(?:so that|to ensure)\s+", label, maxsplit=1)[0]
    label = label.strip(" .;:")
    if len(label) > 80:
        label = label[:77].rsplit(" ", 1)[0].rstrip(" ,;:-") + "..."
    return label or requirement_id or "Functional requirement"


class AnalysisResult(StrictModel):
    status: Literal["SUCCESS"]
    schemaVersion: Literal["2.0"]
    documentTitle: str = Field(min_length=1)
    documentInformation: DocumentInformation
    inputContext: InputContext
    executiveSummary: str
    analysisScope: AnalysisScope
    codebaseInventory: list[CodeInventory]
    supportingArtifactInventory: list[SupportingInventory]
    applicationOverview: Overview
    highLevelRequirements: list[FunctionalRequirement]
    nonFunctionalRequirements: list[NonFunctionalRequirement]
    umlDiagrams: Diagrams
    requirementsToDesignTraceability: list[Traceability]
    evidenceConflicts: list
    assumptions: list
    limitations: list[str]
    warnings: list[str]
    validationStatement: str

    @model_validator(mode="before")
    @classmethod
    def derive_missing_capabilities(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        requirements = value.get("highLevelRequirements")
        if not isinstance(requirements, list):
            return value

        normalized = dict(value)
        normalized_requirements = []
        repaired = False
        for requirement in requirements:
            if not isinstance(requirement, dict):
                normalized_requirements.append(requirement)
                continue
            capability = requirement.get("capability")
            if isinstance(capability, str) and capability.strip():
                normalized_requirements.append(requirement)
                continue
            statement = requirement.get("requirement")
            if not isinstance(statement, str) or not statement.strip():
                normalized_requirements.append(requirement)
                continue
            normalized_requirement = dict(requirement)
            normalized_requirement["capability"] = _derived_capability(
                statement, str(requirement.get("id", "")),
            )
            normalized_requirements.append(normalized_requirement)
            repaired = True

        if not repaired:
            return value
        normalized["highLevelRequirements"] = normalized_requirements
        warning = (
            "TIP derived one or more missing functional requirement capability labels "
            "from their requirement statements."
        )
        warnings = normalized.get("warnings")
        if isinstance(warnings, list):
            if warning not in warnings:
                normalized["warnings"] = [*warnings, warning]
        elif "warnings" not in normalized:
            normalized["warnings"] = [warning]
        return normalized


class ManualStory(StrictModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=20_000)
    acceptanceCriteria: str = Field(default="", max_length=20_000)
    priority: str | None = Field(default=None, max_length=100)


class AnalysisOptions(StrictModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    target_application: str = Field(min_length=1, max_length=200)
    analysis_mode: Literal["FULL", "INCREMENTAL", "UNKNOWN"] = "INCREMENTAL"
    code_source: Literal["uploads", "repository", "local", "indexed"] = "uploads"
    upload_kind: Literal["LOCAL_FILES", "LOCAL_FOLDER", "ARCHIVE"] = "LOCAL_FILES"
    repo_url: str | None = Field(default=None, max_length=2000)
    local_path: str | None = Field(default=None, max_length=2000)
    branch: str | None = Field(default=None, max_length=200)
    selected_path: str | None = Field(default=None, max_length=2000)
    indexed_repo_id: str | None = Field(default=None, max_length=200)
    focus: str = Field(default="", max_length=2000)
    jira_issue_keys: list[Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]*-\d+$")]] = Field(
        default_factory=list, max_length=20
    )
    manual_stories: list[ManualStory] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def source_selection(self):
        if self.code_source == "repository" and not self.repo_url:
            raise ValueError("repo_url is required")
        if self.code_source == "local" and not self.local_path:
            raise ValueError("local_path is required")
        if self.code_source == "indexed" and not self.indexed_repo_id:
            raise ValueError("indexed_repo_id is required")
        if self.selected_path and self.analysis_mode == "FULL":
            raise ValueError("Selected paths require INCREMENTAL or UNKNOWN scope")
        return self