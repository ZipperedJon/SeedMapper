"""The SeedMapper desktop application (Tkinter)."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

from . import __app_name__, __version__, biomes, exporters, msf
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
        self._swatch = tk.Label(frm, width=4, background=self._color.get(),
                                relief="sunken")
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
        rgb, hexval = colorchooser.askcolor(color=self._color.get(), parent=self)
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
            messagebox.showerror("Invalid Y", "Y must be a whole number or blank.",
                                 parent=self)
            return

        self._wp.name = self._name.get().strip() or "Waypoint"
        self._wp.x = x
        self._wp.z = z
        self._wp.y = y
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
        self.geometry("1100x720")
        self.minsize(820, 520)

        self.project = Project()
        self.current_path: Path | None = None
        self.dirty = False

        self._coord_var = tk.StringVar(value="X: -, Z: -")
        self._status_var = tk.StringVar(value="Ready")
        self._seed_var = tk.StringVar(value=self.project.seed)
        self._version_var = tk.StringVar(value=self.project.mc_version)
        self._biome_var = tk.BooleanVar(value=False)
        self._add_var = tk.BooleanVar(value=False)

        self._build_menu()
        self._build_toolbar()
        self._build_body()
        self._build_statusbar()

        self._biome_available = biomes.try_load_backend() is not None
        self._refresh_biome_control()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._refresh_all()
        self._update_title()

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
        viewmenu.add_command(label="Reset view (home)", accelerator="Ctrl+H",
                             command=lambda: self.map.go_home())
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
        seed_entry = ttk.Entry(bar, textvariable=self._seed_var, width=22)
        seed_entry.pack(side="left", padx=(4, 12))
        seed_entry.bind("<FocusOut>", lambda e: self._on_seed_version_change())
        seed_entry.bind("<Return>", lambda e: self._on_seed_version_change())

        ttk.Label(bar, text="MC version:").pack(side="left")
        ver_entry = ttk.Entry(bar, textvariable=self._version_var, width=8)
        ver_entry.pack(side="left", padx=(4, 12))
        ver_entry.bind("<FocusOut>", lambda e: self._on_seed_version_change())
        ver_entry.bind("<Return>", lambda e: self._on_seed_version_change())

        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=8)

        self._add_btn = ttk.Checkbutton(
            bar, text="Add waypoint (click map)", variable=self._add_var,
            style="Toolbutton", command=self._toggle_add_mode)
        self._add_btn.pack(side="left", padx=4)

        self._biome_chk = ttk.Checkbutton(
            bar, text="Biome layer", variable=self._biome_var,
            style="Toolbutton", command=self._toggle_biomes)
        self._biome_chk.pack(side="left", padx=4)

        ttk.Button(bar, text="Home", command=lambda: self.map.go_home()).pack(side="left", padx=4)

    def _build_body(self):
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(side="top", fill="both", expand=True)

        # Left: waypoint list + buttons.
        left = ttk.Frame(paned, padding=(6, 6))
        paned.add(left, weight=0)

        ttk.Label(left, text="Waypoints", font=("Segoe UI", 10, "bold")).pack(anchor="w")

        cols = ("name", "x", "z", "dim")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", height=20,
                                 selectmode="browse")
        self.tree.heading("name", text="Name")
        self.tree.heading("x", text="X")
        self.tree.heading("z", text="Z")
        self.tree.heading("dim", text="Dim")
        self.tree.column("name", width=140)
        self.tree.column("x", width=56, anchor="e")
        self.tree.column("z", width=56, anchor="e")
        self.tree.column("dim", width=70)
        self.tree.pack(fill="both", expand=True, pady=(4, 6))
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", lambda e: self._edit_selected())

        btns = ttk.Frame(left)
        btns.pack(fill="x")
        ttk.Button(btns, text="Add", command=self._add_waypoint_dialog).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(btns, text="Edit", command=self._edit_selected).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(btns, text="Delete", command=self._delete_selected).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(left, text="Go to on map", command=self._goto_selected).pack(fill="x", pady=(6, 0))

        # Right: the map.
        self.map = MapCanvas(paned)
        paned.add(self.map, weight=1)
        self.map.on_coords = self._on_map_coords
        self.map.on_place = self._on_map_place
        self.map.on_select = self._on_map_select
        self.map.on_edit = self._on_map_edit

    def _build_statusbar(self):
        bar = ttk.Frame(self, relief="sunken")
        bar.pack(side="bottom", fill="x")
        ttk.Label(bar, textvariable=self._coord_var, anchor="w", width=24).pack(side="left", padx=8)
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", pady=2)
        ttk.Label(bar, textvariable=self._status_var, anchor="w").pack(side="left", padx=8)

    # ------------------------------------------------------------------ #
    # Biome control
    # ------------------------------------------------------------------ #
    def _refresh_biome_control(self):
        state = "normal" if self._biome_available else "disabled"
        self._biome_chk.config(state=state)
        if not self._biome_available:
            self._biome_var.set(False)
            self._status_var.set(
                "Biome layer unavailable (no world-gen backend installed). "
                "Grid + waypoints only.")

    def _toggle_biomes(self):
        if not self._biome_available:
            self._biome_var.set(False)
            return
        enabled = self._biome_var.get()
        if enabled:
            provider = biomes.get_provider(self.project.seed, self.project.mc_version)
            self.map.set_biome_provider(provider)
        self.map.set_biome_enabled(enabled)

    # ------------------------------------------------------------------ #
    # Toolbar actions
    # ------------------------------------------------------------------ #
    def _toggle_add_mode(self):
        self.map.set_add_mode(self._add_var.get())
        if self._add_var.get():
            self._status_var.set("Add mode: click on the map to drop a waypoint.")
        else:
            self._status_var.set("Ready")

    def _on_seed_version_change(self):
        seed = self._seed_var.get().strip()
        version = self._version_var.get().strip() or "1.21"
        if seed != self.project.seed or version != self.project.mc_version:
            self.project.seed = seed
            self.project.mc_version = version
            self._mark_dirty()
            if self._biome_var.get():
                self._toggle_biomes()

    # ------------------------------------------------------------------ #
    # Map callbacks
    # ------------------------------------------------------------------ #
    def _on_map_coords(self, x, z):
        self._coord_var.set(f"X: {int(round(x))}, Z: {int(round(z))}")

    def _on_map_place(self, x, z):
        wp = Waypoint(name="Waypoint", x=x, z=z)
        dlg = WaypointDialog(self, wp, "New waypoint")
        if dlg.result:
            self.project.add(dlg.result)
            self._mark_dirty()
            self._refresh_all()
            self.map.set_selected(dlg.result.id)
        # Leave add mode after one placement.
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
        cx, cz = self.map.center_x, self.map.center_z
        wp = Waypoint(name="Waypoint", x=int(round(cx)), z=int(round(cz)))
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
        if wp and messagebox.askyesno("Delete waypoint",
                                      f"Delete '{wp.name}'?"):
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
        path = filedialog.askopenfilename(title="Open map",
                                          filetypes=MSF_FILETYPES)
        if not path:
            return
        try:
            self.project = msf.load(path)
        except msf.MsfError as exc:
            messagebox.showerror("Cannot open file", str(exc))
            return
        self.current_path = Path(path)
        self.dirty = False
        self._seed_var.set(self.project.seed)
        self._version_var.set(self.project.mc_version)
        self._refresh_all()
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
            title="Export CSV", defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
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
        # Rebuild the tree.
        self.tree.delete(*self.tree.get_children())
        for w in self.project.waypoints:
            y = "" if w.y is None else w.y
            self.tree.insert("", "end", iid=w.id,
                             values=(w.name, w.x, w.z, w.dimension))
        self.map.set_waypoints(self.project.waypoints)

    def _mark_dirty(self):
        self.dirty = True
        self._update_title()

    def _update_title(self):
        name = self.current_path.name if self.current_path else "Untitled"
        star = "*" if self.dirty else ""
        self.title(f"{star}{name} - {__app_name__}")

    def _confirm_discard(self):
        if not self.dirty:
            return True
        answer = messagebox.askyesnocancel(
            "Unsaved changes",
            "You have unsaved changes. Save before continuing?")
        if answer is None:
            return False
        if answer:
            return self.save_project()
        return True

    def _on_close(self):
        if self._confirm_discard():
            self.destroy()

    def _about(self):
        backend = biomes.BACKEND_NAME or "none (grid + waypoints only)"
        messagebox.showinfo(
            "About " + __app_name__,
            f"{__app_name__} v{__version__}\n\n"
            "A Minecraft seed map with custom waypoints.\n"
            f"Biome backend: {backend}\n\n"
            "Files are saved as .msf; export to CSV or Markdown.")


def run():
    app = App()
    app.mainloop()
