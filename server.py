import socket
import threading
import json
import time
from typing import Dict

# --- Configurações do Servidor ---
MY_IP = '127.0.0.1'
MY_PORT = 8765
MY_ID = f'SERVER_{MY_PORT}'

PEER_SERVERS = [
    {'ip': '127.0.0.1', 'port': 8766, 'id': f'SERVER_8766'},
]

HEARTBEAT_INTERVAL = 10  # segundos
HEARTBEAT_TIMEOUT = 25   # segundos

# Dicionário para armazenar o status dos peers (thread-safe)
peer_status: Dict[str, Dict] = {}
status_lock = threading.Lock() # Lock para proteger o acesso ao peer_status

# --- Funções do Cliente de Heartbeat ---
def send_heartbeat(peer):
    """Tenta enviar um heartbeat para um peer e processa a resposta."""
    try:
        with socket.create_connection((peer['ip'], peer['port']), timeout=5) as client_socket:
            # Envia a mensagem de heartbeat
            msg = {"SERVER_ID": peer['id'], "TASK": "HEARTBEAT"}
            print(f"[HEARTBEAT] Enviando para {peer['id']} ({peer['ip']}:{peer['port']}): {json.dumps(msg)}")
            client_socket.sendall(json.dumps(msg).encode('utf-8'))

            # Recebe a resposta
            response = client_socket.recv(1024)
            if not response:
                print(f"[HEARTBEAT] Sem resposta de {peer['id']} ({peer['ip']}:{peer['port']})")
                return # Conexão fechada sem resposta

            data = json.loads(response.decode('utf-8'))
            print(f"[HEARTBEAT] Resposta recebida de {peer['id']} ({peer['ip']}:{peer['port']}): {json.dumps(data)}")

            if data.get("RESPONSE") == "ALIVE":
                with status_lock:
                    peer_status[peer['id']] = {'last_alive': time.time()}

    except (socket.timeout, ConnectionRefusedError):
        print(f"[HEARTBEAT] Falha ao conectar com {peer['id']} ({peer['ip']}:{peer['port']}) - offline ou recusado.")
        with status_lock:
            if peer['id'] in peer_status:
                del peer_status[peer['id']]
    except Exception as e:
        print(f"Erro inesperado em send_heartbeat para {peer['id']}: {e}")

def heartbeat_loop():
    """Loop que envia heartbeats para todos os peers periodicamente."""
    while True:
        for peer in PEER_SERVERS:
            # Não é necessário checar se é o próprio servidor, pois ele não está na lista
            send_heartbeat(peer)
        time.sleep(HEARTBEAT_INTERVAL)

# --- Funções do Servidor Principal ---
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

                # Envia a resposta 'ALIVE'
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
            # Cria uma nova thread para cada conexão, para não bloquear o servidor
            handler_thread = threading.Thread(target=handle_connection, args=(conn, addr))
            handler_thread.start()

# --- Monitoramento de Timeout ---
def timeout_monitor():
    """Verifica periodicamente se algum peer ficou inativo."""
    while True:
        time.sleep(HEARTBEAT_INTERVAL)
        now = time.time()
        
        with status_lock:
            # Itera sobre uma cópia para poder modificar o dicionário
            for peer_id, info in list(peer_status.items()):
                if (now - info['last_alive']) > HEARTBEAT_TIMEOUT:
                    print(f"!!! Peer {peer_id} está INATIVO (timeout) !!!")
                    del peer_status[peer_id]

# --- Início do Programa ---
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