import socket
import json
from datetime import datetime
import mysql.connector
from mysql.connector import Error
import threading
import time

def buscar_saldo(cpf):
    """
    Busca o nome do cliente e o saldo da conta no banco de dados MySQL com base no CPF.
    """
    connection = None
    try:
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='ceub123456',
            database='sys'
        )
        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)
            sql_query = "SELECT c.NOME, a.SALDO FROM CONTA AS a JOIN USERS AS c ON a.fk_id_user = c.ID WHERE C.CPF = %s"
            cursor.execute(sql_query, (cpf,))
            usuario = cursor.fetchone()
            if usuario:
                return (usuario['NOME'], usuario['SALDO'], datetime.now().isoformat())
    except Error as e:
        print(f"Erro de DB na thread: {e}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
    return None

def atualizar_saldo(cpf: str, novo_saldo: float) -> bool:
    """
    Atualiza o saldo de um usuário no banco de dados com base no seu CPF.
    """
    connection = None
    try:
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='ceub123456',
            database='sys'
        )
        if connection.is_connected():
            cursor = connection.cursor()
            sql_query = "UPDATE CONTA AS a JOIN USERS AS c ON a.fk_id_user = c.ID SET a.SALDO = %s WHERE c.CPF = %s"
            cursor.execute(sql_query, (novo_saldo, cpf))
            connection.commit()
            if cursor.rowcount > 0:
                return True
    except Error as e:
        print(f"Erro de DB na thread: {e}")
        if connection:
            connection.rollback()
    finally:
        if connection and connection.is_connected():
            connection.close()
    return False

def run_worker_session(endereco: str, porta: int, worker_id: int):
    """
    Função alvo de cada thread. Simula um cliente completo:
    1. Cria seu próprio socket.
    2. Conecta.
    3. Envia 'ALIVE'.
    4. Recebe e processa UMA tarefa.
    5. Desconecta.
    """
    TIMEOUT_TAREFA_SEGUNDOS = 10

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            
            # Define um timeout para operações de socket (connect, recv)
            client_socket.settimeout(TIMEOUT_TAREFA_SEGUNDOS)

            # 1. Conecta ao servidor
            client_socket.connect((endereco, porta))
            # print(f"Worker [{worker_id}] conectou.")

            # 2. Envia a mensagem 'ALIVE'
            alive_message = {"WORKER": "ALIVE"}
            client_socket.sendall((json.dumps(alive_message) + '\n').encode('utf-8'))

            # 3. Aguarda por uma tarefa
            task_message_bytes = client_socket.recv(4096)
            if not task_message_bytes:
                print(f"Worker [{worker_id}]: Servidor fechou a conexão prematuramente.")
                return

            task_data = json.loads(task_message_bytes.decode('utf-8'))
            
            # 4. Processa a tarefa
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

            # print(f"Worker [{worker_id}] concluiu e vai desconectar.")

    except socket.timeout:
        print(f"Worker [{worker_id}]: Timeout! O servidor não respondeu a tempo.")
    except ConnectionRefusedError:
        print(f"Worker [{worker_id}]: Conexão recusada pelo servidor.")
    except Exception as e:
        print(f"Worker [{worker_id}]: Ocorreu um erro inesperado: {e}")

# --- O Lançador de Threads ---
if __name__ == "__main__":
    ENDERECO_IP = '10.62.217.32'
    PORTA = 5900

    # --- PARÂMETROS DO TESTE DE ESTRESSE ---
    NUMERO_DE_CLIENTES_SIMULTANEOS = 50 
    INTERVALO_ENTRE_RAJADAS_SEGUNDOS = 1 

    ## IDEIA DE CLIENTES UTILIZADA COM IA.
    worker_counter = 0
    try:
        print(f"Iniciando teste de estresse contra {ENDERECO_IP}:{PORTA}")
        print(f"Lançando {NUMERO_DE_CLIENTES_SIMULTANEOS} clientes a cada {INTERVALO_ENTRE_RAJADAS_SEGUNDOS} segundo(s).")
        print("Pressione Ctrl+C para parar.")

        while True:
            print(f"\n--- Disparando rajada de {NUMERO_DE_CLIENTES_SIMULTANEOS} clientes ---")
            
            # Cria e inicia a rajada de threads
            for i in range(NUMERO_DE_CLIENTES_SIMULTANEOS):
                worker_counter += 1
                thread = threading.Thread(
                    target=run_worker_session,
                    args=(ENDERECO_IP, PORTA, worker_counter)
                )
                thread.start()
            
            # Aguarda antes de disparar a próxima rajada
            time.sleep(INTERVALO_ENTRE_RAJADAS_SEGUNDOS)

    except KeyboardInterrupt:
        print("\nTeste de estresse interrompido pelo usuário. Encerrando.")
