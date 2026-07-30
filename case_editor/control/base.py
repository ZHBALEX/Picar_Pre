from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from case_editor.data_facts import CaseFacts


@dataclass(frozen=True)
class SyncChange:
    control_file: str
    field: str
    current: Any
    desired: Any
    source: str
    mode: str = "authoritative"


@dataclass(frozen=True)
class SyncIssue:
    severity: str
    message: str


@dataclass
class SyncPlan:
    case_dir: Path
    profile: str
    facts: CaseFacts
    changes: list[SyncChange] = field(default_factory=list)
    issues: list[SyncIssue] = field(default_factory=list)
    written_files: list[Path] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)

    def format_report(self) -> str:
        lines = [
            "Setup Sync Plan",
            "===============",
            f"Case dir : {self.case_dir}",
            f"Profile  : {self.profile}",
            f"Changes  : {len(self.changes)}",
            f"Status   : {'BLOCKED' if self.has_errors else 'READY'}",
        ]
        if self.changes:
            lines.extend(["", "Planned Changes", "---------------"])
            for change in self.changes:
                lines.append(
                    f"- {change.control_file} :: {change.field}: "
                    f"{_format_value(change.current)} -> {_format_value(change.desired)} "
                    f"[{change.source}]"
                )
        else:
            lines.extend(["", "No setup changes are needed."])

        if self.issues:
            lines.extend(["", "Checks", "------"])
            for issue in self.issues:
                lines.append(f"- {issue.severity.upper()}: {issue.message}")

        if self.written_files:
            lines.extend(["", "Written Files", "-------------"])
            lines.extend(f"- {path}" for path in self.written_files)
        return "\n".join(lines)


class ControlProfile(ABC):
    name: str

    @abstractmethod
    def plan(self, case_dir: str | Path, facts: CaseFacts) -> SyncPlan:
        raise NotImplementedError

    @abstractmethod
    def apply(self, plan: SyncPlan) -> list[Path]:
        raise NotImplementedError


def _format_value(value: Any) -> str:
    if isinstance(value, (tuple, list)):
        return "(" + ", ".join(_format_value(item) for item in value) + ")"
    if isinstance(value, float):
        return f"{value:.16g}"
    return str(value)
