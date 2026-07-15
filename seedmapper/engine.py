"""World-generation engine: a ctypes wrapper over our bundled cubiomes.dll.

The DLL is compiled from the vendored cubiomes source (see native/). It exposes
fast batch biome fills and per-structure region searches, and supports
Minecraft versions up to 1.21. If the DLL cannot be loaded, `available()`
returns False and the app degrades to a grid + waypoint mapper.
"""

from __future__ import annotations

import ctypes
import os
import sys
from typing import Optional

# --------------------------------------------------------------------------- #
# Minecraft versions (label -> cubiomes MCVersion enum ordinal).
# Ordinals come from the vendored cubiomes biomes.h enum. Newest first.
# --------------------------------------------------------------------------- #
VERSION_LIST: list[tuple[str, int]] = [
    ("1.21 (snapshot)", 28),   # MC_1_21_WD
    ("1.21.3", 27),
    ("1.21.1", 26),
    ("1.20.6", 25),
    ("1.19.4", 24),
    ("1.19.2", 23),
    ("1.18.2", 22),
    ("1.17.1", 21),
    ("1.16.5", 20),
    ("1.16.1", 19),
    ("1.15.2", 18),
    ("1.14.4", 17),
    ("1.13.2", 16),
    ("1.12.2", 15),
    ("1.11.2", 14),
    ("1.10.2", 13),
    ("1.9.4", 12),
    ("1.8.9", 11),
    ("1.7.10", 10),
]
VERSION_LABELS = [label for label, _ in VERSION_LIST]
DEFAULT_VERSION = "1.21.3"
_LABEL_TO_CONST = {label: const for label, const in VERSION_LIST}

DIMENSIONS = {"overworld": 0, "nether": -1, "end": 1}


def version_const(label: str) -> int:
    """Map a version label to a cubiomes constant, with sensible fallbacks."""
    label = (label or "").strip()
    if label in _LABEL_TO_CONST:
        return _LABEL_TO_CONST[label]
    # Match on major.minor prefix, e.g. "1.20" or "1.20.1" -> first "1.20.x".
    parts = label.split(".")
    if len(parts) >= 2:
        prefix = f"{parts[0]}.{parts[1]}"
        for lab, const in VERSION_LIST:
            if lab.startswith(prefix):
                return const
    return _LABEL_TO_CONST[DEFAULT_VERSION]


def normalize_version(label: str) -> str:
    """Return the canonical label we store, mapping legacy strings forward."""
    label = (label or "").strip()
    if label in _LABEL_TO_CONST:
        return label
    parts = label.split(".")
    if len(parts) >= 2:
        prefix = f"{parts[0]}.{parts[1]}"
        for lab, _ in VERSION_LIST:
            if lab.startswith(prefix):
                return lab
    return DEFAULT_VERSION


# --------------------------------------------------------------------------- #
# Structures we can overlay (cubiomes StructureType ordinals from finders.h).
# --------------------------------------------------------------------------- #
class ST:
    Desert_Pyramid = 1
    Jungle_Temple = 2
    Swamp_Hut = 3
    Igloo = 4
    Village = 5
    Ocean_Ruin = 6
    Shipwreck = 7
    Monument = 8
    Mansion = 9
    Outpost = 10
    Ruined_Portal = 11
    Ancient_City = 13
    Treasure = 14
    Fortress = 18
    Bastion = 19
    End_City = 20
    Trail_Ruins = 23
    Trial_Chambers = 24


# key, label, structure type, dimension, colour, short symbol, default-on
STRUCTURES: list[dict] = [
    {"key": "village",   "label": "Village",          "type": ST.Village,        "dim": "overworld", "color": "#d8b26e", "sym": "V",  "on": True},
    {"key": "outpost",   "label": "Pillager Outpost", "type": ST.Outpost,        "dim": "overworld", "color": "#c0603a", "sym": "P",  "on": True},
    {"key": "monument",  "label": "Ocean Monument",   "type": ST.Monument,       "dim": "overworld", "color": "#2fb4c4", "sym": "M",  "on": True},
    {"key": "mansion",   "label": "Woodland Mansion", "type": ST.Mansion,        "dim": "overworld", "color": "#8b3a2f", "sym": "W",  "on": True},
    {"key": "desert",    "label": "Desert Pyramid",   "type": ST.Desert_Pyramid, "dim": "overworld", "color": "#e6cf6b", "sym": "D",  "on": True},
    {"key": "jungle",    "label": "Jungle Temple",    "type": ST.Jungle_Temple,  "dim": "overworld", "color": "#4a8f2f", "sym": "J",  "on": True},
    {"key": "hut",       "label": "Swamp Hut",        "type": ST.Swamp_Hut,      "dim": "overworld", "color": "#5b7a4a", "sym": "H",  "on": True},
    {"key": "igloo",     "label": "Igloo",            "type": ST.Igloo,          "dim": "overworld", "color": "#e8f0f4", "sym": "I",  "on": True},
    {"key": "ruin",      "label": "Ocean Ruin",       "type": ST.Ocean_Ruin,     "dim": "overworld", "color": "#3f9c8f", "sym": "O",  "on": False},
    {"key": "shipwreck", "label": "Shipwreck",        "type": ST.Shipwreck,      "dim": "overworld", "color": "#9c7a4a", "sym": "S",  "on": False},
    {"key": "portal",    "label": "Ruined Portal",    "type": ST.Ruined_Portal,  "dim": "overworld", "color": "#9b59b6", "sym": "R",  "on": False},
    {"key": "city",      "label": "Ancient City",     "type": ST.Ancient_City,   "dim": "overworld", "color": "#3a4a55", "sym": "A",  "on": True},
    {"key": "trail",     "label": "Trail Ruins",      "type": ST.Trail_Ruins,    "dim": "overworld", "color": "#b08b5e", "sym": "T",  "on": False},
    {"key": "trial",     "label": "Trial Chambers",   "type": ST.Trial_Chambers, "dim": "overworld", "color": "#c79a3a", "sym": "C",  "on": False},
]


