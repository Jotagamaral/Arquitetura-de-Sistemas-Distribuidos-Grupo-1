# server/run_server.py
import sys
import os

# Imports relativos
from .dist_server import Server
from logs.logger import logger

if __name__ == "__main__":
    
    # --- LÓGICA DE ARGUMENTOS ---
    
    # 1. Checa se um argumento foi passado (o argumento 0 é o nome do script)
    if len(sys.argv) < 2:
        logger.critical("ERRO: Você deve especificar o caminho para o arquivo de configuração.")
        logger.critical("Exemplo: python -m server.run_server server/config_s1.json")
        sys.exit(1) # Encerra o script
    
    # 2. Pega o caminho do config a partir do argumento
    config_path = sys.argv[1]
    
    # 3. Checa se o arquivo existe
    #    (O comando 'python -m' roda da raiz, então o caminho deve ser completo)
    if not os.path.exists(config_path):
        logger.critical(f"ERRO: Arquivo de configuração não encontrado em: {config_path}")
        sys.exit(1)
        
    
    try:
        logger.info(f"Iniciando o servidor com config: {config_path}...")
        
        # 4. Usa o caminho do argumento para iniciar o servidor
        server = Server(config_path=config_path) 
        
        server.start() 
    
    except Exception as e:
        logger.critical(f"Falha ao iniciar o servidor: {e}", exc_info=True)