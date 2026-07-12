import socket
import threading
import time

from typing import Set #, Dict, Any, List, Tuple

from datetime import datetime

import os
import json
import struct
from pathlib import Path
import argparse

from config import positions, table_round, PORT_MAP
from Parser import fileEnvNodeCreate
from Parser import process_all_data
from logger import create_logger
from network import create_socket
from calculations import calculate_propagation_delay, find_unique_packets

# from Parser import reconstruct_all_data, reconstruct_data

# === Аргументы ===
parser = argparse.ArgumentParser()
parser.add_argument("--id", required=True)   # required - обязательные значения 
parser.add_argument("--pos", required=True, help="x,y например 0,10 или -10,-5") # help Комментрарии внутри кода
parser.add_argument("--packets", type=str, default="")  # Тип преобразованных данных str. Если не задан аргумент - default
parser.add_argument("--sink", action="store_true")  # Укаание на булевые значения. Если не указан аргумент - false
args = parser.parse_args()

def parse_packets(s: str) -> Set[int]:
    if not s: return set()
    if '-' in s:
        a, b = map(int, s.split('-'))
        return set(range(a, b+1))
    return set(map(int, s.split(',')))

# === Данные узла ===
node_id = args.id
position = tuple(map(float, args.pos.split(',')))

is_sink = args.sink
if is_sink:
    is_sink = '1'
else:
    is_sink = '0'

"""Априорная информация, которую неободимо собирать в процессе функционирования всей сети,
используя служеюные сообщения. Для упрощения, known_network известе с самого начала"""
# known_network: Dict[str, Dict[str, Any]] = {}

network_status = {}
network_status[node_id] = {
    'packets': {},
    'position': position,
    'is_sink': is_sink,
    'neibors': {},    # neibors = {node's_id: {'position': (), 'packets_id': [...], 'is_sink': is_sink}}
    }

node_ports = PORT_MAP.copy()

# === Сокет === #
my_port = PORT_MAP[node_id]
sock = create_socket(my_port, clearing=True) # Создание сокета и отчистка буфера сообщений

print(f"\n=== Узел {node_id} запущен ===")
print(f"Порт: {my_port}") ### Для моделирования
print(f"Позиция: {position}") ### Для моделирования
print(f"Известные порты: {node_ports}") ### Для моделирования
if is_sink == '1':
    print("СТАТУС: Я — СТОК") 
elif is_sink == '0': 
    print("СТАТУС - Я НЕ СТОК!")
print("=" * 30)

# === Утилиты ===

# Настройка логирования
log_file = 'logs.txt'
log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), log_file)
logger = create_logger(node_id, log_path)

