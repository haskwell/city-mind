from collections import deque
import random
from core.city_grid import Grid, LocationType
from scipy import stats

MAX_STEPS_PER_ATTEMPT = 500_000
MAX_ATTEMPTS = 20

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

def select_unassigned_variable(grid, domains, unassigned):
    return min(unassigned, key=lambda c: len(domains.get(c, [])))

def order_domain_values(cell, domain, grid, domains):
    random.shuffle(domain)
    return domain

def forward_check(grid, cell, domains, trail, remaining_counts):
    for neighbor in grid.get_cells_within_hops(cell.row, cell.col, 3):
        if neighbor.is_assigned():
            continue
        for val in domains[neighbor][:]:
            if remaining_counts.get(val, 0) <= 0:
                domains[neighbor].remove(val)
                trail.append((neighbor, val))
                continue
            neighbor.location_type = val
            if not check_all_constraints(grid, neighbor, domains):
                domains[neighbor].remove(val)
                trail.append((neighbor, val))
            neighbor.location_type = None
        if not domains[neighbor]:
            return False
    return True

# AC-3 (arc consistency)
def ac3(grid, domains, trail=None):
    queue = deque()
    for row in grid.cells:
        for cell in row:
            if cell.is_assigned():
                continue
            for neighbor in grid.get_cells_within_hops(cell.row, cell.col, 3):
                if neighbor is not cell and not neighbor.is_assigned():
                    queue.append((cell, neighbor))

    while queue:
        xi, xj = queue.popleft()
        if revise(xi, xj, domains, grid, trail):
            if len(domains[xi]) == 0:
                return False
            for neighbor in grid.get_cells_within_hops(xi.row, xi.col, 3):
                if neighbor is not xj and not neighbor.is_assigned():
                    queue.append((neighbor, xi))

    return True

def revise(xi, xj, domains, grid, trail=None):
    revised = False
    for x in domains.get(xi, [])[:]:
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
            if trail is not None:
                trail.append((xi, x))  # record what was pruned
            revised = True
    return revised

# Backtracking search
def backtrack(grid, domains, remaining_counts, unassigned, depth=0):
    stats.steps += 1
    stats.depth = depth
    stats.max_depth = max(stats.max_depth, depth)

    if stats.steps > MAX_STEPS_PER_ATTEMPT:
        return False

    if not unassigned:
        violations = identify_violated_constraints(grid)
        return len(violations) == 0

    cell = select_unassigned_variable(grid, domains, unassigned)

    ordered_values = order_domain_values(
        cell, list(domains.get(cell, [])), grid, domains
    )

    for value in ordered_values:
        if remaining_counts.get(value, 0) <= 0:
            continue

        # --- assign ---
        cell.location_type = value
        remaining_counts[value] -= 1
        unassigned.discard(cell)

        trail = []

        if remaining_counts[value] == 0:
            for c in unassigned:
                if value in domains.get(c, []):
                    domains[c].remove(value)
                    trail.append((c, value))

        if check_all_constraints(grid, cell, domains):
            if forward_check(grid, cell, domains, trail, remaining_counts):
                if backtrack(grid, domains, remaining_counts, unassigned, depth + 1):
                    return True

        for pruned_cell, pruned_val in trail:
            domains[pruned_cell].append(pruned_val)

        # --- undo ---
        cell.location_type = None
        remaining_counts[value] += 1
        unassigned.add(cell)

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
def find_farthest_hospital_from_depot(grid):
    """
    Find the hospital farthest from the ambulance depot using Manhattan distance.
    Returns the hospital cell or None if no hospital or depot exists.
    """
    hospitals = list(grid.cells_of_type(LocationType.HOSPITAL))
    depots = list(grid.cells_of_type(LocationType.AMBULANCE_DEPOT))
    
    if not hospitals or not depots:
        return None
    
    depot = depots[0]  # There should only be one depot
    farthest_hospital = None
    max_distance = -1
    
    for hospital in hospitals:
        # Calculate Manhattan distance
        distance = abs(hospital.row - depot.row) + abs(hospital.col - depot.col)
        
        if distance > max_distance:
            max_distance = distance
            farthest_hospital = hospital
    
    return farthest_hospital

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


def run_layout(grid_size, required_counts):
    if required_counts is None:
        raise ValueError("required_counts must come from UI")

    total_cells = grid_size * grid_size
    used = sum(required_counts.values())

    if used > total_cells:
        raise ValueError(f"Too many buildings ({used}) for grid size {total_cells}")

    grid = Grid(grid_size)
    remaining_counts = {}
    remaining_counts[LocationType.HOSPITAL] = required_counts.get(LocationType.HOSPITAL, 0)
    remaining_counts[LocationType.AMBULANCE_DEPOT] = required_counts.get(LocationType.AMBULANCE_DEPOT, 0)
    remaining_counts[LocationType.SCHOOL] = required_counts.get(LocationType.SCHOOL, 0)
    remaining_counts[LocationType.INDUSTRIAL] = required_counts.get(LocationType.INDUSTRIAL, 0)
    remaining_counts[LocationType.POWER_PLANT] = required_counts.get(LocationType.POWER_PLANT, 0)
    remaining_counts[LocationType.RESIDENTIAL] = required_counts.get(LocationType.RESIDENTIAL, 0)
    remaining_counts[LocationType.EMPTY] = total_cells - used

    for attempt in range(MAX_ATTEMPTS):
        print(f"[C1] Attempt {attempt + 1}/{MAX_ATTEMPTS} with backtracking...")
        stats.steps = 0
        grid = Grid(grid_size)
        domains = {
            cell: [lt for lt, cnt in remaining_counts.items() 
                if cnt > 0 and lt != LocationType.EMPTY]
            for row in grid.cells for cell in row
        }
        if not ac3(grid, domains):
            break
        unassigned = {cell for row in grid.cells for cell in row}
        rc = dict(remaining_counts)  # fresh copy each attempt
        
        if backtrack(grid, domains, rc, unassigned):
            for row in grid.cells:
                for cell in row:
                    if not cell.is_assigned():
                        cell.location_type = LocationType.EMPTY
            assign_simulation_properties(grid)
            farthest = find_farthest_hospital_from_depot(grid)
            if farthest:
                farthest.location_type = LocationType.PRIMARY_HOSPITAL
            return grid, []
        
        if stats.steps < MAX_STEPS_PER_ATTEMPT:
            break  # genuinely no solution, not just bad luck
    
    grid, violations = minimum_conflict_layout(grid, required_counts)
    assign_simulation_properties(grid)
    return grid, violations