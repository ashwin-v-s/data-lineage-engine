from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ImportAsset(StrictModel):
    id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    namespace: str = Field(default="general", min_length=1, max_length=200)
    type: str = Field(default="asset", min_length=1, max_length=80)
    kind: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=50)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id", "name", "namespace", "type")
    @classmethod
    def nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class ImportRelationship(StrictModel):
    source_id: str = Field(min_length=1, max_length=200)
    target_id: str = Field(min_length=1, max_length=200)
    type: str = Field(default="declared_dependency", min_length=1, max_length=120)
    provenance: str | None = Field(default=None, max_length=1000)


class ImportSource(StrictModel):
    kind: Literal["upload"]
    ref: str = Field(min_length=1, max_length=255)


class ImportEnvelope(StrictModel):
    contract_version: Literal["kairos.ingest.v1"]
    source: ImportSource
    idempotency_key: str = Field(min_length=1, max_length=256)
    assets: list[ImportAsset] = Field(max_length=1000)
    relationships: list[ImportRelationship] = Field(default_factory=list, max_length=2000)

    @field_validator("idempotency_key")
    @classmethod
    def valid_key(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value
