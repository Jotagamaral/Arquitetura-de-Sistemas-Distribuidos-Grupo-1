"""
worker_lib/logger.py
Configuração do logger global usando loguru.
"""

from loguru import logger     # Biblioteca para logs formatados e coloridos
from random import randint    # Gera ID aleatório do log
import sys                    # Permite enviar logs também ao terminal

# Nome do arquivo de log
ARQUIVO_LOG = 'log_worker.log'
IDENTIFICACAO = randint(10, 100000000)

# Remove loggers anteriores e adiciona novo com formato personalizado
logger.remove()
logger.add(
    ARQUIVO_LOG,
    format="<green>{time:DD/MM/YYYY HH:mm:ss}</green> | <level>{level: <8}</level> "
           "| <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
           "<level>{message}</level>",
    level="INFO",
    rotation="10 MB",   # Cria novo arquivo ao atingir 10 MB
    catch=True
)

# Também mostra os logs no terminal
logger.add(
    sys.stdout,
    format="<green>{time:DD/MM/YYYY HH:mm:ss}</green> | <level>{level: <8}</level> "
           "| <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
           "<level>{message}</level>",
    level="INFO"
)

# Associa um ID aleatório ao logger para rastreamento
logger = logger.bind(id=IDENTIFICACAO)