def send_to(target_id, data, purpose_nodes, Route, msg_type):
    
    # Создаем шаблон сообщения
    msg = {'type': msg_type,
           'sender': node_id,
           'time': time.time(),}
    
    if msg_type == 'Hello':
        msg['position'] = position
        msg['packets_id'] = network_status[node_id]['packets']
        msg['is_sink'] = is_sink
        
    if msg_type == 'Known_Fullset':
        msg['data'] = data
        msg['route'] = Route
        msg['recievers'] = purpose_nodes
        
    if msg_type == 'Retrans_Fullset':
        msg['data'] = data
        msg['recievers'] = purpose_nodes

    if msg_type == 'Request':
        msg['recievers'] = purpose_nodes
        msg['data'] = data
        msg['route'] = Route
        
    if msg_type == 'Packets':
        # msg['data'] = data
        msg['route'] = Route
        msg['recievers'] = purpose_nodes
        
        # Костыль, чтобы не слать два сообщения (все в одном)
        if isinstance(data, list):
            msg['neibors'] = data[1] # Info_target
            # msg['data'] = data[0] # data (packets)
    
    # Трансформируем сообщение в нужный формат
    msg_json = json.dumps(msg).encode()
    length_msg_json = len(msg_json)
    
    msg_out = struct.pack(f'!I{length_msg_json}s', length_msg_json, msg_json)
    
    # Отдельно если это пакеты необходимо добавить пакеты в конец. и читать их затем последовательно
    if msg_type == 'Packets':
        if isinstance(data, list):
            packets = data[0]
        else:
            packets = data
            
        for data_index in packets:
            pckg_folder_name_byte = data_index.encode('utf-8')
            length_pckg_folder_name = len(pckg_folder_name_byte)
           
            msg_out += struct.pack(f'!B{length_pckg_folder_name}s', length_pckg_folder_name, pckg_folder_name_byte)

            for pckg in packets[data_index]:
                pckg_name_byte = pckg.encode('utf-8') # Перерводим название в байты, посокльку оно строковое
                length_pckg_name = len(pckg_name_byte) # Получаем длину в байтах
                
                # Формируем добавочкную поссылку, включая каждый пакеты последовательно в сообщение на отправку
                msg_out += struct.pack(f'!B{length_pckg_name}s', length_pckg_name, pckg_name_byte) + packets[data_index][pckg]
                    
    # Отправляем сообщение
    try:
        # Добавляем задержку распространения сигна (иммитация задежки)
        prorp_delay, _ = calculate_propagation_delay(positions[target_id], position)
        
        total_delay = prorp_delay + 0.05
        
        # 2. фиксируем "момент старта передачи"
        start_time = datetime.now()
           
        if purpose_nodes:
            if target_id in purpose_nodes:
                # 3. логируем именно его
                logger['log_event_send'](
                    msg_type=msg_type,
                    targets=[target_id],
                    delay=total_delay,
                    start_time=start_time)
        
        # Создаем преамбулу сообщения
        temp1 = {'type': 'CONFIG',
                 'sender': node_id,
                 'recv_msg': msg_type, 
                 'time_start': time.time(),}

        temp1_json = json.dumps(temp1).encode()
        length_temp1_json = len(temp1_json)
        CONFIG = struct.pack(f'!{length_temp1_json}s', length_temp1_json, temp1_json)
        
        time.sleep(total_delay) # Ждем время распространения сигнала
        
        sock.sendto(CONFIG, ('127.0.0.1', node_ports[target_id]))
        
        t_modul = len(msg_out)/100 
        time.sleep(t_modul)
        
        # ОТПРАВКА
        sock.sendto(msg_out, ('127.0.0.1', node_ports[target_id]))
        print(f"[{node_id}]: Отправил {msg['type']} -> {target_id}")
    except Exception as e:
        print(f"[{node_id}]: Ошибка отправки в {target_id}: {e}")   

def send_in(msg_type=None, data=None, purpose_nodes=None, Route=None):
    """
    Функция, которая отправляет сообщения всем в радиусе.
    Иммитация ненаправленного излучения (сообщение содержит метку получателя) 
    
      - data: передаваемые данные (пакеты)    
        
      - target: сосед, которому отправляется сообзение,
        
      - purpose_nodes: кому назначено это сообщение.
        
    """
    # Запускаем отдельные процессы для отправки сообщений всем соседям в радиусе
    print("") # Структура вывода
    for target in table_round[node_id].keys():
        threading.Thread(target=send_to, args=(target, data, purpose_nodes, Route, msg_type,), daemon=True).start()
    
