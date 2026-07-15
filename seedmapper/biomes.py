"""Biome background rendering, backed by the bundled cubiomes engine.

Uses `engine.fill_biomes` (a single batched native call) to sample a coarse
grid of biome ids and upscale it with nearest-neighbour. Batched sampling is
fast enough (hundreds of thousands of samples/sec) to render sharp maps.
"""

from __future__ import annotations

from typing import Optional

from PIL import Image

from . import engine
from .colors import biome_color

# Compatibility shims kept for callers/tests that referenced the old module.
BACKEND_NAME = "cubiomes"
parse_seed = engine.parse_seed


def try_load_backend() -> Optional[str]:
    return BACKEND_NAME if engine.available() else None


class BiomeProvider:
    def __init__(self, seed: str, mc_version: str, dimension: str = "overworld"):
        self.seed = seed
        self.mc_version = mc_version
        self.dimension = dimension
        self._cache_key = None
        self._cache_img: Optional[Image.Image] = None

    def render(self, x0, z0, x1, z1, width, height):
        if width < 2 or height < 2 or x1 <= x0 or z1 <= z0:
            return None

        # Sample roughly one cell per 3 screen pixels, capped for speed.
        cols = max(16, min(320, int(width / 3)))
        rows = max(16, min(320, int(height / 3)))

        key = (round(x0), round(z0), round(x1), round(z1), cols, rows,
               self.seed, self.mc_version, self.dimension)
        if key == self._cache_key and self._cache_img is not None:
            return self._cache_img.resize((width, height), Image.NEAREST)

        ids = engine.fill_biomes(self.mc_version, self.seed, self.dimension,
                                 x0, z0, x1, z1, cols, rows)
        if ids is None:
            return None

        small = Image.new("RGB", (cols, rows))
        px = small.load()
        idx = 0
        for j in range(rows):
            for i in range(cols):
                px[i, j] = biome_color(ids[idx])
                idx += 1

        self._cache_key = key
        self._cache_img = small
        return small.resize((width, height), Image.NEAREST)


def get_provider(seed: str, mc_version: str,
                 dimension: str = "overworld") -> Optional[BiomeProvider]:
    if not engine.available():
        return None
    return BiomeProvider(seed, mc_version, dimension)
