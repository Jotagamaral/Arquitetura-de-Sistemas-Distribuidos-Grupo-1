
"""
worker_lib/config.py
Configurações e parâmetros do Worker. Edite conforme necessário.
"""

# Altere este ID para identificar seu worker. Pode ser o nome da máquina, etc.
WORKER_ID = 'WORKER_CARLOS_01'

# --- PONTO DE ATENÇÃO ---
# Endereço do Servidor "Pai" (Home Master).
# O Worker tentará se conectar a este servidor ao iniciar e sempre que
# perder a conexão com um servidor temporário.
#
# Para testar na mesma máquina, você pode usar '127.0.0.1' e a porta
# de um dos servidores que você criou anteriormente (ex: 8765).
HOME_MASTER_IP = '127.0.0.1'
# Ajuste esta porta para apontar ao servidor (ex: 8765)
HOME_MASTER_PORT = 8765

# Tempo em segundos que o worker espera antes de tentar se reconectar
# a um servidor que caiu.
RECONNECT_DELAY = 10  # segundos