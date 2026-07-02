#!/usr/bin/env python3
"""Verify that expected PowerMem packages are visible on PyPI."""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


DEFAULT_PACKAGES = ("powermem", "powermem-mcp")
PYPI_JSON_URL = "https://pypi.org/pypi/{package}/json"


class ReleaseCheckError(RuntimeError):
    """Raised when a package release is missing or incomplete on PyPI."""


def parse_version(value: str) -> str:
    version = value.strip()
    if version.startswith("v"):
        version = version[1:]
    if not version:
        raise ReleaseCheckError("release version cannot be empty")
    return version


def _expected_filename_prefix(package: str, version: str) -> str:
    normalized_package = package.replace("-", "_")
    return f"{normalized_package}-{version}"


def fetch_pypi_json(package: str) -> dict:
    url = PYPI_JSON_URL.format(package=package)
    try:
        with urlopen(url, timeout=30) as response:
            return json.load(response)
    except (HTTPError, URLError, TimeoutError) as error:
        raise ReleaseCheckError(f"failed to fetch PyPI metadata for {package}: {error}")


def check_package_release(package: str, version: str, pypi_data: dict) -> None:
    releases = pypi_data.get("releases") or {}
    files = releases.get(version)
    if not files:
        raise ReleaseCheckError(f"{package} missing release {version} on PyPI")

    expected_prefix = _expected_filename_prefix(package, version)
    filenames = [file_info.get("filename", "") for file_info in files]
    matching_filenames = [
        filename for filename in filenames if filename.startswith(expected_prefix)
    ]
    if not matching_filenames:
        raise ReleaseCheckError(
            f"{package} release {version} has no files starting with {expected_prefix}"
        )

    has_wheel = any(filename.endswith(".whl") for filename in matching_filenames)
    has_sdist = any(filename.endswith(".tar.gz") for filename in matching_filenames)
    missing_types = []
    if not has_wheel:
        missing_types.append("wheel")
    if not has_sdist:
        missing_types.append("sdist")
    if missing_types:
        missing = ", ".join(missing_types)
        raise ReleaseCheckError(f"{package} release {version} is missing {missing}")


def check_packages(
    packages: list[str],
    version: str,
    *,
    fetcher: Callable[[str], dict] = fetch_pypi_json,
    retries: int = 6,
    delay_seconds: float = 10,
) -> None:
    if retries < 1:
        raise ReleaseCheckError("retries must be at least 1")
    if delay_seconds < 0:
        raise ReleaseCheckError("delay_seconds cannot be negative")

    last_error: ReleaseCheckError | None = None
    for attempt in range(1, retries + 1):
        try:
            for package in packages:
                check_package_release(package, version, fetcher(package))
            return
        except ReleaseCheckError as error:
            last_error = error
            if attempt < retries:
                time.sleep(delay_seconds)
    if last_error is not None:
        raise last_error


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify that powermem release packages are available on PyPI."
    )
    release = parser.add_mutually_exclusive_group(required=True)
    release.add_argument("--version", help="Release version, for example 1.1.6")
    release.add_argument("--tag", help="Release tag, for example v1.1.6")
    parser.add_argument("--packages", nargs="+", default=list(DEFAULT_PACKAGES))
    parser.add_argument("--retries", type=int, default=6)
    parser.add_argument("--delay-seconds", type=float, default=10)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    version = parse_version(args.version or args.tag)

    try:
        check_packages(
            args.packages,
            version,
            retries=args.retries,
            delay_seconds=args.delay_seconds,
        )
    except ReleaseCheckError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    joined_packages = ", ".join(args.packages)
    print(f"PyPI release {version} verified for: {joined_packages}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
