import math
from collections import deque
import numpy as np
from sklearn.ensemble import RandomForestClassifier
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


def _generate_fake_training_data():
    rng = np.random.default_rng(42)
    n = 2000

    pop = rng.uniform(0, 500, n)
    dist = rng.uniform(0, 15, n)

    labels = []
    for p, d in zip(pop, dist):
        if p > 300 or d <= 1:
            labels.append("High")
        elif p < 100 and d > 3:
            labels.append("Low")
        else:
            labels.append("Medium")

    X = np.column_stack([pop, dist])
    return X, labels


def _train_rf(X_train, y_train):
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    return model


def _extract_node_features(city_graph, industry_dist):
    result = []
    for node, data in city_graph.nodes(data=True):
        loc_type = data.get("type")
        if not loc_type or loc_type == LocationType.EMPTY:
            continue
        pop_density = data.get("population_density", 0.0)
        dist = industry_dist.get(node, 0)
        result.append((node, [pop_density, dist]))
    return result


def _predict_risk(model, node_features):
    if not node_features:
        return {}
    nodes = [nf[0] for nf in node_features]
    X = np.array([nf[1] for nf in node_features], dtype=float)
    predictions = model.predict(X)
    return {node: pred for node, pred in zip(nodes, predictions)}


def _build_explanations(node_risk_map, industry_dist, city_graph):
    explanations = {}
    for node, risk in node_risk_map.items():
        node_data = dict(city_graph.g.nodes[node])
        pop = node_data.get("population_density", 0.0)
        dist = industry_dist.get(node, 0)

        if pop > 300:
            pop_label = "High density"
        elif pop > 100:
            pop_label = "Medium density"
        else:
            pop_label = "Low density"

        if dist <= 1:
            dist_label = "Adjacent to industrial"
        elif dist <= 3:
            dist_label = "Near industrial"
        else:
            dist_label = "Far from industrial"

        explanations[node] = f"{pop_label} | {dist_label} | {risk} risk"

    return explanations


def _write_risk_to_graph(city_graph, node_risk_map):
    risk_values = {"High": 1.5, "Medium": 1.2, "Low": 1.0}
    for node, risk in node_risk_map.items():
        city_graph.g.nodes[node]["risk_index"] = risk_values[risk]
    city_graph.update_effective_costs()


def run_risk_prediction(city_graph):
    industry_dist = _build_industry_dist(city_graph)
    X_train, y_train = _generate_fake_training_data()
    model = _train_rf(X_train, y_train)
    node_features = _extract_node_features(city_graph, industry_dist)
    node_risk_map = _predict_risk(model, node_features)

    if not node_risk_map:
        return {
            "risk_levels": {},
            "explanations": {},
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0,
            "model_analysis": {},
            "error": "No valid nodes for risk prediction"
        }
    explanations = _build_explanations(node_risk_map, industry_dist, city_graph)
    _write_risk_to_graph(city_graph, node_risk_map)
    risk_levels = {f"[{node[0]}, {node[1]}]": risk for node, risk in node_risk_map.items()}
    explanations_out = {f"[{node[0]}, {node[1]}]": exp for node, exp in explanations.items()}
    counts = {"High": 0, "Medium": 0, "Low": 0}
    for risk in node_risk_map.values():
        counts[risk] += 1

    model_analysis = {
        "population_density": float(model.feature_importances_[0]),
        "dist_to_industry": float(model.feature_importances_[1]),
    }

    return {
        "risk_levels": risk_levels,
        "explanations": explanations_out,
        "high_count": counts["High"],
        "medium_count": counts["Medium"],
        "low_count": counts["Low"],
        "model_analysis": model_analysis,
        "n_samples": len(node_risk_map)
    }
