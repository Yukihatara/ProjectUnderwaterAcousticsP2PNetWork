import os
from pathlib import Path

def split_data_to_packages(data_path, output_base_dir, package_size_bytes=1024):
    """
    Разбивает изображение на пакеты фиксированного размера (кроме последнего)
    
    Args:
        data_path: путь к данным WindowsPath('Data/Habr-Info.txt')
        output_base_dir: базовая папка для всех пакетов 'Packeges'
        package_size_bytes: размер пакета в байтах
    """
    
    # Создаем базовую папку
    Path(output_base_dir).mkdir(parents=True, exist_ok=True)
    
    # Получаем имя файла без расширения и создаем подпапку с номером
    # Для удобства используем порядковый номер, но можно и имя файла
    
    # Создаем уникальную папку для этого изображения
    # Нумеруем папки последовательно: 00001, 00002, 00003...
    existing_folders = [d for d in Path(output_base_dir).iterdir() if d.is_dir()]
    next_number = len(existing_folders) + 1
    package_dir = Path(output_base_dir) / f"{next_number}"  # 1, 2, etc.  <-- Folders
    package_dir.mkdir(parents=True)
    
    # # Сохраняем информацию о соответствии папки и исходного файла
    # manifest_file = package_dir / "_manifest.txt"
    # with open(manifest_file, 'w') as f:
    #     f.write(f"original_file: {Path(data_path).name}\n")
    #     f.write(f"original_path: {data_path}\n")
    #     f.write(f"package_size: {package_size_bytes}\n")
    
    # Читаем и разбиваем файл
    with open(data_path, 'rb') as f:
        package_number = 1
        total_bytes = 0
        
        while True:
            # Читаем пакет
            package_data = f.read(package_size_bytes)
            if not package_data:  # Конец файла
                break
            
            # Сохраняем пакет
            package_name = f"{package_number}.bin"  # 1.bin, 2.bin, ...
            package_path = package_dir / package_name
            
            package_size = len(package_data)
            
            if package_size < package_size_bytes:
                package_data = package_data + b'\x00' * (package_size_bytes - package_size)
            
            with open(package_path, 'wb') as pkg_file:
                pkg_file.write(package_data)
            
            total_bytes += package_size
            
            status = "полный" if package_size == package_size_bytes else "последний (меньше)"
            print(f"  Пакет {package_number:05d}: {package_size} байт - {status}")
            
            package_number += 1
    
    print(f"\nДанные '{Path(data_path).name}' разбиты на {package_number-1} пакетов")
    print(f"  Папка: {package_dir}")
    print(f"  Общий размер: {total_bytes} байт\n")
    
    return package_dir, package_number - 1

def process_all_data(data_dir='Data', packages_dir='Packages', storage_dir = 'Storage', package_size=1024):
    """
    Обрабатывает все данные в папке
    """
    data_path = Path(data_dir) # 'Data'
    
    if not data_path.exists():
        print(f"Папка '{data_dir}' не найдена!")
        return
    
    # Получаем пути ко всем файлам в папке с заданым расширением
    data_extensions = ['.txt', '.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp']
    data = []
    for ext in data_extensions:
        data.extend(data_path.glob(f"*{ext}"))
        
        # Система регистронезависимая поэтому только .txt, с учетом .TXT автоматически
        # data.extend(data_path.glob(f"*{ext.upper()}")) 
        
    # data: [WindowsPath('Data/Habr-Info.txt'), ...] для всех файлов
    
    if not data:
        print(f"В папке '{data_dir}' нет новых данных!")
        return False
    
    print(f"Найдено файлов: {len(data)}")
    print("="*60)
    
    
    storage_path = Path(storage_dir)
    storage_path.mkdir(parents=True, exist_ok=True)  # Создаём папку, если её нет
    for i, data_path in enumerate(data, 1): # data_path: Data\Habr-Info.txt
        print(f"\n[{i}/{len(data)}] Обработка: {data_path.name}")
        split_data_to_packages(data_path, packages_dir, package_size)
        
        if storage_dir != None:
            target = storage_path / data[i-1].name
            data_path.rename(target)
        
    print("="*60)
    print(f"Готово! Все данные разбиты на пакеты в папке '{packages_dir}'")
    
    return True



def reconstruct_data(package_dir, output_path=None):
    """
    Восстанавливает данные из пакетов
    
    Args:
        package_dir: папка с пакетами
        output_path: путь для сохранения восстановленного файла
    """
    package_dir = Path(package_dir)
    
    if not package_dir.exists():
        print(f"Папка {package_dir} не найдена!")
        return False
    
    # Читаем манифест
    manifest_file = package_dir / "_manifest.txt"
    if manifest_file.exists():
        with open(manifest_file, 'r') as f:
            for line in f:
                if line.startswith('original_file:'):
                    original_name = line.split(':')[1].strip()
    
    # Получаем все пакеты в правильном порядке
    package_files = sorted(package_dir.glob("*.bin"))
    
    if not package_files:
        print(f"В папке {package_dir} нет пакетов!")
        return
    
    # Определяем имя выходного файла
    if output_path is None:
        if manifest_file.exists():
            output_path = package_dir / f"restored_{original_name}"
        else:
            output_path = package_dir / "restored_data.jpg"
    
    # Восстанавливаем файл простой конкатенацией
    with open(output_path, 'wb') as output_file:
        for pkg_file in package_files:
            with open(pkg_file, 'rb') as pkg:
                output_file.write(pkg.read())
    
    print(f"✓ данных восстановлено восстановлено: {output_path}")
    print(f"  Количество пакетов: {len(package_files)}")
    print(f"  Размер: {output_path.stat().st_size} байт")
    
    return

def reconstruct_all_data(packages_dir='Packages'):
    """
    Восстанавливает все данные из пакетов
    """
    packages_path = Path(packages_dir)
    
    if not packages_path.exists():
        print(f"Папка '{packages_dir}' не найдена!")
        return
    
    # Находим все папки с пакетами (игнорируем системные файлы)
    package_folders = [d for d in packages_path.iterdir() if d.is_dir()]
    
    if not package_folders:
        print(f"В папке '{packages_dir}' нет папок с пакетами!")
        return
    
    print(f"Найдено наборов пакетов: {len(package_folders)}")
    print("="*60)
    
    for folder in package_folders:
        print(f"\nВосстановление: {folder.name}")
        reconstruct_data(folder)
    
    print("="*60)
    print("Готово! Все изображения восстановлены")
    
def fileEnvNodeCreate(node_id):
    # Создаем фаловое окружение каждом узлу
    env_node = Path('node_' + node_id) # Путь к файловому окружению
    packages_storage = env_node / 'Packages' # Путь к папке с пакетами
    data_storage = env_node / 'Data' # Путь к папке с данными (исходными), если такие есть
    delete_storage = env_node / 'Storage' 
    
    # Созда папки, если не были созданы ранее
    env_node.mkdir(parents=True, exist_ok=True)
    packages_storage.mkdir(parents=True, exist_ok=True)
    data_storage.mkdir(parents=True, exist_ok=True)
    delete_storage.mkdir(parents=True, exist_ok=True)
    
    print("Файловое окружение было создано")
    return