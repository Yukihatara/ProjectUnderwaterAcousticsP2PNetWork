# config.py
import os
import sys
import shutil

"""Знаний расположения всех узлов сети, енобходимое для того,, чтобы реализовать
ненаправленное излучение. В оптимальных алгоритма и протоколов MAC использоваться не будет""" 
positions = {
    'A': tuple(map(float, '0,100,0'.split(','))),       #B
    'B': tuple(map(float, '50,120,0'.split(','))), #A        #E
    'C': tuple(map(float, '50,80,0'.split(','))),       #C
    'D': tuple(map(float, '50,40,0'.split(','))),      
    'E': tuple(map(float, '100,100,0'.split(','))),     #D
}

table_round = {
    'A': {'B': positions['B'], 'C': positions['C'], 'D': positions['D']},
    'B': {'A': positions['A'], 'C': positions['C'], 'E': positions['E']},
    'C': {'A': positions['A'], 'B': positions['B'], 'D': positions['D'], 'E': positions['E']},
    'D': {'A': positions['A'], 'C': positions['C'], 'E': positions['E']},
    'E': {'B': positions['B'], 'C': positions['C'], 'D': positions['D']},
}

dstrb_packets = {
    'A': sorted(set(range(1,11))),
    'B': sorted(set(range(5,11))),
    'C': sorted(set(range(4,8))),
    'D': sorted(set(range(1,6))),
    'E': sorted(set([])),
    }

is_sink_value = {
    'A': False,
    'B': False,
    'C': False,
    'D': False,
    'E': True,
    } 

stok = 'E'

# === ФИКСИРОВАННЫЕ ПОРТЫ ===
PORT_MAP = {
    'A': 5001,
    'B': 5002, 
    'C': 5003,
    'D': 5004,
    'E': 5005
}
# MAX_NODE = 5
# MAX_RANGE = 80
# MAX_PACKETS = list(range(1,11))

def select_config_folder(configs_path='NetConfig'):
    """
    Выбирает папку с конфигурацией из списка доступных.
    
    Args:
        configs_path: путь к папке с конфигурациями
    
    Returns:
        относительный путь к выбранной папке с конфигурацией
    """
    # Получаем список папок в директории
    folders = [f for f in os.listdir(configs_path) 
               if os.path.isdir(os.path.join(configs_path, f))]
    
    # Выводим первые три папки
    print("Доступные конфигурации:")
    for i, folder in enumerate(folders, 1):
        print(f"{i}. {folder}")
    
    # Запрашиваем выбор пользователя
    while True:
        try:
            choice = int(input(f"\nВыберите конфигурацию (1-{len(folders)}): "))
            if 1 <= choice <= len(folders):
                break
            print(f"Пожалуйста, введите число от 1 до {len(folders)}")
        except ValueError:
            print("Пожалуйста, введите корректное число")
    
    # Формируем относительный путь от текущей рабочей директории
    selected_folder = folders[choice - 1]
    
    relative_path = os.path.join(configs_path,selected_folder)

    return relative_path

def RefreshNetConfig():
    
    source_dir = select_config_folder('NetConfig')
    # Текущая директория
    current_dir = os.getcwd()
    
    # Запрашиваем путь к директории-источнику
    # source_dir = 'NetConfig'
    
    # Проверяем, существует ли директория-источник
    if not os.path.exists(source_dir):
        print(f"Ошибка: Директория '{source_dir}' не существует!")
        sys.exit(1)
    
    # Получаем список всех папок в директории-источнике
    try:
        folders_to_copy = [f for f in os.listdir(source_dir) 
                          if os.path.isdir(os.path.join(source_dir, f))]
    except PermissionError:
        print(f"Ошибка: Нет доступа к директории '{source_dir}'")
        sys.exit(1)
    
    if not folders_to_copy:
        print("В указанной директории нет папок для копирования.")
        sys.exit(0)
    
    print(f"\nНайдены папки для копирования: {', '.join(folders_to_copy)}")
    
    # Удаляем существующие папки в текущей директории
    print("\nУдаление существующих папок в текущей директории...")
    for folder in folders_to_copy:
        folder_path = os.path.join(current_dir, folder)
        if os.path.exists(folder_path):
            try:
                if os.path.isdir(folder_path):
                    shutil.rmtree(folder_path)
                    print(f"  Удалена папка: {folder}")
            except (PermissionError, OSError) as e:
                print(f"  Ошибка при удалении {folder}: {e}")
    
    # Копируем папки из источника в текущую директорию
    print("\nКопирование папок...")
    for folder in folders_to_copy:
        source_path = os.path.join(source_dir, folder)
        dest_path = os.path.join(current_dir, folder)
        
        try:
            shutil.copytree(source_path, dest_path)
            print(f"  Скопирована папка: {folder}")
        except (PermissionError, FileExistsError, OSError) as e:
            print(f"  Ошибка при копировании {folder}: {e}")
    
    print("\nГотово!")