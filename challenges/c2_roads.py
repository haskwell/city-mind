"""
Challenge 2: Road Network Optimization
----------------------------------------
Uses Kruskal's MST + Double Dijkstra to build the road network.

Goal:
  1. Connect every node (grid cell) at the lowest possible total road cost.
  2. Guarantee that the HOSPITAL and AMBULANCE_DEPOT have at least TWO
     completely separate (edge-disjoint) paths between them — so if one
     road floods, a backup route always exists.

Algorithm (4-step process from the design document):
  Step 1 — Kruskal's MST  : Build the cheapest spanning network over all nodes.
  Step 2 — Dijkstra #1    : Find the shortest hospital→depot path on that MST.
  Step 3 — Remove + Dijkstra #2 : Temporarily remove Step-2 edges, run Dijkstra
                                  again to find a completely different second path.
  Step 4 — Merge          : Add both paths back into the final graph.

Input  : A completed Grid object from Challenge 1
Output : A NetworkX graph (G) where edges represent roads with cost weights.

The same NetworkX graph object is shared across ALL challenges.
No module should modify G directly — use the helper methods provided below.

Run standalone:
    python c2_roads.py
"""

import math
import heapq
import networkx as nx

# ── import the Grid and LocationType from Challenge 1 ──────────────────────────
from challenges.c1_layout import Grid, LocationType


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Graph initialisation
# Build the NetworkX graph from the grid produced by Challenge 1.
# Every non-EMPTY cell becomes a node; potential roads between adjacent
# cells become candidate edges with a computed base cost.
# ══════════════════════════════════════════════════════════════════════════════

def build_candidate_edges(grid: Grid) -> list[tuple]:
    """
    Generate ALL potential road edges between adjacent (non-EMPTY) grid cells.

    For every pair of horizontally or vertically adjacent cells that are both
    non-EMPTY, create a candidate edge with a base_cost.

    Base cost formula (use something sensible, e.g.):
        base_cost = 1 + (cell_a.risk_index + cell_b.risk_index)
    You can adjust this formula — just be consistent.

    Returns
    -------
    List of tuples: (base_cost, node_id_a, node_id_b)
        node_id = (row, col) tuple that uniquely identifies each grid cell.
    """
    edges = []

    # TODO: iterate over every cell in the grid
    # For each cell, check its RIGHT neighbor and DOWN neighbor
    # If both cells are non-EMPTY, compute base_cost and append to edges

    # HINT:
    # for r in range(grid.size):
    #     for c in range(grid.size):
    #         cell = grid.get_cell(r, c)
    #         if cell.location_type == LocationType.EMPTY:
    #             continue
    #         # check right neighbor: grid.get_cell(r, c+1)
    #         # check down  neighbor: grid.get_cell(r+1, c)

    return edges  # [(base_cost, (r1,c1), (r2,c2)), ...]


def initialise_graph(grid: Grid) -> nx.Graph:
    """
    Create a NetworkX Graph and add every non-EMPTY cell as a node.

    Node attributes to store (from the design doc):
        - type             : cell.location_type
        - population_density: cell.population_density
        - risk_index       : cell.risk_index
        - accessible       : cell.accessible

    Returns
    -------
    nx.Graph with nodes added but NO edges yet.
    """
    G = nx.Graph()

    # TODO: iterate over grid cells, skip EMPTY ones, add each as a node
    # node id = (row, col)
    # G.add_node((r, c), type=..., population_density=..., risk_index=..., accessible=...)

    return G


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Kruskal's MST
# Connect every node at minimum total cost.
# NetworkX has nx.minimum_spanning_tree() but you may also implement manually
# using a Union-Find / Disjoint Set Union (DSU) structure.
# ══════════════════════════════════════════════════════════════════════════════

class UnionFind:
    """
    Disjoint Set Union (Union-Find) data structure.
    Used by Kruskal's algorithm to detect cycles.
    """

    def __init__(self, nodes):
        # TODO: initialise parent and rank dictionaries for all nodes
        self.parent = {}
        self.rank   = {}
        for node in nodes:
            self.parent[node] = node
            self.rank[node]   = 0

    def find(self, x):
        """Return the root representative of x (with path compression)."""
        # TODO: implement path compression
        # if self.parent[x] != x: self.parent[x] = self.find(self.parent[x])
        # return self.parent[x]
        pass

    def union(self, x, y) -> bool:
        """
        Merge the sets containing x and y.
        Returns True if they were in different sets (edge is safe to add),
        False if they were already connected (would form a cycle).
        """
        # TODO: implement union by rank
        pass


