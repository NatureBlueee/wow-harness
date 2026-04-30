#!/bin/bash
# /toolkit handler — print .towow/toolkit-index.yaml in human-readable form.
# Exit 0 = OK; 1 = missing index; 2 = parse error.

set -eu

ROOT="$(cd "$(/Users/nature/个人项目/Towow/scripts/hooks/find-towow-root.sh)" && pwd)"
INDEX="$ROOT/.towow/toolkit-index.yaml"

if [ ! -f "$INDEX" ]; then
  echo "toolkit: index not found at $INDEX" >&2
  echo "toolkit: if this is a fresh repo, copy 99-appendix-prototypes/config/toolkit-index.yaml to .towow/" >&2
  exit 1
fi

MODE="${1:-grouped}"

python3 - "$INDEX" "$MODE" <<'PY'
import sys
import yaml

index_path, mode = sys.argv[1], sys.argv[2]
try:
    with open(index_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
except yaml.YAMLError as e:
    sys.stderr.write(f"toolkit: yaml parse error: {e}\n")
    sys.exit(2)

entries = data.get("entries", [])
active = [e for e in entries if e.get("status", "active").startswith("active")]
retired = [e for e in entries if not e.get("status", "active").startswith("active")]

print("# /toolkit — .towow/ pull-surface tooling\n")
print(data.get("purpose", "").strip() + "\n")

def render(e):
    name = e.get("name", e.get("id", "?"))
    cat = e.get("category", "-")
    status = e.get("status", "active")
    purpose = (e.get("purpose") or "").strip()
    inv = e.get("invocation")
    print(f"## {name}")
    print(f"- id: `{e.get('id')}` | category: `{cat}` | status: `{status}`")
    if purpose:
        print(f"- purpose: {purpose}")
    if isinstance(inv, str):
        print(f"- run: `{inv}`")
    elif isinstance(inv, dict):
        for k, v in inv.items():
            print(f"- run ({k}): `{v}`")
    if "entries" in e:
        print("- sub-entries:")
        for sub in e["entries"]:
            writer = sub.get("writer", "?")
            wstatus = sub.get("writer_status", "?")
            pend = sub.get("pending_retire_wp")
            retby = sub.get("retired_by_wp")
            label = wstatus
            if pend:
                label += f" (pending retire in {pend})"
            if retby:
                label += f" (retired by {retby})"
            print(f"  - `{sub.get('file')}` — writer `{writer}`, {label} — `{sub.get('invocation')}`")
    retby = e.get("retired_by_wp")
    pkt = e.get("retirement_packet")
    if retby or pkt:
        bits = []
        if retby:
            bits.append(f"retired by {retby}")
        if pkt:
            bits.append(f"packet: `{pkt}`")
        print(f"- retirement: {' | '.join(bits)}")
    print()

if mode == "all":
    for e in entries:
        render(e)
else:
    if active:
        print("---\n## Active entries\n")
        for e in active:
            render(e)
    if retired:
        print("---\n## Retired (kept for historical discoverability)\n")
        for e in retired:
            render(e)

print("---")
print(f"Index: `.towow/toolkit-index.yaml` (last_updated: {data.get('last_updated','?')}, by WP {data.get('updated_by_wp','?')})")
print("Amendment protocol: update the yaml when a .towow/ pull-tool is added or retires; do not edit this skill for entry-specific text.")
PY
