from enum import Enum
from collections import deque

# Location types
class LocationType(Enum):
    EMPTY       = "EMPTY"
    RESIDENTIAL = "RESIDENTIAL"
    HOSPITAL    = "HOSPITAL"
    PRIMARY_HOSPITAL = "PRIMARY_HOSPITAL"
    SCHOOL      = "SCHOOL"
    INDUSTRIAL  = "INDUSTRIAL"
    POWER_PLANT = "POWER_PLANT"
    AMBULANCE_DEPOT = "AMBULANCE_DEPOT"

# Grid cell
class Cell:
    def __init__(self, row, col):
        self.row = row
        self.col = col
        self.location_type = None          # assigned by CSP
        self.population_density = 0.0      # set after assignment
        self.risk_index = 0.0              # set after assignment
        self.accessible = True

    def is_assigned(self):
        return self.location_type is not None

    def __repr__(self):
        lt = self.location_type.value if self.location_type else "?"
        return f"Cell({self.row},{self.col},{lt})"

# Grid
class Grid:
    def __init__(self, size):
        self.size = size
        self.cells = [[Cell(r, c) for c in range(size)] for r in range(size)]
        self._hop_cache = {}   # (row, col, hops) -> list[Cell]
        self._precompute_hops(max_hops=3)

    def _precompute_hops(self, max_hops):
        for r in range(self.size):
            for c in range(self.size):
                for h in range(1, max_hops + 1):
                    self._hop_cache[(r, c, h)] = self._bfs_hops(r, c, h)

    def _bfs_hops(self, row, col, hops):
        start = self.get_cell(row, col)
        if start is None:
            return []
        visited = set()
        queue = deque()
        result = []
        queue.append((start, 0))
        visited.add((start.row, start.col))
        while queue:
            current, distance = queue.popleft()
            result.append(current)
            if distance >= hops:
                continue
            for neighbor in self.get_neighbors(current.row, current.col):
                pos = (neighbor.row, neighbor.col)
                if pos not in visited:
                    visited.add(pos)
                    queue.append((neighbor, distance + 1))
        return result

    def get_cells_within_hops(self, row, col, hops):
        return self._hop_cache.get((row, col, hops), [])

    def get_cell(self, row, col):
        if 0 <= row < self.size and 0 <= col < self.size:
            return self.cells[row][col]
        return None

    def get_neighbors(self, row, col):
        neighbors = [
            self.get_cell(row - 1, col),  # up
            self.get_cell(row + 1, col),  # down
            self.get_cell(row, col - 1),  # left
            self.get_cell(row, col + 1),  # right
        ]

        return [n for n in neighbors if n is not None]

    def unassigned_cells(self):
        for row in self.cells:
            for cell in row:
                if not cell.is_assigned():
                    yield cell

    def assigned_cells(self):
        for row in self.cells:
            for cell in row:
                if cell.is_assigned():
                    yield cell

    def cells_of_type(self, location_type):
        for cell in self.assigned_cells():
            if cell.location_type == location_type:
                yield cell

    def display(self):

        symbols = {
            LocationType.EMPTY: ".",
            LocationType.RESIDENTIAL: "R",
            LocationType.HOSPITAL: "H",
            LocationType.SCHOOL: "S",
            LocationType.INDUSTRIAL: "I",
            LocationType.POWER_PLANT: "P",
            LocationType.AMBULANCE_DEPOT: "A"
        }

        for row in self.cells:
            print(" ".join(
                symbols.get(cell.location_type, "?")
                for cell in row
            ))

    def __repr__(self):
        return f"Grid(size={self.size})"
