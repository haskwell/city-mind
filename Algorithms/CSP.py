from __future__ import annotations

import networkx as nx
import math
import random
from collections import defaultdict
from itertools import product as itertools_product


# ─────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────
INCOMPATIBLE_NEIGHBORS = {
    "Industrial": {"School", "Hospital"},
    "School":     {"Industrial"},
    "Hospital":   {"Industrial"},
    }

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx


_INCOMPATIBLE: Set[frozenset] = {
    frozenset({"industrial", "hospital"}),
    frozenset({"industrial", "school"}),
}

# Tier 1: placed via CSP
_TIER1_ORDER = ["power_plant", "industrial", "hospital", "ambulance_depot", "school"]
# Tier 2: placed greedily
_TIER2 = {"residential"}


@dataclass
class CSPResult:
    assignment: Dict[int, Optional[str]]
    success: bool
    violations: List[Tuple[str, str]] = field(default_factory=list)
    nodes_explored: int = 0
    elapsed: float = 0.0

    def __repr__(self) -> str:
        s = "SATISFYING" if self.success else f"BEST-EFFORT ({len(self.violations)} violations)"
        return (f"<CSPResult [{s}] nodes_explored={self.nodes_explored} "
                f"elapsed={self.elapsed:.3f}s>")


class CityLayoutCSP:
    """
    CSP solver for CityMind Challenge 1.

    Parameters
    ----------
    city_graph      : CityGraph  the shared city graph
    building_counts : dict       {location_type: count}
    time_limit      : float      seconds before returning best-effort (default 30)
    seed            : ignored (kept for API compatibility)
    """

    def __init__(
        self,
        city_graph,
        building_counts: Dict[str, int],
        time_limit: float = 30.0,
        seed=None,
    ):
        self.G: nx.Graph = city_graph.G
        self.rows = city_graph.rows
        self.cols = city_graph.cols

        self.building_counts = {k: v for k, v in building_counts.items() if v > 0}
        self.time_limit = time_limit
        self.all_nodes: List[int] = sorted(self.G.nodes())

        self._adj: Dict[int, List[int]] = {
            n: list(self.G.neighbors(n)) for n in self.all_nodes
        }

        self._within3: Dict[int, Set[int]] = {}
        self._within2: Dict[int, Set[int]] = {}
        self._precompute_reachability()

        # ---- build Tier 1 variable list ----
        self._t1_vars: List[Tuple[str, int]] = []
        for btype in _TIER1_ORDER:
            cnt = self.building_counts.get(btype, 0)
            for i in range(cnt):
                self._t1_vars.append((btype, i))
        # Any unknown type also goes into tier 1
        for btype, cnt in self.building_counts.items():
            if btype not in _TIER1_ORDER and btype not in _TIER2:
                for i in range(cnt):
                    self._t1_vars.append((btype, i))

        self._n_t1 = len(self._t1_vars)

        # ---- tier 2 counts ----
        self._t2_counts: Dict[str, int] = {
            t: self.building_counts[t]
            for t in _TIER2
            if t in self.building_counts
        }

        self._nodes_explored = 0
        self._deadline = 0.0
        self._best: Optional[Dict[int, Optional[str]]] = None
        self._best_score = float("inf")

    # ------------------------------------------------------------------ setup

    def _precompute_reachability(self) -> None:
        for nid in self.all_nodes:
            d3: Set[int] = set()
            d2: Set[int] = set()
            q: deque = deque([(nid, 0)])
            vis: Set[int] = {nid}
            while q:
                cur, depth = q.popleft()
                if depth > 0:
                    d3.add(cur)
                    if depth <= 2:
                        d2.add(cur)
                if depth < 3:
                    for nb in self._adj[cur]:
                        if nb not in vis:
                            vis.add(nb)
                            q.append((nb, depth + 1))
            self._within3[nid] = d3
            self._within2[nid] = d2

    # ------------------------------------------------------------------ solve

    def solve(self) -> CSPResult:
        self._deadline = time.time() + self.time_limit
        self._nodes_explored = 0
        self._best = None
        self._best_score = float("inf")
        t0 = time.time()

        node_asgn: Dict[int, str] = {}
        domains: List[Optional[List[int]]] = [None] * self._n_t1
        last_placed: Dict[str, int] = {}   # symmetry breaking

        success = self._backtrack(0, node_asgn, domains, last_placed)

        if success:
            # Greedy tier-2 placement
            t2_ok = self._place_tier2(node_asgn)
            success = success and t2_ok

        elapsed = time.time() - t0
        final = self._to_full(node_asgn)
        self._apply_to_graph(final)

        if success:
            return CSPResult(
                assignment=final, success=True,
                nodes_explored=self._nodes_explored, elapsed=elapsed,
            )

        # Try tier-2 on best-effort tier-1 result
        if self._best is not None:
            # Reconstruct placed dict from best
            best_placed = {n: t for n, t in self._best.items() if t}
            self._place_tier2(best_placed)
            final2 = self._to_full(best_placed)
            self._apply_to_graph(final2)
            return CSPResult(
                assignment=final2, success=False,
                violations=self._check_constraints(final2),
                nodes_explored=self._nodes_explored, elapsed=elapsed,
            )

        return CSPResult(
            assignment=final, success=False,
            violations=self._check_constraints(final),
            nodes_explored=self._nodes_explored, elapsed=elapsed,
        )

    # ------------------------------------------------------------ tier-2 greedy

    def _place_tier2(self, node_asgn: Dict[int, str]) -> bool:
        """
        Greedily place residential (and other tier-2) buildings.
        Each residential must be within 3 hops of a hospital (C2).
        Returns True if all were placed successfully.
        """
        hospitals = {n for n, t in node_asgn.items() if t == "hospital"}
        occupied = set(node_asgn.keys())
        success = True

        for btype, count in self._t2_counts.items():
            placed = 0
            # Sort candidates by coverage (prefer nodes near multiple hospitals
            # so that nodes far from hospitals are "saved" for last — greedy heuristic)
            candidates = sorted(
                (n for n in self.all_nodes if n not in occupied),
                key=lambda n: -len(self._within3[n] & hospitals)
            )
            for n in candidates:
                if placed >= count:
                    break
                if btype == "residential" and not (self._within3[n] & hospitals):
                    continue  # C2 not satisfied
                node_asgn[n] = btype
                occupied.add(n)
                placed += 1
            if placed < count:
                success = False  # couldn't place all

        return success

    # -------------------------------------------------------------- backtrack

    def _backtrack(
        self,
        var_idx: int,
        node_asgn: Dict[int, str],
        domains: List[Optional[List[int]]],
        last_placed: Dict[str, int],
    ) -> bool:

        if var_idx == self._n_t1:
            return self._t1_constraints_ok(node_asgn)

        if time.time() > self._deadline:
            self._maybe_update_best(node_asgn, var_idx)
            return False

        btype, _ = self._t1_vars[var_idx]
        occupied = set(node_asgn.keys())
        min_node = last_placed.get(btype, -1)

        if domains[var_idx] is None:
            domains[var_idx] = self._make_domain(btype, node_asgn, min_node)

        for node in domains[var_idx]:
            if node <= min_node:
                continue
            if node in occupied:
                continue
            if not self._c1_ok(btype, node, node_asgn):
                continue

            self._nodes_explored += 1

            node_asgn[node] = btype
            prev_last = last_placed.get(btype, -1)
            last_placed[btype] = node

            saved: List[Tuple[int, List[int]]] = []
            ok = self._propagate(btype, node, var_idx + 1, node_asgn, domains, saved)

            if ok and self._backtrack(var_idx + 1, node_asgn, domains, last_placed):
                return True

            for vi, old_dom in saved:
                domains[vi] = old_dom
            del node_asgn[node]
            last_placed[btype] = prev_last

        self._maybe_update_best(node_asgn, var_idx)
        return False

    # ------------------------------------------------------- domain + C1

    def _make_domain(
        self, btype: str, node_asgn: Dict[int, str], min_node: int
    ) -> List[int]:
        occupied = set(node_asgn.keys())
        candidates = [
            n for n in self.all_nodes
            if n > min_node
            and n not in occupied
            and self._c1_ok(btype, n, node_asgn)
        ]
        if btype in ("industrial", "hospital", "school"):
            candidates.sort(key=lambda n: sum(
                1 for nb in self._adj[n]
                if nb not in occupied
                and any(frozenset({btype, ft}) in _INCOMPATIBLE
                        for ft in self.building_counts)
            ))
        return candidates

    def _c1_ok(self, btype: str, node: int, node_asgn: Dict[int, str]) -> bool:
        if btype not in ("industrial", "hospital", "school"):
            return True
        for nb in self._adj[node]:
            nb_t = node_asgn.get(nb)
            if nb_t and frozenset({btype, nb_t}) in _INCOMPATIBLE:
                return False
        return True

    # -------------------------------------------- propagation / forward check

    def _propagate(
        self,
        btype: str,
        node: int,
        start_idx: int,
        node_asgn: Dict[int, str],
        domains: List[Optional[List[int]]],
        saved: List[Tuple[int, List[int]]],
    ) -> bool:
        future_need: Dict[str, int] = {}
        for i in range(start_idx, self._n_t1):
            t, _ = self._t1_vars[i]
            future_need[t] = future_need.get(t, 0) + 1

        # Nodes banned for each future type
        banned_for: Dict[str, Set[int]] = {}
        for ft in future_need:
            if frozenset({btype, ft}) in _INCOMPATIBLE:
                banned_for[ft] = set(self._adj[node]) | {node}
            else:
                banned_for[ft] = {node}

        saved_set: Set[int] = set()

        for i in range(start_idx, self._n_t1):
            ft, _ = self._t1_vars[i]
            if domains[i] is None:
                continue
            banned = banned_for.get(ft, {node})
            overlap = set(domains[i]) & banned
            if not overlap:
                continue
            if i not in saved_set:
                saved.append((i, list(domains[i])))
                saved_set.add(i)
            domains[i] = [n for n in domains[i] if n not in banned]
            if len(domains[i]) < future_need[ft]:
                return False

        # Extra: verify enough nodes coverable by hospitals for future residential
        # (done here cheaply: check after each hospital is placed)
        if btype == "hospital":
            hospitals_now = {n for n, t in node_asgn.items() if t == "hospital"}
            res_need = self._t2_counts.get("residential", 0)
            if res_need > 0 and future_need.get("hospital", 0) == 0:
                occupied = set(node_asgn.keys())
                coverable = sum(
                    1 for n in self.all_nodes
                    if n not in occupied and self._within3[n] & hospitals_now
                )
                if coverable < res_need:
                    return False

        # C3: after placing industrial, check power_plant can still be placed
        if btype == "industrial" and "power_plant" in future_need:
            ind_now = {n for n, t in node_asgn.items() if t == "industrial"}
            occupied = set(node_asgn.keys())
            pp_spots = sum(
                1 for n in self.all_nodes
                if n not in occupied and self._within2[n] & ind_now
            )
            if pp_spots < future_need["power_plant"]:
                return False

        return True

    # ----------------------------------------- tier-1 final constraint check

    def _t1_constraints_ok(self, node_asgn: Dict[int, str]) -> bool:
        """C3 check — C1 and C2-setup checked incrementally."""
        industrials = {n for n, t in node_asgn.items() if t == "industrial"}
        for n, t in node_asgn.items():
            if t == "power_plant" and not (self._within2[n] & industrials):
                return False
        return True

    # ----------------------------------------- full constraint check

    def _check_constraints(
        self, full_asgn: Dict[int, Optional[str]]
    ) -> List[Tuple[str, str]]:
        violations: List[Tuple[str, str]] = []
        seen: Set[str] = set()
        hospitals = {n for n, t in full_asgn.items() if t == "hospital"}
        industrials = {n for n, t in full_asgn.items() if t == "industrial"}
        for nid, t in full_asgn.items():
            if not t:
                continue
            for nb in self._adj[nid]:
                nb_t = full_asgn.get(nb)
                if nb_t and frozenset({t, nb_t}) in _INCOMPATIBLE:
                    key = f"{min(nid,nb)}-{max(nid,nb)}"
                    if key not in seen:
                        seen.add(key)
                        violations.append(("C1", f"node {nid}({t}) adj {nb}({nb_t})"))
            if t == "residential" and not (self._within3[nid] & hospitals):
                violations.append(("C2", f"residential {nid}: no hospital <=3 hops"))
            if t == "power_plant" and not (self._within2[nid] & industrials):
                violations.append(("C3", f"power_plant {nid}: no industrial <=2 hops"))
        return violations

    # ----------------------------------------- best-effort

    def _maybe_update_best(
        self, node_asgn: Dict[int, str], var_idx: int
    ) -> None:
        full = self._to_full(node_asgn)
        v = self._check_constraints(full)
        score = len(v) * 100 + (self._n_t1 - var_idx)
        if score < self._best_score:
            self._best_score = score
            self._best = full

    def _to_full(self, node_asgn: Dict[int, str]) -> Dict[int, Optional[str]]:
        return {nid: node_asgn.get(nid) for nid in self.all_nodes}

    def _apply_to_graph(self, full: Dict[int, Optional[str]]) -> None:
        for nid, t in full.items():
            self.G.nodes[nid]["location_type"] = t


