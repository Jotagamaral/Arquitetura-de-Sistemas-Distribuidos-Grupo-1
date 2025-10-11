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
from collections import deque
from typing import Dict, Any


def receive_full_message(sock: socket.socket, buffer: bytearray) -> tuple[dict | None, bytearray]:
    """
    Lê o socket até encontrar o delimitador '\n' e retorna o objeto JSON.
    Retorna a mensagem e o buffer atualizado.
    """
    
    # Tenta ler mais dados se necessário
    while b'\n' not in buffer:
        try:
            # Buffer de leitura deve ser grande o suficiente, mas não excessivo
            chunk = sock.recv(4096)
            if not chunk:
                return None, buffer
            buffer.extend(chunk)
        except socket.timeout:
            return None, buffer 
        except Exception as e:
            # Erro de leitura, encerra a conexão para esta thread
            logger.error(f"Erro ao receber dados: {e}")
            return None, bytearray()

    # Processa o buffer: divide na primeira ocorrência de \n
    parts = buffer.split(b'\n', 1)
    message_part = parts[0]
    buffer = bytearray(parts[1]) if len(parts) > 1 else bytearray()
    
    # Tenta decodificar e deserializar JSON
    try:
        # Tira espaços em branco/caracteres invisíveis
        data = json.loads(message_part.decode('utf-8').strip())
        return data, buffer
    except json.JSONDecodeError as e:
        logger.warning(f"JSON inválido recebido: {e} - Raw: {message_part.decode()}")
        # Descarta a parte inválida e continua com o restante do buffer
        return None, buffer
    except Exception as e:
        logger.error(f"Erro inesperado ao decodificar mensagem: {e}")
        return None, bytearray()

def send_message(sock: socket.socket, message: dict):
    """Envia uma mensagem JSON terminada em \n."""
    try:
        json_message = json.dumps(message) + '\n'
        sock.sendall(json_message.encode('utf-8'))
    except Exception as e:
        logger.error(f"Falha ao enviar mensagem: {e}")
        raise

def handle_connection(conn: socket.socket, addr):
    """Lida com uma conexão de entrada de um peer/worker."""
    # Buffer local para armazenar dados incompletos da conexão atual
    conn_buffer = bytearray()
    
    try:
        with conn:
            # Define timeout baixo para evitar bloqueio infinito ao usar `recv`
            conn.settimeout(1.0) 
            
            while True:
                data, conn_buffer = receive_full_message(conn, conn_buffer)

                if data is None:
                    # Se receive_full_message retorna None, a conexão foi encerrada ou houve um erro grave.
                    if not conn_buffer:
                        logger.info(f"Conexão de {addr} encerrada ou erro de leitura.")
                        break
                    else:
                        # Se for None, mas houver buffer, significa timeout. Apenas continua.
                        continue


                # -------------------------
                # 1. HEARTBEAT de outro Master
                # -------------------------
                if data.get("TASK") == "HEARTBEAT":
                    peer_id = data.get("SERVER_ID")
                    logger.info(f"[SERVER] Recebido HEARTBEAT de {peer_id} ({addr})")
                    if peer_id:
                        with status_lock:
                            peer_status[peer_id] = {'last_alive': time.time()} # Atualiza o status
                    
                    response = {"SERVER_ID": MY_ID, "TASK": "HEARTBEAT", "RESPONSE": "ALIVE"}
                    send_message(conn, response)
                    continue

                # -------------------------
                # 2. Apresentação do Worker (WORKER:ALIVE)
                # -------------------------
                if data.get("WORKER") == "ALIVE":
                    worker_id = data.get("WORKER_ID")
                    logger.info(f"[SERVER] Worker apresentou-se: {worker_id} ({addr})")
                    
                    # Logica para descobrir o Master original (por enquanto None/Local)
                    master_origin = data.get("ORIGINAL_MASTER_ID", None) 
                    
                    with status_lock:
                        worker_status[worker_id] = {
                            'addr': addr, 
                            'last_seen': time.time(),
                            'original_master': master_origin # Necessário para devolver o worker
                        }

                    # Resposta ACK
                    ack = {"STATUS": "ACK", "MSG": "WELCOME", "MASTER_ID": MY_ID}
                    send_message(conn, ack)
                    logger.info(f"[SERVER] Enviado ACK ao worker {worker_id}")
                    
                    # TODO: A distribuição de tarefas será feita por outro módulo
                    # mas para manter a funcionalidade de teste, enviamos uma tarefa:
                    if worker_id == 'WORKER_CARLOS_01':
                         task = {"TASK": "QUERY", "USER": "Carlos", "TASK_ID": time.time()}
                         send_message(conn, task)
                         logger.info(f"[SERVER] Enviando tarefa de teste ao worker {worker_id}")
                    
                    continue

                # -------------------------
                # 3. Resultado de Tarefa Enviado pelo Worker
                # -------------------------
                if data.get("STATUS") in ["OK", "NOK"]:
                    task_id = data.get("TASK_ID", "N/A")
                    worker_id = data.get("WORKER_ID")
                    logger.info(f"[SERVER] Resultado da Tarefa {task_id} recebido de {worker_id}: {data}")
                    # TODO: Aqui se faria o 'despacho' do resultado ao cliente original.
                    continue

                # -------------------------
                # 4. Mensagem Desconhecida
                # -------------------------
                logger.warning(f"[SERVER] Mensagem desconhecida de {addr}: {data}")

    except Exception as e:
        logger.error(f"Erro ao lidar com conexão de {addr}: {e}")

def server_listen_loop():
    """Loop principal que escuta por novas conexões."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Tenta bindear até ter sucesso (útil para reinício rápido)
        while True:
            try:
                server_socket.bind((MY_IP, MY_PORT))
                break
            except Exception as e:
                logger.error(f"Falha ao bindar em {MY_IP}:{MY_PORT}. Tentando novamente em 5s. Erro: {e}")
                time.sleep(5)
                
        server_socket.listen()
        logger.info(f"Servidor TCP iniciado em {MY_IP}:{MY_PORT} (ID: {MY_ID})")
        
        while True:
            try:
                conn, addr = server_socket.accept()
                handler_thread = threading.Thread(target=handle_connection, args=(conn, addr))
                handler_thread.start()
            except Exception as e:
                logger.critical(f"Erro fatal no accept do servidor: {e}")
                time.sleep(1) # Evita loop de erro rápido