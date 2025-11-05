# run_server.py
from .dist_server import Server
from .logs.logger import logger # Supondo que o logger está no mesmo nível

if __name__ == "__main__":
    try:
        logger.info("Iniciando o servidor...")
        # Aponta para o seu config
        server = Server(config_path="server/config.json") 
        # O server.start() agora chama o _wait_for_shutdown internamente
        server.start() 
    except Exception as e:
        logger.critical(f"Falha ao iniciar o servidor: {e}")