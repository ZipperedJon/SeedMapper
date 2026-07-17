"""Biome id -> RGB colour table, roughly matching common map-viewer palettes.

Ids come from cubiomes' BiomeID enum. Unmapped ids fall back to grey; the
"modified"/"hills" variants (base id + 128, or nearby ids) reuse a base tone.
"""

from __future__ import annotations

# Core, hand-picked colours for the biomes people actually navigate by.
BIOME_COLORS: dict[int, tuple[int, int, int]] = {
    -1: (80, 80, 80),      # none
    0:  (45, 62, 128),     # ocean
    1:  (141, 179, 96),    # plains
    2:  (250, 223, 152),   # desert
    3:  (96, 96, 96),      # mountains / windswept hills
    4:  (5, 102, 33),      # forest
    5:  (11, 102, 89),     # taiga
    6:  (82, 110, 79),     # swamp
    7:  (61, 90, 163),     # river
    8:  (122, 20, 20),     # nether wastes
    9:  (128, 128, 160),   # the end
    10: (112, 112, 160),   # frozen ocean
    11: (160, 160, 255),   # frozen river
    12: (240, 244, 248),   # snowy tundra / plains
    13: (160, 160, 160),   # snowy mountains
    14: (176, 96, 176),    # mushroom fields
    15: (150, 90, 150),    # mushroom field shore
    16: (250, 222, 176),   # beach
    17: (208, 188, 132),   # desert hills
    18: (34, 85, 45),      # wooded hills
    19: (22, 90, 78),      # taiga hills
    20: (114, 120, 154),   # mountain edge
    21: (83, 123, 9),      # jungle
    22: (73, 110, 8),      # jungle hills
    23: (98, 139, 23),     # jungle edge / sparse jungle
    24: (38, 52, 110),     # deep ocean
    25: (162, 162, 132),   # stony shore
    26: (250, 240, 192),   # snowy beach
    27: (48, 116, 68),     # birch forest
    28: (43, 104, 60),     # birch forest hills
    29: (64, 81, 26),      # dark forest
    30: (49, 85, 74),      # snowy taiga
    31: (36, 63, 54),      # snowy taiga hills
    32: (89, 102, 81),     # giant tree taiga
    33: (69, 79, 62),      # giant tree taiga hills
    34: (80, 112, 80),     # wooded mountains
    35: (189, 178, 95),    # savanna
    36: (167, 157, 100),   # savanna plateau
    37: (217, 69, 21),     # badlands / mesa
    38: (176, 151, 101),   # wooded badlands plateau
    39: (202, 140, 101),   # badlands plateau
    40: (75, 75, 171),     # small end islands
    41: (128, 128, 128),   # end midlands
    42: (128, 128, 128),   # end highlands
    43: (114, 114, 114),   # end barrens
    44: (0, 162, 199),     # warm ocean
    45: (32, 122, 194),    # lukewarm ocean
    46: (48, 80, 160),     # cold ocean
    47: (0, 120, 150),     # deep warm ocean
    48: (28, 96, 150),     # deep lukewarm ocean
    49: (40, 64, 128),     # deep cold ocean
    50: (80, 80, 140),     # deep frozen ocean
    129: (181, 219, 136),  # sunflower plains
    140: (180, 220, 230),  # ice spikes
    149: (89, 123, 9),     # modified jungle
    157: (88, 116, 108),   # giant spruce taiga
    168: (118, 142, 20),   # bamboo jungle
    169: (98, 122, 15),    # bamboo jungle hills
    170: (77, 41, 41),     # soul sand valley
    171: (152, 26, 26),    # crimson forest
    172: (22, 122, 105),   # warped forest
    173: (48, 41, 41),     # basalt deltas
    174: (77, 74, 84),     # dripstone caves
    175: (40, 84, 40),     # lush caves
    177: (128, 180, 110),  # meadow
    178: (200, 220, 220),  # grove
    179: (220, 232, 236),  # snowy slopes
    180: (196, 202, 214),  # jagged peaks
    181: (208, 216, 228),  # frozen peaks
    182: (144, 144, 144),  # stony peaks
    183: (10, 20, 24),      # deep dark
    184: (76, 109, 58),    # mangrove swamp
    185: (246, 192, 208),  # cherry grove
    190: (214, 196, 74),   # sulfur caves (26.2 - not modeled by the engine yet)
}

_FALLBACK = (110, 110, 110)