def process_request_packets(msg):
    print("\n====Обрабатываю запрос====")
    # def process_request_packets(msg, mode): # mode: SndPck or RtrPck
    need_packets_dict = msg.get('data').get('need_packets') #  {idx: list('n1','n2'...)}
    
    need_packets = set(list(need_packets_dict.values())[0])
    data_index = list(need_packets_dict)[0]
    
    # Сохраняем полученную инфомрацию в переменную
    neibors_cluster = msg.get('data').get('neibors') # neibors = {node's_id: {'position': (), 'packets_id': [...]}}
    
    back_node = msg.get('route').copy()
    
    print(f" Текущий кластер: {list(neibors_cluster)}")
    print(f" need_packets: {need_packets}")
    
    # Проверяем наличие need_packets у соседей
    around_packets = set() # Сумма пакетов у всех соседей в радиусе
    for node in neibors_cluster:
        # Если нет папки с рассматриваемыми пакетами создаем пустую папку
        if data_index not in neibors_cluster[node]['packets']:
            neibors_cluster[node]['packets'][data_index] = list()
    
        around_packets.update(set(neibors_cluster[node]['packets'][data_index]))
            
    local_need = need_packets - around_packets
    print(f" Сумма пакетов в кластере: {around_packets}\n Не хватает: {local_need}")
    if local_need != need_packets: # Если "==", кластер не содержит запрошенных пакетов для отправки
        
        # Поиск уникальных пакетов
        NodeAndUniqPck, all_unique_packets = find_unique_packets(neibors_cluster.copy(), data_index)
        
        # Некоторые уникальные пакеты не пересекаются с need_packets - отфильтруем
        for key, value in NodeAndUniqPck.items():
            NodeAndUniqPck[key] = value & need_packets

        # Хранилище загрузок
        busy_storage = {} # {'node_id': num}        

        # Создаем переменную, в которой будут узлы и пакеты, которые они отправят
        send_storage = NodeAndUniqPck.copy()

        for key, value in NodeAndUniqPck.items():
            busy_storage[key] = len(value)
            
        # Находим оставшиеся пакеты
        remaining_packets = need_packets - all_unique_packets
        print(f" uniq_packets: {need_packets - remaining_packets}")
        print(f" remaining_packets: {remaining_packets}")
        
        # Уникальные пакеты не покрывают запрос полностью - есть оставшиеся пакеты
        remaining_packets = need_packets - all_unique_packets # Находим оставшиеся пакеты
        
        if remaining_packets != set():
            for pck in remaining_packets:
                sorted_busy_storage = dict(sorted(busy_storage.items(), key=lambda x: x[1])) # Сортировка по возрастанию загрузки
                for key, bus_value in sorted_busy_storage.items():
                        if pck in neibors_cluster[key]['packets'][data_index]:                            
                            busy_storage[key] += 1
                            send_storage[key].update(set([pck]))
                            break
        
        print(f" Результат распределения нагрузки:\n {send_storage}")
        # Создаем шаблон сообщения для отправки
        msg_to_send = {data_index: {}} # Пустоее сообщение
        if node_id in send_storage and send_storage[node_id] != set(): # Проверка на наличии пакетов для отправки
            for i in list(send_storage[node_id]):
                pkg_name = i + '.bin'
                pkg = Path('Node_'+node_id + '/Packages/' + data_index + '/' + pkg_name)
                with open(pkg, 'rb') as p:    
                    msg_to_send[data_index][i] = p.read()
            
            recs = back_node.copy()[-1]
            recs_target = list(set(recs)&set(network_status[node_id]['neibors']))
            R = back_node.copy() # Создаем копию для изменения
            R.pop() 
            
            print(f" Маршрут запроса: {back_node}\n Получатели: {recs_target}\n{'='*20}")
            
            if len(back_node) < 2:
                # Отправляем всем узлам назад (по запросу) пакеты, чтобы они могли распределить нагрузку
                
                with send_lock:
                    send_in(msg_type='Packets', 
                            data=msg_to_send, 
                            purpose_nodes=recs_target, 
                            Route=R)
            else:
                info_target = {}
                """Поскольку алгоритм распределяет пакеты на основе пакетов,
                содержащихся у соседей, при ретрансляции необходимо искусственно
                показать, что у соседей есть эти пакеты, даже если у них на текущий
                момент еще нет этих пакетов
                """
                for n in recs_target:
                    info_target[n] = network_status[node_id]['neibors'][n].copy()
                    if data_index in info_target[n]['packets']:
                        info_target[n]['packets'][data_index] += list(msg_to_send[data_index])
                    else:
                        info_target[n]['packets'][data_index] = list(msg_to_send[data_index])
                
                extend_msg_to_send = [msg_to_send, info_target]
                # Если пакеты отправляются для ретрансляции, необходимо дополнительно передать информацию о соседях
                send_in(msg_type='Packets', 
                        data=extend_msg_to_send, 
                        purpose_nodes=recs_target, 
                        Route=R)
        
    if local_need != set(): # Есть пакеты, которых не хватает кластеру     
        retrans_msg = msg.copy() # Копирую сообщение в отдельную переменную
        retrans_msg['data']['need_packets'] = {data_index: list(local_need)} # Записываю новый need_packets
        
        retranslation(retrans_msg, 'Request')
                
