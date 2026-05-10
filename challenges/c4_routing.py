import math
import heapq

from core.city_graph import CityGraph
from challenges.c1_layout import LocationType


def _heuristic(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def _astar(cg: CityGraph, start, target):
    if start == target:
        return [start]

    g = cg.g
    open_heap = []
    heapq.heappush(open_heap, (0.0, 0.0, start))

    came_from = {}
    g_cost = {start: 0.0}

    while open_heap:
        _, cost, current = heapq.heappop(open_heap)

        if current == target:
            path = []
            node = current
            while node in came_from:
                path.append(node)
                node = came_from[node]
            path.append(start)
            path.reverse()
            return path

        if cost > g_cost.get(current, math.inf):
            continue

        for neighbor in g.neighbors(current):
            edge = g[current][neighbor]
            if edge.get("blocked", False):
                continue
            new_cost = g_cost[current] + edge["effective_cost"]
            if new_cost < g_cost.get(neighbor, math.inf):
                g_cost[neighbor] = new_cost
                came_from[neighbor] = current
                f = new_cost + _heuristic(neighbor, target)
                heapq.heappush(open_heap, (f, new_cost, neighbor))

    return None

def _find_depot(cg: CityGraph):
    for node, data in cg.nodes(data=True):
        if data.get("type") == LocationType.AMBULANCE_DEPOT:
            return node
    return None


def _pick_next_target(cg: CityGraph, current_pos, remaining_civilians):
    best_civilian = None
    best_path = None
    best_cost = math.inf

    for civilian in remaining_civilians:
        path = _astar(cg, current_pos, civilian)
        if path is None:
            continue
        cost = len(path)
        if cost < best_cost:
            best_cost = cost
            best_civilian = civilian
            best_path = path

    if best_civilian is None:
        return None, None
    return best_civilian, best_path


def init_routing(cg: CityGraph, civilian_nodes: list) -> dict:
    depot = _find_depot(cg)
    if depot is None:
        raise ValueError("No AMBULANCE_DEPOT found in the city graph.")

    remaining = [tuple(c) for c in civilian_nodes]
    current_pos = depot

    current_target, current_path = _pick_next_target(cg, current_pos, remaining)

    return {
        "current_pos":         current_pos,
        "current_path":        current_path if current_path else [],
        "current_target":      current_target,
        "remaining_civilians": remaining,
        "rescued":             [],
        "unreachable":         [],
        "step":                0,
        "done":                len(remaining) == 0 or current_target is None,
        "depot":               depot,
    }


def step_routing(cg: CityGraph, sim_state: dict) -> dict:
    sim_state["step"] += 1
    step = sim_state["step"]

    current_pos    = sim_state["current_pos"]
    current_path   = sim_state["current_path"]
    current_target = sim_state["current_target"]
    if sim_state["done"] or not current_path or len(current_path) < 2:
        sim_state["done"] = True
        return _event("done", sim_state, "Simulation complete — all civilians processed.", step)

    next_node = current_path[1]
    g = cg.g
    edge_blocked = False
    if g.has_edge(current_pos, next_node):
        edge_blocked = g[current_pos][next_node].get("blocked", False)
    else:
        edge_blocked = True

    if edge_blocked:
        remaining_with_target = list(sim_state["remaining_civilians"])
        new_target, new_path = _pick_next_target(cg, current_pos, remaining_with_target)

        if new_target is None:
            sim_state["unreachable"].extend(remaining_with_target)
            sim_state["remaining_civilians"] = []
            sim_state["current_target"] = None
            sim_state["current_path"] = []
            sim_state["done"] = True
            return _event("unreachable", sim_state,
                          f"All remaining civilians unreachable after road block. "
                          f"Stranded: {len(sim_state['unreachable'])}.", step)

        sim_state["current_target"] = new_target
        sim_state["current_path"]   = new_path
        return _event("replan", sim_state,
                      f"Road blocked! Re-planned route to {new_target}.", step)

    sim_state["current_pos"]  = next_node
    sim_state["current_path"] = current_path[1:]
    current_pos = next_node

    if current_pos == current_target:
        sim_state["rescued"].append(current_target)
        sim_state["remaining_civilians"].remove(current_target)

        if not sim_state["remaining_civilians"]:
            sim_state["done"] = True
            sim_state["current_target"] = None
            sim_state["current_path"]   = []
            return _event("done", sim_state,
                          f"Rescued {current_target}! All civilians processed.", step)

        new_target, new_path = _pick_next_target(
            cg, current_pos, sim_state["remaining_civilians"]
        )

        if new_target is None:
            sim_state["unreachable"].extend(sim_state["remaining_civilians"])
            sim_state["remaining_civilians"] = []
            sim_state["current_target"] = None
            sim_state["current_path"]   = []
            sim_state["done"] = True
            return _event("done", sim_state,
                          f"Rescued {current_target}! Remaining civilians are unreachable.", step)

        sim_state["current_target"] = new_target
        sim_state["current_path"]   = new_path
        return _event("rescue", sim_state,
                      f"Rescued civilian at {current_target}! Heading to {new_target}.", step)

    return _event("move", sim_state,
                  f"Moved to {current_pos}. {len(sim_state['current_path']) - 1} steps to target.", step)

def _event(event_type: str, sim_state: dict, message: str, step: int) -> dict:
    return {
        "type":              event_type,
        "current_pos":       list(sim_state["current_pos"]),
        "current_path":      [list(n) for n in sim_state["current_path"]],
        "current_target":    list(sim_state["current_target"]) if sim_state["current_target"] else None,
        "rescued_count":     len(sim_state["rescued"]),
        "unreachable_count": len(sim_state["unreachable"]),
        "rescued":           [list(n) for n in sim_state["rescued"]],
        "unreachable":       [list(n) for n in sim_state["unreachable"]],
        "done":              sim_state["done"],
        "message":           message,
        "step":              step,
    }
