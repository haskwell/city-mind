import tkinter as tk

from scipy import stats
from challenges.c1_layout import run_layout, LocationType
import threading

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


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("City Layout CSP Planner")

        self.cell_size = 55

        # ---------------- LEFT PANEL
        self.left = tk.Frame(self.root, padx=10, pady=10)
        self.left.pack(side="left", fill="y")

        tk.Label(self.left, text="CSP Controls", font=("Arial", 14, "bold")).pack(pady=10)

        self.grid_size_var = tk.IntVar(value=8)

        tk.Label(self.left, text="Grid Size").pack()
        self.grid_spin = tk.Spinbox(self.left, from_=4, to=20, textvariable=self.grid_size_var, command=self.update_total)
        self.grid_spin.pack()

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
            frame.pack(fill="x", pady=2)

            tk.Label(frame, text=lt.value, width=18, anchor="w").pack(side="left")

            spin = tk.Spinbox(
                frame,
                from_=0,
                to=200,
                textvariable=var,
                width=5,
                command=self.update_total
            )
            spin.pack(side="right")

            # update on manual typing too
            var.trace_add("write", lambda *args: self.update_total())

        # ---------------- TOTAL DISPLAY
        self.total_label = tk.Label(self.left, text="", font=("Arial", 12, "bold"))
        self.total_label.pack(pady=10)

        # ---------------- RUN BUTTON
        self.run_btn = tk.Button(
            self.left,
            text="Run CSP",
            bg="#2ecc71",
            fg="white",
            command=self.run_csp
        )
        self.run_btn.pack(fill="x", pady=10)

        self.status = tk.Label(self.left, text="")
        self.status.pack()

        # ---------------- RIGHT PANEL
        self.right = tk.Frame(self.root)
        self.right.pack(side="right", fill="both", expand=True)

        self.canvas = tk.Canvas(self.right, bg="#34495e")
        self.canvas.pack(fill="both", expand=True)

        self.progress_label = tk.Label(self.left, text="Idle", fg="blue")
        self.progress_label.pack(pady=5)

        self.step_label = tk.Label(self.left, text="Steps: 0")
        self.step_label.pack()

        self.depth_label = tk.Label(self.left, text="Depth: 0")
        self.depth_label.pack()

        self.update_total()

    def update_progress_ui(self):
        self.step_label.config(text=f"Steps: {stats.steps}")
        self.depth_label.config(text=f"Depth: {stats.depth} / Max {stats.max_depth}")

        if hasattr(self, "running") and self.running:
            self.root.after(100, self.update_progress_ui)

    # ---------------- TOTAL VALIDATION
    def update_total(self):
        size = self.grid_size_var.get()
        capacity = size * size

        total = sum(var.get() for var in self.count_vars.values())

        self.total_label.config(text=f"Total: {total} / {capacity}")

        if total > capacity:
            self.total_label.config(fg="red")
            self.run_btn.config(state="disabled")
        else:
            self.total_label.config(fg="green")
            self.run_btn.config(state="normal")

    # ---------------- RUN CSP
    def run_csp(self):
        self.run_btn.config(state="disabled")
        self.running = True

        # reset stats
        stats.steps = 0
        stats.depth = 0
        stats.max_depth = 0

        self.progress_label.config(text="Starting CSP...")

        def worker():
            size = self.grid_size_var.get()

            required_counts = {
                lt: var.get()
                for lt, var in self.count_vars.items()
            }

            grid, violations = run_layout(size, required_counts)

            self.root.after(0, lambda: self.finish_csp(grid, violations))

        threading.Thread(target=worker, daemon=True).start()

        self.update_progress_ui()

    def finish_csp(self, grid, violations):
        self.running = False
        self.grid = grid
        self.draw_grid()

        if violations:
            self.progress_label.config(text="Finished with violations")
        else:
            self.progress_label.config(text="Solved successfully")

        self.run_btn.config(state="normal")

    # ---------------- DRAW GRID
    def draw_grid(self):
        self.canvas.delete("all")

        size = self.grid.size
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

                color = COLORS.get(cell.location_type, "#7f8c8d")
                label = LABELS.get(cell.location_type, "?")

                self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="black")

                if label:
                    self.canvas.create_text(
                        (x1 + x2) / 2,
                        (y1 + y2) / 2,
                        text=label,
                        fill="white",
                        font=("Arial", 14, "bold")
                    )

    def run(self):
        self.root.mainloop()