def retranslation(msg, mode):
    print("\nЗапускаю алгоритм ретрансляции")
    sender = msg.get('sender')
    neibors_cluster = msg.get('data').get('neibors')
    whom_to_send = {}
    back_node = msg.get('route')

    # Собираю всех своих соседей, которые не принадлежат моему кластеру и не являются отправителем
    for neibor in network_status[node_id]['neibors']:
        if neibor != sender and neibor not in neibors_cluster and neibor not in back_node:
            whom_to_send[neibor] = network_status[node_id]['neibors'][neibor]
     
    who_to_send_mt = {} # mt - my_target: кто может отправлять моим таргетам?
    
    # Ищем всех, кто связан с whom_to_send из neibors_sender, используя координаты
    for node1 in whom_to_send:
        who_to_send_mt[node1] = {}
        for node2 in neibors_cluster:
            _, dist = calculate_propagation_delay(whom_to_send[node1]['position'],neibors_cluster[node2]['position'] )
            # if dist < 79:
            if dist < 79*20:
                who_to_send_mt[node1].update({dist: node2})
    
    for node in who_to_send_mt:
        source_and_target = {who_to_send_mt[node][min(list(who_to_send_mt[node]))]: node} # {node_id:}
    
    if node_id in source_and_target:
        print(f"source_and_target:\n{source_and_target}\n\n")
        
        if mode == 'Fullset':
            msg_to_send_retranslation = {'neibors': whom_to_send,
                                         'fullset': msg.get('data').get('fullset'),}
            
            someNodes = list()
            for node in source_and_target[node_id]:  
                someNodes.append(node)
            
            R = back_node.copy() # Создаем копию для изменения
            R.append(list(neibors_cluster))
            
            # Выравниваю передачи по времени, чтобы они наинались одовременно всеми абонентами
            print(f"Ретранслирую {mode} в {someNodes}")
            
            with send_lock:
                send_in(msg_type='Known_Fullset',
                        data=msg_to_send_retranslation,
                        purpose_nodes=someNodes,
                        Route=R)
        
        elif mode == 'Request':
            
            msg_to_send_retranslation = {'neibors': whom_to_send,
                                         'need_packets': msg['data']['need_packets'],} # local_need pcks
            
            # someNodes = list()
            # for node in source_and_target[node_id]:    
            #     someNodes.append(node)
            
            R = back_node.copy() # Создаем копию для изменения
            R.append(list(neibors_cluster))
            print(f"Ретранслирую {mode} в {list(whom_to_send)}")
            
            with send_lock:
                send_in(msg_type='Request', 
                        data=msg_to_send_retranslation, 
                        purpose_nodes=list(whom_to_send), 
                        Route=R)
    
    else:
        print(f"Я не учавствую в ретрансляции {mode}")

buff_msg_req = []
buff1_lock = threading.Lock()
buff2_lock = threading.Lock()

