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

def process_task(task_data: dict) -> dict:
    """
    Simula o processamento de uma tarefa recebida do servidor.
    Esta função é onde a "mágica" do seu worker aconteceria de verdade.
    """
    user = task_data.get("USER")
    logger.info(f"Processando tarefa de consulta para o usuário: {user}")

    # --- LÓGICA DE SIMULAÇÃO ---
    # Para fins de exemplo, vamos simular sucesso se o usuário for "Carlos"
    # e falha para qualquer outro usuário.
    if user == "Carlos":
        # Simula uma operação bem-sucedida
        time.sleep(2)  # Simula tempo de processamento
        response = {
            "STATUS": "OK",
            "SALDO": 999.99,
            "USER": user,
            "WORKER_ID": WORKER_ID
        }
        logger.success(f"Tarefa para '{user}' concluída com sucesso.")
        return response
    else:
        # Simula uma falha
        time.sleep(1)
        response = {
            "STATUS": "NOK",
            "TASK": "QUERY",
            "ERROR": f"Usuário '{user}' não encontrado.",
            "WORKER_ID": WORKER_ID
        }
        logger.warning(f"Tarefa para '{user}' falhou: Usuário não encontrado.")
        return response

def main_loop():
    """
    Loop principal que gerencia a conexão com o servidor mestre.
    """
    while True:
        current_ip = state.current_master['ip']
        current_port = state.current_master['port']
        is_home_master = (current_ip == state.home_master['ip'] and
                          current_port == state.home_master['port'])

        try:
            # Tenta estabelecer a conexão com o servidor mestre atual
            with socket.create_connection((current_ip, current_port), timeout=5) as client_socket:
                logger.info(f"Conectado com sucesso ao servidor {current_ip}:{current_port}")

                # 1. Apresenta-se ao servidor para pedir uma tarefa
                presentation_message = {"WORKER": "ALIVE", "WORKER_ID": WORKER_ID}
                client_socket.sendall(json.dumps(presentation_message).encode('utf-8'))
                logger.info(f"Apresentação enviada: {presentation_message}")

                # Loop para escutar comandos do servidor enquanto a conexão estiver ativa
                while True:
                    response_bytes = client_socket.recv(4096)
                    if not response_bytes:
                        logger.warning("Conexão fechada pelo servidor. Tentando reconectar...")
                        break  # Sai do loop de escuta para reconectar

                    data = json.loads(response_bytes.decode('utf-8'))
                    logger.debug(f"Recebido do servidor: {data}")

                    task = data.get("TASK")

                    # 2. Servidor enviou uma tarefa de consulta
                    if task == "QUERY":
                        result = process_task(data)
                        client_socket.sendall(json.dumps(result).encode('utf-8'))
                        logger.info(f"Resultado da tarefa enviado: {result}")
                        # Após enviar o resultado, pede a próxima tarefa
                        client_socket.sendall(json.dumps(presentation_message).encode('utf-8'))

                    # 5. Servidor enviou um comando de redirecionamento
                    elif task == "REDIRECT":
                        target = data.get("TARGET_MASTER")
                        if not target:
                            logger.error("Comando REDIRECT recebido sem TARGET_MASTER. Ignorando.")
                            continue

                        logger.warning(f"Recebido comando REDIRECT. "
                                     f"Desconectando de {current_ip}:{current_port} "
                                     f"e conectando ao novo mestre temporário: {target['ip']}:{target['port']}")

                        # Atualiza o estado para apontar para o novo mestre
                        state.current_master['ip'] = target['ip']
                        state.current_master['port'] = target['port']
                        break  # Quebra o loop de escuta para forçar a reconexão no novo mestre

                    else:
                        logger.warning(f"Recebido comando desconhecido ou não implementado: {data}")
                        # Espera um pouco antes de pedir tarefa de novo
                        time.sleep(5)
                        client_socket.sendall(json.dumps(presentation_message).encode('utf-8'))


        except (socket.timeout, ConnectionRefusedError, ConnectionResetError) as e:
            logger.error(f"Não foi possível conectar ao servidor {current_ip}:{current_port}. Erro: {e}")
            if not is_home_master:
                logger.warning("Falha ao conectar no mestre temporário. Revertendo para o Home Master.")
                # Se a conexão com o mestre temporário falhar, volta para casa.
                state.current_master['ip'] = state.home_master['ip']
                state.current_master['port'] = state.home_master['port']

            logger.info(f"Aguardando {RECONNECT_DELAY} segundos para tentar novamente...")
            time.sleep(RECONNECT_DELAY)
        except Exception as e:
            logger.critical(f"Erro inesperado no loop principal: {e}")
            time.sleep(RECONNECT_DELAY)