# Human-readable biome names (cubiomes BiomeID ordinals).
BIOME_NAMES: dict[int, str] = {
    -1: "—", 0: "Ocean", 1: "Plains", 2: "Desert", 3: "Windswept Hills",
    4: "Forest", 5: "Taiga", 6: "Swamp", 7: "River", 8: "Nether Wastes",
    9: "The End", 10: "Frozen Ocean", 11: "Frozen River", 12: "Snowy Plains",
    13: "Snowy Mountains", 14: "Mushroom Fields", 15: "Mushroom Shore",
    16: "Beach", 17: "Desert Hills", 18: "Wooded Hills", 19: "Taiga Hills",
    20: "Mountain Edge", 21: "Jungle", 22: "Jungle Hills", 23: "Sparse Jungle",
    24: "Deep Ocean", 25: "Stony Shore", 26: "Snowy Beach", 27: "Birch Forest",
    28: "Birch Forest Hills", 29: "Dark Forest", 30: "Snowy Taiga",
    31: "Snowy Taiga Hills", 32: "Old Growth Pine Taiga", 33: "Giant Tree Taiga Hills",
    34: "Windswept Forest", 35: "Savanna", 36: "Savanna Plateau", 37: "Badlands",
    38: "Wooded Badlands", 39: "Badlands Plateau", 40: "Small End Islands",
    41: "End Midlands", 42: "End Highlands", 43: "End Barrens", 44: "Warm Ocean",
    45: "Lukewarm Ocean", 46: "Cold Ocean", 47: "Deep Warm Ocean",
    48: "Deep Lukewarm Ocean", 49: "Deep Cold Ocean", 50: "Deep Frozen Ocean",
    129: "Sunflower Plains", 130: "Desert Lakes", 140: "Ice Spikes",
    149: "Modified Jungle", 157: "Old Growth Spruce Taiga", 168: "Bamboo Jungle",
    169: "Bamboo Jungle Hills", 170: "Soul Sand Valley", 171: "Crimson Forest",
    172: "Warped Forest", 173: "Basalt Deltas", 174: "Dripstone Caves",
    175: "Lush Caves", 177: "Meadow", 178: "Grove", 179: "Snowy Slopes",
    180: "Jagged Peaks", 181: "Frozen Peaks", 182: "Stony Peaks", 183: "Deep Dark",
    184: "Mangrove Swamp", 185: "Cherry Grove",
    190: "Sulfur Caves",   # 26.2 addition; engine can't generate it yet
}


# Reverse lookup and a sorted list for UI (name, id), de-duplicated by name.
_seen = set()
BIOME_CHOICES = []
for _bid, _name in sorted(BIOME_NAMES.items(), key=lambda kv: kv[1]):
    if _bid < 0 or _name in _seen:
        continue
    _seen.add(_name)
    BIOME_CHOICES.append((_name, _bid))
BIOME_NAME_TO_ID = {name.lower(): bid for name, bid in BIOME_CHOICES}

# Biome ids that only generate in the Nether / End.
NETHER_IDS = {8, 170, 171, 172, 173}
END_IDS = {9, 40, 41, 42, 43}


def biome_choices(dimension: str) -> list:
    """(name, id) pairs that can appear in the given dimension."""
    if dimension == "nether":
        ids = NETHER_IDS
    elif dimension == "end":
        ids = END_IDS
    else:  # overworld: everything that isn't Nether/End
        ids = None
    out = []
    for name, bid in BIOME_CHOICES:
        if ids is None:
            if bid not in NETHER_IDS and bid not in END_IDS:
                out.append((name, bid))
        elif bid in ids:
            out.append((name, bid))
    return out


def biome_id_from_name(name: str):
    return BIOME_NAME_TO_ID.get((name or "").strip().lower())


def biome_name(bid: int) -> str:
    if bid in BIOME_NAMES:
        return BIOME_NAMES[bid]
    if bid >= 128 and (bid - 128) in BIOME_NAMES:
        return BIOME_NAMES[bid - 128] + " (variant)"
    return f"Biome {bid}"


def biome_color(bid: int) -> tuple[int, int, int]:
    """Return an RGB colour for a biome id, with graceful fallbacks."""
    if bid in BIOME_COLORS:
        return BIOME_COLORS[bid]
    # "Modified" variants are base id + 128 -> reuse the base colour, tinted.
    if bid >= 128 and (bid - 128) in BIOME_COLORS:
        r, g, b = BIOME_COLORS[bid - 128]
        return (min(255, r + 20), min(255, g + 20), min(255, b + 20))
    return _FALLBACK
