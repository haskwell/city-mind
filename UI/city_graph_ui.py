import tkinter as tk
from tkinter import ttk, messagebox
import math
from Core.city_graph import CityGraph


BUILDING_CONFIG = {
    "hospital":        {"icon": "H",  "color": "#F7C1C1", "border": "#E24B4A", "label": "Hospital"},
    "school":          {"icon": "S",  "color": "#C0DD97", "border": "#639922", "label": "School"},
    "industrial":      {"icon": "I",  "color": "#D3D1C7", "border": "#888780", "label": "Industrial"},
    "residential":     {"icon": "R",  "color": "#FAC775", "border": "#BA7517", "label": "Residential"},
    "power_plant":     {"icon": "P",  "color": "#F4C0D1", "border": "#D4537E", "label": "Power Plant"},
    "ambulance_depot": {"icon": "A",  "color": "#9FE1CB", "border": "#1D9E75", "label": "Amb. Depot"},
}

RISK_CONFIG = {
    "low":    {"color": None,      "mult": 1.0},
    "medium": {"color": "#EF9F27", "mult": 1.2},
    "high":   {"color": "#E24B4A", "mult": 1.5},
}

EMPTY_COLOR  = "#D6E8F8"
EMPTY_BORDER = "#8BBDE0"
BLOCK_COLOR  = "#E24B4A"
BG           = "#F5F4F0"
PANEL_BG     = "#EBEBEA"
TEXT_COLOR   = "#2C2C2A"
MUTED_COLOR  = "#888780"


