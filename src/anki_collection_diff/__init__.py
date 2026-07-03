"""Compare generated Anki APKG files with a live Anki collection."""

from .ankiconnect import AnkiConnectClient, AnkiConnectError
from .apkg import ApkgError, load_apkg_snapshot
from .diff import (
    DiffReport,
    compare_collection_snapshots,
    compare_model_snapshots,
    compare_note_snapshots,
)
from .snapshots import (
    CollectionSnapshot,
    ModelSnapshot,
    NoteSnapshot,
    load_model_snapshot,
    load_note_snapshot,
)

__all__ = [
    "AnkiConnectClient",
    "AnkiConnectError",
    "ApkgError",
    "CollectionSnapshot",
    "DiffReport",
    "ModelSnapshot",
    "NoteSnapshot",
    "compare_collection_snapshots",
    "compare_model_snapshots",
    "compare_note_snapshots",
    "load_apkg_snapshot",
    "load_model_snapshot",
    "load_note_snapshot",
]
