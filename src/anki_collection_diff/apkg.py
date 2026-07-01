from __future__ import annotations

import json
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .snapshots import CardRecord, CollectionSnapshot, ModelSnapshot, NoteRecord

FIELD_SEPARATOR = "\x1f"


class ApkgError(RuntimeError):
    """Raised when an APKG cannot be read as an Anki package."""


@dataclass(frozen=True)
class ApkgSummary:
    path: Path
    deck_names: tuple[str, ...]
    candidate_deck_names: tuple[str, ...]
    model_names: tuple[str, ...]
    note_count: int
    card_count: int
    media_count: int

    def to_json(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "deckNames": list(self.deck_names),
            "candidateDeckNames": list(self.candidate_deck_names),
            "modelNames": list(self.model_names),
            "noteCount": self.note_count,
            "cardCount": self.card_count,
            "mediaCount": self.media_count,
        }


def inspect_apkg(path: Path) -> ApkgSummary:
    snapshot = load_apkg_snapshot(path)
    return ApkgSummary(
        path=path.resolve(),
        deck_names=snapshot.deck_names,
        candidate_deck_names=tuple(snapshot.metadata.get("candidate_deck_names", [])),
        model_names=tuple(sorted(snapshot.models)),
        note_count=len(snapshot.notes),
        card_count=len(snapshot.cards),
        media_count=len(snapshot.media_names),
    )


def load_apkg_snapshot(
    path: Path,
    *,
    deck_name: str | None = None,
    include_subdecks: bool = True,
) -> CollectionSnapshot:
    path = path.resolve()
    with zipfile.ZipFile(path) as package, tempfile.TemporaryDirectory() as tmp:
        collection_member = _find_collection_member(package)
        db_path = Path(tmp) / collection_member
        db_path.write_bytes(package.read(collection_member))
        media_names = _load_media_names(package)
        return _load_collection_db(
            db_path,
            source=str(path),
            media_names=media_names,
            deck_name=deck_name,
            include_subdecks=include_subdecks,
        )


def _find_collection_member(package: zipfile.ZipFile) -> str:
    names = set(package.namelist())
    for candidate in ("collection.anki21b", "collection.anki21", "collection.anki2"):
        if candidate in names:
            return candidate
    raise ApkgError("APKG does not contain collection.anki2/anki21/anki21b.")


def _load_media_names(package: zipfile.ZipFile) -> tuple[str, ...]:
    if "media" not in package.namelist():
        return ()
    media = json.loads(package.read("media").decode("utf-8"))
    return tuple(sorted(str(name) for name in media.values()))


def _load_collection_db(
    db_path: Path,
    *,
    source: str,
    media_names: tuple[str, ...],
    deck_name: str | None,
    include_subdecks: bool,
) -> CollectionSnapshot:
    connection = sqlite3.connect(db_path)
    try:
        decks_raw, models_raw = connection.execute("select decks, models from col").fetchone()
        decks_by_id = {int(key): value for key, value in json.loads(decks_raw).items()}
        models_by_id = {int(key): value for key, value in json.loads(models_raw).items()}

        all_deck_names = tuple(
            sorted(deck["name"] for deck in decks_by_id.values() if deck["name"] != "Default")
        )
        selected_deck_ids = _select_deck_ids(decks_by_id, deck_name, include_subdecks)
        cards_rows = _select_cards(connection, selected_deck_ids)
        selected_note_ids = {row["nid"] for row in cards_rows}
        notes_rows = _select_notes(connection, selected_note_ids)
    finally:
        connection.close()

    notes_by_id = {row["id"]: row for row in notes_rows}
    used_model_ids = {row["mid"] for row in notes_rows}
    models = {
        models_by_id[model_id]["name"]: _model_snapshot(source, models_by_id[model_id])
        for model_id in used_model_ids
    }

    notes = [
        _note_record(row, models_by_id[row["mid"]], _card_ids_for_note(cards_rows, row["id"]))
        for row in sorted(notes_rows, key=lambda item: item["id"])
    ]
    cards = [
        _card_record(row, notes_by_id[row["nid"]], decks_by_id, models_by_id)
        for row in sorted(cards_rows, key=lambda item: item["id"])
        if row["nid"] in notes_by_id
    ]

    selected_deck_names = tuple(
        sorted({card.deck_name for card in cards if card.deck_name != "Default"})
    )
    metadata = {
        "apkg_deck_name_filter": deck_name,
        "apkg_deck_names": all_deck_names,
        "candidate_deck_names": _candidate_deck_names(all_deck_names),
        "note_count": len(notes),
        "card_count": len(cards),
        "media_count": len(media_names),
    }
    return CollectionSnapshot(
        source=source,
        metadata=metadata,
        deck_names=selected_deck_names,
        models=models,
        notes=notes,
        cards=cards,
        media_names=media_names,
    )


