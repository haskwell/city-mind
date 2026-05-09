import math
import heapq

from challenges.c1_layout import Grid, LocationType
from core.city_graph import CityGraph

def _edge_base_cost(cell_a, cell_b) -> float:
    if (cell_a.location_type == LocationType.RESIDENTIAL
            or cell_b.location_type == LocationType.RESIDENTIAL):
        return 0.8
    return 1.0


def build_candidate_edges(grid: Grid) -> list:
    """Return every valid adjacent-cell pair as a (cost, u, v) tuple."""
    edges = []
    for r in range(grid.size):
        for c in range(grid.size):
            cell = grid.get_cell(r, c)
            if cell.location_type == LocationType.EMPTY:
                continue

            right = grid.get_cell(r, c + 1)
            if right is not None and right.location_type != LocationType.EMPTY:
                cost = _edge_base_cost(cell, right)
                edges.append((cost, (r, c), (r, c + 1)))

            down = grid.get_cell(r + 1, c)
            if down is not None and down.location_type != LocationType.EMPTY:
                cost = _edge_base_cost(cell, down)
                edges.append((cost, (r, c), (r + 1, c)))

    return edges

def initialise_graph(grid: Grid) -> CityGraph:
    cg = CityGraph()
    for r in range(grid.size):
        for c in range(grid.size):
            cell = grid.get_cell(r, c)
            if cell.location_type == LocationType.EMPTY:
                continue
            cg.add_node(
                (r, c),
                type=cell.location_type,
                population_density=cell.population_density,
                risk_index=cell.risk_index,
                accessible=cell.accessible,
            )
    return cg

class UnionFind:
    def __init__(self, nodes):
        self.parent = {n: n for n in nodes}
        self.rank   = {n: 0  for n in nodes}

    def find(self, x):
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x, y) -> bool:
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return False
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1
        return True

def kruskal_mst(cg: CityGraph, candidate_edges: list) -> list:
    mst_edges    = []
    sorted_edges = sorted(candidate_edges, key=lambda e: e[0])
    uf           = UnionFind(list(cg.nodes()))
    num_nodes    = cg.number_of_nodes()

    for cost, u, v in sorted_edges:
        if u not in uf.parent or v not in uf.parent:
            continue
        if uf.union(u, v):
            mst_edges.append((u, v, cost))
            if len(mst_edges) == num_nodes - 1:
                break

    return mst_edges

def add_mst_to_graph(cg: CityGraph, mst_edges: list) -> None:
    for u, v, cost in mst_edges:
        cg.add_edge(u, v, base_cost=cost, blocked=False,
                    effective_cost=cost, redundancy=False)

def _build_tree_adjacency(mst_edges: list) -> dict:
    adj = {}
    for u, v, cost in mst_edges:
        adj.setdefault(u, []).append((v, cost))
        adj.setdefault(v, []).append((u, cost))
    return adj


def _path_in_tree(adj: dict, source, target) -> list | None:
    if source == target:
        return []

    visited = {source}
    queue   = [(source, [])]

    while queue:
        node, path = queue.pop(0)
        for neighbour, _ in adj.get(node, []):
            if neighbour in visited:
                continue
            visited.add(neighbour)
            new_path = path + [frozenset({node, neighbour})]
            if neighbour == target:
                return new_path
            queue.append((neighbour, new_path))

    return None

