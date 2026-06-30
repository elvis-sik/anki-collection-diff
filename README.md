# anki-collection-diff

`anki-collection-diff` compares on-disk Anki project history with the live Anki
collection through AnkiConnect.

The first supported disk formats are the snapshot layouts already used in this
workspace:

- note-type snapshots in `templates/<note-type-slug>/<timestamp>/`
- note-field snapshots in
  `backups/note-field-snapshots/<note-type-slug>/<timestamp-label>/`

The library is intentionally cheap: it reads JSON/HTML/CSS files from disk,
fetches only the requested model or note query from AnkiConnect, and reports
structural differences. It does not render cards and it never writes to Anki.

## What It Can Compare

- model field order and field names
- card template fronts and backs
- shared note-type CSS
- note field values, keyed by note id or by stable fields such as
  `Traditional` and `Simplified`
- added and missing notes within the selected query

## Quick Start

Anki must be open with AnkiConnect enabled.

```bash
python -m anki_collection_diff diff-model \
  ../anki-deck-styling/templates/traditional-from-simplified/2026-04-01T16-15-48-0700 \
  --model-name "Traditional from Simplified"
```

To compare note contents for the same deck, key rows by stable note fields:

```bash
python -m anki_collection_diff diff-notes \
  ../anki-deck-styling/backups/note-field-snapshots/traditional-from-simplified/2026-04-01T21-54-10-0700-pre-traditional-split \
  --model-name "Traditional from Simplified" \
  --deck-name "Decks::Idiomas::中文::Character Decks::Traditional from Simplified" \
  --key-field Traditional \
  --key-field Simplified
```

For repeatable audits, put targets in a TOML config:

```bash
python -m anki_collection_diff audit --config examples/traditional-from-simplified.toml
```

By default, diff commands exit with status `1` when differences are found so
they can be used in scripts. Add `--no-fail-on-diff` for exploratory runs.

## Capturing New Baselines

The CLI can also export fresh baselines in the same layout:

```bash
python -m anki_collection_diff snapshot-model \
  --output-root ../anki-deck-styling \
  --model-name "Traditional from Simplified" \
  --deck-name "Decks::Idiomas::中文::Character Decks::Traditional from Simplified"
```

```bash
python -m anki_collection_diff snapshot-notes \
  --output-root ../anki-deck-styling \
  --model-name "Traditional from Simplified" \
  --deck-name "Decks::Idiomas::中文::Character Decks::Traditional from Simplified" \
  --label pre-change
```

## Library Use

```python
from pathlib import Path

from anki_collection_diff.ankiconnect import AnkiConnectClient
from anki_collection_diff.diff import compare_model_snapshots
from anki_collection_diff.snapshots import load_model_snapshot

client = AnkiConnectClient()
disk = load_model_snapshot(Path("templates/my-note-type/2026-06-30T10-00-00-0300"))
live = client.fetch_model_snapshot("My Note Type")
report = compare_model_snapshots(disk, live)

print(report.to_markdown())
```

## Design Boundary

This project is a diff and snapshot library, not a deck authoring framework.
Write-back commands should live elsewhere until a repeated workflow proves they
belong here.
