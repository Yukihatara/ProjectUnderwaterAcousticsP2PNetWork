"""Прикладной уровень: Hello + обвязка для DACAP."""

class ApplicationLayer:
    def __init__(self, node_id, network):
        self.node_id = node_id
        self.network = network

    # ---------- генерация ----------
    def build_hello(self, position):
        return {
            'type': 'Hello',
            'sender': self.node_id,
            'position': position,
            'packets': [],
        }

    def build_rts(self, data_type, duration):
        return {
            'type': 'RTS',
            'sender': self.node_id,
            'data_type': data_type,
            'duration': duration,
        }

    def build_cts(self, duration):
        return {
            'type': 'CTS',
            'sender': self.node_id,
            'duration': duration,
        }

    def build_ack(self):
        return {
            'type': 'ACK',
            'sender': self.node_id,
        }

    # ---------- обработка ----------
    def on_hello(self, msg):
        sender = msg['sender']
        self.network.learn_neighbor(sender, {
            'position': tuple(msg['position']),
            'packets': msg['packets'],
        })
        return sender