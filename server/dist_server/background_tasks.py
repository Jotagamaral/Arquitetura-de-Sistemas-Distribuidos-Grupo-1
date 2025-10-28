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
                
                # CASO 2: Carga CONFORTÁVEL (Abaixo de 'Return') -> DEVOLVER (NOTIFICAR)
                elif count > return_tasks:

                    logger.success(f"[LOAD] Carga confortável ({count} < {return_tasks}). Verificando workers para notificar devolução.")
                    
                    # --- NOVA LÓGICA DE NOTIFICAÇÃO ---
                    
                    # 1. Agrupa workers "emprestados" por seu dono (pelo IP/Porta)
                    workers_to_release_by_owner = {} # (ip, port) -> [worker_id, ...]
                    
                    with self.lock:
                        for wid, winfo in self.worker_status.items():
                            # Verifica se é emprestado E se ainda não foi notificado
                            if 'addr' in winfo and not winfo.get('release_notified', False):
                                hm_info = winfo['addr']
                                hm_id = winfo['OWNER_ID']
                                # Chave é o IP/Porta do dono
                                owner_key = (hm_info[0], hm_info[1], hm_id) 
                                
                                if owner_key not in workers_to_release_by_owner:
                                    workers_to_release_by_owner[owner_key] = []
                                workers_to_release_by_owner[owner_key].append(wid)
                    
                    if not workers_to_release_by_owner:
                        logger.info("[LOAD] Carga confortável, mas não há workers emprestados para notificar.")
                        continue # Pula para o próximo ciclo do loop

                    # 2. Encontra o 'peer object' (que tem o ID) para cada dono
                    active_peers_snapshot = []
                    with self.lock:
                        active_peers_snapshot = list(self.active_peers)

                    for owner_key, worker_ids in workers_to_release_by_owner.items():
                        owner_ip, owner_port, owner_id = owner_key
                        
                        target_peer = None
                        for peer in active_peers_snapshot:
                            if peer['id'] == owner_id:
                                target_peer = peer
                                break
                        
                        if target_peer:
                            # 3. Envia a notificação
                            # (Chama o novo método de client_actions.py)
                            success = self._send_command_release(target_peer, worker_ids)
                            
                            if success:
                                # 4. Marca os workers como 'notificados' para não
                                # enviar de novo no próximo ciclo
                                with self.lock:
                                    for wid in worker_ids:
                                        if wid in self.worker_status:
                                            self.worker_status[wid]['release_notified'] = True
                                            logger.info(f"Worker {wid} marcado como 'release_notified'.")
                        else:
                            logger.warning(f"[LOAD] Queria notificar {owner_ip}:{owner_port} sobre {worker_ids}, mas ele não está na lista de peers ativos.")

                else:
                    logger.success(f"[LOAD] Acima e próximo do threshold ({count} <= {min_tasks}) (mínimo de task limite: {return_tasks}), não necessita de mais workers.")

            except Exception as e:
                logger.error(f"[LOAD] Erro no loop: {e}")