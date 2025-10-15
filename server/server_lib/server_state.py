"""
server_lib/state.py
Variáveis globais e locks para status dos peers.
"""

from typing import Dict, List
import threading
import time

peer_status: Dict[str, Dict] = {}
status_lock = threading.Lock()

# Registro simples de workers que se conectam ao servidor (ip/port, last_seen)
worker_status: Dict[str, Dict] = {}

# Histórico simples de timestamps (epoch) quando tarefas foram concluídas por este servidor
# Usado para calcular throughput / threshold em uma janela de tempo
completed_task_timestamps: List[float] = []

# Fila para armazenar ordens de redirecionamento de workers
# Formato: [{'worker_id': 'xyz', 'target_server': {'ip': '...', 'port': ...}}, ...]
redirect_queue: List[Dict] = []


def record_task_completion(ts: float = None):
	"""Registra uma conclusão de tarefa no histórico."""
	if ts is None:
		ts = time.time()
	with status_lock:
		completed_task_timestamps.append(ts)


def tasks_completed_in_window(window_seconds: int) -> int:
	"""Retorna a contagem de tarefas completadas nos últimos window_seconds."""
	cutoff = time.time() - window_seconds
	with status_lock:
		# remove timestamps antigos para evitar crescimento indefinido
		while completed_task_timestamps and completed_task_timestamps[0] < cutoff:
			completed_task_timestamps.pop(0)
		return len(completed_task_timestamps)
