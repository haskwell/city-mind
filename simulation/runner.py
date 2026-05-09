"""
CLI test runner for Challenge 4 — Emergency Routing.
Run from the project root:  python -m simulation.runner
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from util.save_grid import load_grid
from challenges.c2_roads import run_roads
from challenges.c5_risk_prediction import run_risk_prediction
from challenges.c3_ambulance import run_ambulance
from challenges.c4_routing import init_routing, step_routing
from challenges.c1_layout import LocationType

STEP_DELAY_SECONDS = 0.3   # change to slow down / speed up


def run():
    print("=" * 60)
    print("  CityMind — Challenge 4: Emergency Routing (CLI)")
    print("=" * 60)

    # Load grid
    grid = load_grid()
    print(f"Grid loaded: {grid.size}x{grid.size}")

    # Build roads
    print("Building road network...")
    cg = run_roads(grid)
    print(f"Graph: {cg.number_of_nodes()} nodes, {cg.number_of_edges()} edges")

    # Run risk prediction (updates effective costs)
    print("Running risk prediction...")
    run_risk_prediction(cg)

    # Place ambulances (informational only — routing uses the depot)
    print("Running ambulance placement...")
    run_ambulance(cg)

    # Pick some civilians to rescue: first few RESIDENTIAL nodes
    civilian_nodes = []
    for node, data in cg.nodes(data=True):
        if data.get("type") == LocationType.RESIDENTIAL:
            civilian_nodes.append(node)
        if len(civilian_nodes) >= 4:
            break

    if not civilian_nodes:
        print("No residential nodes found — aborting.")
        return

    print(f"\nCivilians to rescue: {civilian_nodes}")

    # Initialise routing
    sim_state = init_routing(cg, civilian_nodes)
    depot = sim_state["depot"]
    print(f"Depot at: {depot}")
    print(f"First target: {sim_state['current_target']}")
    print("-" * 60)

    # Step loop
    while not sim_state["done"]:
        event = step_routing(cg, sim_state)
        tag = {
            "move":        "  →",
            "replan":      " !!",
            "rescue":      " ✓ ",
            "unreachable": " ✗ ",
            "done":        "===",
        }.get(event["type"], "   ")

        print(f"[step {event['step']:>4}] {tag} {event['message']}")
        time.sleep(STEP_DELAY_SECONDS)

    print("-" * 60)
    print(f"FINAL REPORT")
    print(f"  Total steps  : {sim_state['step']}")
    print(f"  Rescued      : {sim_state['rescued']}")
    print(f"  Unreachable  : {sim_state['unreachable']}")
    print("=" * 60)


if __name__ == "__main__":
    run()