# ---------------------------------------------------------------------------
# Smoke-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")

    try:
        from city_graph import CityGraph  # type: ignore
    except ImportError:
        class CityGraph:  # type: ignore[no-redef]
            def __init__(self, rows, cols):
                self.rows, self.cols = rows, cols
                self.G = nx.Graph()
                for r in range(rows):
                    for c in range(cols):
                        nid = r * cols + c
                        self.G.add_node(nid, row=r, col=c, location_type=None,
                                        population_density=0.0, risk_index=0.0,
                                        accessible=True, cluster_id=None,
                                        risk_level=None, risk_multiplier=1.0,
                                        has_ambulance=False)
                for r in range(rows):
                    for c in range(cols):
                        nid = r * cols + c
                        if c + 1 < cols:
                            self.G.add_edge(nid, nid+1, base_cost=1.0,
                                            is_blocked=False, effective_cost=1.0)
                        if r + 1 < rows:
                            self.G.add_edge(nid, nid+cols, base_cost=1.0,
                                            is_blocked=False, effective_cost=1.0)
            def node_id(self, row, col):
                return row * self.cols + col

    counts = {
        "hospital":        2,
        "school":          3,
        "residential":     8,
        "industrial":      2,
        "power_plant":     1,
        "ambulance_depot": 1,
    }

    short = {"hospital":"H ","school":"Sc","residential":"Re",
             "industrial":"In","power_plant":"Pp","ambulance_depot":"Ad"}

    for grid in [(6,6), (10,10), (15,15), (20,20)]:
        cg = CityGraph(*grid)
        print(f"\n=== {grid[0]}x{grid[1]} grid ===")
        csp = CityLayoutCSP(cg, counts, time_limit=10)
        result = csp.solve()
        print(result)
        if result.violations:
            for v in result.violations:
                print("  VIOLATION:", v)
        else:
            print("All constraints satisfied!")
        for r in range(min(cg.rows, 8)):
            row_str = []
            for c in range(cg.cols):
                nid = cg.node_id(r, c)
                t = result.assignment.get(nid)
                row_str.append(short.get(t, " .") if t else " .")
            print("  " + "  ".join(row_str))
        if cg.rows > 8:
            print("  ... (truncated)")

