from __future__ import annotations

import difflib
import json
from dataclasses import dataclass, field
from collections import Counter
from typing import Any, Iterable

from .snapshots import CollectionSnapshot, ModelSnapshot, NoteRecord, NoteSnapshot


@dataclass(frozen=True)
class Difference:
    path: str
    summary: str
    expected: Any = None
    actual: Any = None
    diff: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "summary": self.summary,
            "expected": self.expected,
            "actual": self.actual,
            "diff": list(self.diff),
        }


@dataclass
class DiffReport:
    title: str
    expected_source: str
    actual_source: str
    differences: list[Difference] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def changed(self) -> bool:
        return bool(self.differences)

    def extend(self, other: "DiffReport") -> None:
        self.differences.extend(other.differences)

    def to_json(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "expected_source": self.expected_source,
            "actual_source": self.actual_source,
            "changed": self.changed,
            "metadata": self.metadata,
            "differences": [difference.to_json() for difference in self.differences],
        }

    def to_markdown(self, *, max_diff_lines: int = 80) -> str:
        lines = [
            f"# {self.title}",
            "",
            f"- expected: `{self.expected_source}`",
            f"- actual: `{self.actual_source}`",
            f"- differences: {len(self.differences)}",
        ]
        if not self.differences:
            lines.append("")
            lines.append("No differences found.")
            return "\n".join(lines) + "\n"

        for index, difference in enumerate(self.differences, start=1):
            lines.append("")
            lines.append(f"## {index}. {difference.path}")
            lines.append("")
            lines.append(difference.summary)
            if difference.diff:
                clipped = list(difference.diff[:max_diff_lines])
                if len(difference.diff) > max_diff_lines:
                    clipped.append(
                        f"... {len(difference.diff) - max_diff_lines} more diff lines omitted"
                    )
                lines.append("")
                lines.append("```diff")
                lines.extend(clipped)
                lines.append("```")
        return "\n".join(lines) + "\n"


def compare_model_snapshots(expected: ModelSnapshot, actual: ModelSnapshot) -> DiffReport:
    report = DiffReport(
        title=f"Model diff: {expected.model_name}",
        expected_source=expected.source,
        actual_source=actual.source,
        metadata={
            "expected_model_name": expected.model_name,
            "actual_model_name": actual.model_name,
        },
    )

    if expected.model_name != actual.model_name:
        report.differences.append(
            Difference(
                path="model.name",
                summary="Model names differ.",
                expected=expected.model_name,
                actual=actual.model_name,
            )
        )

    if expected.fields != actual.fields:
        report.differences.append(
            Difference(
                path="model.fields",
                summary="Field names or field order differ.",
                expected=expected.fields,
                actual=actual.fields,
                diff=_unified_json_diff(expected.fields, actual.fields, "expected fields", "actual fields"),
            )
        )

    expected_template_names = set(expected.templates)
    actual_template_names = set(actual.templates)
    for name in sorted(expected_template_names - actual_template_names):
        report.differences.append(
            Difference(
                path=f"templates.{name}",
                summary="Template exists on disk but not in the live collection.",
                expected=name,
                actual=None,
            )
        )
    for name in sorted(actual_template_names - expected_template_names):
        report.differences.append(
            Difference(
                path=f"templates.{name}",
                summary="Template exists in the live collection but not on disk.",
                expected=None,
                actual=name,
            )
        )

    for template_name in sorted(expected_template_names & actual_template_names):
        expected_template = expected.templates[template_name]
        actual_template = actual.templates[template_name]
        for side in sorted(set(expected_template) | set(actual_template)):
            expected_value = str(expected_template.get(side, ""))
            actual_value = str(actual_template.get(side, ""))
            if expected_value != actual_value:
                report.differences.append(
                    Difference(
                        path=f"templates.{template_name}.{side}",
                        summary="Template content differs.",
                        diff=_unified_text_diff(
                            expected_value,
                            actual_value,
                            f"expected {template_name} {side}",
                            f"actual {template_name} {side}",
                        ),
                    )
                )

    if expected.css != actual.css:
        report.differences.append(
            Difference(
                path="styling.css",
                summary="Shared note-type CSS differs.",
                diff=_unified_text_diff(expected.css, actual.css, "expected css", "actual css"),
            )
        )

    return report


