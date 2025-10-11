"""
worker_runner.py
Arquivo principal para rodar o Worker.
"""

from worker_lib.logger import logger
from worker_lib.config import WORKER_ID, HOME_MASTER_IP, HOME_MASTER_PORT
from worker_lib.worker_main import main_loop
import worker_lib.state as state

if __name__ == "__main__":
    logger.info(f"Iniciando Worker ID: {WORKER_ID}")

    # Define o servidor "pai" e o servidor atual (inicialmente o mesmo)
    state.home_master['ip'] = HOME_MASTER_IP
    state.home_master['port'] = HOME_MASTER_PORT
    state.current_master.update(state.home_master)

    try:
        main_loop()  # Inicia o loop principal
    except KeyboardInterrupt:
        logger.info("Worker encerrado pelo usuário.")
    except Exception as e:
        logger.critical(f"Erro crítico: {e}")
