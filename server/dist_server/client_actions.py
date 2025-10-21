# dist_server/client_actions.py
import socket
import json
import time
from typing import Dict, List
from logs.logger import logger

class ClientActionsMixin:

    def _send_heartbeat(self, peer: dict) -> bool:
        """Tenta enviar um heartbeat para um peer (agora é um método)."""
        retries = self.config['timing']['heartbeat_retries']
        delay = self.config['timing']['heartbeat_retry_delay']
        
        for attempt in range(retries):
            try:
                with socket.create_connection((peer['ip'], peer['port']), timeout=5) as client_socket:
                    msg = {"SERVER_ID": self.id, "TASK": "HEARTBEAT"}
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
                msg = {"MASTER": self.id, "TASK": "WORKER_REQUEST", "REQUESTOR_INFO": requestor_info}
                logger.info(f"[LOAD] Solicitando workers a {peer['id']}")
                s.sendall((json.dumps(msg) + '\n').encode('utf-8')) # Adiciona \n

                reader = s.makefile('r', encoding='utf-8')
                response_line = reader.readline()

                if not response_line:
                    return []
                
                data = json.loads(response_line)
                if data.get('RESPONSE') == 'OK': 
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