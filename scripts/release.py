#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
TAG_PATTERN = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def git_output(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def current_version() -> str:
    text = (ROOT / "app.py").read_text(encoding="utf-8")
    match = re.search(r'^APP_VERSION = "([^"]+)"', text, re.MULTILINE)
    if not match or not SEMVER.fullmatch(match.group(1)):
        raise SystemExit("APP_VERSION is missing or invalid")
    return match.group(1)


def latest_tag() -> str:
    tags = git_output("tag", "--sort=-v:refname").splitlines()
    return next((tag for tag in tags if TAG_PATTERN.fullmatch(tag)), "")


def next_version() -> str:
    tag = latest_tag()
    if not tag:
        return current_version()
    major, minor, patch = TAG_PATTERN.fullmatch(tag).groups()
    return f"{major}.{minor}.{int(patch) + 1}"


def replace_file(path: str, pattern: str, replacement: str, count: int = 0) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    updated, changed = re.subn(pattern, replacement, text, count=count, flags=re.MULTILINE)
    if changed == 0:
        raise SystemExit(f"Version marker not found in {path}")
    target.write_text(updated, encoding="utf-8", newline="\n")


def bump_version(version: str) -> None:
    if not SEMVER.fullmatch(version):
        raise SystemExit(f"Invalid version: {version}")
    replace_file("app.py", r'^APP_VERSION = "[^"]+"$', f'APP_VERSION = "{version}"', 1)
    replace_file(
        "Dockerfile",
        r'(org\.opencontainers\.image\.version=")[^"]+',
        rf'\g<1>{version}',
        1,
    )
    replace_file("templates/index.html", r"\d+\.\d+\.\d+", version)
    replace_file("README.md", r"\d+\.\d+\.\d+", version, 1)
    replace_file("tests/test_app.py", r"\d+\.\d+\.\d+", version)
    replace_file(
        "static/style.css",
        r"v\d+\.\d+\.\d+: child branding",
        f"v{version}: child branding",
        1,
    )


def changelog(version: str) -> None:
    tag = latest_tag()
    if tag:
        entries = git_output("log", "--pretty=format:- %s (%h)", f"{tag}..HEAD")
    else:
        entries = git_output("log", "--reverse", "--pretty=format:- %s (%h)")
    entries = entries or "- No user-facing changes recorded."
    section = (
        f"# Changelog\n\n"
        f"## v{version} - {datetime.now(timezone.utc).date().isoformat()}\n\n"
        f"{entries}\n\n"
    )

    path = ROOT / "CHANGELOG.md"
    if path.exists():
        previous = path.read_text(encoding="utf-8")
        if previous.startswith("# Changelog"):
            previous = previous[len("# Changelog"):].lstrip("\n")
        section += previous
    path.write_text(section, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("next-version", "bump-version", "changelog"))
    parser.add_argument("--version")
    args = parser.parse_args()

    if args.command == "next-version":
        print(next_version())
        return
    if not args.version:
        raise SystemExit("--version is required")
    if args.command == "bump-version":
        bump_version(args.version)
    else:
        changelog(args.version)


if __name__ == "__main__":
    main()
