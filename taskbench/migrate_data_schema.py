"""One-time migration: the shipped data_*/data.json files use field names
and string-encoded JSON that don't match what task_eval.py reads.

Confirmed by running task_eval.py against the shipped data unmodified:
`KeyError: 'task_nodes'`. The same mismatch exists in the upstream
microsoft/JARVIS repo, so this predates this fork's dependency bump.

task_eval.py reads (as native Python objects, not strings):
  data["task_nodes"], data["task_links"], data["task_steps"]

The shipped data.json instead has tool_nodes/tool_links/tool_steps, each
JSON-encoded as a string (e.g. '[{"task": "...", "arguments": [...]}]'
rather than the parsed list). This script renames the three keys and
parses their string values into native lists, in place, for all three
domains. It does NOT touch `instruction` (data.json's own paraphrase of the
request) or user_requests.json's `user_request` (what inference.py actually
sends to models) -- task_eval.py never reads either, so there's nothing to
migrate there; they're deliberately two different strings.

Idempotent: re-running on already-migrated data is a no-op (skips records
that already have task_nodes as a native list).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

RENAME = {
    "tool_nodes": "task_nodes",
    "tool_links": "task_links",
    "tool_steps": "task_steps",
}

DOMAINS = ("data_huggingface", "data_multimedia", "data_dailylifeapis")


def migrate_record(record: dict) -> dict:
    for old_key, new_key in RENAME.items():
        if old_key in record:
            value = record.pop(old_key)
            if isinstance(value, str):
                value = json.loads(value)
            record[new_key] = value
        elif new_key in record and isinstance(record[new_key], str):
            record[new_key] = json.loads(record[new_key])
    return record


def migrate_file(path: Path) -> tuple[int, int]:
    lines = path.read_text().splitlines()
    migrated = []
    changed = 0
    for line in lines:
        if not line.strip():
            continue
        record = json.loads(line)
        before = dict(record)
        record = migrate_record(record)
        if record != before:
            changed += 1
        migrated.append(json.dumps(record))

    backup = path.with_suffix(path.suffix + ".pre_migration_backup")
    if not backup.exists():
        shutil.copy2(path, backup)

    path.write_text("\n".join(migrated) + "\n")
    return len(migrated), changed


def main() -> None:
    root = Path(__file__).resolve().parent
    for domain in DOMAINS:
        data_json = root / domain / "data.json"
        if not data_json.exists():
            print(f"skip {domain}: no data.json")
            continue
        total, changed = migrate_file(data_json)
        print(f"{domain}: {changed}/{total} records migrated (backup: {data_json.name}.pre_migration_backup)")


if __name__ == "__main__":
    main()
