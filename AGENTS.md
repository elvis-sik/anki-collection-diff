# AGENTS.md

## Scope

These instructions apply to the `anki-collection-diff` project.

## Project Purpose

`anki-collection-diff` is a small reusable Python library and CLI for comparing
APKG files on disk with the user's live Anki collection through AnkiConnect.

## Development Notes

- Prefer AnkiConnect over direct SQLite reads or writes.
- Keep the core library dependency-free unless a dependency removes substantial
  complexity.
- Treat APKG-vs-live deck comparison as the public, PyPI-shaped workflow.
- Keep older snapshot helpers internal unless they support APKG comparison or
  migration work.
- Treat diffs as read-only audit output. Do not add write-back behavior without
  a separate explicit command and tests.
- Keep the library usable from deck repositories by exposing both importable
  functions and a CLI.
