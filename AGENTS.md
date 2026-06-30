# AGENTS.md

## Scope

These instructions apply to the `anki-collection-diff` project.

## Project Purpose

`anki-collection-diff` is a small reusable Python library and CLI for comparing
on-disk Anki project history with the user's live Anki collection through
AnkiConnect.

## Development Notes

- Prefer AnkiConnect over direct SQLite reads or writes.
- Keep the core library dependency-free unless a dependency removes substantial
  complexity.
- Preserve compatibility with the existing snapshot layout used by
  `anki-deck-styling`:
  - note-type snapshots under `templates/<note-type-slug>/<timestamp>/`
  - note-field snapshots under
    `backups/note-field-snapshots/<note-type-slug>/<timestamp-label>/`
- Treat diffs as read-only audit output. Do not add write-back behavior without
  a separate explicit command and tests.
- Keep the library usable from deck repositories by exposing both importable
  functions and a CLI.
