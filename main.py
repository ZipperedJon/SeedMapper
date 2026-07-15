"""Entry point for SeedMapper.

Run with:      python main.py
Self-check:    python main.py --diag [output_file]
"""

import sys


def _diag(out_path: str | None) -> None:
    """Write a world-gen self-check report, then exit. Useful for confirming a
    packaged build can load its cubiomes DLL."""
    from seedmapper import __version__, biomes, engine

    lines = [f"SeedMapper {__version__}"]
    lines.append(f"engine available: {engine.available()}")
    lines.append(f"engine error: {engine.load_error()}")
    lines.append(f"MC newest const: {engine._load().sm_mc_newest() if engine.available() else 'n/a'}")
    if engine.available():
        provider = biomes.get_provider("12345", "1.21.3", "overworld")
        img = provider.render(-2000, -2000, 2000, 2000, 48, 48) if provider else None
        lines.append(f"biome render ok: {img is not None} size={img.size if img else None}")
        vills = engine.find_structures(engine.ST.Village, "1.21.3", "12345",
                                       "overworld", -3000, -3000, 3000, 3000)
        lines.append(f"villages found (+/-3000): {len(vills) if vills not in (None, engine.TOO_BROAD) else vills}")
    report = "\n".join(lines)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(report + "\n")
    else:
        print(report)


if __name__ == "__main__":
    if "--diag" in sys.argv:
        idx = sys.argv.index("--diag")
        out = sys.argv[idx + 1] if len(sys.argv) > idx + 1 else None
        _diag(out)
    else:
        from seedmapper.app import run
        run()
