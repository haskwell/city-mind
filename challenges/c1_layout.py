"""
Challenge 1: City Layout Planning
----------------------------------
Uses CSP with Backtracking + MAC (AC-3) to assign location types to grid cells.

Input  : grid size (N), counts of each location type to place
Output : a filled Grid object where every cell has an assigned LocationType

Run from terminal:
    python c1_layout.py
"""

from enum import Enum
from collections import deque

# Location types
class LocationType(Enum):
    EMPTY       = "EMPTY"
    RESIDENTIAL = "RESIDENTIAL"
    HOSPITAL    = "HOSPITAL"
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

    def get_cells_within_hops(self, row, col, hops):
        start = self.get_cell(row, col)

        if start is None:
            return []

        visited = set()
        queue = deque()
        result = []

        # (cell, distance)
        queue.append((start, 0))
        visited.add((start.row, start.col))

        while queue:
            current, distance = queue.popleft()

            result.append(current)

            # stop expanding beyond hop limit
            if distance >= hops:
                continue

            for neighbor in self.get_neighbors(current.row, current.col):

                pos = (neighbor.row, neighbor.col)

                if pos not in visited:
                    visited.add(pos)
                    queue.append((neighbor, distance + 1))

        return result

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


# Constraint definitions
def constraint_industrial_not_adjacent_to_hospital_or_school(grid, cell):

    if not cell.is_assigned():
        return True

    for neighbor in grid.get_neighbors(cell.row, cell.col):
        if neighbor.is_assigned():

            # industrial next to hospital/school
            if (
                cell.location_type == LocationType.INDUSTRIAL and
                neighbor.location_type in [LocationType.HOSPITAL, LocationType.SCHOOL]
            ):
                return False

            # hospital/school next to industrial
            if (
                neighbor.location_type == LocationType.INDUSTRIAL and
                cell.location_type in [LocationType.HOSPITAL, LocationType.SCHOOL]
            ):
                return False

    return True

def constraint_residential_within_3_hops_of_hospital(grid, cell, domains=None):
    # Check this cell if it is residential
    if cell.location_type == LocationType.RESIDENTIAL:
        nearby = grid.get_cells_within_hops(cell.row, cell.col, 3)
        if any(n.location_type == LocationType.HOSPITAL for n in nearby):
            return True
        # No hospital yet — check if one can still be placed nearby
        if domains is not None:
            for n in nearby:
                if n is cell or n.is_assigned():
                    continue
                if LocationType.HOSPITAL in domains.get(n, []):
                    return True   # defer: a neighbour can still become a hospital
            return False  # no candidate left
        else:
            return False  # STRICT final validation

    # If we placed a non-hospital cell, check nearby residential cells
    # that might now have lost their only possible hospital placement
    if cell.location_type != LocationType.HOSPITAL and cell.is_assigned():
        nearby = grid.get_cells_within_hops(cell.row, cell.col, 3)
        for n in nearby:
            if n is cell:
                continue
            if n.location_type == LocationType.RESIDENTIAL:
                n_nearby = grid.get_cells_within_hops(n.row, n.col, 3)
                has_hospital = any(h.location_type == LocationType.HOSPITAL for h in n_nearby)
                if has_hospital:
                    continue
                # No hospital nearby for this residential — can we still place one?
                if domains is not None:
                    can_place = False
                    for h_candidate in n_nearby:
                        if h_candidate.is_assigned():
                            continue
                        if LocationType.HOSPITAL in domains.get(h_candidate, []):
                            can_place = True
                            break
                    if not can_place:
                        return False
                else:
                    return False  # STRICT final validation
    return True

