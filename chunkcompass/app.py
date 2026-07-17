"""The Chunk Compass desktop application (Tkinter)."""

from __future__ import annotations

import os
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

from PIL import ImageTk

from . import (__app_name__, __version__, biomes, colors, engine, exporters,
               icons, msf, updater)
from .colors import biome_name
from .mapcanvas import MapCanvas
from .model import DIMENSIONS, Project, Waypoint

MSF_FILETYPES = [("Minecraft Seed Map", "*.msf"), ("All files", "*.*")]

DIMENSION_CHOICES = ["Overworld", "Nether", "End"]
DIMENSION_KEY = {"Overworld": "overworld", "Nether": "nether", "End": "end"}


class WaypointDialog(tk.Toplevel):
    """Modal dialog to create or edit a single waypoint."""

    def __init__(self, master, waypoint: Waypoint, title: str, categories=()):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.transient(master)
        self.withdraw()          # stay hidden until we've centred it
        self._cat_options = sorted({c for c in categories if c})
        self.result: Waypoint | None = None
        self._wp = waypoint

        self._name_var = tk.StringVar(value=waypoint.name)
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
        self._name_entry = ttk.Entry(frm, textvariable=self._name_var, width=28)
        self._name_entry.grid(row=row, column=1, columnspan=3, sticky="we", **pad)

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
        self._cat_combo = ttk.Combobox(frm, textvariable=self._category,
                                       values=self._cat_options, width=26)
        self._cat_combo.grid(row=row, column=1, columnspan=3, sticky="we", **pad)
        self._cat_combo.bind("<KeyRelease>", self._cat_autocomplete)

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

        self._center_on_parent(master)
        self.grab_set()
        self._name_entry.focus_set()
        self._name_entry.selection_range(0, "end")
        self.wait_window(self)

    def _center_on_parent(self, master):
        """Place the dialog in the middle of the main window so it's seen at once."""
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        try:
            px, py = master.winfo_rootx(), master.winfo_rooty()
            pw, ph = master.winfo_width(), master.winfo_height()
        except tk.TclError:
            pw = ph = 0
        if pw > 1 and ph > 1:
            x = px + (pw - w) // 2
            y = py + (ph - h) // 3        # a touch above centre reads better
        else:                              # fallback: centre on screen
            x = (self.winfo_screenwidth() - w) // 2
            y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
        self.deiconify()                   # now show it at the chosen spot
        self.lift()

    def _cat_autocomplete(self, event):
        if event.keysym in ("BackSpace", "Delete", "Left", "Right", "Up", "Down",
                            "Return", "Escape", "Tab"):
            return
        typed = self._category.get()
        if not typed:
            return
        for opt in self._cat_options:
            if opt.lower().startswith(typed.lower()) and len(opt) > len(typed):
                self._cat_combo.delete(0, "end")
                self._cat_combo.insert(0, opt)
                self._cat_combo.selection_range(len(typed), "end")
                self._cat_combo.icursor(len(typed))
                break

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

        self._wp.name = self._name_var.get().strip() or "Waypoint"
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
        self.geometry("1240x900")
        self.minsize(900, 620)

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
        self._dimension_var = tk.StringVar(value="Overworld")
        self._highlight_ids: set = set()
        self._search_hint = tk.StringVar(value="")
        self._struct_query = None            # cached structure-query coverage
        self._wp_search_var = tk.StringVar()
        self._wp_cat_var = tk.StringVar(value="All categories")
        self._struct_filter_var = tk.StringVar()
        self._biome_filter_var = tk.StringVar()

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
        helpmenu.add_command(label="Check for updates...", command=self._check_updates)
        helpmenu.add_separator()
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
            width=14, state="readonly")
        self._version_combo.pack(side="left", padx=(4, 10))
        self._version_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_seed_version())

        ttk.Label(bar, text="Dimension:").pack(side="left")
        self._dim_combo = ttk.Combobox(
            bar, textvariable=self._dimension_var, values=DIMENSION_CHOICES,
            width=10, state="readonly")
        self._dim_combo.pack(side="left", padx=(4, 10))
        self._dim_combo.bind("<<ComboboxSelected>>", lambda e: self._change_dimension())

        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)

        self._add_btn = ttk.Checkbutton(
            bar, text="Add waypoint (click map)", variable=self._add_var,
            style="Toolbutton", command=self._toggle_add_mode)
        self._add_btn.pack(side="left", padx=4)
        self._biome_chk = ttk.Checkbutton(
            bar, text="Biomes", variable=self._biome_var, command=self._toggle_biomes)
        self._biome_chk.pack(side="left", padx=4)
        self._terrain_chk = ttk.Checkbutton(
            bar, text="Terrain", variable=self._terrain_var, command=self._toggle_terrain)
        self._terrain_chk.pack(side="left", padx=4)

        ttk.Label(bar, text="Depth:").pack(side="left", padx=(8, 2))
        self._depth_combo = ttk.Combobox(
            bar, textvariable=self._depth_var, values=biomes.DEPTH_LABELS,
            width=15, state="readonly")
        self._depth_combo.pack(side="left", padx=(0, 8))
        self._depth_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_depth())

        ttk.Button(bar, text="Home", command=lambda: self.map.go_home()).pack(side="right", padx=4)
        ttk.Button(bar, text="Spawn", command=self._goto_spawn).pack(side="right", padx=4)

        # Second row: search.
        bar2 = ttk.Frame(self, padding=(8, 0, 8, 6))
        bar2.pack(side="top", fill="x")
        ttk.Label(bar2, text="Search structure or biome:").pack(side="left")
        self._search_var = tk.StringVar()
        entry = ttk.Entry(bar2, textvariable=self._search_var, width=28)
        entry.pack(side="left", padx=(4, 4))
        entry.bind("<Return>", lambda e: self._do_search())
        ttk.Button(bar2, text="Find nearest", command=self._do_search).pack(side="left")
        ttk.Label(bar2, textvariable=self._search_hint, foreground="#7f909e",
                  font=("Segoe UI", 8)).pack(side="left", padx=8)

    def _build_body(self):
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(side="top", fill="both", expand=True)

        left = ttk.Frame(paned, padding=(6, 6))
        paned.add(left, weight=0)

        ttk.Label(left, text="Waypoints", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        filt = ttk.Frame(left)
        filt.pack(fill="x", pady=(2, 2))
        ttk.Label(filt, text="Find:").pack(side="left")
        wpe = ttk.Entry(filt, textvariable=self._wp_search_var, width=10)
        wpe.pack(side="left", padx=(2, 4))
        wpe.bind("<KeyRelease>", lambda e: self._refresh_all())
        self._wp_cat_combo = ttk.Combobox(filt, textvariable=self._wp_cat_var,
                                          width=12, state="readonly")
        self._wp_cat_combo.pack(side="left")
        self._wp_cat_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_all())

        cols = ("name", "x", "z", "dim")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", height=6,
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
        self._build_highlight(left)

        self.map = MapCanvas(paned)
        paned.add(self.map, weight=1)
        self.map.on_coords = self._on_map_coords
        self.map.on_place = self._on_map_place
        self.map.on_select = self._on_map_select
        self.map.on_edit = self._on_map_edit
        self.map.on_view_changed = self._on_view_changed
        self.map.on_hover = self._on_hover
        self.map.on_structure_click = self._on_structure_click
        self.map.on_delete = self._delete_by_id
        self.map.on_context = self._on_map_context
        self.map.set_dimension(self._dim())

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
        fe = ttk.Entry(lf, textvariable=self._struct_filter_var)
        fe.pack(fill="x", pady=(0, 3))
        fe.bind("<KeyRelease>", lambda e: self._populate_structures())

        # Build icon images once (all structures); lay out only the ones for
        # the current dimension (and matching the filter).
        self._icon_on = {}      # key -> PhotoImage (enabled)
        self._icon_off = {}     # key -> PhotoImage (disabled/red strike)
        self._struct_cells = {}  # key -> (label_widget, text_widget)
        normal, _explored, disabled = icons.build_icons()
        for s in engine.STRUCTURES:
            self._icon_on[s["key"]] = ImageTk.PhotoImage(normal[s["key"]])
            self._icon_off[s["key"]] = ImageTk.PhotoImage(disabled[s["key"]])
        self._struct_grid = ttk.Frame(lf)
        self._struct_grid.pack(fill="x")
        self._populate_structures()

    def _populate_structures(self):
        for child in self._struct_grid.winfo_children():
            child.destroy()
        self._struct_cells = {}
        dim = self._dim()
        flt = self._struct_filter_var.get().strip().lower()
        items = [s for s in engine.STRUCTURES
                 if s["dim"] == dim and (not flt or flt in s["label"].lower())]
        for i, s in enumerate(items):
            key = s["key"]
            row, col = divmod(i, 3)          # 3 columns keeps the panel short
            cell = ttk.Frame(self._struct_grid)
            cell.grid(row=row, column=col, sticky="w", padx=2, pady=1)
            iconlbl = tk.Label(cell, cursor="hand2")
            iconlbl.pack(side="left")
            txtlbl = tk.Label(cell, text=s["label"], font=("Segoe UI", 8), cursor="hand2")
            txtlbl.pack(side="left", padx=(2, 4))
            iconlbl.bind("<Button-1>", lambda e, k=key: self._toggle_one_structure(k))
            txtlbl.bind("<Button-1>", lambda e, k=key: self._toggle_one_structure(k))
            self._struct_cells[key] = (iconlbl, txtlbl)
            self._update_struct_cell(key)

    def _build_highlight(self, parent):
        lf = ttk.LabelFrame(parent, text="Highlight biomes", padding=(6, 4))
        lf.pack(fill="both", expand=True, pady=(10, 0))
        row = ttk.Frame(lf)
        row.pack(fill="x")
        ttk.Label(row, text="select to highlight", font=("Segoe UI", 7),
                  foreground="#7f909e").pack(side="left")
        ttk.Button(row, text="Clear", width=6, command=self._clear_highlight).pack(side="right")
        bfe = ttk.Entry(lf, textvariable=self._biome_filter_var)
        bfe.pack(fill="x", pady=(2, 0))
        bfe.bind("<KeyRelease>", lambda e: self._populate_biome_list())
        box = ttk.Frame(lf)
        box.pack(fill="both", expand=True, pady=(3, 0))
        sb = ttk.Scrollbar(box, orient="vertical")
        self._biome_list = tk.Listbox(box, selectmode="extended", height=6,
                                      exportselection=False, activestyle="none",
                                      yscrollcommand=sb.set)
        sb.config(command=self._biome_list.yview)
        sb.pack(side="right", fill="y")
        self._biome_list.pack(side="left", fill="both", expand=True)
        self._biome_choice_ids = []
        self._biome_list.bind("<<ListboxSelect>>", lambda e: self._on_highlight_select())
        self._populate_biome_list()

    def _populate_biome_list(self):
        self._biome_list.delete(0, "end")
        self._biome_choice_ids = []
        flt = self._biome_filter_var.get().strip().lower()
        for name, bid in colors.biome_choices(self._dim()):
            if flt and flt not in name.lower():
                continue
            self._biome_list.insert("end", name)
            self._biome_choice_ids.append(bid)

    def _on_highlight_select(self):
        sel = self._biome_list.curselection()
        self._highlight_ids = {self._biome_choice_ids[i] for i in sel}
        if self._biome_var.get():
            self._apply_biome_layer()

    def _clear_highlight(self):
        self._biome_list.selection_clear(0, "end")
        self._highlight_ids = set()
        if self._biome_var.get():
            self._apply_biome_layer()

    # -- search -------------------------------------------------------- #
    def _do_search(self):
        if not self._engine_available:
            return
        q = self._search_var.get().strip()
        if not q:
            return
        ql = q.lower()

        # Priority: exact biome, exact structure, substring structure, substring biome.
        exact_biome = colors.biome_id_from_name(q)
        exact_struct = next((s for s in engine.STRUCTURES if s["label"].lower() == ql), None)
        if exact_biome is not None and exact_struct is None:
            return self._go_biome(exact_biome)
        if exact_struct is not None:
            return self._go_structure(exact_struct)
        sub_struct = next((s for s in engine.STRUCTURES if ql in s["label"].lower()), None)
        if sub_struct is not None:
            return self._go_structure(sub_struct)
        sub_biome = next(((n, b) for n, b in colors.BIOME_CHOICES if ql in n.lower()), None)
        if sub_biome is not None:
            return self._go_biome(sub_biome[1])
        self._search_hint.set("No matching structure or biome")

    def _go_structure(self, sdef):
        if sdef["dim"] != self._dim():
            label = next(k for k, v in DIMENSION_KEY.items() if v == sdef["dim"])
            self._dimension_var.set(label)
            self._change_dimension()
        cx, cz = int(round(self.map.center_x)), int(round(self.map.center_z))
        pos = self._nearest_structure(sdef, cx, cz)
        if pos:
            self.map.center_on(*pos)
            self.map.flash_at(*pos)
            self._search_hint.set(f"{sdef['label']}: {pos[0]}, {pos[1]}")
        else:
            self._search_hint.set(f"No {sdef['label']} found within range")

    def _go_biome(self, bid):
        cx, cz = int(round(self.map.center_x)), int(round(self.map.center_z))
        pos = engine.nearest_biome(self.project.mc_version, self.project.seed,
                                   self._dim(), cx, cz, bid,
                                   y=biomes.depth_y(self._depth_var.get()))
        if pos:
            self.map.center_on(*pos)
            self.map.flash_at(*pos)
            self._search_hint.set(f"{biome_name(bid)}: {pos[0]}, {pos[1]}")
        else:
            self._search_hint.set(f"No {biome_name(bid)} within range")

    def _nearest_structure(self, sdef, cx, cz):
        mc, seed = self.project.mc_version, self.project.seed
        finder = sdef.get("finder", "region")
        if finder == "stronghold":
            res = engine.find_strongholds(mc, seed, cx - 10_000_000, cz - 10_000_000,
                                          cx + 10_000_000, cz + 10_000_000)
            return self._closest(res, cx, cz)
        for r in (2000, 5000, 12000, 30000, 80000):
            x0, z0, x1, z1 = cx - r, cz - r, cx + r, cz + r
            if finder == "mineshaft":
                res = engine.find_mineshafts(mc, seed, x0, z0, x1, z1)
            else:
                res = engine.find_structures(sdef["type"], mc, seed, sdef["dim"],
                                             x0, z0, x1, z1)
            if res == engine.TOO_BROAD or not res:
                continue
            best = self._closest(res, cx, cz)
            if best:
                return best
        return None

    @staticmethod
    def _closest(res, cx, cz):
        if not res or res == engine.TOO_BROAD:
            return None
        return min(res, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cz) ** 2)

    def _update_struct_cell(self, key):
        if key not in self._struct_cells:   # not shown in the current dimension
            return
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
        self._refresh_structures(force=True)

    def _set_all_structures(self, on):
        # Only affects the structures shown for the current dimension.
        for s in engine.STRUCTURES:
            if s["dim"] == self._dim():
                self._struct_enabled[s["key"]].set(on)
                self._update_struct_cell(s["key"])
        self._refresh_structures(force=True)

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

    def _dim(self):
        return DIMENSION_KEY.get(self._dimension_var.get(), "overworld")

    def _make_provider(self):
        p = biomes.get_provider(self.project.seed, self.project.mc_version, self._dim())
        if p is not None:
            p.depth = self._depth_var.get()
            p.terrain = self._terrain_var.get() and self._dim() == "overworld"
            p.highlight = set(self._highlight_ids)
        return p

    def _change_dimension(self):
        dim = self._dim()
        self.map.set_dimension(dim)          # only this dimension's waypoints
        self._populate_structures()          # dimension-specific structure list
        self._populate_biome_list()          # dimension-specific biomes
        self._highlight_ids = set()          # highlight ids don't carry across dims
        self._apply_biome_layer()
        self._refresh_structures(force=True)
        self._status_var.set(f"Dimension: {self._dimension_var.get()}")

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
        self._refresh_structures(force=True)

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
        self._refresh_structures(force=True)
        self._note_version()

    def _note_version(self):
        if self._engine_available and engine.is_approximate(self.project.mc_version):
            self._status_var.set(
                f"Note: {self.project.mc_version} isn't modeled yet - showing "
                "1.21.4 generation (biomes and almost all structures match).")

    def _on_view_changed(self):
        self._refresh_structures()

    def _refresh_structures(self, force=False):
        if not (self._engine_available and self._structures_var.get()):
            self.map.set_structures([])
            self._struct_query = None
            return
        dim = self._dim()
        vx0, vz0, vx1, vz1 = [int(v) for v in self.map.view_bounds()]
        enabled = frozenset(k for k, v in self._struct_enabled.items() if v.get())
        # Skip re-querying while the view stays inside the already-queried area
        # and nothing relevant changed (keeps movement smooth).
        q = self._struct_query
        if (not force and q and q["dim"] == dim and q["seed"] == self.project.seed
                and q["mc"] == self.project.mc_version and q["enabled"] == enabled
                and q["x0"] <= vx0 and q["z0"] <= vz0
                and q["x1"] >= vx1 and q["z1"] >= vz1):
            return
        # Query over an area larger than the viewport so nearby pans are covered.
        padx, padz = (vx1 - vx0) // 2, (vz1 - vz0) // 2
        x0, z0, x1, z1 = vx0 - padx, vz0 - padz, vx1 + padx, vz1 + padz
        mc, seed = self.project.mc_version, self.project.seed
        markers, too_broad = [], False
        for sdef in engine.STRUCTURES:
            if sdef["dim"] != dim or sdef["key"] not in enabled:
                continue
            finder = sdef.get("finder", "region")
            if finder == "stronghold":
                res = engine.find_strongholds(mc, seed, x0, z0, x1, z1)
            elif finder == "mineshaft":
                res = engine.find_mineshafts(mc, seed, x0, z0, x1, z1)
            else:
                res = engine.find_structures(sdef["type"], mc, seed, sdef["dim"],
                                             x0, z0, x1, z1)
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
            self._struct_query = None          # couldn't cover; retry next time
            self._status_var.set("Zoom in to load structures (area too large).")
        else:
            self._struct_query = {"x0": x0, "z0": z0, "x1": x1, "z1": z1,
                                  "dim": dim, "seed": seed, "mc": mc, "enabled": enabled}
            if markers:
                self._status_var.set(f"{len(markers)} structures in view ({dim}).")

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
        dlg = WaypointDialog(self, wp, "Add structure as waypoint", self._categories())
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
                                  self._dim(), xi, zi)
            if bid is not None:
                text += f"   |   {biome_name(bid)}"
        self._coord_var.set(text)

    def _on_hover(self, text):
        if text:
            self._status_var.set(text)

    def _categories(self):
        return sorted({w.category for w in self.project.waypoints if w.category})

    def _on_map_place(self, x, z):
        wp = Waypoint(name="Waypoint", x=x, z=z, dimension=self._dim())
        dlg = WaypointDialog(self, wp, "New waypoint", self._categories())
        if dlg.result:
            self.project.add(dlg.result)
            self._mark_dirty()
            self._refresh_all()
            self.map.set_selected(dlg.result.id)
        self._add_var.set(False)
        self._toggle_add_mode()

    def _on_map_context(self, x, z, root_x, root_y):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label=f"Create waypoint here  ({x}, {z})",
                         command=lambda: self._create_waypoint_at(x, z))
        menu.tk_popup(root_x, root_y)

    def _create_waypoint_at(self, x, z):
        wp = Waypoint(name="Waypoint", x=x, z=z, dimension=self._dim())
        dlg = WaypointDialog(self, wp, "New waypoint", self._categories())
        if dlg.result:
            self.project.add(dlg.result)
            self._mark_dirty()
            self._refresh_all()
            self.map.set_selected(dlg.result.id)

    def _on_map_select(self, wp_id):
        self._select_in_tree(wp_id)

    def _on_map_edit(self, wp_id):
        self._edit_waypoint(wp_id)

    # ------------------------------------------------------------------ #
    # Waypoint list actions
    # ------------------------------------------------------------------ #
    def _add_waypoint_dialog(self):
        wp = Waypoint(name="Waypoint", x=int(round(self.map.center_x)),
                      z=int(round(self.map.center_z)), dimension=self._dim())
        dlg = WaypointDialog(self, wp, "New waypoint", self._categories())
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
        dlg = WaypointDialog(self, wp, "Edit waypoint", self._categories())
        if dlg.result:
            self._mark_dirty()
            self._refresh_all()
            self.map.set_selected(wp_id)

    def _delete_selected(self):
        self._delete_by_id(self._selected_id())

    def _delete_by_id(self, wp_id):
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
        if not wp:
            return
        # Switch to the waypoint's dimension first, then centre on it.
        if wp.dimension != self._dim():
            label = next((k for k, v in DIMENSION_KEY.items() if v == wp.dimension),
                         self._dimension_var.get())
            self._dimension_var.set(label)
            self._change_dimension()
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
        self._refresh_structures(force=True)
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
        # Keep the category filter dropdown in sync with existing categories.
        cats = ["All categories"] + self._categories()
        self._wp_cat_combo.config(values=cats)
        if self._wp_cat_var.get() not in cats:
            self._wp_cat_var.set("All categories")
        query = self._wp_search_var.get().strip().lower()
        catf = self._wp_cat_var.get()

        self.tree.delete(*self.tree.get_children())
        for w in self.project.waypoints:
            if query and query not in w.name.lower():
                continue
            if catf != "All categories" and w.category != catf:
                continue
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

    # ------------------------------------------------------------------ #
    # Auto-update (checks GitHub releases)
    # ------------------------------------------------------------------ #
    def _check_updates(self):
        self._status_var.set("Checking for updates...")

        def work():
            try:
                info = updater.get_latest()
                self.after(0, lambda: self._update_result(info, None))
            except Exception as exc:  # noqa: BLE001
                self.after(0, lambda e=exc: self._update_result(None, str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _update_result(self, info, err):
        if err:
            self._status_var.set("Update check failed.")
            messagebox.showerror("Update check failed",
                                 f"Could not reach GitHub:\n\n{err}")
            return
        tag = info["tag"]
        if not updater.is_newer(tag):
            self._status_var.set(f"Up to date (v{__version__}).")
            messagebox.showinfo("Up to date",
                                f"You're on the latest version (v{__version__}).")
            return
        name, url = updater.pick_installer(info["assets"])
        if not url:
            messagebox.showinfo(
                "Update available",
                f"{tag} is available, but no installer was attached.\n\n{info['url']}")
            return
        if messagebox.askyesno(
                "Update available",
                f"{tag} is available (you have v{__version__}).\n\n"
                "Download and install it now? Chunk Compass will close so the "
                "installer can finish."):
            self._download_update(name, url)

    def _download_update(self, name, url):
        self._status_var.set(f"Downloading {name}...")

        def work():
            try:
                path = updater.download(url, name)
                self.after(0, lambda: self._run_installer(path))
            except Exception as exc:  # noqa: BLE001
                self.after(0, lambda e=exc: (
                    self._status_var.set("Download failed."),
                    messagebox.showerror("Download failed", str(e))))

        threading.Thread(target=work, daemon=True).start()

    def _run_installer(self, path):
        # Offer to save first; cancel aborts the update.
        if not self._confirm_discard():
            return
        # Launch the installer via a short delay so this app is fully closed
        # (and its files unlocked) before msiexec starts - otherwise the MSI
        # reports that the program is in use.
        try:
            cmd = f'ping 127.0.0.1 -n 3 >nul & msiexec /i "{path}"'
            subprocess.Popen(
                cmd, shell=True,
                creationflags=(subprocess.DETACHED_PROCESS
                               | subprocess.CREATE_NEW_PROCESS_GROUP))
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Could not launch installer", str(exc))
            return
        self.destroy()
        os._exit(0)   # ensure the process (and its file locks) fully exits

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
