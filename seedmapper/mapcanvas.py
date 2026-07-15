"""The interactive map: a pan/zoom grid drawn in Minecraft world coordinates.

World coordinates follow Minecraft's convention: +X is east, +Z is south.
On screen, +X goes right and +Z goes down, so the mapping is direct.

An optional *biome provider* can paint a raster background behind the grid.
The provider is any object with:

    render(x0, z0, x1, z1, width, height) -> PIL.Image | None

where (x0, z0) is the world coordinate at the top-left of the view and
(x1, z1) is the bottom-right. Returning None means "nothing to draw".
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from PIL import Image, ImageTk

from .model import Waypoint

# Zoom limits, in screen pixels per Minecraft block.
MIN_SCALE = 0.01
MAX_SCALE = 16.0

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

        # View state: world coordinate at the centre of the viewport, and the
        # zoom level in pixels per block.
        self.center_x: float = 0.0
        self.center_z: float = 0.0
        self.scale: float = 0.5

        self.waypoints: list[Waypoint] = []
        self.selected_id: Optional[str] = None
        self.add_mode: bool = False

        # Biome background support.
        self._biome_provider = None
        self._biome_enabled = False
        self._bg_photo: Optional[ImageTk.PhotoImage] = None
        self._bg_job: Optional[str] = None

        # Callbacks wired up by the app.
        self.on_coords: Callable[[float, float], None] = lambda x, z: None
        self.on_place: Callable[[int, int], None] = lambda x, z: None
        self.on_select: Callable[[Optional[str]], None] = lambda wp_id: None
        self.on_edit: Callable[[str], None] = lambda wp_id: None

        # Drag tracking (distinguish a click from a pan).
        self._drag_start = None
        self._dragged = False

        c = self.canvas
        c.bind("<ButtonPress-1>", self._on_press)
        c.bind("<B1-Motion>", self._on_drag)
        c.bind("<ButtonRelease-1>", self._on_release)
        c.bind("<Double-Button-1>", self._on_double)
        c.bind("<Motion>", self._on_motion)
        c.bind("<MouseWheel>", self._on_wheel)          # Windows / macOS
        c.bind("<Button-4>", lambda e: self._zoom_at(e.x, e.y, 1.2))   # Linux
        c.bind("<Button-5>", lambda e: self._zoom_at(e.x, e.y, 1 / 1.2))
        c.bind("<Configure>", lambda e: self.redraw())

    # ------------------------------------------------------------------ #
    # Coordinate transforms
    # ------------------------------------------------------------------ #
    def _size(self) -> tuple[int, int]:
        return max(self.canvas.winfo_width(), 1), max(self.canvas.winfo_height(), 1)

    def world_to_screen(self, x: float, z: float) -> tuple[float, float]:
        w, h = self._size()
        sx = (x - self.center_x) * self.scale + w / 2
        sy = (z - self.center_z) * self.scale + h / 2
        return sx, sy

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        w, h = self._size()
        x = (sx - w / 2) / self.scale + self.center_x
        z = (sy - h / 2) / self.scale + self.center_z
        return x, z

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def set_waypoints(self, waypoints: list[Waypoint]) -> None:
        self.waypoints = waypoints
        self.redraw()

    def set_selected(self, wp_id: Optional[str]) -> None:
        self.selected_id = wp_id
        self.redraw()

    def set_add_mode(self, enabled: bool) -> None:
        self.add_mode = enabled
        self.canvas.config(cursor="tcross" if enabled else "")

    def set_biome_provider(self, provider) -> None:
        self._biome_provider = provider
        self._request_biome_render()

    def set_biome_enabled(self, enabled: bool) -> None:
        self._biome_enabled = enabled
        if not enabled:
            self._bg_photo = None
        self._request_biome_render()

    def center_on(self, x: float, z: float) -> None:
        self.center_x = float(x)
        self.center_z = float(z)
        self.redraw()

    def go_home(self) -> None:
        self.center_x = 0.0
        self.center_z = 0.0
        self.scale = 0.5
        self.redraw()

    # ------------------------------------------------------------------ #
    # Event handlers
    # ------------------------------------------------------------------ #
    def _on_press(self, event):
        self._drag_start = (event.x, event.y, self.center_x, self.center_z)
        self._dragged = False

    def _on_drag(self, event):
        if not self._drag_start:
            return
        sx, sy, cx, cz = self._drag_start
        dx = event.x - sx
        dy = event.y - sy
        if abs(dx) > 3 or abs(dy) > 3:
            self._dragged = True
        self.center_x = cx - dx / self.scale
        self.center_z = cz - dy / self.scale
        self.redraw(defer_biome=True)

    def _on_release(self, event):
        if self._dragged:
            self._drag_start = None
            self._request_biome_render()
            return
        self._drag_start = None

        if self.add_mode:
            x, z = self.screen_to_world(event.x, event.y)
            self.on_place(round(x), round(z))
            return

        hit = self._hit_test(event.x, event.y)
        self.selected_id = hit
        self.on_select(hit)
        self.redraw()

    def _on_double(self, event):
        hit = self._hit_test(event.x, event.y)
        if hit:
            self.selected_id = hit
            self.on_edit(hit)

    def _on_motion(self, event):
        x, z = self.screen_to_world(event.x, event.y)
        self.on_coords(x, z)

    def _on_wheel(self, event):
        factor = 1.2 if event.delta > 0 else 1 / 1.2
        self._zoom_at(event.x, event.y, factor)

    def _zoom_at(self, sx, sy, factor):
        wx, wz = self.screen_to_world(sx, sy)
        self.scale = max(MIN_SCALE, min(MAX_SCALE, self.scale * factor))
        # Keep the world point under the cursor fixed after zooming.
        w, h = self._size()
        self.center_x = wx - (sx - w / 2) / self.scale
        self.center_z = wz - (sy - h / 2) / self.scale
        self.redraw(defer_biome=True)
        self._request_biome_render()

    def _hit_test(self, sx, sy, radius=10) -> Optional[str]:
        best = None
        best_d2 = radius * radius
        for w in self.waypoints:
            px, py = self.world_to_screen(w.x, w.z)
            d2 = (px - sx) ** 2 + (py - sy) ** 2
            if d2 <= best_d2:
                best_d2 = d2
                best = w.id
        return best

    # ------------------------------------------------------------------ #
    # Biome background (debounced so panning stays smooth)
    # ------------------------------------------------------------------ #
    def _request_biome_render(self):
        if self._bg_job is not None:
            self.after_cancel(self._bg_job)
        self._bg_job = self.after(120, self._render_biome_now)

    def _render_biome_now(self):
        self._bg_job = None
        if not (self._biome_enabled and self._biome_provider):
            self._bg_photo = None
            self.redraw(defer_biome=True)
            return
        w, h = self._size()
        x0, z0 = self.screen_to_world(0, 0)
        x1, z1 = self.screen_to_world(w, h)
        try:
            img = self._biome_provider.render(x0, z0, x1, z1, w, h)
        except Exception:
            img = None
        if img is not None:
            self._bg_photo = ImageTk.PhotoImage(img)
        else:
            self._bg_photo = None
        self.redraw(defer_biome=True)

    # ------------------------------------------------------------------ #
    # Drawing
    # ------------------------------------------------------------------ #
    def redraw(self, defer_biome: bool = False):
        c = self.canvas
        c.delete("all")
        w, h = self._size()

        if self._bg_photo is not None:
            c.create_image(0, 0, image=self._bg_photo, anchor="nw")

        self._draw_grid(w, h)
        self._draw_waypoints()

    def _nice_step(self) -> int:
        """Pick a grid spacing (in blocks) that renders 40-160px apart."""
        target_px = 90
        raw = target_px / self.scale
        step = 1
        steps = [1, 2, 5]
        power = 1
        while True:
            for s in steps:
                candidate = s * power
                if candidate >= raw:
                    return candidate
            power *= 10
            if power > 10_000_000:
                return power

    def _draw_grid(self, w, h):
        c = self.canvas
        step = self._nice_step()
        x0, z0 = self.screen_to_world(0, 0)
        x1, z1 = self.screen_to_world(w, h)

        start_x = int(x0 // step) * step
        gx = start_x
        while gx <= x1:
            sx, _ = self.world_to_screen(gx, 0)
            major = (gx % (step * 5) == 0)
            c.create_line(sx, 0, sx, h,
                          fill=GRID_MAJOR_COLOR if major else GRID_COLOR)
            if major:
                c.create_text(sx + 2, 2, anchor="nw", text=str(gx),
                              fill=TEXT_COLOR, font=("Segoe UI", 7))
            gx += step

        start_z = int(z0 // step) * step
        gz = start_z
        while gz <= z1:
            _, sy = self.world_to_screen(0, gz)
            major = (gz % (step * 5) == 0)
            c.create_line(0, sy, w, sy,
                          fill=GRID_MAJOR_COLOR if major else GRID_COLOR)
            if major:
                c.create_text(2, sy + 2, anchor="nw", text=str(gz),
                              fill=TEXT_COLOR, font=("Segoe UI", 7))
            gz += step

        # Axes through the world origin (0, 0).
        ox, oy = self.world_to_screen(0, 0)
        c.create_line(ox, 0, ox, h, fill=AXIS_COLOR, width=1)
        c.create_line(0, oy, w, oy, fill=AXIS_COLOR, width=1)

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
            label = wp.name
            c.create_text(sx + r + 3, sy, anchor="w", text=label,
                          fill="#e8eef5", font=("Segoe UI", 8, "bold"))
            coord = f"({wp.x}, {wp.z})"
            c.create_text(sx + r + 3, sy + 11, anchor="w", text=coord,
                          fill=TEXT_COLOR, font=("Segoe UI", 7))
