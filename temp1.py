import os
import shutil
from pathlib import Path

os.chdir(os.path.dirname(os.path.abspath(__file__))) # Изменяем рабочую дирректорию

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

def reset_network_config():
    """
    Сбрасывает сетевую конфигурацию до исходного состояния:
    1. Сканирует папку /NetConfig/Type на наличие папок-конфигураций
    2. Удаляет все папки с такими же названиями из рабочей директории
    3. Копирует свежие папки-конфигурации из /NetConfig/Type обратно в рабочую директорию
    """
    work_dir = Path.cwd()

    typeConfig = select_config_folder('NetConfig')

    config_source = work_dir / typeConfig

    # Проверяем существование папки с конфигурациями
    if not config_source.exists():
        print(f"Ошибка: папка с конфигурацией {config_source} не найдена!")
        return
    
    # Получаем список папок конфигурации узлов (только папки, не файлы)
    config_folders = []
    for item in config_source.iterdir():
        if item.is_dir():
            config_folders.append(item.name)
    
    if not config_folders:
        print("В папке с конфигурациями нет папок для копирования!")
        return
    
    print(f"Найдены папки конфигурации: {', '.join(config_folders)}")
    print("Начинаем сброс сетевой конфигурации...")
    
    # Удаляем старые папки-конфигурации из рабочей директории
    for folder_name in config_folders:
        current_config = work_dir / folder_name
        
        if current_config.exists() and current_config.is_dir():
            print(f"  Удаляем старую конфигурацию: {current_config}")
            shutil.rmtree(current_config)
    
    # Копируем свежие папки-конфигурации из исходной папки в рабочую директорию
    for folder_name in config_folders:
        source_path = config_source / folder_name
        dest_path = work_dir / folder_name
        
        print(f"  Копируем конфигурацию: {source_path} -> {dest_path}")
        shutil.copytree(source_path, dest_path)
    
    print(f"Готово! Восстановлено {len(config_folders)} папок конфигурации.")