import hashlib
import io
import json
import os
import re
import stat
import subprocess
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Iterator
from urllib.parse import urlsplit

import httpx
import openpyxl
import xlrd
from docx import Document

from .config import Settings
from .models import Artifact, ManualStory, SourceType

TEXT_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".java", ".kt",
    ".cs", ".go", ".rs", ".rb", ".php", ".c", ".cpp", ".h", ".hpp",
    ".swift", ".scala", ".sql", ".json", ".yaml", ".yml", ".toml",
    ".xml", ".html", ".css", ".scss", ".md", ".txt", ".graphql",
    ".proto", ".tf", ".ini", ".cfg", ".properties", ".sh", ".vue", ".svelte",
}
EXCLUDED_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    ".next", "coverage", "vendor", ".idea", ".vscode",
}
EXCLUDED_NAMES = {
    ".env", ".npmrc", ".pypirc", "id_rsa", "id_ed25519", "credentials",
    "package-lock.json", "bun.lock", "yarn.lock", "pnpm-lock.yaml",
}
MAX_DIAGNOSTIC_ENTRIES = 100


def safe_path(name: str) -> str:
    path = PurePosixPath(name.replace("\\", "/"))
    if (
        not name or path.is_absolute() or ".." in path.parts
        or re.match(r"^[A-Za-z]:", name)
        or any(ord(char) < 32 for char in name)
    ):
        raise ValueError(f"Unsafe artifact path: {name!r}")
    return str(path)


def excluded(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        bool(set(path.parts) & EXCLUDED_DIRS)
        or path.name in EXCLUDED_NAMES
        or path.name.startswith(".env.")
        or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx", ".jks"}
        or path.name.endswith((".min.js", ".map", ".gen.ts"))
    )


def checked_zip(data: bytes, settings: Settings) -> zipfile.ZipFile:
    archive = zipfile.ZipFile(io.BytesIO(data))
    try:
        members = archive.infolist()
        if len(members) > settings.max_files * 20:
            raise ValueError("Archive contains too many entries")
        total = 0
        for item in members:
            safe_path(item.filename)
            mode = item.external_attr >> 16
            if stat.S_ISLNK(mode) or item.flag_bits & 1:
                raise ValueError("Symlinks and encrypted archive members are not supported")
            total += item.file_size
            if total > settings.max_extracted_bytes:
                raise ValueError("Archive exceeds the expanded-size limit")
            if item.file_size > 1_000_000 and item.file_size > max(item.compress_size, 1) * 200:
                raise ValueError("Suspicious archive compression ratio")
        return archive
    except Exception:
        archive.close()
        raise


def check_office(data: bytes, settings: Settings):
    with checked_zip(data, settings) as archive:
        for item in archive.infolist():
            if item.filename.lower().endswith(".xml"):
                content = archive.read(item)
                if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
                    raise ValueError("XML entities and DTDs are not allowed in Office files")


