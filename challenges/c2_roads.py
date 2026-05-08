import math
import heapq
import networkx as nx

from challenges.c1_layout import Grid, LocationType
from core.city_graph import CityGraph


def _edge_base_cost(cell_a, cell_b) -> float:
    return 1.0 + cell_a.risk_index + cell_b.risk_index


def build_candidate_edges(grid: Grid) -> list:
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
        self.rank = {n: 0 for n in nodes}

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
    mst_edges = []
    sorted_edges = sorted(candidate_edges, key=lambda e: e[0])
    uf = UnionFind(list(cg.nodes()))
    num_nodes = cg.number_of_nodes()

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
        cg.add_edge(u, v, base_cost=cost, blocked=False, effective_cost=cost, redundancy=False)


def dijkstra(cg: CityGraph, source, target, excluded_edges: set = None) -> list | None:
    if excluded_edges is None:
        excluded_edges = set()

    g = cg.g
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

    path = []
    node = target
    while node is not None:
        path.append(node)
        node = prev[node]
    return list(reversed(path))


def find_hospital_and_depot(cg: CityGraph) -> tuple:
    hospital = None
    depot = None

    for node, data in cg.nodes(data=True):
        if data.get("type") == LocationType.PRIMARY_HOSPITAL:
            hospital = node
        elif data.get("type") == LocationType.AMBULANCE_DEPOT:
            depot = node
        if hospital and depot:
            break
    return hospital, depot


def _dijkstra_on_nx(g: nx.Graph, source, target, excluded_edges: set = None) -> list | None:
    if excluded_edges is None:
        excluded_edges = set()

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

    path = []
    node = target
    while node is not None:
        path.append(node)
        node = prev[node]
    return list(reversed(path))


def double_dijkstra_redundancy(cg: CityGraph, hospital, depot, candidate_edges: list) -> tuple:
    path1 = dijkstra(cg, hospital, depot)

    if path1 is None:
        print("[C2] WARNING: No path found between hospital and depot!")
        return None, None

    node_data = dict(cg.nodes(data=True))
    augmented = cg.g.copy()
    for cost, u, v in candidate_edges:
        if not augmented.has_edge(u, v):
            augmented.add_edge(u, v, base_cost=cost, blocked=False, effective_cost=cost, redundancy=True)

    excluded_edges = set()
    for i in range(len(path1) - 1):
        excluded_edges.add(frozenset({path1[i], path1[i + 1]}))

    path2 = _dijkstra_on_nx(augmented, hospital, depot, excluded_edges=excluded_edges)

    if path2 is None:
        print("[C2] WARNING: No second independent path found. Redundancy not guaranteed.")

    return path1, path2


def add_redundancy_edges(cg: CityGraph, path2: list) -> None:
    if path2 is None:
        return
    node_data = dict(cg.nodes(data=True))
    for i in range(len(path2) - 1):
        u, v = path2[i], path2[i + 1]
        if cg.has_edge(u, v):
            continue
        cost = 1.0 + node_data[u].get("risk_index", 0.0) + node_data[v].get("risk_index", 0.0)
        cg.add_edge(u, v, base_cost=cost, blocked=False, effective_cost=cost, redundancy=True)


def block_road(cg: CityGraph, u, v) -> None:
    cg.block_road(u, v)
    print(f"[C2] Road {u} ↔ {v} is now BLOCKED.")


def unblock_road(cg: CityGraph, u, v) -> None:
    cg.unblock_road(u, v)


def update_effective_cost(cg: CityGraph, risk_multipliers: dict) -> None:
    cg.update_effective_costs(risk_multipliers)


def run_roads(grid: Grid) -> tuple:
    print("[C2] Building road network...")

    candidate_edges = build_candidate_edges(grid)
    print(f"[C2] {len(candidate_edges)} candidate road(s) found.")

    cg = initialise_graph(grid)
    print(f"[C2] Graph initialised with {cg.number_of_nodes()} node(s).")

    mst_edges = kruskal_mst(cg, candidate_edges)
    add_mst_to_graph(cg, mst_edges)
    print(f"[C2] MST built with {cg.number_of_edges()} road(s).")

    hospital, depot = find_hospital_and_depot(cg)
    if hospital is None or depot is None:
        print("[C2] WARNING: Hospital or depot not found — skipping redundancy step.")
        return cg, None, None

    print(f"[C2] Hospital at {hospital}, Depot at {depot}.")

    path1, path2 = double_dijkstra_redundancy(cg, hospital, depot, candidate_edges)
    add_redundancy_edges(cg, path2)

    if path1:
        print(f"[C2] Primary path   ({len(path1)-1} edges): {path1}")
    if path2:
        print(f"[C2] Secondary path ({len(path2)-1} edges): {path2}")

    print(f"[C2] Final road network: {cg.number_of_nodes()} nodes, {cg.number_of_edges()} edges.")
    return cg, path1, path2