BUILDING_TYPES = {
    "Hospital", "School", "Industrial",
    "Residential", "PowerPlant", "AmbulanceDepot"
}


# ─────────────────────────────────────────────
#  Helper utilities
# ─────────────────────────────────────────────
def _bfs_distances(G, source):
    """Return dict {node_id: hop_distance} from source (unweighted hops)."""
    return nx.single_source_shortest_path_length(G, source)


def _nodes_within_hops(G, source, max_hops):
    """Set of nodes reachable from source within max_hops (unweighted)."""
    dist = _bfs_distances(G, source)
    return {n for n, d in dist.items() if d <= max_hops}


def _blocked_subgraph(G):
    """Return a view of G with blocked edges removed (for hop counts)."""
    def keep(u, v):
        return not G.edges[u, v].get("is_blocked", False)
    return nx.subgraph_view(G, filter_edge=keep)


# ─────────────────────────────────────────────
#  Constraint checkers (partial – used during search)
# ─────────────────────────────────────────────
def _check_no_industrial_next_to_sensitive(assignment, G):
    """Industrial cannot be adjacent to School or Hospital (and vice-versa)."""
    for node_id, btype in assignment.items():
        if btype not in INCOMPATIBLE_NEIGHBORS:
            continue
        forbidden = INCOMPATIBLE_NEIGHBORS[btype]
        for nb in G.neighbors(node_id):
            nb_type = assignment.get(nb)
            if nb_type in forbidden:
                return False, (
                    f"Node {node_id} ({btype}) is adjacent to "
                    f"node {nb} ({nb_type})"
                )
    return True, None


