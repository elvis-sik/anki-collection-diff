# anki-collection-diff

[![PyPI](https://img.shields.io/pypi/v/anki-collection-diff.svg)](https://pypi.org/project/anki-collection-diff/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776ab)](https://pypi.org/project/anki-collection-diff/)
[![Source on GitHub](https://img.shields.io/badge/source-GitHub-24292f)](https://github.com/elvis-sik/anki-collection-diff)
[![License: MIT](https://img.shields.io/badge/license-MIT-16A34A)](LICENSE)

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

Install from PyPI:

```bash
python -m pip install anki-collection-diff
```

Anki must be open with AnkiConnect enabled.

```bash
anki-collection-diff inspect-apkg ../brazil-ddd-codes/out/brazil-ddd-codes.apkg
```

Then compare the APKG to the live deck. Pass a stable key field when note ids are
not expected to match between the package and your collection:

```bash
anki-collection-diff compare-apkg \
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

## Runtime Permissions

APKG inspection is offline and only reads the package file.

APKG-vs-live comparison requires:

- Anki running locally
- AnkiConnect installed and reachable at `http://127.0.0.1:8765`
- permission for the process to open localhost HTTP connections

When running from Codex Desktop or another sandboxed agent, filesystem access to
the project may not imply network access to AnkiConnect. If localhost requests
fail from Python with "Could not reach AnkiConnect" while `curl` or the Anki UI
looks healthy, rerun the comparison with the agent's unsandboxed/escalated
permission flow.

The optional `--deck-agent codex` and `--deck-agent claude` modes shell out to
the corresponding CLI. They do not require this package to know API keys, but
the chosen CLI must already be installed, authenticated, and allowed to access
its normal state directory and model service. For Codex CLI this commonly means
access to `~/.codex`, session files, and the network. If the installed Codex CLI
rejects a local `service_tier` config value, pass a CLI config override when you
run Codex directly, or fix the user-level Codex config before using
`--deck-agent codex`.

For repeatable audits, put APKG targets in a TOML config:

```bash
anki-collection-diff audit --config examples/brazil-ddd-codes.toml
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

## Releasing

Releases are published to PyPI by GitHub Actions when a version tag is pushed.
The workflow uses PyPI Trusted Publishing, so there is no PyPI token in the
repository.

One-time PyPI setup:

- Project name: `anki-collection-diff`
- Owner: `elvis-sik`
- Repository: `anki-collection-diff`
- Workflow: `workflow.yml`
- Environment: `pypi`

Release checklist:

```bash
make check
make build
make twine-check
git tag v0.1.0
git push origin main v0.1.0
```
