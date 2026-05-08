import networkx as nx
from challenges.c1_layout import LocationType


class CityGraph:
    def __init__(self):
        self.G = nx.Graph()

    def add_node(self, node_id, location_type, population_density, risk_index, accessible):
        self.G.add_node(
            node_id,
            type=location_type,
            population_density=population_density,
            risk_index=risk_index,
            accessible=accessible,
        )

    def add_road(self, u, v, base_cost, redundancy=False):
        self.G.add_edge(
            u, v,
            base_cost=base_cost,
            blocked=False,
            effective_cost=base_cost,
            redundancy=redundancy,
        )

    def has_road(self, u, v):
        return self.G.has_edge(u, v)

    def block_road(self, u, v):
        if self.G.has_edge(u, v):
            self.G[u][v]['blocked'] = True

    def unblock_road(self, u, v):
        if self.G.has_edge(u, v):
            self.G[u][v]['blocked'] = False

    def update_effective_costs(self, risk_multipliers):
        for u, v, data in self.G.edges(data=True):
            mul_u = risk_multipliers.get(u, 1.0)
            mul_v = risk_multipliers.get(v, 1.0)
            data['effective_cost'] = data['base_cost'] * mul_u * mul_v

    def find_node_by_type(self, location_type):
        for node, data in self.G.nodes(data=True):
            if data.get('type') == location_type:
                return node
        return None

    def number_of_nodes(self):
        return self.G.number_of_nodes()

    def number_of_edges(self):
        return self.G.number_of_edges()

    def nodes(self, data=False):
        return self.G.nodes(data=data)

    def edges(self, data=False):
        return self.G.edges(data=data)

    def neighbors(self, node):
        return self.G.neighbors(node)

    def get_edge_data(self, u, v):
        return self.G[u][v]