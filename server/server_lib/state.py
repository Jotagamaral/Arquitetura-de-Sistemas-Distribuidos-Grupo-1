"""
server_lib/state.py
Variáveis globais e locks para status dos peers.
"""

from typing import Dict
import threading

peer_status: Dict[str, Dict] = {}
status_lock = threading.Lock()

# Registro simples de workers que se conectam ao servidor (ip/port, last_seen)
worker_status: Dict[str, Dict] = {}
