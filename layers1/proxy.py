# layers/proxy.py
import asyncio
import json
import time

class Proxy:
    def __init__(self, nodes_cfg, host='127.0.0.1', port=7777):
        self.nodes = nodes_cfg
        self.host = host
        self.port = port

    async def _deliver(self, target_id, msg):
        time_st_b = msg.get('time_st_b', 0)
        if time_st_b > time.time():
            await asyncio.sleep(time_st_b - time.time())

        out = {k: v for k, v in msg.items() if k not in ('time_st_b', 'target')}
        reader, writer = await asyncio.open_connection(
            '127.0.0.1', self.nodes[target_id]['port'])
        try:
            writer.write(json.dumps(out).encode())
            await writer.drain()
            print(f"\t[ПОСРЕДНИК] {msg.get('type')} -> {target_id}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def _handle_client(self, reader, writer):
        try:
            data = await reader.read(4096)
            if not data:
                return
            msg = json.loads(data.decode())
            target = msg.get('target')
            if target:
                await self._deliver(target, msg)
        except Exception as e:
            print(f"[ПОСРЕДНИК] {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def start(self):
        server = await asyncio.start_server(self._handle_client, self.host, self.port)
        print(f"[ПОСРЕДНИК] Запущен на {self.host}:{self.port}")
        async with server:
            await server.serve_forever()