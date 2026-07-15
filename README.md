# SeedMapper

A desktop **Minecraft seed map with custom waypoints**. Plot points of interest
on a pannable/zoomable grid, save your map to a `.msf` file, and export your
waypoints to CSV or a nicely formatted Markdown note with a table.

![status](https://img.shields.io/badge/status-active-brightgreen)

## Features

- 🗺️ **Grid map** in Minecraft world coordinates (+X east, +Z south) with pan & zoom
- 🌎 **Toggleable biome layer** (Chunkbase-style) that pans and zooms *with* the grid
- 🏛️ **Structure finder** — villages, temples, monuments, mansions, outposts,
  ancient cities, trial chambers and more, each with its own icon (toggle per type)
- 🧭 **Version picker** — Minecraft **1.7 through 1.21** (including the latest snapshot)
- 📍 **Custom waypoints** — name, X/Y/Z, dimension, category, colour, and notes
- 💾 **Save/Load** your map as a `.msf` file (self-describing JSON under the hood)
- 📤 **Export** all waypoints to **CSV** or a **Markdown note** with a table
- 🎯 **Go to spawn** and **Home** shortcuts
- 🪟 Ships as a standalone Windows `.exe` and `.msi` installer

The biome/structure engine is the [cubiomes](https://github.com/Cubitect/cubiomes)
library, compiled into a bundled `cubiomes.dll`. If that DLL is missing the app
still runs as a grid + waypoint mapper (biome/structure toggles disabled).

## Running from source

```powershell
# From the project folder
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

Requires Python 3.10+.

## Using the app

1. Type your **seed** and **MC version** in the toolbar.
2. Click **Add waypoint (click map)**, then click anywhere on the grid to drop a
   point — or use the **Add** button to enter coordinates directly.
3. Double-click a waypoint (on the map or in the list) to edit it.
4. **File → Save** writes a `.msf` file.
5. **File → Export** produces a `.csv` or a `.md` note.

Pan by dragging; zoom with the mouse wheel; **Home** re-centres on (0, 0).

## The `.msf` file format

`.msf` (Minecraft Seed File) is JSON with a small header:

```json
{
  "magic": "MINECRAFT_SEED_MAP",
  "version": 1,
  "project": {
    "name": "My World",
    "seed": "12345",
    "mc_version": "1.21",
    "waypoints": [
      { "name": "Base", "x": 100, "y": 64, "z": -200,
        "dimension": "overworld", "color": "#e74c3c",
        "category": "Home", "notes": "", "id": "..." }
    ]
  }
}
```

## Building the native engine

The bundled `seedmapper/lib/cubiomes.dll` is compiled from the vendored
cubiomes source in `native/` using [ziglang](https://pypi.org/project/ziglang/)
(a self-contained C compiler — no Visual Studio needed):

```powershell
pip install ziglang
.venv\Scripts\python.exe native\build_native.py
```

A prebuilt `cubiomes.dll` is committed, so you only need this if you change the
native code or want to rebuild it yourself.

## Packaging

```powershell
.\build_exe.ps1                                  # -> dist\SeedMapper.exe
.venv\Scripts\python.exe setup.py bdist_msi      # -> dist\SeedMapper-*.msi
```

Run `SeedMapper.exe --diag report.txt` to write a self-check confirming the
engine loads (useful for verifying a packaged build).

## License

MIT
