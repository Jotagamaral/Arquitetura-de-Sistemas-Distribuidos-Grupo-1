# run_worker.py
from worker_lib import Worker
from logs.logger import logger
import os

# Defina o caminho para o seu novo arquivo de configuração
CONFIG_FILE_PATH = "config.json"

if __name__ == "__main__":
    # Garante que o diretório de logs existe
    os.makedirs("logs", exist_ok=True) 
    
    try:
        # 1. Cria a instância do Worker, passando o caminho do config
        worker = Worker(config_path=CONFIG_FILE_PATH) 
        
        # 2. Inicia o loop principal
        worker.start() 
        
    except KeyboardInterrupt:
        logger.info("Worker encerrado pelo usuário.")
        if 'worker' in locals():
            worker.stop() # Sinaliza para o loop parar
    except FileNotFoundError:
        # Erro comum se o config.json não for encontrado
        logger.critical(f"Arquivo de configuração '{CONFIG_FILE_PATH}' não encontrado.")
    except Exception as e:
        logger.critical(f"Erro crítico não tratado: {e}")