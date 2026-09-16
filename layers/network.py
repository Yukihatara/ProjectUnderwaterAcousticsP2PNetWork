# layers/network.py
import asyncio

class NetworkLayer:
    """Сетевой уровень: соседи, доставка сообщений."""

    def __init__(self, node_id, nodes_cfg, physical, max_range):
        self.node_id = node_id
        self.nodes = nodes_cfg
        self.physical = physical
        self.max_range = max_range
        self.neighbors = {}   # {node_id: {'position':..., 'packets': [...]}}

    def list_reachable(self):
        return [
            nid for nid in self.nodes
            if nid != self.node_id
            and self.physical.in_range(nid, self.max_range)
        ]

    def learn_neighbor(self, sender, info):
        self.neighbors[sender] = info