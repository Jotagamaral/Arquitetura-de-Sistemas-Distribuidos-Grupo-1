import sys
from loguru import logger

# 1. Remove o handler padrão
logger.remove()

# 2. Adiciona o handler do CONSOLE (é bom ter em todos os processos)
logger.add(
    sys.stdout,
    colorize=True,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}:{function}</cyan> - <level>{message}</level>",
    level="INFO",
    # O "enqueue=True" torna o log de console thread-safe
    enqueue=True 
)

def setup_file_logging(process_id: str):
    """
    Configura os handlers de ARQUIVO para um ID de processo específico.
    Isso cria arquivos de log separados por processo.
    """
    
    # Garante que o ID seja seguro para um nome de arquivo
    safe_id = "".join(c for c in process_id if c.isalnum() or c in ('_', '-')).strip()
    if not safe_id:
        safe_id = "unknown_process"
    
    # Define os caminhos de arquivo baseados no ID
    log_path_base = f"logs/{safe_id}" # Ex: "logs/SERVER_1" ou "logs/WORKER_abc123"

    logger.info(f"Configurando logs em arquivo para: {safe_id}")

    # 3. Adiciona o SINK DE ATIVIDADE (específico do processo)
    logger.add(
        f"{log_path_base}_activity.log",
        rotation="10 MB",
        retention="7 days",
        format="{time:DD/MM/YYYY HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="INFO",
        encoding="utf-8",
        enqueue=True # Torna o log de arquivo seguro entre threads
    )

    # 4. Adiciona o SINK DE ERRO (específico do processo)
    logger.add(
        f"{log_path_base}_error.log",
        rotation="5 MB",
        retention="30 days",
        format="{time:DD/MM/YYYY HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="WARNING", # Captura WARNING, ERROR, CRITICAL
        encoding="utf-8",
        enqueue=True
    )
    
    logger.success(f"Logs de arquivo configurados. Saída em: {log_path_base}_*.log")

# Não exportamos mais um logger com filtros de módulo,
# pois agora filtramos por arquivos separados.