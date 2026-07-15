# SeedMapper

A desktop **Minecraft seed map with custom waypoints**. Plot points of interest
on a pannable/zoomable grid, save your map to a `.msf` file, and export your
waypoints to CSV or a nicely formatted Markdown note with a table.

![status](https://img.shields.io/badge/status-active-brightgreen)

## Features

- 🗺️ **Grid map** in Minecraft world coordinates (+X east, +Z south) with pan & zoom
- 📍 **Custom waypoints** — name, X/Y/Z, dimension, category, colour, and notes
- 💾 **Save/Load** your map as a `.msf` file (self-describing JSON under the hood)
- 📤 **Export** all waypoints to **CSV** or a **Markdown note** with a table
- 🌎 **Toggleable biome layer** (Chunkbase-style) *when a world-gen backend is
  installed* — otherwise the app runs as a pure grid mapper
- 🪟 Ships as a standalone Windows `.exe` and `.msi` installer

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

## Biome layer

Accurate biome rendering uses the [cubiomes](https://github.com/Cubitect/cubiomes)
world-generation library via a Python binding. If no binding is installed the
biome toggle is disabled and the app still works as a grid + waypoint mapper.
See the releases page for builds that bundle a backend.

## License

MIT
