import asyncio
import websockets
import json
from datetime import datetime

async def handle_connection(websocket):
    """
    Gerencia a conexão com um cliente (worker).
    """
    print("Novo cliente (worker) conectado.")
    try:
        # 1. Aguarda a flag de 'alive' do worker
        message = await websocket.recv()
        data = json.loads(message)
        
        if data.get("flag") == "WORKER:ALIVE":
            print(f"Worker reportando: {data['flag']}")

            # 2. Envia a tarefa para o worker buscar o saldo
            # O CPF agora é a chave para a busca no banco de dados do worker
            cpf_alvo = "11111111111" 
            task_message = {
                "user_id": cpf_alvo,
                "task": "QUERY",
                "flag": f"<USER:{cpf_alvo}; TASK:QUERY>"
            }
            await websocket.send(json.dumps(task_message))
            print(f"Tarefa enviada para o worker: {json.dumps(task_message)}")

            # 3. Aguarda o retorno do worker com o saldo
            response_message = await websocket.recv()
            response_data = json.loads(response_message)
            
            if response_data.get("status") == "OK":
                print("\n--- Resposta do Worker ---")
                print(f"CPF: {response_data['cpf']}")
                print(f"Saldo: R$ {response_data['saldo']:.2f}")
                print(f"Última atualização: {response_data['update_at']}")
                print("--------------------------\n")
            else:
                print(f"Erro na resposta do worker: {response_data.get('status')}. CPF não encontrado.")

    except websockets.exceptions.ConnectionClosed as e:
        print(f"Conexão fechada inesperadamente: {e}")
    except json.JSONDecodeError:
        print("Erro ao decodificar JSON. Mensagem recebida inválida.")
    except Exception as e:
        print(f"Ocorreu um erro inesperado: {e}")

async def main():
    """
    Inicia e executa o servidor WebSocket.
    """
    # Define o servidor para rodar em localhost na porta 8765
    async with websockets.serve(handle_connection, "localhost", 8765):
        print("Servidor WebSockets iniciado em ws://localhost:8765")
        # Mantém o servidor rodando infinitamente
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())