def compare_note_snapshots(
    expected: NoteSnapshot,
    actual: NoteSnapshot,
    *,
    key_fields: Iterable[str] = (),
    field_names: Iterable[str] = (),
) -> DiffReport:
    key_fields = tuple(key_fields)
    field_names = tuple(field_names)
    report = DiffReport(
        title="Note field diff",
        expected_source=expected.source,
        actual_source=actual.source,
        metadata={"key_fields": key_fields, "field_names": field_names},
    )

    expected_index, expected_duplicates = _index_notes(expected.notes, key_fields)
    actual_index, actual_duplicates = _index_notes(actual.notes, key_fields)

    for key, notes in sorted(expected_duplicates.items()):
        report.differences.append(
            Difference(
                path=f"notes.{key}",
                summary=f"Disk snapshot has {len(notes)} notes with the same key.",
                expected=[note.note_id for note in notes],
                actual=None,
            )
        )
    for key, notes in sorted(actual_duplicates.items()):
        report.differences.append(
            Difference(
                path=f"notes.{key}",
                summary=f"Live collection has {len(notes)} notes with the same key.",
                expected=None,
                actual=[note.note_id for note in notes],
            )
        )

    expected_keys = set(expected_index)
    actual_keys = set(actual_index)
    for key in sorted(expected_keys - actual_keys):
        report.differences.append(
            Difference(
                path=f"notes.{key}",
                summary="Note exists on disk but not in the live collection.",
                expected=expected_index[key].to_json(),
                actual=None,
            )
        )
    for key in sorted(actual_keys - expected_keys):
        report.differences.append(
            Difference(
                path=f"notes.{key}",
                summary="Note exists in the live collection but not on disk.",
                expected=None,
                actual=actual_index[key].to_json(),
            )
        )

    for key in sorted(expected_keys & actual_keys):
        expected_note = expected_index[key]
        actual_note = actual_index[key]
        names = field_names or tuple(sorted(set(expected_note.fields) | set(actual_note.fields)))
        for field_name in names:
            expected_value = expected_note.fields.get(field_name, "")
            actual_value = actual_note.fields.get(field_name, "")
            if expected_value != actual_value:
                report.differences.append(
                    Difference(
                        path=f"notes.{key}.fields.{field_name}",
                        summary="Field value differs.",
                        diff=_unified_text_diff(
                            expected_value,
                            actual_value,
                            f"expected {field_name}",
                            f"actual {field_name}",
                        ),
                    )
                )

    return report


def compare_collection_snapshots(
    expected: CollectionSnapshot,
    actual: CollectionSnapshot,
    *,
    key_fields: Iterable[str] = (),
    field_names: Iterable[str] = (),
    compare_models: bool = True,
    compare_media: bool = True,
) -> DiffReport:
    key_fields = tuple(key_fields)
    field_names = tuple(field_names)
    report = DiffReport(
        title="APKG vs live deck diff",
        expected_source=expected.source,
        actual_source=actual.source,
        metadata={
            "expected_deck_names": expected.deck_names,
            "actual_deck_names": actual.deck_names,
            "key_fields": key_fields,
            "field_names": field_names,
        },
    )

    _compare_counts(report, expected, actual)
    if compare_models:
        _compare_collection_models(report, expected, actual)
    _compare_collection_notes(report, expected, actual, key_fields, field_names)
    _compare_card_counts(report, expected, actual)
    if compare_media:
        _compare_media(report, expected, actual)
    return report