class Extractor:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.warnings: list[str] = []
        self.excluded_files: list[str] = []
        self.unsupported_files: list[str] = []
        self.warning_count = 0
        self.excluded_count = 0
        self.unsupported_count = 0
        self.seen: set[tuple[str, str, str | None, int | None]] = set()
        self.file_count = 0
        self.expanded_bytes = 0

    @staticmethod
    def _remember(items: list[str], value: str):
        if len(items) < MAX_DIAGNOSTIC_ENTRIES:
            items.append(value)

    def _exclude(self, name: str):
        self.excluded_count += 1
        self._remember(self.excluded_files, name)

    def _unsupported(self, name: str):
        self.unsupported_count += 1
        self._remember(self.unsupported_files, name)

    def _warn(self, message: str):
        self.warning_count += 1
        self._remember(self.warnings, message)

    def _count_source(
        self, byte_count: int, file_limit: int | None, byte_limit: int | None,
    ):
        self.file_count += 1
        self.expanded_bytes += byte_count
        if self.file_count > (file_limit or self.settings.max_files):
            raise ValueError("Too many source files")
        if self.expanded_bytes > (byte_limit or self.settings.max_extracted_bytes):
            raise ValueError("Combined expanded artifacts exceed the size limit")

    def artifact(self, source_type: SourceType, name: str, content: str, **metadata) -> Artifact:
        if not content.strip() or content.strip() in {
            "{{Codebase_Data}}", "{{Design_Document_Data}}",
            "{{Jira_User_Stories_Data}}", "{{Raw_Requirements_Data}}",
        }:
            raise ValueError(f"No readable content in {name}")
        if len(content) > self.settings.max_artifact_characters:
            raise ValueError(f"{name} exceeds the per-artifact character limit; select a smaller scope")
        if any(ord(c) < 32 and c not in "\n\r\t" for c in content):
            raise ValueError(f"{name} contains binary/control characters")
        identity = (source_type, name, metadata.get("worksheet"), metadata.get("row"))
        if identity in self.seen:
            raise ValueError(f"Duplicate artifact identity: {name}")
        self.seen.add(identity)
        return Artifact(sourceType=source_type, sourceName=name, content=content, **metadata)

    def extract(
        self, name: str, data: bytes, kind: SourceType = "CODE",
        *, file_limit: int | None = None, byte_limit: int | None = None,
    ) -> list[Artifact]:
        name = safe_path(name)
        self._count_source(len(data), file_limit, byte_limit)
        if kind == "CODE" and excluded(name):
            self._exclude(name)
            return []
        suffix = PurePosixPath(name).suffix.lower()
        if suffix == ".zip" and kind == "CODE":
            result = []
            with checked_zip(data, self.settings) as archive:
                for member in archive.infolist():
                    if member.is_dir():
                        continue
                    member_name = safe_path(member.filename)
                    if excluded(member_name):
                        self._exclude(member_name)
                        continue
                    if PurePosixPath(member_name).suffix.lower() in {".zip", ".tar", ".gz", ".7z"}:
                        raise ValueError("Nested archives are not supported; upload one source ZIP")
                    result.extend(self.extract(
                        member_name, archive.read(member), kind,
                        file_limit=file_limit, byte_limit=byte_limit,
                    ))
            return result
        if kind == "DESIGN_DOCUMENT" and suffix == ".docx":
            check_office(data, self.settings)
            document = Document(io.BytesIO(data))
            lines = [p.text for p in document.paragraphs if p.text.strip()]
            for table in document.tables:
                lines.extend(" | ".join(cell.text for cell in row.cells) for row in table.rows)
            return [self.artifact(kind, name, "\n".join(lines))]
        if kind == "RAW_REQUIREMENT" and suffix in {".xlsx", ".xls"}:
            return self.workbook(name, data, suffix)
        if kind == "JIRA_USER_STORY" and suffix == ".json":
            stories = json.loads(data)
            if not isinstance(stories, list) or not stories:
                raise ValueError("Story JSON must contain a nonempty array of manual story objects")
            if len(stories) > 100:
                raise ValueError("Story JSON is limited to 100 stories")
            return [
                self.story(ManualStory.model_validate(item), f"{name}#{index + 1}")
                for index, item in enumerate(stories)
            ]
        if kind != "CODE" and suffix not in {".txt", ".md"}:
            raise ValueError(f"Unsupported {kind} file: {name}")
        if kind == "CODE" and suffix not in TEXT_EXTENSIONS and PurePosixPath(name).name not in {
            "Dockerfile", "Makefile", "Jenkinsfile", "Procfile",
        }:
            self._unsupported(name)
            return []
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise ValueError(f"{name} is not readable UTF-8 text") from error
        if not text.strip():
            self._warn(f"Empty file omitted: {name}")
            return []
        metadata = (
            {"filePath": name, "sha256": hashlib.sha256(data).hexdigest()}
            if kind == "CODE" else {}
        )
        return [self.artifact(kind, name, text, **metadata)]

    def workbook(self, name: str, data: bytes, suffix: str) -> list[Artifact]:
        result = []
        if suffix == ".xlsx":
            check_office(data, self.settings)
            workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=False)
            try:
                for sheet in workbook:
                    self.sheet_rows(name, sheet.title, sheet.iter_rows(values_only=True), result)
            finally:
                workbook.close()
        else:
            workbook = xlrd.open_workbook(file_contents=data, on_demand=True)
            try:
                for sheet in workbook.sheets():
                    self.sheet_rows(
                        name, sheet.name,
                        (sheet.row_values(index) for index in range(sheet.nrows)), result,
                    )
            finally:
                workbook.release_resources()
        if not result:
            raise ValueError(f"Workbook {name} has no readable rows")
        return result

    def sheet_rows(self, name: str, worksheet: str, rows, result: list[Artifact]):
        # Preserve raw cells, not guessed column mappings or invented requirement IDs.
        for index, values in enumerate(rows, 1):
            if index > 10_000:
                raise ValueError(f"{name}/{worksheet} exceeds 10,000 rows")
            if len(values) > 200:
                raise ValueError(f"{name}/{worksheet} exceeds 200 columns")
            if not any(value is not None and str(value).strip() for value in values):
                continue
            content = json.dumps(
                {openpyxl.utils.get_column_letter(i): str(value)
                 for i, value in enumerate(values, 1) if value is not None},
                ensure_ascii=False,
            )
            result.append(self.artifact(
                "RAW_REQUIREMENT", name, content, worksheet=worksheet, row=index,
            ))

    def story(self, story: ManualStory, source_name: str | None = None) -> Artifact:
        return self.artifact(
            "JIRA_USER_STORY", source_name or f"manual:{story.id}",
            story.model_dump_json(), externalId=story.id,
        )

    def iter_directory(
        self, root: Path, prefix: str = "", *,
        file_limit: int | None = None, byte_limit: int | None = None,
        recursive: bool = True,
    ) -> Iterator[Artifact]:
        file_limit = file_limit or self.settings.max_repository_files
        byte_limit = byte_limit or self.settings.max_repository_bytes
        for directory, names, files in os.walk(root, followlinks=False):
            names[:] = (
                sorted(n for n in names if n not in EXCLUDED_DIRS) if recursive else []
            )
            for filename in sorted(files):
                path = Path(directory) / filename
                relative = path.relative_to(root).as_posix()
                if path.is_symlink() or excluded(relative):
                    self._exclude(relative)
                    continue
                source_path = (PurePosixPath(prefix) / relative).as_posix()
                size = path.stat().st_size
                if size > self.settings.max_repository_file_bytes:
                    self._count_source(size, file_limit, byte_limit)
                    self._unsupported(source_path)
                    self._warn(f"File exceeds the per-file size limit and was omitted: {source_path}")
                    continue
                try:
                    yield from self.extract(
                        source_path, path.read_bytes(),
                        file_limit=file_limit, byte_limit=byte_limit,
                    )
                except ValueError as error:
                    message = str(error)
                    if (
                        "per-artifact character limit" in message
                        or "not readable UTF-8 text" in message
                        or "binary/control characters" in message
                    ):
                        self._unsupported(source_path)
                        self._warn(f"Unreadable or oversized file was omitted: {source_path}")
                        continue
                    raise

    def directory(self, root: Path, prefix: str = "") -> list[Artifact]:
        return list(self.iter_directory(root, prefix))


