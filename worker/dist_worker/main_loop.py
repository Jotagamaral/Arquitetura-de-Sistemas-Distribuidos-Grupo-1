# dist_worker/main_loop.py
import time
from random import randint
from logs.logger import logger 
from payload_models import get_task, task_status

class LogicMixin:

    def _run_loop(self):
        """
        Loop principal do Worker.
        (Antiga 'run_worker' do worker_v1.py)
        """
        
        while self._running: # A flag de controle agora é checada aqui
            try:
                # Decide qual 'owner_id' enviar
                current_owner_id = None
                if self.current_master_host != self.home_host or self.current_master_port != self.home_port:
                    current_owner_id = self.owner_id

                # 1. PEDIR TAREFA
                logger.info(f"Pedindo nova tarefa ao servidor {self.current_master_host}:{self.current_master_port}...")
                
                get_task_payload = get_task(self.worker_id, owner_id=current_owner_id)

                # Chama o método do ClientActionsMixin
                response = self._connect_and_send(get_task_payload, self.current_master_host, self.current_master_port) 

                # Se o worker foi parado, response será None ou a flag estará False
                if not self._running:
                    break # Sai do loop while


                if response is None:
                    logger.warning(f"Falha ao conectar com {self.current_master_host}:{self.current_master_port}.")
                    
                    # Verifica se o worker estava "fora de casa"
                    is_at_home = (self.current_master_host == self.home_host and 
                                  self.current_master_port == self.home_port)

                    if not is_at_home:
                        # Se falhou ao conectar com um mestre temporário, VOLTA PARA CASA
                        logger.error(f"Conexão perdida com mestre temporário. RETORNANDO PARA CASA ({self.home_host}:{self.home_port}).")
                        self.current_master_host = self.home_host
                        self.current_master_port = self.home_port
                        time.sleep(5) # Pausa antes de tentar conectar em casa
                    else:
                        # Se falhou ao conectar com o mestre DE CASA, apenas espere e tente de novo.
                        logger.error(f"Servidor de CASA ({self.home_host}) está offline. Tentando novamente em 15s...")
                        time.sleep(15)
                    
                    continue # Reinicia o loop (agora com o host/porta corretos)

                # 2. PROCESSAR RESPOSTA
                task_cmd = response.get("TASK")

                # --- LÓGICAS DE FEDERAÇÃO ---
                if task_cmd == "REDIRECT":
                    new_master = response.get("SERVER_REDIRECT")
                    if new_master and 'ip' in new_master and 'port' in new_master:
                        logger.warning(f"ORDEM DE REDIRECT: Movendo para {new_master['ip']}:{new_master['port']}")
                        # Atualiza o ESTADO do worker
                        self.current_master_host = new_master['ip']
                        self.current_master_port = new_master['port']
                    else:
                        logger.error("Recebido REDIRECT mal formatado.")
                    time.sleep(2)
                    continue 

                elif task_cmd == "RETURN":
                    home_master = response.get("SERVER_RETURN")
                    if home_master and home_master['ip'] == self.home_host and home_master['port'] == self.home_port:
                        logger.warning(f"ORDEM DE RETORNO: Voltando para casa {home_master['ip']}:{home_master['port']}")
                        # Atualiza o ESTADO do worker
                        self.current_master_host = self.home_host
                        self.current_master_port = self.home_port
                    else:
                         logger.error("Recebido RETURN mal formatado.")
                    time.sleep(2)
                    continue
                # --- FIM DA LÓGICA DE FEDERAÇÃO ---

                # Caso 2a: Fila Vazia
                elif task_cmd == "NO_TASK":
                    logger.info("Fila vazia. Aguardando 5 segundos...")
                    time.sleep(5)
                    continue

                # Caso 2b: Recebeu uma Tarefa Real
                elif task_cmd == "QUERY":
                    task = response
                    logger.success(f"Recebida tarefa QUERY para: {task.get('USER')}")

                    work_time = 1
                    logger.info(f"Processando tarefa por {work_time} segundos...")
                    time.sleep(work_time)

                    status_payload = task_status(
                        status="OK",
                        worker_id=self.worker_id,
                        task=task_cmd
                    )

                    logger.info(f"Reportando status 'OK' para server...")
                    ack_response = self._connect_and_send(status_payload, self.current_master_host, self.current_master_port)

                    if ack_response and ack_response.get("STATUS") == "ACK":
                        logger.success(f"Servidor confirmou (ACK) o recebimento do status.")
                    else:
                        logger.warning(f"Servidor NÃO confirmou o recebimento do status. Resposta: {ack_response}")
                    
                    time.sleep(1) 

                # Caso 2c: Resposta inesperada
                else:
                    logger.error(f"Resposta inesperada do servidor: {response}")
                    time.sleep(5)

            except Exception as e:
                # Só loga o erro se o worker não estiver parando
                if self._running:
                    logger.critical(f"Erro fatal no loop do worker: {e}", exc_info=True)
                    time.sleep(15)
        
        logger.info(f"Worker {self.worker_id} encerrando o loop principal.")