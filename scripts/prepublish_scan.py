#!/usr/bin/env python3
"""Pre-publish safety scan (UPDATE-005 step 1). Prints and writes COUNTS ONLY, never a matched value.

    .venv/bin/python scripts/prepublish_scan.py [--ref HEAD] [--out docs/reviews/prepublish-scan.md]

Scans the files tracked at --ref (what would be published) and, separately, every blob in the full git history.
Patterns: the actual values in .env (exact match), bearer/API-token shapes, the user's home path and username,
customer names from the simulator that aren't the demo fixtures' names, and the spike canaries. Also runs gitleaks
(if installed) on the history, with its findings redacted, and records the published tree's size.
"""
from __future__ import annotations

import argparse
import getpass
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import mmlib  # noqa: E402

TOKEN_SHAPES = {
    "bearer token": re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}"),
    "switch/api key shape (sk_/swk_/pat_)": re.compile(r"\b(?:sk|swk|pat|ghp|gho|github_pat)_[A-Za-z0-9_]{16,}"),
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----\s*\n[A-Za-z0-9+/=]{40,}"),  # a real body, not a test string
    "JWT": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "password assignment": re.compile(r"(?i)\b[A-Z_]*PASSWORD\s*[=:]\s*['\"]?[^\s'\"<>{}$]{6,}"),
}
# Transcripts: where a REAL customer name would be a leak. Elsewhere the simulator's fictional demo names are fixtures.
TRANSCRIPT = re.compile(r"^(rehearsals/|spikes/.*\.(md|log|txt|jsonl)$|console/fixtures/)|\.log$|\.events\.jsonl$")
CANARIES = re.compile(r"CANARY[-_][A-Z0-9-]{4,}|BLOCKME-[A-Z0-9]{4,}")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def blob(sha: str) -> str:
    return subprocess.run(["git", "cat-file", "blob", sha], cwd=ROOT, capture_output=True).stdout.decode("utf-8", "replace")


def secret_values() -> dict[str, str]:
    env = mmlib.load_env()
    keep = ("PASSWORD", "SECRET", "TOKEN", "KEY")
    vals = {k: v for k, v in env.items() if any(x in k for x in keep) and v and len(v) >= 6}
    for f in ("neutral/notary/.credentials.json", "console/server/.credentials.json"):
        p = ROOT / f
        if p.exists():
            vals[f"{f}:api_key"] = json.loads(p.read_text()).get("api_key", "")
    return {k: v for k, v in vals.items() if v}


def customer_names() -> set[str]:
    import simulate  # scripts/simulate.py: the 60 simulated customers
    return {part for c in simulate.customers() for part in c["name"].split() if len(part) >= 4}


def scan_text(text: str, secrets_: dict[str, str], names: set[str], home: str, user: str, path: str = "") -> Counter:
    c: Counter = Counter()
    for k, v in secrets_.items():
        if v in text:
            c[f".env/credential value {k}"] += text.count(v)
    for label, rx in TOKEN_SHAPES.items():
        c[label] += len(rx.findall(text))
    c["home path"] += text.count(home)
    c["username"] += len(re.findall(rf"\b{re.escape(user)}\b", text))
    c["canary string"] += len(CANARIES.findall(text))
    if TRANSCRIPT.search(path):
        c["customer name in a transcript"] += sum(1 for n in names if re.search(rf"\b{re.escape(n)}\b", text))
    return +c


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="HEAD")
    ap.add_argument("--out", default=str(ROOT / "docs/reviews/prepublish-scan.md"))
    args = ap.parse_args()
    secrets_, names, home, user = secret_values(), customer_names(), str(Path.home()), getpass.getuser()

    tree: dict[str, Counter] = {}
    size = 0
    for line in git("ls-tree", "-r", "-l", args.ref).splitlines():
        meta, path = line.split("\t", 1)
        _, _, sha, sz = meta.split()
        size += int(sz)
        hits = scan_text(blob(sha), secrets_, names, home, user, path)
        if hits:
            tree[path] = hits

    hist: Counter = Counter()
    hist_files: set[str] = set()
    for line in git("rev-list", "--all", "--objects").splitlines():
        parts = line.split(" ", 1)
        if len(parts) != 2:
            continue
        sha, path = parts
        if git("cat-file", "-t", sha).strip() != "blob":
            continue
        hits = scan_text(blob(sha), secrets_, names, home, user, path)
        if hits:
            hist.update(hits)
            hist_files.add(path)

    leaks = None
    if shutil.which("gitleaks"):
        rep = ROOT / ".tmp/gitleaks.json"
        rep.parent.mkdir(exist_ok=True)
        subprocess.run(["gitleaks", "detect", "--source", str(ROOT), "--redact", "--no-banner", "-f", "json", "-r", str(rep)],
                       capture_output=True, text=True)
        findings = json.loads(rep.read_text() or "[]") if rep.exists() else []
        leaks = Counter(f.get("RuleID", "?") for f in findings)
        rep.unlink(missing_ok=True)

    pack = git("count-objects", "-vH")
    lines = [f"# Pre-publish scan ({args.ref} = `{git('rev-parse', '--short', args.ref).strip()}`)", "",
             "Counts only; no matched value is printed or stored.", "",
             f"**Published tree:** {len(git('ls-tree', '-r', '--name-only', args.ref).splitlines())} files, "
             f"{size / 1024 / 1024:.2f} MB. **.git:** " + "; ".join(l for l in pack.splitlines() if l.startswith(("size-pack", "count"))), "",
             "## Files at the published ref", ""]
    if tree:
        lines += ["| File | Findings |", "|---|---|"] + [f"| `{p}` | {', '.join(f'{k} ×{v}' for k, v in c.items())} |" for p, c in sorted(tree.items())]
    else:
        lines += ["None."]
    lines += ["", "## Full history (every blob reachable from any ref)", ""]
    lines += [f"- {k}: {v}" for k, v in hist.most_common()] or ["- none"]
    if hist_files:
        lines += ["", f"Paths involved in history: {len(hist_files)} (" + ", ".join(sorted(hist_files)[:15]) + (" …" if len(hist_files) > 15 else "") + ")"]
    lines += ["", "## gitleaks (history, redacted)", ""]
    lines += (["- not installed"] if leaks is None else [f"- {k}: {v}" for k, v in leaks.most_common()] or ["- no findings"])
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 1 if tree else 0


if __name__ == "__main__":
    sys.exit(main())
