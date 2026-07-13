import socket

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