from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModelSnapshot:
    source: str
    metadata: dict[str, Any]
    model_name: str
    fields: list[str]
    templates: dict[str, dict[str, str]]
    css: str
    raw_model: dict[str, Any] | None = None
    note_ids: list[int | str] | None = None
    card_ids: list[int | str] | None = None


@dataclass(frozen=True)
class NoteRecord:
    note_id: int | str
    model_name: str
    tags: tuple[str, ...]
    fields: dict[str, str]
    card_ids: tuple[int | str, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "noteId": self.note_id,
            "modelName": self.model_name,
            "tags": list(self.tags),
            "fields": self.fields,
            "cardIds": list(self.card_ids),
        }


@dataclass(frozen=True)
class NoteSnapshot:
    source: str
    metadata: dict[str, Any]
    notes: list[NoteRecord]


def load_model_snapshot(path: Path) -> ModelSnapshot:
    path = path.resolve()
    metadata = _read_json_optional(path / "metadata.json", {})
    raw_model = _read_json_optional(path / "model.json", None)
    fields = _load_fields(path, raw_model)
    templates = _load_templates(path, raw_model)
    css = _load_css(path, raw_model)
    note_ids = _read_json_optional(path / "note_ids.json", [])
    card_ids = _read_json_optional(path / "card_ids.json", [])
    model_name = str(metadata.get("model_name") or (raw_model or {}).get("name") or path.name)
    return ModelSnapshot(
        source=str(path),
        metadata=dict(metadata),
        model_name=model_name,
        fields=fields,
        templates=templates,
        css=css,
        raw_model=raw_model,
        note_ids=note_ids,
        card_ids=card_ids,
    )


def load_note_snapshot(path: Path) -> NoteSnapshot:
    path = path.resolve()
    metadata = _read_json_optional(path / "metadata.json", {})
    raw_notes = _read_json(path / "notes.json")
    notes = []
    for raw in raw_notes:
        notes.append(
            NoteRecord(
                note_id=raw["noteId"],
                model_name=raw.get("modelName", ""),
                tags=tuple(raw.get("tags", [])),
                fields={name: str(value) for name, value in raw.get("fields", {}).items()},
                card_ids=tuple(raw.get("cardIds", raw.get("cards", []))),
            )
        )
    return NoteSnapshot(source=str(path), metadata=dict(metadata), notes=notes)


def _load_fields(path: Path, raw_model: dict[str, Any] | None) -> list[str]:
    fields_path = path / "fields.json"
    if fields_path.exists():
        return [str(item) for item in _read_json(fields_path)]
    if raw_model:
        return [str(field.get("name", "")) for field in raw_model.get("flds", [])]
    return []


def _load_templates(
    path: Path,
    raw_model: dict[str, Any] | None,
) -> dict[str, dict[str, str]]:
    templates_path = path / "templates.json"
    if templates_path.exists():
        loaded = _read_json(templates_path)
        return {
            str(name): {str(side): str(value) for side, value in sides.items()}
            for name, sides in loaded.items()
        }
    if raw_model:
        return {
            str(template.get("name", "")): {
                "Front": str(template.get("qfmt", "")),
                "Back": str(template.get("afmt", "")),
            }
            for template in raw_model.get("tmpls", [])
        }
    return {}


def _load_css(path: Path, raw_model: dict[str, Any] | None) -> str:
    styling_path = path / "styling.json"
    if styling_path.exists():
        styling = _read_json(styling_path)
        return str(styling.get("css", ""))
    css_path = path / "css.css"
    if css_path.exists():
        return css_path.read_text()
    if raw_model:
        return str(raw_model.get("css", ""))
    return ""


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _read_json_optional(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return _read_json(path)