def Waiting(waiting_time, current_time):
    """В течении 5 секунд собираем все всходящие сообщения, чтобы не обрабатывать
    каждый запрос по отдельности. Спустя 5 секнуд приема всех входящих сообщений
    проверяем маршрут, чтобы он совпадал для всех сообщений; Обхединяем сообщения
    в одно большое, в котором складываются только узлы соседи"""
    
    while (time.time() - current_time) < waiting_time:
        time.sleep(0.05) # 50 ms
        
    with buff1_lock:
        if not buff_msg_req:
            return
        
        first_msg = buff_msg_req[0].copy() # Берем кластер отправителя из первого сообщения
        r = first_msg.get('route')
        
        # Проверяем, что у всех сообщений одинаковый route
        for msg in buff_msg_req:
            if msg.get('route') != r:
                print("Общий кластер отправителя неправильный! Пропускаем весь батч.")
                buff_msg_req.clear()
                return
         
        # Собираем полное сообщение
        full_msg = first_msg.copy()
        for msg in buff_msg_req:
            full_msg['data']['neibors'].update(msg['data']['neibors'])
        
        buff_msg_req.clear()
        
        # Один раз запускаем обработку
        process_request_packets(full_msg)

active_rx = {} # Exemple {'A':{time_start: 9999, msg_type: 'Hello'}}
flag_recieve = False

