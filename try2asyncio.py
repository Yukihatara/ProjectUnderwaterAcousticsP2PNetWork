import asyncio
import json
import math

# Конфигурация
NODES = {
    'A': {'port': 5001, 'position': (0, 100)},
    'B': {'port': 5002, 'position': (50, 120)},
    'C': {'port': 5003, 'position': (50, 80)},
    'D': {'port': 5004, 'position': (50, 40)},
    'E': {'port': 5005, 'position': (100, 100)},
}

HELLO_INTERVAL = 5  # Отправляем Hello каждые 5 секунд

ACOUSTIC_PARAMS = {
    'speed_of_sound' = 1500.0,
    'bitrate' = 1000,
    'packet_overhead' = 100,
}

class SimpleNode:
    def __init__(self, node_id):
        self.node_id = node_id
        self.neighbors = {} # {node_id: {'position': (), 'packets': []}}

    def calculate_distance(self, target_id):
        x1, y1 = NODES[self.node_id]['position']
        x2, y2 = NODES[target_id][['position']]
        return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

    def calculate_propagation_delay(seld, target_id):
        distance = self.calculate_distance(target_id)
        return distance / ACOUSTIC_PARAMS['speed_of_sound']

    async def send_message(self, target_id, msg_type, **kwargs):
        """Отправить любое сообщение одному узлу"""
        try:
            # Подключаемся
            reader, writer = await asyncio.open_connection(
                '127.0.0.1',
                NODES[target_id]['port']
            )

            # Формируем сообщение
            message = {
                'type': msg_type,
                'sender': self.node_id,
                **kwargs, # Все дополнительные поля
            }

            writer.write(json.dumps(message).encode())
            await writer.drain()

            print(f"[{self.node_id}] Отправил {msg_type} -> {target_id}")

            # Закрываем
            writer.close()
            await writer.wait_closed()

        except Exception as e:
             print(f"[{self.node_id}] Ошибка отправки к {target_id}: {e}")

    async def broadcast(self, msg_type, **kwargs):
        """Отправить Hello всем узлам"""
        print(f"\n[{self.node_id}] Отправляю {msg_type} всем...")

        # Создаем задачи для кажого узла
        tasks = []
        for target_id in NODES:
            if target_id != self.node_id:
                tasks.append(self.send_message(target_id, msg_type, **kwargs))

        # Ждем завершения всех отправок (конкурентно)
        if tasks:
            await asyncio.gather(*tasks)

        print(f"[{self.node_id}] {msg_type} отправлены всем!")

    async def handle_connection(self, reader, writer):
        """Обработка входящего Hello"""
        addr = writer.get_extra_info('peername')

        try:
            # Читаем сообщение
            data = await reader.read(1024)
            if not data:
                return

            # Парсим
            msg = json.loads(data.decode())
            msg_type = msg['type']

            if msg_type == 'Hello':
                sender = msg['sender']
                print(f"[{self.node_id}] Получил Hello от {sender}")

                # Сохраняем инофрмацию о себе
                self.neighbors[sender] = {
                    'position': tuple(msg['position']),
                    'packets': msg['packets']
                }

                # Отправляем подтвержение опционально
                response = {'type':'HelloAck', 'from': self.node_id}
                writer.write(json.dumps(response).encode())
                await writer.drain()

        except Exception as e:
            print(f"[{self.node_id}] Ошибка обработки: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def handle_hello(self, msg, writer):
        sender = msg['sender']
        print(f"[{self.node_id}] Получил Hello от {sender}")

        # Сохраняем информацию о соседе
        self.neighbors[sender] = {
            'position': tuple(msg['position']),
            'packets': msg['packets'],
        }

    async def run_server(self):
        """Сервер для приема сообщений"""
        server = await asyncio.start_server(
            self.handle_connection,
            '127.0.0.1',
            NODES[self.node_id]['port'],
        )

        print(f"[{self.node_id}] Сервер запущен на порту {NODES[self.node_id]['port']}")

        async with server:
            await server.serve_forever()

    async def run(self):
        """Запуск узла"""
        # Запускаем сервер в фоне

        server_task = asyncio.create_task(self.run_server())

        # Ждем пока сервер запустится
        await asyncio.sleep(1)

        while True:
            await self.broadcast('Hello', position=NODES[self.node_id]['position'], packets=[])

            if self.neighbors:
                print(f"[{self.node_id}] Знаю о соседях: {list(self.neighbors.keys())}")

            # Ждем перед следующей отправкой
            await asyncio.sleep(HELLO_INTERVAL)

        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
        # Отправка метаданных
        # await self.broadcast('Metadata', data={'fullset': [1,2,3,4,5]})

        # # Отправка запроса
        # await self.broadcast('Request', need_packets=[1,2,3])

        # # Отправка одному конкретному узлу
        # await self.send_message('E', 'Request', need_packets=[1,2,3])

async def main():
    # Создаем и запускаем все узлы
    nodes = []
    for node_id in NODES:
        node = SimpleNode(node_id)
        task = asyncio.create_task(node.run())
        nodes.append(task)

    # Ждем завершения (никогда не завершится)
    await asyncio.gather(*nodes)

if __name__ == '__main__':
    print("Запуск 5 узлов...")
    print("Нажмите Ctrl+C для остановки")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nОстановка...")
