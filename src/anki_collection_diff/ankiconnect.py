from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from .snapshots import ModelSnapshot, NoteRecord, NoteSnapshot
from .util import dump_json, slugify, timestamp_for_path


class AnkiConnectError(RuntimeError):
    """Raised when AnkiConnect is unavailable or returns an error."""


class AnkiConnectClient:
    def __init__(self, url: str = "http://127.0.0.1:8765", version: int = 6, timeout: int = 30):
        self.url = url
        self.version = version
        self.timeout = timeout

    def invoke(self, action: str, params: dict[str, Any] | None = None) -> Any:
        payload = {"action": action, "version": self.version, "params": params or {}}
        request = Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except URLError as exc:
            raise AnkiConnectError(
                f"Could not reach AnkiConnect at {self.url}. Is Anki open?"
            ) from exc

        if body.get("error"):
            raise AnkiConnectError(f"AnkiConnect {action} failed: {body['error']}")
        return body["result"]

    def fetch_model_snapshot(self, model_name: str, deck_name: str | None = None) -> ModelSnapshot:
        version = self.invoke("version")
        models = self.invoke("findModelsByName", {"modelNames": [model_name]})
        if not models:
            raise AnkiConnectError(f"Model not found: {model_name}")

        fields = list(self.invoke("modelFieldNames", {"modelName": model_name}))
        templates = dict(self.invoke("modelTemplates", {"modelName": model_name}))
        styling = dict(self.invoke("modelStyling", {"modelName": model_name}))

        query = None
        note_ids: list[int | str] = []
        card_ids: list[int | str] = []
        if deck_name:
            query = f'deck:"{deck_name}" note:"{model_name}"'
            note_ids = list(self.invoke("findNotes", {"query": query}))
            card_ids = list(self.invoke("findCards", {"query": query}))

        raw_model = dict(models[0])
        metadata = {
            "exported_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "ankiconnect_version": version,
            "model_name": model_name,
            "model_id": raw_model.get("id"),
            "deck_name": deck_name,
            "query": query,
            "note_count": len(note_ids),
            "card_count": len(card_ids),
        }
        return ModelSnapshot(
            source=f"live:{model_name}",
            metadata=metadata,
            model_name=model_name,
            fields=fields,
            templates=templates,
            css=str(styling.get("css", "")),
            raw_model=raw_model,
            note_ids=note_ids,
            card_ids=card_ids,
        )

    def fetch_note_snapshot(
        self,
        *,
        model_name: str,
        deck_name: str | None = None,
        query: str | None = None,
    ) -> NoteSnapshot:
        if not query:
            if not deck_name:
                raise ValueError("Either deck_name or query is required.")
            query = f'deck:"{deck_name}" note:"{model_name}"'

        version = self.invoke("version")
        note_ids = self.invoke("findNotes", {"query": query})
        notes = self.invoke("notesInfo", {"notes": note_ids})
        records = []
        for note in notes:
            records.append(
                NoteRecord(
                    note_id=note["noteId"],
                    model_name=note["modelName"],
                    tags=tuple(note.get("tags", [])),
                    fields={
                        name: str(payload.get("value", ""))
                        for name, payload in note.get("fields", {}).items()
                    },
                    card_ids=tuple(note.get("cards", [])),
                )
            )

        metadata = {
            "exported_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "ankiconnect_version": version,
            "model_name": model_name,
            "deck_name": deck_name,
            "query": query,
            "note_count": len(records),
        }
        return NoteSnapshot(source=f"live:{query}", metadata=metadata, notes=records)

    def export_model_snapshot(
        self,
        *,
        output_root: Path,
        model_name: str,
        deck_name: str | None = None,
        timestamp: str | None = None,
    ) -> Path:
        snapshot = self.fetch_model_snapshot(model_name, deck_name)
        timestamp = timestamp or timestamp_for_path()
        snapshot_dir = output_root / "templates" / slugify(model_name) / timestamp
        template_dir = snapshot_dir / "templates"
        template_dir.mkdir(parents=True, exist_ok=True)

        raw_model = snapshot.raw_model or {}
        for template in raw_model.get("tmpls", []):
            template_slug = f"{template['ord']:02d}-{slugify(template['name'])}"
            current_dir = template_dir / template_slug
            current_dir.mkdir(parents=True, exist_ok=True)
            (current_dir / "front.html").write_text(str(template.get("qfmt", "")))
            (current_dir / "back.html").write_text(str(template.get("afmt", "")))

        metadata = dict(snapshot.metadata)
        metadata["snapshot_dir"] = str(snapshot_dir)
        (snapshot_dir / "css.css").write_text(snapshot.css)
        dump_json(snapshot_dir / "model.json", raw_model)
        dump_json(snapshot_dir / "fields.json", snapshot.fields)
        dump_json(snapshot_dir / "templates.json", snapshot.templates)
        dump_json(snapshot_dir / "styling.json", {"css": snapshot.css})
        dump_json(snapshot_dir / "note_ids.json", snapshot.note_ids)
        dump_json(snapshot_dir / "card_ids.json", snapshot.card_ids)
        dump_json(snapshot_dir / "metadata.json", metadata)
        return snapshot_dir

    def export_note_snapshot(
        self,
        *,
        output_root: Path,
        model_name: str,
        deck_name: str,
        timestamp: str | None = None,
        label: str = "snapshot",
    ) -> Path:
        snapshot = self.fetch_note_snapshot(model_name=model_name, deck_name=deck_name)
        timestamp = timestamp or timestamp_for_path()
        out_dir = (
            output_root
            / "backups"
            / "note-field-snapshots"
            / slugify(model_name)
            / f"{timestamp}-{slugify(label)}"
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        dump_json(out_dir / "metadata.json", snapshot.metadata)
        dump_json(out_dir / "notes.json", [note.to_json() for note in snapshot.notes])
        return out_dir
