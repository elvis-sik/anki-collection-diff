from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from anki_collection_diff.apkg import inspect_apkg, load_apkg_snapshot
from anki_collection_diff.deck_resolver import DeckResolutionError, resolve_deck_name


class ApkgTests(unittest.TestCase):
    def test_load_apkg_snapshot_reads_notes_cards_models_and_media(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            apkg = Path(tmp) / "fixture.apkg"
            _write_fixture_apkg(apkg)

            snapshot = load_apkg_snapshot(apkg)

            self.assertEqual(snapshot.deck_names, ("Example Deck",))
            self.assertEqual(tuple(snapshot.models), ("Example Model",))
            self.assertEqual(snapshot.notes[0].guid, "guid-1")
            self.assertEqual(snapshot.notes[0].fields, {"slug": "one", "name": "One"})
            self.assertEqual(snapshot.cards[0].template_name, "Card 1")
            self.assertEqual(snapshot.media_names, ("image.png",))

    def test_inspect_apkg_reports_candidate_decks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            apkg = Path(tmp) / "fixture.apkg"
            _write_fixture_apkg(apkg)

            summary = inspect_apkg(apkg)

            self.assertEqual(summary.deck_names, ("Example Deck",))
            self.assertEqual(summary.candidate_deck_names, ("Example Deck",))
            self.assertEqual(summary.note_count, 1)
            self.assertEqual(summary.card_count, 1)

    def test_resolver_rejects_unknown_explicit_deck(self) -> None:
        with self.assertRaises(DeckResolutionError):
            resolve_deck_name(
                explicit_deck_name="Missing",
                env_var=None,
                agent=None,
                apkg_candidates=("Example Deck",),
                live_deck_names=("Example Deck",),
            )


def _write_fixture_apkg(path: Path) -> None:
    db_path = path.with_suffix(".anki2")
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            create table col (
              id integer primary key,
              crt integer not null,
              mod integer not null,
              scm integer not null,
              ver integer not null,
              dty integer not null,
              usn integer not null,
              ls integer not null,
              conf text not null,
              models text not null,
              decks text not null,
              dconf text not null,
              tags text not null
            );
            create table notes (
              id integer primary key,
              guid text not null,
              mid integer not null,
              mod integer not null,
              usn integer not null,
              tags text not null,
              flds text not null,
              sfld integer not null,
              csum integer not null,
              flags integer not null,
              data text not null
            );
            create table cards (
              id integer primary key,
              nid integer not null,
              did integer not null,
              ord integer not null,
              mod integer not null,
              usn integer not null,
              type integer not null,
              queue integer not null,
              due integer not null,
              ivl integer not null,
              factor integer not null,
              reps integer not null,
              lapses integer not null,
              left integer not null,
              odue integer not null,
              odid integer not null,
              flags integer not null,
              data text not null
            );
            """
        )
        decks = {
            "1": {"id": 1, "name": "Default"},
            "2": {"id": 2, "name": "Example Deck"},
        }
        models = {
            "3": {
                "id": 3,
                "name": "Example Model",
                "css": ".card {}",
                "flds": [{"name": "slug"}, {"name": "name"}],
                "tmpls": [
                    {
                        "name": "Card 1",
                        "ord": 0,
                        "qfmt": "{{slug}}",
                        "afmt": "{{name}}",
                    }
                ],
            }
        }
        connection.execute(
            "insert into col values (1,0,0,0,0,0,0,0,?,?,?,?,?)",
            ("{}", json.dumps(models), json.dumps(decks), "{}", "{}"),
        )
        connection.execute(
            "insert into notes values (100,'guid-1',3,0,0,' tag ',?,0,0,0,'')",
            ("one\x1fOne",),
        )
        connection.execute(
            "insert into cards values (101,100,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,'')"
        )
        connection.commit()
    finally:
        connection.close()

    with zipfile.ZipFile(path, "w") as package:
        package.write(db_path, "collection.anki2")
        package.writestr("media", json.dumps({"0": "image.png"}))
        package.writestr("0", b"fake image")