def combine_reports(title: str, reports: Iterable[DiffReport]) -> DiffReport:
    reports = list(reports)
    combined = DiffReport(title=title, expected_source="disk", actual_source="live")
    for report in reports:
        for difference in report.differences:
            combined.differences.append(
                Difference(
                    path=f"{report.title}/{difference.path}",
                    summary=difference.summary,
                    expected=difference.expected,
                    actual=difference.actual,
                    diff=difference.diff,
                )
            )
    combined.metadata["reports"] = [report.to_json() for report in reports]
    return combined


def _compare_counts(
    report: DiffReport,
    expected: CollectionSnapshot,
    actual: CollectionSnapshot,
) -> None:
    if len(expected.notes) != len(actual.notes):
        report.differences.append(
            Difference(
                path="counts.notes",
                summary="Note counts differ.",
                expected=len(expected.notes),
                actual=len(actual.notes),
            )
        )
    if len(expected.cards) != len(actual.cards):
        report.differences.append(
            Difference(
                path="counts.cards",
                summary="Card counts differ.",
                expected=len(expected.cards),
                actual=len(actual.cards),
            )
        )


def _compare_collection_models(
    report: DiffReport,
    expected: CollectionSnapshot,
    actual: CollectionSnapshot,
) -> None:
    expected_names = set(expected.models)
    actual_names = set(actual.models)
    for name in sorted(expected_names - actual_names):
        report.differences.append(
            Difference(
                path=f"models.{name}",
                summary="Model exists in the APKG but not in the live deck.",
                expected=name,
                actual=None,
            )
        )
    for name in sorted(actual_names - expected_names):
        report.differences.append(
            Difference(
                path=f"models.{name}",
                summary="Model exists in the live deck but not in the APKG.",
                expected=None,
                actual=name,
            )
        )
    for name in sorted(expected_names & actual_names):
        model_report = compare_model_snapshots(expected.models[name], actual.models[name])
        for difference in model_report.differences:
            report.differences.append(
                Difference(
                    path=f"models.{name}.{difference.path}",
                    summary=difference.summary,
                    expected=difference.expected,
                    actual=difference.actual,
                    diff=difference.diff,
                )
            )


def _compare_collection_notes(
    report: DiffReport,
    expected: CollectionSnapshot,
    actual: CollectionSnapshot,
    key_fields: tuple[str, ...],
    field_names: tuple[str, ...],
) -> None:
    expected_index, expected_duplicates = _index_collection_notes(expected, key_fields)
    actual_index, actual_duplicates = _index_collection_notes(actual, key_fields)

    for key, notes in sorted(expected_duplicates.items()):
        report.differences.append(
            Difference(
                path=f"notes.{key}",
                summary=f"APKG has {len(notes)} notes with the same comparison key.",
                expected=[note.note_id for note in notes],
                actual=None,
            )
        )
    for key, notes in sorted(actual_duplicates.items()):
        report.differences.append(
            Difference(
                path=f"notes.{key}",
                summary=f"Live deck has {len(notes)} notes with the same comparison key.",
                expected=None,
                actual=[note.note_id for note in notes],
            )
        )

    expected_keys = set(expected_index)
    actual_keys = set(actual_index)
    for key in sorted(expected_keys - actual_keys):
        report.differences.append(
            Difference(
                path=f"notes.{key}",
                summary="Note exists in the APKG but not in the live deck.",
                expected=expected_index[key].to_json(),
                actual=None,
            )
        )
    for key in sorted(actual_keys - expected_keys):
        report.differences.append(
            Difference(
                path=f"notes.{key}",
                summary="Note exists in the live deck but not in the APKG.",
                expected=None,
                actual=actual_index[key].to_json(),
            )
        )

    for key in sorted(expected_keys & actual_keys):
        expected_note = expected_index[key]
        actual_note = actual_index[key]
        names = field_names or tuple(sorted(set(expected_note.fields) | set(actual_note.fields)))
        for field_name in names:
            expected_value = expected_note.fields.get(field_name, "")
            actual_value = actual_note.fields.get(field_name, "")
            if expected_value != actual_value:
                report.differences.append(
                    Difference(
                        path=f"notes.{key}.fields.{field_name}",
                        summary="Field value differs.",
                        diff=_unified_text_diff(
                            expected_value,
                            actual_value,
                            f"expected {field_name}",
                            f"actual {field_name}",
                        ),
                    )
                )


