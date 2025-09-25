# coordenador
import socket

# --- Constantes de Conexão ---
HOST = 'localhost'
PORT = 65432

def coordenador_main():
    """
    Função principal que executa a lógica do servidor Coordenador.
    """
    print("--- 🚀 Servidor Coordenador INICIADO ---")

    # Utiliza o 'with' para garantir que o socket seja fechado corretamente
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"Aguardando conexão do Worker na porta {PORT}...")
        
        # Aceita a conexão do Worker (o 'with' também fecha a conexão do cliente)
        conn, addr = s.accept()
        with conn:
            print(f"✅ Worker conectado por {addr}")
            
            # 1. Recebe a mensagem de "estou vivo" do Worker
            data = conn.recv(1024).decode('utf-8')
            print(f"Recebido do Worker: {data}")

            if data == "<WORKER:ALIVE>":
                # 2. Envia a tarefa para o Worker
                cpf_para_buscar = "11111111111"
                mensagem_tarefa = f"<USER:{cpf_para_buscar};TASK:QUERY>"
                print(f"Enviando tarefa para o Worker: {mensagem_tarefa}")
                conn.sendall(mensagem_tarefa.encode('utf-8'))

                # 3. Aguarda o resultado final do Worker
                resultado_worker = conn.recv(1024).decode('utf-8')
                print("\n--- 🏁 RESULTADO FINAL RECEBIDO ---")
                print(resultado_worker)
                print("---------------------------------")

    print("--- 🛑 Servidor Coordenador FINALIZADO ---")

# --- Ponto de entrada do programa ---
# Garante que a função principal só seja executada quando o script for rodado diretamente
if __name__ == "__main__":
    coordenador_main()