import asyncio
import time
import json
import math
import os

from temp1 import reset_network_config

os.chdir(os.path.dirname(os.path.abspath(__file__))) # Изменяем рабочую дирректорию

# Конфигурация
NODES = {
    'A': {'port': 5001, 'position': (0, 1000)},
    'B': {'port': 5002, 'position': (500, 1210)},
    'C': {'port': 5003, 'position': (500, 800)},
    'D': {'port': 5004, 'position': (500, 400)},
    'E': {'port': 5005, 'position': (1000, 999  )},
}

HELLO_INTERVAL = 10  # Отправляем Hello каждые 5 секунд

ACOUSTIC_PARAMS = {
    'speed_of_sound': 1500.0,
    'bitrate': 1000,
    'packet_overhead': 100,
}

class SimpleNode:
    def __init__(self, node_id):
        self.node_id = node_id
        self.neighbors = {} # {node_id: {'position': (), 'packets': []}}

    def calculate_distance(self, target_id):
        x1, y1 = NODES[self.node_id]['position']
        x2, y2 = NODES[target_id]['position']
        return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

    def calculate_propagation_delay(self, target_id):
        distance = self.calculate_distance(target_id)
        return distance / ACOUSTIC_PARAMS['speed_of_sound']

    def calculate_transmission_duration(self, message):
        message_size = len(json.dumps(message).encode())
        bits = message_size * 8 + ACOUSTIC_PARAMS['packet_overhead']
        return bits / ACOUSTIC_PARAMS['bitrate']

    def calculate_total_delivery_time(self, target_id, message):
        propagation = self.calculate_propagation_delay(target_id)
        transmission = self.calculate_transmission_duration(message)
        return propagation + transmission

    async def send_message(self, target_id, msg_type, **kwargs):
        """Отправить любое сообщение одному узлу"""
        try:
            # Формируем сообщение
            message = {
                'type': msg_type,
                'sender': self.node_id,
                **kwargs, # Все дополнительные поля
            }

            distance = self.calculate_distance(target_id)
            propagation_delay = self.calculate_propagation_delay(target_id)     # Время прохождения одного бита в среде
            transmission_duration = self.calculate_transmission_duration(message)   # Длительность ифнормационного потока в секундах
            total_delay = self.calculate_total_delivery_time(target_id, message)

            print(f"\n[{self.node_id}] {msg_type} -> {target_id}")
            print(f"    Расстояние: {distance:.0f}м")
            print(f"    Задержка: {propagation_delay:.2f}с + {transmission_duration:.2f}с = {total_delay:.2f}с")

            message['target'] = target_id

            # Подключаемся
            reader, writer = await asyncio.open_connection(
                '127.0.0.1',
                7777, # NODES[target_id]['port'], 
            )

            current_time = time.time()
            message['time_st_b'] = current_time + propagation_delay
            message['time_end_b'] = current_time + propagation_delay + transmission_duration
            
            writer.write(json.dumps(message).encode())
            await writer.drain()

            # Засыпаем на время модуляции всего сигнала, имитируя передачу
            await asyncio.sleep(transmission_duration) 

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

            time_end_b = msg.get('time_end_b')
            if time_end_b < time.time():
                return
            else:
                await asyncio.sleep(time_end_b - time.time())
                msg_type = msg['type']

                if msg_type == 'Hello':
                    await self.handle_hello(msg, writer)

                # if msg_type == 'Type':    Шаблон запуска обработчка
                #     await self.handle_type(msg, writer)

                    # # Отправляем подтвержение опционально         
                    # response = {'type':'HelloAck', 'from': self.node_id}  ACK-msg, как пример
                    # writer.write(json.dumps(response).encode())
                    # await writer.drain()

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

class Proxy:
    def __init__(self, host='127.0.0.1', port=7777):
        self.host = host
        self.port = port
        self.server = None

    async def send_message(self, target_id, msg):
        try:
            msg_out = msg.copy()
            msg_out.pop('time_st_b', None)
            msg_out.pop('target', None)

            time_st_b = msg.get('time_st_b')

            # Ждем когда первый бит пройдет по среде
            if time_st_b > time.time():
                await asyncio.sleep(time_st_b - time.time())

                # Подключаемся
                reader, writer = await asyncio.open_connection(
                    '127.0.0.1',
                    NODES[target_id]['port'], 
                )

                writer.write(json.dumps(msg_out).encode())
                await writer.drain()
                
                print(f"[ПОСРЕДНИК] Отправил {msg.get('type')} -> {target_id}")

            else:
                print(f"[ПОСРЕДНИК] опоздание при отправке {msg.get('msg_type')} -> {target_id}") 
            # Закрываем
            writer.close()
            await writer.wait_closed()

        except Exception as e:
            print(f"[ПОСРЕДНИК] Ошибка отправки к {target_id}: {e}")

    async def handle_client(self, reader, writer):
        try:
            data = await reader.read(1024)
            if not data:
                return

            msg = json.loads(data.decode())
            print(f"[ПОСРЕДНИК] Получено  {msg.get('type')} от {msg.get('sender')} для {msg.get('target')}")

            # Просто пересылаем получателю
            target_id = msg.get('target')
            if target_id:
                await self.send_message(target_id, msg)
                # Закрываем прошлое соединение
                writer.close()
                await writer.wait_closed()
                
        except json.JSONDecodeError as e:
            print(f"[ПОСРЕДНИК] Ошибка парсинга JSON: {e}")
        except Exception as e:
            print(f"[ПОСРЕДНИК] Ошибка обработки: {e}")
        finally:
            # Закрываем соединение с отправителем
            writer.close()
            await writer.wait_closed()
            print(f"[ПОСРЕДНИК] Соединение с отправителем закрыто")

    async def start(self):
        self.server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port
        )
        print(f"[ПОСРЕДНИК] Запущен на {self.host}:{self.port}")
        await self.server.serve_forever()


async def main():
    # Запускаем менеджер среды (посредника)
    proxy = Proxy()
    proxy_task = asyncio.create_task(proxy.start()) # Запускаем Proxy в фоне
    await asyncio.sleep(1) # ждем, когда запустится сервер

    # Создаем и запускаем все узлы
    nodes = []
    for node_id in NODES:
        node = SimpleNode(node_id)
        task = asyncio.create_task(node.run())
        nodes.append(task)

    # Ждем завершения (никогда не завершится)
    await asyncio.gather(*nodes)

if __name__ == '__main__':
    # reset_network_config() # подготовка исходной конфигурации

    print("Запуск 5 узлов...")
    print("Нажмите Ctrl+C для остановки")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nОстановка...")
