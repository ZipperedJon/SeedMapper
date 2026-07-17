"""Biome background rendering, backed by the bundled cubiomes engine.

Samples a coarse grid of biome ids (batched native call) and upscales it. An
optional terrain mode hillshades the map using approximate surface heights so
elevation/depth is visible. A depth setting chooses which Y-slice of biomes to
show (surface, underground, or bottom).
"""

from __future__ import annotations

from typing import Optional

from PIL import Image

from . import cache, engine
from .colors import biome_color

BACKEND_NAME = "cubiomes"
parse_seed = engine.parse_seed

# Depth presets: label -> Y level sampled for biomes. (MC 1.18+ has 3D biomes;
# underground is mostly the surface biome with cave-biome pockets.)
DEPTHS = [("Surface", 90), ("Underground (caves)", 16), ("Bottom (y=-51)", -51)]
DEPTH_LABELS = [d[0] for d in DEPTHS]
DEFAULT_DEPTH = "Surface"
_DEPTH_Y = {label: y for label, y in DEPTHS}


def depth_y(label: str) -> int:
    return _DEPTH_Y.get(label, 90)


def try_load_backend() -> Optional[str]:
    return BACKEND_NAME if engine.available() else None


class BiomeProvider:
    def __init__(self, seed: str, mc_version: str, dimension: str = "overworld"):
        self.seed = seed
        self.mc_version = mc_version
        self.dimension = dimension
        self.depth = DEFAULT_DEPTH
        self.terrain = False
        self.highlight: set = set()   # biome ids to highlight (others dimmed)

    def render(self, x0, z0, x1, z1, width, height, max_cols=256):
        if width < 2 or height < 2 or x1 <= x0 or z1 <= z0:
            return None

        # ~1 sample per 4 screen px (upscaled), capped. A smaller max_cols gives
        # a coarse but near-instant render (used while moving).
        cols = max(16, min(max_cols, int(width / 4)))
        rows = max(16, min(max_cols, int(height / 4)))
        y = depth_y(self.depth)

        hl = tuple(sorted(self.highlight))
        key = cache.key_hash((round(x0), round(z0), round(x1), round(z1), cols, rows,
                              self.seed, self.mc_version, self.dimension, y,
                              self.terrain, hl))
        cached = cache.get(key)
        if cached is not None:
            return cached.resize((width, height), Image.NEAREST)

        ids = engine.fill_biomes(self.mc_version, self.seed, self.dimension,
                                 x0, z0, x1, z1, cols, rows, y=y)
        if ids is None:
            return None

        if hl:
            colours = []
            for b in ids:
                if b in hl:
                    colours.append(biome_color(b))
                else:
                    r, g, b2 = biome_color(b)
                    v = (int(0.3 * r + 0.59 * g + 0.11 * b2) + 40) // 2
                    colours.append((v, v, v))
        else:
            colours = [biome_color(b) for b in ids]

        if self.terrain:
            heights = engine.fill_heights(self.mc_version, self.seed,
                                          self.dimension, x0, z0, x1, z1, cols, rows)
            if heights:
                colours = self._hillshade(colours, heights, cols, rows)

        small = Image.new("RGB", (cols, rows))
        small.putdata(colours)

        cache.put(key, small)
        return small.resize((width, height), Image.NEAREST)

    @staticmethod
    def _hillshade(colours, heights, cols, rows):
        """Shade each cell by local slope so terrain relief is visible."""
        out = []
        K = 0.08
        for j in range(rows):
            for i in range(cols):
                idx = j * cols + i
                hl = heights[idx - 1] if i > 0 else heights[idx]
                hr = heights[idx + 1] if i < cols - 1 else heights[idx]
                hu = heights[idx - cols] if j > 0 else heights[idx]
                hd = heights[idx + cols] if j < rows - 1 else heights[idx]
                # Light from the north-west: down-right slopes darken.
                slope = (hr - hl) + (hd - hu)
                shade = 1.0 + slope * K
                # Gentle elevation tint: high ground brightens a touch.
                shade += (heights[idx] - 63) * 0.002
                shade = 0.5 if shade < 0.5 else (1.6 if shade > 1.6 else shade)
                r, g, b = colours[idx]
                out.append((min(255, int(r * shade)),
                            min(255, int(g * shade)),
                            min(255, int(b * shade))))
        return out


def get_provider(seed: str, mc_version: str,
                 dimension: str = "overworld") -> Optional[BiomeProvider]:
    if not engine.available():
        return None
    return BiomeProvider(seed, mc_version, dimension)