def receive_handler():
    while True:
        try:
            data, addr = sock.recvfrom(4096)
            
            # Если сейчас идет передача, я не могу принимать.
            if send_lock.locked():
                continue
            
            length_msg_byte_info = struct.unpack('!I', data[:4])[0] # [0], поскольку unpack возвращает map()
            msg_info_byte = data[4:4+length_msg_byte_info] # Словарь с информацией
            
            msg = json.loads(msg_info_byte.decode())
            
            sender = msg.get('sender')
            
            if msg.get('type') == 'CONFIG':
                active_rx[sender] = {'time_start':  msg.get('time_start'),
                                     'recv_msg': msg.get('recv_msg')}
                continue
                
            if msg.get('type') == 'Hello':
                if sender in active_rx: # =================================== #
                    if msg.get('type') in active_rx[sender]['recv_msg']: # == #
                        
                        # Опустошаем active_rx, когда полностью приняли сообщение
                        active_rx.pop(sender)
                        # ====================================#
                        
                        print(f"\nПолучил {msg.get('type')} от {sender}")
                    
                        # Обновляем информацию о своих соседях
                        network_status[node_id]['neibors'].update({sender: {'position': msg.get('position'), 
                                                                            'packets': msg.get('packets_id'), 
                                                                            'is_sink': msg.get('is_sink')
                                                                            }})
                        continue
            
            if msg.get('type') == 'Known_Fullset':
                if sender in active_rx: # =================================== #
                    if msg.get('type') in active_rx[sender]['recv_msg']: # == #
                        
                        # Опустошаем active_rx, когда полностью приняли сообщение
                        active_rx.pop(sender)
                        # ====================================#
                        
                """
                'route': list(...)
                'data' = {'neibors': network_status[node_id]['neibors'],
                        'fullset': temp_data['fullset'],}
                """
                recievers = msg.get('recievers')
                
                if not sender or sender == node_id or node_id not in recievers :
                # if not sender or sender == node_id:
                    continue
                
                print(f"\nПолучил {msg.get('type')} от {sender}")
                
                # Заполняю знания
                temp_storage.update(msg.get('data').get('fullset'))
                
                # Если я конечный узел, останавливаюсь
                if is_sink == '1':
                    continue
                
                # Если среди моих сосдей сток и он получил данные - останавливаюсь
                stop_var = 0
                for val in msg.get('data').get('neibors').values():
                    if val['is_sink'] == '1':
                        print('Стоковый узел получил Мета-данные')
                        stop_var += 1
                        break
                if stop_var == 1:
                    continue

                # Запускаем алгоритм ретрансляции
                retranslation(msg, 'Fullset')
                continue
            
            if msg.get('type') == 'Request':
                if sender in active_rx: # =================================== #
                    if msg.get('type') in active_rx[sender]['recv_msg']: # == #
                        
                        # Опустошаем active_rx, когда полностью приняли сообщение
                        active_rx.pop(sender)
                        # ====================================#
                
                recievers = msg.get('recievers')
                
                if not sender or sender == node_id or node_id not in recievers:
                # if not sender or sender == node_id:
                    continue
                
                print(f"\nПолучил {msg.get('type')} от {sender}: {list(msg.get('data').get('need_packets'))}")

 
                """
                msg_request_packets = {
                    'neibors': network_status[node_id]['neibors'],
                    'need_packets': list(need_packets),}
                """
                with buff1_lock:
                    was_empty = len(buff_msg_req) == 0
                    buff_msg_req.append(msg)

                # Запускаем таймер ТОЛЬКО если буфер был пустой
                if was_empty:
                    threading.Thread(
                        target=Waiting,
                        args=(5, time.time()),   # 5 секунд (можно изменить)
                        daemon=True
                    ).start()
                
                continue
                
            if msg.get('type') == 'Packets':
                if sender in active_rx: # =================================== #
                    if msg.get('type') in active_rx[sender]['recv_msg']: # == #
                        
                        # Опустошаем active_rx, когда полностью приняли сообщение
                        active_rx.pop(sender)
                        # ====================================#
                
                recievers = msg.get('recievers')
                # Если в сообщении нет отправилея / Если отправил сам себе / Если получателем являюсь не я
                if not sender or sender == node_id or node_id not in recievers:
                # if not sender or sender == node_id:
                    continue

                packets = data[4+length_msg_byte_info:]
                
                if len(packets) == 0:
                    print(f"[{node_id}] Получены пакеты, но нет данных!")
                    continue
                
                # offset - смещение
                ofset = 0 #---------# 
                
                pkg_folder_name_length = struct.unpack('!B', packets[:1])[0]
                
                ofset += 1 #---------#
                
                pkg_folder_name = packets[ofset:ofset+pkg_folder_name_length].decode('utf-8')
                
                ofset += pkg_folder_name_length
                
                # Создаем папку для созранения, если ее нет
                path_to_save = 'Node_' + node_id + '/Packages/' + pkg_folder_name
                os.makedirs(path_to_save, exist_ok=True)
                
                new_packets = [] # Список всех новых пакетов
                while ofset < len(packets):
                    
                    """Get packets name and value"""
                    pckg_name_length = struct.unpack('!B', packets[ofset:ofset+1])[0]
                    
                    ofset += 1 #---------#
                    
                    pckg_name = packets[ofset: ofset+pckg_name_length].decode('utf-8')
                    new_packets.append(pckg_name) # Write new_packets
                    
                    ofset += pckg_name_length #---------#
                    
                    pkcg_data = packets[ofset:ofset+60] 
                    
                    ofset += 60 #---------#
                    
                    # Save packets in my storage
                    path_to_save_file = path_to_save + '/' + pckg_name + '.bin'
                    with open(path_to_save_file, 'wb') as ptsf:
                        ptsf.write(pkcg_data)
                
                print(f"\nПолучил PACKETS от {sender}: {new_packets}")
                
                if 'packets' not in network_status[node_id]:
                    network_status[node_id]['packets'] = {}
                    
                if pkg_folder_name not in network_status[node_id]['packets']:
                    network_status[node_id]['packets'][pkg_folder_name] = []
                    
                network_status[node_id]['packets'][pkg_folder_name] += new_packets
                    
                print(f"[{node_id}] Обновил свои пакеты в network_status:\n  - {network_status[node_id]['packets']}")
                
                # Если были получены пакеты и в route есть следующие получатели
                if msg['route'] != list():
                    # Необходимо разделить на два сообщения
                    if 'neibors' in msg:
                        # Получаем список соседей, который совместо учавствуют в ретрансляции (актуализированный)
                        Neibors = msg.get('neibors') # Абоненты, которые учавствуют в передаче
 
                        msg_to_send = msg.copy()
                    
                        msg_to_send.pop('neibors')
                        
                        msg_to_send['data'] = {'neibors': Neibors, 
                                               'need_packets': {pkg_folder_name: new_packets}}
                                
                        process_request_packets(msg_to_send)
                        
                        """Формируем как при request данные. Исскусствено созданный need_packets,
                        чтобы узлы могли распределить между собой нагрузку. local_need в таком
                        случае будет равен нулю, посколку need_packets состоит из имеющихся пакетов.
                        Отправляем пакеты дальше, изменя route. mode=None, чтобы избежать ненужной 
                        ретрансляции"""
                        
        except socket.timeout:
            continue
        except ConnectionResetError as cre:  # ← СПЕЦИФИЧЕСКОЕ ИСКЛЮЧЕНИЕ ПЕРВЫМ
            print(f"[{node_id}] Подключение к несуществующему узлу <{cre}>")
            import traceback
            traceback.print_exc()
            continue
        except json.JSONDecodeError as e:
            print(f"[{node_id}] Ошибка декодирования JSON: {e}")
            continue
        except Exception as e:  # ← ОБЩЕЕ ИСКЛЮЧЕНИЕ ПОСЛЕДНИМ
            print(f"[{node_id}] Ошибка приема: {type(e).__name__}: {e}")
            continue

