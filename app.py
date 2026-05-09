import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, render_template, request, jsonify
from challenges.c1_layout import run_layout, LocationType
from util.save_grid import save_grid, load_grid
from challenges.c2_roads import run_roads
from challenges.c5_crime import run_crime
from challenges.c3_ambulance import run_ambulance
from scipy import stats as scipy_stats

app = Flask(__name__, template_folder="templates", static_folder="static")

# Global server-side state (single-user local tool)
state = {
    "grid": None,
    "city_graph": None,
    "path1": None,
    "path2": None,
    "ambulance_result": None,
}


def grid_to_json(grid):
    cells = []
    for r in range(grid.size):
        for c in range(grid.size):
            cell = grid.get_cell(r, c)
            cells.append({
                "row": r,
                "col": c,
                "type": cell.location_type.value if cell.location_type else "EMPTY",
                "population_density": cell.population_density,
                "risk_index": cell.risk_index,
            })
    return {"size": grid.size, "cells": cells}


def graph_to_json(cg, path1, path2):
    edges = []
    for u, v, data in cg.edges(data=True):
        edges.append({
            "u": list(u),
            "v": list(v),
            "blocked": data.get("blocked", False),
            "redundancy": data.get("redundancy", False),
        })
    mst_count = sum(1 for _, _, d in cg.edges(data=True) if not d.get("redundancy", False))
    extra_count = sum(1 for _, _, d in cg.edges(data=True) if d.get("redundancy", False))
    return {
        "edges": edges,
        "path1": [list(n) for n in path1] if path1 else None,
        "path2": [list(n) for n in path2] if path2 else None,
        "nodes": cg.number_of_nodes(),
        "mst_edges": mst_count,
        "extra_edges": extra_count,
        "path1_hops": len(path1) - 1 if path1 else None,
        "path2_hops": len(path2) - 1 if path2 else None,
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/run_csp", methods=["POST"])
def api_run_csp():
    data = request.json
    grid_size = int(data.get("grid_size", 5))
    counts_raw = data.get("counts", {})

    required_counts = {}
    skip = {LocationType.EMPTY, LocationType.PRIMARY_HOSPITAL}
    for lt in LocationType:
        if lt in skip:
            continue
        val = counts_raw.get(lt.value, 0)
        required_counts[lt] = int(val)

    scipy_stats.steps = 0
    scipy_stats.depth = 0
    scipy_stats.max_depth = 0

    try:
        grid, violations = run_layout(grid_size, required_counts)
        state["grid"] = grid
        state["city_graph"] = None
        state["path1"] = None
        state["path2"] = None
        state["ambulance_result"] = None

        return jsonify({
            "success": True,
            "grid": grid_to_json(grid),
            "violations": len(violations),
            "steps": getattr(scipy_stats, "steps", 0),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/save_grid", methods=["POST"])
def api_save_grid():
    if state["grid"] is None:
        return jsonify({"success": False, "error": "No grid to save"}), 400
    save_grid(state["grid"])
    return jsonify({"success": True})


@app.route("/api/load_grid", methods=["GET"])
def api_load_grid():
    if not os.path.exists("saved_grid.json"):
        return jsonify({"success": False, "error": "No saved grid found"}), 404
    grid = load_grid()
    state["grid"] = grid
    state["city_graph"] = None
    state["path1"] = None
    state["path2"] = None
    state["ambulance_result"] = None
    return jsonify({"success": True, "grid": grid_to_json(grid)})


@app.route("/api/run_roads", methods=["POST"])
def api_run_roads():
    if state["grid"] is None:
        return jsonify({"success": False, "error": "Run CSP first"}), 400
    try:
        cg = run_roads(state["grid"])
        state["city_graph"] = cg
        state["path1"] = None
        state["path2"] = None
        state["ambulance_result"] = None
        return jsonify({"success": True, **graph_to_json(cg, None, None)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/run_ambulance", methods=["POST"])
def api_run_ambulance():
    if state["city_graph"] is None:
        return jsonify({"success": False, "error": "Run Roads first"}), 400
    try:
        result = run_ambulance(state["city_graph"])
        state["ambulance_result"] = result
        placements = result.get("placements", [])
        worst = result.get("worst_case_distance", math.inf)
        coverage = result.get("coverage", {})
        covered = sum(1 for d in coverage.values() if d < math.inf)
        return jsonify({
            "success": True,
            "placements": [list(p) for p in placements],
            "worst_case_distance": round(worst, 3) if worst < math.inf else None,
            "covered": covered,
            "total_citizens": len(coverage),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
    
@app.route("/api/run_crime", methods=["POST"])
def api_run_crime():
    if state["city_graph"] is None:
        return jsonify({"success": False, "error": "Run Roads first"}), 400
    try:
        data = request.json or {}
        k = int(data.get("k", 0))
        result = run_crime(state["city_graph"], k=k)
        cluster_labels = result["cluster_labels"]
        risk_levels    = result["risk_levels"]
        explanations   = result["explanations"]
        return jsonify({
            "success":        True,
            "high":           result["high_count"],
            "medium":         result["medium_count"],
            "low":            result["low_count"],
            "cluster_labels": cluster_labels,
            "risk_levels":    risk_levels,
            "explanations":   explanations,
            "model_analysis": result["model_analysis"],
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


if __name__ == "__main__":
    app.run(debug=True, port=5000)