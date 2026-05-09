import math
from collections import deque
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from challenges.c1_layout import LocationType


def _build_industry_dist(city_graph):
    industrial_nodes = [
        n for n, d in city_graph.nodes(data=True)
        if d.get("type") == LocationType.INDUSTRIAL
    ]

    dist = {n: math.inf for n, _ in city_graph.nodes(data=True)}

    queue = deque()
    for src in industrial_nodes:
        dist[src] = 0
        queue.append(src)

    while queue:
        node = queue.popleft()
        for neighbor in city_graph.neighbors(node):
            if dist[neighbor] == math.inf:
                dist[neighbor] = dist[node] + 1
                queue.append(neighbor)

    max_finite = max((v for v in dist.values() if v != math.inf), default=1)
    for node in dist:
        if dist[node] == math.inf:
            dist[node] = max_finite + 1

    return dist


def _build_feature_matrix(city_graph):
    industry_dist = _build_industry_dist(city_graph)

    nodes = []
    features = []

    for node, data in city_graph.nodes(data=True):
        loc_type = data.get("type")
        if not loc_type or loc_type == LocationType.EMPTY:
            continue
        pop_density = data.get("population_density", 0.0)
        dist = industry_dist.get(node, 0)
        row, col = node
        nodes.append(node)
        features.append([pop_density, dist, row, col])

    if len(nodes) == 0:
        return nodes, np.array([]).reshape(0, 4)

    X = np.array(features, dtype=float)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    return nodes, X_scaled


def _pick_k(X, k_max=8):
    n_samples = len(X)
    if n_samples < 4:
        return 2

    k_max = min(k_max, n_samples - 1)
    if k_max < 2:
        return 2

    inertias = []
    k_range = range(2, k_max + 1)

    for k in k_range:
        km = KMeans(n_clusters=k, n_init=10, random_state=42)
        km.fit(X)
        inertias.append(km.inertia_)

    if len(inertias) < 3:
        return 2

    deltas = [inertias[i] - inertias[i + 1] for i in range(len(inertias) - 1)]
    second_deriv = [deltas[i] - deltas[i + 1] for i in range(len(deltas) - 1)]
    elbow_idx = int(np.argmax(second_deriv))
    return list(k_range)[elbow_idx + 1]


def run_kmeans(city_graph, k=0):
    nodes, X = _build_feature_matrix(city_graph)

    if len(nodes) == 0:
        return {}

    if k == 0:
        k = _pick_k(X)

    k = max(2, min(k, len(nodes)))

    km = KMeans(n_clusters=k, n_init=10, random_state=42)
    labels = km.fit_predict(X)

    return {node: int(label) for node, label in zip(nodes, labels)}


def run_crime(city_graph, k=0):
    cluster_map = run_kmeans(city_graph, k=k)

    cluster_labels = {f"[{node[0]}, {node[1]}]": label for node, label in cluster_map.items()}

    return {
        "cluster_labels": cluster_labels,
        "risk_levels":    {},
        "explanations":   {},
        "high_count":     0,
        "medium_count":   0,
        "low_count":      0,
        "model_analysis": {},
    }