import networkx as nx
import math

class CityGraph:
    def __init__(self, rows, cols):
        self.rows = rows
        self.cols = cols
        self.G = nx.Graph()   # NetworkX does the heavy lifting
        self._build_grid()

    def _node_id(self, row, col):
        return row * self.cols + col

    def _build_grid(self):
        # Step 1: add all nodes
        for row in range(self.rows):
            for col in range(self.cols):
                nid = self._node_id(row, col)
                self.G.add_node(nid,
                    row=row,
                    col=col,
                    location_type=None,       # set by Challenge 1
                    population_density=0.0,
                    risk_index=0.0,
                    accessible=True,
                    cluster_id=None,          # set by Challenge 5 part 1
                    risk_level=None,          # set by Challenge 5 part 2
                    risk_multiplier=1.0,      # 1.0 / 1.2 / 1.5
                    has_ambulance=False
                )

        # Step 2: add edges between adjacent cells (4-connectivity)
        for row in range(self.rows):
            for col in range(self.cols):
                nid = self._node_id(row, col)
                # right neighbor
                if col + 1 < self.cols:
                    neighbor = self._node_id(row, col + 1)
                    self.G.add_edge(nid, neighbor,
                        base_cost=1.0,
                        is_blocked=False,
                        effective_cost=1.0
                    )
                # bottom neighbor
                if row + 1 < self.rows:
                    neighbor = self._node_id(row + 1, col)
                    self.G.add_edge(nid, neighbor,
                        base_cost=1.0,
                        is_blocked=False,
                        effective_cost=1.0
                    )
    def set_location_type(self, node_id, location_type):
        self.G.nodes[node_id]['location_type'] = location_type

    def block_road(self, a, b):
        self.G.edges[a, b]['is_blocked'] = True
        self.G.edges[a, b]['effective_cost'] = math.inf

    def update_risk(self, node_id, risk_level, multiplier=None):
        if multiplier is None:
            risk_multipliers = {"low": 1.0, "medium": 1.2, "high": 1.5}
            multiplier = risk_multipliers.get(risk_level, 1.0)
        self.G.nodes[node_id]['risk_level'] = risk_level
        self.G.nodes[node_id]['risk_multiplier'] = multiplier
        # also update all edges touching this node
        for neighbor in self.G.neighbors(node_id):
            edge = self.G.edges[node_id, neighbor]
            if not edge['is_blocked']:
                other_mult = self.G.nodes[neighbor]['risk_multiplier']
                edge['effective_cost'] = edge['base_cost'] * max(multiplier, other_mult)

    def unblock_road(self, a, b):
        self.G.edges[a, b]['is_blocked'] = False
        # Reset effective cost based on risk multipliers
        node_a_mult = self.G.nodes[a]['risk_multiplier']
        node_b_mult = self.G.nodes[b]['risk_multiplier']
        self.G.edges[a, b]['effective_cost'] = self.G.edges[a, b]['base_cost'] * max(node_a_mult, node_b_mult)

    def get_edge(self, a, b):
        return self.G.edges[a, b]

    def get_node(self, node_id):
        return self.G.nodes[node_id]

    def get_neighbors(self, node_id):
        return list(self.G.neighbors(node_id))

    def node_id(self, row, col):
        return self._node_id(row, col)

    def stats(self):
        stats = {
            "nodes": self.G.number_of_nodes(),
            "edges": self.G.number_of_edges(),
            "blocked_edges": sum(1 for _, _, data in self.G.edges(data=True) if data['is_blocked']),
            "buildings": sum(1 for _, data in self.G.nodes(data=True) if data['location_type'] is not None),
            "high_risk_nodes": sum(1 for _, data in self.G.nodes(data=True) if data['risk_level'] == 'high'),
            "ambulance_depots": sum(1 for _, data in self.G.nodes(data=True) if data['location_type'] == 'ambulance_depot')
        }
        return stats

    def reset(self):
        # Reset all nodes to default state
        for node_id in self.G.nodes():
            self.G.nodes[node_id].update({
                'location_type': None,
                'population_density': 0.0,
                'risk_index': 0.0,
                'accessible': True,
                'cluster_id': None,
                'risk_level': None,
                'risk_multiplier': 1.0,
                'has_ambulance': False
            })
        
        # Reset all edges to default state
        for a, b in self.G.edges():
            self.G.edges[a, b].update({
                'is_blocked': False,
                'effective_cost': 1.0
            })