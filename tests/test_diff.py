from __future__ import annotations

import unittest

from anki_collection_diff.diff import compare_model_snapshots, compare_note_snapshots
from anki_collection_diff.snapshots import ModelSnapshot, NoteRecord, NoteSnapshot


class DiffTests(unittest.TestCase):
    def test_model_diff_detects_template_change(self) -> None:
        expected = ModelSnapshot(
            source="disk",
            metadata={},
            model_name="Example",
            fields=["Front", "Back"],
            templates={"Card 1": {"Front": "{{Front}}", "Back": "{{Back}}"}},
            css=".card { color: black; }",
        )
        actual = ModelSnapshot(
            source="live",
            metadata={},
            model_name="Example",
            fields=["Front", "Back"],
            templates={"Card 1": {"Front": "{{Front}}", "Back": "{{FrontSide}}\n{{Back}}"}},
            css=".card { color: black; }",
        )

        report = compare_model_snapshots(expected, actual)

        self.assertTrue(report.changed)
        self.assertEqual(report.differences[0].path, "templates.Card 1.Back")

    def test_note_diff_uses_key_fields(self) -> None:
        expected = NoteSnapshot(
            source="disk",
            metadata={},
            notes=[
                NoteRecord(
                    note_id=1,
                    model_name="Traditional from Simplified",
                    tags=(),
                    fields={"Traditional": "A", "Simplified": "B", "Meaning": "old"},
                    card_ids=(10,),
                )
            ],
        )
        actual = NoteSnapshot(
            source="live",
            metadata={},
            notes=[
                NoteRecord(
                    note_id=99,
                    model_name="Traditional from Simplified",
                    tags=(),
                    fields={"Traditional": "A", "Simplified": "B", "Meaning": "new"},
                    card_ids=(100,),
                )
            ],
        )

        report = compare_note_snapshots(
            expected,
            actual,
            key_fields=("Traditional", "Simplified"),
        )

        self.assertTrue(report.changed)
        self.assertEqual(
            report.differences[0].path,
            "notes.Traditional=A | Simplified=B.fields.Meaning",
        )

    def test_note_diff_can_limit_fields(self) -> None:
        expected = NoteSnapshot(
            source="disk",
            metadata={},
            notes=[
                NoteRecord(
                    note_id=1,
                    model_name="Example",
                    tags=(),
                    fields={"Key": "A", "Ignored": "old", "Checked": "same"},
                    card_ids=(),
                )
            ],
        )
        actual = NoteSnapshot(
            source="live",
            metadata={},
            notes=[
                NoteRecord(
                    note_id=2,
                    model_name="Example",
                    tags=(),
                    fields={"Key": "A", "Ignored": "new", "Checked": "same"},
                    card_ids=(),
                )
            ],
        )

        report = compare_note_snapshots(
            expected,
            actual,
            key_fields=("Key",),
            field_names=("Checked",),
        )

        self.assertFalse(report.changed)


if __name__ == "__main__":
    unittest.main()
