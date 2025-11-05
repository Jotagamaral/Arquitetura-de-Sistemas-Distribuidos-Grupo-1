# dist_server/connection_handler.py
import socket
import threading
import json
import time
from random import randint
from ..logs.logger import logger
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

                            # --- COMUNICAÇÃO COM WORKER ---

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
                                
                                # --- NOVA LÓGICA DE REGISTRO DE DONO ---
                                if "OWNER_UUID" in data:
                                    owner_id = data["OWNER_UUID"]
                                    logger.warning(f"Worker {entity_id} é 'EMPRESTADO'. Dono: {owner_id}")
                                    with self.lock:
                                        # Salva a informação do dono no status do worker
                                        self.worker_status[entity_id]['OWNER_UUID'] = owner_id
                                # --- FIM DA NOVA LÓGICA ---

                            # --- COMUNICAÇÃO COM SERVIDOR ---

                            elif task == "HEARTBEAT" and "SERVER_ID" in data:

                                connection_type = "SERVER"
                                entity_id = data.get("SERVER_ID")

                                logger.info(f"Conexão identificada como SERVER: {entity_id}")

                            elif task == "WORKER_REQUEST" and "MASTER" in data:
                                connection_type = "SERVER_REQUEST"
                                entity_id = data.get("MASTER")
                                logger.info(f"Conexão identificada como WORKER_REQUEST do SERVER: {entity_id}")
                                
                            elif task == "COMMAND_RELEASE" and "MASTER" in data:
                                connection_type = "SERVER_RELEASE"
                                entity_id = data.get("MASTER")
                                logger.info(f"Conexão identificada como COMMAND_RELEASE do SERVER: {entity_id}")
                                
                                # Processa a liberação e responde imediatamente
                                workers_list = data.get("WORKERS", [])
                                logger.success(f"Recebida notificação de {entity_id} para liberar {len(workers_list)} workers: {workers_list}")
                                
                                # (Aqui você adicionará sua lógica para lidar com
                                # a devolução quando ela for implementada)
                                
                                # Constrói o payload 5.2 (Confirmação)
                                response = server_release_ack(master_id=self.id, workers_list=workers_list)
                                conn.sendall((json.dumps(response) + '\n').encode('utf-8'))
                                break # Encerra a conexão
                            
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
                                # O 'entity_id' já foi pego na identificação da conexão
                                
                                # ATUALIZA O "ALIVE" DO WORKER
                                with self.lock:
                                    if entity_id in self.worker_status:
                                        self.worker_status[entity_id]['last_seen'] = time.time()
                                    # (Seu código original de registro do worker já fez isso na 1ª msg)

                                # --- PASSO 1: LÓGICA DE FEDERAÇÃO (Obrigatória, do seu projeto) ---
                                # O worker está pedindo uma tarefa, MAS ele está na fila de redirect?
                                
                                redirect_msg = None
                                with self.lock:
                                    for order in self.redirect_queue:
                                        if order['worker_id'] == entity_id:
                                            target_server = order['target_server']
                                            task_type = order.get('TASK', 'REDIRECT')
                                            
                                            if task_type == 'RETURN':
                                                redirect_msg = server_order_return(master_id=self.id, return_target_server=target_server)
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
                            master_id = data.get("MASTER")
                            requestor_info = data.get("REQUESTOR_INFO")
                            
                            if not requestor_info:
                                logger.warning(f"Pedido de {master_id} sem 'REQUESTOR_INFO'. Ignorando.")
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
                                logger.info(f"[REQUEST] Pedido de {master_id} negado: contagem de workers ({current_worker_count}) abaixo do mínimo ({min_workers_to_keep}).")
                            elif current_task_count < min_tasks_threshold:
                                # Não compartilha se a carga JÁ ESTIVER baixa
                                # (Se a carga está baixa, nós mesmos precisamos dos workers!)
                                logger.info(f"[REQUEST] Pedido de {master_id} negado: carga atual ({current_task_count}) abaixo do threshold ({min_tasks_threshold}).")
                            else:
                                # Carga está saudável E temos workers suficientes para compartilhar.
                                logger.success(f"[REQUEST] Pedido de {master_id} APROVADO.")
                                can_share = True

                            # --- FIM DA NOVA LÓGICA ---

                            if can_share:
                                # Pega *qualquer* worker. Como todos estão ocupados,
                                # simplesmente pegar o primeiro da lista é suficiente.
                                worker_to_move_id = None
                                with self.lock:
                                    if self.worker_status: # Checagem extra de segurança
                                        worker_to_move_id = list(self.worker_status.keys())[0] 
                                
                                if worker_to_move_id:
                                    redirect_order = {'worker_id': worker_to_move_id, 'target_server': requestor_info}
                                    with self.lock:
                                        self.redirect_queue.append(redirect_order)
                                    logger.success(f"Worker {worker_to_move_id} agendado para redirect para {master_id}")
                                    response = server_response_available(master_id=self.id, worker_uuid_list=[worker_to_move_id])
                                else:
                                    # Caso raro: 'can_share' foi True, mas no exato momento
                                    # de pegar o worker, a lista estava vazia.
                                    logger.warning(f"[REQUEST] Pedido de {master_id} aprovado, mas sem workers para enviar.")
                                    response = server_response_unavailable(master_id=self.id, include_empty_list=True)
                            else:
                                # 'can_share' foi False
                                response = server_response_unavailable(master_id=self.id)
                            
                            conn.sendall((json.dumps(response) + '\n').encode('utf-8'))
                            break # Encerra conexão com requisitante

                        # Lógica de HEARTBEAT
                        elif connection_type == "SERVER" and task == "HEARTBEAT":
                            logger.info("Recebido solicitação de Heartbeat. Enviando Alive para:")
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