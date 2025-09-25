"""
server_lib/monitor.py
Função para monitorar timeout dos peers.
"""

import time
from .config import HEARTBEAT_INTERVAL, HEARTBEAT_TIMEOUT
from .state import peer_status, status_lock

def timeout_monitor():
    """Verifica periodicamente se algum peer ficou inativo."""
    while True:
        time.sleep(HEARTBEAT_INTERVAL)
        now = time.time()
        with status_lock:
            for peer_id, info in list(peer_status.items()):
                if (now - info['last_alive']) > HEARTBEAT_TIMEOUT:
                    print(f"!!! Peer {peer_id} está INATIVO (timeout) !!!")
                    del peer_status[peer_id]
