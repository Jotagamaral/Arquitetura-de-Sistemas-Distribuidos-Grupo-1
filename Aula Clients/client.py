import websockets
import json
from datetime import datetime
import mysql.connector
from mysql.connector import Error
import asyncio

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
            password='Batata-Fr1t@',
            database='sys'
        )
        
        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)
            
            # Consulta SQL para buscar o nome do cliente e o saldo da conta
            # A consulta faz um JOIN entre as tabelas CLIENTE e CONTA
            sql_query = """
                SELECT C.NOME, A.SALDO 
                FROM CONTA AS A
                JOIN CLIENTE AS C ON A.ID_CLIENTE = C.ID_CLIENTE
                WHERE C.CPF = %s
            """
            
            cursor.execute(sql_query, (cpf,))
            
            usuario = cursor.fetchone()

            if usuario:
                # Retorna a tupla com o nome, o saldo e a data/hora atuais
                return (usuario['NOME'], usuario['SALDO'], datetime.now().isoformat())
            
    except Error as e:
        print(f"Erro ao conectar ou executar a consulta no MySQL: {e}")
        return None
    
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print("Conexão com o MySQL fechada.")

    return None

async def run_client():
    uri = "ws://localhost:8765"
    try:
        async with websockets.connect(uri) as websocket:
            print("Cliente conectado ao servidor.")
            
            # 1. Enviar a flag de 'alive'
            alive_message = {
                "flag": "WORKER:ALIVE"
            }
            await websocket.send(json.dumps(alive_message))
            print("Enviado: <WORKER:ALIVE>")

            # 2. Aguardar a tarefa do servidor
            task_message = await websocket.recv()
            task_data = json.loads(task_message)
            
            if task_data.get("task") == "QUERY":
                cpf_alvo = task_data.get("user_id")
                print(f"Tarefa recebida do servidor: Buscar saldo para o CPF {cpf_alvo}")
                
                # 3. Executar a função de busca
                resultado_busca = buscar_saldo(cpf_alvo)
                
                if resultado_busca:
                    nome, saldo_decimal, update_at = resultado_busca

                    # Converte o objeto Decimal para float ou string
                    saldo_json_serializable = float(saldo_decimal)
                    
                    # 4. Enviar o resultado de volta para o servidor
                    response_message = {
                        "cpf": cpf_alvo,
                        "saldo": saldo_json_serializable,
                        "task": "QUERY",
                        "status": "OK",
                        "update_at": update_at
                    }
                    await websocket.send(json.dumps(response_message))
                    print(f"Resposta enviada: <CPF:{cpf_alvo}; SALDO:{saldo_json_serializable}; TASK:QUERY; STATUS:OK>")
                else:
                    # Se o CPF não for encontrado
                    response_message = {
                        "cpf": cpf_alvo,
                        "task": "QUERY",
                        "status": "NOK"
                    }
                    await websocket.send(json.dumps(response_message))
                    print(f"Resposta enviada: <CPF:{cpf_alvo}; TASK:QUERY; STATUS:NOK>")
                    
    except ConnectionRefusedError:
        print("Erro: Não foi possível conectar ao servidor. Verifique se o server.py está em execução.")
    except Exception as e:
        print(f"Ocorreu um erro: {e}")

if __name__ == "__main__":
    asyncio.run(run_client())