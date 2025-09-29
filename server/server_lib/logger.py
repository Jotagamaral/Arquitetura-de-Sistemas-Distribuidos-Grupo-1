"""
server_lib/logger.py
Configuração do logger global usando loguru.
"""

from loguru import logger
from random import randint

ARQUIVO_LOG = 'log_server.txt'
IDENTIFICACAO = randint(10,100000000)


logger.add(ARQUIVO_LOG, format="<green>{time:DD/MM/YYYY HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - | <level>{message}</level>", level="INFO")
logger = logger.bind(id=IDENTIFICACAO)
