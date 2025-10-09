"""
server_lib/logger.py
Configuração do logger global usando loguru.
"""

from loguru import logger
from random import randint
import sys

ARQUIVO_LOG = 'log_server.log'
IDENTIFICACAO = randint(10,100000000)



# Remove quaisquer sinks anteriores para evitar duplicação
logger.remove()

# Sink: arquivo
logger.add(ARQUIVO_LOG, format="<green>{time:DD/MM/YYYY HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - | <level>{message}</level>", level="INFO")

# Sink: console (stdout)
logger.add(sys.stdout, format="<green>{time:DD/MM/YYYY HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - | <level>{message}</level>", level="INFO")

logger = logger.bind(id=IDENTIFICACAO)
