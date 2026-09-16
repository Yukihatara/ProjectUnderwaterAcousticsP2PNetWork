# layers/application.py
class ApplicationLayer:
    """Прикладной уровень: Hello, будущие приложения."""

    def __init__(self, node_id, network):
        self.node_id = node_id
        self.network = network

    def build_hello(self, position):
        return {
            'type': 'Hello',
            'sender': self.node_id,
            'position': position,
            'packets': [],
        }

    def on_hello(self, msg):
        sender = msg['sender']
        self.network.learn_neighbor(sender, {
            'position': tuple(msg['position']),
            'packets': msg['packets'],
        })
        return sender