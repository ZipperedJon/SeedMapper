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
from tkinter import ttk
from typing import Callable, Optional

from PIL import Image, ImageTk

from . import icons
from .model import Waypoint

MIN_SCALE = 0.002
MAX_SCALE = 16.0

# Extra fraction of the viewport rendered around the edges so a pan reveals
# already-drawn biome pixels instead of blank space. Larger = more map loaded
# at once and fewer regenerations while panning (smoother movement).
BIOME_MARGIN = 1.0

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
        self.dimension: str = "overworld"     # only same-dim waypoints are drawn
        self._callout = None

        # Biome background state.
        self._biome_provider = None
        self._biome_enabled = False
        self._bg = None                        # dict(pil, photo, bounds, scale, full)
        self._settle_job: Optional[str] = None
        self._sharpen_job: Optional[str] = None

        # Callbacks wired up by the app.
        self.on_coords: Callable[[float, float], None] = lambda x, z: None
        self.on_place: Callable[[int, int], None] = lambda x, z: None
        self.on_select: Callable[[Optional[str]], None] = lambda wp_id: None
        self.on_edit: Callable[[str], None] = lambda wp_id: None
        self.on_view_changed: Callable[[], None] = lambda: None
        self.on_hover: Callable[[Optional[str]], None] = lambda text: None
        self.on_structure_click: Callable = lambda marker, rx, ry: None
        self.on_delete: Callable[[str], None] = lambda wp_id: None
        self.on_context: Callable = lambda x, z, rx, ry: None

        # Structure icon images (built lazily; needs a live Tk root).
        self._icons: dict = {}
        self._icons_grey: dict = {}

        self._drag_start = None
        self._last_drag = None
        self._dragged = False
        self._flash = None       # (x, z) world point to highlight after a search
        self._hover_busy = False
        self._last_mouse = None

        c = self.canvas
        c.bind("<ButtonPress-1>", self._on_press)
        c.bind("<B1-Motion>", self._on_drag)
        c.bind("<ButtonRelease-1>", self._on_release)
        c.bind("<Double-Button-1>", self._on_double)
        c.bind("<Motion>", self._on_motion)
        c.bind("<MouseWheel>", self._on_wheel)
        c.bind("<Button-4>", lambda e: self._zoom_at(e.x, e.y, 1.2))
        c.bind("<Button-5>", lambda e: self._zoom_at(e.x, e.y, 1 / 1.2))
        c.bind("<Button-3>", self._on_right_click)
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

    def set_dimension(self, dimension: str) -> None:
        self.dimension = dimension
        self._clear_callout()
        self.redraw()

    def _visible_waypoints(self):
        return [w for w in self.waypoints if w.dimension == self.dimension]

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
    def flash_at(self, x, z):
        self._flash = (x, z)
        self.redraw()

    def _on_press(self, event):
        self._drag_start = (event.x, event.y, self.center_x, self.center_z)
        self._last_drag = (event.x, event.y)
        self._dragged = False
        self._clear_callout()
        if self._flash is not None:
            self._flash = None
            self.redraw()

    def _on_drag(self, event):
        if not self._drag_start:
            return
        px, py, _, _ = self._drag_start
        lx, ly = self._last_drag
        dx, dy = event.x - lx, event.y - ly
        self._last_drag = (event.x, event.y)
        if abs(event.x - px) > 3 or abs(event.y - py) > 3:
            self._dragged = True
        if dx or dy:
            # Shift the world under the cursor and slide every existing canvas
            # item by the same pixels - far cheaper than a full redraw per event.
            self.center_x -= dx / self.scale
            self.center_z -= dy / self.scale
            self.canvas.move("all", dx, dy)

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
            wp = next((w for w in self.waypoints if w.id == hit), None)
            if wp is not None:
                self._show_callout(wp)
            return
        marker = self._struct_hit_test(event.x, event.y)
        if marker:
            self.on_structure_click(marker, event.x_root, event.y_root)
            return
        self.selected_id = None
        self.on_select(None)
        self.redraw()

    def _on_right_click(self, event):
        self._clear_callout()
        x, z = self.screen_to_world(event.x, event.y)
        self.on_context(round(x), round(z), event.x_root, event.y_root)

    def _on_double(self, event):
        hit = self._hit_test(event.x, event.y)
        if hit:
            self.selected_id = hit
            self.on_edit(hit)

    def _on_motion(self, event):
        # Throttle the (relatively expensive) coordinate/biome/structure hover
        # work to at most ~20x/sec so moving the mouse stays smooth.
        self._last_mouse = (event.x, event.y)
        if not self._hover_busy:
            self._hover_busy = True
            self.after(50, self._hover_tick)

    def _hover_tick(self):
        self._hover_busy = False
        if self._last_mouse is None:
            return
        mx, my = self._last_mouse
        x, z = self.screen_to_world(mx, my)
        self.on_coords(x, z)
        s = self._struct_hit_test(mx, my)
        self.on_hover(f"{s['label']}  ({s['x']}, {s['z']})" if s else None)

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
        for wp in self._visible_waypoints():
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

    def _biome_covers_view(self) -> bool:
        """True if the current render still covers the viewport at this zoom, so
        we can skip regenerating (just reposition) - key to smooth movement."""
        bg = self._bg
        if not bg or abs(self.scale - bg["scale"]) > 1e-9:
            return False
        x0, z0, x1, z1 = self.view_bounds()
        return (bg["bx0"] <= x0 and bg["bz0"] <= z0
                and bg["bx1"] >= x1 and bg["bz1"] >= z1)

    def _render_biome(self):
        if not (self._biome_enabled and self._biome_provider):
            self._bg = None
            return
        covers = self._biome_covers_view()
        if covers and self._bg and self._bg.get("full"):
            return                             # already sharp and covering
        if not covers:
            self._do_render(fast=True)         # instant coarse pass, no hitch
        self._schedule_sharpen()

    def _do_render(self, fast: bool):
        w, h = self._size()
        wv, hv = w / self.scale, h / self.scale
        ex0 = self.center_x - wv * (0.5 + BIOME_MARGIN)
        ez0 = self.center_z - hv * (0.5 + BIOME_MARGIN)
        ex1 = self.center_x + wv * (0.5 + BIOME_MARGIN)
        ez1 = self.center_z + hv * (0.5 + BIOME_MARGIN)
        pw = max(2, int(w * (1 + 2 * BIOME_MARGIN)))
        ph = max(2, int(h * (1 + 2 * BIOME_MARGIN)))
        max_cols = 96 if fast else 256
        try:
            pil = self._biome_provider.render(ex0, ez0, ex1, ez1, pw, ph, max_cols)
        except Exception:  # noqa: BLE001
            pil = None
        if pil is None:
            self._bg = None
            return
        self._bg = {
            "pil": pil,
            "photo": ImageTk.PhotoImage(pil),
            "bx0": ex0, "bz0": ez0, "bx1": ex1, "bz1": ez1,
            "scale": self.scale, "full": not fast,
        }

    def _schedule_sharpen(self):
        if self._sharpen_job is not None:
            self.after_cancel(self._sharpen_job)
        self._sharpen_job = self.after(260, self._sharpen)

    def _sharpen(self):
        # Once the view has been still for a moment, replace the coarse pass
        # with a full-resolution render (the app was responsive meanwhile).
        self._sharpen_job = None
        if not (self._biome_enabled and self._biome_provider and self._bg):
            return
        if self._bg.get("full") or not self._biome_covers_view():
            return
        self._do_render(fast=False)
        self.redraw()

    # ------------------------------------------------------------------ #
    # Drawing
    # ------------------------------------------------------------------ #
    def redraw(self):
        c = self.canvas
        self._clear_callout()
        c.delete("all")
        w, h = self._size()
        self._draw_biome(w, h)
        self._draw_grid(w, h)
        self._draw_structures()
        self._draw_waypoints()
        self._draw_flash()

    # ------------------------------------------------------------------ #
    # Waypoint callout (interactive popup)
    # ------------------------------------------------------------------ #
    def _clear_callout(self):
        if not self._callout:
            return
        win, frame, ptr = self._callout
        for item in (win, ptr):
            try:
                self.canvas.delete(item)
            except tk.TclError:
                pass
        try:
            frame.destroy()
        except tk.TclError:
            pass
        self._callout = None

    def _show_callout(self, wp):
        self._clear_callout()
        sx, sy = self.world_to_screen(wp.x, wp.z)
        frame = ttk.Frame(self.canvas, relief="solid", borderwidth=1, padding=(8, 6))
        ttk.Label(frame, text=wp.name, font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w")
        coord = f"X {wp.x}     Z {wp.z}"
        if wp.y is not None:
            coord += f"     Y {wp.y}"
        ttk.Label(frame, text=coord, font=("Segoe UI", 9)).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(0, 4))
        nextrow = 2
        if wp.category:
            ttk.Label(frame, text=wp.category, font=("Segoe UI", 8),
                      foreground="#3a6ea5").grid(row=2, column=0, columnspan=3, sticky="w")
            nextrow = 3
        ttk.Button(frame, text="Edit", width=6,
                   command=lambda: (self._clear_callout(), self.on_edit(wp.id))
                   ).grid(row=nextrow, column=0, padx=1, pady=(4, 0))
        ttk.Button(frame, text="Delete", width=7,
                   command=lambda: (self._clear_callout(), self.on_delete(wp.id))
                   ).grid(row=nextrow, column=1, padx=1, pady=(4, 0))
        ttk.Button(frame, text="✕", width=2, command=self._clear_callout
                   ).grid(row=nextrow, column=2, padx=1, pady=(4, 0))
        # Pointer from the waypoint up to the box, then the box itself.
        ptr = self.canvas.create_line(sx, sy, sx + 16, sy - 16,
                                      fill=SELECT_COLOR, width=2)
        win = self.canvas.create_window(sx + 16, sy - 16, window=frame, anchor="sw")
        self._callout = (win, frame, ptr)

    def _draw_flash(self):
        if self._flash is None:
            return
        sx, sy = self.world_to_screen(*self._flash)
        for r in (18, 12, 6):
            self.canvas.create_oval(sx - r, sy - r, sx + r, sy + r,
                                    outline=SELECT_COLOR, width=2)

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
        # Draw a bit beyond the viewport so a drag reveals pre-drawn lines.
        padx, padz = (x1 - x0) * 0.5, (z1 - z0) * 0.5
        x0, x1, z0, z1 = x0 - padx, x1 + padx, z0 - padz, z1 + padz

        gx = int(x0 // step) * step
        while gx <= x1:
            sx, _ = self.world_to_screen(gx, 0)
            major = (gx % (step * 5) == 0)
            c.create_line(sx, -padz, sx, h + padz,
                          fill=GRID_MAJOR_COLOR if major else GRID_COLOR)
            if major:
                c.create_text(sx + 2, 2, anchor="nw", text=str(gx),
                              fill=TEXT_COLOR, font=("Segoe UI", 7))
            gx += step

        gz = int(z0 // step) * step
        while gz <= z1:
            _, sy = self.world_to_screen(0, gz)
            major = (gz % (step * 5) == 0)
            c.create_line(-padx, sy, w + padx, sy,
                          fill=GRID_MAJOR_COLOR if major else GRID_COLOR)
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
        normal, grey, _disabled = icons.build_icons()
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
                fill = "#8ea0ae" if s.get("explored") else "#e6f0f8"
                c.create_text(sx + 14, sy + 1, anchor="w", text=s["label"],
                              fill="#0b1119", font=("Segoe UI", 9, "bold"))
                c.create_text(sx + 13, sy, anchor="w", text=s["label"],
                              fill=fill, font=("Segoe UI", 9, "bold"))

    def _draw_waypoints(self):
        c = self.canvas
        for wp in self._visible_waypoints():
            sx, sy = self.world_to_screen(wp.x, wp.z)
            selected = (wp.id == self.selected_id)
            r = 6 if selected else 5
            outline = SELECT_COLOR if selected else "#0e1621"
            width = 3 if selected else 1
            c.create_oval(sx - r, sy - r, sx + r, sy + r,
                          fill=wp.color, outline=outline, width=width)
            c.create_text(sx + r + 3, sy, anchor="w", text=wp.name,
                          fill="#e8eef5", font=("Segoe UI", 9, "bold"))
            c.create_text(sx + r + 3, sy + 12, anchor="w", text=f"({wp.x}, {wp.z})",
                          fill=TEXT_COLOR, font=("Segoe UI", 8))
