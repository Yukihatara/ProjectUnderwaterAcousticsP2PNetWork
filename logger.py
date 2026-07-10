# logger.py

import queue
import json
from datetime import datetime
import threading

def create_logger(node_id, log_path):
    """Создает логгер и возвращает функции для работы с ним"""
    log_queue = queue.Queue()
    log_thread_running = True
    
    def log_writer():
        """Отдельный поток для записи логов в файл"""
        nonlocal log_thread_running
        while log_thread_running:
            try:
                log_entry = log_queue.get(timeout=0.5)
                with open(log_path, 'a', encoding='utf-8') as f:
                    f.write(log_entry + '\n')
                    f.flush()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[{node_id}] Ошибка записи лога: {e}")
    
    def log_event_send(msg_type, targets, delay, start_time):
        """Логирует отправку сообщения"""
        if msg_type == 'Hello':
            return
        
        log_entry = {
            "time_start": start_time.isoformat(timespec='milliseconds'),
            "node": node_id,
            "event": "send",
            "type": msg_type,
            "targets": targets if targets else [],
            "delay": round(delay, 4)
        }
        log_queue.put(json.dumps(log_entry, ensure_ascii=False))
    
    def log_event(operation, target, details=None):
        """Логирует общее событие"""
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        target_str = str(target) if target else "ALL"
        details_str = str(details) if details else "None"
        log_message = f"{timestamp} | {node_id} | {operation} | {target_str} | {details_str}"
        log_queue.put(log_message)
    
    def stop_logger():
        """Останавливает поток логгера"""
        nonlocal log_thread_running
        log_thread_running = False
    
    # Запускаем поток
    thread = threading.Thread(target=log_writer, daemon=True)
    thread.start()
    
    # Возвращаем интерфейс для работы
    return {
        'log_event_send': log_event_send, # Use this
        'log_event': log_event,
        'stop': stop_logger,
        'thread': thread
    }

# # Использование:
# logger = create_logger(node_id, log_path)
# logger['log_send'](msg_type, targets, delay, start_time)
# logger['log_event']('receive', sender, 'Got packet')