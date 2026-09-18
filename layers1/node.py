"""Узел = стек слоёв + транспорт + главный цикл + DACAP."""

import asyncio
import json
import random
import time

from .physical import PhysicalLayer
from .mac import MACLayer
from .network import NetworkLayer
from .application import ApplicationLayer


# --- тайминги DACAP ---
RTS_TIMEOUT = 2.0     # сколько ждём CTS
ACK_TIMEOUT = 2.0     # сколько ждём ACK
SIFS = 0.05           # короткая межкадровая пауза
RTS_SIZE = 4          # «стоимость» RTS/CTS/ACK в секундах (упрощение: фикс.)
CTS_SIZE = 4
ACK_SIZE = 2


class Transport:
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
        print(f"[ТРАНСПОРТ] Сервер слушает {host}:{port}")
        async with server:
            await server.serve_forever()


class Node:
    def __init__(self, node_id, cfg):
        self.node_id = node_id
        self.cfg = cfg

        self.physical = PhysicalLayer(node_id, cfg['nodes'], cfg['acoustic'])
        self.mac = MACLayer(node_id)
        self.network = NetworkLayer(node_id, cfg['nodes'], self.physical, cfg['max_range'])
        self.app = ApplicationLayer(node_id, self.network)

        self.transport = Transport(cfg['proxy_host'], cfg['proxy_port'])

    # ==================================================================
    #                        ИСХОДЯЩАЯ ПЕРЕДАЧА
    # ==================================================================
    async def _transmit_to(self, target_id, message):
        """Отправить один кадр. Ждёт время модуляции."""
        prop = self.physical.propagation_delay(target_id)
        tx = self.physical.transmission_duration(message)
        now = time.time()

        out = dict(message)
        out['target'] = target_id
        out['time_st_b'] = now + prop
        out['time_end_b'] = now + prop + tx

        await self.transport.send_raw(out)
        await asyncio.sleep(tx)

    async def _broadcast_frame(self, message):
        """Разослать кадр всем в радиусе (для Hello или RTS всем)."""
        targets = self.network.list_reachable()
        tasks = [self._transmit_to(t, message) for t in targets]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def broadcast_hello(self):
        await self.mac.acquire_tx()
        try:
            msg = self.app.build_hello(self.cfg['nodes'][self.node_id]['position'])
            print(f"\n[{self.node_id}] Broadcast Hello -> {self.network.list_reachable()}")
            await self._broadcast_frame(msg)
        finally:
            self.mac.release_tx()

    # ---------- DACAP: полный цикл ----------
    async def send_dacap(self, target_id, payload):
        """RTS → CTS → DATA → ACK."""
        # сколько займут Data + ACK + паузы — это и есть duration в RTS
        data_dur = self.physical.transmission_duration(payload)
        total_duration = data_dur + ACK_SIZE + 3 * SIFS

        # --- 1) RTS ---
        await self.mac.acquire_tx()
        try:
            rts = self.app.build_rts(payload['type'], total_duration)

            # себя тоже помечаем занятым (мы уже начали передачу)
            self.mac.set_nav(total_duration)

            self.mac.waiting_cts = asyncio.Event()
            await self._transmit_to(target_id, rts)
            print(f"[{self.node_id}] -> RTS {target_id} (duration={total_duration:.1f}s)")
        finally:
            self.mac.release_tx()

        # --- 2) ждём CTS ---
        try:
            await asyncio.wait_for(self.mac.waiting_cts.wait(), timeout=RTS_TIMEOUT)
        except asyncio.TimeoutError:
            print(f"[{self.node_id}] CTS не пришёл — отмена")
            self.mac.waiting_cts = None
            return False

        self.mac.waiting_cts = None
        await asyncio.sleep(SIFS)

        # --- 3) DATA ---
        await self.mac.acquire_tx()
        try:
            self.mac.waiting_ack = asyncio.Event()
            await self._transmit_to(target_id, payload)
            print(f"[{self.node_id}] -> DATA {target_id}")
        finally:
            self.mac.release_tx()

        # --- 4) ждём ACK ---
        try:
            await asyncio.wait_for(self.mac.waiting_ack.wait(), timeout=ACK_TIMEOUT)
            print(f"[{self.node_id}] <- ACK от {target_id}, сессия закрыта")
            self.mac.waiting_ack = None
            return True
        except asyncio.TimeoutError:
            print(f"[{self.node_id}] ACK не пришёл — потеря")
            self.mac.waiting_ack = None
            return False

    # ==================================================================
    #                       ВХОДЯЩАЯ ПЕРЕДАЧА
    # ==================================================================
    async def _handle_connection(self, reader, writer):
        if not self.mac.try_acquire_rx():
            print(f"\t[{self.node_id}] ЗАНЯТ передачей — входящее отброшено")
            writer.close()
            await writer.wait_closed()
            return

        try:
            data = await reader.read(4096)
            if not data:
                return
            msg = json.loads(data.decode())

            # ждём окончания физического приёма
            time_end_b = msg.get('time_end_b', 0)
            if time_end_b < time.time():
                return
            await asyncio.sleep(time_end_b - time.time())

            await self._dispatch(msg)

        except Exception as e:
            print(f"\t[{self.node_id}] Ошибка обработки: {e}")
        finally:
            self.mac.release_rx()
            writer.close()
            await writer.wait_closed()

    async def _dispatch(self, msg):
        t = msg['type']
        sender = msg['sender']
        target = msg.get('target')

        # Служебные кадры DACAP обрабатываем в MAC
        if t in ('RTS', 'CTS'):
            self._handle_control(msg)
            return

        # Остальное — по прикладному уровню, но только если адресовано нам
        if target and target != self.node_id:
            return

        if t == 'Hello':
            sender = self.app.on_hello(msg)
            print(f"\t[{self.node_id}] Получил Hello от {sender}")

        elif t == 'ACK':
            if self.mac.waiting_ack and msg.get('sender') == msg.get('target'):
                self.mac.waiting_ack.set()
            # если ACK пришёл не нам по сессии — игнорируем

    def _handle_control(self, msg):
        """RTS/CTS: обновляем NAV, реагируем если адресовано нам."""
        sender = msg['sender']
        target = msg.get('target')
        duration = msg.get('duration', 0)

        # Любой услышанный RTS/CTS — повод замолчать
        self.mac.set_nav(duration)

        if msg['type'] == 'RTS' and target == self.node_id: # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
            # мы адресат: планируем ответить CTS
            asyncio.create_task(self._respond_cts(sender, duration))

        elif msg['type'] == 'CTS' and target == self.node_id:
            # пришёл наш CTS — разбудить ожидание
            if self.mac.waiting_cts:
                self.mac.waiting_cts.set()

    async def _respond_cts(self, sender, duration):
        await asyncio.sleep(SIFS)
        # не отвечаем, если сами что-то передаём
        if self.mac.is_transmitting:
            return
        await self.mac.acquire_tx()
        try:
            cts = self.app.build_cts(duration)
            await self._transmit_to(sender, cts)
            print(f"\t[{self.node_id}] <- RTS от {sender}, отправляю CTS")
        finally:
            self.mac.release_tx()

    # ==================================================================
    #                            ГЛАВНЫЙ ЦИКЛ
    # ==================================================================
    async def run(self):
        asyncio.create_task(self.transport.serve(
            self._handle_connection,
            '127.0.0.1',
            self.cfg['nodes'][self.node_id]['port'],
        ))
        await asyncio.sleep(1)
        await asyncio.sleep(random.uniform(0, self.cfg['hello_interval'] / 1.2))

        while True:
            # Hello — по-прежнему broadcast (для обнаружения соседей)
            await self.broadcast_hello()

            # раз в цикл попробуем отправить Hello какому-то соседу через DACAP,
            # чтобы продемонстрировать работу RTS/CTS/DATA/ACK
            if self.network.neighbors:
                target = random.choice(list(self.network.neighbors.keys()))
                payload = self.app.build_hello(
                    self.cfg['nodes'][self.node_id]['position'])
                payload['target'] = target
                await self.send_dacap(target, payload)

            if self.network.neighbors:
                print(f"[{self.node_id}] Соседи: {list(self.network.neighbors.keys())}")

            await asyncio.sleep(
                self.cfg['hello_interval']
                + random.uniform(-self.cfg['hello_jitter'], self.cfg['hello_jitter'])
            )