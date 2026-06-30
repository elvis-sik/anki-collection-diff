from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TargetConfig:
    name: str
    model_name: str
    deck_name: str | None = None
    query: str | None = None
    model_snapshot: Path | None = None
    note_snapshot: Path | None = None
    key_fields: tuple[str, ...] = ()
    fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class AuditConfig:
    ankiconnect_url: str
    targets: tuple[TargetConfig, ...]


def load_audit_config(path: Path) -> AuditConfig:
    data = tomllib.loads(path.read_text())
    base = path.parent
    collection = data.get("collection", {})
    targets = []

    for item in data.get("targets", []):
        targets.append(
            TargetConfig(
                name=str(item["name"]),
                model_name=str(item["model_name"]),
                deck_name=item.get("deck_name"),
                query=item.get("query"),
                model_snapshot=_optional_path(base, item.get("model_snapshot")),
                note_snapshot=_optional_path(base, item.get("note_snapshot")),
                key_fields=tuple(item.get("key_fields", [])),
                fields=tuple(item.get("fields", [])),
            )
        )

    return AuditConfig(
        ankiconnect_url=str(collection.get("ankiconnect_url", "http://127.0.0.1:8765")),
        targets=tuple(targets),
    )


def _optional_path(base: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    return (base / path).resolve()
