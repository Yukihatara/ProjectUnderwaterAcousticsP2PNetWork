
import socket
import threading

import struct
import json

import time
from time import datetime

from config import positions, table_round, PORT_MAP
from logger import create_logger

# === Сокет === #
def create_socket(port, clearing = True):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', port))
    sock.settimeout(1.0)
    
    if clearing:
        
        # ОЧИСТКА БУФЕРА: читаем все старые данные
        print("Очищаю буфер сокета...")        
        sock.setblocking(False)
        cleared = 0
        while True:
            try:
                data, addr = sock.recvfrom(4096)
                cleared += 1
                print(f"Очищен старый пакет ({len(data)} байт) от {addr}")
            except (socket.error, BlockingIOError):
                break
        sock.setblocking(True)
        print(f"Очищено {cleared} старых пакетов")
    return sock
    
def send_to(target_id, 
            data, 
            purpose_nodes, 
            Route, 
            msg_type,
            node_id,
            is_sink,
            my_packets,
            logger,
            sock):
    
    # Создаем шаблон сообщения
    msg = {'type': msg_type,
           'sender': node_id,
           'time': time.time(),}
    
    if msg_type == 'Hello':
        msg['position'] = positions[node_id]
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
        prorp_delay, _ = calculate_propagation_delay(positions[target_id], positions[node_id])
        
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
        CONFIG = struct.pack(f'!I{length_temp1_json}s', length_temp1_json, temp1_json)
        
        time.sleep(total_delay) # Ждем время распространения сигнала
        
        sock.sendto(CONFIG, ('127.0.0.1', node_ports[target_id]))
        
        t_modul = len(msg_out)/100 
        time.sleep(t_modul)
        
        # ОТПРАВКА
        sock.sendto(msg_out, ('127.0.0.1', node_ports[target_id]))
        print(f"[{node_id}]: Отправил {msg['type']} -> {target_id}")
    except Exception as e:
        print(f"[{node_id}]: Ошибка отправки в {target_id}: {e}")   

def send_in(node_id,
            is_sink,
            logger,
            socket,
            msg_type=None, 
            data=None, 
            purpose_nodes=None, 
            Route=None,
            my_packets= None,
):
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
        threading.Thread(target=send_to, args=(target, 
                                               data, 
                                               purpose_nodes, 
                                               Route, 
                                               msg_type,
                                               node_id,
                                               is_sink,
                                               my_packets,
                                               logger,
                                               socket,), daemon=True).start()