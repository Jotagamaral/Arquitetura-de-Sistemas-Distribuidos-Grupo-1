# worker_lib/connection_loop.py
import socket
import json
import time
from logs.logger import logger

class ConnectionLoopMixin:

    def _connection_loop(self):
        """
        Loop principal que tenta se conectar ao servidor e processar tarefas.
        (Substitui o antigo main_loop)
        """
        
        # self._running é a flag de controle da classe Worker
        while self._running:
            # self.current_master e self.home_master vêm da classe Worker
            current_ip = self.current_master['ip']
            current_port = self.current_master['port']
            is_home_master = (current_ip == self.home_master['ip'] and
                              current_port == self.home_master['port'])

            try:
                # Tenta se conectar ao servidor
                with socket.create_connection((current_ip, current_port), timeout=5) as client_socket:
                    logger.info(f"Conectado com sucesso ao servidor {current_ip}:{current_port}")

                    # **CORREÇÃO DE BUG:** Usar makefile para I/O baseada em linha
                    writer = client_socket.makefile('w', encoding='utf-8')
                    reader = client_socket.makefile('r', encoding='utf-8')

                    # Envia mensagem inicial de identificação
                    presentation_message = {"WORKER": "ALIVE", "WORKER_ID": self.worker_id, "OWNER_ID": self.owner_id}
                    
                    # **CORREÇÃO DE BUG:** Adiciona '\n' e flush
                    writer.write(json.dumps(presentation_message) + '\n')
                    writer.flush()

                    # Loop de escuta e resposta
                    while self._running:
                        # **CORREÇÃO DE BUG:** Lê linha por linha
                        line = reader.readline()
                        if not line:
                            logger.warning("Conexão encerrada pelo servidor. Tentando reconectar...")
                            break # Sai do loop interno

                        data = json.loads(line)
                        task = data.get("TASK")

                        # Se for tarefa de consulta, processa e responde
                        if task == "QUERY":
                            # self._process_task vem do outro Mixin
                            result = self._process_task(data) 
                            
                            # **CORREÇÃO DE BUG:** Adiciona '\n' e flush
                            writer.write(json.dumps(result) + '\n')
                            writer.flush()

                        # Se for redirecionamento, atualiza servidor mestre
                        elif task == "REDIRECT":
                            
                            # **CORREÇÃO DE BUG:** Servidor envia um DICT, não uma LISTA
                            target = data.get("MASTER_REDIRECT") 

                            if target and 'ip' in target and 'port' in target:
                                logger.warning(f"Redirecionando para novo mestre {target['ip']}:{target['port']}")
                                self.current_master.update(target)
                                break # Sai do loop interno para reconectar
                            else:
                                logger.error(f"REDIRECT sem destino ou formato inválido: {data}")
                        
                        # Comando desconhecido
                        else:
                            logger.warning(f"Comando desconhecido: {data}")
                            time.sleep(5)
                            # Reenvia apresentação caso o mestre tenha se perdido
                            writer.write(json.dumps(presentation_message) + '\n')
                            writer.flush()

            except (socket.timeout, ConnectionRefusedError, ConnectionResetError, BrokenPipeError, EOFError) as e:
                logger.error(f"Não foi possível conectar ou conexão perdida: {e}")

                if not is_home_master:
                    logger.warning("Erro no mestre temporário. Voltando ao Home Master.")
                    self.current_master.update(self.home_master)
                
                # self.reconnect_delay vem da classe Worker
                logger.info(f"Tentando novamente em {self.reconnect_delay}s...")
                time.sleep(self.reconnect_delay)
            
            except Exception as e:
                if not self._running: # Se self._running for False, é um shutdown esperado
                    break
                logger.critical(f"Erro inesperado no loop: {e}")
                time.sleep(self.reconnect_delay)
        
        logger.info("Loop de conexão do Worker encerrado.")