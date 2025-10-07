"""
worker_lib/logger.py
Configuração do logger global usando loguru.
"""

from loguru import logger
from random import randint

# Nome do arquivo de log para o worker
ARQUIVO_LOG = 'log_worker.txt'
IDENTIFICACAO = randint(10, 100000000)

# Limpa configurações anteriores e adiciona a nova
logger.remove()
logger.add(
    ARQUIVO_LOG,
    format="<green>{time:DD/MM/YYYY HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
    rotation="10 MB",  # Rotaciona o arquivo de log quando atinge 10 MB
    catch=True         # Captura exceções inesperadas
)

logger = logger.bind(id=IDENTIFICACAO)