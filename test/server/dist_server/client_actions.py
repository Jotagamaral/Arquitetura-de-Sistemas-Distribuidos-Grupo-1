# dist_server/client_actions.py
import socket
import json
import time
from typing import Dict, List
from ..logs.logger import logger
from payload_models import server_heartbeat, server_request_worker, server_command_release

class ClientActionsMixin:

    def _send_heartbeat(self, peer: dict) -> bool:
        """Tenta enviar um heartbeat para um peer (agora é um método)."""
        retries = self.config['timing']['heartbeat_retries']
        delay = self.config['timing']['heartbeat_retry_delay']
        
        for attempt in range(retries):
            try:
                with socket.create_connection((peer['ip'], peer['port']), timeout=5) as client_socket:
                    
                    
                    msg = server_heartbeat(server_id=self.id)
                    client_socket.sendall((json.dumps(msg) + '\n').encode('utf-8')) # Adiciona \n

                    reader = client_socket.makefile('r', encoding='utf-8')
                    response_line = reader.readline()

                    if not response_line:
                        logger.warning(f"[HB] Tentativa {attempt + 1}/{retries}: Sem resposta de {peer['id']}")
                        time.sleep(delay)
                        continue

                    data = json.loads(response_line)
                    if data.get("RESPONSE") == "ALIVE":
                        with self.lock:
                            self.peer_status[peer['id']] = {'last_alive': time.time()}
                        logger.success(f"[HB] Sucesso com {peer['id']}.") # Log menos verboso
                        return True
                    else:
                         logger.warning(f"[HB] Resposta inesperada de {peer['id']}: {data}")

            except (socket.timeout, ConnectionRefusedError) as e:
                logger.warning(f"[HB] Tentativa {attempt + 1}/{retries} para {peer['id']} falhou: {e}")
            except Exception as e:
                logger.error(f"[HB] Erro inesperado na tentativa {attempt + 1} para {peer['id']}: {e}")

            if attempt < retries - 1:
                time.sleep(delay)

        logger.error(f"[HB] Todas as {retries} tentativas para {peer['id']} falharam.")
        return False

    def _ask_peer_for_workers(self, peer) -> List[Dict]:
        """Envia solicitação de workers a um peer (agora é um método)."""
        try:
            with socket.create_connection((peer['ip'], peer['port']), timeout=5) as s:

                requestor_info = {'ip': self.host, 'port': self.port}
                msg = server_request_worker(master_id=self.id, requestor_info=requestor_info)

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