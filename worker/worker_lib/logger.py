"""
worker_lib/logger.py
Configuração do logger global usando loguru.
"""

from loguru import logger
from random import randint
import sys

# Nome do arquivo de log para o worker
ARQUIVO_LOG = 'log_worker.txt'
IDENTIFICACAO = randint(10, 100000000)

# Limpa configurações anteriores e adiciona a nova
logger.remove()
logger.add(
    ARQUIVO_LOG,
    format="<green>{time:DD/MM/YYYY HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
    rotation="10 MB",
    catch=True
)

# Adiciona também sink para console (stdout) para aparecer no terminal
logger.add(
    sys.stdout, 
    format="<green>{time:DD/MM/YYYY HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>", 
    level="INFO"
)

logger = logger.bind(id=IDENTIFICACAO)