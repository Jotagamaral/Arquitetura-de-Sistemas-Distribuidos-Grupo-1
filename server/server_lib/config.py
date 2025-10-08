"""
server_lib/config.py
Configurações e parâmetros do servidor. Edite conforme necessário para cada instância.
"""

MY_IP = '127.0.0.1'
MY_PORT = 8765
MY_ID = f'SERVER_{MY_PORT}'

# Configuração para conexão com Servers
PEER_SERVERS = [
    {'ip': '127.0.0.1', 'port': 8766, 'id': f'SERVER_8766'},
]

HEARTBEAT_INTERVAL = 10  # segundos
HEARTBEAT_TIMEOUT = 25   # segundos

# Configuração para conexão com Workers
WORKER_PEERS = [
    {'ip': '127.0.0.1', 'port': 5901, 'id': 'WORKER_5901'},
]

WORKER_POLL_INTERVAL = 15   # segundos
WORKER_CONNECT_TIMEOUT = 5  # segundos
