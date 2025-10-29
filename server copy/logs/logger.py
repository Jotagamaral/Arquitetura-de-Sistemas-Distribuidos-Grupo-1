"""
logs/logger.py
Configuração do logger global usando loguru.
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

# 3. Configura o SINK DO ARQUIVO DE ATIVIDADE GERAL
#    - Guarda tudo que for INFO, SUCCESS, WARNING, ERROR, CRITICAL em um único arquivo.
logger.add(
    "logs/activity.log",
    rotation="10 MB",  # Rotaciona o arquivo quando atingir 10MB
    retention="7 days", # Mantém os logs dos últimos 7 dias
    format="{time:DD/MM/YYYY HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
    level="INFO",
    encoding="utf-8"
)

# 4. Configura o SINK DO ARQUIVO DE ERROS
#    - Guarda apenas WARNING, ERROR, CRITICAL. Essencial para debugging rápido.
logger.add(
    "logs/error.log",
    rotation="5 MB",
    retention="30 days",
    format="{time:DD/MM/YYYY HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
    level="WARNING", # <--- Nível mínimo para este arquivo
    encoding="utf-8"
)

# 5. (OPCIONAL) Configura SINKS específicos por MÓDULO
#    - Usa um filtro para direcionar logs de um módulo específico para um arquivo separado.
#    - Ótimo para depurar o heartbeat ou o load_balancer sem o ruído do resto do sistema.
logger.add(
    "logs/heartbeat.log",
    filter=lambda record: "heartbeat" in record["name"], # <--- A mágica do filtro
    format="{time:HH:mm:ss} | {level: <7} | {message}",
    level="INFO"
)

logger.info("Sistema de logs inicializado. As saídas serão distribuídas.")

# Não é mais necessário o .bind() aqui, vamos usar contextualização.