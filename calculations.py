# calculations.py
import math
import random

def calculate_propagation_delay(target_position, position):
    """Вычисляем задержку распространения сигнала"""
    dx = position[0] - target_position[0]
    dy = position[1] - target_position[1]
    dz = position[2] - target_position[2]
    dist = math.sqrt(dx**2 + dy**2 + dz**2)
    
    base_delay = dist/1500  # Чистая задержка по скорости звука
    noise = abs(random.gauss(0, 0.05))
    prop_delay = base_delay + noise
    
    return max(prop_delay, 0.001), dist   # Минимально-возможная задержка

def find_unique_packets(neibors, data_index):
    """
    Найти уникальные пакеты у каждого узла в списке.
    
    Уникальный пакет = есть ТОЛЬКО у этого узла, нет у других.
    
    Args:
        nodes_around_target: список ID узлов (например, ['B', 'C', 'D'])
    
    Returns:
        dict: {node_id: [уникальные_пакеты_этого_узла]}
    """
    
    result = {}
    
    # 1. Собираем пакеты всех узлов
    all_packets = {}
    all_unique_packets = set()
    for n_id in neibors:
        all_packets[n_id] = set(neibors[n_id]['packets'][data_index])
    
    # 2. Для каждого узла находим уникальные пакеты
    for n_id, n_packets in all_packets.items():
        # Собираем пакеты ВСЕХ остальных узлов
        other_packets = set()
        for other_id, other_packets_set in all_packets.items():
            if other_id != n_id:
                other_packets.update(other_packets_set)
        
        # Уникальные = есть у этого узла, но нет у других
        unique_packets = n_packets - other_packets
        result[n_id] = set(sorted(list(unique_packets)))  # Сортируем для удобства
        
        all_unique_packets.update(unique_packets)
    
    return result, set(sorted(all_unique_packets))