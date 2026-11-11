import json
from pathlib import Path
from urllib.parse import urlsplit
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TIP_", env_file=".env", extra="ignore"
    )

    data_dir: Path = Path("./data")
    graph_backend: Literal["kuzu", "sqlite"] = "kuzu"
    embedding_provider: Literal["hash", "sentence_transformers"] = "hash"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = Field(default=384, ge=32, le=4096)
    rag_chunk_characters: int = Field(default=2000, ge=200, le=10000)
    gateway_url: str = ""
    gateway_model: str = "azure-openai-5-2"
    gateway_headers_json: SecretStr = SecretStr(
        '{"api-key":"{api_key}","Client-Request-Id":"{request_id}",'
        '"Timestamp":"{timestamp}","Authorization":"{signature}",'
        '"Accept":"application/json"}'
    )
    gateway_hmac_secret: SecretStr = SecretStr("")
    gateway_api_key: SecretStr = SecretStr("")
    gateway_app_consumer_key: SecretStr = SecretStr("")
    gateway_signature_template: str = "{api_key}{request_id}{timestamp}{body}"
    gateway_timeout: float = Field(default=180, gt=0, le=600)
    max_model_characters: int = Field(default=300_000, gt=0)
    max_upload_bytes: int = Field(default=30_000_000, gt=0)
    max_extracted_bytes: int = Field(default=60_000_000, gt=0)
    max_files: int = Field(default=500, gt=0)
    max_artifact_characters: int = Field(default=150_000, gt=0)
    max_repository_files: int = Field(default=500_000, ge=1, le=1_000_000)
    max_repository_bytes: int = Field(default=5_000_000_000, gt=0)
    max_repository_file_bytes: int = Field(default=30_000_000, gt=0)
    repository_clone_timeout_seconds: int = Field(default=600, ge=10, le=1800)
    repository_index_batch_files: int = Field(default=100, ge=1, le=2_000)
    max_analysis_files: int = Field(default=100, ge=1, le=100)
    max_analysis_characters: int = Field(default=150_000, gt=0)
    analysis_batch_files: int = Field(default=5, ge=1, le=100)
    analysis_batch_characters: int = Field(default=25_000, gt=0)
    max_graph_index_files: int = Field(default=5_000, ge=1)
    max_graph_index_characters: int = Field(default=25_000_000, gt=0)
    max_knowledge_index_files: int = Field(default=500, ge=1)
    max_knowledge_index_characters: int = Field(default=5_000_000, gt=0)
    max_concurrent_tasks: int = Field(default=2, ge=1, le=8)
    repository_hosts: str = (
        "github.com,gitlab.com,bitbucket.org,gitlab.onefiserv.net"
    )
    local_source_root: Path | None = None
    jira_base_url: str = ""
    jira_email: str = ""
    jira_token: SecretStr = SecretStr("")
    jira_api_version: str = "3"
    jira_acceptance_field: str = ""
    # Optional existing RAG service. Its summaries select local source files;
    # they are never substituted for implementation evidence.
    rag_base_url: str = ""

    @field_validator("local_source_root", mode="before")
    @classmethod
    def empty_optional_path(cls, value):
        return None if value == "" else value

    @field_validator("gateway_url", "jira_base_url", "rag_base_url")
    @classmethod
    def safe_service_url(cls, value: str) -> str:
        if not value:
            return value
        url = urlsplit(value)
        if (
            not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
            or (
                url.scheme != "https"
                and not (
                    url.scheme == "http"
                    and url.hostname in {"localhost", "127.0.0.1", "::1"}
                )
            )
        ):
            raise ValueError("Service URL must be HTTPS (HTTP is allowed on loopback only)")
        return value.rstrip("/")

    def header_templates(self) -> dict[str, str]:
        value = json.loads(self.gateway_headers_json.get_secret_value())
        if not isinstance(value, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in value.items()
        ):
            raise ValueError("TIP_GATEWAY_HEADERS_JSON must be a JSON string-to-string map")
        return value

    @property
    def gateway_auth_configured(self) -> bool:
        return bool(
            self.gateway_signing_key()
            and self.gateway_hmac_secret.get_secret_value()
            and self.gateway_signature_template
        )

    def gateway_signing_key(self) -> str:
        consumer_key = self.gateway_app_consumer_key.get_secret_value()
        api_key = self.gateway_api_key.get_secret_value()
        if consumer_key and api_key and consumer_key != api_key:
            raise ValueError(
                "TIP_GATEWAY_API_KEY and TIP_GATEWAY_APP_CONSUMER_KEY must match: "
                "the Postman script sets apiKey from AppConsumerKey"
            )
        return consumer_key or api_key
