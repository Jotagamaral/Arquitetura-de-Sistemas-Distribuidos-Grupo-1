import threading
import time
from config import ENDERECO_IP, PORTA, NUMERO_DE_CLIENTES_SIMULTANEOS, INTERVALO_ENTRE_RAJADAS_SEGUNDOS
from network.client_worker import run_worker_session

if __name__ == "__main__":
    worker_counter = 0
    try:
        print(f"Iniciando teste de estresse contra {ENDERECO_IP}:{PORTA}")
        print(f"Lançando {NUMERO_DE_CLIENTES_SIMULTANEOS} clientes a cada {INTERVALO_ENTRE_RAJADAS_SEGUNDOS} segundo(s).")
        print("Pressione Ctrl+C para parar.")
        while True:
            print(f"\n--- Disparando rajada de {NUMERO_DE_CLIENTES_SIMULTANEOS} clientes ---")
            for i in range(NUMERO_DE_CLIENTES_SIMULTANEOS):
                worker_counter += 1
                thread = threading.Thread(
                    target=run_worker_session,
                    args=(ENDERECO_IP, PORTA, worker_counter)
                )
                thread.start()
            time.sleep(INTERVALO_ENTRE_RAJADAS_SEGUNDOS)
    except KeyboardInterrupt:
        print("\nTeste de estresse interrompido pelo usuário. Encerrando.")
