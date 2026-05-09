import numpy as np
from collections import deque
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


INDUSTRIAL_TYPES = {"INDUSTRIAL"}
EMPTY_TYPES = {"EMPTY"}


def _get_industrial_nodes(cg):
    return [
        node for node, data in cg.nodes(data=True)
        if data.get("type") in INDUSTRIAL_TYPES
    ]


def _bfs_dist_to_industrial(cg, start, industrial_nodes):
    if not industrial_nodes:
        return 999

    industrial_set = set(industrial_nodes)

    if start in industrial_set:
        return 0

    visited = {start}
    queue = deque([(start, 0)])

    while queue:
        node, dist = queue.popleft()
        for neighbor in cg.neighbors(node):
            if neighbor in industrial_set:
                return dist + 1
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, dist + 1))

    return 999


def _build_feature_matrix(cg):
    industrial_nodes = _get_industrial_nodes(cg)

    nodes = []
    features = []

    for node, data in cg.nodes(data=True):
        if data.get("type") in EMPTY_TYPES or data.get("type") is None:
            continue

        density = data.get("population_density", 0.0)
        dist = _bfs_dist_to_industrial(cg, node, industrial_nodes)

        nodes.append(node)
        features.append([density, dist])

    return nodes, np.array(features, dtype=float)


def _pick_k(X, max_k=6):
    if len(X) <= 2:
        return 2

    max_k = min(max_k, len(X) - 1)
    inertias = []

    for k in range(2, max_k + 1):
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        km.fit(X)
        inertias.append(km.inertia_)

    deltas = [inertias[i] - inertias[i + 1] for i in range(len(inertias) - 1)]
    best_idx = int(np.argmax(deltas))
    return best_idx + 2


def run_crime(cg, k=0):
    nodes, X = _build_feature_matrix(cg)

    if len(nodes) == 0:
        return {
            "cluster_labels": {},
            "risk_levels":    {},
            "explanations":   {},
            "model_analysis": {},
            "high_count":     0,
            "medium_count":   0,
            "low_count":      0,
        }

    if k <= 0:
        k = _pick_k(X)

    k = min(k, len(nodes))
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    km.fit(X_scaled)
    labels = km.labels_

    cluster_labels = {}
    for node, label in zip(nodes, labels):
        key = str(list(node))
        cluster_labels[key] = int(label)

    risk_levels   = {str(list(n)): "Low"  for n in nodes}
    explanations  = {str(list(n)): "RF not yet implemented" for n in nodes}
    model_analysis = {"population_density": 0.0, "dist_to_industrial": 0.0, "location_type": 0.0}

    print("[C5] risk_index BEFORE update:")
    for node, data in cg.nodes(data=True):
        if data.get("type") in EMPTY_TYPES or data.get("type") is None:
            continue
        print(f"  {list(node)} ({data.get('type')}) -> {data.get('risk_index', 0.0)}")

    for node, data in cg.nodes(data=True):
        if data.get("type") in EMPTY_TYPES or data.get("type") is None:
            continue
        cg.g.nodes[node]["risk_index"] = 0.1

    cg.update_effective_costs()

    print("[C5] risk_index AFTER update:")
    for node, data in cg.nodes(data=True):
        if data.get("type") in EMPTY_TYPES or data.get("type") is None:
            continue
        print(f"  {list(node)} ({data.get('type')}) -> {data.get('risk_index', 0.0)}")

    return {
        "cluster_labels": cluster_labels,
        "risk_levels":    risk_levels,
        "explanations":   explanations,
        "model_analysis": model_analysis,
        "high_count":     0,
        "medium_count":   0,
        "low_count":      len(nodes),
    }