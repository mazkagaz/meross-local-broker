#!/usr/bin/env python3
"""Copy the shared profile engine from meross-local-cloud into the broker.

Usage:
    python tools/sync_profile_engine.py --source ../meross-cloud
    python tools/sync_profile_engine.py --source ../meross-cloud --check

The broker never imports the integration at runtime. The canonical modules are
copied byte-for-byte and pinned in profile_engine/UPSTREAM.md; CI runs --check
against the same integration commit.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path

FILES = (
    "compiler.py",
    "constants.py",
    "match.py",
    "models.py",
    "paths.py",
    "registry.py",
    "runtime.py",
)
TARGET = (
    Path(__file__).resolve().parents[1]
    / "meross_local_broker/rootfs/opt/custom_broker/profile_engine"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_commit(source: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source", default=os.environ.get("MEROSS_CLOUD_REPO",
                                          "../meross-cloud"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    source = (Path(args.source).resolve()
              / "custom_components/meross_cloud/profiles")
    if not source.is_dir():
        print(f"ERROR: profiles directory not found: {source}",
              file=sys.stderr)
        return 2

    drift = []
    for name in FILES:
        upstream = source / name
        vendored = TARGET / name
        if not upstream.is_file():
            print(f"ERROR: missing upstream file {upstream}", file=sys.stderr)
            return 2
        if args.check:
            if not vendored.is_file() or digest(upstream) != digest(vendored):
                drift.append(name)
        else:
            TARGET.mkdir(parents=True, exist_ok=True)
            vendored.write_bytes(upstream.read_bytes())

    if args.check and drift:
        print("Profile engine drift: " + ", ".join(drift), file=sys.stderr)
        return 1

    commit = source_commit(Path(args.source).resolve())
    lines = [
        "# Shared profile engine — provenance",
        "",
        "Source: `mazkagaz/meross-local-cloud`, "
        "`custom_components/meross_cloud/profiles/`.",
        f"Pinned commit: `{commit}`.",
        "",
        "These files are copied byte-for-byte by "
        "`tools/sync_profile_engine.py`. Do not edit them here; update the "
        "integration, then re-run the sync tool.",
        "",
        "| File | SHA-256 |",
        "| --- | --- |",
    ]
    for name in FILES:
        lines.append(f"| `{name}` | `{digest(source / name)}` |")
    content = "\n".join(lines) + "\n"
    if args.check:
        current = TARGET / "UPSTREAM.md"
        existing = current.read_text() if current.is_file() else ""
        missing = [
            name for name in FILES
            if digest(source / name) not in existing
        ]
        if commit not in existing or missing:
            print("Profile engine UPSTREAM.md is stale: "
                  + (", ".join(missing) or "commit"), file=sys.stderr)
            return 1
    else:
        (TARGET / "UPSTREAM.md").write_text(content)

    print("Profile engine is in sync." if args.check
          else "Profile engine synced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