class CityGraphUI:
    def __init__(self, root):
        self.root = root
        self.root.title("CityMind — Graph Visualizer")
        self.root.configure(bg=BG)
        self.root.minsize(900, 600)

        self.graph = None
        self.mode = tk.StringVar(value="view")
        self.building_type = tk.StringVar(value="hospital")
        self.risk_level = tk.StringVar(value="high")
        self.rows_var = tk.IntVar(value=6)
        self.cols_var = tk.IntVar(value=8)

        self.node_items = {}       # node_id -> canvas rect id
        self.edge_items = {}       # (a,b) -> canvas line id
        self.block_first = None    # for block mode two-click
        self.selected_node = None

        self._build_ui()
        self._build_graph()

    def _build_ui(self):
        # ── Top toolbar ──────────────────────────────────────────────────────
        toolbar = tk.Frame(self.root, bg=PANEL_BG, pady=6, padx=10)
        toolbar.pack(fill=tk.X, side=tk.TOP)

        tk.Label(toolbar, text="CITYMIND", font=("Courier", 13, "bold"),
                 bg=PANEL_BG, fg=TEXT_COLOR).pack(side=tk.LEFT, padx=(0, 16))

        tk.Label(toolbar, text="rows", font=("Courier", 10), bg=PANEL_BG, fg=MUTED_COLOR).pack(side=tk.LEFT)
        tk.Scale(toolbar, from_=2, to=30, orient=tk.HORIZONTAL, variable=self.rows_var,
                 length=80, font=("Courier", 9), bg=PANEL_BG, fg=TEXT_COLOR,
                 highlightthickness=0, troughcolor=PANEL_BG).pack(side=tk.LEFT, padx=(2, 8))

        tk.Label(toolbar, text="cols", font=("Courier", 10), bg=PANEL_BG, fg=MUTED_COLOR).pack(side=tk.LEFT)
        tk.Scale(toolbar, from_=2, to=30, orient=tk.HORIZONTAL, variable=self.cols_var,
                 length=80, font=("Courier", 9), bg=PANEL_BG, fg=TEXT_COLOR,
                 highlightthickness=0, troughcolor=PANEL_BG).pack(side=tk.LEFT, padx=(2, 8))

        tk.Button(toolbar, text="Build ↻", font=("Courier", 10, "bold"),
                  command=self._build_graph, bg="#378ADD", fg="white",
                  relief=tk.FLAT, padx=10, pady=3).pack(side=tk.LEFT, padx=(0, 16))

        tk.Frame(toolbar, bg=MUTED_COLOR, width=1, height=24).pack(side=tk.LEFT, padx=8)

        for mode, label, color in [("view", "VIEW", "#3B6D11"), ("place", "PLACE", "#185FA5"),
                                    ("block", "BLOCK", "#A32D2D"), ("risk", "RISK", "#854F0B")]:
            tk.Radiobutton(toolbar, text=label, variable=self.mode, value=mode,
                           font=("Courier", 9, "bold"), bg=PANEL_BG, fg=color,
                           activebackground=PANEL_BG, selectcolor=PANEL_BG,
                           command=self._on_mode_change).pack(side=tk.LEFT, padx=4)

        tk.Frame(toolbar, bg=MUTED_COLOR, width=1, height=24).pack(side=tk.LEFT, padx=8)

        tk.Label(toolbar, text="building", font=("Courier", 9), bg=PANEL_BG, fg=MUTED_COLOR).pack(side=tk.LEFT)
        bld_menu = ttk.Combobox(toolbar, textvariable=self.building_type, width=14,
                                values=list(BUILDING_CONFIG.keys()), state="readonly",
                                font=("Courier", 9))
        bld_menu.pack(side=tk.LEFT, padx=(2, 10))

        tk.Label(toolbar, text="risk", font=("Courier", 9), bg=PANEL_BG, fg=MUTED_COLOR).pack(side=tk.LEFT)
        risk_menu = ttk.Combobox(toolbar, textvariable=self.risk_level, width=7,
                                 values=["low", "medium", "high"], state="readonly",
                                 font=("Courier", 9))
        risk_menu.pack(side=tk.LEFT, padx=(2, 10))

        tk.Button(toolbar, text="Clear", font=("Courier", 9),
                  command=self._clear_graph, bg=PANEL_BG, fg=MUTED_COLOR,
                  relief=tk.FLAT, padx=8).pack(side=tk.LEFT)

        # ── Main area: canvas + side legend ──────────────────────────────────
        main = tk.Frame(self.root, bg=BG)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=(6, 0))

        # Canvas with scrollbars
        canvas_frame = tk.Frame(main, bg=BG)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_frame, bg="#EEF4FA", highlightthickness=0, cursor="hand2")
        hbar = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        vbar = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        hbar.pack(side=tk.BOTTOM, fill=tk.X)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self._on_canvas_click)

        # Side panel with scrollbar
        side_container = tk.Frame(main, bg=PANEL_BG, width=280)
        side_container.pack(side=tk.RIGHT, fill=tk.Y)
        side_container.pack_propagate(False)

        # Create canvas and scrollbar for side panel
        side_canvas = tk.Canvas(side_container, bg=PANEL_BG, highlightthickness=0)
        side_scrollbar = tk.Scrollbar(side_container, orient=tk.VERTICAL, command=side_canvas.yview)
        side = tk.Frame(side_canvas, bg=PANEL_BG)

        # Configure scrolling
        side_canvas.configure(yscrollcommand=side_scrollbar.set)
        side_canvas_frame = side_canvas.create_window((0, 0), window=side, anchor=tk.NW)

        # Pack scrollbar and canvas
        side_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        side_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Configure canvas to update scroll region when frame changes
        side.bind('<Configure>', lambda e: side_canvas.configure(scrollregion=side_canvas.bbox('all')))

        tk.Label(side, text="LEGEND", font=("Courier", 9, "bold"),
                 bg=PANEL_BG, fg=MUTED_COLOR).pack(anchor=tk.W, pady=(0, 6))

        for btype, cfg in BUILDING_CONFIG.items():
            f = tk.Frame(side, bg=PANEL_BG)
            f.pack(anchor=tk.W, pady=1)
            tk.Canvas(f, width=14, height=14, bg=cfg["color"],
                      highlightbackground=cfg["border"], highlightthickness=1).pack(side=tk.LEFT)
            tk.Label(f, text=f"  {cfg['label']}", font=("Courier", 9),
                     bg=PANEL_BG, fg=TEXT_COLOR).pack(side=tk.LEFT)

        tk.Frame(side, bg=MUTED_COLOR, height=1).pack(fill=tk.X, pady=8)
        tk.Label(side, text="RISK", font=("Courier", 9, "bold"),
                 bg=PANEL_BG, fg=MUTED_COLOR).pack(anchor=tk.W, pady=(0, 4))
        for level, cfg in RISK_CONFIG.items():
            if cfg["color"]:
                f = tk.Frame(side, bg=PANEL_BG)
                f.pack(anchor=tk.W, pady=1)
                c = tk.Canvas(f, width=10, height=10, bg=cfg["color"],
                              highlightthickness=0)
                c.pack(side=tk.LEFT)
                tk.Label(f, text=f"  {level} (×{cfg['mult']})", font=("Courier", 9),
                         bg=PANEL_BG, fg=TEXT_COLOR).pack(side=tk.LEFT)

        tk.Frame(side, bg=MUTED_COLOR, height=1).pack(fill=tk.X, pady=8)
        
        # Challenges Section
        tk.Label(side, text="CHALLENGES", font=("Courier", 9, "bold"),
                 bg=PANEL_BG, fg=MUTED_COLOR).pack(anchor=tk.W, pady=(0, 4))
        
        self.challenge_frames = {}
        self.challenge_buttons = {}
        self.challenge_content = {}
        self.challenge_states = {}  # Track expanded/collapsed state
        
        challenges = [
            ("1: CSP Layout", "csp_layout"),
            ("2: Future Challenge", "future_challenge"),
            ("3: Future Challenge", "future_challenge2"),
            ("4: Future Challenge", "future_challenge3"),
            ("5: Future Challenge", "future_challenge4")
        ]
        
        for label, value in challenges:
            # Challenge container
            challenge_frame = tk.Frame(side, bg=PANEL_BG, relief=tk.RAISED, bd=1)
            challenge_frame.pack(fill=tk.X, pady=2)
            
            # Header button
            header = tk.Frame(challenge_frame, bg=PANEL_BG, cursor="hand2")
            header.pack(fill=tk.X)
            header.bind("<Button-1>", lambda e, v=value: self._toggle_challenge(v))
            
            # Arrow indicator and label
            self.challenge_states[value] = False  # Initially collapsed
            arrow_label = tk.Label(header, text="▶", font=("Courier", 8, "bold"),
                                  bg=PANEL_BG, fg=TEXT_COLOR)
            arrow_label.pack(side=tk.LEFT, padx=5, pady=2)
            
            tk.Label(header, text=label, font=("Courier", 8, "bold"),
                     bg=PANEL_BG, fg=TEXT_COLOR).pack(side=tk.LEFT, padx=2, pady=2)
            
            self.challenge_buttons[value] = arrow_label
            
            # Content frame (initially hidden)
            content_frame = tk.Frame(challenge_frame, bg=PANEL_BG)
            content_frame.pack(fill=tk.X)
            content_frame.pack_forget()  # Initially hidden
            
            self.challenge_frames[value] = content_frame
            
            # Add content for Challenge 1 only
            if value == "csp_layout":
                self._build_csp_content(content_frame)
            else:
                tk.Label(content_frame, text="Coming soon...", font=("Courier", 8, "italic"),
                         bg=PANEL_BG, fg=MUTED_COLOR).pack(padx=10, pady=5)
        
        tk.Frame(side, bg=MUTED_COLOR, height=1).pack(fill=tk.X, pady=8)
        tk.Label(side, text="STATS", font=("Courier", 9, "bold"),
                 bg=PANEL_BG, fg=MUTED_COLOR).pack(anchor=tk.W, pady=(0, 4))
        self.stats_labels = {}
        for key in ["nodes", "edges", "blocked_edges", "buildings", "high_risk_nodes", "ambulance_depots"]:
            f = tk.Frame(side, bg=PANEL_BG)
            f.pack(anchor=tk.W, pady=1, fill=tk.X)
            tk.Label(f, text=key.replace("_", " "), font=("Courier", 8),
                     bg=PANEL_BG, fg=MUTED_COLOR).pack(side=tk.LEFT)
            lbl = tk.Label(f, text="0", font=("Courier", 8, "bold"),
                           bg=PANEL_BG, fg=TEXT_COLOR)
            lbl.pack(side=tk.RIGHT)
            self.stats_labels[key] = lbl

        # ── Status bar ───────────────────────────────────────────────────────
        self.status_var = tk.StringVar(value="ready")
        status_bar = tk.Label(self.root, textvariable=self.status_var,
                              font=("Courier", 9), bg=PANEL_BG, fg=MUTED_COLOR,
                              anchor=tk.W, padx=10, pady=4)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    # ── Graph construction ────────────────────────────────────────────────────

    def _build_graph(self):
        rows = max(2, min(30, self.rows_var.get()))
        cols = max(2, min(30, self.cols_var.get()))
        self.rows_var.set(rows)
        self.cols_var.set(cols)
        self.graph = CityGraph(rows, cols)
        self.block_first = None
        self.selected_node = None
        self._render()
        self._update_stats()
        self._update_csp_sliders()  # Update CSP sliders with new grid size
        self._set_status(f"built {rows}×{cols} grid — {rows*cols} nodes")

    def _clear_graph(self):
        if self.graph:
            self.graph.reset()
            self.block_first = None
            self.selected_node = None
            self._render()
            self._update_stats()
            self._set_status("graph cleared")

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _cell_size(self):
        r, c = self.graph.rows, self.graph.cols
        if r > 15 or c > 15:
            return 40
        if r > 10 or c > 10:
            return 50
        return 60

    def _gap_size(self):
        r, c = self.graph.rows, self.graph.cols
        if r > 15 or c > 15:
            return 15
        if r > 10 or c > 10:
            return 20
        return 25

    def _render(self):
        self.canvas.delete("all")
        self.node_items.clear()
        self.edge_items.clear()

        g = self.graph
        cs = self._cell_size()
        pad = 16
        gap = self._gap_size()

        # Draw edges first (below nodes)
        for a, b, data in g.G.edges(data=True):
            na, nb = g.G.nodes[a], g.G.nodes[b]
            x1 = pad + na['col'] * (cs + gap) + cs // 2
            y1 = pad + na['row'] * (cs + gap) + cs // 2
            x2 = pad + nb['col'] * (cs + gap) + cs // 2
            y2 = pad + nb['row'] * (cs + gap) + cs // 2
            color = BLOCK_COLOR if data['is_blocked'] else "#4A90E2"
            width = 4 if data['is_blocked'] else 2
            item = self.canvas.create_line(x1, y1, x2, y2, fill=color, width=width, tags="edge")
            self.edge_items[(min(a, b), max(a, b))] = item

        # Draw nodes
        for nid, data in g.G.nodes(data=True):
            x = pad + data['col'] * (cs + gap)
            y = pad + data['row'] * (cs + gap)
            btype = data['location_type']
            cfg = BUILDING_CONFIG.get(btype) if btype else None
            bg = cfg['color'] if cfg else EMPTY_COLOR
            border = cfg['border'] if cfg else EMPTY_BORDER

            rect = self.canvas.create_rectangle(
                x, y, x + cs, y + cs,
                fill=bg, outline=border, width=2, tags=("node", f"node_{nid}")
            )
            self.node_items[nid] = rect

            # Label
            label = cfg['icon'] if cfg else str(nid) if cs >= 44 else ""
            self.canvas.create_text(
                x + cs // 2, y + cs // 2,
                text=label,
                font=("Courier", max(8, cs // 5), "bold"),
                fill=border if cfg else MUTED_COLOR,
                tags=f"node_{nid}"
            )

            # Risk dot
            rl = data['risk_level']
            if rl and RISK_CONFIG[rl]['color']:
                dot_r = max(4, cs // 8)
                self.canvas.create_oval(
                    x + cs - dot_r * 2 - 2, y + 2,
                    x + cs - 2,             y + dot_r * 2 + 2,
                    fill=RISK_CONFIG[rl]['color'], outline="", tags=f"node_{nid}"
                )

        # Update scroll region
        total_w = pad * 2 + g.cols * (cs + gap)
        total_h = pad * 2 + g.rows * (cs + gap)
        self.canvas.configure(scrollregion=(0, 0, total_w, total_h))

    def _render_node(self, nid):
        """Re-render a single node without full redraw."""
        g = self.graph
        cs = self._cell_size()
        pad = 16
        gap = self._gap_size()
        data = g.G.nodes[nid]

        self.canvas.delete(f"node_{nid}")
        x = pad + data['col'] * (cs + gap)
        y = pad + data['row'] * (cs + gap)
        btype = data['location_type']
        cfg = BUILDING_CONFIG.get(btype) if btype else None
        bg = cfg['color'] if cfg else EMPTY_COLOR
        border = cfg['border'] if cfg else EMPTY_BORDER

        selected = (nid == self.selected_node)
        rect = self.canvas.create_rectangle(
            x, y, x + cs, y + cs,
            fill=bg, outline="#378ADD" if selected else border,
            width=3 if selected else 2,
            tags=("node", f"node_{nid}")
        )
        self.node_items[nid] = rect

        label = cfg['icon'] if cfg else str(nid) if cs >= 44 else ""
        self.canvas.create_text(
            x + cs // 2, y + cs // 2,
            text=label, font=("Courier", max(8, cs // 5), "bold"),
            fill=border if cfg else MUTED_COLOR,
            tags=f"node_{nid}"
        )

        rl = data['risk_level']
        if rl and RISK_CONFIG[rl]['color']:
            dot_r = max(4, cs // 8)
            self.canvas.create_oval(
                x + cs - dot_r * 2 - 2, y + 2,
                x + cs - 2,             y + dot_r * 2 + 2,
                fill=RISK_CONFIG[rl]['color'], outline="",
                tags=f"node_{nid}"
            )

    def _render_edge(self, a, b):
        key = (min(a, b), max(a, b))
        if key in self.edge_items:
            self.canvas.delete(self.edge_items[key])
        g = self.graph
        cs = self._cell_size()
        pad = 16
        gap = self._gap_size()
        na, nb = g.G.nodes[a], g.G.nodes[b]
        x1 = pad + na['col'] * (cs + gap) + cs // 2
        y1 = pad + na['row'] * (cs + gap) + cs // 2
        x2 = pad + nb['col'] * (cs + gap) + cs // 2
        y2 = pad + nb['row'] * (cs + gap) + cs // 2
        data = g.get_edge(a, b)
        color = BLOCK_COLOR if data['is_blocked'] else "#4A90E2"
        width = 4 if data['is_blocked'] else 2
        item = self.canvas.create_line(x1, y1, x2, y2, fill=color, width=width, tags="edge")
        self.canvas.tag_lower("edge", "node")
        self.edge_items[key] = item

    # ── Interaction ───────────────────────────────────────────────────────────

    def _on_canvas_click(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        nid = self._hit_node(cx, cy)
        if nid is None:
            return
        mode = self.mode.get()

        if mode == "view":
            self._select_node(nid)

        elif mode == "place":
            btype = self.building_type.get()
            self.graph.set_location_type(nid, btype)
            self._render_node(nid)
            self._update_stats()
            self._set_status(f"placed {BUILDING_CONFIG[btype]['label']} at node {nid}")

        elif mode == "block":
            if self.block_first is None:
                self.block_first = nid
                self._select_node(nid)
                self._set_status(f"selected node {nid} — click adjacent node to block/unblock road")
            else:
                a, b = self.block_first, nid
                self.block_first = None
                self._deselect()
                try:
                    edge = self.graph.get_edge(a, b)
                    if edge['is_blocked']:
                        self.graph.unblock_road(a, b)
                        self._set_status(f"road {a}↔{b} unblocked")
                    else:
                        self.graph.block_road(a, b)
                        self._set_status(f"road {a}↔{b} blocked")
                    self._render_edge(a, b)
                    # also re-render neighbor nodes (effective cost changed)
                    self._render_node(a)
                    self._render_node(b)
                    self._update_stats()
                except KeyError:
                    self._set_status(f"nodes {a} and {b} are not adjacent — try again")

        elif mode == "risk":
            level = self.risk_level.get()
            self.graph.update_risk(nid, level)
            self._render_node(nid)
            # Re-render edges touching this node
            for nb_id in self.graph.get_neighbors(nid):
                self._render_edge(nid, nb_id)
            self._update_stats()
            self._set_status(f"node {nid} risk set to {level} (×{RISK_CONFIG[level]['mult']})")

    def _hit_node(self, cx, cy):
        cs = self._cell_size()
        pad = 16
        gap = self._gap_size()
        col = int((cx - pad) // (cs + gap))
        row = int((cy - pad) // (cs + gap))
        if 0 <= row < self.graph.rows and 0 <= col < self.graph.cols:
            # Check we're inside the cell (not in the gap)
            local_x = (cx - pad) % (cs + gap)
            local_y = (cy - pad) % (cs + gap)
            if local_x <= cs and local_y <= cs:
                return self.graph.node_id(row, col)
        return None

    def _select_node(self, nid):
        prev = self.selected_node
        self.selected_node = nid
        if prev is not None:
            self._render_node(prev)
        self._render_node(nid)
        data = self.graph.get_node(nid)
        btype = data['location_type']
        label = BUILDING_CONFIG[btype]['label'] if btype else "empty"
        nb = self.graph.get_neighbors(nid)
        blocked = sum(1 for n in nb if self.graph.get_edge(nid, n)['is_blocked'])
        self._set_status(
            f"node {nid}  ({data['row']}, {data['col']})  |  "
            f"type: {label}  |  risk: {data['risk_level'] or 'none'} "
            f"(×{data['risk_multiplier']:.1f})  |  "
            f"neighbors: {len(nb)}  blocked edges: {blocked}"
        )

    def _deselect(self):
        prev = self.selected_node
        self.selected_node = None
        if prev is not None:
            self._render_node(prev)

    def _on_mode_change(self):
        self.block_first = None
        self._deselect()
        self._set_status(f"mode: {self.mode.get()}")

    def _toggle_challenge(self, challenge_id):
        """Toggle the expanded/collapsed state of a challenge dropdown."""
        is_expanded = self.challenge_states.get(challenge_id, False)
        content_frame = self.challenge_frames[challenge_id]
        arrow_label = self.challenge_buttons[challenge_id]
        
        if is_expanded:
            # Collapse
            content_frame.pack_forget()
            arrow_label.config(text="▶")
            self.challenge_states[challenge_id] = False
        else:
            # Expand
            content_frame.pack(fill=tk.X, pady=(0, 5))
            arrow_label.config(text="▼")
            self.challenge_states[challenge_id] = True

    def _build_csp_content(self, parent_frame):
        """Build the content for Challenge 1 (CSP Layout)."""
        # Building count sliders
        self.csp_vars = {}
        self.csp_sliders = {}  # Store slider references for dynamic updates
        building_types = [
            ("Hospital", "hospital"),
            ("School", "school"), 
            ("Industrial", "industrial"),
            ("Residential", "residential"),
            ("Power Plant", "power_plant"),
            ("Ambulance Depot", "ambulance_depot")
        ]
        
        tk.Label(parent_frame, text="Building Counts", 
                font=("Courier", 8, "bold"), bg=PANEL_BG, fg=TEXT_COLOR).pack(anchor=tk.W, padx=10, pady=(5, 3))
        
        # Get current grid size
        grid_size = self.graph.rows * self.graph.cols if self.graph else 100
        
        for display_name, key in building_types:
            f = tk.Frame(parent_frame, bg=PANEL_BG)
            f.pack(fill=tk.X, padx=10, pady=1)
            
            tk.Label(f, text=display_name, font=("Courier", 8), 
                    bg=PANEL_BG, fg=MUTED_COLOR, width=12, anchor=tk.W).pack(side=tk.LEFT)
            
            var = tk.IntVar(value=1)
            self.csp_vars[key] = var
            
            # Dynamic slider with max based on grid size
            slider = tk.Scale(f, from_=0, to=grid_size, orient=tk.HORIZONTAL, variable=var,
                            length=100, font=("Courier", 7), bg=PANEL_BG, fg=TEXT_COLOR,
                            highlightthickness=0, troughcolor=PANEL_BG,
                            command=lambda x: self._update_csp_total())
            slider.pack(side=tk.RIGHT, padx=(5, 0))
            self.csp_sliders[key] = slider
        
        # Total buildings counter
        total_frame = tk.Frame(parent_frame, bg=PANEL_BG)
        total_frame.pack(fill=tk.X, padx=10, pady=(5, 3))
        
        tk.Label(total_frame, text="Total Buildings:", font=("Courier", 8, "bold"),
                bg=PANEL_BG, fg=TEXT_COLOR).pack(side=tk.LEFT)
        
        self.csp_total_label = tk.Label(total_frame, text="0/0", font=("Courier", 8, "bold"),
                                      bg=PANEL_BG, fg="#378ADD")
        self.csp_total_label.pack(side=tk.RIGHT)
        
        # Grid size info
        self.csp_grid_label = tk.Label(parent_frame, text=f"Grid Size: {self.graph.rows}×{self.graph.cols} = {grid_size}" if self.graph else "Grid Size: 0×0 = 0",
                                      font=("Courier", 7), bg=PANEL_BG, fg=MUTED_COLOR)
        self.csp_grid_label.pack(anchor=tk.W, padx=10, pady=(0, 5))
        
        # Execute button
        tk.Button(parent_frame, text="EXECUTE CSP", 
                 font=("Courier", 8, "bold"), bg="#378ADD", fg="white",
                 relief=tk.FLAT, command=self._execute_csp).pack(fill=tk.X, padx=10, pady=(8, 5))
        
        # Initialize total counter
        self._update_csp_total()

    def _update_csp_total(self):
        """Update the total buildings counter."""
        if hasattr(self, 'csp_vars'):
            total = sum(var.get() for var in self.csp_vars.values())
            grid_size = self.graph.rows * self.graph.cols if self.graph else 0
            self.csp_total_label.config(text=f"{total}/{grid_size}")
            
            # Color code the total
            if total == grid_size:
                self.csp_total_label.config(fg="#28a745")  # Green
            elif total > grid_size:
                self.csp_total_label.config(fg="#dc3545")  # Red
            else:
                self.csp_total_label.config(fg="#378ADD")  # Blue

    def _update_csp_sliders(self):
        """Update CSP sliders when grid size changes."""
        if hasattr(self, 'csp_sliders') and self.graph:
            grid_size = self.graph.rows * self.graph.cols
            
            # Update slider max values
            for slider in self.csp_sliders.values():
                slider.config(to=grid_size)
            
            # Update grid size label
            self.csp_grid_label.config(text=f"Grid Size: {self.graph.rows}×{self.graph.cols} = {grid_size}")
            
            # Update total counter
            self._update_csp_total()

    def _execute_csp(self):
        """Execute the CSP algorithm with current parameters."""
        try:
            # Import CSP modules here to avoid circular imports
            import sys
            import os
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Algorithms'))
            from Algorithms.CSP import CSPLayoutSolver, CSPConfig
            
            # Get building counts
            counts = {}
            total_buildings = 0
            for key, var in self.csp_vars.items():
                count = var.get()
                if count > 0:
                    # Convert UI keys to CSP format
                    csp_key = key.title() if key != "power_plant" else "PowerPlant"
                    if key == "ambulance_depot":
                        csp_key = "AmbulanceDepot"
                    counts[csp_key] = count
                    total_buildings += count
            
            # Check if total matches grid size
            grid_size = self.graph.rows * self.graph.cols
            if total_buildings != grid_size:
                messagebox.showwarning("Invalid Configuration", 
                    f"Total building count ({total_buildings}) must equal grid size ({grid_size})")
                return
            
            # Create CSP configuration
            config = CSPConfig(
                rows=self.graph.rows,
                cols=self.graph.cols,
                counts=counts,
                max_backtracks=50000
            )
            
            # Run CSP solver
            self._set_status("running CSP solver...")
            solver = CSPLayoutSolver(config)
            result = solver.solve()
            
            # Apply results to graph
            if result.success:
                self._apply_csp_result(result)
                self._set_status("CSP completed successfully!")
                messagebox.showinfo("Success", "CSP layout generated successfully!")
            else:
                self._apply_csp_result(result)
                self._set_status(f"CSP completed with {len(result.violations)} violations")
                violations_text = "\n".join(result.violations[:5])  # Show first 5 violations
                if len(result.violations) > 5:
                    violations_text += f"\n... and {len(result.violations) - 5} more"
                messagebox.showwarning("Partial Solution", 
                    f"CSP found a partial solution with {len(result.violations)} violations:\n\n{violations_text}")
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to execute CSP: {str(e)}")
            self._set_status("CSP execution failed")

    def _apply_csp_result(self, result):
        """Apply CSP result to the current graph."""
        # Update node types
        for node_id, location_type in result.assignment.items():
            self.graph.set_location_type(node_id, location_type.lower())
        
        # Update edge costs from CSP result
        for edge in result.graph.edges(data=True):
            a, b, data = edge
            if self.graph.G.has_edge(a, b):
                self.graph.G.edges[a, b]['base_cost'] = data['base_cost']
                self.graph.G.edges[a, b]['effective_cost'] = data['effective_cost']
        
        # Refresh display
        self._render()
        self._update_stats()

    def _set_status(self, msg):
        self.status_var.set(msg)

    def _update_stats(self):
        if not self.graph:
            return
        s = self.graph.stats()
        for key, lbl in self.stats_labels.items():
            lbl.config(text=str(s.get(key, 0)))

    # ── Public API for external extensions ───────────────────────────────────

    def get_graph(self):
        """Return the underlying CityGraph — use this for algorithms."""
        return self.graph

    def refresh(self):
        """Call after modifying graph externally to re-render everything."""
        self._render()
        self._update_stats()


def launch():
    root = tk.Tk()
    app = CityGraphUI(root)
    root.mainloop()


if __name__ == "__main__":
    launch()