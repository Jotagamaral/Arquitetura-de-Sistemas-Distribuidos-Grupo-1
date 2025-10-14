import socket
import threading
import json
import time
from .config import MY_IP, MY_PORT, MY_ID, lista_peers, IDLE_WORKER_THRESHOLD
from .state import peer_status, status_lock, worker_status, redirect_queue, record_task_completion
from .logger import logger
from random import randint

def handle_connection(conn: socket.socket, addr):
    """
    Lida com uma conexão de entrada, que pode ser de um peer ou de um worker.
    Esta função agora mantém o contexto de com quem está falando.
    """
    # Variáveis para manter o contexto desta conexão específica
    connection_type = "UNKNOWN"
    entity_id = None

    try:
        with conn:
            conn.settimeout(None)
            while True:
                message = conn.recv(4096)

                if not message:
                    logger.info(f"Conexão de {addr} encerrada.")
                    break

                try:
                    data = json.loads(message.decode('utf-8'))

                except json.JSONDecodeError:
                    logger.warning(f"Recebido dado não-JSON de {addr}: {message[:100]}...")
                    continue

                task = data.get("TASK")

                # --- LÓGICA DE IDENTIFICAÇÃO (PRIMEIRA MENSAGEM) ---
                if connection_type == "UNKNOWN":
                    if task == "HEARTBEAT" and "SERVER_ID" in data:
                        connection_type = "SERVER"
                        entity_id = data.get("SERVER_ID")
                        logger.info(f"Conexão de {addr} identificada como SERVER: {entity_id}")
                    elif "WORKER" in data and "WORKER_ID" in data:
                        connection_type = "WORKER"
                        entity_id = data.get("WORKER_ID")
                        logger.info(f"Conexão de {addr} identificada como WORKER: {entity_id}")
                    elif task == "WORKER_REQUEST" and "MASTER" in data:
                        connection_type = "SERVER_REQUEST"
                        entity_id = data.get("MASTER")
                        logger.info(f"Conexão de {addr} identificada como WORKER_REQUEST do SERVER: {entity_id}")
                    else:
                        logger.warning(f"Primeira mensagem de {addr} não identificada: {data}")
                        break

                # --- PROCESSAMENTO DE MENSAGENS ---

                # # Se a conexão é de um WORKER
                # if connection_type == "WORKER":
                #     # 1. Verifica se há uma ordem de redirecionamento para este worker
                #     order_to_remove = None
                #     with status_lock:

                #         for order in redirect_queue:

                #             if order['worker_id'] == entity_id:

                #                 target_server = order['target_server']
                #                 redirect_msg = {"MASTER": MY_ID, "TASK": "REDIRECT", "MASTER_REDIRECT": [target_server['ip'], target_server['port']]}

                #                 logger.warning(f"[LOAD] Ordenando worker {entity_id} a redirecionar para {target_server}")
                #                 conn.sendall(json.dumps(redirect_msg).encode('utf-8'))
                #                 order_to_remove = order

                #                 break # Worker será desconectado, encerra o loop
                    
                #     if order_to_remove:
                #         with status_lock:
                #             redirect_queue.remove(order_to_remove)
                #         break # Sai do loop while para fechar a conexão

                #     # 2. Se não houver redirect, processa a mensagem normalmente
                #     if data.get("WORKER") == "ALIVE":
                #         with status_lock:
                #             worker_status[entity_id] = {'addr': addr, 'last_seen': time.time(), 'conn': conn}
                        
                #         lista_users = ['Arthur', 'Carlos', 'Michel', 'Maria', 'Fernanda', 'Joao']
                #         task_msg = {"TASK": "QUERY", "USER": lista_users[randint(0, 5)]}
                        
                #         logger.info(f"[SERVER] Enviando tarefa para worker {entity_id}: {task_msg}")
                #         conn.sendall(json.dumps(task_msg).encode('utf-8'))
                    
                #     elif data.get("STATUS"):
                #         logger.info(f"[SERVER] Resultado recebido de {entity_id}: {data}")
                #         record_task_completion()
                #         with status_lock: # Atualiza o 'last_seen' do worker
                #             if entity_id in worker_status:
                #                 worker_status[entity_id]['last_seen'] = time.time()

                # --- NOVO TRECHO DA LÓGICA DO WORKER ---
                if connection_type == "WORKER":
                    # Se for a primeira apresentação, registra o worker e envia a primeira tarefa
                    if data.get("WORKER") == "ALIVE":
                        with status_lock:
                            worker_status[entity_id] = {'addr': addr, 'last_seen': time.time(), 'conn': conn}
                        
                        lista_users = ['Arthur', 'Carlos', 'Michel', 'Maria', 'Fernanda', 'Joao']
                        task_msg = {"TASK": "QUERY", "USER": lista_users[randint(0, 5)]}
                        logger.info(f"[SERVER] Enviando primeira tarefa para worker {entity_id}: {task_msg}")
                        conn.sendall(json.dumps(task_msg).encode('utf-8'))

                    # Se for o resultado de uma tarefa anterior, envia a próxima tarefa
                    elif data.get("STATUS"):
                        logger.info(f"[SERVER] Resultado recebido de {entity_id}: {data}")
                        record_task_completion()
                        with status_lock: # Atualiza o 'last_seen' do worker
                            if entity_id in worker_status:
                                worker_status[entity_id]['last_seen'] = time.time()
                        
                        # --- Lógica de Redirect ---
                        # Verifica se há uma ordem de redirecionamento ANTES de enviar a próxima tarefa
                        order_to_remove = None
                        with status_lock:
                            for order in redirect_queue:
                                if order['worker_id'] == entity_id:
                                    target_server = order['target_server']
                                    redirect_msg = {"TASK": "REDIRECT", "MASTER_REDIRECT": [target_server['ip'], target_server['port']]}
                                    logger.warning(f"[LOAD] Ordenando worker {entity_id} a redirecionar para {target_server}")
                                    conn.sendall(json.dumps(redirect_msg).encode('utf-8'))
                                    order_to_remove = order
                                    break
                        
                        if order_to_remove:
                            with status_lock:
                                redirect_queue.remove(order_to_remove)
                            break # Encerra a conexão

                        # Se não há redirect, envia a próxima tarefa
                        lista_users = ['Arthur', 'Carlos', 'Michel', 'Maria', 'Fernanda', 'Joao']
                        next_task_msg = {"TASK": "QUERY", "USER": lista_users[randint(0, 5)]}
                        logger.info(f"[SERVER] Enviando próxima tarefa para worker {entity_id}: {next_task_msg}")
                        conn.sendall(json.dumps(next_task_msg).encode('utf-8'))
                    continue # Volta para o início do loop para esperar a próxima mensagem

                # Se a conexão é um pedido de workers de outro SERVER
                elif connection_type == "SERVER_REQUEST" and task == "WORKER_REQUEST":
                    master_id = data.get("MASTER")
                    idle_candidates = []
                    now = time.time()

                    # Variáveis para armazenar os dados do servidor que pediu ajuda
                    ip_server_needed = None
                    port_server_needed = None

                    # Procura o peer na lista para encontrar seu IP e Porta
                    for peer in lista_peers:
                        if peer['id'] == master_id:
                            ip_server_needed = peer['ip']
                            port_server_needed = peer['port']
                            break

                    with status_lock:
                        for wid, winfo in worker_status.items():
                            if True: #(now - winfo.get('last_seen', 0)) >= IDLE_WORKER_THRESHOLD:
                                idle_candidates.append({'id': wid})
                    
                    if idle_candidates:
                        worker_to_move = idle_candidates[0] # Pega o primeiro
                        # Adiciona a ordem à fila de redirecionamento
                        redirect_order = {'worker_id': worker_to_move['id'], 'target_server': {'ip': ip_server_needed, 'port': port_server_needed}}
                        
                        with status_lock:
                            redirect_queue.append(redirect_order)

                        logger.success(f"[LOAD] Worker {worker_to_move['id']} agendado para redirecionar para {master_id}")
                        response = {"MASTER": MY_ID, "RESPONSE": "AVAILABLE", "WORKERS": idle_candidates}
                    else:
                        response = {"MASTER": MY_ID, "RESPONSE": "UNAVAILABLE"}

                    conn.sendall(json.dumps(response).encode('utf-8'))
                    break # Encerra a conexão após responder

                # Se a conexão é um heartbeat de outro SERVER
                elif connection_type == "SERVER" and task == "HEARTBEAT":
                    with status_lock:
                        peer_status[entity_id] = {'last_alive': time.time()}
                    response = {"SERVER_ID": entity_id, "TASK": "HEARTBEAT", "RESPONSE": "ALIVE"}
                    conn.sendall(json.dumps(response).encode('utf-8'))
                    break # Encerra a conexão após responder

    except (ConnectionResetError, BrokenPipeError):
        logger.warning(f"Conexão com {addr} ({entity_id}) perdida abruptamente.")
    except Exception as e:
        logger.error(f"Erro na conexão com {addr} ({entity_id}): {e}")
    finally:
        # Limpeza: remove o worker do status quando a conexão é encerrada
        if connection_type == "WORKER" and entity_id:
            with status_lock:
                if entity_id in worker_status:
                    del worker_status[entity_id]
                    logger.info(f"[SERVER] Worker {entity_id} desconectado e removido do status.")

def server_listen_loop():
    # Esta função continua a mesma
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((MY_IP, MY_PORT))
        server_socket.listen()
        logger.success(f"Servidor TCP iniciado em {MY_IP}:{MY_PORT} (ID: {MY_ID})")
        while True:
            conn, addr = server_socket.accept()
            handler_thread = threading.Thread(target=handle_connection, args=(conn, addr))
            handler_thread.start()