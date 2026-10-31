"""Cross-platform process detection and debounced profile switching."""

from __future__ import annotations

import csv
import io
import logging
import os
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from .config import ProfileLibrary
from .models import Profile, ProfileChange

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DetectedGame:
    profile: Profile
    executable: str


def executable_basename(process_name: str) -> str:
    """Normalise a process name to a lower-case basename."""

    return Path(str(process_name).strip().strip('"')).name.lower()


def find_running_game(
    library: ProfileLibrary,
    process_names: Iterable[str],
    *,
    priority_ids: Sequence[str] = (),
) -> DetectedGame | None:
    normalised = [executable_basename(name) for name in process_names if name]
    if not normalised:
        return None
    match = library.find_by_executable(normalised, priority_ids=priority_ids)
    if match is None:
        return None
    profile, exe = match
    return DetectedGame(profile=profile, executable=exe)


def process_snapshot() -> list[str]:
    """Return running process names without requiring psutil.

    psutil is preferred because it is fast and handles access errors.  The
    fallbacks are deliberately dependency-free.
    """

    try:
        import psutil  # type: ignore
    except ImportError:
        psutil = None  # type: ignore[assignment]
    if psutil is not None:
        names: list[str] = []
        for process in psutil.process_iter(["name"]):
            try:
                name = process.info.get("name")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            if name:
                names.append(name)
        return names

    if os.name == "nt":
        try:
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            completed = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=4,
                check=False,
                creationflags=creationflags,
            )
            rows = csv.reader(io.StringIO(completed.stdout))
            return [row[0] for row in rows if row and row[0]]
        except (OSError, subprocess.SubprocessError) as exc:
            log.debug("tasklist fallback failed: %s", exc)
            return []
    try:
        completed = subprocess.run(
            ["ps", "-eo", "comm="],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
        return [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    except (OSError, subprocess.SubprocessError) as exc:
        log.debug("ps fallback failed: %s", exc)
        return []


class GameSession:
    """State machine that emits one change per game start/exit.

    Process polling may run several times per second; profile application is a
    slow serial operation and must not be repeated while the same game remains
    open.
    """

    def __init__(
        self,
        library: ProfileLibrary,
        desktop_profile_id: str = "desktop",
        *,
        priority_ids: Sequence[str] = (),
    ) -> None:
        self.library = library
        self.desktop_profile_id = desktop_profile_id
        self.priority_ids = tuple(priority_ids)
        self._current_id: str | None = None
        self._current_exe = ""
        self._current_game = ""

    @property
    def current_profile_id(self) -> str | None:
        return self._current_id

    @property
    def current_executable(self) -> str:
        return self._current_exe

    @property
    def current_game(self) -> str:
        return self._current_game

    def reset(self) -> None:
        self._current_id = None
        self._current_exe = ""
        self._current_game = ""

    def update(self, process_names: Iterable[str]) -> ProfileChange | None:
        detected = find_running_game(
            self.library,
            process_names,
            priority_ids=self.priority_ids,
        )
        if detected is not None:
            if detected.profile.id == self._current_id:
                return None
            reason = "game_switched" if self._current_id else "game_started"
            self._current_id = detected.profile.id
            self._current_exe = detected.executable
            self._current_game = detected.profile.game
            return ProfileChange(
                profile_id=detected.profile.id,
                reason=reason,
                exe=detected.executable,
                game=detected.profile.game,
            )
        if self._current_id is not None:
            self._current_id = None
            self._current_exe = ""
            self._current_game = ""
            return ProfileChange(
                profile_id=self.desktop_profile_id,
                reason="game_exited",
            )
        return None


def describe_processes(limit: int = 8) -> str:
    names = sorted({executable_basename(name) for name in process_snapshot()})
    return ", ".join(names[:limit]) + ("..." if len(names) > limit else "")
