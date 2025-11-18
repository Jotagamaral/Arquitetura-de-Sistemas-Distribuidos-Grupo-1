# dist_server/client_actions.py
import socket
import json
import time
from typing import Dict, List
from random import uniform
from logs.logger import logger
from payload_models import server_heartbeat, server_request_worker, server_command_release, server_release_completed

class ClientActionsMixin:

    def _send_heartbeat(self, peer: dict) -> bool:
        """Tenta enviar um heartbeat para um peer usando backoff exponencial."""
        retries = self.config['timing']['heartbeat_retries']
        base_delay = self.config['timing'].get('heartbeat_retry_delay', 5)
        backoff_factor = self.config['timing'].get('heartbeat_backoff_factor', 2)
        max_delay = self.config['timing'].get('heartbeat_max_delay', 60)
        jitter_frac = self.config['timing'].get('heartbeat_jitter_frac', 0.1)
   
        for attempt in range(retries):
            try:
                with socket.create_connection((peer['ip'], peer['port']), timeout=5) as client_socket:
                    msg = server_heartbeat(server_id=self.id)
                    client_socket.sendall((json.dumps(msg) + '\n').encode('utf-8')) # Adiciona \n

                    reader = client_socket.makefile('r', encoding='utf-8')
                    response_line = reader.readline()

                    if not response_line:
                        logger.warning(f"[HB] Tentativa {attempt + 1}/{retries}: Sem resposta de {peer['id']}")
                        # irá dormir abaixo com backoff
                        raise ConnectionError("Sem resposta")

                    data = json.loads(response_line)
                    if data.get("RESPONSE") == "ALIVE":
                        with self.lock:
                            self.peer_status[peer['id']] = {'last_alive': time.time()}
                        logger.success(f"[HB] Sucesso com {peer['id']}.")
                        return True
                    else:
                        logger.warning(f"[HB] Resposta inesperada de {peer['id']}: {data}")
                        # tratar como falha e tentar novamente

            except (socket.timeout, ConnectionRefusedError, ConnectionError) as e:
                logger.warning(f"[HB] Tentativa {attempt + 1}/{retries} para {peer['id']} falhou: {e}")
            except Exception as e:
                logger.error(f"[HB] Erro inesperado na tentativa {attempt + 1} para {peer['id']}: {e}")

            # calcula delay exponencial com cap e jitter antes da próxima tentativa
            if attempt < retries - 1:
                raw_delay = base_delay * (backoff_factor ** attempt)
                capped = min(raw_delay, max_delay)
                jitter = uniform(-jitter_frac, jitter_frac)
                delay = capped * (1 + jitter)
                logger.info(f"[HB] Dormindo {delay:.2f}s antes da próxima tentativa ({attempt + 1}/{retries}).")
                time.sleep(delay)

        logger.error(f"[HB] Todas as {retries} tentativas para {peer['id']} falharam.")
        return False

    def _ask_peer_for_workers(self, peer) -> List[Dict]:
        """Envia solicitação de workers a um peer (agora é um método)."""
        try:
            with socket.create_connection((peer['ip'], peer['port']), timeout=5) as s:

                requestor_info = {'ip': self.host, 'port': self.port}
                msg = server_request_worker(requestor_info=requestor_info)

                logger.info(f"[LOAD] Solicitando workers a {peer['id']}")

                s.sendall((json.dumps(msg) + '\n').encode('utf-8')) # Adiciona \n

                reader = s.makefile('r', encoding='utf-8')
                response_line = reader.readline()

                if not response_line:
                    return []
                
                data = json.loads(response_line)
                if data.get('RESPONSE') == 'AVAILABLE': 
                    logger.success(f"[LOAD] Peer {peer['id']} respondeu OK ao pedido de workers.")
                    return [] 
                
                elif data.get('RESPONSE') == 'UNAVAILABLE':
                    logger.info(f"[LOAD] Peer {peer['id']} não tem workers disponíveis.")
                    return []
                
                else:
                    logger.warning(f"[LOAD] Resposta inesperada de {peer['id']}: {data}")
                    return []
        except Exception as e:
            logger.warning(f"[LOAD] Falha ao perguntar para peer {peer['id']}: {e}")
            return []

    def _send_command_release(self, peer: dict, worker_ids: list) -> bool:
        """
        Envia uma notificação COMMAND_RELEASE para um peer (dono original).
        Retorna True se o peer confirmar com RELEASE_ACK.
        """
        try:
            # Constrói o payload 5.1
            msg = server_command_release(master_id=self.id, worker_ids=worker_ids)
            logger.info(f"[RELEASE] Notificando {peer['id']} sobre liberação de {len(worker_ids)} workers.")

            with socket.create_connection((peer['ip'], peer['port']), timeout=5) as s:
                s.sendall((json.dumps(msg) + '\n').encode('utf-8')) # Adiciona \n

                reader = s.makefile('r', encoding='utf-8')
                response_line = reader.readline()

                if not response_line:
                    logger.warning(f"[RELEASE] Sem resposta de {peer['id']} para COMMAND_RELEASE.")
                    return False
                
                data = json.loads(response_line)
                
                # Espera pelo payload 5.2
                if data.get('RESPONSE') == 'RELEASE_ACK':
                    logger.success(f"[RELEASE] {peer['id']} confirmou recebimento (RELEASE_ACK) para {data.get('WORKERS', [])}.")
                    
                    return True
                else:
                    logger.warning(f"[RELEASE] Resposta inesperada de {peer['id']}: {data}")
                    return False
         
        except Exception as e:
            logger.warning(f"[RELEASE] Falha ao enviar COMMAND_RELEASE para {peer['id']}: {e}")
            return False

    def _send_release_completed(self, peer: dict, worker_ids: list):
        """
        Envia uma notificação "RELEASE_COMPLETED" para um peer (o que devolveu).
        Esta é uma notificação "fire-and-forget".
        """
        try:
            # Constrói o payload
            msg = server_release_completed(server_id=self.id, worker_uuids=worker_ids)
            
            logger.info(f"[RELEASE] Enviando confirmação final (RELEASE_COMPLETED) para {peer['id']} sobre {worker_ids}")

            # Conecta, envia e fecha.
            with socket.create_connection((peer['ip'], peer['port']), timeout=5) as s:
                s.sendall((json.dumps(msg) + '\n').encode('utf-8'))
            
            logger.success(f"[RELEASE] Confirmação final enviada para {peer['id']}.")

        except Exception as e:
            # Se falhar, apenas logamos. Não é uma falha crítica.
            logger.warning(f"[RELEASE] Falha ao enviar RELEASE_COMPLETED para {peer['id']}: {e}")