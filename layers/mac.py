# layers/mac.py
import asyncio

class MACLayer:
    """Канальный уровень: доступ к среде, half-duplex."""

    def __init__(self, node_id):
        self.node_id = node_id
        self.tx_lock = asyncio.Lock()
        self.is_transmitting = False
        self.active_receptions = 0

    @property
    def is_receiving(self):
        return self.active_receptions > 0

    async def acquire_tx(self):
        """Захватить канал на передачу. Ждём, пока идёт приём."""
        while self.is_receiving:
            await asyncio.sleep(0.01)
        await self.tx_lock.acquire()
        self.is_transmitting = True

    def release_tx(self):
        self.is_transmitting = False
        if self.tx_lock.locked():
            self.tx_lock.release()

    def try_acquire_rx(self):
        """Попытка начать приём. False — если заняты передачей."""
        if self.is_transmitting:
            return False
        self.active_receptions += 1
        return True

    def release_rx(self):
        self.active_receptions = max(0, self.active_receptions - 1)