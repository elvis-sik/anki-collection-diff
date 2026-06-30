from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .ankiconnect import AnkiConnectClient, AnkiConnectError
from .config import load_audit_config
from .diff import (
    DiffReport,
    combine_reports,
    compare_model_snapshots,
    compare_note_snapshots,
)
from .snapshots import load_model_snapshot, load_note_snapshot


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except AnkiConnectError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="anki-collection-diff",
        description="Compare on-disk Anki snapshots with a live Anki collection.",
    )
    parser.add_argument("--ankiconnect-url", default="http://127.0.0.1:8765")
    subparsers = parser.add_subparsers(required=True)

    snapshot_model = subparsers.add_parser("snapshot-model")
    snapshot_model.add_argument("--output-root", required=True, type=Path)
    snapshot_model.add_argument("--model-name", required=True)
    snapshot_model.add_argument("--deck-name")
    snapshot_model.add_argument("--timestamp")
    snapshot_model.set_defaults(func=_snapshot_model)

    snapshot_notes = subparsers.add_parser("snapshot-notes")
    snapshot_notes.add_argument("--output-root", required=True, type=Path)
    snapshot_notes.add_argument("--model-name", required=True)
    snapshot_notes.add_argument("--deck-name", required=True)
    snapshot_notes.add_argument("--timestamp")
    snapshot_notes.add_argument("--label", default="snapshot")
    snapshot_notes.set_defaults(func=_snapshot_notes)

    diff_model = subparsers.add_parser("diff-model")
    diff_model.add_argument("snapshot", type=Path)
    diff_model.add_argument("--model-name", required=True)
    diff_model.add_argument("--deck-name")
    _add_output_args(diff_model)
    diff_model.set_defaults(func=_diff_model)

    diff_notes = subparsers.add_parser("diff-notes")
    diff_notes.add_argument("snapshot", type=Path)
    diff_notes.add_argument("--model-name", required=True)
    diff_notes.add_argument("--deck-name")
    diff_notes.add_argument("--query")
    diff_notes.add_argument("--key-field", action="append", default=[])
    diff_notes.add_argument("--field", action="append", default=[])
    _add_output_args(diff_notes)
    diff_notes.set_defaults(func=_diff_notes)

    audit = subparsers.add_parser("audit")
    audit.add_argument("--config", required=True, type=Path)
    _add_output_args(audit)
    audit.set_defaults(func=_audit)
    return parser


def _add_output_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--no-fail-on-diff", action="store_true")


def _snapshot_model(args: argparse.Namespace) -> int:
    client = AnkiConnectClient(args.ankiconnect_url)
    out = client.export_model_snapshot(
        output_root=args.output_root,
        model_name=args.model_name,
        deck_name=args.deck_name,
        timestamp=args.timestamp,
    )
    print(out)
    return 0


def _snapshot_notes(args: argparse.Namespace) -> int:
    client = AnkiConnectClient(args.ankiconnect_url)
    out = client.export_note_snapshot(
        output_root=args.output_root,
        model_name=args.model_name,
        deck_name=args.deck_name,
        timestamp=args.timestamp,
        label=args.label,
    )
    print(out)
    return 0


def _diff_model(args: argparse.Namespace) -> int:
    client = AnkiConnectClient(args.ankiconnect_url)
    expected = load_model_snapshot(args.snapshot)
    actual = client.fetch_model_snapshot(args.model_name, args.deck_name)
    report = compare_model_snapshots(expected, actual)
    return _emit_report(report, args)


def _diff_notes(args: argparse.Namespace) -> int:
    client = AnkiConnectClient(args.ankiconnect_url)
    expected = load_note_snapshot(args.snapshot)
    actual = client.fetch_note_snapshot(
        model_name=args.model_name,
        deck_name=args.deck_name,
        query=args.query,
    )
    report = compare_note_snapshots(
        expected,
        actual,
        key_fields=args.key_field,
        field_names=args.field,
    )
    return _emit_report(report, args)


def _audit(args: argparse.Namespace) -> int:
    config = load_audit_config(args.config)
    client = AnkiConnectClient(config.ankiconnect_url)
    reports: list[DiffReport] = []

    for target in config.targets:
        if target.model_snapshot:
            expected_model = load_model_snapshot(target.model_snapshot)
            actual_model = client.fetch_model_snapshot(target.model_name, target.deck_name)
            model_report = compare_model_snapshots(expected_model, actual_model)
            model_report.title = f"{target.name}: model"
            reports.append(model_report)

        if target.note_snapshot:
            expected_notes = load_note_snapshot(target.note_snapshot)
            actual_notes = client.fetch_note_snapshot(
                model_name=target.model_name,
                deck_name=target.deck_name,
                query=target.query,
            )
            note_report = compare_note_snapshots(
                expected_notes,
                actual_notes,
                key_fields=target.key_fields,
                field_names=target.fields,
            )
            note_report.title = f"{target.name}: notes"
            reports.append(note_report)

    combined = combine_reports(f"Anki collection audit: {args.config}", reports)
    return _emit_report(combined, args)


def _emit_report(report: DiffReport, args: argparse.Namespace) -> int:
    if args.format == "json":
        text = json.dumps(report.to_json(), ensure_ascii=False, indent=2) + "\n"
    else:
        text = report.to_markdown()

    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")

    if report.changed and not args.no_fail_on_diff:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
