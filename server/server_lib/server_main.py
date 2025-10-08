"""
server_lib/server_main.py
Funções relacionadas ao servidor principal (escuta e resposta de conexões).
"""

import socket
import threading
import json
import time
from .config import MY_IP, MY_PORT, MY_ID
from .state import peer_status, status_lock, worker_status
from server_lib.logger import logger

def handle_connection(conn: socket.socket, addr):
    """Lida com uma conexão de entrada de um peer."""
    try:
        with conn:
            conn.settimeout(None)
            while True:
                try:
                    message = conn.recv(4096)
                except ConnectionResetError:
                    logger.warning(f"Conexão resetada por {addr}")
                    break
                except Exception as e:
                    logger.error(f"Erro ao receber dados de {addr}: {e}")
                    break

                if not message:
                    logger.info(f"Conexão de {addr} encerrada pelo peer.")
                    break

                # tenta decodificar JSON
                try:
                    data = json.loads(message.decode('utf-8'))
                except Exception as e:
                    logger.warning(f"Recebido dado não-JSON de {addr}: {e} - raw={message}")
                    continue

                # HEARTBEAT de outro servidor
                if data.get("TASK") == "HEARTBEAT":
                    peer_id = data.get("SERVER_ID")
                    logger.info(f"[SERVER] Recebido HEARTBEAT de {peer_id} ({addr}): {json.dumps(data)}")
                    if peer_id:
                        with status_lock:
                            peer_status[peer_id] = {'last_alive': time.time()}
                    response = {"SERVER_ID": peer_id, "TASK": "HEARTBEAT", "RESPONSE": "ALIVE"}
                    logger.info(f"[SERVER] Respondendo HEARTBEAT para {peer_id} ({addr}): {json.dumps(response)}")
                    conn.sendall(json.dumps(response).encode('utf-8'))
                    continue

                # Apresentação do worker
                if data.get("WORKER") == "ALIVE":
                    worker_id = data.get("WORKER_ID")
                    logger.info(f"[SERVER] Worker apresentou-se: {worker_id} ({addr}) - {json.dumps(data)}")
                    with status_lock:
                        worker_status[worker_id] = {'addr': addr, 'last_seen': time.time()}

                    # ACK
                    ack = {"STATUS": "ACK", "MSG": "WELCOME"}
                    conn.sendall(json.dumps(ack).encode('utf-8'))
                    logger.info(f"[SERVER] Enviado ACK ao worker {worker_id}: {ack}")

                    # Envia tarefa de teste
                    task = {"TASK": "QUERY", "USER": "Carlos"}
                    logger.info(f"[SERVER] Enviando tarefa de teste ao worker {worker_id}: {task}")
                    conn.sendall(json.dumps(task).encode('utf-8'))
                    continue

                # Resultado de tarefa enviado pelo worker
                if data.get("STATUS"):
                    logger.info(f"[SERVER] Resultado recebido de {addr}: {data}")
                    # Aqui você poderia enfileirar resultados, atualizar estado, etc.
                    continue

                # Caso desconhecido
                logger.warning(f"[SERVER] Mensagem desconhecida de {addr}: {data}")
    except Exception as e:
        logger.error(f"Erro ao lidar com conexão de {addr}: {e}")

def server_listen_loop():
    """Loop principal que escuta por novas conexões."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((MY_IP, MY_PORT))
        server_socket.listen()
        logger.info(f"Servidor TCP iniciado em {MY_IP}:{MY_PORT} (ID: {MY_ID})")
        while True:
            conn, addr = server_socket.accept()
            handler_thread = threading.Thread(target=handle_connection, args=(conn, addr))
            handler_thread.start()
