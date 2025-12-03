# dist_server/background_tasks.py
import time
import psutil
import os
from datetime import datetime, timezone
import threading
from random import choice
from logs.logger import logger
from payload_models import new_task_payload, server_performance_report

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


    def _performance_reporter_loop(self):
        """
        Thread dedicada a coletar métricas e enviar para o Supervisor.
        """
        # Carrega configs do JSON
        config_sup = self.config.get('supervisor', {})
        report_interval = config_sup.get('supervisor_interval', 10)
        supervisor_info = config_sup.get('supervisor_info')

        while self._running:
            # Dorme primeiro
            for _ in range(report_interval):
                if not self._running: return
                time.sleep(1)

            try:
                # 1. COLETAR DADOS DO SISTEMA
                try:
                    load_avg = psutil.getloadavg() # Retorna tupla (1m, 5m, 15m)
                except AttributeError:
                    load_avg = (0.0, 0.0, 0.0) # Fallback para Windows antigo

                mem = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                cpu_percent = psutil.cpu_percent(interval=0.1)
                
                uptime = time.time() - self.start_time

                system_data = {
                    "uptime_seconds": int(uptime),
                    "load_average_1m": load_avg[0],
                    "load_average_5m": load_avg[1],
                    "cpu": {
                        "usage_percent": cpu_percent,
                        "count_logical": psutil.cpu_count(logical=True),
                        "count_physical": psutil.cpu_count(logical=False)
                    },
                    "memory": {
                        "total_mb": int(mem.total / (1024 * 1024)),
                        "available_mb": int(mem.available / (1024 * 1024)),
                        "percent_used": mem.percent,
                        "memory_used": int(mem.used / (1024 * 1024))
                    },
                    "disk": {
                        "total_gb": round(disk.total / (1024**3), 2),
                        "free_gb": round(disk.free / (1024**3), 2),
                        "percent_used": disk.percent
                    }
                }

                # 2. COLETAR DADOS DA "FAZENDA" (Workers/Tasks)
                farm_data = self._collect_farm_state()

                # 3. DADOS DE CONFIGURAÇÃO
                config_data = {
                     "max_queue": self.config['load_balancing'].get('max_queue_threshold', 0)
                }

                # 4. DADOS DOS VIZINHOS
                neighbors_data = self._collect_neighbors_state()

                # 5. GERAR PAYLOAD
                payload = server_performance_report(
                    server_uuid=self.id,
                    system_data=system_data,
                    farm_data=farm_data,
                    config_thresholds=config_data,
                    neighbors_data=neighbors_data
                )

                # 6. ENVIAR
                if supervisor_info:
                    self._send_to_supervisor(supervisor_info, payload)
                else:
                    logger.warning("[REPORT] Supervisor não configurado no JSON.")
                
                # Log local para debug visual
                logger.info(f"[REPORT] Métricas coletadas. CPU: {system_data['cpu']['usage_percent']}% | Fila: {farm_data['tasks']['tasks_pending']}")

            except Exception as e:
                logger.error(f"[REPORT] Erro ao gerar relatório de performance: {e}")


    def _collect_farm_state(self) -> dict:
        """Helper para calcular o estado dos workers e tarefas."""
        now = time.time()
        timeout = self.config['timing']['heartbeat_timeout']
        
        workers_total = 0
        workers_alive = 0
        workers_idle = 0
        workers_borrowed = 0 

        workers_received = 0
        workers_failed = 0
        
        with self.lock:
            queue_size = len(self.task_queue)
            # running seria tasks que saíram da fila mas não voltaram. 
            # Se não rastreamos isso, assumimos 0 ou implementamos depois.
            tasks_running = 0 
            
            workers_total = len(self.worker_status)
            
            for w_id, w_info in self.worker_status.items():
                print("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
                print(w_info)
                is_alive = (now - w_info['last_seen']) < timeout
                
                if is_alive:
                    workers_alive += 1
                    workers_idle += 0
                    
                    # Verifica se é worker recebido
                    if w_info.get('SERVER_UUID'): 
                         workers_received += 1
                else:
                    if w_info.get("BORROWED") == True:
                        workers_borrowed += 1
                    else:
                        workers_failed += 1


        return {
            "workers": {
                "total_registered": workers_total,
                "workers_utilization": 0, # Placeholder
                "workers_alive": workers_alive,
                "workers_idle": workers_idle,
                "workers_borrowed": workers_borrowed,
                "workers_recieved": workers_received,
                "workers_failed": workers_failed
            },
            "tasks": {
                "tasks_pending": queue_size,
                "tasks_running": tasks_running
            }
        }


    def _collect_neighbors_state(self) -> list:
        """Helper para formatar status dos vizinhos."""
        neighbors = []
        with self.lock:
            for peer_id, status in self.peer_status.items():
                # Converte timestamp para ISO
                last_seen_ts = status.get('last_alive', 0)
                last_seen_iso = datetime.fromtimestamp(last_seen_ts, tz=timezone.utc).isoformat()
                
                neighbors.append({
                    "server_uuid": peer_id,
                    "status": "available", # Se está no peer_status, assumimos available
                    "last_heartbeat": last_seen_iso
                })
        return neighbors

