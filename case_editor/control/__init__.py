from __future__ import annotations

from .base import ControlProfile, SyncChange, SyncIssue, SyncPlan
from .picar_current import PicarCurrentProfile


_PROFILES: dict[str, ControlProfile] = {
    "picar-current": PicarCurrentProfile(),
}


def get_control_profile(name: str = "picar-current") -> ControlProfile:
    key = name.strip().lower()
    try:
        return _PROFILES[key]
    except KeyError as exc:
        available = ", ".join(sorted(_PROFILES))
        raise ValueError(f"Unknown control profile {name!r}; available profiles: {available}") from exc


__all__ = [
    "ControlProfile",
    "PicarCurrentProfile",
    "SyncChange",
    "SyncIssue",
    "SyncPlan",
    "get_control_profile",
]