def _check_residential_near_hospital(assignment, G, max_hops=3):
    """Every Residential node must be within max_hops of a Hospital."""
    sub = _blocked_subgraph(G)
    hospitals = {n for n, t in assignment.items() if t == "Hospital"}
    if not hospitals:
        residentials = [n for n, t in assignment.items() if t == "Residential"]
        if residentials:
            return False, "No hospitals placed but Residential nodes exist"
        return True, None

    hospital_coverage = set()
    for h in hospitals:
        hospital_coverage |= _nodes_within_hops(sub, h, max_hops)

    for node_id, btype in assignment.items():
        if btype == "Residential" and node_id not in hospital_coverage:
            return False, (
                f"Residential node {node_id} is more than {max_hops} hops "
                f"from any hospital"
            )
    return True, None


def _check_powerplant_near_industrial(assignment, G, max_hops=2):
    """Every PowerPlant must be within max_hops of an Industrial zone."""
    sub = _blocked_subgraph(G)
    industrials = {n for n, t in assignment.items() if t == "Industrial"}

    for node_id, btype in assignment.items():
        if btype != "PowerPlant":
            continue
        reachable = _nodes_within_hops(sub, node_id, max_hops)
        if not (reachable & industrials):
            return False, (
                f"PowerPlant at node {node_id} has no Industrial zone "
                f"within {max_hops} hops"
            )
    return True, None


