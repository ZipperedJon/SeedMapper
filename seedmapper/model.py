"""Core data model: waypoints and the map project that holds them."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Optional

# Minecraft dimensions a waypoint can belong to.
DIMENSIONS = ("overworld", "nether", "end")

# A small palette offered in the UI. Users can also type any hex colour.
DEFAULT_COLORS = (
    "#e74c3c",  # red
    "#e67e22",  # orange
    "#f1c40f",  # yellow
    "#2ecc71",  # green
    "#1abc9c",  # teal
    "#3498db",  # blue
    "#9b59b6",  # purple
    "#ecf0f1",  # white
    "#95a5a6",  # grey
    "#2c3e50",  # dark
)


@dataclass
class Waypoint:
    """A single point of interest placed on the map."""

    name: str = "Waypoint"
    x: int = 0
    z: int = 0
    y: Optional[int] = None          # altitude; optional
    dimension: str = "overworld"
    color: str = "#e74c3c"
    category: str = ""               # free-form grouping label, e.g. "Village"
    notes: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Waypoint":
        # Only pull known fields so future/legacy files degrade gracefully.
        known = {f: data[f] for f in cls.__dataclass_fields__ if f in data}
        wp = cls(**known)
        if not wp.id:
            wp.id = uuid.uuid4().hex
        return wp


@dataclass
class Project:
    """A named collection of waypoints tied to a seed and MC version."""

    name: str = "Untitled Map"
    seed: str = ""
    mc_version: str = "1.21.3"
    waypoints: list = field(default_factory=list)

    def add(self, wp: Waypoint) -> None:
        self.waypoints.append(wp)

    def remove(self, wp_id: str) -> None:
        self.waypoints = [w for w in self.waypoints if w.id != wp_id]

    def get(self, wp_id: str) -> Optional[Waypoint]:
        for w in self.waypoints:
            if w.id == wp_id:
                return w
        return None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "seed": self.seed,
            "mc_version": self.mc_version,
            "waypoints": [w.to_dict() for w in self.waypoints],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Project":
        proj = cls(
            name=data.get("name", "Untitled Map"),
            seed=str(data.get("seed", "")),
            mc_version=str(data.get("mc_version", "1.21.3")),
        )
        proj.waypoints = [Waypoint.from_dict(w) for w in data.get("waypoints", [])]
        return proj
