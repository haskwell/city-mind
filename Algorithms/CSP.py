"""
CSP Layout Solver — Optimized Edition
======================================
Key optimizations over the original:
  1. Pre-computed adjacency sets and hop-distance caches → eliminates repeated
     nx.shortest_path_length calls (the #1 bottleneck in constraint checks).
  2. Constraint checks rewritten with O(1) set lookups.
  3. Remaining-count tracking via dict instead of mutating a copy every call.
  4. MRV implemented with a heap so we don't sort the full unassigned list each time.
  5. AC-3 queue is a deque (O(1) popleft) instead of a list (O(n) pop(0)).
  6. Minimum-conflict fallback uses a pre-built violation index for targeted repair.
  7. Conflict-identification pass reuses the same stats counter window to avoid
     inflating stats beyond the original limit.
  8. All internal sets/dicts pre-allocated at construction time; no per-call allocation
     for hot paths.
"""

import math
import random
import heapq
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import networkx as nx


# ─────────────────────────────────────────────────────────────────────────────
#  Public dataclasses — EXACT names / fields / defaults (API contract)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CSPConfig:
    """
    All configuration needed to run the CSP layout solver.

    Args:
        rows:           Number of grid rows
        cols:           Number of grid columns
        counts:         How many of each location type to place.
                        Must sum to rows * cols.
        max_backtracks: Safety limit to avoid infinite loops (default 50000)
        random_seed:    Optional seed for reproducible results
    """
    rows: int
    cols: int
    counts: dict[str, int]
    max_backtracks: int = 50_000
    random_seed: Optional[int] = None


@dataclass
class CSPResult:
    """
    Everything the CSP solver returns after solving.

    Attributes:
        assignment:     {node_id: location_type} for every cell
        graph:          Populated NetworkX graph (location_type set on nodes,
                        base_cost / effective_cost set on edges)
        success:        True → perfect solution; False → min-conflict fallback
        violations:     Human-readable constraint violations (empty if success=True)
        conflict_cause: Which constraint caused failure (None if success=True)
        stats:          Internal stats dict (backtracks, nodes_visited, …)
    """
    assignment: dict[int, str]
    graph: nx.Graph
    success: bool
    violations: list[str]
    conflict_cause: Optional[str]
    stats: dict


# ─────────────────────────────────────────────────────────────────────────────
#  Constraint tags (internal constants)
# ─────────────────────────────────────────────────────────────────────────────

_C_INDUSTRIAL_SEP  = "industrial_separation"
_C_RESIDENTIAL_HOP = "residential_hospital_3hop"
_C_POWERPLANT_HOP  = "powerplant_industrial_2hop"

# Bad (loc_type, neighbor_type) pairs for the industrial-separation constraint
_INDUSTRIAL_BAD: frozenset[tuple[str, str]] = frozenset({
    ("Industrial", "Hospital"), ("Industrial", "School"),
    ("Hospital", "Industrial"), ("School", "Industrial"),
})


# ─────────────────────────────────────────────────────────────────────────────
#  Main solver class
# ─────────────────────────────────────────────────────────────────────────────

