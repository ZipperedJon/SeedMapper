"""Biome background rendering, backed by cubiomes (via the `cubiomespi` wheel,
which bundles a prebuilt Windows DLL - no C compiler required).

The provider samples biomes on a capped coarse grid and upscales with
nearest-neighbour, which is both fast and visually appropriate since biome
regions are chunky. If the backend is missing, `get_provider` returns None and
the app runs as a plain grid + waypoint mapper.
"""

from __future__ import annotations

from typing import Optional

from PIL import Image

from .colors import biome_color

BACKEND_NAME: Optional[str] = None
BACKEND_ERROR: Optional[str] = None

# Highest MC version the bundled cubiomes DLL knows about.
_MAX_VERSION_CONST = 25  # MCVersion.MC_1_20

# How many biome samples to take per render (trades sharpness for speed).
MAX_SAMPLES = 2600


def java_string_hashcode(text: str) -> int:
    """Reproduce Java's String.hashCode(), used by Minecraft for text seeds."""
    h = 0
    for ch in text:
        h = (31 * h + ord(ch)) & 0xFFFFFFFF
    # Wrap to signed 32-bit.
    if h >= 0x80000000:
        h -= 0x100000000
    return h


def parse_seed(seed: str) -> int:
    """Turn a user-entered seed into the integer Minecraft would use."""
    seed = (seed or "").strip()
    if not seed:
        return 0
    try:
        return int(seed)
    except ValueError:
        return java_string_hashcode(seed)


def _version_const(mc_version: str) -> int:
    """Map a version string like '1.20' to a cubiomes MCVersion constant."""
    from cubiomespi.cubiomes import MCVersion

    table = {
        "1.0": MCVersion.MC_1_0_0, "1.1": MCVersion.MC_1_1_0,
        "1.2": MCVersion.MC_1_2_5, "1.3": MCVersion.MC_1_3_2,
        "1.4": MCVersion.MC_1_4_7, "1.5": MCVersion.MC_1_5_2,
        "1.6": MCVersion.MC_1_6_4, "1.7": MCVersion.MC_1_7_10,
        "1.8": MCVersion.MC_1_8_9, "1.9": MCVersion.MC_1_9_4,
        "1.10": MCVersion.MC_1_10_2, "1.11": MCVersion.MC_1_11_2,
        "1.12": MCVersion.MC_1_12_2, "1.13": MCVersion.MC_1_13_2,
        "1.14": MCVersion.MC_1_14_4, "1.15": MCVersion.MC_1_15_2,
        "1.16": MCVersion.MC_1_16_5, "1.17": MCVersion.MC_1_17_1,
        "1.18": MCVersion.MC_1_18_2, "1.19": MCVersion.MC_1_19,
        "1.20": MCVersion.MC_1_20,
    }
    v = (mc_version or "").strip()
    if v in table:
        return table[v]
    # Match on major.minor prefix (e.g. "1.20.1" -> "1.20").
    parts = v.split(".")
    if len(parts) >= 2:
        key = f"{parts[0]}.{parts[1]}"
        if key in table:
            return table[key]
    # Newer than the DLL knows -> use the newest it supports.
    return _MAX_VERSION_CONST


class BiomeProvider:
    def render(self, x0, z0, x1, z1, width, height):
        raise NotImplementedError


class CubiomesProvider(BiomeProvider):
    def __init__(self, seed: str, mc_version: str, dimension: str = "overworld"):
        from cubiomespi.cubiomes import Dimension, Generator

        dim_map = {
            "overworld": Dimension.DIM_OVERWORLD,
            "nether": Dimension.DIM_NETHER,
            "end": Dimension.DIM_END,
        }
        self._seed_int = parse_seed(seed)
        self._version = _version_const(mc_version)
        self._dim = dim_map.get(dimension, Dimension.DIM_OVERWORLD)
        self._gen = Generator(self._version, self._seed_int, self._dim)
        self._cache_key = None
        self._cache_img: Optional[Image.Image] = None

    def render(self, x0, z0, x1, z1, width, height):
        from cubiomespi.cubiomes import get_biome_at

        if width < 2 or height < 2 or x1 <= x0 or z1 <= z0:
            return None

        # Choose a sample grid capped at MAX_SAMPLES, matching the view aspect.
        aspect = width / height
        cols = max(8, min(width, int((MAX_SAMPLES * aspect) ** 0.5)))
        rows = max(8, min(height, int(cols / aspect)))

        # Cache on rounded bounds so tiny movements reuse the last render.
        key = (round(x0), round(z0), round(x1), round(z1), cols, rows,
               self._seed_int, self._version, self._dim)
        if key == self._cache_key and self._cache_img is not None:
            return self._cache_img.resize((width, height), Image.NEAREST)

        span_x = (x1 - x0) / cols
        span_z = (z1 - z0) / rows
        y = 63  # surface-ish sample height

        small = Image.new("RGB", (cols, rows))
        px = small.load()
        g = self._gen
        for j in range(rows):
            wz = int(z0 + (j + 0.5) * span_z)
            for i in range(cols):
                wx = int(x0 + (i + 0.5) * span_x)
                px[i, j] = biome_color(get_biome_at(g, wx, y, wz))

        self._cache_key = key
        self._cache_img = small
        return small.resize((width, height), Image.NEAREST)


def try_load_backend() -> Optional[str]:
    """Detect a usable biome backend. Returns its name or None."""
    global BACKEND_NAME, BACKEND_ERROR
    try:
        import cubiomespi.cubiomes  # noqa: F401  (import triggers DLL load)
    except Exception as exc:  # noqa: BLE001
        BACKEND_ERROR = f"cubiomespi: {exc}"
        BACKEND_NAME = None
        return None
    BACKEND_NAME = "cubiomespi"
    return BACKEND_NAME


def get_provider(seed: str, mc_version: str,
                 dimension: str = "overworld") -> Optional[BiomeProvider]:
    """Return a working biome provider, or None if unavailable."""
    if try_load_backend() is None:
        return None
    try:
        return CubiomesProvider(seed, mc_version, dimension)
    except Exception as exc:  # noqa: BLE001
        global BACKEND_ERROR
        BACKEND_ERROR = f"provider init failed: {exc}"
        return None
