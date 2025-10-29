# dist_server/background_tasks.py
import time
from logs.logger import logger

class BackgroundTasksMixin:

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
                    logger.warning(f"[HB] Removendo peer inativo {peer['id']} da lista ativa.")
                    with self.lock:
                        if peer in self.active_peers:
                            self.active_peers.remove(peer)
                        if peer['id'] in self.peer_status:
                            del self.peer_status[peer['id']]
            
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
        """Verifica carga e pede workers (agora é um método)."""

        interval = self.config['timing']['load_balancer_interval']
        config_lb = self.config['load_balancing']
        min_tasks = config_lb['threshold_min_tasks']
        return_tasks = config_lb.get('threshold_return_tasks', min_tasks + 5)
        window = config_lb['threshold_window']

        while self._running:
             # Dorme primeiro
            for _ in range(interval):
                if not self._running: break
                time.sleep(1)

            if not self._running: break

            try:
                count = self._tasks_completed_in_window(window) # Chama método helper
                logger.info(f"[LOAD] Tarefas completadas nos últimos {window}s: {count}")

                if count < min_tasks:
                    logger.warning(f"[LOAD] Abaixo do threshold ({count} < {min_tasks}), solicitando workers.")
                    active_peers_snapshot = []
                    with self.lock:
                        active_peers_snapshot = list(self.active_peers)

                    if not active_peers_snapshot:
                        logger.error("[LOAD] Nenhum peer ativo para solicitar workers.")
                        continue

                    for peer in active_peers_snapshot:
                         if not self._running: break # Permite parada rápida
                         # Chama o método da classe para pedir workers
                         self._ask_peer_for_workers(peer)
                
                # CASO 2: Carga ALTA (Acima de 'Return') -> DEVOLVER (NOTIFICAR E AGENDAR)
                elif count > return_tasks:
                    logger.success(f"[LOAD] Carga alta ({count} > {return_tasks}). Verificando workers para devolver.")
                    
                    # 1. Agrupa workers "emprestados" por seu dono (pelo ID do dono)
                    #    Precisamos guardar o ID do dono E o dict do home_master
                    workers_to_release_by_owner = {} # key: 'SERVER_2', value: [{'id': 'W_01', 'home_master': {...}}]
                    
                    active_peers_snapshot = []
                    with self.lock:
                        active_peers_snapshot = list(self.active_peers)

                    with self.lock:
                        for wid, winfo in self.worker_status.items():
                            # ---- CORREÇÃO IMPORTANTE ----
                            # Você precisa do 'home_master' (o dict) e do 'home_master_id' (o ID do server)
                            # Assumindo que você salva 'home_master_id' no _handle_connection
                            if 'OWNER_ID' in winfo and not winfo.get('release_notified', False):
                                
                                owner_id = winfo['OWNER_ID']   # O string 'SERVER_2'
                                # ---- FIM DA CORREÇÃO ----
                                
                                if owner_id not in workers_to_release_by_owner:
                                    workers_to_release_by_owner[owner_id] = []
                                workers_to_release_by_owner[owner_id].append({'id': wid})
                    
                    if not workers_to_release_by_owner:
                        logger.info("[LOAD] Carga alta, mas não há workers (cujo dono está ativo) para notificar.")
                        continue

                    # 2. Encontra o 'peer object' (que tem o ID) para cada dono
                    for owner_id, worker_list in workers_to_release_by_owner.items():
                        
                        target_peer = None
                        for peer in active_peers_snapshot:
                            if peer['id'] == owner_id:
                                target_peer = peer
                                break
                        
                        if target_peer:
                            # 3. Envia a notificação
                            worker_ids_to_notify = [w['id'] for w in worker_list]
                            success = self._send_command_release(target_peer, worker_ids_to_notify)
                            
                            # 4. AÇÃO PÓS-CONFIRMAÇÃO (O que você pediu)
                            if success:
                                logger.success(f"[LOAD] Peer {target_peer['id']} confirmou liberação. Agendando devolução...")
                                
                                # 5. Adiciona workers à fila de redirect
                                with self.lock:
                                    for worker_info in worker_list:
                                        wid = worker_info['id']
                                        
                                        if wid in self.worker_status: # Checa de novo (pode ter caído)
                                            # 5a. Marca como notificado
                                            self.worker_status[wid]['release_notified'] = True
                                            
                                            # 5b. AGENDA A DEVOLUÇÃO
                                            redirect_order = {
                                                'worker_id': wid,
                                                'target_server': target_peer['id'],
                                                'TASK': 'RETURN' # Novo tipo de redirect
                                            }
                                            self.redirect_queue.append(redirect_order)
                                            logger.info(f"Worker {wid} agendado para RETORNAR para {target_peer['id']}.")
                        else:
                            logger.warning(f"[LOAD] Queria notificar {owner_id}, mas ele não está na lista de peers ativos.")

                # CASO 3: Carga normal
                else:
                    logger.info(f"[LOAD] Carga estável ({min_tasks} <= {count} <= {return_tasks}). Nenhuma ação.")

            except Exception as e:
                logger.error(f"[LOAD] Erro no loop: {e}", exc_info=True)