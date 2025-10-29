"""
worker_lib/logger.py
Configuração do logger global para o Worker usando loguru.
"""
from loguru import logger
import sys

# 1. Remove a configuração padrão para começar do zero
logger.remove()

# 2. Configura o SINK DO CONSOLE (para visualização em tempo real)
#    - Nível: INFO para cima.
#    - Formato: Mais simples e colorido para leitura rápida.
logger.add(
    sys.stdout,
    colorize=True,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}:{function}</cyan> - <level>{message}</level>",
    level="INFO"
)

# 3. Configura o SINK DO ARQUIVO DE ATIVIDADE GERAL DO WORKER
#    - Guarda tudo que for INFO, SUCCESS, WARNING, ERROR, CRITICAL.
logger.add(
    "logs/activity.log",  # Nome de arquivo específico para o worker
    rotation="5 MB",   # Rotaciona o arquivo quando atingir 5MB (workers tendem a logar menos)
    retention="7 days", # Mantém os logs dos últimos 7 dias
    format="{time:DD/MM/YYYY HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
    level="INFO",
    encoding="utf-8"
)

# 4. Configura o SINK DO ARQUIVO DE ERROS DO WORKER
#    - Guarda apenas WARNING, ERROR, CRITICAL. Essencial para debugging rápido.
logger.add(
    "logs/error.log",  # Nome de arquivo específico para o worker
    rotation="2 MB",
    retention="30 days",
    format="{time:DD/MM/YYYY HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
    level="WARNING", # Nível mínimo para este arquivo
    encoding="utf-8"
)

logger.info("Sistema de logs do Worker inicializado.")

# A antiga linha "logger = logger.bind(id=...)" foi removida.
# É melhor adicionar o WORKER_ID como contexto no ponto de entrada do programa.