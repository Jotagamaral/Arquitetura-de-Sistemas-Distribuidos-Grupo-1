# run_worker.py
from .dist_worker import Worker
from logs.logger import logger

WORKER_CONFIG_PATH = "worker/config.json"

if __name__ == "__main__":
    worker = None
    try:
        logger.info("Iniciando o worker...")
        # Você pode passar um config aqui se quiser no futuro
        worker = Worker(config_path=WORKER_CONFIG_PATH) 
        # start() agora é o loop principal e vai bloquear a execução aqui
        worker.start() 
    
    except KeyboardInterrupt:
        logger.warning("Recebido sinal de encerramento. Parando worker...")
        if worker:
            worker.stop()
        logger.info("Worker encerrado pelo usuário.")
    
    except Exception as e:
        logger.critical(f"Falha ao iniciar o worker: {e}", exc_info=True)
        if worker:
            worker.stop()