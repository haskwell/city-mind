import math
import random
import networkx as nx
from dataclasses import dataclass, field
from typing import Optional
@dataclass
class CSPConfig:
    """
    All configuration needed to run the CSP layout solver.

    Args:
        rows:               Number of grid rows
        cols:               Number of grid columns
        counts:             How many of each location type to place.
                            Must sum to rows * cols.
                            Example:
                                {
                                    'Hospital':       2,
                                    'AmbulanceDepot': 1,
                                    'School':         3,
                                    'Industrial':     3,
                                    'PowerPlant':     2,
                                    'Residential':    89,
                                }
        max_backtracks:     Safety limit to avoid infinite loops (default 50000)
        random_seed:        Optional seed for reproducible results
    """
    rows: int
    cols: int
    counts: dict[str, int]
    max_backtracks: int = 50_000
    random_seed: Optional[int] = None


@dataclass
class CSPResult:
    """
    Everything the CSP solver gives back after solving.

    Attributes:
        assignment:         dict mapping node_id → location_type for every cell
        graph:              The populated NetworkX graph (nodes have location_type set,
                            edges have base_cost set: 0.8 if either node is Residential,
                            1.0 otherwise)
        success:            True  → perfect solution found (all constraints satisfied)
                            False → best minimum-conflict layout returned instead
        violations:         List of human-readable constraint violations in the result
                            (empty if success=True)
        conflict_cause:     If success=False, which constraint made it impossible
                            (None if success=True)
        stats:              Internal stats: backtracks used, nodes visited, etc.
    """
    assignment: dict[int, str]
    graph: nx.Graph
    success: bool
    violations: list[str]
    conflict_cause: Optional[str]
    stats: dict
    

