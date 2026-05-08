import networkx as nx


class CityGraph:
    def __init__(self):
        self._g = nx.Graph()

    @property
    def g(self) -> nx.Graph:
        return self._g

    def add_node(self, node_id, **attrs):
        self._g.add_node(node_id, **attrs)

    def add_edge(self, u, v, base_cost: float, blocked: bool = False, effective_cost: float = None, redundancy: bool = False):
        if effective_cost is None:
            effective_cost = base_cost
        self._g.add_edge(u, v, base_cost=base_cost, blocked=blocked, effective_cost=effective_cost, redundancy=redundancy)

    def block_road(self, u, v):
        if self._g.has_edge(u, v):
            self._g[u][v]["blocked"] = True

    def unblock_road(self, u, v):
        if self._g.has_edge(u, v):
            self._g[u][v]["blocked"] = False

    def update_effective_costs(self, risk_multipliers: dict):
        for u, v, data in self._g.edges(data=True):
            m_u = risk_multipliers.get(u, 1.0)
            m_v = risk_multipliers.get(v, 1.0)
            self._g[u][v]["effective_cost"] = data["base_cost"] * m_u * m_v

    def number_of_nodes(self) -> int:
        return self._g.number_of_nodes()

    def number_of_edges(self) -> int:
        return self._g.number_of_edges()

    def has_edge(self, u, v) -> bool:
        return self._g.has_edge(u, v)

    def nodes(self, data=False):
        return self._g.nodes(data=data)

    def edges(self, data=False):
        return self._g.edges(data=data)

    def neighbors(self, node):
        return self._g.neighbors(node)

    def __getitem__(self, node):
        return self._g[node]