def _all_constraints_ok(assignment, G):
    """Run all three constraint checkers; return (ok, rule_name, detail)."""
    ok, detail = _check_no_industrial_next_to_sensitive(assignment, G)
    if not ok:
        return False, "IndustrialSeparation", detail

    ok, detail = _check_residential_near_hospital(assignment, G)
    if not ok:
        return False, "ResidentialHospitalProximity", detail

    ok, detail = _check_powerplant_near_industrial(assignment, G)
    if not ok:
        return False, "PowerPlantIndustrialProximity", detail

    return True, None, None


# ─────────────────────────────────────────────
#  Forward-checking / arc consistency helpers
# ─────────────────────────────────────────────
def _is_consistent_with_partial(node_id, btype, assignment, G):
    """
    Quick local consistency check before committing a variable.
    Checks the Industrial-separation constraint only (local, cheap).
    The proximity constraints are global and checked at the end.
    """
    forbidden_neighbors = INCOMPATIBLE_NEIGHBORS.get(btype, set())
    for nb in G.neighbors(node_id):
        nb_type = assignment.get(nb)
        if nb_type in forbidden_neighbors:
            return False
        # Also check reverse: if new node type is forbidden for existing neighbor
        nb_forbidden = INCOMPATIBLE_NEIGHBORS.get(nb_type, set())
        if btype in nb_forbidden:
            return False
    return True


