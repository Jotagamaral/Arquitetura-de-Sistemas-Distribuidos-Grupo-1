# worker
import socket
import psycopg2

# --- Constantes de Conexão ---
HOST_SERVIDOR = 'localhost' # Usaremos localhost para facilitar os testes
PORTA_SERVIDOR = 65432

# --- Configuração do Banco de Dados ---
DB_CONFIG = {
    "dbname": "base",
    "user": "postgres",
    "password": "ceub123456",
    "host": "localhost",
    "port": "5432"
}

# 1. FUNÇÃO DE TRABALHO (equivalente à função 'eh_primo' do exemplo)
def buscar_saldo_por_cpf(cpf: str):
    """
    Função de lógica: recebe um CPF, busca no banco e retorna (saldo, updated_at).
    """
    conn = None
    cur = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        sql_query = """
            SELECT c.saldo, c.updated_at 
            FROM contas as c 
            JOIN users as u ON c.fk_id_user = u.id
            WHERE u.cpf = %s;
        """
        cur.execute(sql_query, (cpf,))
        return cur.fetchone()
    except Exception as e:
        print(f"❌ Erro ao buscar no banco de dados: {e}")
        return None
    finally:
        if cur: cur.close()
        if conn: conn.close()

# 2. FUNÇÃO PRINCIPAL DE COMUNICAÇÃO (equivalente à 'worker_cliente')
def worker_main():
    """
    Função principal que executa a lógica de comunicação do Worker.
    """
    # Utiliza o 'with' para garantir que o socket seja fechado
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        print("--- 🛠️  Worker INICIADO ---")
        s.connect((HOST_SERVIDOR, PORTA_SERVIDOR))
        print(f"Conectado ao Coordenador em {HOST_SERVIDOR}:{PORTA_SERVIDOR}")
        
        # Etapa 1: Envia a flag de que está vivo
        s.sendall(b"<WORKER:ALIVE>")
        print("Enviado: <WORKER:ALIVE>")

        # Etapa 2: Aguarda a tarefa do Coordenador
        data = s.recv(1024).decode('utf-8')
        print(f"Tarefa recebida: {data}")

        # Etapa 3: Processa a tarefa
        if "TASK:QUERY" in data:
            cpf_para_buscar = data.split(';')[0].split(':')[1].replace('>', '')
            
            # Chama a função de trabalho para consultar o banco
            print(f"Buscando dados para o CPF: {cpf_para_buscar}...")
            dados_banco = buscar_saldo_por_cpf(cpf_para_buscar)

            # Etapa 4: Formata e envia a resposta para o Coordenador
            if dados_banco:
                saldo = dados_banco[0]
                resposta = f"<CPF:{cpf_para_buscar};SALDO:{saldo};TASK:QUERY;STATUS:OK>"
            else:
                resposta = f"<CPF:{cpf_para_buscar};TASK:QUERY;STATUS:NOK>"
            
            print(f"Enviando resposta: {resposta}")
            s.sendall(resposta.encode('utf-8'))

    print("--- ✅ Worker FINALIZADO ---")


# --- Ponto de entrada do programa ---
if __name__ == "__main__":
    worker_main()