def adf_text(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        text = value.get("text", "")
        children = "\n".join(adf_text(child) for child in value.get("content", []))
        return "\n".join(part for part in (text, children) if part)
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=False)


def jira_stories(keys: list[str], settings: Settings, extractor: Extractor) -> list[Artifact]:
    if not keys:
        return []
    if not settings.jira_base_url or not settings.jira_token.get_secret_value():
        raise ValueError("Jira integration is not configured on the backend")
    if settings.jira_api_version not in {"2", "3"}:
        raise ValueError("TIP_JIRA_API_VERSION must be 2 or 3")
    fields = ["summary", "description", "priority", "status", "labels", "components"]
    if settings.jira_acceptance_field:
        if not re.fullmatch(r"customfield_\d+", settings.jira_acceptance_field):
            raise ValueError("TIP_JIRA_ACCEPTANCE_FIELD must identify a customfield number")
        fields.append(settings.jira_acceptance_field)
    token = settings.jira_token.get_secret_value()
    auth = (settings.jira_email, token) if settings.jira_email else None
    headers = {} if auth else {"Authorization": f"Bearer {token}"}
    result = []
    with httpx.Client(timeout=30, follow_redirects=False, auth=auth, headers=headers) as client:
        for key in dict.fromkeys(keys):
            response = client.get(
                f"{settings.jira_base_url}/rest/api/{settings.jira_api_version}/issue/{key}",
                params={"fields": ",".join(fields)},
            )
            if response.status_code != 200:
                raise ValueError(f"Jira returned HTTP {response.status_code} for {key}")
            issue = response.json()
            supplied = issue.get("fields")
            if not isinstance(supplied, dict) or not supplied.get("summary"):
                raise ValueError(f"Jira returned no readable story for {key}")
            content = {
                "id": issue.get("key", key),
                "title": supplied["summary"],
                "description": adf_text(supplied.get("description")),
                "priority": supplied.get("priority"),
                "status": supplied.get("status"),
                "labels": supplied.get("labels"),
                "components": supplied.get("components"),
            }
            if settings.jira_acceptance_field in supplied:
                content["acceptanceCriteria"] = adf_text(
                    supplied[settings.jira_acceptance_field]
                )
            result.append(extractor.artifact(
                "JIRA_USER_STORY", f"jira:{key}",
                json.dumps(content, ensure_ascii=False), externalId=key,
            ))
    return result


