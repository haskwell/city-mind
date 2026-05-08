import tkinter as tk
from tkinter import ttk
from challenges.c1_layout import run_layout, LocationType

# Color scheme for each location type
COLORS = {
    LocationType.EMPTY:           "#f0f0f0",  # light gray
    LocationType.RESIDENTIAL:     "#4CAF50",  # green
    LocationType.HOSPITAL:        "#F44336",  # red
    LocationType.SCHOOL:          "#2196F3",  # blue
    LocationType.INDUSTRIAL:      "#FF9800",  # orange
    LocationType.POWER_PLANT:     "#9C27B0",  # purple
    LocationType.AMBULANCE_DEPOT: "#00BCD4",  # cyan
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

class GridVisualizer:
    def __init__(self, grid):
        self.grid = grid
        self.cell_size = 60
        self.padding = 2
        
        self.root = tk.Tk()
        self.root.title("City Layout Planning - Challenge 1")
        self.root.configure(bg="#2c3e50")
        
        # Main container
        main_frame = tk.Frame(self.root, bg="#2c3e50", padx=20, pady=20)
        main_frame.pack()
        
        # Title
        title = tk.Label(
            main_frame, 
            text="City Layout", 
            font=("Helvetica", 24, "bold"),
            bg="#2c3e50",
            fg="white"
        )
        title.pack(pady=(0, 10))
        
        # Canvas for grid
        canvas_size = grid.size * self.cell_size + (grid.size + 1) * self.padding
        self.canvas = tk.Canvas(
            main_frame, 
            width=canvas_size, 
            height=canvas_size,
            bg="#34495e",
            highlightthickness=0
        )
        self.canvas.pack()
        
        # Legend frame
        legend_frame = tk.Frame(main_frame, bg="#2c3e50")
        legend_frame.pack(pady=(15, 0))
        
        # Create legend
        self._create_legend(legend_frame)
        
        # Status label
        self.status_label = tk.Label(
            main_frame,
            text="",
            font=("Helvetica", 12),
            bg="#2c3e50",
            fg="#ecf0f1"
        )
        self.status_label.pack(pady=(10, 0))
        
        # Draw the grid
        self.draw_grid()
        
        # Bind click events for cell info
        self.canvas.bind("<Button-1>", self.on_cell_click)
        
        # Hover effect
        self.canvas.bind("<Motion>", self.on_hover)
        self.hover_rect = None
        
    def _create_legend(self, parent):
        tk.Label(
            parent, 
            text="Legend:", 
            font=("Helvetica", 10, "bold"),
            bg="#2c3e50",
            fg="white"
        ).pack(anchor="w")
        
        legend_items = [
            (LocationType.RESIDENTIAL, "Residential"),
            (LocationType.HOSPITAL, "Hospital"),
            (LocationType.SCHOOL, "School"),
            (LocationType.INDUSTRIAL, "Industrial"),
            (LocationType.POWER_PLANT, "Power Plant"),
            (LocationType.AMBULANCE_DEPOT, "Ambulance Depot"),
            (LocationType.EMPTY, "Empty"),
        ]
        
        for lt, name in legend_items:
            row = tk.Frame(parent, bg="#2c3e50")
            row.pack(fill="x", pady=1)
            
            color_box = tk.Label(
                row, 
                text="   ", 
                bg=COLORS[lt],
                width=2,
                relief="solid",
                borderwidth=1
            )
            color_box.pack(side="left", padx=(0, 5))
            
            tk.Label(
                row,
                text=f"{LABELS[lt]} - {name}",
                font=("Helvetica", 9),
                bg="#2c3e50",
                fg="#bdc3c7"
            ).pack(side="left")
    
    def draw_grid(self):
        for row in range(self.grid.size):
            for col in range(self.grid.size):
                cell = self.grid.get_cell(row, col)
                self._draw_cell(row, col, cell)
                
    def _draw_cell(self, row, col, cell):
        x1 = col * self.cell_size + (col + 1) * self.padding
        y1 = row * self.cell_size + (row + 1) * self.padding
        x2 = x1 + self.cell_size
        y2 = y1 + self.cell_size
        
        color = COLORS.get(cell.location_type, "#7f8c8d")
        
        # Draw cell rectangle
        rect = self.canvas.create_rectangle(
            x1, y1, x2, y2,
            fill=color,
            outline="#2c3e50",
            width=2,
            tags=f"cell_{row}_{col}"
        )
        
        # Draw label
        label = LABELS.get(cell.location_type, "?")
        if label:
            self.canvas.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                text=label,
                font=("Helvetica", 16, "bold"),
                fill="white",
                tags=f"text_{row}_{col}"
            )
        
        # Store cell data for click handling
        self.canvas.itemconfig(rect, tags=(f"cell_{row}_{col}", str(id(cell))))
        
    def on_cell_click(self, event):
        col = event.x // (self.cell_size + self.padding)
        row = event.y // (self.cell_size + self.padding)
        
        if 0 <= row < self.grid.size and 0 <= col < self.grid.size:
            cell = self.grid.get_cell(row, col)
            info = (
                f"Cell ({row}, {col})\n"
                f"Type: {cell.location_type.value}\n"
                f"Population: {cell.population_density:.1f}\n"
                f"Risk Index: {cell.risk_index:.2f}"
            )
            self.status_label.config(text=info)
            
    def on_hover(self, event):
        col = event.x // (self.cell_size + self.padding)
        row = event.y // (self.cell_size + self.padding)
        
        if self.hover_rect:
            self.canvas.delete(self.hover_rect)
            self.hover_rect = None
            
        if 0 <= row < self.grid.size and 0 <= col < self.grid.size:
            x1 = col * self.cell_size + (col + 1) * self.padding
            y1 = row * self.cell_size + (row + 1) * self.padding
            x2 = x1 + self.cell_size
            y2 = y1 + self.cell_size
            
            self.hover_rect = self.canvas.create_rectangle(
                x1-2, y1-2, x2+2, y2+2,
                outline="#f1c40f",
                width=3
            )
            self.canvas.tag_lower(self.hover_rect)
            
    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    print("=== Challenge 1: City Layout Planning ===\n")

    grid, violations = run_layout(grid_size=8)

    if violations:
        print(f"\n[WARNING] Layout has {len(violations)} constraint violation(s):")
        for cell, rule in violations:
            print(f"  - Cell ({cell.row},{cell.col}) [{cell.location_type}] violates: {rule}")
    else:
        print("\n[OK] All constraints satisfied.")

    # Quick summary
    print("\nPlacement summary:")
    for lt in LocationType:
        count = len(list(grid.cells_of_type(lt)))
        if count:
            print(f"  {lt.value}: {count}")
    
    # Launch Tkinter window
    print("\nLaunching visualizer...")
    app = GridVisualizer(grid)
    app.run()