"""
worker_lib/state.py
Armazena informações dinâmicas sobre o estado de conexão do Worker.
"""
from typing import Dict

# Servidor mestre atual (pode mudar via redirecionamento)
current_master: Dict[str, any] = {'ip': None, 'port': None}

# Servidor "pai" (Home Master) — sempre o ponto de retorno padrão
home_master: Dict[str, any] = {'ip': None, 'port': None}
