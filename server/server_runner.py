"""
server_runner.py
Arquivo principal para rodar o servidor. Pode ser duplicado para criar múltiplos servidores, basta alterar as configurações em server_lib/config.py.
"""

from server_lib.config import MY_IP, MY_PORT, MY_ID, PEER_SERVERS, HEARTBEAT_INTERVAL, HEARTBEAT_TIMEOUT
from server_lib.state import peer_status, status_lock
from server_lib.heartbeat import heartbeat_loop
from server_lib.server_main import server_listen_loop
from server_lib.monitor import timeout_monitor
import threading
import time

if __name__ == "__main__":
    try:
        # Cria e inicia as threads para cada funcionalidade principal
        server_thread = threading.Thread(target=server_listen_loop, daemon=True)
        heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        monitor_thread = threading.Thread(target=timeout_monitor, daemon=True)

        server_thread.start()
        heartbeat_thread.start()
        monitor_thread.start()

        # Mantém a thread principal viva para que as threads de fundo possam rodar
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nServidor encerrado.")
