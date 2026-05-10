import math
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from challenges.c1_layout import LocationType


def _build_feature_matrix(city_graph):
    nodes = []
    features = []

    for node, data in city_graph.nodes(data=True):
        loc_type = data.get("type")
        if not loc_type or loc_type == LocationType.EMPTY:
            continue
        pop_density = data.get("population_density", 0.0)
        row, col = node
        nodes.append(node)
        features.append([pop_density, row, col])

    if len(nodes) == 0:
        return nodes, np.array([]).reshape(0, 3)

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


def run_clustering(city_graph, k=0):
    nodes, X = _build_feature_matrix(city_graph)

    if len(nodes) == 0:
        return {
            "cluster_labels": {},
            "k_used": 0,
            "error": "No valid nodes for clustering"
        }

    if k == 0:
        k = _pick_k(X)

    k = max(2, min(k, len(nodes)))

    km = KMeans(n_clusters=k, n_init=10, random_state=42)
    labels = km.fit_predict(X)

    cluster_map = {node: int(label) for node, label in zip(nodes, labels)}
    cluster_labels = {f"[{node[0]}, {node[1]}]": label for node, label in cluster_map.items()}

    return {
        "cluster_labels": cluster_labels,
        "k_used": k,
        "inertia": float(km.inertia_),
        "n_samples": len(nodes)
    }
