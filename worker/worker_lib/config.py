"""
worker_lib/config.py
Configurações e parâmetros do Worker.
"""

# Identificação única do worker (pode ser o nome da máquina)
WORKER_ID = 'WORKER_CARLOS_01'

# Endereço e porta do servidor principal (Home Master)
HOME_MASTER_IP = '127.0.0.1'     # Localhost (para testes locais)
HOME_MASTER_PORT = 8765          # Porta usada na comunicação

# Tempo (em segundos) antes de tentar reconectar após falha
RECONNECT_DELAY = 10
