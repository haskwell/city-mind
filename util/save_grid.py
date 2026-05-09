import json
from core.city_grid import Grid, LocationType

def save_grid(grid, filepath="saved_grid.json"):
    data = []
    for r in range(grid.size):
        for c in range(grid.size):
            cell = grid.get_cell(r, c)
            data.append({
                "row": r,
                "col": c,
                "location_type": cell.location_type.value if cell.location_type else None,
                "population_density": cell.population_density,
                "risk_index": cell.risk_index,
                "accessible": cell.accessible
            })
    with open(filepath, "w") as f:
        json.dump({"size": grid.size, "cells": data}, f, indent=2)
    print(f"[C1] Grid saved to {filepath}")


def load_grid(filepath="saved_grid.json"):
    with open(filepath, "r") as f:
        data = json.load(f)
    
    grid = Grid(data["size"])
    type_map = {lt.value: lt for lt in LocationType}
    
    for cell_data in data["cells"]:
        cell = grid.get_cell(cell_data["row"], cell_data["col"])
        cell.location_type = type_map.get(cell_data["location_type"])
        cell.population_density = cell_data["population_density"]
        cell.risk_index = cell_data["risk_index"]
        cell.accessible = cell_data["accessible"]
    
    print(f"[C1] Grid loaded from {filepath}")
    return grid