def _select_deck_ids(
    decks_by_id: dict[int, dict[str, Any]],
    deck_name: str | None,
    include_subdecks: bool,
) -> set[int]:
    if deck_name:
        selected = {
            deck_id
            for deck_id, deck in decks_by_id.items()
            if deck["name"] == deck_name
            or (include_subdecks and deck["name"].startswith(f"{deck_name}::"))
        }
        if not selected:
            raise ApkgError(f"Deck not found in APKG: {deck_name}")
        return selected

    non_default = {deck_id for deck_id, deck in decks_by_id.items() if deck["name"] != "Default"}
    return non_default or set(decks_by_id)


def _select_cards(connection: sqlite3.Connection, deck_ids: set[int]) -> list[dict[str, Any]]:
    rows = connection.execute("select id, nid, did, ord from cards").fetchall()
    return [
        {"id": row[0], "nid": row[1], "did": row[2], "ord": row[3]}
        for row in rows
        if row[2] in deck_ids
    ]


def _select_notes(connection: sqlite3.Connection, note_ids: set[int]) -> list[dict[str, Any]]:
    if not note_ids:
        return []
    rows = connection.execute("select id, guid, mid, flds, tags from notes").fetchall()
    return [
        {"id": row[0], "guid": row[1], "mid": row[2], "flds": row[3], "tags": row[4]}
        for row in rows
        if row[0] in note_ids
    ]


def _model_snapshot(source: str, model: dict[str, Any]) -> ModelSnapshot:
    templates = {
        str(template.get("name", "")): {
            "Front": str(template.get("qfmt", "")),
            "Back": str(template.get("afmt", "")),
        }
        for template in model.get("tmpls", [])
    }
    fields = [str(field.get("name", "")) for field in model.get("flds", [])]
    return ModelSnapshot(
        source=source,
        metadata={"model_id": model.get("id")},
        model_name=str(model.get("name", "")),
        fields=fields,
        templates=templates,
        css=str(model.get("css", "")),
        raw_model=model,
    )


def _note_record(
    row: dict[str, Any],
    model: dict[str, Any],
    card_ids: tuple[int | str, ...],
) -> NoteRecord:
    field_names = [str(field.get("name", "")) for field in model.get("flds", [])]
    values = str(row["flds"]).split(FIELD_SEPARATOR)
    fields = {
        name: values[index] if index < len(values) else ""
        for index, name in enumerate(field_names)
    }
    for index, value in enumerate(values[len(field_names) :], start=len(field_names)):
        fields[f"__extra_{index}"] = value
    return NoteRecord(
        note_id=row["id"],
        guid=str(row["guid"]),
        model_name=str(model.get("name", "")),
        tags=tuple(str(row["tags"]).split()),
        fields=fields,
        card_ids=card_ids,
    )


def _card_ids_for_note(cards_rows: list[dict[str, Any]], note_id: int) -> tuple[int | str, ...]:
    return tuple(row["id"] for row in cards_rows if row["nid"] == note_id)


def _card_record(
    row: dict[str, Any],
    note_row: dict[str, Any],
    decks_by_id: dict[int, dict[str, Any]],
    models_by_id: dict[int, dict[str, Any]],
) -> CardRecord:
    model = models_by_id[note_row["mid"]]
    template_ord = int(row["ord"])
    template_name = _template_name(model, template_ord)
    return CardRecord(
        card_id=row["id"],
        note_id=row["nid"],
        deck_name=str(decks_by_id[row["did"]]["name"]),
        model_name=str(model.get("name", "")),
        template_ord=template_ord,
        template_name=template_name,
    )


def _template_name(model: dict[str, Any], ord_value: int) -> str:
    for template in model.get("tmpls", []):
        if int(template.get("ord", -1)) == ord_value:
            return str(template.get("name", ord_value))
    return str(ord_value)


def _candidate_deck_names(deck_names: tuple[str, ...]) -> tuple[str, ...]:
    candidates = list(deck_names)
    common = _common_deck_parent(deck_names)
    if common and common not in candidates:
        candidates.insert(0, common)
    return tuple(candidates)


def _common_deck_parent(deck_names: tuple[str, ...]) -> str | None:
    if len(deck_names) < 2:
        return None
    split = [name.split("::") for name in deck_names]
    prefix: list[str] = []
    for parts in zip(*split):
        if len(set(parts)) != 1:
            break
        prefix.append(parts[0])
    return "::".join(prefix) if prefix else None
