"""
server_lib/heartbeat.py
Funções relacionadas ao envio e monitoramento de heartbeat entre servidores.
"""

import socket
import json
import time
from .config import PEER_SERVERS, HEARTBEAT_INTERVAL
from .state import peer_status, status_lock
from .logger import logger

def send_heartbeat(peer):
    """Tenta enviar um heartbeat para um peer e processa a resposta."""
    try:
        with socket.create_connection((peer['ip'], peer['port']), timeout=5) as client_socket:
            msg = {"SERVER_ID": peer['id'], "TASK": "HEARTBEAT"}
            logger.info(f"[HEARTBEAT] Enviando para {peer['id']} ({peer['ip']}:{peer['port']}): {json.dumps(msg)}")
            client_socket.sendall(json.dumps(msg).encode('utf-8'))
            response = client_socket.recv(1024)
            if not response:
                logger.warning(f"[HEARTBEAT] Sem resposta de {peer['id']} ({peer['ip']}:{peer['port']})")
                return
            data = json.loads(response.decode('utf-8'))
            logger.info(f"[HEARTBEAT] Resposta recebida de {peer['id']} ({peer['ip']}:{peer['port']}): {json.dumps(data)}")
            if data.get("RESPONSE") == "ALIVE":
                with status_lock:
                    peer_status[peer['id']] = {'last_alive': time.time()}
    except (socket.timeout, ConnectionRefusedError):
        logger.warning(f"[HEARTBEAT] Falha ao conectar com {peer['id']} ({peer['ip']}:{peer['port']}) - offline ou recusado.")
        with status_lock:
            if peer['id'] in peer_status:
                del peer_status[peer['id']]
    except Exception as e:
        logger.error(f"Erro inesperado em send_heartbeat para {peer['id']}: {e}")

def heartbeat_loop():
    """Loop que envia heartbeats para todos os peers periodicamente."""
    while True:
        for peer in PEER_SERVERS:
            send_heartbeat(peer)
        time.sleep(HEARTBEAT_INTERVAL)