def kruskal_mst(G: nx.Graph, candidate_edges: list) -> list[tuple]:
    """
    Run Kruskal's algorithm on candidate_edges to find the Minimum Spanning Tree.

    Parameters
    ----------
    G               : The NetworkX graph (nodes already added).
    candidate_edges : List of (base_cost, node_a, node_b) from build_candidate_edges().

    Returns
    -------
    List of MST edges: [(node_a, node_b, base_cost), ...]

    Steps:
      1. Sort candidate_edges by base_cost (ascending).
      2. Initialise UnionFind with all nodes in G.
      3. Iterate sorted edges; add edge to MST if it doesn't form a cycle (uf.union).
      4. Stop when MST has (num_nodes - 1) edges.
    """
    mst_edges = []

    # TODO: implement Kruskal's here

    return mst_edges


def add_mst_to_graph(G: nx.Graph, mst_edges: list) -> None:
    """
    Add the MST edges into the NetworkX graph G.

    Each edge should store:
        - base_cost     : the raw cost computed earlier
        - blocked       : False (no road is blocked at start)
        - effective_cost: same as base_cost initially
                          (will be updated when risk scores arrive from Challenge 5)

    G.add_edge(u, v, base_cost=..., blocked=False, effective_cost=...)
    """
    # TODO: loop over mst_edges and add each to G
    pass


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Dijkstra's Shortest Path
# Used twice (Double Dijkstra) to find two edge-disjoint paths between
# the HOSPITAL and AMBULANCE_DEPOT.
# ══════════════════════════════════════════════════════════════════════════════

def dijkstra(G: nx.Graph, source, target, excluded_edges: set = None) -> list | None:
    """
    Standard Dijkstra's algorithm on graph G using edge attribute 'effective_cost'.

    Parameters
    ----------
    G               : NetworkX graph with edges having 'effective_cost' attribute.
    source          : Starting node id (row, col).
    target          : Goal node id (row, col).
    excluded_edges  : A set of frozenset({u, v}) pairs to SKIP during traversal.
                      Used in the second Dijkstra run to force a different path.

    Returns
    -------
    List of node ids representing the shortest path [source, ..., target],
    or None if no path exists.

    Algorithm:
      - Use a min-heap (priority queue): heapq
      - dist[node] = best known distance from source
      - prev[node] = previous node on best path (for path reconstruction)
      - Skip edges in excluded_edges
      - Stop when target is popped from the heap
    """
    if excluded_edges is None:
        excluded_edges = set()

    dist = {node: math.inf for node in G.nodes}
    dist[source] = 0
    prev = {node: None for node in G.nodes}
    heap = [(0, source)]   # (cost, node)

    # TODO: implement Dijkstra using heapq
    # while heap:
    #     cost, u = heapq.heappop(heap)
    #     if cost > dist[u]: continue
    #     if u == target: break
    #     for v in G.neighbors(u):
    #         edge = G[u][v]
    #         if frozenset({u, v}) in excluded_edges: continue
    #         if edge.get('blocked', False): continue
    #         new_cost = dist[u] + edge['effective_cost']
    #         if new_cost < dist[v]:
    #             dist[v] = new_cost
    #             prev[v] = u
    #             heapq.heappush(heap, (new_cost, v))

    # TODO: reconstruct and return path using prev[]
    # if dist[target] == math.inf: return None
    # path = []
    # node = target
    # while node is not None:
    #     path.append(node)
    #     node = prev[node]
    # return list(reversed(path))

    return None  # replace with actual return


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — Double Dijkstra (Hospital ↔ Depot redundancy)
# Ensures the hospital and ambulance depot always have a backup road.
# ══════════════════════════════════════════════════════════════════════════════

def find_hospital_and_depot(G: nx.Graph) -> tuple:
    """
    Scan graph nodes to locate the HOSPITAL node and the AMBULANCE_DEPOT node.

    Returns
    -------
    (hospital_node, depot_node) where each is a (row, col) tuple,
    or (None, None) if either is missing.
    """
    hospital = None
    depot    = None

    # TODO: iterate G.nodes(data=True) and find nodes where data['type'] matches
    # LocationType.HOSPITAL and LocationType.AMBULANCE_DEPOT

    return hospital, depot


def double_dijkstra_redundancy(G: nx.Graph, hospital, depot) -> tuple[list, list]:
    """
    Find two edge-disjoint paths between hospital and depot.

    Step 2: Run Dijkstra #1 on the current MST graph → path1
    Step 3: Collect all edges in path1 into excluded_edges set.
            Run Dijkstra #2 with those edges excluded → path2
    Step 4: The edges of path2 that aren't already in G get added as new roads.

    Parameters
    ----------
    G        : NetworkX graph (MST edges already added).
    hospital : node id of the hospital.
    depot    : node id of the ambulance depot.

    Returns
    -------
    (path1, path2) — two lists of node ids.
    path2 may be None if no second path is possible (warn the user).
    """
    # --- Dijkstra #1 ---
    path1 = dijkstra(G, hospital, depot)

    if path1 is None:
        print("[C2] WARNING: No path found between hospital and depot!")
        return None, None

    # --- Build excluded_edges from path1 ---
    excluded_edges = set()
    # TODO: iterate consecutive pairs in path1 and add frozenset({u, v}) to excluded_edges

    # --- Dijkstra #2 (forced different route) ---
    path2 = dijkstra(G, hospital, depot, excluded_edges=excluded_edges)

    if path2 is None:
        print("[C2] WARNING: No second independent path found. Redundancy not guaranteed.")

    return path1, path2


