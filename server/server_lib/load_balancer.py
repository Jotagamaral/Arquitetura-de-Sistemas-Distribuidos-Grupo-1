import socket
import json
import time
from .config import lista_peers, THRESHOLD_WINDOW, THRESHOLD_MIN_TASKS, LOAD_BALANCER_INTERVAL
from .state import tasks_completed_in_window, worker_status, status_lock
from .logger import logger
from .config import MY_ID

def ask_peer_for_workers(peer) -> list:
    """Envia uma solicitação simples a um peer pedindo candidatos workers.
    Retorna lista de worker dicts recebida (pode ser vazia)."""
    try:
        with socket.create_connection((peer['ip'], peer['port']), timeout=5) as s:

            msg = {"MASTER": MY_ID, "TASK": "WORKER_REQUEST"}
            logger.info(f"[LOAD] Solicitando workers a {peer['id']} -> {msg}")

            s.sendall(json.dumps(msg).encode('utf-8'))
            resp = s.recv(8192)

            if not resp:
                return []
            
            data = json.loads(resp.decode('utf-8'))
            if data.get('RESPONSE') == 'AVAILABLE':
                logger.success(f"[LOAD] Recebido Lista de Workers de {peer['id']}: {data.get('WORKERS')}")
                return data.get('WORKERS') or []
            
            elif data.get('RESPONSE') == 'UNAVAILABLE':
                logger.info(f"[LOAD] Nenhuma lista de Workers recebido de {peer['id']}")

            else:
                logger.warning(f"[LOAD] Resposta inesperada de {peer['id']}: {data}")

            return []
        
    except Exception as e:
        logger.warning(f"[LOAD] Falha ao perguntar para peer {peer['id']}: {e}")
        return []

def load_balancer_loop():
    """Loop que verifica o throughput local e pede workers a peers ATIVOS quando necessário."""
    while True:
        time.sleep(LOAD_BALANCER_INTERVAL)
        try:
            count = tasks_completed_in_window(THRESHOLD_WINDOW)
            logger.info(f"[LOAD] Tarefas completadas nos últimos {THRESHOLD_WINDOW}s: {count}")

            if count < THRESHOLD_MIN_TASKS:
                logger.warning(f"[LOAD] Abaixo do threshold ({count} < {THRESHOLD_MIN_TASKS}), solicitando workers a peers.")

                active_peers_snapshot = []
                with status_lock:
                    # Cria uma cópia segura da lista de peers ativos no momento
                    active_peers_snapshot = list(lista_peers)

                if not active_peers_snapshot:
                    logger.info("[LOAD] Nenhum peer ativo para solicitar workers.")
                    continue

                # Itera sobre a cópia segura dos peers que estão ATIVOS
                for peer in active_peers_snapshot:
                    candidates = ask_peer_for_workers(peer)
                    
                    # A lógica para processar os candidatos continua a mesma
                    for w in candidates:
                        wid = w.get('id')
                        if wid in worker_status:
                            logger.info(f"[LOAD] Ignorando worker {wid} porque já está registrado localmente")
                            continue
                        # (Futuramente, aqui entraria a lógica para recrutar o worker)

            else:
                logger.success(f"[LOAD] Acima do threshold ({count} > {THRESHOLD_MIN_TASKS}), servidor não saturado.")
            
            count = 0
        except Exception as e:
            logger.error(f"[LOAD] Erro no loop do load balancer: {e}")