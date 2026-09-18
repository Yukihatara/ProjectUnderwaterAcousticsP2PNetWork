# layers/node.py
import asyncio
import json
import time
import random

from .physical import PhysicalLayer
from .mac import MACLayer
from .network import NetworkLayer
from .application import ApplicationLayer


class Transport:
    """Отвечает только за сокеты: соединиться с Proxy, принять от сервера."""

    def __init__(self, proxy_host, proxy_port):
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port

    async def send_raw(self, payload: dict):
        reader, writer = await asyncio.open_connection(self.proxy_host, self.proxy_port)
        try:
            writer.write(json.dumps(payload).encode())
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async def serve(self, handler, host, port):
        server = await asyncio.start_server(handler, host, port)
        async with server:
            await server.serve_forever()


class Node:
    """Узел = стек слоёв + транспорт + event loop."""

    def __init__(self, node_id, cfg):
        self.node_id = node_id
        self.cfg = cfg

        # слои снизу вверх
        self.physical = PhysicalLayer(node_id, cfg['nodes'], cfg['acoustic'])
        self.mac      = MACLayer(node_id)
        self.network  = NetworkLayer(node_id, cfg['nodes'], self.physical, cfg['max_range'])
        self.app      = ApplicationLayer(node_id, self.network)

        self.transport = Transport(cfg['proxy_host'], cfg['proxy_port'])

    # ---------- Исходящая передача ----------
    async def _transmit_to(self, target_id, message):
        """Передать уже собранное сообщение одному узлу через Proxy."""
        prop = self.physical.propagation_delay(target_id)
        tx   = self.physical.transmission_duration(message)
        now  = time.time()

        out = dict(message)
        out['target']   = target_id
        out['time_st_b'] = now + prop
        out['time_end_b'] = now + prop + tx

        await self.transport.send_raw(out)
        # имитируем модуляцию всего сигнала
        await asyncio.sleep(tx)

    async def send(self, target_id, message):
        await self._transmit_to(target_id, message)

    async def broadcast(self, message):
        """Рассылка всем, кто в радиусе. Обёрнута в MAC."""
        await self.mac.acquire_tx()
        try:
            targets = self.network.list_reachable()
            tasks = [self._transmit_to(t, message) for t in targets]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            self.mac.release_tx()

    # ---------- Входящая передача ----------
    async def _handle_connection(self, reader, writer):
        if not self.mac.try_acquire_rx():
            print(f"[{self.node_id}] ЗАНЯТ передачей — входящее отброшено")
            writer.close()
            await writer.wait_closed()
            return

        try:
            data = await reader.read(4096)
            if not data:
                return
            msg = json.loads(data.decode())

            # ждём окончания приёма всего сигнала
            time_end_b = msg.get('time_end_b', 0)
            if time_end_b < time.time():
                return
            await asyncio.sleep(time_end_b - time.time())

            # поднимаем на прикладной уровень
            if msg['type'] == 'Hello':
                sender = self.app.on_hello(msg)
                print(f"[{self.node_id}] Получил Hello от {sender}")

        except Exception as e:
            print(f"[{self.node_id}] Ошибка обработки: {e}")
        finally:
            self.mac.release_rx()
            writer.close()
            await writer.wait_closed()

    # ---------- Главный цикл ----------
    async def run(self):
        # сервер приёма
        asyncio.create_task(self.transport.serve(
            self._handle_connection,
            '127.0.0.1',
            self.cfg['nodes'][self.node_id]['port'],
        ))
        await asyncio.sleep(1)

        # фазовая рассинхронизация
        await asyncio.sleep(random.uniform(0, self.cfg['hello_interval'] / 1.2))

        while True:
            msg = self.app.build_hello(self.cfg['nodes'][self.node_id]['position'])
            await self.broadcast(msg)

            if self.network.neighbors:
                print(f"[{self.node_id}] Соседи: {list(self.network.neighbors.keys())}")

            await asyncio.sleep(
                self.cfg['hello_interval']
                + random.uniform(-self.cfg['hello_jitter'], self.cfg['hello_jitter'])
            )