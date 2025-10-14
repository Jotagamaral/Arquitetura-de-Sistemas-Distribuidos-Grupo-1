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
from random import randint


def process_task(task_data: dict) -> dict:
    """
    Simula o processamento de uma tarefa recebida.
    """
    user = task_data.get("USER")
    logger.info(f"Processando tarefa de consulta para o usuário: {user}")

    # Simulação: sucesso
    if user != 'Joao':
        time.sleep(2)  # Simula tempo de processamento
        response = {"STATUS": "OK", "SALDO": randint(50, 999), "USER": user, "WORKER_ID": WORKER_ID}
        logger.success(f"Tarefa concluída com sucesso.")
        return response
    else:
        time.sleep(1)
        response = {"STATUS": "NOK", "TASK": "QUERY", "ERROR": f"User not found"}

        logger.warning(f"Tarefa para '{user}' falhou: Usuário não encontrado.")
        return response


def main_loop():
    """
    Loop principal que tenta se conectar ao servidor e processar tarefas.
    """
    while True:
        current_ip = state.current_master['ip']
        current_port = state.current_master['port']
        is_home_master = (current_ip == state.home_master['ip'] and
                          current_port == state.home_master['port'])

        try:
            # Tenta se conectar ao servidor
            with socket.create_connection((current_ip, current_port), timeout=5) as client_socket:
                logger.info(f"Conectado com sucesso ao servidor {current_ip}:{current_port}")

                # Envia mensagem inicial de identificação
                presentation_message = {"WORKER": "ALIVE", "WORKER_ID": WORKER_ID}
                client_socket.sendall(json.dumps(presentation_message).encode('utf-8'))

                # Loop de escuta e resposta
                while True:
                    response_bytes = client_socket.recv(4096)
                    if not response_bytes:
                        logger.warning("Conexão encerrada. Tentando reconectar...")
                        break

                    data = json.loads(response_bytes.decode('utf-8'))
                    task = data.get("TASK")

                    # Se for tarefa de consulta, processa e responde
                    if task == "QUERY":
                        result = process_task(data)
                        client_socket.sendall(json.dumps(result).encode('utf-8'))

                        #---------------------------------------------#
                        # client_socket.sendall(json.dumps(presentation_message).encode('utf-8'))

                    # Se for redirecionamento, atualiza servidor mestre
                    elif task == "REDIRECT":

                        ip_master, port_master = data.get("MASTER_REDIRECT")
                        target = {'ip': ip_master, 'port': port_master}

                        if target:
                            logger.warning(f"Redirecionando para novo mestre {target['ip']}:{target['port']}")
                            state.current_master.update(target)
                            break
                        else:
                            logger.error("REDIRECT sem destino. Ignorando.")
                            
 
                    # Comando desconhecido
                    else:
                        logger.warning(f"Comando desconhecido: {data}")
                        time.sleep(5)
                        client_socket.sendall(json.dumps(presentation_message).encode('utf-8'))

        except (socket.timeout, ConnectionRefusedError, ConnectionResetError) as e:
            logger.error(f"Não foi possível conectar: {e}")

            if not is_home_master:
                logger.warning("Erro no mestre temporário. Voltando ao Home Master.")
                state.current_master.update(state.home_master)

            logger.info(f"Tentando novamente em {RECONNECT_DELAY}s...")
            time.sleep(RECONNECT_DELAY)
            
        except Exception as e:
            logger.critical(f"Erro inesperado: {e}")
            time.sleep(RECONNECT_DELAY)
