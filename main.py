"""Entry point for SeedMapper.

Run with:      python main.py
Self-check:    python main.py --diag [output_file]
"""

import sys


def _diag(out_path: str | None) -> None:
    """Write a biome-backend self-check report, then exit. Useful for
    confirming a packaged build can load its world-gen DLL."""
    from seedmapper import __version__, biomes

    lines = [f"SeedMapper {__version__}"]
    backend = biomes.try_load_backend()
    lines.append(f"biome backend: {backend or 'NONE'}")
    lines.append(f"backend error: {biomes.BACKEND_ERROR}")
    if backend:
        provider = biomes.get_provider("12345", "1.20", "overworld")
        img = provider.render(-2000, -2000, 2000, 2000, 48, 48) if provider else None
        lines.append(f"render ok: {img is not None} size={img.size if img else None}")
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
