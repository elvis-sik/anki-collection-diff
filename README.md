# Anki Collection Diff

[![PyPI](https://img.shields.io/pypi/v/anki-collection-diff.svg)](https://pypi.org/project/anki-collection-diff/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776ab)](https://pypi.org/project/anki-collection-diff/)
[![Source on GitHub](https://img.shields.io/badge/source-GitHub-24292f)](https://github.com/elvis-sik/anki-collection-diff)
[![License: MIT](https://img.shields.io/badge/license-MIT-16A34A)](LICENSE)

Know what a generated `.apkg` would change before you replace the copy in your
live Anki collection.

`anki-collection-diff` compares an APKG on disk with one deck exposed through
AnkiConnect. It is built for reproducible deck projects: build the package,
inspect it, compare it to Anki, then decide whether a rollout is warranted.

**Read-only by design.** APKG inspection stays offline. Live comparison reads
from AnkiConnect and never edits your collection, note types, media, or sync
state.

## Install

```bash
uv tool install anki-collection-diff
# or: python -m pip install anki-collection-diff
```

For live comparisons, start Anki with AnkiConnect enabled. The default endpoint
is `http://127.0.0.1:8765`.

## The Fast Path

First inspect the package without opening Anki:

```bash
anki-collection-diff inspect-apkg out/my-deck.apkg
```

Then compare it with the installed deck. A stable key field makes note matching
reliable even when the APKG and collection do not share note IDs:

```bash
anki-collection-diff compare-apkg out/my-deck.apkg \
  --deck-name "My Deck" \
  --key-field slug
```

The report is Markdown by default, so it works well in a terminal, CI log, or
release review. It exits `1` when differences exist and `0` when the snapshots
match. Add `--no-fail-on-diff` when you are exploring rather than gating a
workflow.

## What It Checks

| Surface | Examples |
| --- | --- |
| Deck contents | note and card counts; added and missing notes; selected field values |
| Note types | field order and names; card-template fronts and backs; shared CSS |
| Media | files present in the APKG but missing from the live collection |
| Structure | card counts by model/template and APKG deck candidates |

Use `--field FieldName` to limit field comparison, `--no-models` to skip note
type checks, or `--no-media` when media is outside the change under review.

## Repeatable Audits

Keep a public-safe TOML target file next to a deck project:

```toml
[collection]
ankiconnect_url = "http://127.0.0.1:8765"

[[targets]]
name = "my-deck"
apkg = "out/my-deck.apkg"
deck_name = "My Deck"
key_fields = ["slug"]
```

Run the whole audit with:

```bash
anki-collection-diff audit --config release/audit.toml
```

See [`examples/brazil-ddd-codes.toml`](examples/brazil-ddd-codes.toml) for a
working example.

## Deck Selection

`compare-apkg` accepts `--deck-name` directly. It can also read a deck name
from `ANKI_COLLECTION_DIFF_DECK` (or a custom `--deck-env`), or automatically
use the single unambiguous APKG candidate. The optional `--deck-agent codex`
and `--deck-agent claude` modes ask an already-installed agent CLI to resolve an
ambiguous name; they are not required for ordinary use.

## Boundaries

This is a diff and audit tool, not a deck authoring, import, or sync framework.
It deliberately does not write to Anki. Use it before a separate, intentional
rollout step.

When an agent sandbox blocks localhost access, rerun the comparison with that
agent's normal local-network or escalated permission path. The package still
does not gain write access to Anki.

## Development

```bash
make check
make build
make twine-check
```

PyPI releases use GitHub Actions Trusted Publishing; the repository contains no
PyPI token.

## License

MIT. See [LICENSE](LICENSE).
