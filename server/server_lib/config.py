"""
server_lib/config.py
Configurações e parâmetros do servidor. Edite conforme necessário para cada instância.
"""

MY_IP = '127.0.0.1'
MY_PORT = 8765
MY_ID = f'SERVER_1'

# Configuração para conexão com Servers
PEER_SERVERS = [
    {'ip': '127.0.0.1', 'port': 8766, 'id': f'SERVER_2'},
]

lista_peers = list(PEER_SERVERS) # Lista de peers dinâmica

HEARTBEAT_INTERVAL = 10  # segundos
HEARTBEAT_TIMEOUT = 25   # segundos

HEARTBEAT_RETRIES = 5           # Número de tentativas de conexão
HEARTBEAT_RETRY_DELAY = 2       # Segundos de espera entre cada tentativa

# Load / capacity threshold monitoring
# Janela (segundos) para medir throughput (ex.: últimos 60 segundos)
THRESHOLD_WINDOW = 20
# Número mínimo de tarefas completadas aceitável na janela acima; se ficar
# abaixo disso, o servidor pedirá workers a peers
THRESHOLD_MIN_TASKS = 2

# Critério simples para considerar um worker 'ocioso' e elegível para ser
# movido: tempo em segundos desde o último trabalho
IDLE_WORKER_THRESHOLD = 20

# Intervalo de checagem do load-balancer (segundos)
LOAD_BALANCER_INTERVAL = 10

