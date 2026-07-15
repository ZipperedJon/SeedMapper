"""Export waypoints to CSV and to a Markdown note with a table."""

from __future__ import annotations

import csv
from pathlib import Path

from .model import Project

CSV_COLUMNS = ["name", "dimension", "x", "y", "z", "category", "color", "notes"]


def _y(value) -> str:
    return "" if value is None else str(value)


def export_csv(project: Project, path: str | Path) -> Path:
    """Write all waypoints to a CSV file (one row per waypoint)."""
    path = Path(path)
    if path.suffix.lower() != ".csv":
        path = path.with_suffix(".csv")

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([c.upper() for c in CSV_COLUMNS])
        for w in project.waypoints:
            writer.writerow(
                [w.name, w.dimension, w.x, _y(w.y), w.z, w.category, w.color, w.notes]
            )
    return path


def _md_escape(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def export_markdown(project: Project, path: str | Path) -> Path:
    """Write a nicely formatted Markdown note containing a waypoint table."""
    path = Path(path)
    if path.suffix.lower() not in (".md", ".markdown", ".txt"):
        path = path.with_suffix(".md")

    lines: list[str] = []
    lines.append(f"# {project.name}")
    lines.append("")
    lines.append(f"- **Seed:** `{project.seed or 'unknown'}`")
    lines.append(f"- **Minecraft version:** {project.mc_version}")
    lines.append(f"- **Waypoints:** {len(project.waypoints)}")
    lines.append("")

    header = "| Name | Dimension | X | Y | Z | Category | Notes |"
    divider = "| --- | --- | ---: | ---: | ---: | --- | --- |"
    lines.append(header)
    lines.append(divider)

    for w in project.waypoints:
        lines.append(
            "| {name} | {dim} | {x} | {y} | {z} | {cat} | {notes} |".format(
                name=_md_escape(w.name),
                dim=_md_escape(w.dimension),
                x=w.x,
                y=_y(w.y),
                z=w.z,
                cat=_md_escape(w.category),
                notes=_md_escape(w.notes),
            )
        )

    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
