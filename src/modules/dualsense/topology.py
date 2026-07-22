from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping


def path_key(info: Mapping[str, Any]) -> bytes:
    """Return a stable, case-insensitive key for one hidapi path."""
    value = info.get("path", b"")
    if isinstance(value, bytes):
        return value.upper()
    return str(value).encode("utf-8", errors="surrogatepass").upper()


@dataclass(slots=True)
class StableTopology:
    """Debounce lightweight HID enumeration without opening any device."""

    required_observations: int = 2
    _counts: dict[bytes, int] = field(default_factory=dict)
    _latest: dict[bytes, dict[str, Any]] = field(default_factory=dict)

    def observe(self, interfaces: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
        current: dict[bytes, dict[str, Any]] = {}
        for source in interfaces:
            info = dict(source)
            key = path_key(info)
            if key:
                current[key] = info

        previous = self._counts
        self._counts = {
            key: previous.get(key, 0) + 1
            for key in current
        }
        self._latest = current
        threshold = max(1, int(self.required_observations))
        return tuple(
            current[key]
            for key in sorted(current)
            if self._counts[key] >= threshold
        )

    def is_present(self, path: bytes | str | None) -> bool:
        if path is None:
            return False
        return path_key({"path": path}) in self._latest

    def reset(self) -> None:
        self._counts.clear()
        self._latest.clear()
