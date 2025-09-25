"""
server_lib/server_main.py
Funções relacionadas ao servidor principal (escuta e resposta de conexões).
"""

import socket
import threading
import json
import time
from .config import MY_IP, MY_PORT, MY_ID
from .state import peer_status, status_lock

def handle_connection(conn: socket.socket, addr):
    """Lida com uma conexão de entrada de um peer."""
    try:
        with conn:
            message = conn.recv(1024)
            if not message:
                print(f"Conexão de {addr} fechada sem dados.")
                return
            data = json.loads(message.decode('utf-8'))
            if data.get("TASK") == "HEARTBEAT":
                peer_id = data.get("SERVER_ID")
                print(f"[SERVER] Recebido HEARTBEAT de {peer_id} ({addr}): {json.dumps(data)}")
                if peer_id:
                    with status_lock:
                        peer_status[peer_id] = {'last_alive': time.time()}
                response = {
                    "SERVER_ID": peer_id,
                    "TASK": "HEARTBEAT",
                    "RESPONSE": "ALIVE"
                }
                print(f"[SERVER] Respondendo HEARTBEAT para {peer_id} ({addr}): {json.dumps(response)}")
                conn.sendall(json.dumps(response).encode('utf-8'))
    except Exception as e:
        print(f"Erro ao lidar com conexão de {addr}: {e}")

def server_listen_loop():
    """Loop principal que escuta por novas conexões."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((MY_IP, MY_PORT))
        server_socket.listen()
        print(f"Servidor TCP iniciado em {MY_IP}:{MY_PORT} (ID: {MY_ID})")
        while True:
            conn, addr = server_socket.accept()
            handler_thread = threading.Thread(target=handle_connection, args=(conn, addr))
            handler_thread.start()
