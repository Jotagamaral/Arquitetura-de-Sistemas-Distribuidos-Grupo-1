"""
worker_lib/state.py
Variáveis de estado dinâmico do Worker.
"""
from typing import Dict

# Dicionário que armazena o endereço do servidor mestre atual.
# Pode ser alterado por um comando de REDIRECT.
current_master: Dict[str, any] = {
    'ip': None,
    'port': None
}

# Dicionário que armazena o endereço do servidor "pai", para onde o worker
# deve retornar caso a conexão com um mestre temporário falhe.
home_master: Dict[str, any] = {
    'ip': None,
    'port': None
}