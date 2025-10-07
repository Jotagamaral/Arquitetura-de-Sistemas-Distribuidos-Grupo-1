"""
worker_runner.py
Arquivo principal para rodar o Worker.
"""

from worker_lib.config import WORKER_ID, HOME_MASTER_IP, HOME_MASTER_PORT
from worker_lib.worker_main import main_loop
from worker_lib.logger import logger
import worker_lib.state as state

if __name__ == "__main__":
    logger.info(f"Iniciando Worker ID: {WORKER_ID}")

    # Configuração inicial do estado. O worker sempre começa apontando para seu "servidor pai".
    state.home_master['ip'] = HOME_MASTER_IP
    state.home_master['port'] = HOME_MASTER_PORT
    state.current_master['ip'] = HOME_MASTER_IP
    state.current_master['port'] = HOME_MASTER_PORT

    try:
        # Inicia o loop principal que gerencia a conexão e as tarefas.
        main_loop()
    except KeyboardInterrupt:
        logger.info("Worker encerrado pelo usuário.")
    except Exception as e:
        logger.critical(f"Erro crítico não tratado no worker_runner: {e}")