# ─────────────────────────────────────────────
#  Core CSP solver (backtracking + heuristics)
# ─────────────────────────────────────────────
class CityCSSPSolver:
    """
    Constraint Satisfaction Problem solver for city layout.

    Parameters
    ----------
    city_graph : CityGraph
        The graph to solve on.
    building_counts : dict
        e.g. {"Hospital": 2, "School": 3, "Industrial": 1, ...}
    seed : int, optional
        Random seed for reproducibility.
    max_attempts : int
        Number of random-restart attempts before giving up.
    """

    def __init__(self, city_graph, building_counts, seed=42, max_attempts=200):
        self.cg = city_graph
        self.G = city_graph.G
        self.building_counts = {k: v for k, v in building_counts.items() if v > 0}
        self.seed = seed
        self.max_attempts = max_attempts
        random.seed(seed)

        # Validate totals
        total_buildings = sum(self.building_counts.values())
        total_nodes = self.G.number_of_nodes()
        if total_buildings > total_nodes:
            raise ValueError(
                f"Cannot place {total_buildings} buildings on {total_nodes} nodes."
            )

    # ── Public entry point ──────────────────────────────────────────────
    def solve(self):
        """
        Attempt to find a valid assignment.

        Returns
        -------
        dict  {node_id: building_type}  on success.

        Raises
        ------
        CSPConflictError  if no valid layout is found, with diagnosis.
        """
        # Pre-flight mathematical validity check
        self._preflight_check()

        # Build ordered list of (building_type, count) with placement priority:
        # Industrial first (most constrained separator), then Hospital,
        # then PowerPlant (must be near Industrial), then the rest.
        priority_order = [
            "Industrial", "Hospital", "PowerPlant",
            "School", "Residential", "AmbulanceDepot"
        ]
        ordered_types = []
        for t in priority_order:
            if t in self.building_counts:
                ordered_types.extend([t] * self.building_counts[t])
        # remaining types not in priority list
        for t, cnt in self.building_counts.items():
            if t not in priority_order:
                ordered_types.extend([t] * cnt)

        best_partial = {}
        for attempt in range(self.max_attempts):
            assignment = {}
            remaining = list(ordered_types)  # mutable copy
            if attempt > 0:
                random.shuffle(remaining)

            result = self._backtrack(assignment, remaining)
            if result is not None:
                self._apply_to_graph(result)
                return result
            # Track best partial for diagnostics
            if len(assignment) > len(best_partial):
                best_partial = dict(assignment)

        # Failed – diagnose
        raise CSPConflictError(
            self._diagnose(best_partial),
            best_partial,
            self.building_counts,
            self.G
        )

    # ── Backtracking search ─────────────────────────────────────────────
    def _backtrack(self, assignment, remaining_types):
        if not remaining_types:
            # All buildings placed – run full global constraint check
            ok, rule, detail = _all_constraints_ok(assignment, self.G)
            if ok:
                return assignment
            return None

        btype = remaining_types[0]
        rest = remaining_types[1:]

        # Variable ordering: choose the node with the fewest valid options
        candidates = self._order_candidates(btype, assignment)

        for node_id in candidates:
            if node_id in assignment:
                continue
            if not _is_consistent_with_partial(node_id, btype, assignment, self.G):
                continue

            assignment[node_id] = btype
            result = self._backtrack(assignment, rest)
            if result is not None:
                return result
            del assignment[node_id]

        return None

    def _order_candidates(self, btype, assignment):
        """
        Return nodes ordered by a heuristic suited to the building type.
        - Industrial: prefer nodes far from Hospitals/Schools already placed
        - Hospital: prefer central nodes (high closeness) for coverage
        - PowerPlant: prefer nodes near existing Industrial nodes
        - Others: shuffle for diversity
        """
        sub = _blocked_subgraph(self.G)
        available = [n for n in self.G.nodes() if n not in assignment]

        if btype == "Industrial":
            sensitive = {n for n, t in assignment.items()
                         if t in ("School", "Hospital")}
            def score(n):
                if not sensitive:
                    return random.random()
                min_d = min(
                    (nx.shortest_path_length(sub, n, s)
                     if nx.has_path(sub, n, s) else 999)
                    for s in sensitive
                )
                return -min_d  # higher (less negative) = farther = better
            return sorted(available, key=score)

        if btype == "Hospital":
            # Prefer nodes with high degree (central)
            return sorted(available,
                          key=lambda n: -self.G.degree(n) + random.uniform(0, 0.5))

        if btype == "PowerPlant":
            industrials = {n for n, t in assignment.items() if t == "Industrial"}
            def pp_score(n):
                if not industrials:
                    return random.random()
                min_d = min(
                    (nx.shortest_path_length(sub, n, ind)
                     if nx.has_path(sub, n, ind) else 999)
                    for ind in industrials
                )
                return min_d  # smaller = closer to industrial = better
            return sorted(available, key=pp_score)

        random.shuffle(available)
        return available

    # ── Pre-flight mathematical checks ─────────────────────────────────
    def _preflight_check(self):
        """
        Detect mathematically impossible configurations before search.
        Raises CSPConflictError with the specific rule and a proposed fix.
        """
        G = self.G
        sub = _blocked_subgraph(G)
        n_nodes = G.number_of_nodes()
        counts = self.building_counts

        # Rule 1: Industrial separation
        # A node adjacent to an Industrial cannot be School or Hospital.
        # Worst case: if all nodes are adjacent to each other (complete graph),
        # you cannot have both Industrial and (School/Hospital).
        if ("Industrial" in counts and
                (counts.get("School", 0) + counts.get("Hospital", 0)) > 0):
            # Check if there exist enough non-adjacent node pairs
            ind_cnt = counts["Industrial"]
            sens_cnt = counts.get("School", 0) + counts.get("Hospital", 0)
            # Each industrial blocks all its neighbors for sensitive buildings.
            # Rough feasibility: need ind_cnt + sens_cnt <= n_nodes and
            # there must exist an independent set structure.
            # We do a soft check here; hard failures caught by search.
            max_degree = max(dict(G.degree()).values())
            if ind_cnt * (max_degree + 1) + sens_cnt > n_nodes:
                raise CSPConflictError(
                    [{
                        "rule": "IndustrialSeparation",
                        "detail": (
                            f"Grid too small: {ind_cnt} Industrial zones each "
                            f"block up to {max_degree} neighbors, leaving "
                            f"insufficient space for {sens_cnt} sensitive buildings."
                        ),
                        "proposed_fix": (
                            f"Reduce Industrial to {max(0, ind_cnt-1)} or "
                            f"reduce Schools+Hospitals to "
                            f"{max(0, sens_cnt-1)}, or increase grid size."
                        )
                    }],
                    {},
                    counts,
                    G
                )

        # Rule 2: Residential-Hospital proximity
        if "Residential" in counts and "Hospital" not in counts:
            raise CSPConflictError(
                [{
                    "rule": "ResidentialHospitalProximity",
                    "detail": (
                        f"{counts['Residential']} Residential zones requested "
                        f"but 0 Hospitals – every Residential must be within "
                        f"3 hops of a Hospital."
                    ),
                    "proposed_fix": "Add at least 1 Hospital."
                }],
                {},
                counts,
                G
            )

        if "Residential" in counts and "Hospital" in counts:
            # Check if a single hospital can cover all residentials in 3 hops
            # (conservative: all hospitals together must cover everything)
            hosp_cnt = counts["Hospital"]
            res_cnt = counts["Residential"]
            # Max nodes within 3 hops of a single node in a grid
            max_coverage = min(n_nodes, 1 + 4*1 + 4*2 + 4*3)  # 3-hop grid ball ≈ 25
            if res_cnt > hosp_cnt * max_coverage:
                raise CSPConflictError(
                    [{
                        "rule": "ResidentialHospitalProximity",
                        "detail": (
                            f"{hosp_cnt} hospital(s) can cover at most "
                            f"~{hosp_cnt * max_coverage} nodes within 3 hops, "
                            f"but {res_cnt} Residential zones are required."
                        ),
                        "proposed_fix": (
                            f"Add at least "
                            f"{math.ceil(res_cnt / max_coverage) - hosp_cnt} "
                            f"more Hospital(s), or reduce Residential count."
                        )
                    }],
                    {},
                    counts,
                    G
                )

        # Rule 3: PowerPlant-Industrial proximity
        if "PowerPlant" in counts and "Industrial" not in counts:
            raise CSPConflictError(
                [{
                    "rule": "PowerPlantIndustrialProximity",
                    "detail": (
                        f"{counts['PowerPlant']} PowerPlant(s) requested but "
                        f"0 Industrial zones – each PowerPlant must be within "
                        f"2 hops of an Industrial zone."
                    ),
                    "proposed_fix": "Add at least 1 Industrial zone."
                }],
                {},
                counts,
                G
            )

    # ── Diagnostics for failed search ──────────────────────────────────
    def _diagnose(self, best_partial):
        """Return a list of conflict dicts explaining what went wrong."""
        conflicts = []
        G = self.G
        counts = self.building_counts

        # Which buildings were not placed?
        placed = defaultdict(int)
        for t in best_partial.values():
            placed[t] += 1
        unplaced = {t: counts[t] - placed.get(t, 0)
                    for t in counts if counts[t] - placed.get(t, 0) > 0}

        if unplaced:
            conflicts.append({
                "rule": "Placement",
                "detail": f"Could not place: {unplaced}",
                "proposed_fix": (
                    "Increase grid size, reduce building counts, or relax "
                    "proximity/separation constraints."
                )
            })

        ok, rule, detail = _all_constraints_ok(best_partial, G)
        if not ok:
            fix_map = {
                "IndustrialSeparation": (
                    "Reduce Industrial count or ensure grid has non-adjacent "
                    "nodes available for Schools/Hospitals."
                ),
                "ResidentialHospitalProximity": (
                    "Add more Hospitals or reduce Residential count."
                ),
                "PowerPlantIndustrialProximity": (
                    "Add more Industrial zones or place PowerPlants closer "
                    "to existing Industrial zones."
                ),
            }
            conflicts.append({
                "rule": rule,
                "detail": detail,
                "proposed_fix": fix_map.get(rule, "Adjust building counts or grid size.")
            })

        return conflicts

    # ── Apply solution to graph ─────────────────────────────────────────
    def _apply_to_graph(self, assignment):
        for node_id, btype in assignment.items():
            self.cg.set_location_type(node_id, btype)


