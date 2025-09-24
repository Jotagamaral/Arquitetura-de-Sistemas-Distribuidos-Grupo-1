import socket
import json
from db.database import buscar_saldo, atualizar_saldo

def run_worker_session(endereco: str, porta: int, worker_id: int):
    """
    Função alvo de cada thread. Simula um cliente completo:
    1. Cria seu próprio socket.
    2. Conecta.
    3. Envia 'ALIVE'.
    4. Recebe e processa UMA tarefa.
    5. Desconecta.
    """
    import time
    TIMEOUT_TAREFA_SEGUNDOS = 10
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.settimeout(TIMEOUT_TAREFA_SEGUNDOS)
            client_socket.connect((endereco, porta))
            alive_message = {"WORKER": "ALIVE"}
            client_socket.sendall((json.dumps(alive_message) + '\n').encode('utf-8'))
            task_message_bytes = client_socket.recv(4096)
            if not task_message_bytes:
                print(f"Worker [{worker_id}]: Servidor fechou a conexão prematuramente.")
                return
            task_data = json.loads(task_message_bytes.decode('utf-8'))
            if task_data.get("TASK") == "QUERY":
                cpf_alvo = task_data.get("USER")
                print(f"Worker [{worker_id}] recebeu TAREFA QUERY para CPF {cpf_alvo}")
                resultado_busca = buscar_saldo(cpf_alvo)
                response_message = {}
                if resultado_busca:
                    _, saldo_decimal, _ = resultado_busca
                    saldo_json = float(saldo_decimal)
                    response_message = {"WORKER": f"Joao Gabriel-{worker_id}", "CPF": cpf_alvo, "SALDO": saldo_json, "TASK": "QUERY", "STATUS": "OK"}
                else:
                    response_message = {"WORKER": f"Joao Gabriel-{worker_id}", "CPF": cpf_alvo, "TASK": "QUERY", "STATUS": "NOK"}
                client_socket.sendall(json.dumps(response_message).encode('utf-8'))
            elif task_data.get("TASK") == "UPDATE":
                cpf_alvo = task_data.get("CPF")
                novo_saldo = task_data.get("SALDO")
                print(f"Worker [{worker_id}] TAREFA UPDATE para CPF {cpf_alvo}")
                sucesso_atualizacao = atualizar_saldo(cpf_alvo, novo_saldo)
                response_message = {}
                if sucesso_atualizacao:
                    response_message = {"WORKER": f"Joao Gabriel-{worker_id}", "CPF": cpf_alvo, "SALDO": novo_saldo, "TASK": "UPDATE", "STATUS": "OK"}
                else:
                    response_message = {"WORKER": f"Joao Gabriel-{worker_id}", "CPF": cpf_alvo, "TASK": "UPDATE", "STATUS": "NOK"}
                client_socket.sendall(json.dumps(response_message).encode('utf-8'))
    except socket.timeout:
        print(f"Worker [{worker_id}]: Timeout! O servidor não respondeu a tempo.")
    except ConnectionRefusedError:
        print(f"Worker [{worker_id}]: Conexão recusada pelo servidor.")
    except Exception as e:
        print(f"Worker [{worker_id}]: Ocorreu um erro inesperado: {e}")
