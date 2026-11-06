#!/usr/bin/env python3
"""Move a branch of this repo into the runtime checkout for a live rehearsal, with a snapshot to restore from.

The runtime checkout (default: ../crosswire) holds what this repo never does: .env, .venv, the agents' workspaces
(their identity, repos and .disclosures data) and the Console's credentials. Fixes are committed here and only
*copied* there.

    python3 scripts/runtime_sync.py snapshot <name>   # tracked files + each workspace's guards/settings
    python3 scripts/runtime_sync.py apply <name>      # snapshot, copy this repo's tracked files over, re-render guards
    python3 scripts/runtime_sync.py restore <name>    # put the snapshot back, remove files the apply added

Never written: .env, .venv/, workspace/ (except what setup.sh re-renders: each agent's hooks/ and .claude/settings.json),
switch/state/, console/server/.credentials.json, neutral/notary/.credentials.json, .tmp/ outside .tmp/snapshots/.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
RUNTIME = Path(os.environ.get("CROSSWIRE_RUNTIME", HERE.parent / "crosswire")).resolve()
SNAPS = RUNTIME / ".tmp" / "snapshots"
NEVER = (".env", ".venv/", "workspace/", "switch/state/", ".tmp/", "console/server/.credentials.json",
         "neutral/notary/.credentials.json", "node_modules/")
WORKSPACE_GUARDS = ("hooks", ".claude/settings.json", ".mcp.json")


def tracked(repo: Path) -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=repo, capture_output=True, text=True, check=True).stdout
    return [f for f in out.splitlines() if f]


def protected(rel: str) -> bool:
    return any(rel == p.rstrip("/") or rel.startswith(p) for p in NEVER) or "/node_modules/" in rel


def workspace_guard_files() -> list[str]:
    files = []
    for agent in ("payco", "shopco", "mediator"):
        ws = RUNTIME / "workspace" / agent
        for item in WORKSPACE_GUARDS:
            p = ws / item
            if p.is_dir():
                files += [str(f.relative_to(RUNTIME)) for f in p.rglob("*") if f.is_file()]
            elif p.is_file():
                files.append(str(p.relative_to(RUNTIME)))
    return files


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "-"


def snapshot(name: str) -> Path:
    SNAPS.mkdir(parents=True, exist_ok=True)
    files = [f for f in tracked(RUNTIME) if (RUNTIME / f).is_file()] + workspace_guard_files()
    out = SNAPS / f"{name}.tar.gz"
    with tarfile.open(out, "w:gz") as tar:
        for f in files:
            tar.add(RUNTIME / f, arcname=f)
    (SNAPS / f"{name}.json").write_text(json.dumps({"made": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "files": {f: sha(RUNTIME / f) for f in files},
                                                    "added_by_apply": []}, indent=1))
    print(f"snapshot {out.relative_to(RUNTIME)}: {len(files)} files")
    return out


def apply(name: str) -> None:
    snapshot(name)
    manifest_path = SNAPS / f"{name}.json"
    manifest = json.loads(manifest_path.read_text())
    changed, added = 0, []
    for rel in tracked(HERE):
        if protected(rel):
            continue
        src, dst = HERE / rel, RUNTIME / rel
        if not src.is_file():
            continue
        if dst.is_file() and sha(dst) == sha(src):
            continue
        if not dst.exists():
            added.append(rel)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        changed += 1
    manifest["added_by_apply"] = added
    manifest_path.write_text(json.dumps(manifest, indent=1))
    r = subprocess.run(["bash", "scripts/setup.sh"], cwd=RUNTIME, capture_output=True, text=True)
    print(f"applied {HERE.name}@{subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=HERE, capture_output=True, text=True).stdout.strip()}: "
          f"{changed} file(s) copied ({len(added)} new); setup.sh exit {r.returncode}")
    if r.returncode != 0:
        print(r.stderr[-800:], file=sys.stderr)
        raise SystemExit("setup.sh failed after apply: run `restore` to roll back")


def restore(name: str) -> None:
    manifest = json.loads((SNAPS / f"{name}.json").read_text())
    subprocess.run(["chflags", "-R", "nouchg", str(RUNTIME / "workspace")], capture_output=True)  # setup locks the controls
    with tarfile.open(SNAPS / f"{name}.tar.gz", "r:gz") as tar:
        tar.extractall(RUNTIME, filter="data")
    for rel in manifest.get("added_by_apply", []):
        (RUNTIME / rel).unlink(missing_ok=True)
    bad = [f for f, h in manifest["files"].items() if sha(RUNTIME / f) != h]
    print(f"restored {name}: {len(manifest['files'])} files, removed {len(manifest.get('added_by_apply', []))} added; mismatches: {len(bad)}")
    if bad:
        raise SystemExit(f"restore mismatch: {bad[:5]}")


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] not in ("snapshot", "apply", "restore"):
        print(__doc__)
        return 2
    {"snapshot": snapshot, "apply": apply, "restore": restore}[argv[0]](argv[1])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
