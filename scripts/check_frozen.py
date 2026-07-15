"""Diagnostic: verify the biome backend loads when frozen by PyInstaller."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from seedmapper import biomes

name = biomes.try_load_backend()
print("BACKEND:", name)
print("ERROR:", biomes.BACKEND_ERROR)
if name:
    p = biomes.get_provider("12345", "1.20", "overworld")
    img = p.render(-2000, -2000, 2000, 2000, 64, 64)
    print("RENDER_OK:", img is not None, img.size if img else None)
