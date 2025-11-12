# dist_worker/client_actions.py
import socket
import json
from logs.logger import logger

class ClientActionsMixin:
    
    def _connect_and_send(self, payload: dict, host: str, port: int) -> dict:
        """
        Função helper para conectar, enviar UM payload e receber UMA resposta.
        (Antiga 'connect_and_send' do worker_v1.py)
        """
        # Se o worker foi sinalizado para parar, não tente novas conexões
        if not self._running:
            return None

        try:
            with socket.create_connection((host, port), timeout=5) as s:
                
                s.sendall((json.dumps(payload) + '\n').encode('utf-8'))
                
                reader = s.makefile('r', encoding='utf-8')
                response_line = reader.readline()

                if not response_line:
                    logger.warning("Servidor fechou a conexão sem resposta.")
                    return None
                
                response_data = json.loads(response_line)
                return response_data

        except socket.timeout:
            logger.error(f"Timeout ao tentar conectar com {host}:{port}")
            return None
        except ConnectionRefusedError:
            # Só loga o erro se o worker não estiver parando
            if self._running:
                logger.error(f"Conexão recusada por {host}:{port}. O servidor está online?")
            return None
        except Exception as e:
            if self._running:
                logger.error(f"Erro inesperado na comunicação: {e}")
            return None