def constraint_power_plant_within_2_hops_of_industrial(grid, cell, domains=None):
    # Check this cell if it is a power plant
    if cell.location_type == LocationType.POWER_PLANT:
        nearby = grid.get_cells_within_hops(cell.row, cell.col, 2)
        if any(n.location_type == LocationType.INDUSTRIAL for n in nearby):
            return True
        if domains is not None:
            for n in nearby:
                if n is cell or n.is_assigned():
                    continue
                if LocationType.INDUSTRIAL in domains.get(n, []):
                    return True
            return False
        else:
            return False  # STRICT final validation

    # If we placed a non-industrial cell, check nearby power plants
    if cell.location_type != LocationType.INDUSTRIAL and cell.is_assigned():
        nearby = grid.get_cells_within_hops(cell.row, cell.col, 2)
        for n in nearby:
            if n is cell:
                continue
            if n.location_type == LocationType.POWER_PLANT:
                n_nearby = grid.get_cells_within_hops(n.row, n.col, 2)
                has_industrial = any(i.location_type == LocationType.INDUSTRIAL for i in n_nearby)
                if has_industrial:
                    continue
                if domains is not None:
                    can_place = False
                    for i_candidate in n_nearby:
                        if i_candidate.is_assigned():
                            continue
                        if LocationType.INDUSTRIAL in domains.get(i_candidate, []):
                            can_place = True
                            break
                    if not can_place:
                        return False
                else:
                    return False  # STRICT final validation
    return True

def check_all_constraints(grid, cell, domains=None):
    return (
        constraint_industrial_not_adjacent_to_hospital_or_school(grid, cell) and
        constraint_residential_within_3_hops_of_hospital(grid, cell, domains) and
        constraint_power_plant_within_2_hops_of_industrial(grid, cell, domains)
    )

def identify_violated_constraints(grid):

    violations = []

    for row in grid.cells:
        for cell in row:

            if not cell.is_assigned():
                continue

            # check each constraint individually
            if not constraint_industrial_not_adjacent_to_hospital_or_school(grid, cell):
                violations.append((cell, "INDUSTRIAL_ADJACENCY"))

            if not constraint_residential_within_3_hops_of_hospital(grid, cell):
                violations.append((cell, "RESIDENTIAL_HOSPITAL_DISTANCE"))

            if not constraint_power_plant_within_2_hops_of_industrial(grid, cell):
                violations.append((cell, "POWERPLANT_INDUSTRIAL_DISTANCE"))

    return violations


# CSP helpers
def get_domain(cell, remaining_counts):
    if cell.is_assigned():
        return []
    return [lt for lt, count in remaining_counts.items() if count > 0]

def select_unassigned_variable(grid, domains):

    best_cell = None
    min_size = float('inf')

    for cell in grid.unassigned_cells():

        domain_size = len(domains.get(cell, []))

        if domain_size < min_size:
            min_size = domain_size
            best_cell = cell

    return best_cell

def order_domain_values(cell, domain, grid, domains):
    def count_eliminations(value):
        eliminations = 0
        cell.location_type = value
        try:
            affected: set = set()
            for nearby in grid.get_cells_within_hops(cell.row, cell.col, 3):
                if nearby is not cell:
                    affected.add(nearby)

            for affected_cell in affected:
                if affected_cell.is_assigned():
                    continue
                for candidate_value in domains.get(affected_cell, []):
                    try:
                        affected_cell.location_type = candidate_value
                        if not check_all_constraints(grid, affected_cell, domains):
                            eliminations += 1
                    finally:
                        affected_cell.location_type = None   # always undo
        finally:
            cell.location_type = None                        # always undo cell

        return eliminations

    return sorted(domain, key=count_eliminations)


# AC-3 (arc consistency)
def ac3(grid, domains):
    queue = deque()
    for row in grid.cells:
        for cell in row:
            if cell.is_assigned():
                continue
            for neighbor in grid.get_neighbors(cell.row, cell.col):
                if not neighbor.is_assigned():
                    queue.append((cell, neighbor))

    while queue:
        xi, xj = queue.popleft()
        if revise(xi, xj, domains, grid):
            if len(domains[xi]) == 0:
                return False
            for neighbor in grid.get_neighbors(xi.row, xi.col):
                if neighbor != xj and not neighbor.is_assigned():
                    queue.append((neighbor, xi))

    return True

def revise(xi, xj, domains, grid):
    revised = False
    for x in domains.get(xi, [])[:]:   # iterate over a copy
        xi.location_type = x
        satisfies = False
        for y in domains.get(xj, []):
            xj.location_type = y
            if check_all_constraints(grid, xi, domains) and check_all_constraints(grid, xj, domains):
                satisfies = True
                break
        xi.location_type = None
        xj.location_type = None
        if not satisfies:
            domains[xi].remove(x)
            revised = True
    return revised

