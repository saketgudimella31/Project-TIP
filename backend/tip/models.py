from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    jiraUserStoriesProvided: bool
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
    plantUml: str
    sourceEvidence: list[Evidence]
    reason: str

    @model_validator(mode="after")
    def valid_shape(self):
        if self.generated:
            if not all([self.title, self.plantUml, self.sourceEvidence]):
                raise ValueError("Generated diagrams require a title, UML, and evidence")
        elif (
            self.title or self.description or self.plantUml or self.sourceEvidence
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
        if (self.focus or self.selected_path) and self.analysis_mode == "FULL":
            raise ValueError("Selected paths or retrieval focus require INCREMENTAL or UNKNOWN scope")
        return self