def receive_from(): # Here must be only recive config message!
    while True:
        try:
            data, addr = sock.recvfrom(4096)
            
            # Если сейчас идет передача, я не могу принимать.
            if send_lock.locked():
                continue
            
            length_msg_byte_info = struct.unpack('!I', data[:4])[0] # [0], поскольку unpack возвращает map()
            msg_info_byte = data[4:4+length_msg_byte_info] # Словарь с информацией
            
            msg = json.loads(msg_info_byte.decode())
            
            sender = msg.get('sender')
            
            if msg.get('type') == 'CONFIG':
                with recieve_lock:
                    active_rx[sender] = {'time_start':  msg.get('time_start'),
                                         'recv_msg': msg.get('recv_msg')}
                    receive_handler()
                continue
         
        except socket.timeout:
            continue
        except ConnectionResetError as cre:  # ← СПЕЦИФИЧЕСКОЕ ИСКЛЮЧЕНИЕ ПЕРВЫМ
            print(f"[{node_id}] Подключение к несуществующему узлу <{cre}>")
            import traceback
            traceback.print_exc()
            continue
        except json.JSONDecodeError as e:
            print(f"[{node_id}] Ошибка декодирования JSON: {e}")
            continue
        except Exception as e:  # ← ОБЩЕЕ ИСКЛЮЧЕНИЕ ПОСЛЕДНИМ
            print(f"[{node_id}] Ошибка приема: {type(e).__name__}: {e}")
            continue

send_lock = threading.Lock()
recieve_lock = threading.Lock()

def Hello():
    print('Starting exchange Hello message')
    time.sleep(12)
    while True:
        # # Проверяем в цикле активность приема
        # while True:
        #     if flag_recieve == True:
        #         continue
        #     else:
        #         break
        if recieve_lock.locked():
            time.sleep(0.1)
            continue
        
            with send_lock:
            # if send_lock.acquire(timeout=5)
                send_in(msg_type='Hello',)
            
            for key, value in network_status[node_id]['neibors'].items():
                print(f"| - [{key}]:\n |{'-'*5}>position: {value['position']}\n |{'-'*5}>packets_id: {value['packets']}")
        else:    
            time.sleep(47.4)
        
# def Hello():
#     time.sleep(12)
#     while True:
#         # Пытаемся захватить lock с таймаутом 5 секунд
#         if send_lock.acquire(timeout=5):
#             try:
#                 send_in(msg_type='Hello',)
#             finally:
#                 send_lock.release()  # обязательно освобождаем
#         else:
#             # Не удалось захватить lock за 5 секунд
#             print("Не удалось получить lock, пропускаем итерацию")
#             # Можно либо пропустить, либо повторить попытку
        
#         for key, value in network_status[node_id]['neibors'].items():
#             print(f"| - [{key}]:\n |{'-'*5}>position: {value['position']}\n |{'-'*5}>packets_id: {value['packets']}")
        
