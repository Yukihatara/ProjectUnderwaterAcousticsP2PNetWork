# main.py
import asyncio

from layers.node import Node
from layers.proxy import Proxy

MAX_RANGE = 2400
NODES = {
    'A': {'port': 5001, 'position': (0, 2/3 * MAX_RANGE)},
    'B': {'port': 5002, 'position': (1.75/3 * MAX_RANGE, 3.5/3 * MAX_RANGE)},
    'C': {'port': 5003, 'position': (1.75/3 * MAX_RANGE, 1.5/3 * MAX_RANGE)},
    'D': {'port': 5004, 'position': (1.75/3 * MAX_RANGE, 0)},
    'E': {'port': 5005, 'position': (1.75/3 * 2 * MAX_RANGE, 2/3 * MAX_RANGE)},
}

CFG = {
    'nodes': NODES,
    'max_range': MAX_RANGE,
    'acoustic': {'speed_of_sound': 1500.0, 'bitrate': 1000, 'packet_overhead': 100},
    'hello_interval': 10.0,
    'hello_jitter': 2.0,
    'proxy_host': '127.0.0.1',
    'proxy_port': 7777,
}


async def main():
    proxy = Proxy(NODES, CFG['proxy_host'], CFG['proxy_port'])
    asyncio.create_task(proxy.start())
    await asyncio.sleep(1)

    nodes = [Node(nid, CFG) for nid in NODES]
    await asyncio.gather(*(n.run() for n in nodes))


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nОстановка...")