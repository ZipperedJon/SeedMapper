"""The SeedMapper desktop application (Tkinter)."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

from PIL import ImageTk

from . import __app_name__, __version__, biomes, engine, exporters, icons, msf
from .colors import biome_name
from .mapcanvas import MapCanvas
from .model import DIMENSIONS, Project, Waypoint

MSF_FILETYPES = [("Minecraft Seed Map", "*.msf"), ("All files", "*.*")]


class WaypointDialog(tk.Toplevel):
    """Modal dialog to create or edit a single waypoint."""

    def __init__(self, master, waypoint: Waypoint, title: str):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.transient(master)
        self.result: Waypoint | None = None
        self._wp = waypoint

        self._name = tk.StringVar(value=waypoint.name)
        self._x = tk.StringVar(value=str(waypoint.x))
        self._z = tk.StringVar(value=str(waypoint.z))
        self._y = tk.StringVar(value="" if waypoint.y is None else str(waypoint.y))
        self._dimension = tk.StringVar(value=waypoint.dimension)
        self._category = tk.StringVar(value=waypoint.category)
        self._color = tk.StringVar(value=waypoint.color)

        pad = {"padx": 6, "pady": 4}
        frm = ttk.Frame(self, padding=12)
        frm.grid(sticky="nsew")

        row = 0
        ttk.Label(frm, text="Name").grid(row=row, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self._name, width=28).grid(
            row=row, column=1, columnspan=3, sticky="we", **pad)

        row += 1
        ttk.Label(frm, text="X").grid(row=row, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self._x, width=10).grid(row=row, column=1, sticky="w", **pad)
        ttk.Label(frm, text="Z").grid(row=row, column=2, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self._z, width=10).grid(row=row, column=3, sticky="w", **pad)

        row += 1
        ttk.Label(frm, text="Y (optional)").grid(row=row, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self._y, width=10).grid(row=row, column=1, sticky="w", **pad)
        ttk.Label(frm, text="Dimension").grid(row=row, column=2, sticky="w", **pad)
        ttk.Combobox(frm, textvariable=self._dimension, values=list(DIMENSIONS),
                     width=10, state="readonly").grid(row=row, column=3, sticky="w", **pad)

        row += 1
        ttk.Label(frm, text="Category").grid(row=row, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self._category, width=28).grid(
            row=row, column=1, columnspan=3, sticky="we", **pad)

        row += 1
        ttk.Label(frm, text="Colour").grid(row=row, column=0, sticky="w", **pad)
        self._swatch = tk.Label(frm, width=4, background=self._color.get(), relief="sunken")
        self._swatch.grid(row=row, column=1, sticky="w", **pad)
        ttk.Button(frm, text="Pick colour...", command=self._pick_color).grid(
            row=row, column=2, columnspan=2, sticky="w", **pad)

        row += 1
        ttk.Label(frm, text="Notes").grid(row=row, column=0, sticky="nw", **pad)
        self._notes = tk.Text(frm, width=30, height=4, wrap="word")
        self._notes.insert("1.0", waypoint.notes)
        self._notes.grid(row=row, column=1, columnspan=3, sticky="we", **pad)

        row += 1
        btns = ttk.Frame(frm)
        btns.grid(row=row, column=0, columnspan=4, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="Cancel", command=self._cancel).pack(side="right", padx=4)
        ttk.Button(btns, text="OK", command=self._ok).pack(side="right", padx=4)

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self._cancel())
        self.grab_set()
        self.wait_window(self)

    def _pick_color(self):
        _, hexval = colorchooser.askcolor(color=self._color.get(), parent=self)
        if hexval:
            self._color.set(hexval)
            self._swatch.config(background=hexval)

    def _ok(self):
        try:
            x = int(float(self._x.get()))
            z = int(float(self._z.get()))
        except ValueError:
            messagebox.showerror("Invalid coordinates",
                                 "X and Z must be whole numbers.", parent=self)
            return
        y_raw = self._y.get().strip()
        try:
            y = int(float(y_raw)) if y_raw else None
        except ValueError:
            messagebox.showerror("Invalid Y", "Y must be a whole number or blank.", parent=self)
            return

        self._wp.name = self._name.get().strip() or "Waypoint"
        self._wp.x, self._wp.z, self._wp.y = x, z, y
        self._wp.dimension = self._dimension.get()
        self._wp.category = self._category.get().strip()
        self._wp.color = self._color.get()
        self._wp.notes = self._notes.get("1.0", "end").strip()
        self.result = self._wp
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.geometry("1180x760")
        self.minsize(860, 560)

        self.project = Project()
        self.current_path: Path | None = None
        self.dirty = False
        self._engine_available = engine.available()

        self._coord_var = tk.StringVar(value="X: -, Z: -")
        self._status_var = tk.StringVar(value="Ready")
        self._seed_var = tk.StringVar(value=self.project.seed)
        self._version_var = tk.StringVar(value=self.project.mc_version)
        self._biome_var = tk.BooleanVar(value=True)
        self._terrain_var = tk.BooleanVar(value=False)
        self._depth_var = tk.StringVar(value=biomes.DEFAULT_DEPTH)
        self._add_var = tk.BooleanVar(value=False)
        self._structures_var = tk.BooleanVar(value=True)
        self._struct_enabled = {
            s["key"]: tk.BooleanVar(value=s["on"]) for s in engine.STRUCTURES}

        self._build_menu()
        self._build_toolbar()
        self._build_body()
        self._build_statusbar()

        self._refresh_engine_controls()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._refresh_all()
        self._update_title()

        # Turn the biome layer on by default when the engine is available.
        if self._engine_available and self._biome_var.get():
            self._toggle_biomes()
        self._note_version()

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #
    def _build_menu(self):
        menubar = tk.Menu(self)

        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="New", accelerator="Ctrl+N", command=self.new_project)
        filemenu.add_command(label="Open...", accelerator="Ctrl+O", command=self.open_project)
        filemenu.add_command(label="Save", accelerator="Ctrl+S", command=self.save_project)
        filemenu.add_command(label="Save As...", command=self.save_project_as)
        filemenu.add_separator()
        filemenu.add_command(label="Export to CSV...", command=self.export_csv)
        filemenu.add_command(label="Export to Markdown note...", command=self.export_markdown)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=filemenu)

        viewmenu = tk.Menu(menubar, tearoff=0)
        viewmenu.add_checkbutton(label="Show biome layer", variable=self._biome_var,
                                 command=self._toggle_biomes)
        viewmenu.add_checkbutton(label="Terrain shading", variable=self._terrain_var,
                                 command=self._toggle_terrain)
        viewmenu.add_checkbutton(label="Show structures", variable=self._structures_var,
                                 command=self._toggle_structures)
        viewmenu.add_separator()
        viewmenu.add_command(label="Reset view (home)", accelerator="Ctrl+H",
                             command=lambda: self.map.go_home())
        viewmenu.add_command(label="Go to spawn", command=self._goto_spawn)
        menubar.add_cascade(label="View", menu=viewmenu)

        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="About", command=self._about)
        menubar.add_cascade(label="Help", menu=helpmenu)

        self.config(menu=menubar)
        self.bind("<Control-n>", lambda e: self.new_project())
        self.bind("<Control-o>", lambda e: self.open_project())
        self.bind("<Control-s>", lambda e: self.save_project())
        self.bind("<Control-h>", lambda e: self.map.go_home())

    def _build_toolbar(self):
        bar = ttk.Frame(self, padding=(8, 6))
        bar.pack(side="top", fill="x")

        ttk.Label(bar, text="Seed:").pack(side="left")
        seed_entry = ttk.Entry(bar, textvariable=self._seed_var, width=20)
        seed_entry.pack(side="left", padx=(4, 12))
        seed_entry.bind("<FocusOut>", lambda e: self._apply_seed_version())
        seed_entry.bind("<Return>", lambda e: self._apply_seed_version())

        ttk.Label(bar, text="Version:").pack(side="left")
        self._version_combo = ttk.Combobox(
            bar, textvariable=self._version_var, values=engine.VERSION_LABELS,
            width=15, state="readonly")
        self._version_combo.pack(side="left", padx=(4, 12))
        self._version_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_seed_version())

        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=8)

        self._add_btn = ttk.Checkbutton(
            bar, text="Add waypoint (click map)", variable=self._add_var,
            style="Toolbutton", command=self._toggle_add_mode)
        self._add_btn.pack(side="left", padx=4)
        self._biome_chk = ttk.Checkbutton(
            bar, text="Biomes", variable=self._biome_var,
            style="Toolbutton", command=self._toggle_biomes)
        self._biome_chk.pack(side="left", padx=4)
        self._terrain_chk = ttk.Checkbutton(
            bar, text="Terrain", variable=self._terrain_var,
            style="Toolbutton", command=self._toggle_terrain)
        self._terrain_chk.pack(side="left", padx=4)

        ttk.Label(bar, text="Depth:").pack(side="left", padx=(8, 2))
        self._depth_combo = ttk.Combobox(
            bar, textvariable=self._depth_var, values=biomes.DEPTH_LABELS,
            width=16, state="readonly")
        self._depth_combo.pack(side="left", padx=(0, 8))
        self._depth_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_depth())

        ttk.Button(bar, text="Spawn", command=self._goto_spawn).pack(side="left", padx=4)
        ttk.Button(bar, text="Home", command=lambda: self.map.go_home()).pack(side="left", padx=4)

    def _build_body(self):
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(side="top", fill="both", expand=True)

        left = ttk.Frame(paned, padding=(6, 6))
        paned.add(left, weight=0)

        ttk.Label(left, text="Waypoints", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        cols = ("name", "x", "z", "dim")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", height=14,
                                 selectmode="browse")
        for c, t, w, anc in (("name", "Name", 130, "w"), ("x", "X", 54, "e"),
                             ("z", "Z", 54, "e"), ("dim", "Dim", 66, "w")):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor=anc)
        self.tree.pack(fill="both", expand=True, pady=(4, 6))
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", lambda e: self._edit_selected())

        btns = ttk.Frame(left)
        btns.pack(fill="x")
        ttk.Button(btns, text="Add", command=self._add_waypoint_dialog).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(btns, text="Edit", command=self._edit_selected).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(btns, text="Delete", command=self._delete_selected).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(left, text="Go to on map", command=self._goto_selected).pack(fill="x", pady=(6, 0))

        self._build_legend(left)

        self.map = MapCanvas(paned)
        paned.add(self.map, weight=1)
        self.map.on_coords = self._on_map_coords
        self.map.on_place = self._on_map_place
        self.map.on_select = self._on_map_select
        self.map.on_edit = self._on_map_edit
        self.map.on_view_changed = self._on_view_changed
        self.map.on_hover = self._on_hover
        self.map.on_structure_click = self._on_structure_click

    def _build_legend(self, parent):
        lf = ttk.LabelFrame(parent, text="Structures", padding=(6, 4))
        lf.pack(fill="x", pady=(10, 0))

        top = ttk.Frame(lf)
        top.pack(fill="x", pady=(0, 4))
        ttk.Checkbutton(top, text="Show", variable=self._structures_var,
                        command=self._toggle_structures).pack(side="left")
        ttk.Button(top, text="All", width=4,
                   command=lambda: self._set_all_structures(True)).pack(side="right", padx=1)
        ttk.Button(top, text="None", width=5,
                   command=lambda: self._set_all_structures(False)).pack(side="right", padx=1)
        ttk.Label(lf, text="Click an icon to toggle it",
                  font=("Segoe UI", 7), foreground="#7f909e").pack(anchor="w")

        # Clickable icon toggles.
        self._icon_on = {}      # key -> PhotoImage (enabled)
        self._icon_off = {}     # key -> PhotoImage (disabled/red strike)
        self._struct_cells = {}  # key -> (label_widget, text_widget)
        normal, _explored, disabled = icons.build_icons()
        grid = ttk.Frame(lf)
        grid.pack(fill="x")
        for i, s in enumerate(engine.STRUCTURES):
            key = s["key"]
            self._icon_on[key] = ImageTk.PhotoImage(normal[key])
            self._icon_off[key] = ImageTk.PhotoImage(disabled[key])
            row, col = divmod(i, 2)
            cell = ttk.Frame(grid)
            cell.grid(row=row, column=col, sticky="w", padx=2, pady=1)
            iconlbl = tk.Label(cell, cursor="hand2")
            iconlbl.pack(side="left")
            txtlbl = tk.Label(cell, text=s["label"], font=("Segoe UI", 8), cursor="hand2")
            txtlbl.pack(side="left", padx=(3, 8))
            iconlbl.bind("<Button-1>", lambda e, k=key: self._toggle_one_structure(k))
            txtlbl.bind("<Button-1>", lambda e, k=key: self._toggle_one_structure(k))
            self._struct_cells[key] = (iconlbl, txtlbl)
            self._update_struct_cell(key)

    def _update_struct_cell(self, key):
        on = self._struct_enabled[key].get()
        iconlbl, txtlbl = self._struct_cells[key]
        iconlbl.config(image=self._icon_on[key] if on else self._icon_off[key])
        txtlbl.config(foreground="#1a1a1a" if on else "#9aa6b0",
                      font=("Segoe UI", 8, "" if on else "overstrike"))

    def _toggle_one_structure(self, key):
        self._struct_enabled[key].set(not self._struct_enabled[key].get())
        self._update_struct_cell(key)
        if not self._structures_var.get():
            self._structures_var.set(True)
        self._refresh_structures()

    def _set_all_structures(self, on):
        for s in engine.STRUCTURES:
            self._struct_enabled[s["key"]].set(on)
            self._update_struct_cell(s["key"])
        self._refresh_structures()

    def _build_statusbar(self):
        bar = ttk.Frame(self, relief="sunken")
        bar.pack(side="bottom", fill="x")
        ttk.Label(bar, textvariable=self._coord_var, anchor="w", width=44,
                  font=("Segoe UI", 11)).pack(side="left", padx=8)
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", pady=2)
        ttk.Label(bar, textvariable=self._status_var, anchor="w",
                  font=("Segoe UI", 11)).pack(side="left", padx=8)

    # ------------------------------------------------------------------ #
    # Engine-dependent controls
    # ------------------------------------------------------------------ #
    def _refresh_engine_controls(self):
        state = "normal" if self._engine_available else "disabled"
        self._biome_chk.config(state=state)
        self._terrain_chk.config(state=state)
        self._depth_combo.config(state="readonly" if self._engine_available else "disabled")
        if not self._engine_available:
            self._biome_var.set(False)
            self._terrain_var.set(False)
            self._structures_var.set(False)
            self._status_var.set(
                "World-gen engine unavailable - running as grid + waypoint mapper. "
                f"({engine.load_error()})")

    def _make_provider(self):
        p = biomes.get_provider(self.project.seed, self.project.mc_version)
        if p is not None:
            p.depth = self._depth_var.get()
            p.terrain = self._terrain_var.get()
        return p

    def _apply_biome_layer(self):
        if not self._engine_available:
            return
        self.map.set_biome_provider(self._make_provider())
        self.map.set_biome_enabled(self._biome_var.get())

    def _toggle_biomes(self):
        if not self._engine_available:
            self._biome_var.set(False)
            return
        self._apply_biome_layer()

    def _toggle_terrain(self):
        if not self._engine_available:
            self._terrain_var.set(False)
            return
        if self._terrain_var.get() and not self._biome_var.get():
            self._biome_var.set(True)   # terrain shades the biome layer
        self._apply_biome_layer()

    def _apply_depth(self):
        if self._engine_available and self._biome_var.get():
            self._apply_biome_layer()

    def _toggle_structures(self):
        if not self._engine_available:
            self._structures_var.set(False)
            return
        self._refresh_structures()

    def _toggle_add_mode(self):
        self.map.set_add_mode(self._add_var.get())
        self._status_var.set("Add mode: click the map to drop a waypoint."
                             if self._add_var.get() else "Ready")

    def _apply_seed_version(self):
        seed = self._seed_var.get().strip()
        version = engine.normalize_version(self._version_var.get())
        self._version_var.set(version)
        changed = (seed != self.project.seed or version != self.project.mc_version)
        if not changed:
            return
        self.project.seed = seed
        self.project.mc_version = version
        self._mark_dirty()
        self._apply_biome_layer()
        self._refresh_structures()
        self._note_version()

    def _note_version(self):
        if self._engine_available and engine.is_approximate(self.project.mc_version):
            self._status_var.set(
                f"Note: {self.project.mc_version} isn't modeled yet - showing "
                "1.21.4 generation (biomes and almost all structures match).")

    def _on_view_changed(self):
        self._refresh_structures()

    def _refresh_structures(self):
        if not (self._engine_available and self._structures_var.get()):
            self.map.set_structures([])
            return
        x0, z0, x1, z1 = self.map.view_bounds()
        markers, too_broad = [], False
        for sdef in engine.STRUCTURES:
            if not self._struct_enabled[sdef["key"]].get():
                continue
            res = engine.find_structures(
                sdef["type"], self.project.mc_version, self.project.seed,
                sdef["dim"], int(x0), int(z0), int(x1), int(z1))
            if res == engine.TOO_BROAD:
                too_broad = True
                continue
            for (x, z) in (res or []):
                sid = f"{sdef['key']}:{x}:{z}"
                markers.append({"x": x, "z": z, "key": sdef["key"],
                                "color": sdef["color"], "label": sdef["label"],
                                "id": sid, "explored": sid in self.project.explored})
        self.map.set_structures(markers)
        if too_broad:
            self._status_var.set("Zoom in to load structures (area too large).")
        elif markers:
            self._status_var.set(f"{len(markers)} structures in view.")

    def _on_structure_click(self, marker, root_x, root_y):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label=f"{marker['label']}  ({marker['x']}, {marker['z']})",
                         state="disabled")
        menu.add_separator()
        menu.add_command(label="Add as waypoint",
                         command=lambda: self._structure_to_waypoint(marker))
        explored = marker["id"] in self.project.explored
        menu.add_command(
            label="Unmark explored" if explored else "Mark as explored",
            command=lambda: self._toggle_explored(marker))
        menu.tk_popup(root_x, root_y)

    def _structure_to_waypoint(self, marker):
        wp = Waypoint(name=marker["label"], x=marker["x"], z=marker["z"],
                      category="Structure", color=marker["color"])
        dlg = WaypointDialog(self, wp, "Add structure as waypoint")
        if dlg.result:
            self.project.add(dlg.result)
            self._mark_dirty()
            self._refresh_all()
            self.map.set_selected(dlg.result.id)

    def _toggle_explored(self, marker):
        sid = marker["id"]
        if sid in self.project.explored:
            self.project.explored.discard(sid)
        else:
            self.project.explored.add(sid)
        self._mark_dirty()
        self._refresh_structures()

    def _goto_spawn(self):
        if not self._engine_available:
            return
        pos = engine.get_spawn(self.project.mc_version, self.project.seed)
        if pos:
            self.map.center_on(pos[0], pos[1])
            self._status_var.set(f"Spawn at ({pos[0]}, {pos[1]})")

    # ------------------------------------------------------------------ #
    # Map callbacks
    # ------------------------------------------------------------------ #
    def _on_map_coords(self, x, z):
        xi, zi = int(round(x)), int(round(z))
        text = f"X: {xi}, Z: {zi}"
        if self._engine_available:
            bid = engine.biome_at(self.project.mc_version, self.project.seed,
                                  "overworld", xi, zi)
            if bid is not None:
                text += f"   |   {biome_name(bid)}"
        self._coord_var.set(text)

    def _on_hover(self, text):
        if text:
            self._status_var.set(text)

    def _on_map_place(self, x, z):
        wp = Waypoint(name="Waypoint", x=x, z=z)
        dlg = WaypointDialog(self, wp, "New waypoint")
        if dlg.result:
            self.project.add(dlg.result)
            self._mark_dirty()
            self._refresh_all()
            self.map.set_selected(dlg.result.id)
        self._add_var.set(False)
        self._toggle_add_mode()

    def _on_map_select(self, wp_id):
        self._select_in_tree(wp_id)

    def _on_map_edit(self, wp_id):
        self._edit_waypoint(wp_id)

    # ------------------------------------------------------------------ #
    # Waypoint list actions
    # ------------------------------------------------------------------ #
    def _add_waypoint_dialog(self):
        wp = Waypoint(name="Waypoint", x=int(round(self.map.center_x)),
                      z=int(round(self.map.center_z)))
        dlg = WaypointDialog(self, wp, "New waypoint")
        if dlg.result:
            self.project.add(dlg.result)
            self._mark_dirty()
            self._refresh_all()
            self.map.set_selected(dlg.result.id)

    def _selected_id(self):
        sel = self.tree.selection()
        return sel[0] if sel else None

    def _edit_selected(self):
        wp_id = self._selected_id()
        if wp_id:
            self._edit_waypoint(wp_id)

    def _edit_waypoint(self, wp_id):
        wp = self.project.get(wp_id)
        if not wp:
            return
        dlg = WaypointDialog(self, wp, "Edit waypoint")
        if dlg.result:
            self._mark_dirty()
            self._refresh_all()
            self.map.set_selected(wp_id)

    def _delete_selected(self):
        wp_id = self._selected_id()
        if not wp_id:
            return
        wp = self.project.get(wp_id)
        if wp and messagebox.askyesno("Delete waypoint", f"Delete '{wp.name}'?"):
            self.project.remove(wp_id)
            self._mark_dirty()
            self._refresh_all()

    def _goto_selected(self):
        wp_id = self._selected_id()
        wp = self.project.get(wp_id) if wp_id else None
        if wp:
            self.map.center_on(wp.x, wp.z)
            self.map.set_selected(wp.id)

    def _on_tree_select(self, event):
        wp_id = self._selected_id()
        if wp_id:
            self.map.set_selected(wp_id)

    def _select_in_tree(self, wp_id):
        if wp_id and self.tree.exists(wp_id):
            self.tree.selection_set(wp_id)
            self.tree.see(wp_id)
        elif not wp_id:
            self.tree.selection_remove(self.tree.selection())

    # ------------------------------------------------------------------ #
    # File actions
    # ------------------------------------------------------------------ #
    def new_project(self):
        if not self._confirm_discard():
            return
        self.project = Project()
        self.current_path = None
        self.dirty = False
        self._seed_var.set(self.project.seed)
        self._version_var.set(self.project.mc_version)
        self._refresh_all()
        self._update_title()
        self._status_var.set("New map created.")

    def open_project(self):
        if not self._confirm_discard():
            return
        path = filedialog.askopenfilename(title="Open map", filetypes=MSF_FILETYPES)
        if not path:
            return
        try:
            self.project = msf.load(path)
        except msf.MsfError as exc:
            messagebox.showerror("Cannot open file", str(exc))
            return
        self.project.mc_version = engine.normalize_version(self.project.mc_version)
        self.current_path = Path(path)
        self.dirty = False
        self._seed_var.set(self.project.seed)
        self._version_var.set(self.project.mc_version)
        self._refresh_all()
        if self._biome_var.get():
            self._toggle_biomes()
        self._refresh_structures()
        self._update_title()
        self._status_var.set(f"Opened {self.current_path.name}")

    def save_project(self):
        if self.current_path is None:
            return self.save_project_as()
        return self._write_to(self.current_path)

    def save_project_as(self):
        path = filedialog.asksaveasfilename(
            title="Save map", defaultextension=".msf", filetypes=MSF_FILETYPES,
            initialfile=(self.project.name or "map") + ".msf")
        if not path:
            return False
        return self._write_to(Path(path))

    def _write_to(self, path: Path):
        self.project.name = path.stem
        try:
            saved = msf.save(self.project, path)
        except OSError as exc:
            messagebox.showerror("Cannot save", str(exc))
            return False
        self.current_path = saved
        self.dirty = False
        self._update_title()
        self._status_var.set(f"Saved {saved.name}")
        return True

    def export_csv(self):
        if not self._has_waypoints():
            return
        path = filedialog.asksaveasfilename(
            title="Export CSV", defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile=(self.project.name or "waypoints") + ".csv")
        if not path:
            return
        out = exporters.export_csv(self.project, path)
        self._status_var.set(f"Exported {len(self.project.waypoints)} waypoints to {out.name}")

    def export_markdown(self):
        if not self._has_waypoints():
            return
        path = filedialog.asksaveasfilename(
            title="Export Markdown note", defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("Text", "*.txt")],
            initialfile=(self.project.name or "waypoints") + ".md")
        if not path:
            return
        out = exporters.export_markdown(self.project, path)
        self._status_var.set(f"Exported note to {out.name}")

    def _has_waypoints(self):
        if not self.project.waypoints:
            messagebox.showinfo("Nothing to export", "There are no waypoints yet.")
            return False
        return True

    # ------------------------------------------------------------------ #
    # Shared helpers
    # ------------------------------------------------------------------ #
    def _refresh_all(self):
        self.tree.delete(*self.tree.get_children())
        for w in self.project.waypoints:
            self.tree.insert("", "end", iid=w.id, values=(w.name, w.x, w.z, w.dimension))
        self.map.set_waypoints(self.project.waypoints)

    def _mark_dirty(self):
        self.dirty = True
        self._update_title()

    def _update_title(self):
        name = self.current_path.name if self.current_path else "Untitled"
        self.title(f"{'*' if self.dirty else ''}{name} - {__app_name__}")

    def _confirm_discard(self):
        if not self.dirty:
            return True
        answer = messagebox.askyesnocancel(
            "Unsaved changes", "You have unsaved changes. Save before continuing?")
        if answer is None:
            return False
        if answer:
            return self.save_project()
        return True

    def _on_close(self):
        if self._confirm_discard():
            self.destroy()

    def _about(self):
        newest = "up to 1.21" if self._engine_available else "unavailable"
        messagebox.showinfo(
            "About " + __app_name__,
            f"{__app_name__} v{__version__}\n\n"
            "A Minecraft seed map with custom waypoints, biome rendering,\n"
            "and structure finding.\n\n"
            f"World-gen engine: cubiomes ({newest})\n"
            "Files are saved as .msf; export to CSV or Markdown.")


def run():
    App().mainloop()
