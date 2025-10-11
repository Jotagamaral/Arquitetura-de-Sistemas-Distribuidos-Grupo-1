"""
server_lib/state.py
Armazena informações dinâmicas sobre o estado dos peers e dos workers.
"""
import threading
from collections import deque
from typing import Dict, Any, Deque

# Lock para garantir acesso seguro às estruturas de estado (concorrência)
status_lock: threading.Lock = threading.Lock()

# Status dos Peers (Outros Servidores Master)
# { peer_id: {'last_alive': float, 'is_saturado': bool, 'emprestimo_status': str} }
peer_status: Dict[str, Dict[str, Any]] = {}

# Status dos Workers (A Farm do Master)
# { worker_id: {'addr': tuple, 'last_seen': float, 'original_master': str | None} }
worker_status: Dict[str, Dict[str, Any]] = {}

# Fila de Tarefas Recebidas de Clientes (Simulação de Carga) - Objetivo O3
# Deque é thread-safe o suficiente para as operações básicas de append/pop
# mas o acesso a `len()` deve ser protegido ou tratado com cautela em threads.
# Usaremos `status_lock` para proteger o acesso a esta fila.
task_queue: Deque[Dict[str, Any]] = deque()

# Variável global para armazenar dados incompletos de conexões
# Cada thread de conexão em server_main usará seu próprio buffer local, mas mantemos o conceito.