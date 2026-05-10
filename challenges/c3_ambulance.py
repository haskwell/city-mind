import math
import heapq
import random

from core.city_graph import CityGraph
from challenges.c1_layout import LocationType


NUM_AMBULANCES = 3
POPULATION_SIZE = 60
NUM_GENERATIONS = 120
MUTATION_RATE = 0.25
TOURNAMENT_SIZE = 5
ELITE_COUNT = 4


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

def _precompute_distances(cg: CityGraph, nodes_of_interest: list) -> dict:
    dist_map = {}
    for node in nodes_of_interest:
        dist_map[node] = _dijkstra_single(cg, node)
    return dist_map


def _get_citizen_nodes(cg: CityGraph) -> list:
    citizens = []
    for node, data in cg.nodes(data=True):
        lt = data.get("type")
        if lt in (LocationType.RESIDENTIAL, LocationType.SCHOOL, LocationType.POWER_PLANT, LocationType.INDUSTRIAL):
            citizens.append(node)
    return citizens


def _get_placement_nodes(cg: CityGraph) -> list:
    excluded = {LocationType.EMPTY, LocationType.INDUSTRIAL, LocationType.POWER_PLANT, LocationType.HOSPITAL, LocationType.PRIMARY_HOSPITAL, LocationType.AMBULANCE_DEPOT}
    nodes = []
    for node, data in cg.nodes(data=True):
        if data.get("type") not in excluded:
            nodes.append(node)
    return nodes


def _fitness(chromosome: tuple, citizen_nodes: list, dist_from_citizens: dict) -> float:
    if not citizen_nodes:
        return 0.0
    worst = 0.0
    for citizen in citizen_nodes:
        citizen_dists = dist_from_citizens[citizen]
        best_for_citizen = min(
            citizen_dists.get(amb, math.inf) for amb in chromosome
        )
        if best_for_citizen > worst:
            worst = best_for_citizen
    return worst


def _random_chromosome(placement_nodes: list) -> tuple:
    chosen = random.sample(placement_nodes, min(NUM_AMBULANCES, len(placement_nodes)))
    return tuple(chosen)


def _tournament_select(population: list, fitnesses: list) -> tuple:
    candidates = random.sample(range(len(population)), min(TOURNAMENT_SIZE, len(population)))
    best = min(candidates, key=lambda i: fitnesses[i])
    return population[best]


def _crossover(parent1: tuple, parent2: tuple, placement_nodes: list) -> tuple:
    combined = list(set(parent1) | set(parent2))
    if len(combined) < NUM_AMBULANCES:
        extras = [n for n in placement_nodes if n not in combined]
        random.shuffle(extras)
        combined.extend(extras)
    random.shuffle(combined)
    return tuple(combined[:NUM_AMBULANCES])


def _mutate(chromosome: tuple, placement_nodes: list) -> tuple:
    chrom_list = list(chromosome)
    idx = random.randrange(len(chrom_list))
    candidates = [n for n in placement_nodes if n not in chrom_list]
    if candidates:
        chrom_list[idx] = random.choice(candidates)
    return tuple(chrom_list)


def run_ambulance(cg: CityGraph) -> dict:
    print("[C3] Starting ambulance placement (Genetic Algorithm)...")

    citizen_nodes = _get_citizen_nodes(cg)
    placement_nodes = _get_placement_nodes(cg)

    if not placement_nodes:
        print("[C3] ERROR: No valid placement nodes found.")
        return {"placements": [], "worst_case_distance": math.inf, "coverage": {}}

    if len(placement_nodes) < NUM_AMBULANCES:
        print(f"[C3] WARNING: Only {len(placement_nodes)} placement nodes — using all of them.")
        best_chromosome = tuple(placement_nodes)
        dist_from_citizens = _precompute_distances(cg, citizen_nodes)
        worst = _fitness(best_chromosome, citizen_nodes, dist_from_citizens)
        coverage = {c: min(dist_from_citizens[c].get(a, math.inf) for a in best_chromosome) for c in citizen_nodes}
        return {
            "placements": list(best_chromosome),
            "worst_case_distance": worst,
            "coverage": coverage,
        }

    print(f"[C3] Pre-computing shortest paths for {len(citizen_nodes)} citizen node(s)...")
    dist_from_citizens = _precompute_distances(cg, citizen_nodes)
    print(f"[C3] Distance matrix ready. Running GA over {len(placement_nodes)} placement node(s)...")

    population = [_random_chromosome(placement_nodes) for _ in range(POPULATION_SIZE)]
    fitnesses = [_fitness(chrom, citizen_nodes, dist_from_citizens) for chrom in population]

    best_idx = min(range(len(population)), key=lambda i: fitnesses[i])
    best_chromosome = population[best_idx]
    best_fitness = fitnesses[best_idx]

    for generation in range(NUM_GENERATIONS):
        sorted_pairs = sorted(zip(fitnesses, population), key=lambda x: x[0])
        elites = [chrom for _, chrom in sorted_pairs[:ELITE_COUNT]]

        new_population = list(elites)

        while len(new_population) < POPULATION_SIZE:
            p1 = _tournament_select(population, fitnesses)
            p2 = _tournament_select(population, fitnesses)
            child = _crossover(p1, p2, placement_nodes)
            if random.random() < MUTATION_RATE:
                child = _mutate(child, placement_nodes)
            new_population.append(child)

        population = new_population
        fitnesses = [_fitness(chrom, citizen_nodes, dist_from_citizens) for chrom in population]

        gen_best_idx = min(range(len(population)), key=lambda i: fitnesses[i])
        gen_best_fit = fitnesses[gen_best_idx]

        if gen_best_fit < best_fitness:
            best_fitness = gen_best_fit
            best_chromosome = population[gen_best_idx]

        if (generation + 1) % 20 == 0:
            print(f"[C3] Generation {generation + 1}/{NUM_GENERATIONS} — best worst-case distance: {best_fitness:.3f}")

    coverage = {}
    for citizen in citizen_nodes:
        dists = dist_from_citizens[citizen]
        coverage[citizen] = min(dists.get(amb, math.inf) for amb in best_chromosome)

    print(f"[C3] GA complete. Ambulances placed at: {list(best_chromosome)}")
    print(f"[C3] Worst-case citizen distance: {best_fitness:.3f}")
    print(f"[C3] Citizens covered (finite distance): {sum(1 for d in coverage.values() if d < math.inf)}/{len(citizen_nodes)}")

    return {
        "placements": list(best_chromosome),
        "worst_case_distance": best_fitness,
        "coverage": coverage,
    }