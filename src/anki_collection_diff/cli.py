from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .ankiconnect import AnkiConnectClient, AnkiConnectError
from .apkg import ApkgError, inspect_apkg, load_apkg_snapshot
from .deck_resolver import DeckResolutionError, resolve_deck_name
from .diff import DiffReport, combine_reports, compare_collection_snapshots


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (AnkiConnectError, ApkgError, DeckResolutionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="anki-collection-diff",
        description="Compare APKG files with a live Anki collection.",
    )
    parser.add_argument("--ankiconnect-url", default="http://127.0.0.1:8765")
    subparsers = parser.add_subparsers(required=True)

    inspect_parser = subparsers.add_parser("inspect-apkg")
    inspect_parser.add_argument("apkg", type=Path)
    inspect_parser.add_argument("--format", choices=["text", "json"], default="text")
    inspect_parser.set_defaults(func=_inspect_apkg)

    compare = subparsers.add_parser("compare-apkg")
    compare.add_argument("apkg", type=Path)
    compare.add_argument("--apkg-deck-name")
    compare.add_argument("--deck-name")
    compare.add_argument("--deck-env", default="ANKI_COLLECTION_DIFF_DECK")
    compare.add_argument("--deck-agent", choices=["codex", "claude"])
    compare.add_argument("--key-field", action="append", default=[])
    compare.add_argument("--field", action="append", default=[])
    compare.add_argument("--no-models", action="store_true")
    compare.add_argument("--no-media", action="store_true")
    _add_output_args(compare)
    compare.set_defaults(func=_compare_apkg)

    audit = subparsers.add_parser("audit")
    audit.add_argument("--config", required=True, type=Path)
    _add_output_args(audit)
    audit.set_defaults(func=_audit)
    return parser


def _add_output_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--no-fail-on-diff", action="store_true")


def _inspect_apkg(args: argparse.Namespace) -> int:
    summary = inspect_apkg(args.apkg)
    if args.format == "json":
        print(json.dumps(summary.to_json(), ensure_ascii=False, indent=2))
        return 0

    print(f"APKG: {summary.path}")
    print(f"Notes: {summary.note_count}")
    print(f"Cards: {summary.card_count}")
    print(f"Media files: {summary.media_count}")
    print("Decks:")
    for name in summary.deck_names:
        print(f"  - {name}")
    print("Candidate live deck names:")
    for name in summary.candidate_deck_names:
        print(f"  - {name}")
    print("Models:")
    for name in summary.model_names:
        print(f"  - {name}")
    return 0


def _compare_apkg(args: argparse.Namespace) -> int:
    client = AnkiConnectClient(args.ankiconnect_url)
    expected = load_apkg_snapshot(args.apkg, deck_name=args.apkg_deck_name)
    live_deck = resolve_deck_name(
        explicit_deck_name=args.deck_name,
        env_var=args.deck_env,
        agent=args.deck_agent,
        apkg_candidates=tuple(expected.metadata.get("candidate_deck_names", ())),
        live_deck_names=client.deck_names(),
    )
    actual = client.fetch_deck_snapshot(live_deck, include_media=not args.no_media)
    report = compare_collection_snapshots(
        expected,
        actual,
        key_fields=args.key_field,
        field_names=args.field,
        compare_models=not args.no_models,
        compare_media=not args.no_media,
    )
    report.title = f"APKG vs live deck: {args.apkg.name}"
    report.metadata["live_deck_name"] = live_deck
    return _emit_report(report, args)


def _audit(args: argparse.Namespace) -> int:
    config = _load_audit_config(args.config)
    client = AnkiConnectClient(config["ankiconnect_url"])
    reports: list[DiffReport] = []
    for target in config["targets"]:
        expected = load_apkg_snapshot(
            target["apkg"],
            deck_name=target.get("apkg_deck_name"),
        )
        live_deck = resolve_deck_name(
            explicit_deck_name=target.get("deck_name"),
            env_var=target.get("deck_env", "ANKI_COLLECTION_DIFF_DECK"),
            agent=target.get("deck_agent"),
            apkg_candidates=tuple(expected.metadata.get("candidate_deck_names", ())),
            live_deck_names=client.deck_names(),
        )
        actual = client.fetch_deck_snapshot(
            live_deck,
            include_media=not target.get("no_media", False),
        )
        report = compare_collection_snapshots(
            expected,
            actual,
            key_fields=target.get("key_fields", ()),
            field_names=target.get("fields", ()),
            compare_models=not target.get("no_models", False),
            compare_media=not target.get("no_media", False),
        )
        report.title = f"{target['name']}: {target['apkg'].name}"
        report.metadata["live_deck_name"] = live_deck
        reports.append(report)

    combined = combine_reports(f"APKG audit: {args.config}", reports)
    return _emit_report(combined, args)


def _load_audit_config(path: Path) -> dict[str, object]:
    import tomllib

    data = tomllib.loads(path.read_text())
    base = path.parent
    collection = data.get("collection", {})
    targets = []
    for item in data.get("targets", []):
        target = dict(item)
        target["apkg"] = _resolve_path(base, item["apkg"])
        targets.append(target)
    return {
        "ankiconnect_url": collection.get("ankiconnect_url", "http://127.0.0.1:8765"),
        "targets": targets,
    }


def _resolve_path(base: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (base / path).resolve()


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
