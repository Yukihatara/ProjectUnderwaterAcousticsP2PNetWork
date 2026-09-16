# layers/physical.py
import json
import math

class PhysicalLayer:
    """Физ. уровень: расстояния, задержки, длительность передачи."""

    def __init__(self, node_id, nodes_cfg, params):
        self.node_id = node_id
        self.nodes = nodes_cfg
        self.params = params  # speed_of_sound, bitrate, packet_overhead

    def distance_to(self, target_id):
        x1, y1 = self.nodes[self.node_id]['position']
        x2, y2 = self.nodes[target_id]['position']
        return math.hypot(x2 - x1, y2 - y1)

    def propagation_delay(self, target_id):
        return self.distance_to(target_id) / self.params['speed_of_sound']

    def transmission_duration(self, message):
        size = len(json.dumps(message).encode())
        bits = size * 8 + self.params['packet_overhead']
        return bits / self.params['bitrate']

    def in_range(self, target_id, max_range):
        return self.distance_to(target_id) < max_range