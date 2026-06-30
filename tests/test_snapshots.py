from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from anki_collection_diff.snapshots import load_model_snapshot, load_note_snapshot
from anki_collection_diff.util import slugify


class SnapshotTests(unittest.TestCase):
    def test_slugify_matches_existing_snapshot_style(self) -> None:
        self.assertEqual(slugify("Traditional from Simplified"), "traditional-from-simplified")

    def test_load_model_snapshot_reads_existing_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "metadata.json").write_text(
                json.dumps({"model_name": "Example"}, ensure_ascii=False)
            )
            (root / "fields.json").write_text(json.dumps(["Front", "Back"]))
            (root / "templates.json").write_text(
                json.dumps({"Card 1": {"Front": "{{Front}}", "Back": "{{Back}}"}},
                           ensure_ascii=False)
            )
            (root / "styling.json").write_text(json.dumps({"css": ".card {}"}))
            (root / "note_ids.json").write_text(json.dumps([1]))
            (root / "card_ids.json").write_text(json.dumps([2]))

            snapshot = load_model_snapshot(root)

            self.assertEqual(snapshot.model_name, "Example")
            self.assertEqual(snapshot.fields, ["Front", "Back"])
            self.assertEqual(snapshot.templates["Card 1"]["Back"], "{{Back}}")
            self.assertEqual(snapshot.css, ".card {}")
            self.assertEqual(snapshot.note_ids, [1])
            self.assertEqual(snapshot.card_ids, [2])

    def test_load_note_snapshot_reads_note_field_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "metadata.json").write_text("{}")
            (root / "notes.json").write_text(
                json.dumps(
                    [
                        {
                            "noteId": 1,
                            "modelName": "Example",
                            "tags": ["tag"],
                            "fields": {"Front": "A"},
                            "cardIds": [2],
                        }
                    ]
                )
            )

            snapshot = load_note_snapshot(root)

            self.assertEqual(snapshot.notes[0].note_id, 1)
            self.assertEqual(snapshot.notes[0].fields["Front"], "A")
            self.assertEqual(snapshot.notes[0].card_ids, (2,))


if __name__ == "__main__":
    unittest.main()
