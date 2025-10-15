import socket
import json
import time
from .server_config import lista_peers, HEARTBEAT_INTERVAL, HEARTBEAT_RETRIES, HEARTBEAT_RETRY_DELAY, MY_ID
from .server_state import peer_status, status_lock
from .server_logger import logger

def send_heartbeat(peer: dict) -> bool:
    """
    Tenta enviar um heartbeat para um peer com um sistema de retentativas.
    Retorna True em caso de sucesso, False se todas as tentativas falharem.
    """
    for attempt in range(HEARTBEAT_RETRIES):
        try:
            with socket.create_connection((peer['ip'], peer['port']), timeout=5) as client_socket:
                
                msg = {"SERVER_ID": MY_ID, "TASK": "HEARTBEAT"}
                
                client_socket.sendall(json.dumps(msg).encode('utf-8'))
                response = client_socket.recv(1024)

                if not response:
                    logger.warning(f"[HEARTBEAT] Tentativa {attempt + 1}/{HEARTBEAT_RETRIES}: Sem resposta de {peer['id']}")
                    time.sleep(HEARTBEAT_RETRY_DELAY)
                    continue # Tenta novamente

                data = json.loads(response.decode('utf-8'))
                if data.get("RESPONSE") == "ALIVE":
                    with status_lock:
                        peer_status[peer['id']] = {'last_alive': time.time()}
                    logger.info(f"[HEARTBEAT] Sucesso na comunicação com {peer['id']}.")
                    return True # Sucesso! Sai da função.

        except (socket.timeout, ConnectionRefusedError) as e:
            logger.warning(f"[HEARTBEAT] Tentativa {attempt + 1}/{HEARTBEAT_RETRIES} para {peer['id']} falhou: {e}")
            
        except Exception as e:
            logger.error(f"[HEARTBEAT] Erro inesperado na tentativa {attempt + 1} para {peer['id']}: {e}")

        # Espera um pouco antes da próxima tentativa
        if attempt < HEARTBEAT_RETRIES - 1:
            time.sleep(HEARTBEAT_RETRY_DELAY)

    # Se o loop terminar sem sucesso, todas as tentativas falharam
    logger.error(f"[HEARTBEAT] Todas as {HEARTBEAT_RETRIES} tentativas para {peer['id']} falharam.")
    return False

def heartbeat_loop():
    """
    Loop que envia heartbeats. Se um peer falhar todas as tentativas,
    ele é removido da lista dinâmica.
    """
    while True:
        # Itera sobre uma cópia da lista para permitir a remoção de itens da original
        # de forma segura dentro do loop.
        for peer in list(lista_peers):
            
            success = send_heartbeat(peer)
            
            if not success:
                logger.warning(f"Removendo o peer inativo {peer['id']} da lista de verificação.")
                with status_lock:
                    # Remove da lista dinâmica de peers
                    if peer in lista_peers:
                        lista_peers.remove(peer)
                    
                    # Remove também do dicionário de status
                    if peer['id'] in peer_status:
                        del peer_status[peer['id']]
        
        time.sleep(HEARTBEAT_INTERVAL)