# --------------------------------------------------------------------------- #
# Seed parsing (numeric, or Java String.hashCode for text seeds).
# --------------------------------------------------------------------------- #
def java_string_hashcode(text: str) -> int:
    h = 0
    for ch in text:
        h = (31 * h + ord(ch)) & 0xFFFFFFFF
    if h >= 0x80000000:
        h -= 0x100000000
    return h


def parse_seed(seed: str) -> int:
    seed = (seed or "").strip()
    if not seed:
        return 0
    try:
        return int(seed)
    except ValueError:
        return java_string_hashcode(seed)


# --------------------------------------------------------------------------- #
# DLL loading & signatures.
# --------------------------------------------------------------------------- #
_dll = None
_load_error: Optional[str] = None


def _candidate_paths() -> list[str]:
    names = ["cubiomes.dll"]
    here = os.path.dirname(os.path.abspath(__file__))
    paths = [os.path.join(here, "lib", n) for n in names]
    # Frozen (PyInstaller) fallbacks.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        for n in names:
            paths.append(os.path.join(meipass, "seedmapper", "lib", n))
            paths.append(os.path.join(meipass, "lib", n))
            paths.append(os.path.join(meipass, n))
    return paths


def _load():
    global _dll, _load_error
    if _dll is not None:
        return _dll
    for path in _candidate_paths():
        if os.path.exists(path):
            try:
                dll = ctypes.CDLL(path)
            except OSError as exc:
                _load_error = f"{path}: {exc}"
                continue
            _bind(dll)
            _dll = dll
            return dll
    if _load_error is None:
        _load_error = "cubiomes.dll not found"
    return None


def _bind(dll):
    dll.sm_mc_newest.restype = ctypes.c_int
    dll.sm_mc_newest.argtypes = []

    dll.sm_fill_biomes.restype = ctypes.c_int
    dll.sm_fill_biomes.argtypes = [
        ctypes.c_int, ctypes.c_uint64, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, ctypes.c_double, ctypes.c_double,
        ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int),
    ]

    dll.sm_find_structures.restype = ctypes.c_int
    dll.sm_find_structures.argtypes = [
        ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.POINTER(ctypes.c_int), ctypes.c_int,
    ]

    dll.sm_get_spawn.restype = ctypes.c_int
    dll.sm_get_spawn.argtypes = [
        ctypes.c_int, ctypes.c_uint64, ctypes.POINTER(ctypes.c_int)]

    dll.sm_biome_at.restype = ctypes.c_int
    dll.sm_biome_at.argtypes = [
        ctypes.c_int, ctypes.c_uint64, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, ctypes.c_int]


def available() -> bool:
    return _load() is not None


def load_error() -> Optional[str]:
    return _load_error


# --------------------------------------------------------------------------- #
# High-level API used by the app.
# --------------------------------------------------------------------------- #
def fill_biomes(mc_label: str, seed: str, dimension: str,
                x0: float, z0: float, x1: float, z1: float,
                cols: int, rows: int, y: int = 63) -> Optional[list]:
    """Return a flat list of cols*rows biome ids covering the world rect."""
    dll = _load()
    if dll is None:
        return None
    mc = version_const(mc_label)
    sd = parse_seed(seed)
    dim = DIMENSIONS.get(dimension, 0)
    stepx = (x1 - x0) / cols
    stepz = (z1 - z0) / rows
    buf = (ctypes.c_int * (cols * rows))()
    dll.sm_fill_biomes(mc, sd, dim, y, int(x0), int(z0),
                       float(stepx), float(stepz), cols, rows, buf)
    return list(buf)


# Sentinel: area spans too many regions; caller should zoom in.
TOO_BROAD = -1


def find_structures(struct_type: int, mc_label: str, seed: str, dimension: str,
                    x0: int, z0: int, x1: int, z1: int,
                    maxout: int = 4096) -> Optional[list]:
    """Return a list of (x, z) tuples, or TOO_BROAD if the area is too large."""
    dll = _load()
    if dll is None:
        return None
    mc = version_const(mc_label)
    sd = parse_seed(seed)
    dim = DIMENSIONS.get(dimension, 0)
    out = (ctypes.c_int * (2 * maxout))()
    n = dll.sm_find_structures(struct_type, mc, sd, dim,
                               int(x0), int(z0), int(x1), int(z1), out, maxout)
    if n == TOO_BROAD:
        return TOO_BROAD
    n = min(n, maxout)
    return [(out[2 * i], out[2 * i + 1]) for i in range(n)]


def biome_at(mc_label: str, seed: str, dimension: str,
             x: int, z: int, y: int = 63) -> Optional[int]:
    """Return the biome id at a single block (cheap; cached generator)."""
    dll = _load()
    if dll is None:
        return None
    dim = DIMENSIONS.get(dimension, 0)
    return dll.sm_biome_at(version_const(mc_label), parse_seed(seed),
                           dim, int(x), int(y), int(z))


def get_spawn(mc_label: str, seed: str) -> Optional[tuple[int, int]]:
    dll = _load()
    if dll is None:
        return None
    out = (ctypes.c_int * 2)()
    dll.sm_get_spawn(version_const(mc_label), parse_seed(seed), out)
    return (out[0], out[1])
