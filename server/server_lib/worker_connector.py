"""
server_lib/worker_connector.py
Módulo que tenta conectar periodicamente a lista de workers e pede "trabalhos" (WORKER:ALIVE).
"""

import socket
import json
import time
from server_lib.config import WORKER_PEERS, WORKER_POLL_INTERVAL, WORKER_CONNECT_TIMEOUT
from server_lib.logger import logger
from server_lib.state import status_lock


def poll_worker(peer):
    """Tenta conectar a um worker e pedir trabalho."""
    try:
        with socket.create_connection((peer['ip'], peer['port']), timeout=WORKER_CONNECT_TIMEOUT) as s:
            msg = {"WORKER": "ALIVE", "SERVER_ID": "REQUESTOR"}
            logger.info(f"[WORKER] Conectado ao worker {peer['id']} - enviando apresentação: {msg}")
            s.sendall(json.dumps(msg).encode('utf-8'))

            resp = s.recv(4096)
            if not resp:
                logger.warning(f"[WORKER] Sem resposta de {peer['id']}")
                return

            data = json.loads(resp.decode('utf-8'))
            logger.info(f"[WORKER] Resposta do worker {peer['id']}: {data}")

    except (socket.timeout, ConnectionRefusedError) as e:
        logger.warning(f"[WORKER] Falha ao conectar ao worker {peer['id']} ({peer['ip']}:{peer['port']}): {e}")
    except Exception as e:
        logger.error(f"[WORKER] Erro inesperado ao falar com worker {peer['id']}: {e}")


def worker_poll_loop():
    """Loop que percorre a lista de workers periodicamente e tenta pedir tarefas."""
    while True:
        for peer in WORKER_PEERS:
            poll_worker(peer)
        time.sleep(WORKER_POLL_INTERVAL)
