"""
worker_lib/worker_main.py
Contém a lógica principal do Worker.
"""

import socket
import json
import time
from .config import WORKER_ID, RECONNECT_DELAY
from .logger import logger
import worker_lib.state as state


# Variável para acumular dados incompletos
_buffer = b''


def receive_full_message(sock: socket.socket) -> dict | None:
    """
    Lê o socket até encontrar o delimitador '\n' e retorna o objeto JSON.
    Usa um buffer global para dados incompletos.
    """
    global _buffer
    
    # Tenta ler mais dados se necessário
    while b'\n' not in _buffer:
        try:
            # Buffer de leitura deve ser grande o suficiente, mas não excessivo
            chunk = sock.recv(4096)
            if not chunk:
                # Se o servidor fechar a conexão, limpa o buffer e retorna None
                _buffer = b''
                return None
            _buffer += chunk
        except socket.timeout:
            # Permite que o loop tente ler novamente se houver timeout (não deve ocorrer com settimeout(None))
            return None 
        except Exception as e:
            logger.error(f"Erro ao receber dados: {e}")
            _buffer = b''
            return None

    # Processa o buffer: divide na primeira ocorrência de \n
    message_part, _buffer = _buffer.split(b'\n', 1)
    
    # Tenta decodificar e deserializar JSON
    try:
        data = json.loads(message_part.decode('utf-8').strip())
        return data
    except json.JSONDecodeError as e:
        logger.error(f"JSON inválido recebido: {e} - Raw: {message_part.decode()}")
        return None
    except Exception as e:
        logger.error(f"Erro inesperado ao decodificar mensagem: {e}")
        return None


def process_task(task_data: dict) -> dict:
    """
    Simula o processamento de uma tarefa recebida.
    """
    user = task_data.get("USER")
    logger.info(f"Processando tarefa de consulta para o usuário: {user}")

    # Simulação: sucesso se o usuário for "Carlos"
    if user == "Carlos":
        time.sleep(2)  # Simula tempo de processamento
        response = {"STATUS": "OK", "SALDO": 999.99, "USER": user, "WORKER_ID": WORKER_ID, "TASK_ID": task_data.get("TASK_ID")}
        logger.success(f"Tarefa para '{user}' concluída com sucesso.")
        return response
    else:
        time.sleep(1)
        response = {"STATUS": "NOK", "TASK": "QUERY", "ERROR": f"Usuário '{user}' não encontrado.",
                    "WORKER_ID": WORKER_ID, "TASK_ID": task_data.get("TASK_ID")}
        logger.warning(f"Tarefa para '{user}' falhou: Usuário não encontrado.")
        return response

def send_message(sock: socket.socket, message: dict):
    """Envia uma mensagem JSON terminada em \n."""
    try:
        json_message = json.dumps(message) + '\n'
        sock.sendall(json_message.encode('utf-8'))
    except Exception as e:
        logger.error(f"Falha ao enviar mensagem: {e}")
        raise

def main_loop():
    """
    Loop principal que tenta se conectar ao servidor e processar tarefas.
    """
    global _buffer
    
    while True:
        current_ip = state.current_master['ip']
        current_port = state.current_master['port']
        is_home_master = (current_ip == state.home_master['ip'] and
                          current_port == state.home_master['port'])
        
        _buffer = b'' # Limpa o buffer a cada nova tentativa de conexão
        
        try:
            # Tenta se conectar ao servidor
            with socket.create_connection((current_ip, current_port), timeout=5) as client_socket:
                # O socket não deve ter timeout para o loop de escuta
                client_socket.settimeout(None)
                logger.info(f"Conectado com sucesso ao servidor {current_ip}:{current_port}")

                # 1. Envia mensagem inicial de identificação (Apresentação)
                presentation_message = {"WORKER": "ALIVE", "WORKER_ID": WORKER_ID}
                send_message(client_socket, presentation_message)
                logger.info("Apresentação inicial enviada ao Master.")


                # 2. Loop de escuta e resposta
                while True:
                    data = receive_full_message(client_socket)
                    
                    if data is None:
                        logger.warning("Conexão encerrada pelo Master ou erro de leitura. Tentando reconectar...")
                        break # Sai do loop interno e tenta nova conexão

                    task = data.get("TASK")

                    # Processa Tarefa de Consulta (QUERY)
                    if task == "QUERY":
                        result = process_task(data)
                        
                        # 1. Envia o resultado
                        send_message(client_socket, result)
                        logger.info(f"Resultado de tarefa enviado: {result.get('STATUS')}")
                        
                        # 2. Reafirma sua presença
                        send_message(client_socket, presentation_message)
                        logger.info("Reapresentação enviada ao Master.")


                    # Redirecionamento (REDIRECT) - Objetivo O5
                    elif task == "REDIRECT":
                        target = data.get("TARGET_MASTER")
                        if target and 'ip' in target and 'port' in target:
                            logger.warning(f"Recebido comando REDIRECT. Novo Master: {target['ip']}:{target['port']}")
                            state.current_master.update(target)
                            
                            # Envia ACK e encerra a conexão para iniciar uma nova
                            ack_msg = {"STATUS": "ACK", "MSG": "REDIRECT_RECEIVED"}
                            send_message(client_socket, ack_msg)
                            time.sleep(0.5) # Dá tempo para a mensagem ser enviada
                            
                            break # Sai do loop interno para tentar conectar ao novo Master
                        else:
                            logger.error(f"REDIRECT sem destino ou formato inválido: {data}. Ignorando.")

                    # ACK ou mensagem de status (ignora)
                    elif data.get("STATUS") == "ACK":
                        logger.debug(f"ACK recebido do Master: {data.get('MSG')}")
                        continue
                    
                    # Comando desconhecido
                    else:
                        logger.warning(f"Comando desconhecido: {data}")


        except (socket.timeout, ConnectionRefusedError, ConnectionResetError) as e:
            logger.error(f"Não foi possível conectar: {e}")
            if not is_home_master:
                logger.warning("Erro no mestre temporário. Voltando ao Home Master.")
                state.current_master.update(state.home_master)
            logger.info(f"Tentando novamente em {RECONNECT_DELAY}s...")
            time.sleep(RECONNECT_DELAY)
        except Exception as e:
            logger.critical(f"Erro inesperado no loop principal: {e}")
            time.sleep(RECONNECT_DELAY)