#         time.sleep(11)
            
                     
def MainLoop():    
    time.sleep(15)
    
    while True:
        """Fullset"""
        if node_id == 'A' and temp_storage != {}:
            print("Я источник с полным набором данных")
        
            # Формируем посылку
            msg_to_send_info = {'neibors': network_status[node_id]['neibors'],
                                'fullset': temp_storage,}
            
            while recieve_lock.locked():
                pass
            with send_lock: 
                send_in(msg_type='Known_Fullset',
                        data=msg_to_send_info,
                        purpose_nodes=list(network_status.get(node_id).get('neibors')), 
                        Route=list(node_id),) # Отправляем сообщение всем в радиусе

        """Request"""                  
        if is_sink == '1' and temp_storage != {}: # Пришла информация о существоании в сети некоторого изображения (индексы его пакетов)
            
            # Поиск недостающих пакетов
            for pkg_folder in temp_storage:
                if pkg_folder in network_status[node_id]['packets']: # Есть папка, но не хватает пакетов
                    need_packets = {pkg_folder: list(set(temp_storage[pkg_folder]) - set(network_status[node_id]['packets'][pkg_folder]))}
                    if need_packets != set():
                        break
                    continue
                
                else: # Нет папки с пакетами
                    need_packets = {pkg_folder: list(temp_storage[pkg_folder])}
                    break
            
            # Зная, что пара ключ-значение - одна, можно так:
            if list(need_packets.values())[0] != list() and network_status[node_id]['neibors'] != {}:        
                msg_request_packets = {
                    'neibors': network_status[node_id]['neibors'],
                    'need_packets': need_packets,}
                
                while recieve_lock.locked():
                    pass
                with send_lock:
                    send_in(msg_type='Request',
                            data=msg_request_packets,
                            purpose_nodes=list(network_status[node_id]['neibors']),
                            Route=list(node_id),)
        time.sleep(30)

# === Запуск ===
fileEnvNodeCreate(node_id) # Создание фалового окружения перед запуском

temp_storage = {}
temp_storage_lock = threading.Lock()

threading.Thread(target=Hello, daemon=True).start()
threading.Thread(target=MainLoop, daemon=True).start()
threading.Thread(target=receive_from, daemon=True).start()

try:
    # Костыль для узлов, с начальным распрпеделением!!!
    """Заранее в папку загружены бинарники рассматриваемого файла"""
    Packages_dir = os.path.join('Node_'+node_id, 'Packages')
    for pckg_folder in os.listdir(Packages_dir):
        path_pckg_folder = os.path.join(Packages_dir, pckg_folder)
        pkgs_list_bin = os.listdir(path_pckg_folder)
        pkgs_list_bin = [i.split('.')[0] for i in pkgs_list_bin]
        temp_storage.update({pckg_folder: pkgs_list_bin}) 
        network_status[node_id]['packets'].update(temp_storage)
        print('Собрал информацию о своих бинарниках')
        
    while True: 
        time.sleep(5)
        
        """Паршу данные, если такие есть (result=True), затем перебираю
        новые пакеты и сохраняю их в temp_storage,
        где 
            ключ - название данных,
            value - список пакетов"""
                        
        if node_id == 'A' and len(os.listdir('node_A/data')) != 0: # or source is True
            result = process_all_data(data_dir = 'Node_'+node_id+'/Data',
                                      packages_dir = 'Node_'+node_id+'/Packages',
                                      storage_dir = 'Node_'+node_id+'/storage',
                                      package_size=60)
            
            # Поскольку данные новые - их полный набор
            if result:
                Packages_dir = os.path.join('Node_A', 'Packages')
                
                for pckg_folder in os.listdir(Packages_dir):
                    path_pckg_folder = os.path.join(Packages_dir, pckg_folder)
                    pkgs_list_bin = os.listdir(path_pckg_folder)
                    pkgs_list = [i.split('.')[0] for i in pkgs_list_bin]
                    
                    temp_storage.update({pckg_folder: pkgs_list})
                    
                    # Обновляем информацию о своих пакетах
                    network_status[node_id]['packets'].update(temp_storage)
                    
        print(f"[{node_id}] Пакеты: {network_status[node_id]['packets']}")
            
except KeyboardInterrupt:
    print(f"\n[{node_id}] Выключаюсь...")