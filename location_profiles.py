"""Location shared with the other profiles on this host (#287).

Conduit sends the user's location to one profile: the one sharing is bound
to, which keeps the store, the agreed key and the place rules. With "Share
with this host's other profiles" on in Conduit (``sharing.other_profiles``),
every other profile on the same host that is paired with the same iPhone
(the same relay installation) reads that store as its own: ``now``,
``places``, ``history``, ``distance_to``, ``locate`` and maps lookups. A
locate goes through the asking profile's own pairing, naming the sharing
profile, so the phone answers it like one of that profile's. Place rules
stay with the sharing profile.

A profile that shares location itself (talking or background on) always
reads its own store.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .location_store import LocationStore

PAIRING_FILE = "conduit-push.json"


def store_for(home: Any, make: Callable[[Any], LocationStore] = LocationStore) -> tuple[LocationStore, str | None]:
    """The store this profile reads, and the name of the profile it belongs
    to when that's another one (None for its own). ``make`` opens a store."""
    own = make(home)
    if _sharing_on(own):
        return own, None
    installation = _installation(Path(home))
    if installation:
        for name, path in profile_homes(Path(home)):
            if _installation(path) != installation:
                continue
            store = make(path)
            if not store.exists():
                continue
            view = store.snapshot()
            if view is not None and view["sharing"].get("other_profiles") is True and _on(view["sharing"]):
                return store, name
    return own, None


def profile_homes(home: Path) -> list[tuple[str, Path]]:
    """Every other Hermes profile on this host, as (name, home): the default
    profile is the root, named ones live in its profiles/ folder."""
    root = home.parent.parent if home.parent.name == "profiles" else home
    try:
        named = sorted(path for path in (root / "profiles").iterdir() if path.is_dir())
    except OSError:
        named = []
    try:
        own = home.resolve()
    except OSError:
        return []
    found = []
    for name, path in [("default", root)] + [(path.name, path) for path in named]:
        try:
            if path.resolve() != own:
                found.append((name, path))
        except OSError:
            continue
    return found


def _sharing_on(store: LocationStore) -> bool:
    if not store.exists():
        return False
    view = store.snapshot()
    return view is not None and _on(view["sharing"])


def _on(sharing: dict[str, Any]) -> bool:
    return bool(sharing.get("talking") or sharing.get("background"))


def _installation(home: Path) -> str:
    """The relay installation (the iPhone) this profile is paired with, or ""."""
    try:
        value = json.loads((home / PAIRING_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    installation = value.get("installation_id") if isinstance(value, dict) else None
    return installation if isinstance(installation, str) and value.get("credential") else ""

