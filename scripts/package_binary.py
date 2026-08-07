#!/usr/bin/env python3
"""Package a PyInstaller executable for GitHub Releases."""

from __future__ import annotations

import argparse
import re
import shutil
import stat
import sys
import tarfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
PLATFORMS = {"linux-x86_64", "windows-x86_64"}


def current_version() -> str:
    text = (ROOT / "app.py").read_text(encoding="utf-8")
    match = re.search(r'^APP_VERSION = "([^\"]+)"', text, re.MULTILINE)
    if not match or not SEMVER.fullmatch(match.group(1)):
        raise SystemExit("APP_VERSION is missing or invalid")
    return match.group(1)


def package_binary(version: str, platform: str, distpath: Path) -> Path:
    binary_name = f"RewardHub-{version}"
    executable = distpath / (f"{binary_name}.exe" if platform == "windows-x86_64" else binary_name)
    if not executable.is_file():
        raise SystemExit(f"Binary not found: {executable}")

    package_dir = ROOT / "build" / "package"
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(executable, package_dir / executable.name)
    shutil.copy2(ROOT / "BINARY_DEPLOYMENT.md", package_dir / "README.md")

    if platform == "windows-x86_64":
        archive = ROOT / "build" / f"RewardHub-{version}-{platform}.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
            for file in package_dir.iterdir():
                output.write(file, file.name)
    else:
        archive = ROOT / "build" / f"RewardHub-{version}-{platform}.tar.gz"
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        packaged_executable = package_dir / executable.name
        packaged_executable.chmod(packaged_executable.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        with tarfile.open(archive, "w:gz") as output:
            for file in package_dir.iterdir():
                output.add(file, arcname=file.name)
    return archive


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default=current_version())
    parser.add_argument("--platform", required=True, choices=sorted(PLATFORMS))
    parser.add_argument("--distpath", default=str(ROOT / "build" / "dist"))
    args = parser.parse_args()
    if not SEMVER.fullmatch(args.version):
        raise SystemExit(f"Invalid version: {args.version}")
    archive = package_binary(args.version, args.platform, Path(args.distpath).resolve())
    print(archive)


if __name__ == "__main__":
    main()