# Backtracking search
def backtrack(grid, domains, remaining_counts):
    # Base case: every cell has been assigned
    if next(grid.unassigned_cells(), None) is None:
        return True

    cell = select_unassigned_variable(grid, domains)
    if cell is None:
        return True

    # Snapshot the domain list before LCV ordering (ordering may mutate state)
    ordered_values = order_domain_values(
        cell, list(domains.get(cell, [])), grid, domains
    )

    for value in ordered_values:
        if remaining_counts.get(value, 0) <= 0:
            continue

        # --- assign ---
        cell.location_type = value
        remaining_counts[value] -= 1

        if check_all_constraints(grid, cell, domains):
            # Deep-copy domains so we can restore on backtrack
            saved_domains = {c: list(v) for c, v in domains.items()}

            if ac3(grid, domains):
                if backtrack(grid, domains, remaining_counts):
                    return True

            # Restore pruned domains
            domains.clear()
            domains.update(saved_domains)

        # --- undo ---
        cell.location_type = None
        remaining_counts[value] += 1

    return False


# Minimum conflict fallback
def minimum_conflict_layout(grid, required_counts):
    import random

    # Clear any partial assignments left by backtracking
    for row in grid.cells:
        for cell in row:
            cell.location_type = None

    all_cells = [cell for row in grid.cells for cell in row]
    random.shuffle(all_cells)

    idx = 0
    for lt, count in required_counts.items():
        for _ in range(count):
            if idx >= len(all_cells):
                break
            all_cells[idx].location_type = lt
            idx += 1

    # Fill remaining cells with EMPTY
    while idx < len(all_cells):
        all_cells[idx].location_type = LocationType.EMPTY
        idx += 1

    violations = identify_violated_constraints(grid)

    print(f"[C1] Fallback layout complete — {len(violations)} violation(s).")
    if violations:
        by_rule: dict = {}
        for vcell, rule in violations:
            by_rule.setdefault(rule, []).append(vcell)
        for rule, cells in by_rule.items():
            coords = [(c.row, c.col) for c in cells]
            print(f"  {rule}: {len(cells)} cell(s) at {coords}")

    return grid, violations


# Post-assignment: fill in simulation properties
def assign_simulation_properties(grid):
    import random

    # (density_min, density_max, risk_index)
    props = {
        LocationType.EMPTY:           (0,    0,    0.00),
        LocationType.RESIDENTIAL:     (50,   200,  0.30),
        LocationType.HOSPITAL:        (50,   50,   0.10),
        LocationType.SCHOOL:          (30,   150,  0.15),
        LocationType.INDUSTRIAL:      (100,  500,  0.60),
        LocationType.POWER_PLANT:     (20,   50,   0.70),
        LocationType.AMBULANCE_DEPOT: (10,   30,   0.05),
    }

    for row in grid.cells:
        for cell in row:
            if cell.location_type is None:
                continue
            lo, hi, risk = props.get(cell.location_type, (0, 0, 0.0))
            cell.population_density = float(random.randint(lo, hi)) if lo != hi else float(lo)
            cell.risk_index = risk


# Main entry point
def run_layout(grid_size=8, required_counts=None):
    if required_counts is None:
        required_counts = {
            LocationType.RESIDENTIAL:    40,  # majority
            LocationType.HOSPITAL:        8,
            LocationType.SCHOOL:          5,
            LocationType.INDUSTRIAL:      5,
            LocationType.POWER_PLANT:     3,
            LocationType.AMBULANCE_DEPOT: 3,
        }

    grid = Grid(grid_size)

    # EMPTY fills whatever cells remain after the required types are placed
    total_cells = grid_size * grid_size
    remaining_counts = dict(required_counts)
    remaining_counts[LocationType.EMPTY] = total_cells - sum(required_counts.values())

    # Every unassigned cell starts with all types that still have quota
    domains = {
        cell: [lt for lt, cnt in remaining_counts.items() if cnt > 0]
        for row in grid.cells
        for cell in row
    }

    success = backtrack(grid, domains, remaining_counts)

    if success:
        violations = []
    else:
        print("[C1] Backtracking could not find a perfect layout.")
        print("[C1] Falling back to minimum-conflict placement...")
        grid, violations = minimum_conflict_layout(grid, required_counts)

    assign_simulation_properties(grid)
    return grid, violations
