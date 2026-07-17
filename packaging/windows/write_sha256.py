"""Write or verify updater-compatible SHA-256 sidecar files."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _sidecar(path: Path) -> Path:
    return Path(f"{path}.sha256")


def _payload(path: Path) -> bytes:
    return f"{_digest(path)}  {path.name}\n".encode("ascii")


def write(path: Path) -> Path:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    sidecar = _sidecar(path)
    sidecar.write_bytes(_payload(path))
    return sidecar


def check(path: Path) -> Path:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    sidecar = _sidecar(path)
    if sidecar.read_bytes() != _payload(path):
        raise ValueError(f"invalid SHA-256 sidecar: {sidecar}")
    return sidecar


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()

    action = check if args.check else write
    for value in args.files:
        sidecar = action(Path(value))
        print(sidecar)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
