# launch_all_windows_improved.py
import subprocess
import time
import os

from config import RefreshNetConfig

# Копируем из папки исходное состояние сети
# RefreshNetConfig('NetConfig_no_distrib')
# RefreshNetConfig('NetConfig_zero_distrib')
RefreshNetConfig()

# nodes = [
#     {"id": "A", "pos": "0,100,0", "packets": "1-10", "sink": False},
#     {"id": "B", "pos": "50,121,0", "packets": "5-10", "sink": False},
#     {"id": "C", "pos": "50,80,0", "packets": "4-7", "sink": False},
#     {"id": "D", "pos": "50,40,0", "packets": "1-5", "sink": False},
#     {"id": "E", "pos": "100,100,0", "packets": "", "sink": True}
# ]

nodes = [
    {"id": "A", "pos": "0,1200,0", "packets": "1-10", "sink": False},
    {"id": "B", "pos": "1000,1603,0", "packets": "5-10", "sink": False},
    {"id": "C", "pos": "1000,800,0", "packets": "4-7", "sink": False},
    {"id": "D", "pos": "1000,1,0", "packets": "1-5", "sink": False},
    {"id": "E", "pos": "2000,1200,0", "packets": "", "sink": True}
]

print("Создание/очистка logs-файла")

# Название лог-файла
log_file = 'logs.txt'

# Создание пути для существующего/будущего лог-файла
log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), log_file)


if os.path.exists(log_path):
    with open(log_path, 'w') as file:
        print(f"  - Файл {log_file} очищен")
else:
    with open(log_path, 'w') as file:
        print(f"  - Cоздан файл {log_file}")
        pass

time.sleep(1)

print("Запуск 5 узлов в отдельных окнах...")
print("Закройте все окна для завершения работы.\n")

for node in nodes:
    # Собираем команду
    cmd_parts = ["python", "node_16.py", 
                 "--id", node["id"], 
                 "--pos", node["pos"]]
    
    if node.get("packets"):
        cmd_parts.extend(["--packets", node["packets"]])
    if node.get("sink"):
        cmd_parts.append("--sink")
    
    # Запуск в новом окне cmd
    cmd_str = " ".join(cmd_parts)
    subprocess.Popen(f'start cmd /k "{cmd_str}"', shell=True)
    time.sleep(2)  # Увеличил задержку для стабильности

print("Все узлы запущены!")
print("Для завершения закройте окна терминалов вручную.")
