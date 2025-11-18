# dist_server/background_tasks.py
import time
import threading
from random import choice
from logs.logger import logger
from payload_models import new_task_payload

class BackgroundTasksMixin:

    def _internal_producer_loop(self):
        """Simula a criação de novas tarefas."""
        while self._running:
            # Ajuste o tempo como desejar
            for _ in range(5): 
                if not self._running: return
                time.sleep(1)

            logger.info("[PRODUCER] Gerando 2 novas tarefas...")
            try:
                with self.lock:
                    for _ in range(2):
                        user = choice(self.lista_users)
                        task_payload = new_task_payload(user=user, task_type="QUERY")
                        self.task_queue.append(task_payload)

                    logger.success(f"[PRODUCER] 2 tarefas adicionadas. Fila agora com {len(self.task_queue)} tarefas.")
            except Exception as e:
                logger.error(f"[PRODUCER] Erro ao gerar tarefas: {e}")


    def _heartbeat_loop(self):
        """Loop que envia heartbeats periodicamente (agora é um método)."""
        interval = self.config['timing']['heartbeat_interval']
        while self._running:
            peers_to_check = []
            with self.lock:
                peers_to_check = list(self.active_peers) # Usa a lista dinâmica

            if not peers_to_check:
                 logger.info("[HB] Nenhuma peer ativo para verificar.")

            for peer in peers_to_check:
                if not self._running: break # Permite parada rápida
                success = self._send_heartbeat(peer) # Chama o método da classe
                
                if not success:
                    logger.warning(f"[HB] Peer: {peer['id']} inativo, aguardando próxima tentativa de conexão.")
                    # with self.lock:
                    #     if peer in self.active_peers:
                    #         self.active_peers.remove(peer)
                    #     if peer['id'] in self.peer_status:
                    #         del self.peer_status[peer['id']]
            
            # Dorme pelo intervalo, mas checa self._running em intervalos menores
            for _ in range(interval):
                if not self._running: break
                time.sleep(1)


    def _monitor_loop(self):
        """Verifica timeouts de peers periodicamente (agora é um método)."""
        interval = self.config['timing']['heartbeat_interval'] 
        timeout = self.config['timing']['heartbeat_timeout']
        while self._running:
             # Dorme primeiro
            for _ in range(interval):
                if not self._running: break
                time.sleep(1)
            if not self._running: break

            now = time.time()
            peers_to_remove_id = []
            with self.lock:
                for peer_id, info in self.peer_status.items():
                    if (now - info['last_alive']) > timeout:
                        logger.warning(f"[Monitor] Peer {peer_id} está INATIVO (timeout).")
                        peers_to_remove_id.append(peer_id)
                
                # Remove fora do loop de iteração
                for peer_id in peers_to_remove_id:
                    del self.peer_status[peer_id]
                    peer_to_remove = None
                    for peer in self.active_peers:
                        if peer['id'] == peer_id:
                            peer_to_remove = peer
                            break
                    if peer_to_remove:
                        self.active_peers.remove(peer_to_remove)
                        logger.info(f"[Monitor] Peer {peer_id} removido da lista ativa.")


    def _load_balancer_loop(self):
        """Verifica carga e pede/devolve workers."""

        interval = self.config['timing']['load_balancer_interval']
        config_lb = self.config['load_balancing']

        min_queue_size = config_lb.get('min_queue_threshold', 10)
        max_queue_size = config_lb.get('max_queue_threshold', 100)
        min_workers = config_lb.get('min_workers_before_sharing', 2)

        while self._running:
            # Dorme primeiro
            for _ in range(interval):
                if not self._running: break
                time.sleep(1)

            if not self._running: break

            try:
                # --- A MÉTRICA PRINCIPAL ---
                current_queue_size = 0
                with self.lock:
                    current_queue_size = len(self.task_queue)

                logger.info(f"[LOAD] Tamanho atual da fila: {current_queue_size}")

              
                # CASO 1: Fila MUITO CHEIA -> PEDIR WORKERS
                if current_queue_size > max_queue_size:
                    logger.warning(f"[LOAD] Fila ALTA ({current_queue_size} > {max_queue_size}), solicitando workers.")

                    active_peers_snapshot = []
                    with self.lock:
                        active_peers_snapshot = list(self.active_peers)

                    if not active_peers_snapshot:
                        logger.error("[LOAD] Carga alta, mas nenhum peer ativo para solicitar workers.")
                        continue

                    for peer in active_peers_snapshot:
                        if not self._running: break # Permite parada rápida
                        # Chama o método da classe para pedir workers
                        self._ask_peer_for_workers(peer)
                
                # CASO 2: Fila MUITO VAZIA -> DEVOLVER WORKERS
                elif current_queue_size < min_queue_size:
                    logger.success(f"[LOAD] Fila VAZIA ({current_queue_size} < {min_queue_size}). Verificando workers para devolver.")

                    # 1. Agrupa workers "emprestados" por seu dono (pelo ID do dono)
                    workers_to_release_by_owner = {} # key: 'SERVER_2', value: [{'id': 'W_01'}]
                    
                    active_peers_snapshot = []
                    with self.lock:
                        active_peers_snapshot = list(self.active_peers)


                    with self.lock:
                        workers_to_release = 0
                        for wid, winfo in self.worker_status.items():
                            # Verifica se o worker é emprestado ('OWNER_UUID') e se já não foi notificado
                            if 'SERVER_UUID' in winfo and not winfo.get('release_notified', False):
                                
                                owner_id = winfo['SERVER_UUID'] # O string 'SERVER_2'
                                
                                if owner_id not in workers_to_release_by_owner:
                                    workers_to_release_by_owner[owner_id] = []
                                workers_to_release_by_owner[owner_id].append({'id': wid})

                                workers_to_release += 1

                                # Não deixa o server ficar menos que o mínimo de workers
                                if workers_to_release + 1 >= min_workers:
                                    break
                    
                    if not workers_to_release_by_owner:
                        logger.info("[LOAD] Carga baixa, mas não há workers possíveis para devolver.")
                        continue

                    # 2. Encontra o 'peer object' (que tem o ID) para cada dono
                    for owner_id, worker_list in workers_to_release_by_owner.items():
                        
                        target_peer = None
                        for peer in active_peers_snapshot:
                            if peer['id'] == owner_id:
                                target_peer = peer
                                break
                        
                        if target_peer:
                            
                            # Verifica se já existe uma thread rodando para este peer
                            with self.lock:
                                if owner_id in self.pending_release_attempts:
                                    logger.info(f"[LOAD] Tentativa de release para {owner_id} já está em andamento. Aguardando.")
                                    continue # Pula para o próximo peer

                                # Se não há thread, crie uma e registre no estado
                                logger.info(f"[LOAD] Disparando thread de release (com backoff) para {owner_id}.")
                                self.pending_release_attempts[owner_id] = time.time()
                            
                            # Cria e inicia a thread assíncrona
                            release_thread = threading.Thread(
                                target=self._handle_release_with_backoff,
                                args=(target_peer, worker_list), # Passa o peer e a lista de workers
                                daemon=True
                            )
                            release_thread.start()

                        else:
                            logger.warning(f"[LOAD] Queria devolver workers para {owner_id}, mas ele não está na lista de peers ativos.")

                # CASO 3: Carga normal
                else:
                    logger.info(f"[LOAD] Fila estável ({min_queue_size} <= {current_queue_size} <= {max_queue_size}). Nenhuma ação.")
                    
            except Exception as e:
                logger.error(f"[LOAD] Erro no loop: {e}", exc_info=True)


    def _handle_release_with_backoff(self, peer: dict, worker_list: list):
        """
        Esta função é executada em sua PRÓPRIA THREAD.
        Tenta enviar o COMMAND_RELEASE com backoff exponencial.
        """
        owner_id = peer['id']
        worker_ids_to_notify = [w['id'] for w in worker_list]
        
        attempt = 0
        max_retries = 5 
        base_delay = 5 # 5 segundos
        max_delay = 30
        
        while attempt < max_retries:
            logger.info(f"[RELEASE_HANDLER_{owner_id}] Tentativa {attempt + 1}/{max_retries} de enviar COMMAND_RELEASE.")
            
            # Chama sua função de client_actions, que já tem suas próprias retentativas
            # Se ela falhar após suas retentativas, 'success' será False
            success = self._send_command_release(peer, worker_ids_to_notify)
            
            if success:
                # SUCESSO!
                logger.success(f"[RELEASE_HANDLER_{owner_id}] Peer {owner_id} confirmou liberação. Agendando devolução...")
                
                # Agenda a devolução (lógica original do _load_balancer_loop)
                with self.lock:
                    for worker_info in worker_list:
                        wid = worker_info['id']
                        if wid in self.worker_status:
                            self.worker_status[wid]['release_notified'] = True
                            redirect_order = {
                                'worker_id': wid,
                                'target_server': {"ip": peer['ip'], "port": peer['port']}, # Passa o objeto 'peer'
                                'TASK': 'RETURN'
                            }
                            self.redirect_queue.append(redirect_order)
                            logger.info(f"Worker {wid} agendado para RETORNAR para {peer['id']}.")
                
                # Limpa o estado e encerra a thread
                with self.lock:
                    self.pending_release_attempts.pop(owner_id, None)
                return # Encerra a thread
            
            # FALHA! Prepara para a próxima tentativa com backoff
            attempt += 1
            if attempt < max_retries:
                # Backoff Exponencial: 5s, 10s, 20s, 40s...
                delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                logger.warning(f"[RELEASE_HANDLER_{owner_id}] Falha na tentativa. Aguardando {delay}s para a próxima.")
                time.sleep(delay)

        # Se o loop terminar (max_retries atingido)
        logger.error(f"[RELEASE_HANDLER_{owner_id}] Falha ao notificar peer após {max_retries} tentativas. Desistindo.")
        # Limpa o estado para que o _load_balancer_loop possa tentar de novo no futuro
        with self.lock:
            self.pending_release_attempts.pop(owner_id, None)