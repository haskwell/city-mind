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

    def update_risk(self, node_id, risk_level, multiplier):
        self.G.nodes[node_id]['risk_level'] = risk_level
        self.G.nodes[node_id]['risk_multiplier'] = multiplier
        # also update all edges touching this node
        for neighbor in self.G.neighbors(node_id):
            edge = self.G.edges[node_id, neighbor]
            if not edge['is_blocked']:
                other_mult = self.G.nodes[neighbor]['risk_multiplier']
                edge['effective_cost'] = edge['base_cost'] * max(multiplier, other_mult)