"""The interactive map: a pan/zoom grid drawn in Minecraft world coordinates.

World coordinates follow Minecraft's convention: +X is east, +Z is south.
On screen, +X goes right and +Z goes down, so the mapping is direct.

The biome layer is rendered slightly larger than the viewport and repositioned
via the same world->screen transform on every redraw, so it pans and zooms
together with the grid. Structure markers are drawn from world coordinates too,
so they always stay pinned to the right spot.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from PIL import Image, ImageTk

from . import icons
from .model import Waypoint

MIN_SCALE = 0.002
MAX_SCALE = 16.0

# Extra fraction of the viewport rendered around the edges so a pan reveals
# already-drawn biome pixels instead of blank space. Larger = more map loaded.
BIOME_MARGIN = 0.6

BG_COLOR = "#0e1621"
GRID_COLOR = "#22303c"
GRID_MAJOR_COLOR = "#31465a"
AXIS_COLOR = "#5b7fa6"
TEXT_COLOR = "#8ba3bd"
SELECT_COLOR = "#ffd24a"


class MapCanvas(tk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.canvas = tk.Canvas(self, bg=BG_COLOR, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.center_x: float = 0.0
        self.center_z: float = 0.0
        self.scale: float = 0.5

        self.waypoints: list[Waypoint] = []
        self.structures: list[dict] = []      # dicts: x, z, color, sym, label
        self.selected_id: Optional[str] = None
        self.add_mode: bool = False

        # Biome background state.
        self._biome_provider = None
        self._biome_enabled = False
        self._bg = None                        # dict(pil, photo, bx0, bz0, scale)
        self._settle_job: Optional[str] = None

        # Callbacks wired up by the app.
        self.on_coords: Callable[[float, float], None] = lambda x, z: None
        self.on_place: Callable[[int, int], None] = lambda x, z: None
        self.on_select: Callable[[Optional[str]], None] = lambda wp_id: None
        self.on_edit: Callable[[str], None] = lambda wp_id: None
        self.on_view_changed: Callable[[], None] = lambda: None
        self.on_hover: Callable[[Optional[str]], None] = lambda text: None
        self.on_structure_click: Callable = lambda marker, rx, ry: None

        # Structure icon images (built lazily; needs a live Tk root).
        self._icons: dict = {}
        self._icons_grey: dict = {}

        self._drag_start = None
        self._dragged = False

        c = self.canvas
        c.bind("<ButtonPress-1>", self._on_press)
        c.bind("<B1-Motion>", self._on_drag)
        c.bind("<ButtonRelease-1>", self._on_release)
        c.bind("<Double-Button-1>", self._on_double)
        c.bind("<Motion>", self._on_motion)
        c.bind("<MouseWheel>", self._on_wheel)
        c.bind("<Button-4>", lambda e: self._zoom_at(e.x, e.y, 1.2))
        c.bind("<Button-5>", lambda e: self._zoom_at(e.x, e.y, 1 / 1.2))
        c.bind("<Configure>", lambda e: (self.redraw(), self._request_settle()))

    # ------------------------------------------------------------------ #
    # Coordinate transforms
    # ------------------------------------------------------------------ #
    def _size(self) -> tuple[int, int]:
        return max(self.canvas.winfo_width(), 1), max(self.canvas.winfo_height(), 1)

    def world_to_screen(self, x: float, z: float) -> tuple[float, float]:
        w, h = self._size()
        return ((x - self.center_x) * self.scale + w / 2,
                (z - self.center_z) * self.scale + h / 2)

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        w, h = self._size()
        return ((sx - w / 2) / self.scale + self.center_x,
                (sy - h / 2) / self.scale + self.center_z)

    def view_bounds(self):
        w, h = self._size()
        x0, z0 = self.screen_to_world(0, 0)
        x1, z1 = self.screen_to_world(w, h)
        return x0, z0, x1, z1

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def set_waypoints(self, waypoints: list[Waypoint]) -> None:
        self.waypoints = waypoints
        self.redraw()

    def set_structures(self, structures: list[dict]) -> None:
        self.structures = structures
        self.redraw()

    def set_selected(self, wp_id: Optional[str]) -> None:
        self.selected_id = wp_id
        self.redraw()

    def set_add_mode(self, enabled: bool) -> None:
        self.add_mode = enabled
        self.canvas.config(cursor="tcross" if enabled else "")

    def set_biome_provider(self, provider) -> None:
        self._biome_provider = provider
        self._bg = None
        self._request_settle()

    def set_biome_enabled(self, enabled: bool) -> None:
        self._biome_enabled = enabled
        if not enabled:
            self._bg = None
            self.redraw()
        else:
            self._request_settle()

    def center_on(self, x: float, z: float) -> None:
        self.center_x = float(x)
        self.center_z = float(z)
        self.redraw()
        self._request_settle()

    def go_home(self) -> None:
        self.center_x = 0.0
        self.center_z = 0.0
        self.scale = 0.5
        self.redraw()
        self._request_settle()

    # ------------------------------------------------------------------ #
    # Events
    # ------------------------------------------------------------------ #
    def _on_press(self, event):
        self._drag_start = (event.x, event.y, self.center_x, self.center_z)
        self._dragged = False

    def _on_drag(self, event):
        if not self._drag_start:
            return
        sx, sy, cx, cz = self._drag_start
        dx, dy = event.x - sx, event.y - sy
        if abs(dx) > 3 or abs(dy) > 3:
            self._dragged = True
        self.center_x = cx - dx / self.scale
        self.center_z = cz - dy / self.scale
        self.redraw()

    def _on_release(self, event):
        was_drag = self._dragged
        self._drag_start = None
        if was_drag:
            self._request_settle()
            return
        if self.add_mode:
            x, z = self.screen_to_world(event.x, event.y)
            self.on_place(round(x), round(z))
            return
        hit = self._hit_test(event.x, event.y)
        if hit:
            self.selected_id = hit
            self.on_select(hit)
            self.redraw()
            return
        marker = self._struct_hit_test(event.x, event.y)
        if marker:
            self.on_structure_click(marker, event.x_root, event.y_root)
            return
        self.selected_id = None
        self.on_select(None)
        self.redraw()

    def _on_double(self, event):
        hit = self._hit_test(event.x, event.y)
        if hit:
            self.selected_id = hit
            self.on_edit(hit)

    def _on_motion(self, event):
        x, z = self.screen_to_world(event.x, event.y)
        self.on_coords(x, z)
        # Structure hover tooltip.
        s = self._struct_hit_test(event.x, event.y)
        if s:
            self.on_hover(f"{s['label']}  ({s['x']}, {s['z']})")
        else:
            self.on_hover(None)

    def _on_wheel(self, event):
        self._zoom_at(event.x, event.y, 1.2 if event.delta > 0 else 1 / 1.2)

    def _zoom_at(self, sx, sy, factor):
        wx, wz = self.screen_to_world(sx, sy)
        self.scale = max(MIN_SCALE, min(MAX_SCALE, self.scale * factor))
        w, h = self._size()
        self.center_x = wx - (sx - w / 2) / self.scale
        self.center_z = wz - (sy - h / 2) / self.scale
        self.redraw()
        self._request_settle()

    def _hit_test(self, sx, sy, radius=10) -> Optional[str]:
        best, best_d2 = None, radius * radius
        for wp in self.waypoints:
            px, py = self.world_to_screen(wp.x, wp.z)
            d2 = (px - sx) ** 2 + (py - sy) ** 2
            if d2 <= best_d2:
                best_d2, best = d2, wp.id
        return best

    def _struct_hit_test(self, sx, sy, radius=9):
        best, best_d2 = None, radius * radius
        for s in self.structures:
            px, py = self.world_to_screen(s["x"], s["z"])
            d2 = (px - sx) ** 2 + (py - sy) ** 2
            if d2 <= best_d2:
                best_d2, best = d2, s
        return best

    # ------------------------------------------------------------------ #
    # Settle: after movement stops, re-render biomes and let app refresh
    # structures for the new view.
    # ------------------------------------------------------------------ #
    def _request_settle(self):
        if self._settle_job is not None:
            self.after_cancel(self._settle_job)
        self._settle_job = self.after(140, self._on_settle)

    def _on_settle(self):
        self._settle_job = None
        if self._biome_enabled and self._biome_provider:
            self._render_biome()
        self.on_view_changed()
        self.redraw()

    def _render_biome(self):
        w, h = self._size()
        wv, hv = w / self.scale, h / self.scale
        ex0 = self.center_x - wv * (0.5 + BIOME_MARGIN)
        ez0 = self.center_z - hv * (0.5 + BIOME_MARGIN)
        ex1 = self.center_x + wv * (0.5 + BIOME_MARGIN)
        ez1 = self.center_z + hv * (0.5 + BIOME_MARGIN)
        pw = max(2, int(w * (1 + 2 * BIOME_MARGIN)))
        ph = max(2, int(h * (1 + 2 * BIOME_MARGIN)))
        try:
            pil = self._biome_provider.render(ex0, ez0, ex1, ez1, pw, ph)
        except Exception:
            pil = None
        if pil is None:
            self._bg = None
            return
        self._bg = {
            "pil": pil,
            "photo": ImageTk.PhotoImage(pil),
            "bx0": ex0, "bz0": ez0,
            "scale": self.scale,
        }

    # ------------------------------------------------------------------ #
    # Drawing
    # ------------------------------------------------------------------ #
    def redraw(self):
        c = self.canvas
        c.delete("all")
        w, h = self._size()
        self._draw_biome(w, h)
        self._draw_grid(w, h)
        self._draw_structures()
        self._draw_waypoints()

    def _draw_biome(self, w, h):
        if not (self._biome_enabled and self._bg):
            return
        bg = self._bg
        sx, sy = self.world_to_screen(bg["bx0"], bg["bz0"])
        if abs(self.scale - bg["scale"]) < 1e-9:
            photo = bg["photo"]
        else:
            # Zoom changed since last render: rescale until the settle redraw.
            factor = self.scale / bg["scale"]
            neww = max(1, int(bg["pil"].width * factor))
            newh = max(1, int(bg["pil"].height * factor))
            resized = bg["pil"].resize((neww, newh), Image.NEAREST)
            photo = ImageTk.PhotoImage(resized)
            self._bg["_tmp_photo"] = photo  # keep a ref alive
        self.canvas.create_image(sx, sy, image=photo, anchor="nw")

    def _nice_step(self) -> int:
        raw = 90 / self.scale
        power = 1
        while power <= 100_000_000:
            for s in (1, 2, 5):
                if s * power >= raw:
                    return s * power
            power *= 10
        return power

    def _draw_grid(self, w, h):
        c = self.canvas
        step = self._nice_step()
        x0, z0, x1, z1 = self.view_bounds()

        gx = int(x0 // step) * step
        while gx <= x1:
            sx, _ = self.world_to_screen(gx, 0)
            major = (gx % (step * 5) == 0)
            c.create_line(sx, 0, sx, h, fill=GRID_MAJOR_COLOR if major else GRID_COLOR)
            if major:
                c.create_text(sx + 2, 2, anchor="nw", text=str(gx),
                              fill=TEXT_COLOR, font=("Segoe UI", 7))
            gx += step

        gz = int(z0 // step) * step
        while gz <= z1:
            _, sy = self.world_to_screen(0, gz)
            major = (gz % (step * 5) == 0)
            c.create_line(0, sy, w, sy, fill=GRID_MAJOR_COLOR if major else GRID_COLOR)
            if major:
                c.create_text(2, sy + 2, anchor="nw", text=str(gz),
                              fill=TEXT_COLOR, font=("Segoe UI", 7))
            gz += step

        ox, oy = self.world_to_screen(0, 0)
        c.create_line(ox, 0, ox, h, fill=AXIS_COLOR)
        c.create_line(0, oy, w, oy, fill=AXIS_COLOR)

    def _ensure_icons(self):
        if self._icons:
            return
        normal, grey = icons.build_icons()
        self._icons = {k: ImageTk.PhotoImage(v) for k, v in normal.items()}
        self._icons_grey = {k: ImageTk.PhotoImage(v) for k, v in grey.items()}

    def _draw_structures(self):
        if not self.structures:
            return
        self._ensure_icons()
        c = self.canvas
        w, h = self._size()
        show_label = self.scale > 0.4
        for s in self.structures:
            sx, sy = self.world_to_screen(s["x"], s["z"])
            if sx < -20 or sy < -20 or sx > w + 20 or sy > h + 20:
                continue
            table = self._icons_grey if s.get("explored") else self._icons
            img = table.get(s["key"])
            if img is not None:
                c.create_image(sx, sy, image=img)
            else:
                c.create_rectangle(sx - 7, sy - 7, sx + 7, sy + 7,
                                   fill=s["color"], outline="#0b1119")
            if show_label:
                fill = "#7f909e" if s.get("explored") else "#cfe0ee"
                c.create_text(sx + 13, sy, anchor="w", text=s["label"],
                              fill=fill, font=("Segoe UI", 7))

    def _draw_waypoints(self):
        c = self.canvas
        for wp in self.waypoints:
            sx, sy = self.world_to_screen(wp.x, wp.z)
            selected = (wp.id == self.selected_id)
            r = 6 if selected else 5
            outline = SELECT_COLOR if selected else "#0e1621"
            width = 3 if selected else 1
            c.create_oval(sx - r, sy - r, sx + r, sy + r,
                          fill=wp.color, outline=outline, width=width)
            c.create_text(sx + r + 3, sy, anchor="w", text=wp.name,
                          fill="#e8eef5", font=("Segoe UI", 8, "bold"))
            c.create_text(sx + r + 3, sy + 11, anchor="w", text=f"({wp.x}, {wp.z})",
                          fill=TEXT_COLOR, font=("Segoe UI", 7))