def _compare_card_counts(
    report: DiffReport,
    expected: CollectionSnapshot,
    actual: CollectionSnapshot,
) -> None:
    expected_counts = _card_counts(expected)
    actual_counts = _card_counts(actual)
    if expected_counts != actual_counts:
        report.differences.append(
            Difference(
                path="cards.by_template",
                summary="Card counts by model/template differ.",
                expected=dict(sorted(expected_counts.items())),
                actual=dict(sorted(actual_counts.items())),
                diff=_unified_json_diff(
                    dict(sorted(expected_counts.items())),
                    dict(sorted(actual_counts.items())),
                    "expected cards",
                    "actual cards",
                ),
            )
        )


def _compare_media(
    report: DiffReport,
    expected: CollectionSnapshot,
    actual: CollectionSnapshot,
) -> None:
    missing = sorted(set(expected.media_names) - set(actual.media_names))
    if missing:
        report.differences.append(
            Difference(
                path="media.missing",
                summary="Media files are present in the APKG but missing from the live collection media folder.",
                expected=missing,
                actual=None,
            )
        )


def _card_counts(snapshot: CollectionSnapshot) -> Counter[str]:
    return Counter(f"{card.model_name}::{card.template_name}" for card in snapshot.cards)


def _index_collection_notes(
    snapshot: CollectionSnapshot,
    key_fields: tuple[str, ...],
) -> tuple[dict[str, NoteRecord], dict[str, list[NoteRecord]]]:
    grouped: dict[str, list[NoteRecord]] = {}
    for note in snapshot.notes:
        grouped.setdefault(_collection_note_key(note, snapshot, key_fields), []).append(note)
    unique = {key: values[0] for key, values in grouped.items() if len(values) == 1}
    duplicates = {key: values for key, values in grouped.items() if len(values) > 1}
    return unique, duplicates


def _collection_note_key(
    note: NoteRecord,
    snapshot: CollectionSnapshot,
    key_fields: tuple[str, ...],
) -> str:
    if key_fields:
        return f"{note.model_name} | " + " | ".join(
            f"{name}={note.fields.get(name, '')}" for name in key_fields
        )
    model = snapshot.models.get(note.model_name)
    first_field = model.fields[0] if model and model.fields else next(iter(note.fields), "")
    return f"{note.model_name} | {first_field}={note.fields.get(first_field, '')}"


def _index_notes(
    notes: Iterable[NoteRecord],
    key_fields: tuple[str, ...],
) -> tuple[dict[str, NoteRecord], dict[str, list[NoteRecord]]]:
    grouped: dict[str, list[NoteRecord]] = {}
    for note in notes:
        grouped.setdefault(_note_key(note, key_fields), []).append(note)

    unique = {key: values[0] for key, values in grouped.items() if len(values) == 1}
    duplicates = {key: values for key, values in grouped.items() if len(values) > 1}
    return unique, duplicates


def _note_key(note: NoteRecord, key_fields: tuple[str, ...]) -> str:
    if not key_fields:
        return str(note.note_id)
    return " | ".join(f"{name}={note.fields.get(name, '')}" for name in key_fields)


def _unified_json_diff(expected: Any, actual: Any, fromfile: str, tofile: str) -> tuple[str, ...]:
    expected_text = json.dumps(expected, ensure_ascii=False, indent=2)
    actual_text = json.dumps(actual, ensure_ascii=False, indent=2)
    return _unified_text_diff(expected_text, actual_text, fromfile, tofile)


def _unified_text_diff(expected: str, actual: str, fromfile: str, tofile: str) -> tuple[str, ...]:
    return tuple(
        difflib.unified_diff(
            expected.splitlines(),
            actual.splitlines(),
            fromfile=fromfile,
            tofile=tofile,
            lineterm="",
        )
    )
