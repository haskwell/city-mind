import math
import heapq

from core.city_graph import CityGraph
from challenges.c1_layout import LocationType

NUM_OFFICERS = 10
MIN_HOP_SPREAD = 2


def _dijkstra_single(cg: CityGraph, source) -> dict:
    g = cg.g
    dist = {node: math.inf for node in g.nodes}
    dist[source] = 0
    heap = [(0.0, source)]
    while heap:
        cost, u = heapq.heappop(heap)
        if cost > dist[u]:
            continue
        for v in g.neighbors(u):
            edge = g[u][v]
            if edge.get("blocked", False):
                continue
            new_cost = cost + edge["effective_cost"]
            if new_cost < dist[v]:
                dist[v] = new_cost
                heapq.heappush(heap, (new_cost, v))
    return dist


def _bfs_hops(cg: CityGraph, source) -> dict:
    g = cg.g
    hops = {source: 0}
    queue = [source]
    while queue:
        node = queue.pop(0)
        for v in g.neighbors(node):
            if v not in hops:
                hops[v] = hops[node] + 1
                queue.append(v)
    return hops


def _get_candidate_nodes(cg: CityGraph) -> list:
    excluded = {LocationType.EMPTY}
    return [n for n, d in cg.nodes(data=True) if d.get("type") not in excluded]


def _risk_priority(cg: CityGraph, node) -> int:
    risk_order = {"High": 0, "Medium": 1, "Low": 2}
    risk = cg.g.nodes[node].get("risk_index", 1.0)
    if risk >= 1.5:
        return 0
    elif risk >= 1.2:
        return 1
    else:
        return 2


def _too_close(cg: CityGraph, placed: list, candidate, min_hops: int) -> bool:
    hops = _bfs_hops(cg, candidate)
    for p in placed:
        if hops.get(p, math.inf) < min_hops:
            return True
    return False


def run_police(cg: CityGraph) -> dict:
    print("[C6] Starting police officer placement (Greedy)...")

    candidates = _get_candidate_nodes(cg)
    if not candidates:
        return {"placements": [], "coverage": {}}

    candidates.sort(key=lambda n: _risk_priority(cg, n))

    placed = []
    for node in candidates:
        if len(placed) >= NUM_OFFICERS:
            break
        if not _too_close(cg, placed, node, MIN_HOP_SPREAD):
            placed.append(node)

    if len(placed) < NUM_OFFICERS:
        for node in candidates:
            if len(placed) >= NUM_OFFICERS:
                break
            if node not in placed:
                placed.append(node)

    all_nodes = [n for n, d in cg.nodes(data=True) if d.get("type") not in {LocationType.EMPTY}]
    coverage = {}
    for node in all_nodes:
        hops = _bfs_hops(cg, node)
        coverage[node] = min(hops.get(p, math.inf) for p in placed)

    print(f"[C6] Officers placed at: {placed}")
    return {
        "placements": placed,
        "coverage": coverage,
    }