def greedy_bridge_augmentation(cg: CityGraph,
                                mst_edges: list,
                                candidate_edges: list) -> list:
    graph_nodes  = set(cg.nodes())
    mst_edge_set = {frozenset({u, v}) for u, v, _ in mst_edges}

    uncovered_bridges = set(mst_edge_set)
    tree_adj = _build_tree_adjacency(mst_edges)

    # Pre-compute coverage for every non-tree candidate edge once up front.
    # coverage_map: (u, v) -> (cost, frozenset of bridges it covers)
    coverage_map: dict = {}
    for cost, u, v in candidate_edges:
        if frozenset({u, v}) in mst_edge_set:
            continue
        if u not in graph_nodes or v not in graph_nodes:
            continue
        path_edges = _path_in_tree(tree_adj, u, v)
        if path_edges:
            coverage_map[(u, v)] = (cost, frozenset(path_edges))

    augmentation_edges = []

    while uncovered_bridges:
        best_key      = None
        best_count    = 0
        best_cost     = math.inf

        for (u, v), (cost, covered_set) in coverage_map.items():
            count = len(uncovered_bridges & covered_set)
            if count > best_count or (count == best_count and cost < best_cost):
                best_key   = (u, v)
                best_count = count
                best_cost  = cost

        if best_key is None or best_count == 0:
            print(f"[C2] WARNING: {len(uncovered_bridges)} bridge(s) could "
                  f"not be covered — some nodes may lack a redundant path.")
            break

        u, v = best_key
        cost = coverage_map[best_key][0]
        augmentation_edges.append((u, v, cost))

        uncovered_bridges -= coverage_map[best_key][1]
        del coverage_map[best_key]

    return augmentation_edges


def add_augmentation_edges(cg: CityGraph, augmentation_edges: list) -> None:
    for u, v, cost in augmentation_edges:
        if cg.has_edge(u, v):
            continue
        cg.add_edge(u, v, base_cost=cost, blocked=False,
                    effective_cost=cost, redundancy=True)

def dijkstra(cg: CityGraph, source, target,
             excluded_edges: set = None) -> list | None:
    if excluded_edges is None:
        excluded_edges = set()

    g    = cg.g
    dist = {node: math.inf for node in g.nodes}
    dist[source] = 0
    prev = {node: None for node in g.nodes}
    heap = [(0, source)]

    while heap:
        cost, u = heapq.heappop(heap)
        if cost > dist[u]:
            continue
        if u == target:
            break
        for v in g.neighbors(u):
            edge = g[u][v]
            if frozenset({u, v}) in excluded_edges:
                continue
            if edge.get("blocked", False):
                continue
            new_cost = dist[u] + edge["effective_cost"]
            if new_cost < dist[v]:
                dist[v] = new_cost
                prev[v] = u
                heapq.heappush(heap, (new_cost, v))

    if dist[target] == math.inf:
        return None

    path, node = [], target
    while node is not None:
        path.append(node)
        node = prev[node]
    return list(reversed(path))

def find_hospital_and_depot(cg: CityGraph) -> tuple:
    hospital = None
    depot    = None
    for node, data in cg.nodes(data=True):
        if data.get("type") == LocationType.PRIMARY_HOSPITAL:
            hospital = node
        elif data.get("type") == LocationType.AMBULANCE_DEPOT:
            depot = node
        if hospital and depot:
            break
    return hospital, depot


def block_road(cg: CityGraph, u, v) -> None:
    cg.block_road(u, v)
    print(f"[C2] Road {u} ↔ {v} is now BLOCKED.")


def unblock_road(cg: CityGraph, u, v) -> None:
    cg.unblock_road(u, v)

def run_roads(grid: Grid) -> CityGraph:
    print("[C2] Building road network...")

    candidate_edges = build_candidate_edges(grid)
    print(f"[C2] {len(candidate_edges)} candidate road(s) found.")

    cg = initialise_graph(grid)
    print(f"[C2] Graph initialised with {cg.number_of_nodes()} node(s).")

    mst_edges = kruskal_mst(cg, candidate_edges)
    add_mst_to_graph(cg, mst_edges)
    print(f"[C2] MST built with {cg.number_of_edges()} road(s).")

    augmentation_edges = greedy_bridge_augmentation(cg, mst_edges, candidate_edges)
    add_augmentation_edges(cg, augmentation_edges)
    print(f"[C2] Bridge augmentation added {len(augmentation_edges)} extra road(s).")

    print(f"[C2] Final road network: {cg.number_of_nodes()} nodes, "
          f"{cg.number_of_edges()} edges.")

    return cg