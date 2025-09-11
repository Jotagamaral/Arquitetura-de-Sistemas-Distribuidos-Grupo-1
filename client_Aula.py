import socket
import json
from datetime import datetime
import mysql.connector
from mysql.connector import Error

# A função buscar_saldo continua exatamente a mesma, não precisa de alterações.
def buscar_saldo(cpf):
    """
    Busca o nome do cliente e o saldo da conta no banco de dados MySQL com base no CPF.
    Retorna uma tupla com os dados do usuário, saldo e a data de atualização.
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
            
            sql_query = """
                SELECT c.NOME, a.SALDO
                FROM CONTA AS a
                JOIN USERS AS c ON a.fk_id_user = c.ID
                WHERE C.CPF = %s
            """
            
            cursor.execute(sql_query, (cpf,))
            
            usuario = cursor.fetchone()

            if usuario:
                return (usuario['NOME'], usuario['SALDO'], datetime.now().isoformat())
            
    except Error as e:
        print(f"Erro ao conectar ou executar a consulta no MySQL: {e}")
        return None
    
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

    return None

def atualizar_saldo(cpf, saldo):
    """
    Faz o update do saldo no banco de dados MySQL com base no CPF.
    Retorna uma tupla com os dados do usuário, saldo e a data de atualização.
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
            
            sql_query = """
                UPDATE CONTA as a
                JOIN USERS AS c ON a.fk_id_user = c.ID
                SET a.SALDO = %s
                WHERE a.id = (SELECT ID FROM USERS u WHERE u.CPF = %s)
            """
            
            cursor.execute(sql_query, (saldo, cpf,))
            
            usuario = cursor.fetchone()

            if usuario:
                return (usuario['NOME'], usuario['SALDO'], datetime.now().isoformat())
            
    except Error as e:
        print(f"Erro ao conectar ou executar a consulta no MySQL: {e}")
        return None
    
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

    return None


