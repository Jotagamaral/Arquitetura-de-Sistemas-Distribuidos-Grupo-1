# dist_server/connection_handler.py
import socket
import threading
import json
import time
from random import randint
from logs.logger import logger
from payload_models import server_no_task, server_ack, server_release_ack, server_order_return, server_order_redirect, server_response_available, server_response_unavailable, server_heartbeat_response

class ConnectionHandlerMixin:
    
    def _listen_loop(self):
        """Loop principal que escuta por novas conexões."""
        try:
            # self.host e self.port são definidos no __init__ da classe Server
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                self.server_socket = server_socket # Guardando para o shutdown limpo
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_socket.bind((self.host, self.port))
                server_socket.listen()
                logger.success(f"Servidor escutando em {self.host}:{self.port}")
                
                while self._running:
                    try:
                        server_socket.settimeout(1.0) 
                        conn, addr = server_socket.accept()
                        server_socket.settimeout(None) 
                        
                        handler_thread = threading.Thread(
                            target=self._handle_connection, args=(conn, addr), daemon=True
                        )
                        handler_thread.start()
                    except socket.timeout:
                        continue # Volta ao início do loop para checar self._running
                    except Exception as e:
                        if not self._running:
                            logger.info("Listener encerrando devido ao shutdown.")
                            break
                        logger.error(f"Erro no accept(): {e}")

        except Exception as e:
            if self._running:
                logger.critical(f"Erro fatal na thread Listener: {e}")
                self.stop() # Tenta parar o servidor se o listener falhar

    def _handle_connection(self, conn: socket.socket, addr):
        """Lida com uma conexão de entrada (agora é um método)."""

        connection_type = "UNKNOWN"
        entity_id = None
        order_to_remove = None

        # Adiciona contexto do cliente aos logs desta thread
        with logger.contextualize(client_addr=f"{addr[0]}:{addr[1]}"):
            try:
                with conn:
                    # Usa makefile para leitura baseada em linhas
                    reader = conn.makefile('r', encoding='utf-8')
                    while self._running:
                        line = reader.readline()
                        if not line:
                            logger.info(f"Conexão encerrada por {entity_id or 'peer desconhecido'}.")
                            break

                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            logger.warning(f"Recebido dado não-JSON: {line.strip()}")
                            continue

                        task = data.get("TASK")

                        # --- LÓGICA DE IDENTIFICAÇÃO (PRIMEIRA MENSAGEM) ---
                        if connection_type == "UNKNOWN":

                            # --- COMUNICAÇÃO DO WORKER ---

                            if ("WORKER" in data or "STATUS" in data) and "WORKER_UUID" in data:

                                connection_type = "WORKER"
                                entity_id = data.get("WORKER_UUID")

                                logger.info(f"Conexão identificada como WORKER: {entity_id}")

                                # Registra o worker (se for a primeira vez)
                                with self.lock:
                                    if entity_id not in self.worker_status:
                                        self.worker_status[entity_id] = {
                                            'addr': addr, 
                                            'last_seen': time.time()
                                        }
                                
                                # --- LÓGICA DE REGISTRO DE DONO ---
                                if "SERVER_UUID" in data:
                                    owner_id = data["SERVER_UUID"]
                                    logger.warning(f"Worker {entity_id} é 'EMPRESTADO'. Dono: {owner_id}")
                                    with self.lock:
                                        # Salva a informação do dono no status do worker
                                        self.worker_status[entity_id]['SERVER_UUID'] = owner_id

                            # --- COMUNICAÇÃO DO SERVIDOR ---

                            elif task == "HEARTBEAT" and "SERVER_UUID" in data:

                                connection_type = "SERVER"
                                server_uuid = data.get("SERVER_UUID")
                                entity_id = None

                                for peer in self.active_peers:
                                    if (peer['id'] == server_uuid) or (peer['ip'] == addr[0]):
                                        entity_id = peer['id']
                                        break

                                logger.info(f"Conexão identificada como SERVER: {entity_id}")

                            elif task == "WORKER_REQUEST":
                                connection_type = "SERVER_REQUEST"
                                server_ip, server_port = data.get("REQUESTOR_INFO")['ip'], data.get("REQUESTOR_INFO")['port']

                                # Achar o uuid do Server

                                entity_id = None

                                for peer in self.active_peers:
                                    if peer['ip'] == server_ip and peer['port'] == server_port:
                                        entity_id = peer['id']
                                        break

                                logger.info(f"Conexão identificada como WORKER_REQUEST do SERVER: {entity_id}")
                                
                            elif task == "COMMAND_RELEASE" and "SERVER_UUID" in data:
                                connection_type = "SERVER_RELEASE"
                                entity_id = data.get("SERVER_UUID")
                                logger.info(f"Conexão identificada como COMMAND_RELEASE do SERVER: {entity_id}")
                                
                                # Processa a liberação e responde imediatamente
                                workers_list = data.get("WORKERS_UUID", [])
                                logger.success(f"Recebida notificação de {entity_id} para liberar {len(workers_list)} workers: {workers_list}")
                                
                                target_peer = None
                                with self.lock: # Protege a leitura de self.active_peers
                                    for peer in self.active_peers:
                                        if peer['id'] == entity_id:
                                            target_peer = peer
                                            break
                                
                                if target_peer:
                                    # Registra o LOTE de workers que estamos esperando
                                    with self.lock:
                                        # Armazena o lote por server_id
                                        self.pending_returns[entity_id] = {
                                            'peer': target_peer,
                                            # Salva uma cópia para podermos modificar a 'pending'
                                            'workers_pending': list(workers_list), 
                                            # Salva a lista original para o payload final
                                            'workers_original': list(workers_list),
                                            'timestamp': time.time()
                                        }
                                    logger.info(f"Registrado lote de {len(workers_list)} workers 'em trânsito' de volta de {entity_id}.")
                                else:
                                    logger.error(f"Recebido COMMAND_RELEASE de {entity_id}, mas ele não está na lista de active_peers.")

                                # Constrói o payload 5.2 (Confirmação de notificação)
                                response = server_release_ack(master_id=self.id, workers_list=workers_list)
                                conn.sendall((json.dumps(response) + '\n').encode('utf-8'))

                                break # Encerra a conexão
                            
                            elif "RESPONSE" in data and data.get("RESPONSE") == "RELEASE_COMPLETED":
                                entity_id = data.get("SERVER_UUID")
                                logger.success(f"Recebida a confirmação de recebimento de workers pelo server: {entity_id}")

                            else:
                                logger.warning(f"Primeira mensagem não identificada: {data}")
                                break
                            
                        # --- PROCESSAMENTO ---
                        
                        # Lógica do Worker
                        if connection_type == "WORKER":
                            
                            # O Worker agora nos diz o que quer:
                            if "WORKER" in data:
                                task = data.get("WORKER")
                            
                            elif "STATUS" in data:
                                task = "STATUS" # Para entrar no if status
                            
                            else:
                                task= data.get("TASK")

                            # --- ROTA 1: Worker pede uma tarefa ---
                            if task == "ALIVE":

                                server_that_returned_id = None
                                batch_is_complete = False
                                peer_to_notify = None
                                original_worker_list = []

                                with self.lock:
                                    # Procura em qual lote pendente este worker está
                                    for server_id, return_info in self.pending_returns.items():
                                        if entity_id in return_info['workers_pending']:
                                            # Encontramos! O worker 'w1' pertence ao lote de 'SERVER_1'
                                            logger.success(f"[RETURN] Worker {entity_id} retornou com sucesso de {server_id}.")
                                            
                                            # Remove o worker da lista de pendentes
                                            return_info['workers_pending'].remove(entity_id)
                                            server_that_returned_id = server_id
                                            
                                            # Verifica se o lote está completo
                                            if not return_info['workers_pending']:
                                                batch_is_complete = True
                                                peer_to_notify = return_info['peer']
                                                original_worker_list = return_info['workers_original']
                                                
                                            break # Encontrou o worker, pode parar de procurar

                                # Se um lote foi completado, remova-o da lista e envie a notificação
                                if batch_is_complete and server_that_returned_id:
                                    logger.success(f"Lote completo! Todos os workers de {server_that_returned_id} retornaram.")
                                    
                                    # Remove o lote finalizado da estrutura
                                    with self.lock:
                                        self.pending_returns.pop(server_that_returned_id) 
                                    
                                    # Envia a notificação final em uma thread
                                    notify_thread = threading.Thread(
                                        target=self._send_release_completed,
                                        args=(peer_to_notify, original_worker_list),
                                        daemon=True
                                    )
                                    notify_thread.start()
                                
                                # ATUALIZA O "ALIVE" DO WORKER
                                with self.lock:
                                    if entity_id in self.worker_status:
                                        self.worker_status[entity_id]['last_seen'] = time.time()

                                # Verifica Redirect
                                redirect_msg = None

                                with self.lock:
                                    for order in self.redirect_queue:
                                        if order['worker_id'] == entity_id:
                                            target_server = order['target_server']
                                            task_type = order.get('TASK', 'REDIRECT')
                                            
                                            if task_type == 'RETURN':
                                                redirect_msg = server_order_return(return_target_server=target_server)
                                                logger.warning(f"Ordenando RETORNO para {entity_id} -> {target_server}")
                                            else: # REDIRECT normal
                                                redirect_msg = server_order_redirect(redirect_target_server=target_server)
                                                logger.warning(f"Ordenando REDIRECT (via GET_TASK) para {entity_id} -> {target_server['ip']}")

                                            order_to_remove = order
                                            break # Encontramos, saia do loop

                                if order_to_remove:
                                    # SIM, ele deve ser redirecionado. Envie a ordem e encerre.
                                    with self.lock:
                                        self.redirect_queue.remove(order_to_remove)
                                    conn.sendall((json.dumps(redirect_msg) + '\n').encode('utf-8'))
                                    break # Encerra a conexão com o worker

                                # --- PASSO 2: LÓGICA DE FILA (Normal, da v1) ---
                                # Se não há ordem de redirect, procure uma tarefa na fila.
                                task_to_send = None
                                with self.lock:
                                    if self.task_queue: # Se a fila NÃO estiver vazia
                                        task_to_send = self.task_queue.pop(0) # Pega a primeira
                                
                                if task_to_send:
                                    # Envia a tarefa da fila
                                    logger.info(f"Enviando tarefa para {entity_id}.")
                                    conn.sendall((json.dumps(task_to_send) + '\n').encode('utf-8'))
                                else:
                                    # Fila vazia, envie "NO_TASK"
                                    logger.info(f"Fila vazia. Nenhuma tarefa para {entity_id}.")
                                    conn.sendall((json.dumps(server_no_task()) + '\n').encode('utf-8'))
                                
                                break # Encerra conexão (modelo de conexão curta da v1)

                            # --- ROTA 2: Worker reporta um status ---
                            elif task == "STATUS":
                                status = data.get("STATUS")
                                
                                with self.lock:
                                    if entity_id in self.worker_status:
                                        self.worker_status[entity_id]['last_seen'] = time.time()
                                
                                if status == "OK":
                                    logger.success(f"Worker {entity_id} reportou {status} para a tarefa.")
                                    self._record_task_completion() # Seu helper original de state_helpers.py
                                
                                elif status == "NOK":
                                    logger.warning(f"Worker {entity_id} reportou {status} para a tarefa.")
                                    self._record_task_completion() # Seu helper original de state_helpers.py

                                # Confirma o recebimento
                                conn.sendall((json.dumps(server_ack()) + '\n').encode('utf-8'))
                                break # Encerra conexão

                        # Lógica de WORKER_REQUEST
                        elif connection_type == "SERVER_REQUEST" and task == "WORKER_REQUEST":
                            
                            requestor_info = data.get("REQUESTOR_INFO")
                            
                            if not requestor_info:
                                logger.warning(f"Pedido de {entity_id} sem 'REQUESTOR_INFO'. Ignorando.")
                                break # Encerra sem resposta

                            # --- NOVA LÓGICA DE DECISÃO DE COMPARTILHAMENTO ---
                            
                            # 1. Obter métricas de configuração
                            config_lb = self.config['load_balancing']
                            window = config_lb['threshold_window']
                            min_tasks_threshold = config_lb['threshold_min_tasks']
                            min_workers_to_keep = config_lb.get('min_workers_before_sharing', 2) # Padrão 2 se não estiver no config

                            # 2. Obter métricas de estado ATUAIS
                            #    (self._tasks_completed_in_window já lida com seu próprio lock)
                            current_task_count = self._tasks_completed_in_window(window)
                            
                            current_worker_count = 0
                            with self.lock: # Protege a leitura de self.worker_status
                                current_worker_count = len(self.worker_status)

                            # 3. Lógica de decisão
                            can_share = False
                            if current_worker_count <= min_workers_to_keep:
                                # Não compartilha se tiver menos que o mínimo de workers
                                logger.info(f"[REQUEST] Pedido de {entity_id} negado: contagem de workers ({current_worker_count}) abaixo do mínimo ({min_workers_to_keep}).")
                            elif current_task_count < min_tasks_threshold:
                                # Não compartilha se a carga JÁ ESTIVER baixa
                                # (Se a carga está baixa, nós mesmos precisamos dos workers!)
                                logger.info(f"[REQUEST] Pedido de {entity_id} negado: carga atual ({current_task_count}) abaixo do threshold ({min_tasks_threshold}).")
                            else:
                                # Carga está saudável E temos workers suficientes para compartilhar.
                                logger.success(f"[REQUEST] Pedido de {entity_id} APROVADO.")
                                can_share = True

                            # --- FIM DA NOVA LÓGICA ---

                            if can_share:
                                # Pega qualquer worker.
                                worker_to_move_id = None
                                with self.lock:
                                    if self.worker_status: # Checagem extra de segurança
                                        worker_to_move_id = list(self.worker_status.keys())[0] 
                                
                                if worker_to_move_id:
                                    redirect_order = {'worker_id': worker_to_move_id, 'target_server': requestor_info}
                                    with self.lock:
                                        self.redirect_queue.append(redirect_order)
                                    logger.success(f"Worker {worker_to_move_id} agendado para redirect para {entity_id}")
                                    response = server_response_available(master_id=self.id, worker_uuid_list=[worker_to_move_id])
                                else:
                                    # Caso raro: 'can_share' foi True, mas no exato momento
                                    # de pegar o worker, a lista estava vazia.
                                    logger.warning(f"[REQUEST] Pedido de {entity_id} aprovado, mas sem workers para enviar.")
                                    response = server_response_unavailable(master_id=self.id, include_empty_list=True)
                            else:
                                # 'can_share' foi False
                                response = server_response_unavailable(master_id=self.id)
                            
                            conn.sendall((json.dumps(response) + '\n').encode('utf-8'))
                            break # Encerra conexão com requisitante

                        # Lógica de HEARTBEAT
                        elif connection_type == "SERVER" and task == "HEARTBEAT":
                            logger.info("Recebido solicitação de Heartbeat. Enviando Alive")
                            with self.lock:
                                self.peer_status[entity_id] = {'last_alive': time.time()}
                            response = server_heartbeat_response(server_id=self.id)
                            conn.sendall((json.dumps(response) + '\n').encode('utf-8'))
                            break # Encerra conexão após responder


            except (ConnectionResetError, BrokenPipeError, EOFError):
                 logger.warning(f"Conexão perdida abruptamente.")
            except Exception as e:
                 logger.error(f"Erro inesperado na conexão: {e}")
            finally:
                # Limpeza final da conexão
                 if connection_type == "WORKER" and order_to_remove and entity_id:
                     with self.lock:
                         if entity_id in self.worker_status:
                             del self.worker_status[entity_id]
                             logger.info(f"Worker {entity_id} removido do status.")