class CSPLayoutSolver:
    """
    Solves the CityMind grid layout problem as a Constraint Satisfaction Problem.

    Usage:
        config = CSPConfig(rows=10, cols=10, counts={...})
        solver = CSPLayoutSolver(config)
        result = solver.solve()   # <-- one line, returns CSPResult

    The solver:
        1. Builds a NetworkX grid graph
        2. Runs Backtracking + MAC (AC-3) with MRV + LCV heuristics
        3. If no perfect solution exists, identifies the culprit constraint
           and falls back to a minimum-conflict greedy repair
        4. After assignment, sets edge base_cost (0.8 residential, 1.0 otherwise)
        5. Returns a CSPResult — the graph is ready for Challenge 2 immediately
    """

    # Constraint tags (used in conflict identification)
    _C_INDUSTRIAL_SEP  = "industrial_separation"      # Industrial ≠ adjacent Hospital/School
    _C_RESIDENTIAL_HOP = "residential_hospital_3hop"  # Residential within 3 hops of Hospital
    _C_POWERPLANT_HOP  = "powerplant_industrial_2hop" # PowerPlant within 2 hops of Industrial

    def __init__(self, config: CSPConfig):
        self._cfg   = config
        self._G     = nx.Graph()
        self._stats = {"backtracks": 0, "nodes_visited": 0}
        
        if config.random_seed is not None:
            random.seed(config.random_seed)

        total_cells = config.rows * config.cols
        total_counts = sum(config.counts.values())
        if total_counts != total_cells:
            raise ValueError(
                f"counts sum to {total_counts} but grid has {total_cells} cells "
                f"({config.rows}×{config.cols}). They must match exactly."
            )
        
        self._build_empty_grid()

    # ------------------------------------------------------------------ #
    #  PUBLIC API                                                          #
    # ------------------------------------------------------------------ #

    def solve(self) -> CSPResult:
        """Run the solver. Returns a fully populated CSPResult."""
        domains    = {n: list(self._cfg.counts.keys()) for n in self._G.nodes()}
        remaining  = dict(self._cfg.counts)
        assignment: dict[int, str] = {}

        solution = self._backtrack(assignment, domains, remaining)

        if solution is not None:
            self._apply_assignment(solution)
            self._set_edge_costs()
            return CSPResult(
                assignment     = solution,
                graph          = self._G,
                success        = True,
                violations     = [],
                conflict_cause = None,
                stats          = dict(self._stats),
            )

        # No perfect solution — identify which constraint is the culprit
        culprit = self._identify_conflict()

        # Fall back to minimum-conflict repair
        mc_assignment = self._minimum_conflict_layout()
        violations    = self._collect_violations(mc_assignment)
        self._apply_assignment(mc_assignment)
        self._set_edge_costs()

        return CSPResult(
            assignment     = mc_assignment,
            graph          = self._G,
            success        = False,
            violations     = violations,
            conflict_cause = culprit,
            stats          = dict(self._stats),
        )

    # ------------------------------------------------------------------ #
    #  GRID CONSTRUCTION                                                   #
    # ------------------------------------------------------------------ #

    def _node_id(self, row: int, col: int) -> int:
        return row * self._cfg.cols + col

    def _build_empty_grid(self):
        rows, cols = self._cfg.rows, self._cfg.cols
        for r in range(rows):
            for c in range(cols):
                nid = self._node_id(r, c)
                self._G.add_node(nid, row=r, col=c, location_type=None)

        for r in range(rows):
            for c in range(cols):
                nid = self._node_id(r, c)
                if c + 1 < cols:
                    self._G.add_edge(nid, self._node_id(r, c + 1),
                                     base_cost=1.0, is_blocked=False, effective_cost=1.0)
                if r + 1 < rows:
                    self._G.add_edge(nid, self._node_id(r + 1, c),
                                     base_cost=1.0, is_blocked=False, effective_cost=1.0)

    def _apply_assignment(self, assignment: dict[int, str]):
        for nid, loc_type in assignment.items():
            self._G.nodes[nid]['location_type'] = loc_type

    def _set_edge_costs(self):
        """
        After assignment, update base_cost on every edge.
        Residential neighbour → 0.8, otherwise 1.0.
        """
        for a, b in self._G.edges():
            ta = self._G.nodes[a]['location_type']
            tb = self._G.nodes[b]['location_type']
            cost = 0.8 if (ta == 'Residential' or tb == 'Residential') else 1.0
            self._G.edges[a, b]['base_cost']      = cost
            self._G.edges[a, b]['effective_cost'] = cost

    # ------------------------------------------------------------------ #
    #  CONSTRAINT CHECKS                                                   #
    # ------------------------------------------------------------------ #

    def _is_consistent(self, node_id: int, loc_type: str,
                       assignment: dict[int, str]) -> bool:
        """Return True iff assigning loc_type to node_id violates no constraint."""
        return (
            self._check_industrial_sep(node_id, loc_type, assignment)
            and self._check_residential_hop(node_id, loc_type, assignment)
            and self._check_powerplant_hop(node_id, loc_type, assignment)
        )

    def _check_industrial_sep(self, node_id: int, loc_type: str,
                              assignment: dict[int, str]) -> bool:
        """Industrial cannot be adjacent to Hospital or School and vice versa."""
        bad_pairs = {('Industrial', 'Hospital'), ('Industrial', 'School'),
                     ('Hospital', 'Industrial'), ('School', 'Industrial')}
        for nb in self._G.neighbors(node_id):
            nb_type = assignment.get(nb)
            if nb_type and (loc_type, nb_type) in bad_pairs:
                return False
        return True

    def _check_residential_hop(self, node_id: int, loc_type: str,
                               assignment: dict[int, str]) -> bool:
        """
        When placing Residential, there must be a Hospital within 3 hops
        already placed — OR enough unassigned nodes within 3 hops that could
        still become a Hospital later (optimistic check, lets backtracking proceed).
        """
        if loc_type != 'Residential':
            return True

        # Check if a Hospital already exists within 3 hops
        for other_id, other_type in assignment.items():
            if other_type == 'Hospital':
                try:
                    if nx.shortest_path_length(self._G, node_id, other_id) <= 3:
                        return True
                except nx.NetworkXNoPath:
                    pass

        # Optimistic: are there unassigned nodes within 3 hops?
        # (Hospitals might still be placed there → don't prune yet)
        for other_id in self._G.nodes():
            if other_id not in assignment:
                try:
                    if nx.shortest_path_length(self._G, node_id, other_id) <= 3:
                        return True  # still possible
                except nx.NetworkXNoPath:
                    pass

        return False

    def _check_powerplant_hop(self, node_id: int, loc_type: str,
                              assignment: dict[int, str]) -> bool:
        """
        When placing PowerPlant, there must be an Industrial within 2 hops
        already placed — OR unassigned nodes within 2 hops (optimistic).
        """
        if loc_type != 'PowerPlant':
            return True

        for other_id, other_type in assignment.items():
            if other_type == 'Industrial':
                try:
                    if nx.shortest_path_length(self._G, node_id, other_id) <= 2:
                        return True
                except nx.NetworkXNoPath:
                    pass

        for other_id in self._G.nodes():
            if other_id not in assignment:
                try:
                    if nx.shortest_path_length(self._G, node_id, other_id) <= 2:
                        return True
                except nx.NetworkXNoPath:
                    pass

        return False

    # ------------------------------------------------------------------ #
    #  BACKTRACKING CORE                                                   #
    # ------------------------------------------------------------------ #

    def _backtrack(self, assignment: dict[int, str],
                   domains: dict[int, list[str]],
                   remaining: dict[int, int]) -> Optional[dict[int, str]]:

        if len(assignment) == len(self._G.nodes()):
            return assignment

        if self._stats["backtracks"] >= self._cfg.max_backtracks:
            return None

        node_id = self._mrv_select(assignment, domains)
        self._stats["nodes_visited"] += 1

        for loc_type in self._lcv_order(node_id, assignment, domains, remaining):
            if remaining.get(loc_type, 0) == 0:
                continue
            if not self._is_consistent(node_id, loc_type, assignment):
                continue

            # Tentatively assign
            assignment[node_id] = loc_type
            remaining[loc_type] -= 1

            # MAC: forward-check via AC-3 and collect pruned values
            domains_copy = {k: list(v) for k, v in domains.items()}
            pruned_ok = self._mac_ac3(node_id, loc_type, assignment, domains_copy)

            if pruned_ok:
                result = self._backtrack(assignment, domains_copy, remaining)
                if result is not None:
                    return result

            # Undo
            del assignment[node_id]
            remaining[loc_type] += 1
            self._stats["backtracks"] += 1

        return None

    # ------------------------------------------------------------------ #
    #  MRV & LCV HEURISTICS                                               #
    # ------------------------------------------------------------------ #

    def _mrv_select(self, assignment: dict[int, str],
                    domains: dict[int, list[str]]) -> int:
        """Most Constrained Variable: unassigned node with smallest domain."""
        unassigned = [n for n in self._G.nodes() if n not in assignment]
        return min(unassigned, key=lambda n: len(domains[n]))

    def _lcv_order(self, node_id: int, assignment: dict[int, str],
                   domains: dict[int, list[str]],
                   remaining: dict[int, int]) -> list[str]:
        """
        Least Constraining Value: order values by how few options they
        eliminate from unassigned neighbours. Fewer eliminations → try first.
        """
        available = [t for t in domains[node_id] if remaining.get(t, 0) > 0]

        def eliminations(loc_type: str) -> int:
            count = 0
            test_assign = {**assignment, node_id: loc_type}
            for nb in self._G.neighbors(node_id):
                if nb not in assignment:
                    for val in domains[nb]:
                        if not self._is_consistent(nb, val, test_assign):
                            count += 1
            return count

        return sorted(available, key=eliminations)

    # ------------------------------------------------------------------ #
    #  MAC / AC-3                                                          #
    # ------------------------------------------------------------------ #

    def _mac_ac3(self, assigned_node: int, assigned_type: str,
                 assignment: dict[int, str],
                 domains: dict[int, list[str]]) -> bool:
        """
        Maintain Arc Consistency after an assignment.
        Prunes domains of neighbours. Returns False if any domain is wiped.
        Operates on a domains copy so backtracking can restore original.
        """
        queue = [(nb, assigned_node) for nb in self._G.neighbors(assigned_node)
                 if nb not in assignment]

        while queue:
            xi, xj = queue.pop(0)
            if xi in assignment:
                continue

            removed = []
            for val in list(domains[xi]):
                # val is inconsistent if it conflicts with every value in xj's domain
                xj_vals = [assignment[xj]] if xj in assignment else domains[xj]
                all_conflict = all(
                    not self._is_consistent(xi, val, {**assignment, xj: xj_val})
                    for xj_val in xj_vals
                )
                if all_conflict:
                    domains[xi].remove(val)
                    removed.append(val)

            if not domains[xi]:
                return False  # domain wiped out → dead end

            if removed:
                for xk in self._G.neighbors(xi):
                    if xk not in assignment and xk != xj:
                        queue.append((xk, xi))

        return True

    # ------------------------------------------------------------------ #
    #  CONFLICT IDENTIFICATION                                            #
    # ------------------------------------------------------------------ #

    def _identify_conflict(self) -> str:
        """
        Determine which constraint makes the problem unsolvable by trying
        to solve with each constraint disabled. The one whose removal
        allows a solution is the culprit.
        """
        constraints_to_test = [
            self._C_INDUSTRIAL_SEP,
            self._C_RESIDENTIAL_HOP,
            self._C_POWERPLANT_HOP,
        ]

        for skip in constraints_to_test:
            domains   = {n: list(self._cfg.counts.keys()) for n in self._G.nodes()}
            remaining = dict(self._cfg.counts)
            result    = self._backtrack_skip_constraint({}, domains, remaining, skip)
            if result is not None:
                return skip

        return "multiple_constraints_conflict"

    def _backtrack_skip_constraint(self, assignment, domains, remaining,
                                   skip_constraint: str):
        """Backtrack but skip one named constraint — used only for diagnosis."""
        if len(assignment) == len(self._G.nodes()):
            return assignment

        # Hard limit for diagnosis pass
        if self._stats["backtracks"] >= self._cfg.max_backtracks * 2:
            return None

        node_id = self._mrv_select(assignment, domains)

        for loc_type in self._lcv_order(node_id, assignment, domains, remaining):
            if remaining.get(loc_type, 0) == 0:
                continue

            consistent = self._is_consistent_skip(node_id, loc_type,
                                                   assignment, skip_constraint)
            if not consistent:
                continue

            assignment[node_id] = loc_type
            remaining[loc_type] -= 1
            domains_copy = {k: list(v) for k, v in domains.items()}
            result = self._backtrack_skip_constraint(
                assignment, domains_copy, remaining, skip_constraint)
            if result is not None:
                return result

            del assignment[node_id]
            remaining[loc_type] += 1
            self._stats["backtracks"] += 1

        return None

    def _is_consistent_skip(self, node_id, loc_type, assignment, skip):
        checks = {
            self._C_INDUSTRIAL_SEP:  self._check_industrial_sep,
            self._C_RESIDENTIAL_HOP: self._check_residential_hop,
            self._C_POWERPLANT_HOP:  self._check_powerplant_hop,
        }
        return all(
            fn(node_id, loc_type, assignment)
            for tag, fn in checks.items()
            if tag != skip
        )

    # ------------------------------------------------------------------ #
    #  MINIMUM-CONFLICT FALLBACK                                          #
    # ------------------------------------------------------------------ #

    def _minimum_conflict_layout(self) -> dict[int, str]:
        """
        Greedy initial placement followed by iterative min-conflict repair.
        Used only when backtracking fails — guarantees we return something.
        """
        # Step 1: random greedy placement respecting counts
        all_types = []
        for loc_type, count in self._cfg.counts.items():
            all_types.extend([loc_type] * count)
        random.shuffle(all_types)

        nodes = list(self._G.nodes())
        assignment = {nodes[i]: all_types[i] for i in range(len(nodes))}

        # Step 2: iterative repair — 1000 passes max
        for _ in range(1000):
            violated = [n for n in nodes
                        if not self._is_consistent(n, assignment[n], assignment)]
            if not violated:
                break

            # Pick a random violated node
            node = random.choice(violated)
            current_type = assignment[node]

            # Find a different node of each other type we could swap with
            best_node   = None
            best_score  = self._count_violations_for_node(node, assignment)

            for candidate in random.sample(nodes, min(30, len(nodes))):
                if assignment[candidate] == current_type:
                    continue
                # Try swap
                old_a = assignment[node]
                old_b = assignment[candidate]
                assignment[node]      = old_b
                assignment[candidate] = old_a

                score = (self._count_violations_for_node(node, assignment) +
                         self._count_violations_for_node(candidate, assignment))

                if score < best_score:
                    best_score = score
                    best_node  = candidate
                    old_a, old_b = old_b, old_a  # keep this swap

                # Undo if not better
                assignment[node]      = old_a
                assignment[candidate] = old_b

            if best_node is not None:
                # Apply the best swap found
                assignment[node], assignment[best_node] = (
                    assignment[best_node], assignment[node]
                )

        return assignment

    def _count_violations_for_node(self, node_id: int,
                                    assignment: dict[int, str]) -> int:
        """Count how many constraints node_id currently violates."""
        loc_type = assignment[node_id]
        others   = {k: v for k, v in assignment.items() if k != node_id}
        return sum([
            not self._check_industrial_sep(node_id, loc_type, others),
            not self._check_residential_hop(node_id, loc_type, others),
            not self._check_powerplant_hop(node_id, loc_type, others),
        ])

    # ------------------------------------------------------------------ #
    #  VIOLATION REPORTING                                                #
    # ------------------------------------------------------------------ #

    def _collect_violations(self, assignment: dict[int, str]) -> list[str]:
        """Return human-readable list of all constraint violations in assignment."""
        violations = []
        for node_id, loc_type in assignment.items():
            others = {k: v for k, v in assignment.items() if k != node_id}
            r, c   = self._G.nodes[node_id]['row'], self._G.nodes[node_id]['col']

            if not self._check_industrial_sep(node_id, loc_type, others):
                violations.append(
                    f"Node {node_id} ({r},{c}) [{loc_type}]: "
                    f"Industrial adjacent to Hospital/School"
                )
            if not self._check_residential_hop(node_id, loc_type, others):
                violations.append(
                    f"Node {node_id} ({r},{c}) [{loc_type}]: "
                    f"Residential not within 3 hops of any Hospital"
                )
            if not self._check_powerplant_hop(node_id, loc_type, others):
                violations.append(
                    f"Node {node_id} ({r},{c}) [{loc_type}]: "
                    f"PowerPlant not within 2 hops of any Industrial"
                )
        return violations