def selected_root(root: Path, selected_path: str | None) -> Path:
    if not selected_path:
        return root
    selected_path = safe_path(selected_path)
    if excluded(selected_path):
        raise ValueError("Selected path is excluded from source analysis")
    selected = (root / selected_path).resolve()
    if not selected.is_relative_to(root.resolve()) or not selected.is_dir():
        raise ValueError("Selected path must be an existing directory inside the source root")
    return selected


@contextmanager
def source_directory(settings: Settings, *, repo_url=None, local_path=None,
                     branch=None, selected_path=None):
    if local_path:
        if not settings.local_source_root:
            raise ValueError("Server directory access is disabled; use a browser folder upload")
        allowed = settings.local_source_root.resolve()
        root = Path(local_path).resolve()
        if not root.is_relative_to(allowed) or not root.is_dir():
            raise ValueError("Local path is outside TIP_LOCAL_SOURCE_ROOT or is not a directory")
        yield selected_root(root, selected_path)
        return
    sparse_path = safe_path(selected_path) if selected_path else None
    if sparse_path == ".":
        sparse_path = None
    if sparse_path and excluded(sparse_path):
        raise ValueError("Selected path is excluded from source analysis")
    url = urlsplit(repo_url or "")
    allowed_hosts = {host.strip().lower() for host in settings.repository_hosts.split(",")}
    if (
        url.scheme != "https" or not url.hostname or url.hostname.lower() not in allowed_hosts
        or url.username or url.password or url.query or url.fragment
        or url.port not in {None, 443}
        or not re.fullmatch(r"/[A-Za-z0-9._/-]+", url.path)
        or ".." in PurePosixPath(url.path).parts
    ):
        raise ValueError(
            "Repository must be a credential-free HTTPS URL on an allowed host listed in TIP_REPOSITORY_HOSTS"
        )
    if branch and (branch.startswith("-") or not re.fullmatch(r"[\w./-]+", branch)):
        raise ValueError("Invalid branch name")
    environment = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_LFS_SKIP_SMUDGE": "1",
    }

    def run_git(command):
        try:
            return subprocess.run(
                command, capture_output=True,
                timeout=settings.repository_clone_timeout_seconds,
                check=False, env=environment,
            )
        except subprocess.TimeoutExpired as error:
            raise ValueError(
                "Repository clone or checkout exceeded the "
                f"{settings.repository_clone_timeout_seconds}-second timeout"
            ) from error

    with tempfile.TemporaryDirectory(prefix="tip-repo-") as directory:
        target = Path(directory) / "source"
        command = [
            "git", "-c", "core.hooksPath=/dev/null", "-c", "protocol.file.allow=never",
            "clone", "--depth=1", "--single-branch",
        ]
        if sparse_path:
            command.extend(["--filter=blob:none", "--no-checkout"])
        if branch:
            command.extend(["--branch", branch])
        command.extend(["--", repo_url, str(target)])
        process = run_git(command)
        if process.returncode:
            raise ValueError(
                "Repository clone failed; check URL, branch, and backend Git credentials"
            )
        if sparse_path:
            checkout_commands = (
                ["git", "-C", str(target), "sparse-checkout", "init", "--cone"],
                ["git", "-C", str(target), "sparse-checkout", "set", "--cone", "--", sparse_path],
                ["git", "-C", str(target), "checkout"],
            )
            for checkout_command in checkout_commands:
                if run_git(checkout_command).returncode:
                    raise ValueError(
                        "Repository subdirectory checkout failed; check the path and backend Git version"
                    )
        yield selected_root(target, sparse_path)