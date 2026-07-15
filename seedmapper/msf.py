"""Read/write the .msf (Minecraft Seed File) format.

The format is JSON on disk with a small header so the file is self-describing
and easy to inspect, while still using a dedicated extension for the app.
"""

from __future__ import annotations

import json
from pathlib import Path

from .model import Project

MSF_MAGIC = "MINECRAFT_SEED_MAP"
MSF_VERSION = 1
MSF_EXTENSION = ".msf"


class MsfError(Exception):
    """Raised when a .msf file cannot be read or is not valid."""


def save(project: Project, path: str | Path) -> Path:
    """Write *project* to *path*, ensuring a .msf extension."""
    path = Path(path)
    if path.suffix.lower() != MSF_EXTENSION:
        path = path.with_suffix(MSF_EXTENSION)

    document = {
        "magic": MSF_MAGIC,
        "version": MSF_VERSION,
        "project": project.to_dict(),
    }
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return path


def load(path: str | Path) -> Project:
    """Read a .msf file and return a Project."""
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MsfError(f"Could not open file: {exc}") from exc

    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MsfError(f"File is not valid .msf (bad JSON): {exc}") from exc

    if not isinstance(document, dict) or document.get("magic") != MSF_MAGIC:
        raise MsfError("This does not look like a SeedMapper .msf file.")

    version = document.get("version", 0)
    if version > MSF_VERSION:
        raise MsfError(
            f"This file was made by a newer version of SeedMapper "
            f"(file v{version}, this app supports v{MSF_VERSION})."
        )

    project_data = document.get("project")
    if not isinstance(project_data, dict):
        raise MsfError("File is missing project data.")

    return Project.from_dict(project_data)
