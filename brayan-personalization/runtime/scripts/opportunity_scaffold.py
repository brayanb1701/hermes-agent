#!/usr/bin/env python3
"""Deterministically scaffold opportunity closeout input examples.

This helper never calls an LLM. By default it creates only
`opportunities/<slug>/closeout-input.example.md` when missing.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

HOME = Path.home()
DEFAULT_VAULT = HOME / "personal_vault"
TEMPLATE_REL = Path("_meta/templates/opportunity-closeout-input-template.md")


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    data: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def extract_title(text: str, fm: dict[str, str], fallback: str) -> str:
    if fm.get("title"):
        return fm["title"]
    match = re.search(r"^#\s+(.+)$", text, re.M)
    return match.group(1).strip() if match else fallback


def render_template(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    unresolved = sorted(set(re.findall(r"{{\s*([A-Za-z0-9_]+)\s*}}", rendered)))
    if unresolved:
        raise ValueError(f"unresolved template placeholders: {', '.join(unresolved)}")
    return rendered


def opportunity_paths(vault: Path, one: str | None, all_records: bool) -> list[Path]:
    if one:
        return [Path(one).expanduser().resolve()]
    if all_records:
        return sorted((vault / "opportunities").glob("*/opportunity.md"))
    raise ValueError("pass --opportunity <path> or --all")


def scaffold_one(path: Path, vault: Path, template: str, args: argparse.Namespace) -> dict[str, object]:
    slug = path.parent.name
    target_name = "closeout-input.md" if args.live_closeout else "closeout-input.example.md"
    target = path.parent / target_name
    if not path.exists():
        return {"opportunity_path": str(path), "target_path": str(target), "status": "error", "error": "opportunity.md missing"}
    text = path.read_text(encoding="utf-8", errors="replace")
    fm = parse_frontmatter(text)
    title = extract_title(text, fm, slug)
    today = date.today().isoformat()
    values = {
        "date": today,
        "slug": slug,
        "opportunity_title": title,
        "input_status": "pending" if args.live_closeout else "example",
        "proposed_status": "applied|archived",
        "proposed_result_status": "submitted|awarded|rejected|expired|no-submission|withdrawn|superseded|unknown",
        "project_closeout_check": "not-needed|continue-project|close-project|needs-review",
        "example_notice": "Note: this is an example scaffold. Copy to closeout-input.md and set status: pending when ready for processing." if not args.live_closeout else "Live closeout input. Fill the factual fields and keep status: pending for the closing agent.",
    }
    rendered = render_template(template, values)
    result = {"opportunity_path": str(path), "target_path": str(target), "slug": slug, "title": title}
    if target.exists() and not args.force:
        result["status"] = "skipped-existing"
        return result
    if args.dry_run:
        result["status"] = "would-create" if not target.exists() else "would-overwrite"
        return result
    target.write_text(rendered, encoding="utf-8")
    result["status"] = "created" if not args.force else ("overwritten" if target.exists() else "created")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--opportunity", help="Path to one opportunities/<slug>/opportunity.md")
    group.add_argument("--all", action="store_true", help="Process all opportunities/*/opportunity.md")
    parser.add_argument("--examples-only", action="store_true", help="Create closeout-input.example.md files (default)")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT), help="Vault path (default: ~/personal_vault)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing target files")
    parser.add_argument("--live-closeout", action="store_true", help="Create closeout-input.md instead of .example")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be created")
    args = parser.parse_args()
    if args.examples_only and args.live_closeout:
        raise SystemExit("--examples-only and --live-closeout are mutually exclusive")

    vault = Path(args.vault).expanduser().resolve()
    mode = "live-closeout" if args.live_closeout else "examples-only"
    template_path = vault / TEMPLATE_REL
    errors: list[dict[str, str]] = []
    results: list[dict[str, object]] = []
    try:
        template = template_path.read_text(encoding="utf-8")
        paths = opportunity_paths(vault, args.opportunity, args.all)
        for path in paths:
            try:
                results.append(scaffold_one(path, vault, template, args))
            except Exception as exc:
                errors.append({"path": str(path), "error": repr(exc)})
    except Exception as exc:
        errors.append({"path": str(template_path), "error": repr(exc)})
        paths = []

    created = [r["target_path"] for r in results if r.get("status") in {"created", "overwritten"}]
    would_create = [r["target_path"] for r in results if r.get("status") in {"would-create", "would-overwrite"}]
    skipped = [r["target_path"] for r in results if r.get("status") == "skipped-existing"]
    item_errors = [{"path": r.get("opportunity_path", ""), "target_path": r.get("target_path", ""), "error": r.get("error", "unknown")} for r in results if r.get("status") == "error"]
    all_errors = errors + item_errors

    print(json.dumps({
        "wakeAgent": bool(all_errors),
        "script": "opportunity_scaffold.py",
        "dry_run": args.dry_run,
        "mode": mode,
        "vault": str(vault),
        "opportunity_count": len(paths),
        "created_count": len(created),
        "would_create_count": len(would_create),
        "skipped_existing_count": len(skipped),
        "error_count": len(all_errors),
        "created": created,
        "would_create": would_create,
        "skipped_existing": skipped,
        "errors": all_errors,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