def add_redundancy_edges(G: nx.Graph, path2: list) -> None:
    """
    Add any edges from path2 that are NOT already in G.
    These are the 'extra' roads that create the backup route.

    Each new edge gets the same attributes as MST edges:
        base_cost, blocked=False, effective_cost
    """
    if path2 is None:
        return

    # TODO: iterate consecutive pairs in path2
    # if G.has_edge(u, v): skip (already there from MST)
    # else: compute base_cost and add to G
    pass


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — Graph update helpers (used by other challenges)
# All other modules MUST use these methods instead of touching G directly.
# ══════════════════════════════════════════════════════════════════════════════

def block_road(G: nx.Graph, u, v) -> None:
    """
    Mark the road between u and v as blocked (e.g., flooded).
    Sets edge attribute 'blocked' = True.
    Used by Challenge 4 during the live simulation.
    """
    if G.has_edge(u, v):
        G[u][v]['blocked'] = True
        print(f"[C2] Road {u} ↔ {v} is now BLOCKED.")
    else:
        print(f"[C2] WARNING: Tried to block non-existent road {u} ↔ {v}.")


def unblock_road(G: nx.Graph, u, v) -> None:
    """Restore a previously blocked road."""
    if G.has_edge(u, v):
        G[u][v]['blocked'] = False


def update_effective_cost(G: nx.Graph, risk_multipliers: dict) -> None:
    """
    Recalculate effective_cost for every edge based on risk scores.
    Called by Challenge 5 after crime risk scores have been assigned.

    Parameters
    ----------
    risk_multipliers : dict mapping node_id → multiplier (1.0 / 1.2 / 1.5)

    Formula:
        effective_cost = base_cost
                         × risk_multipliers.get(u, 1.0)
                         × risk_multipliers.get(v, 1.0)
    """
    # TODO: iterate G.edges(data=True) and update each edge's effective_cost
    pass


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — Main entry point
# ══════════════════════════════════════════════════════════════════════════════

def run_roads(grid: Grid) -> nx.Graph:
    """
    Full Challenge 2 pipeline. Called by the simulation runner.

    Steps
    -----
    1. Build candidate edges from the grid.
    2. Initialise the NetworkX graph (nodes only).
    3. Run Kruskal's MST → add MST edges to G.
    4. Find hospital + depot nodes.
    5. Run Double Dijkstra → add redundancy edges to G.
    6. Print summary and return G.

    Parameters
    ----------
    grid : Completed Grid object from Challenge 1 (run_layout).

    Returns
    -------
    nx.Graph — the shared city graph used by all subsequent challenges.
    """
    print("[C2] Building road network...")

    # Step 1
    candidate_edges = build_candidate_edges(grid)
    print(f"[C2] {len(candidate_edges)} candidate road(s) found.")

    # Step 2
    G = initialise_graph(grid)
    print(f"[C2] Graph initialised with {G.number_of_nodes()} node(s).")

    # Step 3
    mst_edges = kruskal_mst(G, candidate_edges)
    add_mst_to_graph(G, mst_edges)
    print(f"[C2] MST built with {G.number_of_edges()} road(s).")

    # Step 4
    hospital, depot = find_hospital_and_depot(G)
    if hospital is None or depot is None:
        print("[C2] WARNING: Hospital or depot not found — skipping redundancy step.")
        return G

    print(f"[C2] Hospital at {hospital}, Depot at {depot}.")

    # Step 5
    path1, path2 = double_dijkstra_redundancy(G, hospital, depot)
    add_redundancy_edges(G, path2)

    if path1:
        print(f"[C2] Primary path   ({len(path1)-1} edges): {path1}")
    if path2:
        print(f"[C2] Secondary path ({len(path2)-1} edges): {path2}")

    print(f"[C2] Final road network: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges.")
    return G


# ── Standalone test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from challenges.c1_layout import run_layout, LocationType

    # Small test grid
    grid_size = 6
    required_counts = {
        LocationType.RESIDENTIAL:     8,
        LocationType.HOSPITAL:        1,
        LocationType.SCHOOL:          2,
        LocationType.INDUSTRIAL:      2,
        LocationType.POWER_PLANT:     1,
        LocationType.AMBULANCE_DEPOT: 1,
    }

    print("=== Running Challenge 1 (layout) ===")
    grid, violations = run_layout(grid_size, required_counts)
    grid.display()

    print("\n=== Running Challenge 2 (roads) ===")
    G = run_roads(grid)

    print(f"\nNodes : {list(G.nodes)[:5]} ...")
    print(f"Edges : {list(G.edges(data=True))[:3]} ...")