import tkinter as tk
from tkinter import ttk
import threading

from scipy import stats
from challenges.c1_layout import run_layout, LocationType
from challenges.c2_roads import run_roads

# ── Colours and labels shared across both challenges ──────────────────────────
COLORS = {
    LocationType.EMPTY:           "#f0f0f0",
    LocationType.RESIDENTIAL:     "#4CAF50",
    LocationType.HOSPITAL:        "#F44336",
    LocationType.SCHOOL:          "#2196F3",
    LocationType.INDUSTRIAL:      "#FF9800",
    LocationType.POWER_PLANT:     "#9C27B0",
    LocationType.AMBULANCE_DEPOT: "#00BCD4",
}

LABELS = {
    LocationType.EMPTY:           "",
    LocationType.RESIDENTIAL:     "R",
    LocationType.HOSPITAL:        "H",
    LocationType.SCHOOL:          "S",
    LocationType.INDUSTRIAL:      "I",
    LocationType.POWER_PLANT:     "P",
    LocationType.AMBULANCE_DEPOT: "A",
}

# Road drawing colours
ROAD_COLOR         = "#ECF0F1"   # normal MST road
ROAD_BLOCKED_COLOR = "#E74C3C"   # blocked road (future use)
PATH1_COLOR        = "#F1C40F"   # primary hospital→depot path
PATH2_COLOR        = "#1ABC9C"   # secondary (backup) path
ROAD_WIDTH         = 3


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("CityMind — Urban Intelligence System")

        self.cell_size = 55
        self.grid      = None   # set after C1 finishes
        self.city_graph = None  # set after C2 finishes
        self.path1      = None  # primary hospital→depot path
        self.path2      = None  # backup  hospital→depot path

        # ── Root layout: left controls panel + right canvas ──────────────────
        self.left = tk.Frame(self.root, padx=10, pady=10, width=220)
        self.left.pack(side="left", fill="y")
        self.left.pack_propagate(False)

        self.right = tk.Frame(self.root)
        self.right.pack(side="right", fill="both", expand=True)

        # ── Canvas (shared by both C1 grid view and C2 overlay) ──────────────
        self.canvas = tk.Canvas(self.right, bg="#34495e")
        self.canvas.pack(fill="both", expand=True)

        # ── Build left panel content ──────────────────────────────────────────
        self._build_left_panel()

        self.update_total()

    # ══════════════════════════════════════════════════════════════════════════
    # LEFT PANEL CONSTRUCTION
    # ══════════════════════════════════════════════════════════════════════════

    def _build_left_panel(self):
        """Build every widget in the left control panel."""

        # ── Title ─────────────────────────────────────────────────────────────
        tk.Label(
            self.left, text="CityMind Controls",
            font=("Arial", 14, "bold")
        ).pack(pady=(10, 4))

        # ── Separator ────────────────────────────────────────────────────────
        ttk.Separator(self.left, orient="horizontal").pack(fill="x", pady=4)

        # ── CHALLENGE 1 section ───────────────────────────────────────────────
        tk.Label(
            self.left, text="Challenge 1 — City Layout (CSP)",
            font=("Arial", 11, "bold"), fg="#2C3E50"
        ).pack(anchor="w", pady=(6, 2))

        # Grid size
        row_gs = tk.Frame(self.left)
        row_gs.pack(fill="x", pady=2)
        tk.Label(row_gs, text="Grid Size", width=18, anchor="w").pack(side="left")
        self.grid_size_var = tk.IntVar(value=8)
        tk.Spinbox(
            row_gs, from_=4, to=20,
            textvariable=self.grid_size_var,
            width=5,
            command=self.update_total
        ).pack(side="right")

        # Location type counts
        self.count_vars = {}
        for lt in [
            LocationType.RESIDENTIAL,
            LocationType.HOSPITAL,
            LocationType.SCHOOL,
            LocationType.INDUSTRIAL,
            LocationType.POWER_PLANT,
            LocationType.AMBULANCE_DEPOT,
        ]:
            var = tk.IntVar(value=0)
            self.count_vars[lt] = var

            frame = tk.Frame(self.left)
            frame.pack(fill="x", pady=1)
            tk.Label(frame, text=lt.value, width=18, anchor="w").pack(side="left")
            sp = tk.Spinbox(
                frame, from_=0, to=200,
                textvariable=var, width=5,
                command=self.update_total
            )
            sp.pack(side="right")
            var.trace_add("write", lambda *_: self.update_total())

        # Total counter
        self.total_label = tk.Label(
            self.left, text="", font=("Arial", 11, "bold")
        )
        self.total_label.pack(pady=6)

        # Run CSP button
        self.run_csp_btn = tk.Button(
            self.left, text="▶  Run CSP (Challenge 1)",
            bg="#2ECC71", fg="white",
            font=("Arial", 10, "bold"),
            command=self.run_csp
        )
        self.run_csp_btn.pack(fill="x", pady=4)

        # CSP progress readouts
        self.progress_label = tk.Label(self.left, text="Idle", fg="#2980B9")
        self.progress_label.pack()
        self.step_label  = tk.Label(self.left, text="Steps: 0")
        self.step_label.pack()
        self.depth_label = tk.Label(self.left, text="Depth: 0")
        self.depth_label.pack()

        # ── Separator ────────────────────────────────────────────────────────
        ttk.Separator(self.left, orient="horizontal").pack(fill="x", pady=8)

        # ── CHALLENGE 2 section ───────────────────────────────────────────────
        tk.Label(
            self.left, text="Challenge 2 — Road Network",
            font=("Arial", 11, "bold"), fg="#2C3E50"
        ).pack(anchor="w", pady=(0, 4))

        # Run Roads button
        self.run_roads_btn = tk.Button(
            self.left, text="▶  Build Roads (Challenge 2)",
            bg="#3498DB", fg="white",
            font=("Arial", 10, "bold"),
            state="disabled",            # enabled only after C1 succeeds
            command=self.run_roads
        )
        self.run_roads_btn.pack(fill="x", pady=4)

        # C2 status
        self.roads_status_label = tk.Label(
            self.left, text="Run Challenge 1 first.", fg="#7F8C8D"
        )
        self.roads_status_label.pack()

        # C2 result readouts
        self.roads_nodes_label = tk.Label(self.left, text="Nodes: —")
        self.roads_nodes_label.pack()
        self.roads_edges_label = tk.Label(self.left, text="Roads (MST): —")
        self.roads_edges_label.pack()
        self.roads_extra_label = tk.Label(self.left, text="Extra (backup): —")
        self.roads_extra_label.pack()
        self.roads_path1_label = tk.Label(self.left, text="Primary path: —")
        self.roads_path1_label.pack()
        self.roads_path2_label = tk.Label(self.left, text="Backup path: —")
        self.roads_path2_label.pack()

        # ── Legend ────────────────────────────────────────────────────────────
        ttk.Separator(self.left, orient="horizontal").pack(fill="x", pady=8)
        tk.Label(
            self.left, text="Legend",
            font=("Arial", 10, "bold")
        ).pack(anchor="w")
        self._build_legend()

    def _build_legend(self):
        """Small colour legend at the bottom of the left panel."""
        legend_items = [
            (ROAD_COLOR,  "Road (MST)"),
            (PATH1_COLOR, "Primary H→D path"),
            (PATH2_COLOR, "Backup H→D path"),
        ]
        for color, label in legend_items:
            row = tk.Frame(self.left)
            row.pack(fill="x", pady=1, anchor="w")
            tk.Canvas(row, width=16, height=16, bg=color,
                      highlightthickness=1, highlightbackground="#999").pack(side="left", padx=(0, 6))
            tk.Label(row, text=label, anchor="w").pack(side="left")

        for lt, label in [
            (LocationType.HOSPITAL,        "Hospital (H)"),
            (LocationType.AMBULANCE_DEPOT, "Ambulance Depot (A)"),
        ]:
            row = tk.Frame(self.left)
            row.pack(fill="x", pady=1, anchor="w")
            tk.Canvas(row, width=16, height=16, bg=COLORS[lt],
                      highlightthickness=1, highlightbackground="#999").pack(side="left", padx=(0, 6))
            tk.Label(row, text=label, anchor="w").pack(side="left")

    # ══════════════════════════════════════════════════════════════════════════
    # TOTAL VALIDATION
    # ══════════════════════════════════════════════════════════════════════════

    def update_total(self):
        size     = self.grid_size_var.get()
        capacity = size * size
        total    = sum(var.get() for var in self.count_vars.values())

        self.total_label.config(text=f"Total: {total} / {capacity}")

        if total > capacity:
            self.total_label.config(fg="red")
            self.run_csp_btn.config(state="disabled")
        else:
            self.total_label.config(fg="#27AE60")
            self.run_csp_btn.config(state="normal")

    # ══════════════════════════════════════════════════════════════════════════
    # CHALLENGE 1 — RUN CSP
    # ══════════════════════════════════════════════════════════════════════════

    def run_csp(self):
        self.run_csp_btn.config(state="disabled")
        self.run_roads_btn.config(state="disabled")
        self.running = True

        stats.steps    = 0
        stats.depth    = 0
        stats.max_depth = 0

        self.progress_label.config(text="Running CSP…", fg="#E67E22")

        def worker():
            size = self.grid_size_var.get()
            required_counts = {lt: var.get() for lt, var in self.count_vars.items()}
            grid, violations = run_layout(size, required_counts)
            self.root.after(0, lambda: self.finish_csp(grid, violations))

        threading.Thread(target=worker, daemon=True).start()
        self.update_progress_ui()

    def update_progress_ui(self):
        self.step_label.config(text=f"Steps: {stats.steps}")
        self.depth_label.config(text=f"Depth: {stats.depth} / Max {stats.max_depth}")
        if hasattr(self, "running") and self.running:
            self.root.after(100, self.update_progress_ui)

    def finish_csp(self, grid, violations):
        self.running    = False
        self.grid       = grid
        self.city_graph = None   # reset C2 result when C1 re-runs
        self.path1      = None
        self.path2      = None

        self.draw_grid()         # draw just the grid (no roads yet)

        if violations:
            self.progress_label.config(
                text=f"Finished with {len(violations)} violation(s)", fg="#E74C3C"
            )
        else:
            self.progress_label.config(text="Solved successfully ✓", fg="#27AE60")

        self.run_csp_btn.config(state="normal")
        # Enable C2 only when C1 has a layout (even with violations)
        self.run_roads_btn.config(state="normal")
        self.roads_status_label.config(
            text="Ready — click Build Roads.", fg="#2980B9"
        )
        # Reset C2 readouts
        self.roads_nodes_label.config(text="Nodes: —")
        self.roads_edges_label.config(text="Roads (MST): —")
        self.roads_extra_label.config(text="Extra (backup): —")
        self.roads_path1_label.config(text="Primary path: —")
        self.roads_path2_label.config(text="Backup path: —")

    # ══════════════════════════════════════════════════════════════════════════
    # CHALLENGE 2 — BUILD ROADS
    # ══════════════════════════════════════════════════════════════════════════

    def run_roads(self):
        if self.grid is None:
            return

        self.run_roads_btn.config(state="disabled")
        self.run_csp_btn.config(state="disabled")
        self.roads_status_label.config(text="Building road network…", fg="#E67E22")

        def worker():
            G, path1, path2 = run_roads(self.grid)
            self.root.after(0, lambda: self.finish_roads(G, path1, path2))

        threading.Thread(target=worker, daemon=True).start()

    def finish_roads(self, G, path1, path2):
        self.city_graph = G
        self.path1      = path1
        self.path2      = path2

        # Count MST edges vs extra redundancy edges
        mst_edge_count   = sum(1 for _, _, d in G.edges(data=True) if not d.get("redundancy", False))
        extra_edge_count = sum(1 for _, _, d in G.edges(data=True) if d.get("redundancy", False))

        self.roads_status_label.config(text="Road network built ✓", fg="#27AE60")
        self.roads_nodes_label.config(text=f"Nodes: {G.number_of_nodes()}")
        self.roads_edges_label.config(text=f"Roads (MST): {mst_edge_count}")
        self.roads_extra_label.config(text=f"Extra (backup): {extra_edge_count}")
        self.roads_path1_label.config(
            text=f"Primary path: {len(path1)-1} hops" if path1 else "Primary path: none"
        )
        self.roads_path2_label.config(
            text=f"Backup path: {len(path2)-1} hops" if path2 else "Backup path: none ⚠"
        )

        # Redraw the grid with the road overlay on top
        self.draw_grid()
        self.draw_roads()

        self.run_roads_btn.config(state="normal")
        self.run_csp_btn.config(state="normal")

    # ══════════════════════════════════════════════════════════════════════════
    # DRAWING — GRID (Challenge 1 view, unchanged logic)
    # ══════════════════════════════════════════════════════════════════════════

    def _cell_centre(self, row, col):
        """Return the pixel (cx, cy) of the centre of cell (row, col)."""
        padding = 2
        x1 = col * self.cell_size + (col + 1) * padding
        y1 = row * self.cell_size + (row + 1) * padding
        return x1 + self.cell_size / 2, y1 + self.cell_size / 2

    def draw_grid(self):
        """Draw all grid cells (clears canvas first)."""
        self.canvas.delete("all")

        if self.grid is None:
            return

        size    = self.grid.size
        padding = 2

        canvas_size = size * self.cell_size + (size + 1) * padding
        self.canvas.config(width=canvas_size, height=canvas_size)

        for r in range(size):
            for c in range(size):
                cell = self.grid.get_cell(r, c)

                x1 = c * self.cell_size + (c + 1) * padding
                y1 = r * self.cell_size + (r + 1) * padding
                x2 = x1 + self.cell_size
                y2 = y1 + self.cell_size

                color = COLORS.get(cell.location_type, "#7F8C8D")
                label = LABELS.get(cell.location_type, "?")

                self.canvas.create_rectangle(
                    x1, y1, x2, y2, fill=color, outline="#2C3E50", width=1
                )
                if label:
                    self.canvas.create_text(
                        (x1 + x2) / 2, (y1 + y2) / 2,
                        text=label, fill="white",
                        font=("Arial", 14, "bold")
                    )

    # ══════════════════════════════════════════════════════════════════════════
    # DRAWING — ROADS (Challenge 2 overlay)
    # ══════════════════════════════════════════════════════════════════════════

    def draw_roads(self):
        """
        Overlay roads on top of the already-drawn grid.

        Drawing order (back → front so important paths are visible):
          1. All MST roads          — thin white lines
          2. Primary path (path1)   — yellow, slightly thicker
          3. Backup  path (path2)   — teal,   slightly thicker
        """
        if self.city_graph is None:
            return

        G = self.city_graph

        # Collect path edge sets for fast lookup
        path1_edges = set()
        if self.path1:
            for i in range(len(self.path1) - 1):
                path1_edges.add(frozenset({self.path1[i], self.path1[i + 1]}))

        path2_edges = set()
        if self.path2:
            for i in range(len(self.path2) - 1):
                path2_edges.add(frozenset({self.path2[i], self.path2[i + 1]}))

        # ── Pass 1: draw all roads (skip highlighted path edges for now) ──────
        for u, v, data in G.edges(data=True):
            edge_key = frozenset({u, v})
            if edge_key in path1_edges or edge_key in path2_edges:
                continue   # drawn in pass 2 / 3 on top

            color  = ROAD_BLOCKED_COLOR if data.get("blocked", False) else ROAD_COLOR
            ux, uy = self._cell_centre(*u)
            vx, vy = self._cell_centre(*v)
            self.canvas.create_line(
                ux, uy, vx, vy,
                fill=color, width=ROAD_WIDTH,
                tags="road"
            )

        # ── Pass 2: primary path (yellow) ─────────────────────────────────────
        for edge_key in path1_edges:
            u, v = tuple(edge_key)
            ux, uy = self._cell_centre(*u)
            vx, vy = self._cell_centre(*v)
            self.canvas.create_line(
                ux, uy, vx, vy,
                fill=PATH1_COLOR, width=ROAD_WIDTH + 2,
                tags="path1"
            )

        # ── Pass 3: backup path (teal) ────────────────────────────────────────
        for edge_key in path2_edges:
            u, v = tuple(edge_key)
            ux, uy = self._cell_centre(*u)
            vx, vy = self._cell_centre(*v)
            self.canvas.create_line(
                ux, uy, vx, vy,
                fill=PATH2_COLOR, width=ROAD_WIDTH + 2,
                dash=(6, 3),       # dashed so it's visually distinct from path1
                tags="path2"
            )

        # ── Pass 4: redraw node labels on top so roads don't cover them ───────
        if self.grid:
            size    = self.grid.size
            padding = 2
            for r in range(size):
                for c in range(size):
                    cell  = self.grid.get_cell(r, c)
                    label = LABELS.get(cell.location_type, "")
                    if not label:
                        continue
                    x1 = c * self.cell_size + (c + 1) * padding
                    y1 = r * self.cell_size + (r + 1) * padding
                    x2 = x1 + self.cell_size
                    y2 = y1 + self.cell_size
                    self.canvas.create_text(
                        (x1 + x2) / 2, (y1 + y2) / 2,
                        text=label, fill="white",
                        font=("Arial", 14, "bold"),
                        tags="label"
                    )

    # ══════════════════════════════════════════════════════════════════════════
    # MAIN LOOP
    # ══════════════════════════════════════════════════════════════════════════

    def run(self):
        self.root.mainloop()