# ─────────────────────────────────────────────
#  Custom exception
# ─────────────────────────────────────────────
class CSPConflictError(Exception):
    """
    Raised when no valid layout exists.

    Attributes
    ----------
    conflicts : list[dict]
        Each dict has keys: 'rule', 'detail', 'proposed_fix'
    best_partial : dict
        Best partial assignment found before failure.
    building_counts : dict
    G : nx.Graph
    """
    def __init__(self, conflicts, best_partial, building_counts, G):
        self.conflicts = conflicts
        self.best_partial = best_partial
        self.building_counts = building_counts
        self.G = G
        super().__init__(self._format())

    def _format(self):
        lines = ["CSP could not find a valid city layout.\n"]
        for c in self.conflicts:
            lines.append(f"  Rule violated : {c['rule']}")
            lines.append(f"  Detail        : {c['detail']}")
            lines.append(f"  Proposed fix  : {c['proposed_fix']}")
            lines.append("")
        return "\n".join(lines)

    def minimum_conflict_proposal(self):
        """
        Return a dict of suggested building_counts that relaxes
        the minimum number of buildings to satisfy all constraints.
        This is a heuristic suggestion, not a guaranteed solve.
        """
        counts = dict(self.building_counts)
        G = self.G
        n_nodes = G.number_of_nodes()

        for c in self.conflicts:
            rule = c["rule"]

            if rule == "IndustrialSeparation":
                # Remove one Industrial
                if counts.get("Industrial", 0) > 0:
                    counts["Industrial"] -= 1

            elif rule == "ResidentialHospitalProximity":
                # Add a hospital
                counts["Hospital"] = counts.get("Hospital", 0) + 1

            elif rule == "PowerPlantIndustrialProximity":
                # Add an industrial
                counts["Industrial"] = counts.get("Industrial", 0) + 1

            elif rule == "Placement":
                # Scale everything down proportionally
                total = sum(counts.values())
                if total > n_nodes:
                    factor = n_nodes / total
                    counts = {k: max(1, int(v * factor)) for k, v in counts.items()}

        return counts


# ─────────────────────────────────────────────
#  Convenience top-level function
# ─────────────────────────────────────────────
def solve_city_layout(city_graph, building_counts, seed=42, max_attempts=300):
    """
    Solve the CSP and mutate city_graph in-place with the result.

    Parameters
    ----------
    city_graph : CityGraph
    building_counts : dict  e.g. {"Hospital": 2, "School": 3}
    seed : int
    max_attempts : int

    Returns
    -------
    assignment : dict {node_id: building_type}

    Raises
    ------
    CSPConflictError  with .conflicts and .minimum_conflict_proposal()
    """
    solver = CityLayoutCSP(city_graph, building_counts, seed=seed,
                            time_limit=max_attempts)  # Use max_attempts as time_limit
    return solver.solve()