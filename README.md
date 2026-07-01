# anki-collection-diff

`anki-collection-diff` compares APKG files on disk with the live Anki collection
through AnkiConnect.

It is meant for generated deck projects where the build output is an `.apkg`,
and you want a cheap repeatable audit of what differs from the copy currently
installed in Anki.

The library is intentionally cheap: it reads the package SQLite database and
media manifest, fetches only the selected live deck through AnkiConnect, and
reports structural differences. It does not render cards and it never writes to
Anki.

## What It Can Compare

- note and card counts
- added and missing notes
- note field values, keyed by stable fields
- model field order and field names
- card template fronts and backs
- shared note-type CSS
- card counts by model/template
- APKG media files missing from the live collection media folder

## Quick Start

Anki must be open with AnkiConnect enabled.

```bash
python -m anki_collection_diff inspect-apkg ../brazil-ddd-codes/out/brazil-ddd-codes.apkg
```

Then compare the APKG to the live deck. Pass a stable key field when note ids are
not expected to match between the package and your collection:

```bash
python -m anki_collection_diff compare-apkg \
  ../brazil-ddd-codes/out/brazil-ddd-codes.apkg \
  --deck-name "Brazilian DDD Codes" \
  --key-field ddd_code
```

Deck selection can come from:

- `--deck-name`
- `ANKI_COLLECTION_DIFF_DECK`, or a custom `--deck-env`
- `--deck-agent codex` or `--deck-agent claude`, which asks the installed CLI to
  choose from APKG candidate deck names and live deck names
- exact automatic match when the APKG has a single unambiguous deck candidate

For repeatable audits, put APKG targets in a TOML config:

```bash
python -m anki_collection_diff audit --config examples/brazil-ddd-codes.toml
```

By default, diff commands exit with status `1` when differences are found so
they can be used in scripts. Add `--no-fail-on-diff` for exploratory runs.

## Library Use

```python
from pathlib import Path

from anki_collection_diff.ankiconnect import AnkiConnectClient
from anki_collection_diff.apkg import load_apkg_snapshot
from anki_collection_diff.diff import compare_collection_snapshots

client = AnkiConnectClient()
apkg = load_apkg_snapshot(Path("out/my-deck.apkg"))
live = client.fetch_deck_snapshot("My Deck")
report = compare_collection_snapshots(apkg, live, key_fields=("slug",))

print(report.to_markdown())
```

## Design Boundary

This project is a diff library, not a deck authoring or sync framework.
Write-back commands should live elsewhere until a repeated workflow proves they
belong here. Project-specific source workflows, such as Markdown bidirectional
sync or local AnkiConnect rollout snapshots, should remain in those projects.