def atualizar_saldo(cpf: str, novo_saldo: float) -> bool:
    """
    Atualiza o saldo de um usuário no banco de dados com base no seu CPF.

    Args:
        cpf (str): O CPF do usuário a ser atualizado.
        novo_saldo (float): O novo valor do saldo.

    Returns:
        bool: True se a atualização foi bem-sucedida, False caso contrário.
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
            
            # Query otimizada: mais direta e legível
            sql_query = """
                UPDATE CONTA AS a
                JOIN USERS AS c ON a.fk_id_user = c.ID
                SET a.SALDO = %s
                WHERE c.CPF = %s
            """
            
            cursor.execute(sql_query, (novo_saldo, cpf))
            
            connection.commit()
            
            if cursor.rowcount > 0:
                print(f"Saldo do CPF {cpf} atualizado com sucesso.")
                return True
            else:
                print(f"Nenhum usuário encontrado com o CPF {cpf}. Nenhuma alteração foi feita.")
                return False
            
    except Error as e:
        print(f"Erro ao atualizar o saldo no MySQL: {e}")
        # Se ocorrer um erro, desfaz a transação.
        if connection:
            connection.rollback()
        return False
    
    finally:
        if connection and connection.is_connected():
            connection.close()
    
    return False
# Função run_client reescrita para ser síncrona e usar a biblioteca 'socket'
def run_client(endereco: str, porta: int) -> None:
    """
    Conecta-se a um servidor TCP, envia uma mensagem 'alive', recebe e processa uma tarefa.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.connect((endereco, porta))
            print(f"Cliente conectado ao servidor em {endereco}:{porta}.")
            
            
            alive_message = {
                "WORKER": "ALIVE"
            }
            # Sockets enviam bytes, então precisamos codificar a string JSON para utf-8
            dados_json = json.dumps(alive_message) + '\n'

            client_socket.sendall(dados_json.encode('utf-8')) 
            print("Enviado: <WORKER:ALIVE>")

            

            # Aguardar a tarefa do servidor
            task_message_bytes = client_socket.recv(4096)
            if not task_message_bytes:
                print("Conexão fechada pelo servidor antes de receber a tarefa.")
                return

            # Decodificamos os bytes recebidos para string e então para JSON
            task_data = json.loads(task_message_bytes.decode('utf-8'))
            
            if task_data.get("TASK") == "QUERY":
                cpf_alvo = task_data.get("USER")
                print(f"Tarefa recebida do servidor: Buscar saldo para o CPF {cpf_alvo}")
                # Executar a função de busca
                resultado_busca = buscar_saldo(cpf_alvo)
                
                response_message = {}
                if resultado_busca:
                    nome, saldo_decimal, timestamp = resultado_busca
                    saldo_json_serializable = float(saldo_decimal)
                    
                    # Montar a mensagem de resposta com sucesso
                    response_message = {
                        "WORKER": "Joao Gabriel",
                        "CPF": cpf_alvo,
                        "SALDO": saldo_json_serializable,
                        "TASK": "QUERY",
                        "STATUS": "OK"
                    }
                    print(f"Resposta enviada: <WORKER:JOAO GABRIEL; CPF:{cpf_alvo}; SALDO:{saldo_json_serializable}; TASK:QUERY; STATUS:OK;>")
                else:
                    # Montar a mensagem de resposta de falha (CPF não encontrado)
                    response_message = {
                        "WORKER": "Joao Gabriel",
                        "CPF": cpf_alvo,
                        "TASK": "QUERY",
                        "STATUS": "NOK"
                    }
                    print(f"Resposta enviada: <WORKER:JOAO GABRIEL; CPF:{cpf_alvo}; TASK:QUERY; STATUS:NOK;>")
                
                # 7. Enviar a resposta final de volta para o servidor
                client_socket.sendall(json.dumps(response_message).encode('utf-8'))

            if task_data.get("TASK") == "UPDATE":
                cpf_alvo = task_data.get("CPF")
                print(f"Tarefa recebida do servidor: Buscar saldo para o CPF {cpf_alvo}")
                
                # Executar a função de busca
                resultado_busca = atualizar_saldo(cpf_alvo)
                
                response_message = {}
                if resultado_busca:
                    nome, saldo_decimal, timestamp = resultado_busca
                    saldo_json_serializable = float(saldo_decimal)
                    
                    # Montar a mensagem de resposta com sucesso
                    response_message = {
                        "WORKER": "Joao Gabriel",
                        "CPF": cpf_alvo,
                        "SALDO": saldo_json_serializable,
                        "TASK": "UPDATE",
                        "STATUS": "OK"
                    }
                    print(f"Resposta enviada: <WORKER:JOAO GABRIEL; CPF:{cpf_alvo}; SALDO:{saldo_json_serializable}; TASK:UPDATE; STATUS:OK;>")
                else:
                    # Montar a mensagem de resposta de falha (CPF não encontrado)
                    response_message = {
                        "WORKER": "Joao Gabriel",
                        "CPF": cpf_alvo,
                        "TASK": "UPDATE",
                        "STATUS": "NOK"
                    }
                    print(f"Resposta enviada: <WORKER:JOAO GABRIEL; CPF:{cpf_alvo}; TASK:UPDATE; STATUS:NOK;>")
                
                # 7. Enviar a resposta final de volta para o servidor
                client_socket.sendall(json.dumps(response_message).encode('utf-8'))
    except ConnectionRefusedError:
        print(f"Erro: Conexão recusada. Verifique se o servidor está em execução em {endereco}:{porta}.")
    except socket.timeout:
        print("Erro: A conexão expirou (timeout). O servidor pode estar ocupado ou não respondendo.")
    except Exception as e:
        print(f"Ocorreu um erro inesperado: {e}")

if __name__ == "__main__":
    ENDERECO_IP = '10.62.217.32'
    PORTA = 5900

    run_client(ENDERECO_IP, PORTA)