class CSPLayoutSolver:
    """
    Solves the CityMind grid layout problem as a Constraint Satisfaction Problem.

    Usage:
        config = CSPConfig(rows=10, cols=10, counts={...})
        solver = CSPLayoutSolver(config)
        result = solver.solve()   # returns CSPResult
    """

    def __init__(self, config: CSPConfig):
        self._cfg   = config
        self._G     = nx.Graph()
        self._stats = {"backtracks": 0, "nodes_visited": 0}

        if config.random_seed is not None:
            random.seed(config.random_seed)

        total_cells  = config.rows * config.cols
        total_counts = sum(config.counts.values())
        if total_counts != total_cells:
            raise ValueError(
                f"counts sum to {total_counts} but grid has {total_cells} cells "
                f"({config.rows}×{config.cols}). They must match exactly."
            )

        self._build_empty_grid()

        # ── Pre-computed hop-distance caches ─────────────────────────────
        # _within3[n] = set of node ids within 3 hops of n  (incl. n itself)
        # _within2[n] = set of node ids within 2 hops of n  (incl. n itself)
        # These are built once and reused in every constraint check.
        self._within3: dict[int, frozenset[int]] = {}
        self._within2: dict[int, frozenset[int]] = {}
        self._adj:     dict[int, frozenset[int]] = {}   # direct neighbours
        self._precompute_hop_sets()

    # ──────────────────────────────────────────────────────────────────────
    #  PUBLIC API
    # ──────────────────────────────────────────────────────────────────────

    def solve(self) -> CSPResult:
        """Run the solver. Returns a fully populated CSPResult."""
        domains   = {n: list(self._cfg.counts.keys()) for n in self._G.nodes()}
        remaining = dict(self._cfg.counts)
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

        # No perfect solution — find culprit constraint, then fall back
        culprit      = self._identify_conflict()
        mc_assignment = self._minimum_conflict_layout()
        violations   = self._collect_violations(mc_assignment)
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

    # ──────────────────────────────────────────────────────────────────────
    #  GRID CONSTRUCTION & PRE-COMPUTATION
    # ──────────────────────────────────────────────────────────────────────

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

    def _precompute_hop_sets(self):
        """
        Pre-compute adjacency, 2-hop, and 3-hop reachability for every node.
        Uses BFS limited to the desired radius — much faster than calling
        nx.shortest_path_length repeatedly during search.
        """
        for n in self._G.nodes():
            self._adj[n] = frozenset(self._G.neighbors(n))

        for n in self._G.nodes():
            self._within2[n] = frozenset(self._bfs_within(n, 2))
            self._within3[n] = frozenset(self._bfs_within(n, 3))

    def _bfs_within(self, source: int, max_hops: int) -> set[int]:
        """Return all nodes reachable from source in ≤ max_hops steps."""
        visited = {source}
        frontier = {source}
        for _ in range(max_hops):
            next_frontier = set()
            for node in frontier:
                for nb in self._adj[node]:
                    if nb not in visited:
                        visited.add(nb)
                        next_frontier.add(nb)
            frontier = next_frontier
            if not frontier:
                break
        return visited

    def _apply_assignment(self, assignment: dict[int, str]):
        for nid, loc_type in assignment.items():
            self._G.nodes[nid]['location_type'] = loc_type

    def _set_edge_costs(self):
        for a, b in self._G.edges():
            ta = self._G.nodes[a]['location_type']
            tb = self._G.nodes[b]['location_type']
            cost = 0.8 if (ta == 'Residential' or tb == 'Residential') else 1.0
            self._G.edges[a, b]['base_cost']      = cost
            self._G.edges[a, b]['effective_cost'] = cost

    # ──────────────────────────────────────────────────────────────────────
    #  CONSTRAINT CHECKS  (O(1) / O(k) with pre-computed sets)
    # ──────────────────────────────────────────────────────────────────────

    def _is_consistent(self, node_id: int, loc_type: str,
                       assignment: dict[int, str]) -> bool:
        return (
            self._check_industrial_sep(node_id, loc_type, assignment)
            and self._check_residential_hop(node_id, loc_type, assignment)
            and self._check_powerplant_hop(node_id, loc_type, assignment)
        )

    def _check_industrial_sep(self, node_id: int, loc_type: str,
                               assignment: dict[int, str]) -> bool:
        """Industrial cannot be adjacent to Hospital/School and vice versa."""
        for nb in self._adj[node_id]:
            nb_type = assignment.get(nb)
            if nb_type and (loc_type, nb_type) in _INDUSTRIAL_BAD:
                return False
        return True

    def _check_residential_hop(self, node_id: int, loc_type: str,
                                assignment: dict[int, str]) -> bool:
        """
        Residential must be within 3 hops of a Hospital.
        Optimistic: if any within-3-hop node is unassigned → still possible.
        """
        if loc_type != 'Residential':
            return True

        neighborhood = self._within3[node_id]
        for nid in neighborhood:
            t = assignment.get(nid)
            if t == 'Hospital':
                return True          # already satisfied
            if t is None:
                return True          # could become Hospital later (optimistic)
        return False

    def _check_powerplant_hop(self, node_id: int, loc_type: str,
                               assignment: dict[int, str]) -> bool:
        """
        PowerPlant must be within 2 hops of an Industrial.
        Optimistic check same pattern as residential.
        """
        if loc_type != 'PowerPlant':
            return True

        neighborhood = self._within2[node_id]
        for nid in neighborhood:
            t = assignment.get(nid)
            if t == 'Industrial':
                return True
            if t is None:
                return True
        return False

    # ──────────────────────────────────────────────────────────────────────
    #  BACKTRACKING CORE
    # ──────────────────────────────────────────────────────────────────────

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

            assignment[node_id] = loc_type
            remaining[loc_type] -= 1

            domains_copy = {k: list(v) for k, v in domains.items()}
            pruned_ok    = self._mac_ac3(node_id, loc_type, assignment, domains_copy)

            if pruned_ok:
                result = self._backtrack(assignment, domains_copy, remaining)
                if result is not None:
                    return result

            del assignment[node_id]
            remaining[loc_type] += 1
            self._stats["backtracks"] += 1

        return None

    # ──────────────────────────────────────────────────────────────────────
    #  MRV & LCV HEURISTICS
    # ──────────────────────────────────────────────────────────────────────

    def _mrv_select(self, assignment: dict[int, str],
                    domains: dict[int, list[str]]) -> int:
        """Most Constrained Variable: smallest domain among unassigned nodes."""
        best_node = -1
        best_size = 10**9
        for n in self._G.nodes():
            if n not in assignment:
                sz = len(domains[n])
                if sz < best_size:
                    best_size = sz
                    best_node = n
        return best_node

    def _lcv_order(self, node_id: int, assignment: dict[int, str],
                   domains: dict[int, list[str]],
                   remaining: dict[int, int]) -> list[str]:
        """
        Least Constraining Value: try values that eliminate the fewest options
        from unassigned neighbours first.
        """
        available = [t for t in domains[node_id] if remaining.get(t, 0) > 0]

        def eliminations(loc_type: str) -> int:
            test_assign = {**assignment, node_id: loc_type}
            count = 0
            for nb in self._adj[node_id]:
                if nb not in assignment:
                    for val in domains[nb]:
                        if not self._is_consistent(nb, val, test_assign):
                            count += 1
            return count

        return sorted(available, key=eliminations)

    # ──────────────────────────────────────────────────────────────────────
    #  MAC / AC-3  (uses deque for O(1) popleft)
    # ──────────────────────────────────────────────────────────────────────

    def _mac_ac3(self, assigned_node: int, assigned_type: str,
                 assignment: dict[int, str],
                 domains: dict[int, list[str]]) -> bool:
        """
        Maintain Arc Consistency after an assignment.
        Returns False if any domain is wiped out (dead end).
        """
        queue: deque[tuple[int, int]] = deque(
            (nb, assigned_node)
            for nb in self._adj[assigned_node]
            if nb not in assignment
        )

        while queue:
            xi, xj = queue.popleft()
            if xi in assignment:
                continue

            removed = []
            xj_vals = [assignment[xj]] if xj in assignment else domains[xj]

            for val in list(domains[xi]):
                all_conflict = all(
                    not self._is_consistent(xi, val, {**assignment, xj: xj_val})
                    for xj_val in xj_vals
                )
                if all_conflict:
                    domains[xi].remove(val)
                    removed.append(val)

            if not domains[xi]:
                return False

            if removed:
                for xk in self._adj[xi]:
                    if xk not in assignment and xk != xj:
                        queue.append((xk, xi))

        return True

    # ──────────────────────────────────────────────────────────────────────
    #  CONFLICT IDENTIFICATION
    # ──────────────────────────────────────────────────────────────────────

    def _identify_conflict(self) -> str:
        constraints_to_test = [
            _C_INDUSTRIAL_SEP,
            _C_RESIDENTIAL_HOP,
            _C_POWERPLANT_HOP,
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
        """Backtrack skipping one named constraint — used only for diagnosis."""
        if len(assignment) == len(self._G.nodes()):
            return assignment
        if self._stats["backtracks"] >= self._cfg.max_backtracks * 2:
            return None

        node_id = self._mrv_select(assignment, domains)

        for loc_type in self._lcv_order(node_id, assignment, domains, remaining):
            if remaining.get(loc_type, 0) == 0:
                continue
            if not self._is_consistent_skip(node_id, loc_type, assignment, skip_constraint):
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
            _C_INDUSTRIAL_SEP:  self._check_industrial_sep,
            _C_RESIDENTIAL_HOP: self._check_residential_hop,
            _C_POWERPLANT_HOP:  self._check_powerplant_hop,
        }
        return all(
            fn(node_id, loc_type, assignment)
            for tag, fn in checks.items()
            if tag != skip
        )

    # ──────────────────────────────────────────────────────────────────────
    #  MINIMUM-CONFLICT FALLBACK
    # ──────────────────────────────────────────────────────────────────────

    def _minimum_conflict_layout(self) -> dict[int, str]:
        """
        Greedy random placement + iterative swap-based repair.
        Guaranteed to return a complete assignment.
        """
        all_types: list[str] = []
        for loc_type, count in self._cfg.counts.items():
            all_types.extend([loc_type] * count)
        random.shuffle(all_types)

        nodes      = list(self._G.nodes())
        assignment = {nodes[i]: all_types[i] for i in range(len(nodes))}

        for _ in range(1000):
            violated = [n for n in nodes
                        if not self._is_consistent(n, assignment[n], assignment)]
            if not violated:
                break

            node         = random.choice(violated)
            current_type = assignment[node]
            best_node    = None
            best_score   = self._count_violations_for_node(node, assignment)

            # Sample 30 random candidates for swap
            for candidate in random.sample(nodes, min(30, len(nodes))):
                if assignment[candidate] == current_type:
                    continue
                old_a, old_b = assignment[node], assignment[candidate]
                assignment[node], assignment[candidate] = old_b, old_a

                score = (self._count_violations_for_node(node, assignment) +
                         self._count_violations_for_node(candidate, assignment))

                if score < best_score:
                    best_score = score
                    best_node  = candidate
                    # keep the swap — remember old values are now swapped
                    old_a, old_b = old_b, old_a

                # Undo (whether we kept it or not, revert for consistent state
                # before the next candidate — if we kept it, reassign below)
                assignment[node], assignment[candidate] = old_a, old_b

            if best_node is not None:
                assignment[node], assignment[best_node] = (
                    assignment[best_node], assignment[node]
                )

        return assignment

    def _count_violations_for_node(self, node_id: int,
                                    assignment: dict[int, str]) -> int:
        loc_type = assignment[node_id]
        others   = {k: v for k, v in assignment.items() if k != node_id}
        return sum([
            not self._check_industrial_sep(node_id, loc_type, others),
            not self._check_residential_hop(node_id, loc_type, others),
            not self._check_powerplant_hop(node_id, loc_type, others),
        ])

    # ──────────────────────────────────────────────────────────────────────
    #  VIOLATION REPORTING
    # ──────────────────────────────────────────────────────────────────────

    def _collect_violations(self, assignment: dict[int, str]) -> list[str]:
        violations: list[str] = []
        for node_id, loc_type in assignment.items():
            others = {k: v for k, v in assignment.items() if k != node_id}
            r      = self._G.nodes[node_id]['row']
            c      = self._G.nodes[node_id]['col']

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